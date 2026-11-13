# -*- coding: utf-8 -*-
"""Encerra, de forma segura e auditável, execuções de
`coordenador_analises` travadas em EM_ANDAMENTO além de qualquer tempo
plausível de execução real.

## Contexto do achado (missão PREGÃO 2.1, Agente F, 2026-11-13)

Investigação somente-leitura (consulta direta ao Supabase de produção,
sem nenhuma escrita) confirmou 20 linhas EM_ANDAMENTO, TODAS de
2026-11-05 entre 02:51:07 e 02:53:16 UTC (uma única rodada de
`jobs/comite_noturno.py`, que processa até `LIMITE_TICKERS_RODADA=20`
tickers por execução - bate exatamente com a contagem). Cada uma das
20 já tem as 6 execuções de especialista esperadas registradas em
`coordenador_especialistas_execucoes` (o processo rodou até o fim) -
confirma a hipótese já documentada em
`data/coordenador_central/persistencia.py` (comentário de
`_TENTATIVAS_UPDATE`, linhas ~26-38): o UPDATE final de
`concluir_analise` falhou por um bug real e determinístico (ausência de
serialização de `date`/`datetime` antes de mandar o `resultado` jsonb
pro cliente HTTP do Supabase - toda análise cujo resultado consolidado
contivesse uma data, como o especialista `catalisadores`, falhava o
UPDATE de forma 100% reproduzível). Esse bug já foi corrigido em
produção no mesmo dia (`4aa50a8`, 2026-11-05 20:14 -03,
`_serializar_jsonb` em persistencia.py) - só não existe, em lugar
nenhum do código, nenhum mecanismo de timeout/limpeza automática que
revisite linhas EM_ANDAMENTO antigas e as feche; por isso estas 20
linhas específicas (anteriores à correção) nunca foram tocadas de novo
e ficam travadas em EM_ANDAMENTO pra sempre, sem o fallback mínimo que
`concluir_analise` já tenta hoje (porque o processo que as criou já
terminou e nunca mais vai chamar `concluir_analise` pra elas).

Referência de "tempo plausível de execução": amostra de 100 análises
CONCLUIDA mais recentes em produção -> duracao_ms entre 3842ms e
21047ms (média ~10.1s). As 20 linhas têm, no momento desta escrita,
~203h (~8.5 dias) de idade - ordens de magnitude acima de qualquer
execução real, mesmo com margem generosa.

## O que este script faz

1. Lê (SELECT, sempre) as linhas `status='EM_ANDAMENTO'` com
   `iniciado_em` mais antigo que `--limiar-horas` (default 2h - bem
   acima do máximo observado de execução real, com margem grande).
2. Em modo padrão (SEM `--aplicar`): só IMPRIME o que seria alterado -
   nenhuma escrita, pode ser rodado livremente quantas vezes quiser.
3. Só com `--aplicar` E `--confirmo EXECUTAR-EM-PRODUCAO` (os dois
   exatos, nenhum default) grava a alteração - reaproveitando
   `data.coordenador_central.persistencia.concluir_analise` (já
   testado, já tem retry + fallback mínimo embutido) pra marcar
   `status='ERRO'`, `concluido_em=agora`, e uma mensagem clara em
   `erro` citando o motivo e a data do fechamento retroativo. NUNCA
   deleta a linha - o registro original (id, solicitacao, ticker,
   iniciado_em, e a telemetria em coordenador_especialistas_execucoes)
   fica intacto pra auditoria futura. `resultado` nunca é preenchido
   por este script (não existe mais o dado real de quando a análise
   rodou - inventar um resultado seria pior que deixar `None`).
4. Nunca usa status novo (`EXPIRADA` etc.) - segue a convenção já
   explícita no próprio código de persistencia.py ("nunca um enum de
   status novo"): usa o `ERRO` que já existe no contrato de status
   (EM_ANDAMENTO/CONCLUIDA/PARCIAL/ERRO, ver sql/coordenador_central.sql)
   e deixa o motivo detalhado na coluna `erro`, já existente.
5. Rejeita `--limiar-horas` abaixo de `_LIMIAR_HORAS_MINIMO_SEGURO`
   (0.5h) ANTES de consultar ou escrever qualquer coisa - proteção
   contra erro de operador (ex.: `--limiar-horas 0`) que classificaria
   uma análise genuinamente em andamento como órfã (revisão de
   PR #309).

## IMPORTANTE - autorização

Este script NÃO foi executado com `--aplicar` contra produção. Alterar
registro real de produção exige aprovação explícita do Rodrigo à
parte, mesmo com autorização geral de merge da missão - ver
`.claude/.../feedback_approval_before_prod_merge` e a instrução
explícita desta missão. Development/revisão: só rodar sem `--aplicar`
(modo leitura) é seguro e pode ser feito livremente.

Uso:
    python scripts/encerrar_analises_orfas.py                                  # dry-run (só mostra)
    python scripts/encerrar_analises_orfas.py --limiar-horas 6                 # dry-run com limiar custom
    python scripts/encerrar_analises_orfas.py --aplicar --confirmo EXECUTAR-EM-PRODUCAO   # grava (SÓ com aprovação explícita do Rodrigo)
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_LIMIAR_HORAS_DEFAULT = 2.0
# Piso de segurança contra falso positivo por erro de operador: a
# duração real mais longa plausível de um fluxo (ver data/
# coordenador_central/fluxos.py:analisar_ticker - pior caso sequencial
# com todos os timeouts de 30s somados: executar_varios + model_builder
# + valuation_reviewer + sintese_ia, 2 chamadas) fica em torno de 150s
# (2.5min). Qualquer --limiar-horas abaixo deste piso arrisca classificar
# como "órfã" uma análise que está genuinamente em andamento (falso
# positivo) - bloqueado ANTES de qualquer SELECT/escrita, nunca só um
# aviso (revisão de PR #305/#309, achado: nada impedia `--limiar-horas 0`
# ou negativo, que teria tratado qualquer linha EM_ANDAMENTO, mesmo uma
# iniciada há 1 segundo, como órfã).
_LIMIAR_HORAS_MINIMO_SEGURO = 0.5
_FRASE_CONFIRMACAO = "EXECUTAR-EM-PRODUCAO"
_MOTIVO_FECHAMENTO = (
    "FECHAMENTO_RETROATIVO: linha travada em EM_ANDAMENTO além de qualquer "
    "tempo plausível de execução real (ver scripts/encerrar_analises_orfas.py "
    "para o achado completo). Encerrada manualmente em {quando} via script de "
    "limpeza, com aprovação explícita do Rodrigo - nunca um timeout automático. "
    "Causa raiz original (incidente de 2026-11-05): UPDATE final de "
    "concluir_analise falhava por ausência de serialização de date/datetime no "
    "resultado jsonb, já corrigido em produção (commit 4aa50a8) - esta linha é "
    "anterior à correção e por isso nunca foi reprocessada."
)


def _agora_utc():
    return datetime.now(timezone.utc)


def _parse_iso(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def localizar_orfas(cliente, limiar_horas: float):
    """SELECT puro - nunca escreve. Devolve lista de linhas EM_ANDAMENTO
    com iniciado_em mais antigo que o limiar."""
    corte = (_agora_utc() - timedelta(hours=limiar_horas)).isoformat()
    resp = (
        cliente.table("coordenador_analises").select(
            "id,ticker,tipo_fluxo,status,iniciado_em,duracao_ms,erro"
        )
        .eq("status", "EM_ANDAMENTO")
        .lt("iniciado_em", corte)
        .order("iniciado_em", desc=False)
        .execute()
    )
    return resp.data or []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limiar-horas", type=float, default=_LIMIAR_HORAS_DEFAULT,
                         help=f"Idade mínima (horas) pra considerar uma linha EM_ANDAMENTO órfã (default {_LIMIAR_HORAS_DEFAULT}h).")
    parser.add_argument("--aplicar", action="store_true",
                         help="Sem esta flag, o script só mostra o que faria (dry-run, seguro, sem escrita).")
    parser.add_argument("--confirmo", default="",
                         help=f"Obrigatório junto com --aplicar: precisa ser exatamente '{_FRASE_CONFIRMACAO}'.")
    args = parser.parse_args()

    if args.limiar_horas < _LIMIAR_HORAS_MINIMO_SEGURO:
        print(
            f"[encerrar_analises_orfas] --limiar-horas={args.limiar_horas} abaixo do piso de segurança "
            f"({_LIMIAR_HORAS_MINIMO_SEGURO}h, bem acima do pior caso real plausível de ~2.5min) - "
            "ABORTANDO antes de consultar ou escrever qualquer coisa, por segurança contra falso positivo "
            "(classificar uma análise genuinamente em andamento como órfã)."
        )
        return 1

    from data.supabase_client import obter_cliente
    cliente = obter_cliente()
    if cliente is None:
        print("[encerrar_analises_orfas] Supabase indisponível (credenciais ausentes/inválidas) - abortando.")
        return 1

    orfas = localizar_orfas(cliente, args.limiar_horas)
    if not orfas:
        print(f"[encerrar_analises_orfas] Nenhuma linha EM_ANDAMENTO com mais de {args.limiar_horas}h de idade. Nada a fazer.")
        return 0

    print(f"[encerrar_analises_orfas] {len(orfas)} linha(s) EM_ANDAMENTO com mais de {args.limiar_horas}h de idade:\n")
    agora = _agora_utc()
    for linha in orfas:
        idade_h = (agora - _parse_iso(linha["iniciado_em"])).total_seconds() / 3600
        print(f"  id={linha['id']} ticker={linha.get('ticker')} iniciado_em={linha['iniciado_em']} idade={idade_h:.1f}h")

    aplicar = args.aplicar and args.confirmo == _FRASE_CONFIRMACAO
    if not args.aplicar:
        print("\n[encerrar_analises_orfas] DRY-RUN (nenhuma escrita) - rode com --aplicar --confirmo "
              f"{_FRASE_CONFIRMACAO} pra de fato encerrar estas linhas (só com aprovação explícita do Rodrigo).")
        return 0
    if not aplicar:
        print("\n[encerrar_analises_orfas] --aplicar foi passado mas --confirmo não bate com a frase exigida - "
              "ABORTANDO sem escrever nada, por segurança.")
        return 1

    from data.coordenador_central.persistencia import concluir_analise

    quando = agora.isoformat()
    sucesso, falha = 0, 0
    for linha in orfas:
        ok = concluir_analise(
            linha["id"], status="ERRO",
            erro=_MOTIVO_FECHAMENTO.format(quando=quando),
            duracao_ms=None,
        )
        print(f"  id={linha['id']} ticker={linha.get('ticker')} -> {'OK' if ok else 'FALHOU (ver log acima)'}")
        sucesso += 1 if ok else 0
        falha += 0 if ok else 1

    print(f"\n[encerrar_analises_orfas] {sucesso} encerrada(s) com sucesso, {falha} falha(s).")
    return 0 if falha == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
