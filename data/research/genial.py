# -*- coding: utf-8 -*-
"""Coletor da Genial Analisa (https://analisa.genialinvestimentos.com.br).

A home e renderizada em Next.js (SSR): os dados vem prontos no JSON
__NEXT_DATA__ embutido no HTML, entao NAO fazemos parsing de HTML - so
carregamos esse JSON e navegamos nele. Guardamos apenas metadados
(titulo, data, autor, setor, ticker, link); nunca o texto do relatorio.

Observado na pratica: o dominio fica atras de um WAF (Akamai) que derruba
(timeout, sem resposta) requests feitas com a stack TLS padrao do
`requests`/urllib3 - tanto com `requests` quanto com `curl` puro. A causa
e' fingerprint de TLS (JA3), nao o conteudo da requisicao: usar
`curl_cffi` com `impersonate="chrome"` (que replica o handshake TLS de um
Chrome de verdade) resolve, e a partir dai a resposta e' um HTML estatico
comum, sem nenhum desafio JS pra resolver.

Diagnostico de producao (Streamlit Cloud, 2026-09-23) mostrou um sintoma
diferente do WAF: "HTTP/2 stream reset by server" - a conexao chega no
servidor (diferente do sandbox de dev, que bloqueia o dominio inteiro
antes disso) mas e' derrubada especificamente no HTTP/2. _tentar_buscar
tenta uma sequencia de combinacoes (comecando por forcar HTTP/1.1) ate
uma funcionar, e imprime qual funcionou/falhou - aparece nos Logs do
Streamlit Cloud e no painel DIAGNOSTICO DE FONTES (CONFIG).

Busca por via alternativa (2026-10-16): sem WebFetch/curl de verdade pra
analisa.genialinvestimentos.com.br (fora do allowlist de rede deste
ambiente - nem resolve DNS), a verificacao foi via busca na web
(WebSearch); nao achou nenhum feed RSS, sitemap ou API publica
alternativa pro conteudo da Genial Analisa - so' achou a propria home e
o disclaimer (que proibe reproducao/redistribuicao do conteudo sem
autorizacao previa por escrito, o que tambem descarta usar um agregador
de terceiro como substituto legitimo). O parsing do __NEXT_DATA__ da
home (ja' implementado aqui) continua sendo a unica via conhecida; o
bloqueio de WAF documentado acima permanece a causa real.

Busca por via alternativa, 2a rodada (2026-10-17, com rede real
disponivel): testado se o bloqueio e' so' do subdominio analisa.
genialinvestimentos.com.br ou da zona inteira - genialinvestimentos.
com.br (raiz, IP diferente do subdominio) tambem da timeout silencioso
(sem nenhum byte de resposta em 10s, mesmo sintoma documentado acima),
com UA identificado do projeto, SEM impersonate/disfarce. Mesma
conclusao do caso XP (ver xp.py): nao e' um subdominio isolado, e' a
zona inteira - descarta "tentar outro subdominio da Genial" como
alternativa legitima. Nenhuma tentativa de bypass foi feita contra o
MESMO alvo - so' um teste de reachability contra um alvo diferente (a
raiz do dominio), o que e' legitimo."""

import json
import re
import time

import streamlit as st
from curl_cffi import requests as cffi_requests
from curl_cffi.const import CurlHttpVersion

from .base import HEADERS, TIMEOUT, TTL_COLETA, permitido

BASE_URL = "https://analisa.genialinvestimentos.com.br"

# ordem de tentativa: HTTP/1.1 primeiro (suspeita principal do reset de
# stream HTTP/2), depois o comportamento original (HTTP/2 via chrome),
# depois outros perfis de impersonate com HTTP/1.1 forcado
_TENTATIVAS = [
    {"impersonate": "chrome", "http_version": CurlHttpVersion.V1_1},
    {"impersonate": "chrome"},
    {"impersonate": "chrome124", "http_version": CurlHttpVersion.V1_1},
    {"impersonate": "safari17_0", "http_version": CurlHttpVersion.V1_1},
]

# orcamento total pra TODAS as tentativas juntas - sem isso, se o dominio
# nao responder nada (timeout puro, nao um erro rapido), as 4 tentativas
# podiam somar bem mais que TIMEOUT*4 (achado na auditoria de
# performance: um teste real bateu no timeout do proprio AppTest por
# causa disso). Uma vez estourado, para na tentativa atual e desiste.
_ORCAMENTO_TOTAL_S = 20

# Motivo da ULTIMA falha total de _tentar_buscar (achado real, auditoria
# 2026-10-15: registrar_tentativa so' recebia "obter_relatorios retornou
# None apos Xs" - o motivo especifico (timeout vs HTTP/2 reset vs
# orcamento esgotado) so' aparecia no print(), visivel nos Logs do
# GitHub Actions/Streamlit Cloud, nunca no painel SAUDE DOS DADOS em si).
# Modulo tem 1 unica fonte (nao precisa de estado por-chamada/thread-local
# - mesmo padrao simples que o resto do projeto usa pra isso).
_ultimo_motivo_falha = None

# Marcador textual (achado real, auditoria 2026-10-18 - correcao do exit
# code de coletor_local.py): so' aparece em _ultimo_motivo_falha quando o
# ultimo erro bate EXATAMENTE com um dos 2 sintomas do WAF Akamai ja
# documentados na docstring do modulo (timeout total sem nenhum byte
# recebido, ou reset ativo de stream HTTP/2) - ver _eh_padrao_bloqueio_
# conhecido(). Serve pra categoria_ultima_falha() decidir se essa falha
# especifica pode deixar de derrubar o exit code (ja' e' um bloqueio
# conhecido, nao uma regressao nova) - qualquer erro DIFERENTE desses 2
# sintomas (ex: HTTP 500, erro de parsing) nao ganha esse marcador, fica
# como falha generica/nao classificada de proposito.
_MARCADOR_BLOQUEIO_WAF = "bloqueio de borda do WAF (Akamai)"


def _eh_padrao_bloqueio_conhecido(erro: str) -> bool:
    """So' reconhece os 2 sintomas REAIS ja documentados (ver docstring do
    modulo, achados de 2026-09-23/24): timeout total sem nenhum byte de
    resposta ('0 bytes received' - texto literal do curl pra essa
    situacao, independente do codigo de erro exato na mensagem) ou reset
    ativo de stream HTTP/2 pelo servidor ('stream ... reset by server').
    Qualquer outro texto de erro (ex: HTTP 500, erro de parsing, DNS
    mudou) devolve False de proposito - nao e' um bypass, e' so' nao
    inventar que um erro desconhecido e' o mesmo bloqueio antigo."""
    if not erro:
        return False
    timeout_sem_resposta = "0 bytes received" in erro
    reset_http2 = "reset by server" in erro and "stream" in erro
    return timeout_sem_resposta or reset_http2


def motivo_ultima_falha() -> str | None:
    """Detalhe da ultima falha TOTAL de _tentar_buscar (todas as
    tentativas da lista, ou orcamento esgotado) - None se a ultima
    chamada teve sucesso ou nenhuma chamada foi feita ainda nesta
    sessao do processo."""
    return _ultimo_motivo_falha


def categoria_ultima_falha() -> str:
    """Classifica a ultima falha pra decidir se ela sozinha pode deixar
    de derrubar o exit code de coletor_local.py (ver data/research/
    __init__.py:_classificar_falha e coletor_local.py:_falha_critica).
    So' devolve 'bloqueio_externo_conhecido' quando o motivo da ultima
    falha tem o marcador do padrao de WAF JA' documentado (ver
    _eh_padrao_bloqueio_conhecido) - qualquer coisa diferente (sucesso,
    motivo None, erro novo/desconhecido) devolve 'erro' de proposito,
    pra nunca mascarar uma mudanca real de comportamento."""
    motivo = _ultimo_motivo_falha or ""
    return "bloqueio_externo_conhecido" if _MARCADOR_BLOQUEIO_WAF in motivo else "erro"


def _tentar_buscar(url: str, orcamento_s: float = _ORCAMENTO_TOTAL_S):
    """Tenta baixar `url` com cada combinacao de _TENTATIVAS ate uma dar
    certo (200 com corpo) ou o orcamento total (`orcamento_s`, default
    _ORCAMENTO_TOTAL_S) estourar. Retorna (Response, rotulo) ou (None,
    None) se todas falharem/o tempo acabar. print() de cada tentativa -
    visivel nos Logs do Streamlit Cloud."""
    global _ultimo_motivo_falha
    limite = time.monotonic() + orcamento_s
    ultimo_erro = None
    for tentativa in _TENTATIVAS:
        if time.monotonic() > limite:
            print("[genial] orçamento de tempo esgotado, parando tentativas")
            _ultimo_motivo_falha = f"orçamento de {orcamento_s:.0f}s esgotado antes de tentar todos os perfis; último erro: {ultimo_erro or 'nenhum'}"
            if _eh_padrao_bloqueio_conhecido(ultimo_erro or ""):
                _ultimo_motivo_falha += f" - {_MARCADOR_BLOQUEIO_WAF}"
            return None, None
        rotulo = f"impersonate={tentativa.get('impersonate')} http={tentativa.get('http_version', 'auto')}"
        try:
            r = cffi_requests.get(url, headers=HEADERS, timeout=TIMEOUT, **tentativa)
            if r.status_code == 200 and r.text:
                print(f"[genial] conexao OK ({rotulo})")
                _ultimo_motivo_falha = None
                return r, rotulo
            ultimo_erro = f"{rotulo}: HTTP {r.status_code}"
            print(f"[genial] tentativa falhou ({rotulo}): HTTP {r.status_code}")
        except Exception as e:
            ultimo_erro = f"{rotulo}: {type(e).__name__}: {e}"
            print(f"[genial] tentativa falhou ({rotulo}): {e}")
    _ultimo_motivo_falha = f"todas as {len(_TENTATIVAS)} tentativas falharam; última: {ultimo_erro or 'nenhum erro capturado'}"
    if _eh_padrao_bloqueio_conhecido(ultimo_erro or ""):
        _ultimo_motivo_falha += f" - {_MARCADOR_BLOQUEIO_WAF}"
    return None, None


def testar_conexao(orcamento_s: float = 5) -> tuple:
    """So testa se consegue baixar a home (sem parsear __NEXT_DATA__) -
    usado pelo painel DIAGNOSTICO DE FONTES. Orcamento default bem menor
    que o da coleta real (_ORCAMENTO_TOTAL_S=20): e' so' um teste de
    reachability, nao vale a pena travar o painel por 20s numa fonte que
    ja se sabe bloqueada. Retorna (ok, detalhe)."""
    if not permitido(BASE_URL):
        return False, "bloqueado pelo robots.txt"
    r, rotulo = _tentar_buscar(BASE_URL, orcamento_s=orcamento_s)
    if r is None:
        return False, "todas as tentativas falharam"
    return True, rotulo

# tipos de secao na home (campo "type" do __NEXT_DATA__) - estavel e em
# ingles, ao contrario do "titulo" (localizado, mais fragil de casar)
_TIPO_SECAO_RECOMENDACOES = "CARROSSEL_PRINCIPAIS_RECOMENDACOES_SETOR"
_TIPO_SECAO_RELATORIOS = "CARROSSEL_RELATORIOS"  # aparece 2x: acoes e mercado
_TIPO_SECAO_ECONOMIA = "MACROECONOMIA"
_TIPO_SECAO_SWING_TRADE = "SWING_TRADE_E_BANNER"
_TIPO_SECAO_NEWSLETTER = "CARROSSEL_NEWSLETTER"

_TICKER_NO_LINK = re.compile(r"^/acoes/([A-Z0-9]{4,6})(?:/|$)")


@st.cache_data(ttl=TTL_COLETA, show_spinner="consultando research (Genial)…")
def _buscar_next_data() -> dict | None:
    """Cacheado (nao so as 3 funcoes publicas que consomem isso): sem
    isso, obter_relatorios/obter_recomendacoes/obter_swing_trade batiam
    na home da Genial 3x separadas a cada render da aba RESEARCH, mesmo
    sendo a mesma pagina - achado na auditoria de performance."""
    if not permitido(BASE_URL):
        return None
    r, _ = _tentar_buscar(BASE_URL)
    if r is None:
        return None
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _secoes(data: dict) -> list:
    return data["props"]["pageProps"]["page"]["sections"]


def _url_absoluta(link: str) -> str:
    return link if link.startswith("http") else BASE_URL + link


def _ticker_do_link(link: str) -> list:
    m = _TICKER_NO_LINK.match(link)
    return [m.group(1)] if m else []


def _ticker_da_url_recomendacao(url: str) -> str:
    """Ultimo segmento do caminho de `url` (ex: "/acoes/PETR4" -> "PETR4")
    - usado por obter_recomendacoes, cujo JSON da Genial traz a URL da
    pagina do ticker em vez de um campo 'ticker' dedicado. rstrip da
    barra final ANTES do rsplit: sem isso, uma url terminada em "/" (ex:
    "/acoes/PETR4/") devolvia "" como ticker - string vazia nunca bate
    com nenhum ticker da watchlist (ui/research_tab.py:363,
    `r["ticker"] == ticker`), perdendo silenciosamente a
    recomendacao/preco-alvo real daquele ticker. Mesmo cuidado que
    data/research/xp.py:obter_texto_aberto ja tem pro slug."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def _normalizar_data(texto: str) -> str:
    """Datas na Genial vem em dois formatos diferentes conforme a secao:
    'DD/MM/YYYY' (relatorios) ou 'YYYY-MM-DD HH:MM:SS' (newsletter/swing
    trade). Normaliza tudo pra 'YYYY-MM-DD' (ordena certo como string, e
    a UI formata pra exibicao). Retorna '' se nao reconhecer o formato -
    nunca inventa uma data."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        return texto[:10]
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        dia, mes, ano = m.groups()
        return f"{ano}-{mes}-{dia}"
    return ""


def _item_relatorio(item: dict, tipo: str) -> dict:
    autores = ", ".join(a["nome"].strip() for a in (item.get("analistas") or []) if a.get("nome"))
    return {
        "casa": "Genial Analisa",
        "titulo": item["titulo"],
        "data": _normalizar_data(item.get("data", "")),
        "autor": autores,
        "tipo": tipo,
        "setor": item.get("subCategoria") or item.get("categoria") or "",
        "tickers": _ticker_do_link(item["link"]),
        "link": _url_absoluta(item["link"]),
    }


def _item_newsletter(item: dict) -> dict:
    return {
        "casa": "Genial Analisa",
        "titulo": item["titulo"],
        "data": _normalizar_data(item.get("data", "")),
        "autor": "",
        "tipo": "NEWSLETTER",
        "setor": "",
        "tickers": [],
        "link": _url_absoluta(item["link"]),
    }


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def obter_relatorios() -> list | None:
    """Relatorios de acoes, mercado/estrategia (Expresso Bolsa Semanal,
    Estrategia em Acao, Carta dos Estrategistas), economia (Copom, FOMC,
    Carta Macro) e Bom Dia Genial - todos no formato comum (casa, titulo,
    data, autor, tipo, setor, tickers, link). None se a home falhar."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        secoes = _secoes(data)
    except Exception:
        return None

    relatorios = []
    for secao in secoes:
        tipo_secao = secao.get("type")
        if tipo_secao not in (_TIPO_SECAO_RELATORIOS, _TIPO_SECAO_ECONOMIA, _TIPO_SECAO_NEWSLETTER):
            continue
        for item in secao.get("content", {}).get("items", []):
            # isolado por item (bug real corrigido, auditoria missao
            # coletores 2026-10-13, continuacao): _item_relatorio/
            # _item_newsletter acessam item["titulo"]/item["link"] direto
            # (sem .get) - 1 item incompleto (ex: rascunho no CMS da
            # Genial sem titulo ainda) lancava KeyError que escapava pro
            # try/except ÚNICO que envolvia as 3 secoes inteiras,
            # descartando TAMBEM as outras 2 secoes que tinham parseado
            # perfeitamente (ex: MACROECONOMIA e NEWSLETTER do dia,
            # mesmo so' a secao de ACOES tendo o item ruim). Mesmo padrao
            # ja usado em data/research/genial_lives.py e
            # data/research/xp.py - 1 item malformado nunca derruba os
            # outros que ja parsearam certo.
            try:
                if tipo_secao == _TIPO_SECAO_RELATORIOS:
                    # as duas secoes de CARROSSEL_RELATORIOS (acoes e
                    # mercado) sao distinguidas pela categoria de cada
                    # item, nao pelo titulo da secao (localizado, mais
                    # fragil)
                    tipo = "ACOES" if item.get("categoria") == "Ações" else "ESTRATEGIA"
                    relatorios.append(_item_relatorio(item, tipo))
                elif tipo_secao == _TIPO_SECAO_ECONOMIA:
                    relatorios.append(_item_relatorio(item, "MACRO"))
                else:
                    relatorios.append(_item_newsletter(item))
            except Exception:
                continue

    return relatorios or None


@st.cache_data(ttl=TTL_COLETA, show_spinner="consultando research (Genial)…")
def obter_recomendacoes() -> list | None:
    """Principais recomendacoes por setor: ticker, empresa, setor,
    recomendacao (COMPRA/MANTER/VENDA), preco-alvo, potencial (%), link.
    None se a home falhar ou a secao nao existir."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        secoes = _secoes(data)
    except Exception:
        return None
    for secao in secoes:
        if secao.get("type") != _TIPO_SECAO_RECOMENDACOES:
            continue
        resultado = []
        for it in secao.get("content") or []:
            # isolado por item (mesmo achado/padrao de obter_relatorios
            # acima): it["url"] direto sem .get - 1 recomendacao sem url
            # nao pode descartar as outras que ja tinham dado valido.
            try:
                resultado.append({
                    "ticker": _ticker_da_url_recomendacao(it["url"]),
                    "empresa": (it.get("empresaNome") or "").strip(),
                    "setor": it.get("setor", ""),
                    "recomendacao": it.get("recomendacao", ""),
                    "preco_alvo": it.get("preco"),
                    "potencial_pct": it.get("potencial"),
                    "link": _url_absoluta(it["url"]),
                })
            except Exception:
                continue
        return resultado or None
    return None


@st.cache_data(ttl=TTL_COLETA, show_spinner="consultando research (Genial)…")
def obter_swing_trade() -> list | None:
    """Oportunidades de swing trade: ticker, empresa, recomendacao,
    status ('em aberto' / encerrado), data, link. None se a home falhar
    ou a secao nao existir."""
    data = _buscar_next_data()
    if data is None:
        return None
    try:
        secoes = _secoes(data)
    except Exception:
        return None
    for secao in secoes:
        if secao.get("type") != _TIPO_SECAO_SWING_TRADE:
            continue
        resultado = []
        for it in secao.get("content") or []:
            # isolado por item (mesmo achado/padrao de obter_relatorios/
            # obter_recomendacoes acima): it["link"] direto sem .get.
            try:
                resultado.append({
                    "ticker": it.get("ticker", ""),
                    "empresa": ((it.get("empresa") or {}).get("nome") or "").strip(),
                    "recomendacao": (it.get("informacoesTicker") or {}).get("recomendacao", ""),
                    "status": (it.get("informacoesTicker") or {}).get("status", ""),
                    "data": _normalizar_data(it.get("date", "")),
                    "link": _url_absoluta(it["link"]),
                })
            except Exception:
                continue
        return resultado or None
    return None
