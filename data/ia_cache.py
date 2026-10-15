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

# Estados de tabela_disponivel() - mesmo padrao de data/coletores_status.py
# (achado real 2026-10-13: tabela ausente e credencial/RLS invalida
# degradavam pro MESMO False/None antes, escondendo qual das duas causas
# era a real). Aplicado aqui em 2026-10-15 depois de confirmar em produção
# (via leitura direta, read-only) que resumos_ia_cache nao existe no
# Supabase - sql/ia_cache.sql nunca foi rodado la', apesar da tabela ser
# usada desde 2026-10-05. Sem este diagnostico, o pre-processamento em
# lote (ver data/news.py:pregerar_resumos_news) queimava cota real do
# Groq em TODA execucao do coletor (a cada 30min) sem conseguir cachear
# nada - cada resumo gerado era descartado em silencio (_salvar_resultado
# falhava, mas gerar_fn() ja' tinha sido chamado de verdade).
TABELA_AUSENTE = "TABELA_AUSENTE"
TABELA_CREDENCIAL_OU_CONEXAO = "CREDENCIAL_OU_CONEXAO"
TABELA_ERRO_DESCONHECIDO = "ERRO_DESCONHECIDO"

_SINAIS_TABELA_AUSENTE = ("pgrst205", "could not find the table", "schema cache")
_SINAIS_CREDENCIAL_OU_CONEXAO = (
    "401", "403", "pgrst301", "pgrst302", "jwt", "api key", "apikey",
    "unauthorized", "authentication", "permission denied", "42501",
    "invalid_grant", "invalid signature",
    # RLS (mesmo achado de data/coletores_status.py, auditoria 2026-10-15
    # do secret SUPABASE_SECRET_KEY errado em producao): o texto REAL do
    # Postgres pra violacao de RLS e' "new row violates row-level security
    # policy" - nem sempre vem com "42501" no texto que chega aqui. Sem
    # este sinal, essa falha caia em ERRO_DESCONHECIDO, escondendo que a
    # causa real e' credencial/permissao, nao tabela ausente nem erro
    # aleatorio.
    "row-level security", "row level security", " rls ",
    "timeout", "timed out", "conexao", "conexão", "connection", "dns",
    "ssl", "unreachable", "econnrefused", "name or service not known",
    "waf", "bloquead",
)


def _texto_erro(erro: Exception) -> str:
    partes = [str(erro), repr(erro)]
    for atributo in ("code", "message", "details", "hint"):
        valor = getattr(erro, atributo, None)
        if valor:
            partes.append(str(valor))
    return " ".join(partes).lower()


def _classificar_erro_tabela(erro: Exception) -> str:
    texto = _texto_erro(erro)
    if any(s in texto for s in _SINAIS_TABELA_AUSENTE):
        return TABELA_AUSENTE
    if any(s in texto for s in _SINAIS_CREDENCIAL_OU_CONEXAO):
        return TABELA_CREDENCIAL_OU_CONEXAO
    return TABELA_ERRO_DESCONHECIDO


def tabela_disponivel() -> bool | str | None:
    """Diagnostico (nunca usado pelo fluxo normal de obter_resumo_com_cache/
    obter_varios, que continuam degradando com seguranca independente
    disso - so' serve pra pregerar_resumos_news decidir se vale a pena
    gastar cota de IA, e pro SAUDE DOS DADOS mostrar a causa real em vez
    de 'Supabase indisponível' genérico).

    Retorna True (tabela responde), TABELA_AUSENTE (rodar sql/ia_cache.sql),
    TABELA_CREDENCIAL_OU_CONEXAO (chave/RLS/rede), TABELA_ERRO_DESCONHECIDO
    (outro erro real, sem causa identificável pelo texto) ou None (Supabase
    sem cliente configurado)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        cliente.table(_TABELA).select("chave_documento").limit(1).execute()
        return True
    except Exception as e:
        causa = _classificar_erro_tabela(e)
        print(f"[ia_cache] tabela_disponivel() falhou ({causa}): {e!r}")
        return causa


def chave_research(link: str) -> str:
    """Chave de cache pro resumo de UM relatorio/live especifico do
    Research - o link em si ja e' um identificador unico do documento
    (mesma chave que research_itens usa pelo link), so' normalizado pra
    um hash de tamanho fixo."""
    return hashlib.sha256(f"research:{link}".encode("utf-8")).hexdigest()


#  v2 (2026-10-09, modal editorial NEWS - FASE C): formato do resumo mudou
# de 4 campos fixos (O QUE ACONTECEU/NÚMEROS/IMPACTO/PRÓXIMOS PASSOS) pra
# blocos RESUMO/LEITURA DE MERCADO (ver data/news.py:_PROMPT_SISTEMA_RESUMO)
# - sem bump de versao, todo resumo JA' cacheado pelo formato antigo
# continuaria sendo servido pro modal novo pra sempre (esta tabela nao tem
# TTL, so' expira se o CONJUNTO de fontes do grupo mudar), quebrando o
# parser novo (_separar_secoes_resumo). O prefixo forca cache MISS pra todo
# resumo gerado antes desta mudanca - reprocessado uma vez, na primeira
# visita ao grupo depois do deploy, nunca de novo depois disso.
#
# v3 (2026-10-15, reformulacao editorial completa do Market News): o
# FORMATO (RESUMO:/LEITURA DE MERCADO:) continua igual, mas o CONTEUDO
# esperado mudou bastante - prompt reescrito com os 4 angulos de
# prioridade (o que aconteceu/contexto/impacto potencial/o que acompanhar,
# sem forcar todos), lista explicita de frases proibidas e o gate
# _resumo_e_generico (ver data/news.py). Resumo v2 ja' cacheado pode ter
# sido aceito sob a regra antiga (mais permissiva) mesmo sendo generico -
# bump de versao forca reprocessamento 1x por grupo, mesmo motivo do bump
# v1->v2 acima.
_VERSAO_CHAVE_NEWS = "v3"


def chave_news(titulo: str, links: tuple) -> str:
    """Chave de cache pro resumo de um GRUPO de noticias do NEWS - como
    um grupo nao tem uma unica URL canonica (varias fontes sobre o
    mesmo fato), a chave e' o titulo do grupo + o CONJUNTO de links das
    fontes (ordenado - independente da ordem de tentativa de fetch, que
    e' por prioridade anti-paywall, nao por identidade), hasheado.
    Qualquer mudanca no conjunto de fontes (uma materia nova entrou no
    grupo) gera uma chave NOVA de proposito - trata como um documento
    diferente em vez de arriscar devolver um resumo que nao viu a fonte
    nova. Prefixo de versao (_VERSAO_CHAVE_NEWS) pra invalidar cache
    quando o FORMATO do resumo muda (ver comentario acima)."""
    identidade = _VERSAO_CHAVE_NEWS + "|" + titulo.strip().lower() + "|" + "|".join(sorted(links))
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
    except Exception as e:
        # achado real 2026-10-15: antes desta linha, uma falha de escrita
        # aqui era 100% invisivel - gerar_fn() roda (gasta cota de IA de
        # verdade) mas o resultado nunca e' cacheado, sem NENHUM rastro no
        # log pra saber o motivo (diferente de tabela_disponivel() acima,
        # que ja imprimia). So' print, nunca propaga - mantem o
        # comportamento de sempre (degrada pro gerar_fn() direto).
        print(f"[ia_cache] _reservar_geracao({chave[:12]}...) falhou: {e!r}")
        return False


def _salvar_resultado(cliente, chave: str, resultado: dict, modelo: str):
    try:
        cliente.table(_TABELA).update({
            "resultado": resultado, "modelo": modelo, "status": "concluido", "atualizado_em": _agora_iso(),
        }).eq("chave_documento", chave).execute()
    except Exception as e:
        # resumo ja' foi gerado e retornado pra quem pediu - so' o cache
        # que nao gravou, sem problema pro usuario que pediu; mas sem
        # log nenhum isso ficava indistinguivel de "gravou normalmente"
        # pra quem olhasse os logs do coletor depois (mesmo achado real
        # de _reservar_geracao acima).
        print(f"[ia_cache] _salvar_resultado({chave[:12]}...) falhou: {e!r}")


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
        # achado real 2026-10-15 (continuacao): este bypass e' silencioso
        # de proposito (ver docstring), mas descobrir SE ele esta' sendo
        # tomado (cliente None aqui, mesmo quando outros modulos no MESMO
        # processo conseguem um cliente valido) e' exatamente o que falta
        # pra entender por que pregerar_resumos_news gera resumos de
        # verdade (cota de IA gasta) sem persistir nenhum. So' print.
        print(f"[ia_cache] obter_resumo_com_cache({chave[:12]}...): obter_cliente() retornou None - caindo pro gerar_fn() direto, sem cache")
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
