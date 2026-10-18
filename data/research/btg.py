# -*- coding: utf-8 -*-
"""Coletor da BTG Pactual Research (content.btgpactual.com).

Investigacao original (2026-10-16/17) tinha concluido que o endpoint real
de listagem (POST /api/research/content-hub/analysis/filter) misturava
relatorios publicos e de area logada SEM expor o campo que distingue os
dois no modo lote - so' no GET de detalhe de cada item - o que tornaria
qualquer coleta em lote equivalente a contornar login (decisao registrada:
nao implementar).

Achado que CORRIGE essa premissa (reinvestigacao 2026-10-17, requisicoes
reais, nao suposicao): o campo "tier" ("AREA_PUBLICA" ou "AREA_LOGADA")
JA' vem no proprio POST /filter em lote, item por item - nao e' preciso
nenhuma chamada extra de detalhe pra saber se um item e' publico. Testado
com 300 itens reais (12 paginas x 25), tier presente em TODOS, ~30-40%
"AREA_PUBLICA" (ex: 123/300 numa amostra, 68/200 noutra) - porcentagem
suficiente pra ser um coletor com conteudo real. robots.txt de
content.btgpactual.com permite tudo ("Allow: /"). Nenhum bloqueio
observado em dezenas de requisicoes reais, com User-Agent identificado do
projeto (base.HEADERS) OU um UA de navegador comum - sem diferenca, ou
seja isso NAO e' bypass de fingerprint/WAF como genial.py precisa: BTG
simplesmente nao bloqueia esse dominio/endpoint.

Com isso, o coletor FILTRA por tier=="AREA_PUBLICA" ANTES de persistir
qualquer coisa (nunca guarda nem repassa pra IA um item AREA_LOGADA) -
usa o controle de acesso exatamente como a BTG o expoe, em vez de
ignora-lo. A pagina www.btgpactual.com/acoes/ultimos-relatorios (SPA
distinta, dominio diferente) continua bloqueada pra navegador automatizado
(Chromium/Playwright, 0/8 tentativas, ver auditorias anteriores) - mas
esse coletor nunca depende dela: le direto a API publica do dominio
content.btgpactual.com, que serve a MESMA area (research) sem esse
bloqueio.

Link persistido: nao foi encontrada, no bundle Angular publico da SPA
(content.btgpactual.com/research/home, 111 chunks JS verificados por
padrao de rota), uma rota de pagina com slug amigavel confirmada pro
detalhe de 1 item - por isso o link salvo e' o proprio endpoint de detalhe
da API (.../api/research/content-hub/analysis/{id}), que e' real, publico,
estavel e unico por item (nunca uma URL inventada/adivinhada).

Texto do relatorio (pro resumo por IA, obter_texto_publico): reconsulta o
DETALHE do item (nao reusa nada da coleta) e RECONFIRMA tier==AREA_PUBLICA
antes de devolver qualquer texto - defesa em profundidade, mesmo que um
item tenha virado AREA_LOGADA depois de coletado. O corpo (analyzeComponents.
body, HTML) vem do detalhe; extrator dedicado (nao o generico de
resumir.py, pensado pra paginas HTML/PDF via curl_cffi) porque o link
persistido e' um endpoint JSON, nao uma pagina."""

import re

import requests
from bs4 import BeautifulSoup

from .base import HEADERS, TIMEOUT, permitido

BASE_URL = "https://content.btgpactual.com"
FILTER_URL = f"{BASE_URL}/api/research/content-hub/analysis/filter"
DETAIL_URL = f"{BASE_URL}/api/research/content-hub/analysis/{{id}}"

_NOME_CASA = "BTG Pactual Research"
_TIER_PUBLICO = "AREA_PUBLICA"

# 4 paginas x 25 = 100 itens mais recentes (ordenados por referenceDate
# desc, confirmado na investigacao) - cobre varios dias mesmo em dia cheio
# de publicacoes; o gate de 30min do research (store.precisa_recoletar) e'
# quem evita recoleta constante, igual as outras casas.
_PAGINAS_POR_COLETA = 4
_TAMANHO_PAGINA = 25

# tickers aparecem no "caption" ("Análise | TOTS3, LWSA3, INTB3") quando
# analyzeAsset vem vazio (maioria dos itens AREA_PUBLICA testados, que sao
# analises macro/tecnicas sem 1 ativo especifico associado na estrutura
# da API) - mesmo padrao de ticker usado no resto do projeto (4 letras +
# 1-2 digitos).
_TICKER_NO_CAPTION = re.compile(r"\b([A-Z]{4}\d{1,2})\b")

_ID_NO_LINK = re.compile(r"/([^/]+)$")

_ultimo_motivo_falha = None


def motivo_ultima_falha() -> str | None:
    """Detalhe da ultima falha TOTAL de obter_relatorios (nenhuma pagina
    respondeu) - None se a ultima chamada teve sucesso (mesmo parcial,
    pelo menos 1 pagina OK) ou nenhuma chamada foi feita ainda nesta
    sessao do processo."""
    return _ultimo_motivo_falha


def _requisitar_pagina(pagina: int, timeout: float = TIMEOUT) -> list | None:
    """POST na pagina `pagina` do endpoint de listagem (body {} - a API
    aceita e devolve tudo, paginacao e' so' via query string). None se
    essa pagina falhar - quem chama decide se usa o que já tiver vindo
    de outras paginas."""
    url = f"{FILTER_URL}?pageNumber={pagina}&pageSize={_TAMANHO_PAGINA}"
    try:
        r = requests.post(url, headers=HEADERS, json={}, timeout=timeout)
        if r.status_code != 200:
            return None, f"pagina {pagina}: HTTP {r.status_code}"
        dados = r.json()
        return dados.get("response") or [], None
    except Exception as e:
        return None, f"pagina {pagina}: {type(e).__name__}: {e}"


def testar_conexao(timeout: float = 5) -> tuple:
    """So testa se a pagina 1 do endpoint de listagem responde - usado
    pelo painel DIAGNOSTICO DE FONTES. Retorna (ok, detalhe)."""
    if not permitido(FILTER_URL):
        return False, "bloqueado pelo robots.txt"
    itens, erro = _requisitar_pagina(1, timeout=timeout)
    if itens is None:
        return False, erro or "falhou"
    return True, f"OK ({len(itens)} itens na pagina 1)"


def _tickers(item: dict) -> list:
    tickers = [
        a["asset"]["ticker"]
        for a in (item.get("analyzeAsset") or [])
        if (a.get("asset") or {}).get("ticker")
    ]
    if tickers:
        return tickers
    caption = item.get("caption") or ""
    if "|" in caption:
        return _TICKER_NO_CAPTION.findall(caption.split("|", 1)[1])
    return []


def _autor(item: dict) -> str:
    return ", ".join(a["name"].strip() for a in (item.get("authors") or []) if a.get("name"))


def _setor(item: dict) -> str:
    setores = {
        (a.get("asset") or {}).get("sector", {}).get("name")
        for a in (item.get("analyzeAsset") or [])
        if (a.get("asset") or {}).get("sector", {}).get("name")
    }
    return ", ".join(sorted(setores))


def _link(item: dict) -> str:
    return DETAIL_URL.format(id=item["id"])


def _item_relatorio(item: dict) -> dict:
    tickers = _tickers(item)
    return {
        "casa": _NOME_CASA,
        "titulo": (item.get("caption") or "Análise BTG").strip(),
        "data": (item.get("referenceDate") or "")[:10],
        "autor": _autor(item),
        "tipo": "ACOES" if tickers else "MACRO",
        "setor": _setor(item),
        "tickers": tickers,
        "link": _link(item),
    }


def obter_relatorios() -> list | None:
    """Itens AREA_PUBLICA das paginas mais recentes do content-hub de
    research (formato comum: casa, titulo, data, autor, tipo, setor,
    tickers, link). NUNCA inclui item AREA_LOGADA nem item sem tier
    reconhecido - filtro aplicado aqui, antes de qualquer persistencia.
    None so' se NENHUMA pagina responder; se so' algumas falharem, retorna
    o que as outras trouxerem (mesmo padrao de degradacao gradual que
    xp.py usa entre categorias)."""
    global _ultimo_motivo_falha
    if not permitido(FILTER_URL):
        _ultimo_motivo_falha = "bloqueado pelo robots.txt"
        return None

    relatorios = []
    algum_sucesso = False
    ultimo_erro = None
    for pagina in range(1, _PAGINAS_POR_COLETA + 1):
        itens, erro = _requisitar_pagina(pagina)
        if itens is None:
            ultimo_erro = erro
            continue
        algum_sucesso = True
        for item in itens:
            # isolado por item (mesmo padrao de genial.py/xp.py): 1 item
            # com campo inesperado ausente nao pode descartar os outros
            # que ja' vieram validos na mesma pagina.
            try:
                if item.get("tier") != _TIER_PUBLICO:
                    continue
                relatorios.append(_item_relatorio(item))
            except Exception:
                continue

    if not algum_sucesso:
        _ultimo_motivo_falha = f"todas as {_PAGINAS_POR_COLETA} paginas falharam; ultima: {ultimo_erro or 'nenhum erro capturado'}"
        return None
    _ultimo_motivo_falha = None
    return relatorios or None


def _id_do_link(link: str) -> str | None:
    m = _ID_NO_LINK.search(link or "")
    return m.group(1) if m else None


def obter_texto_publico(link: str) -> tuple:
    """Extrator de texto pro link de um item (usado no lugar do 'baixa a
    pagina publica' generico - ver CASAS['btg']['extrator_texto'] em
    data/research/__init__.py). Reconsulta o endpoint de DETALHE (nao usa
    nenhum texto que porventura tenha sido guardado na coleta - sempre
    busca de novo) e RECONFIRMA tier=="AREA_PUBLICA" antes de devolver
    qualquer texto - defesa em profundidade: mesmo que o item tenha virado
    AREA_LOGADA depois da coleta (ou por algum outro motivo o link nao
    aponte mais pra um item publico), o resumo por IA NUNCA roda em cima
    de conteudo de area logada. Retorna (texto, motivo_falha)."""
    item_id = _id_do_link(link)
    if not item_id:
        return None, "link sem id reconhecível"
    if not permitido(link):
        return None, "bloqueado pelo robots.txt"
    try:
        r = requests.get(link, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code} ao buscar detalhe"
        item = r.json()
    except Exception as e:
        return None, f"erro ao buscar detalhe: {type(e).__name__}: {e}"

    if item.get("tier") != _TIER_PUBLICO:
        return None, "item deixou de ser AREA_PUBLICA (ou tier desconhecido) - resumo bloqueado por segurança"

    html = (item.get("analyzeComponents") or {}).get("body") or ""
    texto = BeautifulSoup(html, "html.parser").get_text(separator=" ").strip()
    if len(texto) < 200:
        return None, "conteúdo muito curto (provavelmente item sem corpo de análise)"
    return texto, None
