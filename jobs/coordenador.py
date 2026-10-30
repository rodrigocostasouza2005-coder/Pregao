# -*- coding: utf-8 -*-
"""Worker independente do Coordenador de Inteligência / Backoffice
(auditoria 2026-10-29 - ver docs/auditoria-coordenador-inteligencia-
20261029.md). NÃO é um coletor novo, NÃO é uma inteligência nova: só
agenda duas funções Python que já existiam, já são testadas e já
persistem no Supabase, mas que até aqui só rodavam quando um usuário
abria uma aba do Streamlit:

- data.market_researcher.registrar_achados_atuais(): memória
  operacional do Backoffice (market_researcher_achados) - achados
  priorizados do painel de SAÚDE DOS DADOS.
- data.sintese_mercado.obter_sintese_mercado(): síntese executiva via
  IA (resumos_ia_cache, origem='sintese_mercado') - cacheada por bucket
  de 20min (ver data/sintese_mercado.py:_BUCKET_MINUTOS), então chamar
  isto a cada ~30min (mesma cadência de .github/workflows/coletores-
  nuvem.yml) gera no máximo 1 síntese nova por bucket, nunca gasta
  cota de IA em duplicidade.

Os dois rodam de forma INDEPENDENTE (mesmo princípio de
data/market_makers.py e data/sintese_mercado.py: falha de um nunca
contamina o outro) e cada execução é registrada em
coordenador_execucoes (sql/coordenador.sql) com duração, resultado e
erro - histórico que não existia antes (coletores_status é por
COLETOR individual, não pela rodada do job que os consolida)."""
import time
from datetime import datetime, timezone

from data.market_researcher import registrar_achados_atuais
from data.sintese_mercado import obter_sintese_mercado
from data.supabase_client import obter_cliente

_TABELA_EXECUCOES = "coordenador_execucoes"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iniciar_execucao(cliente, tipo: str) -> int | None:
    """Reserva uma linha EM_ANDAMENTO pra esta rodada - None se o
    Supabase estiver indisponível (quem chama não trava por isso, só
    não terá o log desta rodada, mesmo espírito de todo o resto do
    projeto: log é auditoria, nunca bloqueia o fluxo principal)."""
    if cliente is None:
        return None
    try:
        resp = cliente.table(_TABELA_EXECUCOES).insert({
            "tipo": tipo, "status": "EM_ANDAMENTO", "iniciado_em": _agora_iso(),
        }).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception as exc:
        print(f"[coordenador] _iniciar_execucao({tipo}) falhou: {exc!r}")
        return None


def _concluir_execucao(cliente, execucao_id: int | None, *, status: str, duracao_ms: int, resumo: str | None = None, erro: str | None = None) -> None:
    if cliente is None or execucao_id is None:
        return
    try:
        cliente.table(_TABELA_EXECUCOES).update({
            "status": status, "concluido_em": _agora_iso(), "duracao_ms": duracao_ms,
            "resumo": resumo, "erro": erro,
        }).eq("id", execucao_id).execute()
    except Exception as exc:
        print(f"[coordenador] _concluir_execucao({execucao_id}) falhou: {exc!r}")


def _rodar_backoffice(cliente) -> bool:
    """Snapshot dos achados atuais do painel de saúde (Backoffice) -
    nunca lança excecao pra fora: qualquer falha fica registrada em
    coordenador_execucoes e devolve False, sem impedir a síntese de
    rodar a seguir."""
    execucao_id = _iniciar_execucao(cliente, "backoffice")
    inicio = time.monotonic()
    try:
        resultado = registrar_achados_atuais()
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        if resultado.get("ok"):
            _concluir_execucao(cliente, execucao_id, status="OK", duracao_ms=duracao_ms,
                                resumo=f"{resultado.get('achados_atuais', 0)} achado(s) atual(is)")
            return True
        _concluir_execucao(cliente, execucao_id, status="ERRO", duracao_ms=duracao_ms,
                            erro=str(resultado.get("motivo") or "falha não especificada"))
        return False
    except Exception as exc:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        print(f"[coordenador] backoffice falhou: {exc!r}")
        _concluir_execucao(cliente, execucao_id, status="ERRO", duracao_ms=duracao_ms, erro=repr(exc))
        return False


def _rodar_sintese(cliente) -> bool:
    """Gera (ou confirma cache do bucket atual) a síntese executiva via
    IA - mesma função e mesmas regras de data/sintese_mercado.py, só
    chamada por agendamento em vez de só sob demanda."""
    execucao_id = _iniciar_execucao(cliente, "sintese")
    inicio = time.monotonic()
    try:
        resultado = obter_sintese_mercado()
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        if resultado.get("ok"):
            rotulo = "gerada agora" if resultado.get("atual") else "reaproveitada (anterior)"
            _concluir_execucao(cliente, execucao_id, status="OK" if resultado.get("atual") else "PARCIAL",
                                duracao_ms=duracao_ms, resumo=f"síntese {rotulo}")
            return True
        _concluir_execucao(cliente, execucao_id, status="ERRO", duracao_ms=duracao_ms,
                            erro=str(resultado.get("motivo") or "falha não especificada"))
        return False
    except Exception as exc:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        print(f"[coordenador] síntese falhou: {exc!r}")
        _concluir_execucao(cliente, execucao_id, status="ERRO", duracao_ms=duracao_ms, erro=repr(exc))
        return False


def executar() -> int:
    """Roda backoffice e síntese de forma independente (uma falha nunca
    impede a outra de rodar) - 0 se as duas funcionaram, 1 se qualquer
    uma falhou (visível no log do GitHub Actions; nenhuma das duas
    envia e-mail nem alerta ninguém, só persiste estado pra interface
    web ler)."""
    cliente = obter_cliente()
    if cliente is None:
        print("[coordenador] Supabase indisponível - nada a fazer nesta rodada")
        return 1
    ok_backoffice = _rodar_backoffice(cliente)
    ok_sintese = _rodar_sintese(cliente)
    return 0 if (ok_backoffice and ok_sintese) else 1


if __name__ == "__main__":
    raise SystemExit(executar())
