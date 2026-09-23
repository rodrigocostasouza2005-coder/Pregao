# -*- coding: utf-8 -*-
"""Interface da fase NOTICIAS, estilo "wire" de terminal financeiro: uma
linha densa por noticia (HORA | TICKER | SELO | MANCHETE | Nº FONTES).
Clique na manchete abre um card (st.dialog) com selo+score explicado,
veiculos com link, tickers citados, resumo sob demanda e botao pra abrir
a materia. render_news(prefs) pra aba NEWS (feed da watchlist) e
render_news_ticker(ticker, prefs) pro bloco compacto na aba EQUITY.

Modulo tambem exporta o renderizador de lista/card (_renderizar_lista,
_abrir_card) pra reuso da aba TOP MERCADO (ui/top_mercado_tab.py)."""

import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from data.news import SELO_MENCAO, eh_fonte_confiavel, obter_noticias, obter_noticias_watchlist, obter_resumo_grupo, ordenar_fontes_para_resumo

_TZ_SP = ZoneInfo("America/Sao_Paulo")

_ORDEM_SELOS = ["PROVÁVEL", "NÃO CONFIRMADA", "SUSPEITA", SELO_MENCAO]

_CLASSE_SELO = {
    "PROVÁVEL": "selo-provavel",
    "NÃO CONFIRMADA": "selo-naoconfirmada",
    "SUSPEITA": "selo-suspeita",
    SELO_MENCAO: "selo-mencao",
}

_SELO_ABREV = {
    "PROVÁVEL": "PROV",
    "NÃO CONFIRMADA": "N.CONF",
    "SUSPEITA": "SUSP",
    SELO_MENCAO: "MENÇ",
}

_JANELA_PADRAO_HORAS = 48
_LIMITE_PADRAO = 50
_TRUNCA_MANCHETE = 92

# larguras relativas das colunas (nao sao px exatos - st.columns usa peso
# relativo -, mas na mesma proporcao pedida: HORA~95/TICKER~60/SELO~78/
# MANCHETE~resto/FONTES~90 - o suficiente pra nada colidir ou cortar).
# Nas linhas do TOP MERCADO (identificadas por n['importancia'] existir)
# entra mais uma coluna estreita pro numero do ranking, separada da hora
# (as duas juntas numa coluna so cortavam a data - "#1 · 21/09 2...").
_COLS_COM_TICKER = [95, 60, 78, 560, 90]
_COLS_SEM_TICKER = [95, 78, 560, 90]
_COLS_RANK_COM_TICKER = [55, 90, 70, 78, 480, 90]
_COLS_RANK_SEM_TICKER = [55, 90, 78, 480, 90]

# CSS proprio do layout wire, injetado via st.markdown (nao mexe em
# style.css, que e' de outra sessao) - reaproveita as variaveis de tema
# ja definidas la (--bg/--neutro/--cinza/--alta/--baixa/--destaque), entao
# acompanha tema/densidade escolhidos pelo usuario. Tag de selo usa
# var(--bg) como cor de texto sobre o tom de destaque: os tons de
# alta/baixa/cinza de cada tema ja sao escolhidos p/ contraste legivel
# contra --bg (uso normal do app), entao o inverso tende a manter
# contraste bom nos 4 temas sem precisar de logica por tema aqui.
#
# .st-key-news-manchete-* : Streamlit aplica automaticamente a classe
# "st-key-<key>" no wrapper de qualquer elemento com key= (mesmo
# mecanismo ja usado em style.css pra .st-key-nav_secao) - usamos isso
# pra transformar o st.button da manchete num link discreto sem tocar
# em style.css. Selector com [class*=] pega qualquer key que comece com
# esse prefixo, mesmo com o sufixo variando por linha/hash.
_CSS_WIRE = """
.w-hora, .w-fontes { color:var(--cinza); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.w-ticker { color:var(--destaque); font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.selo-tag {
    display:inline-block;
    padding:0.04rem 0.32rem;
    border-radius:2px;
    font-size:10px;
    font-weight:700;
    letter-spacing:0.02em;
    white-space:nowrap;
    cursor:help;
    text-align:center;
}
.selo-provavel { background:var(--alta); color:var(--bg); }
.selo-naoconfirmada { background:var(--cinza); color:var(--bg); }
.selo-suspeita { background:var(--baixa); color:var(--bg); }
.selo-mencao { background:transparent; color:var(--cinza); border:1px solid var(--cinza); }

div[class*="st-key-news-manchete-"] button,
div[class*="st-key-top-manchete-"] button {
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
    color:var(--neutro) !important;
    text-decoration:none !important;
    text-align:left !important;
    justify-content:flex-start !important;
    padding:0 !important;
    margin:0 !important;
    min-height:auto !important;
    height:auto !important;
    font-family:'IBM Plex Mono', monospace !important;
    font-size:12.5px !important;
    font-weight:400 !important;
    letter-spacing:0 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    width:100% !important;
    display:block !important;
}
div[class*="st-key-news-manchete-"] button:hover,
div[class*="st-key-top-manchete-"] button:hover {
    color:var(--destaque) !important;
    background:transparent !important;
}
div[class*="st-key-news-manchete-"] button p,
div[class*="st-key-top-manchete-"] button p {
    color:inherit !important;
    font-size:inherit !important;
    text-align:left !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
}

.w-divider { border-bottom:1px solid #1A1A1A; margin:0.1rem 0 0.25rem 0; }

.w-veic-link { color:var(--destaque) !important; text-decoration:none !important; font-size:0.82rem; opacity:0.85; }
.w-veic-link:hover { opacity:1; text-decoration:underline !important; }

.w-ticker-tag {
    display:inline-block; margin:0.15rem 0.3rem 0 0; padding:0.05rem 0.4rem;
    border:1px solid var(--borda); border-radius:2px; font-size:0.72rem;
    color:var(--cinza);
}
.w-ticker-tag-watch { border-color:var(--destaque); color:var(--destaque); font-weight:600; }
.w-regiao-tag {
    font-size:0.55rem; color:var(--cinza); border:1px solid var(--borda);
    border-radius:2px; padding:0 0.18rem; margin-left:0.25rem; vertical-align:middle;
}
.w-ticker-tag-mini {
    display:inline-block; margin-right:0.2rem; padding:0.01rem 0.28rem;
    border:1px solid var(--borda); border-radius:2px; font-size:0.62rem;
    color:var(--cinza);
}

.w-resumo-dialogo { color:var(--neutro); font-size:0.85rem; line-height:1.5; margin-bottom:1.1rem; }
.w-card-divisor { border-top:1px solid var(--borda); margin:0.55rem 0; }

/* pills de filtro: retas e compactas, no padrao dos botoes do terminal.
   Nesta versao do Streamlit, st.pills E st.segmented_control renderizam
   os dois sob data-testid="stButtonGroup" (conferido no bundle JS: nao
   existe "stPills" nem "stSegmentedControl" ali) - as regras de
   style.css pra esses dois seletores nunca bateram por isso. Esta regra
   e' a que efetivamente aplica. */
[data-testid="stButtonGroup"] button {
    background-color: var(--painel-bg) !important;
    border: 1px solid var(--borda) !important;
    color: var(--cinza) !important;
    border-radius: 0 !important;
    font-size: 0.75rem !important;
    padding: 0.05rem 0.6rem !important;
    min-height: 24px !important;
    box-shadow: none !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"] {
    background-color: var(--destaque) !important;
    border-color: var(--destaque) !important;
    color: #000000 !important;
    font-weight: 600;
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_WIRE}</style>", unsafe_allow_html=True)


def _fmt_hora(data_iso: str) -> str:
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m %H:%M")
    except Exception:
        return data_iso


def _dentro_de_horas(data_iso: str, horas: int) -> bool:
    try:
        dt = datetime.fromisoformat(data_iso)
    except Exception:
        return False
    return (datetime.now(_TZ_SP) - dt) <= timedelta(hours=horas)


def _texto_tag(n: dict) -> str:
    abrev = _SELO_ABREV.get(n["selo"], n["selo"])
    if n["selo"] == SELO_MENCAO:
        return abrev
    return f"{abrev} {n['score']}"


def _tooltip_regras(n: dict) -> str:
    if not n["regras"]:
        return "score base, nenhuma regra especial se aplicou"
    return "; ".join(n["regras"])


def _truncar(texto: str, limite: int = _TRUNCA_MANCHETE) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _plural_fontes(qtd: int) -> str:
    return f"{qtd} fonte{'s' if qtd != 1 else ''}"


def _bloco_hora_coluna(n: dict) -> str:
    return f"<div class='w-hora'>{_fmt_hora(n['data'])}</div>"


def _bloco_rank_coluna(n: dict, idx: int) -> str:
    """So pras linhas do TOP MERCADO (identificadas por ter 'importancia'
    - ver data/news.py:obter_top_mercado): posicao no ranking, com o
    criterio do calculo (nº de fontes, recencia, veiculos confiaveis,
    temas de mercado) no tooltip - deixa explicito que e' estimativa,
    nao medicao real de audiencia. Mostra tambem a tag BR/INT (campo
    'regiao' - Parte D), pra distinguir a origem quando BRASIL e
    INTERNACIONAL aparecem juntos (view TUDO)."""
    tooltip = html.escape("estimativa de relevância — " + "; ".join(n["criterio_ranking"]))
    regiao = n.get("regiao")
    badge = f"<span class='w-regiao-tag'>{regiao}</span>" if regiao else ""
    if n.get("ao_vivo"):
        badge += "<span class='w-regiao-tag' style='color:var(--destaque); border-color:var(--destaque);' title='cobertura contínua, não é uma matéria específica'>AO VIVO</span>"
    return f"<div class='w-hora' style='cursor:help;' title='{tooltip}'>#{idx + 1}{badge}</div>"


def _tickers_do_item(n: dict) -> list:
    """Itens fundidos entre tickers (data/news.py:_mesclar_entre_tickers)
    perdem 'ticker' (singular) e ganham 'tickers' (lista, quando o fato
    envolve mais de uma empresa da watchlist) - usado onde precisamos do
    conjunto de tickers de UM item (filtro por ticker), nao so pra
    desenhar a coluna (ver _bloco_ticker_coluna)."""
    if n.get("ticker"):
        return [n["ticker"]]
    return n.get("tickers") or []


def _bloco_ticker_coluna(n: dict, watchlist: list) -> str:
    """Noticia de empresa (obter_noticias) tem n['ticker'] (um so, ja
    sabido de antemao); noticia do TOP MERCADO tem n['tickers'] (varios,
    extraidos do titulo) - essa funcao decide o que mostrar na coluna
    TICKER conforme o que existir."""
    if n.get("ticker"):
        return f"<div class='w-ticker'>{n['ticker']}</div>"
    tickers = n.get("tickers") or []
    if not tickers:
        return "<div class='w-ticker' style='color:var(--cinza);'>—</div>"
    partes = []
    for t in tickers[:2]:
        classe_extra = " w-ticker-tag-watch" if t in watchlist else ""
        partes.append(f"<span class='w-ticker-tag-mini{classe_extra}'>{t}</span>")
    if len(tickers) > 2:
        partes.append(f"<span class='cinza' style='font-size:0.65rem;'>+{len(tickers) - 2}</span>")
    return "<div style='white-space:nowrap; overflow:hidden;'>" + "".join(partes) + "</div>"


_MAX_VEICULOS_VISIVEIS = 6


def _linha_veiculos(fontes: list) -> str:
    """Veiculos do grupo numa linha corrida (' · '), confiaveis primeiro
    - se passar de _MAX_VEICULOS_VISIVEIS, o resto some atras de um
    "e mais N" expansivel (<details>), pra nao esticar o card."""
    vistos = set()
    unicos = []
    for f in fontes:
        if f["veiculo"] not in vistos:
            vistos.add(f["veiculo"])
            unicos.append(f)
    unicos.sort(key=lambda f: not eh_fonte_confiavel(f["veiculo"]))

    def _link(f):
        return f"<a class='w-veic-link' href='{f['link']}' target='_blank'>{html.escape(f['veiculo'])}</a>"

    visiveis, resto = unicos[:_MAX_VEICULOS_VISIVEIS], unicos[_MAX_VEICULOS_VISIVEIS:]
    linha = " · ".join(_link(f) for f in visiveis)

    if resto:
        itens_resto = " · ".join(_link(f) for f in resto)
        linha += (
            " · <details style='display:inline;'>"
            f"<summary style='display:inline; cursor:pointer; color:var(--cinza);'>e mais {len(resto)}</summary>"
            f" {itens_resto}</details>"
        )
    return linha


@st.dialog("NOTÍCIA", width="large")
def _abrir_card(n: dict, watchlist: list):
    """Card com os detalhes completos do grupo - resumo e' gerado aqui,
    na hora do clique (nunca antes), com cache de obter_resumo_grupo."""
    st.markdown(f"**{html.escape(n['titulo'])}**")
    st.caption(_fmt_hora(n["data"]))

    classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
    sufixo_score = "" if n["selo"] == SELO_MENCAO else f" · {n['score']}"
    st.markdown(
        f"<span class='selo-tag {classe_selo}'>{n['selo']}{sufixo_score}</span>",
        unsafe_allow_html=True,
    )
    for regra in n["regras"]:
        st.markdown(f"<div class='cinza' style='font-size:0.76rem; margin-top:0.15rem;'>• {html.escape(regra)}</div>", unsafe_allow_html=True)

    if n.get("tickers"):
        tags = "".join(
            f"<span class='w-ticker-tag{' w-ticker-tag-watch' if t in watchlist else ''}'>{t}</span>"
            for t in n["tickers"]
        )
        st.markdown(f"<div style='margin-top:0.4rem;'>{tags}</div>", unsafe_allow_html=True)

    st.markdown("<div class='w-card-divisor'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Veículos ({n['fontes_count']})</div>"
        f"<div style='font-size:0.82rem;'>{_linha_veiculos(n['fontes'])}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='w-card-divisor'></div>", unsafe_allow_html=True)
    st.markdown("<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Resumo</div>", unsafe_allow_html=True)
    with st.spinner("Gerando resumo..."):
        fontes_ordenadas = ordenar_fontes_para_resumo(n["fontes"])
        resultado = obter_resumo_grupo(n["titulo"], fontes_ordenadas)

    link_final = n["link"]
    if resultado["resumo"]:
        st.markdown(f"<div class='w-resumo-dialogo'>{html.escape(resultado['resumo'])}</div>", unsafe_allow_html=True)
        link_final = resultado["link_original"] or n["link"]
    else:
        motivo = resultado.get("motivo_indisponivel") or "motivo desconhecido"
        st.caption(f"resumo indisponível ({motivo})")

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    st.link_button("ABRIR MATÉRIA ↗", link_final, use_container_width=True)


def _linha_noticia(n: dict, idx: int, mostrar_ticker: bool, prefixo: str, watchlist: list):
    eh_ranking = "importancia" in n
    if eh_ranking:
        cols_pesos = _COLS_RANK_COM_TICKER if mostrar_ticker else _COLS_RANK_SEM_TICKER
    else:
        cols_pesos = _COLS_COM_TICKER if mostrar_ticker else _COLS_SEM_TICKER
    colunas = st.columns(cols_pesos, gap="xsmall", vertical_alignment="center")
    i = 0

    if eh_ranking:
        with colunas[i]:
            st.markdown(_bloco_rank_coluna(n, idx), unsafe_allow_html=True)
        i += 1

    with colunas[i]:
        st.markdown(_bloco_hora_coluna(n), unsafe_allow_html=True)
    i += 1

    if mostrar_ticker:
        with colunas[i]:
            st.markdown(_bloco_ticker_coluna(n, watchlist), unsafe_allow_html=True)
        i += 1

    with colunas[i]:
        classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
        tooltip = html.escape(_tooltip_regras(n))
        st.markdown(f"<span class='selo-tag {classe_selo}' title='{tooltip}'>{_texto_tag(n)}</span>", unsafe_allow_html=True)
    i += 1

    with colunas[i]:
        chave_botao = f"news-manchete-{prefixo}-{idx}-{abs(hash(n['link']))}"
        if st.button(_truncar(n["titulo"]), key=chave_botao, help=n["titulo"]):
            _abrir_card(n, watchlist)
    i += 1

    with colunas[i]:
        st.markdown(f"<div class='w-fontes'>{_plural_fontes(n['fontes_count'])}</div>", unsafe_allow_html=True)

    st.markdown("<div class='w-divider'></div>", unsafe_allow_html=True)


def _renderizar_lista(itens: list, mostrar_ticker: bool, prefixo: str, watchlist: list):
    """Reusado pela aba TOP MERCADO - lista + card, sem nenhum resumo
    automatico (so sob demanda, dentro do card)."""
    for idx, n in enumerate(itens):
        _linha_noticia(n, idx, mostrar_ticker, prefixo, watchlist)


def render_news(prefs: dict):
    """Ponto de entrada da aba NEWS, chamado pelo app.py. Feed de todos os
    tickers da watchlist, ordenado por data, com filtro compacto (pills)
    por ticker e selo. Padrão: últimas 48h, até 50 linhas, com VER MAIS
    pra expandir. Resumo só sob demanda, dentro do card (clique na
    manchete) - nada de resumo automático travando a lista."""
    _injetar_css()

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">NOTÍCIAS</div>', unsafe_allow_html=True)

        watchlist = prefs.get("watchlist") or []
        if not watchlist:
            st.info("Adicione tickers na barra lateral para ver notícias.")
            return

        noticias, falhas = obter_noticias_watchlist(watchlist)

        if falhas:
            st.warning("Indisponível no momento: " + ", ".join(falhas) + ".")

        if not noticias:
            st.info("Nenhuma notícia encontrada para os tickers da sua watchlist no momento.")
            return

        st.caption("Selo de confiabilidade calculado por regras simples (fonte, nº de veículos, linguagem) — não é uma verificação factual definitiva. Clique numa manchete para ver os detalhes.")

        tickers_no_feed = ["TODOS"] + sorted({t for n in noticias for t in _tickers_do_item(n)})
        selos_no_feed = ["TODOS"] + [s for s in _ORDEM_SELOS if s in {n["selo"] for n in noticias}]

        filtro_ticker = st.pills(
            "Ticker", tickers_no_feed, default="TODOS", selection_mode="single", key="news_pill_ticker",
        ) or "TODOS"
        filtro_selo = st.pills(
            "Selo", selos_no_feed, default="TODOS", selection_mode="single", key="news_pill_selo",
        ) or "TODOS"

        base = [
            n for n in noticias
            if (filtro_ticker == "TODOS" or filtro_ticker in _tickers_do_item(n))
            and (filtro_selo == "TODOS" or n["selo"] == filtro_selo)
        ]

        if not base:
            st.info("Nenhuma notícia com esses filtros.")
            return

        if "news_ver_mais" not in st.session_state:
            st.session_state.news_ver_mais = False
        if "news_limite" not in st.session_state:
            st.session_state.news_limite = _LIMITE_PADRAO

        if st.session_state.news_ver_mais:
            candidatas = base
        else:
            candidatas = [n for n in base if _dentro_de_horas(n["data"], _JANELA_PADRAO_HORAS)] or base

        mostrar = candidatas[: st.session_state.news_limite]

        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0 0.4rem 0;'>{len(mostrar)} de {len(candidatas)} notícia(s)</div>",
            unsafe_allow_html=True,
        )

        _renderizar_lista(mostrar, mostrar_ticker=True, prefixo="feed", watchlist=watchlist)

        falta_mostrar = len(candidatas) - len(mostrar)
        falta_janela = not st.session_state.news_ver_mais and len(base) > len(candidatas)
        if falta_mostrar > 0 or falta_janela:
            if st.button("VER MAIS", key="news_ver_mais_btn"):
                st.session_state.news_ver_mais = True
                st.session_state.news_limite += _LIMITE_PADRAO
                st.rerun()


def render_news_ticker(ticker: str, prefs: dict):
    """Bloco compacto com as noticias mais recentes de UM ticker, pra
    encaixar na aba EQUITY (ex: dentro de um st.container(border=True))."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">NOTÍCIAS</div>', unsafe_allow_html=True)

    noticias = obter_noticias(ticker)
    if noticias is None:
        st.warning("Fonte de notícias indisponível no momento.")
        return
    if not noticias:
        st.info("Nenhuma notícia recente encontrada.")
        return

    _renderizar_lista(noticias[:8], mostrar_ticker=False, prefixo=f"eq-{ticker}", watchlist=prefs.get("watchlist") or [])
