# -*- coding: utf-8 -*-
"""Cache GLOBAL (todos os usuarios, nunca por sessao/usuario) de resumos
de IA no Supabase (tabela resumos_ia_cache, ver sql/ia_cache.sql) - um
resumo gerado por qualquer usuario fica disponivel pra todos os outros
pro MESMO documento, evitando chamadas duplicadas ao Groq.

Usado tanto por data/research/resumir.py:obter_resumo quanto por
data/news.py:obter_resumo_grupo - cada um so' passa uma CHAVE que
identifica o documento especifico (ver chave_research/chave_news -
nunca so' o ticker) e uma funcao gerar_fn (SEM ARGUMENTOS, closure) que
e' o fluxo de IA de hoje, sem NENHUMA mudanca de prompt/modelo/
fallback - este modulo nunca interpreta o CONTEUDO do resumo, so'
decide SE chama gerar_fn() ou devolve algo ja' cacheado.

Protecao contra 2 geracoes simultaneas do MESMO documento: a PRIMEIRA
requisicao a chegar reserva a geracao (INSERT puro - nao upsert - que
falha se outra requisicao ja' reservou, via PRIMARY KEY de
chave_documento); quem perde a corrida espera um pouco (poll curto,
~10s) a geracao concorrente terminar antes de desistir e gerar por
conta propria. Uma reserva "gerando" que nunca termina (processo
reiniciado/crash no meio) e' tratada como abandonada apos
_ABANDONO_SEGUNDOS e liberada - nunca bloqueia pra sempre.

NUNCA quebra o fluxo de resumo: qualquer falha do Supabase em qualquer
etapa (indisponivel, tabela ausente, erro de rede) degrada pro
comportamento de sempre - chama gerar_fn() direto, exatamente como
antes desta feature existir."""

import hashlib
import time
from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_TABELA = "resumos_ia_cache"
_ESPERA_TENTATIVAS = 10
_ESPERA_INTERVALO_S = 1.0
_ABANDONO_SEGUNDOS = 120  # reserva 'gerando' mais velha que isso e' tratada como processo morto


def chave_research(link: str) -> str:
    """Chave de cache pro resumo de UM relatorio/live especifico do
    Research - o link em si ja e' um identificador unico do documento
    (mesma chave que research_itens usa pelo link), so' normalizado pra
    um hash de tamanho fixo."""
    return hashlib.sha256(f"research:{link}".encode("utf-8")).hexdigest()


def chave_news(titulo: str, links: tuple) -> str:
    """Chave de cache pro resumo de um GRUPO de noticias do NEWS - como
    um grupo nao tem uma unica URL canonica (varias fontes sobre o
    mesmo fato), a chave e' o titulo do grupo + o CONJUNTO de links das
    fontes (ordenado - independente da ordem de tentativa de fetch, que
    e' por prioridade anti-paywall, nao por identidade), hasheado.
    Qualquer mudanca no conjunto de fontes (uma materia nova entrou no
    grupo) gera uma chave NOVA de proposito - trata como um documento
    diferente em vez de arriscar devolver um resumo que nao viu a fonte
    nova."""
    identidade = titulo.strip().lower() + "|" + "|".join(sorted(links))
    return hashlib.sha256(identidade.encode("utf-8")).hexdigest()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _buscar_linha(cliente, chave: str) -> dict | None:
    try:
        resp = cliente.table(_TABELA).select("*").eq("chave_documento", chave).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def _linha_abandonada(linha: dict) -> bool:
    try:
        criado = datetime.fromisoformat(str(linha["criado_em"]).replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return False
    if criado.tzinfo is None:
        criado = criado.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - criado).total_seconds() > _ABANDONO_SEGUNDOS


def _reservar_geracao(cliente, chave: str, link_principal: str, origem: str) -> bool:
    """INSERT puro (nunca upsert) - True so' se EU criei a linha agora
    (nenhuma linha existia ainda pra essa chave). O UNIQUE/PRIMARY KEY
    de chave_documento garante que so' uma reserva vence mesmo com 2
    requisicoes concorrentes de verdade (threads/processos diferentes).
    False se ja' existir linha OU o insert falhar por qualquer motivo
    (Supabase fora do ar, tabela ausente etc) - os dois casos tratados
    do mesmo jeito por quem chama (obter_resumo_com_cache): nunca
    presume que venceu a corrida so' porque o insert nao levantou
    excecao explicita de duplicidade."""
    try:
        cliente.table(_TABELA).insert({
            "chave_documento": chave, "origem": origem, "link_principal": link_principal,
            "status": "gerando", "criado_em": _agora_iso(), "atualizado_em": _agora_iso(),
        }).execute()
        return True
    except Exception:
        return False


def _salvar_resultado(cliente, chave: str, resultado: dict, modelo: str):
    try:
        cliente.table(_TABELA).update({
            "resultado": resultado, "modelo": modelo, "status": "concluido", "atualizado_em": _agora_iso(),
        }).eq("chave_documento", chave).execute()
    except Exception:
        pass  # resumo ja' foi gerado e retornado pra quem pediu - so' o cache que nao gravou, sem problema


def _liberar_reserva(cliente, chave: str):
    """Geracao que eu reservei falhou (resumo=None) OU a reserva estava
    abandonada (processo anterior nunca terminou) - apaga a linha em
    vez de deixar 'gerando' presa pra sempre, senao toda tentativa
    futura pro mesmo documento ficaria esperando uma geracao que nunca
    vai terminar."""
    try:
        cliente.table(_TABELA).delete().eq("chave_documento", chave).execute()
    except Exception:
        pass


def _esperar_geracao_concorrente(cliente, chave: str) -> dict | None:
    """Poll curto (ate _ESPERA_TENTATIVAS x _ESPERA_INTERVALO_S, ~10s)
    esperando a geracao QUE OUTRA REQUISICAO reservou terminar - usado
    so' quando EU perdi a corrida de _reservar_geracao. Retorna o
    resultado cacheado se terminou dentro da janela, None se continuar
    'gerando' ou a linha desaparecer (reserva liberada por falha/
    abandono) - quem chama cai pro fluxo atual (gera por conta propria)
    nesses casos, nunca fica bloqueado pra sempre."""
    for _ in range(_ESPERA_TENTATIVAS):
        time.sleep(_ESPERA_INTERVALO_S)
        linha = _buscar_linha(cliente, chave)
        if linha is None:
            return None
        if linha.get("status") == "concluido" and linha.get("resultado"):
            return linha["resultado"]
    return None


def obter_varios(chaves: list) -> dict:
    """Leitura em LOTE (1 unica query, SEM reservar nem gerar nada) dos
    resumos JA CONCLUIDOS pras chaves dadas - usada pelo feed editorial
    do NEWS (fase 3) pra mostrar resumo/imagem de itens ja cacheados por
    QUALQUER usuario anterior sem bater 1x no Supabase por card (N+1):
    so' 1 SELECT com IN(...) pra todas as chaves visiveis na tela.

    Retorna {chave: resultado} so' das chaves com status='concluido' e
    'resultado' presente; chave ausente no retorno = ainda nao cacheada
    (quem chama trata como "sem resumo ainda", nunca como erro). Lista
    vazia ou Supabase fora do ar -> {} (nunca lanca excecao, nunca
    bloqueia o feed principal)."""
    if not chaves:
        return {}
    cliente = obter_cliente()
    if cliente is None:
        return {}
    try:
        resp = (
            cliente.table(_TABELA)
            .select("chave_documento,resultado,status")
            .in_("chave_documento", list(dict.fromkeys(chaves)))
            .eq("status", "concluido")
            .execute()
        )
    except Exception:
        return {}
    return {
        linha["chave_documento"]: linha["resultado"]
        for linha in (resp.data or [])
        if linha.get("resultado")
    }


def obter_resumo_com_cache(chave: str, link_principal: str, origem: str, gerar_fn) -> dict:
    """Ponto de entrada unico (Research e News): verifica cache -> se
    nao houver, tenta reservar a geracao -> se perder a corrida, espera
    um pouco a geracao concorrente -> se nada disso resolver, gera
    normalmente (gerar_fn - EXATAMENTE o fluxo de IA de hoje, sem
    mudanca de prompt/modelo/fallback). Falha do Supabase em QUALQUER
    etapa cai direto pro fluxo atual (gerar_fn()), nunca quebra o
    resumo. So' persiste no cache quando gerar_fn() retornar resumo!=
    None (falha de IA/extracao nunca fica "cacheada" como se fosse
    definitiva - pode funcionar numa proxima tentativa)."""
    cliente = obter_cliente()
    if cliente is None:
        return gerar_fn()

    linha = _buscar_linha(cliente, chave)

    if linha is not None and linha.get("status") == "gerando" and _linha_abandonada(linha):
        _liberar_reserva(cliente, chave)
        linha = None

    if linha is not None and linha.get("status") == "concluido" and linha.get("resultado"):
        return linha["resultado"]

    if linha is None:
        if _reservar_geracao(cliente, chave, link_principal, origem):
            resultado = gerar_fn()
            if resultado.get("resumo"):
                _salvar_resultado(cliente, chave, resultado, resultado.get("modelo") or "")
            else:
                _liberar_reserva(cliente, chave)
            return resultado
        # reserva falhou - confirma se foi corrida real (linha apareceu) ou falha do banco
        linha = _buscar_linha(cliente, chave)
        if linha is None:
            return gerar_fn()

    if linha.get("status") == "concluido" and linha.get("resultado"):
        return linha["resultado"]

    resultado_concorrente = _esperar_geracao_concorrente(cliente, chave)
    if resultado_concorrente is not None:
        return resultado_concorrente
    return gerar_fn()
