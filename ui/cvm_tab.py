# -*- coding: utf-8 -*-
"""Interface da fase CVM: documentos oficiais (fato relevante, comunicado
ao mercado, proventos, calendario) das empresas da watchlist. Layout
wire (DATA | TICKER | TIPO | ASSUNTO), FATO RELEVANTE com tag em
destaque. Clique no assunto abre um card com resumo por IA (sob demanda)
e botao pra abrir o documento original.

Auto-contido (CSS proprio, nao importa nada de ui/news_tab.py) porque
esse arquivo esta sendo editado por outra sessao em paralelo - depender
dos internos dele aqui seria fragil."""

import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from data.cvm import TIPO_LABEL, obter_documentos_cvm, obter_documentos_watchlist, obter_resumo_documento

_TZ_SP = ZoneInfo("America/Sao_Paulo")

_ORDEM_TIPOS = ["FATO_RELEVANTE", "COMUNICADO", "RESULTADOS", "PROVENTOS", "CALENDARIO"]

_CLASSE_TIPO = {
    "FATO_RELEVANTE": "cvm-tipo-destaque",
    "COMUNICADO": "cvm-tipo-normal",
    "RESULTADOS": "cvm-tipo-normal",
    "PROVENTOS": "cvm-tipo-normal",
    "CALENDARIO": "cvm-tipo-normal",
}

_JANELA_PADRAO_DIAS = 30
_LIMITE_PADRAO = 50
_TRUNCA_ASSUNTO = 100

_COLS = [88, 62, 118, 1]  # DATA / TICKER / TIPO / ASSUNTO (o 1 e' peso relativo, cresce pra preencher)

_CSS_CVM = """
.cvm-data { color:var(--cinza); white-space:nowrap; font-size:12.5px; }
.cvm-ticker { color:var(--destaque); font-weight:600; white-space:nowrap; font-size:12.5px; }
.cvm-tipo {
    display:inline-block; padding:0.04rem 0.32rem; border-radius:2px;
    font-size:10px; font-weight:700; letter-spacing:0.02em; white-space:nowrap;
}
.cvm-tipo-destaque { background:var(--destaque); color:var(--bg); }
.cvm-tipo-normal { background:transparent; color:var(--cinza); border:1px solid var(--borda); }
.cvm-divider { border-bottom:1px solid #1A1A1A; margin:0.1rem 0 0.25rem 0; }

div[class*="st-key-cvm-assunto-"] button {
    background:transparent !important; border:none !important; box-shadow:none !important;
    color:var(--neutro) !important; text-decoration:none !important; text-align:left !important;
    justify-content:flex-start !important; padding:0 !important; margin:0 !important;
    min-height:auto !important; height:auto !important;
    font-family:'IBM Plex Mono', monospace !important; font-size:12.5px !important; font-weight:400 !important;
    white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
    width:100% !important; display:block !important;
}
div[class*="st-key-cvm-assunto-"] button:hover { color:var(--destaque) !important; background:transparent !important; }
div[class*="st-key-cvm-assunto-"] button p {
    color:inherit !important; font-size:inherit !important; text-align:left !important;
    white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
}

.cvm-resumo { color:var(--neutro); font-size:0.85rem; line-height:1.5; margin-bottom:1.1rem; }

[data-testid="stButtonGroup"] button {
    background-color: var(--painel-bg) !important; border: 1px solid var(--borda) !important;
    color: var(--cinza) !important; border-radius: 0 !important; font-size: 0.75rem !important;
    padding: 0.05rem 0.6rem !important; min-height: 24px !important; box-shadow: none !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"] {
    background-color: var(--destaque) !important; border-color: var(--destaque) !important;
    color: #000000 !important; font-weight: 600;
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_CVM}</style>", unsafe_allow_html=True)


def _fmt_data(data_iso: str) -> str:
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except Exception:
        return data_iso


def _dentro_de_dias(data_iso: str, dias: int) -> bool:
    try:
        dt = datetime.fromisoformat(data_iso)
    except Exception:
        return False
    return (datetime.now(_TZ_SP) - dt) <= timedelta(days=dias)


def _truncar(texto: str, limite: int = _TRUNCA_ASSUNTO) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


@st.dialog("DOCUMENTO CVM", width="large")
def _abrir_card(d: dict):
    st.markdown(f"**{html.escape(d['assunto'])}**")
    st.caption(f"{d['ticker']} · {_fmt_data(d['data'])} · {d['categoria_original']}")

    classe = _CLASSE_TIPO.get(d["tipo"], "cvm-tipo-normal")
    st.markdown(f"<span class='cvm-tipo {classe}'>{d['tipo_label']}</span>", unsafe_allow_html=True)

    st.markdown("<div class='w-card-divisor' style='border-top:1px solid var(--borda); margin:0.6rem 0;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Resumo</div>", unsafe_allow_html=True)

    with st.spinner("Gerando resumo..."):
        resultado = obter_resumo_documento(d["link"], d["assunto"])

    if resultado["resumo"]:
        st.markdown(f"<div class='cvm-resumo'>{html.escape(resultado['resumo'])}</div>", unsafe_allow_html=True)
    else:
        st.caption("resumo indisponível")
        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

    st.link_button("ABRIR DOCUMENTO ↗", d["link"], use_container_width=True)


def _linha_documento(d: dict, idx: int, prefixo: str):
    col_data, col_ticker, col_tipo, col_assunto = st.columns(_COLS, gap="xsmall", vertical_alignment="center")

    with col_data:
        st.markdown(f"<div class='cvm-data'>{_fmt_data(d['data'])}</div>", unsafe_allow_html=True)
    with col_ticker:
        st.markdown(f"<div class='cvm-ticker'>{d['ticker']}</div>", unsafe_allow_html=True)
    with col_tipo:
        classe = _CLASSE_TIPO.get(d["tipo"], "cvm-tipo-normal")
        st.markdown(f"<span class='cvm-tipo {classe}'>{d['tipo_label']}</span>", unsafe_allow_html=True)
    with col_assunto:
        chave = f"cvm-assunto-{prefixo}-{idx}-{abs(hash(d['link']))}"
        if st.button(_truncar(d["assunto"]), key=chave, help=d["assunto"]):
            _abrir_card(d)

    st.markdown("<div class='cvm-divider'></div>", unsafe_allow_html=True)


def _renderizar_lista(itens: list, prefixo: str):
    for idx, d in enumerate(itens):
        _linha_documento(d, idx, prefixo)


def render_cvm(prefs: dict):
    """Ponto de entrada da aba CVM, chamado pelo app.py."""
    _injetar_css()

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CVM</div>', unsafe_allow_html=True)

        watchlist = prefs.get("watchlist") or []
        if not watchlist:
            st.info("Adicione tickers na barra lateral para ver documentos da CVM.")
            return

        documentos, falhas = obter_documentos_watchlist(watchlist)

        if falhas:
            st.warning("Indisponível no momento: " + ", ".join(falhas) + ".")

        if not documentos:
            st.info("Nenhum documento da CVM encontrado para os tickers da sua watchlist no momento.")
            return

        st.caption(
            "Fatos relevantes, comunicados ao mercado, avisos aos acionistas (proventos) e calendário "
            "de eventos, via dados abertos da CVM — atualização diária/semanal da fonte (não é em tempo "
            "real; para o texto oficial imediato, consulte o RAD/ENET da CVM). Clique no assunto para "
            "ver o resumo."
        )

        tickers_no_feed = ["TODOS"] + sorted({d["ticker"] for d in documentos})
        tipos_no_feed = ["TODOS"] + [t for t in _ORDEM_TIPOS if t in {d["tipo"] for d in documentos}]

        filtro_ticker = st.pills(
            "Ticker", tickers_no_feed, default="TODOS", selection_mode="single", key="cvm_pill_ticker",
        ) or "TODOS"
        filtro_tipo = st.pills(
            "Tipo", tipos_no_feed, default="TODOS", selection_mode="single",
            format_func=lambda t: TIPO_LABEL.get(t, t), key="cvm_pill_tipo",
        ) or "TODOS"

        base = [
            d for d in documentos
            if (filtro_ticker == "TODOS" or d["ticker"] == filtro_ticker)
            and (filtro_tipo == "TODOS" or d["tipo"] == filtro_tipo)
        ]

        if not base:
            st.info("Nenhum documento com esses filtros.")
            return

        if "cvm_ver_mais" not in st.session_state:
            st.session_state.cvm_ver_mais = False
        if "cvm_limite" not in st.session_state:
            st.session_state.cvm_limite = _LIMITE_PADRAO

        if st.session_state.cvm_ver_mais:
            candidatos = base
        else:
            candidatos = [d for d in base if _dentro_de_dias(d["data"], _JANELA_PADRAO_DIAS)] or base

        mostrar = candidatos[: st.session_state.cvm_limite]

        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0 0.4rem 0;'>{len(mostrar)} de {len(candidatos)} documento(s)</div>",
            unsafe_allow_html=True,
        )

        _renderizar_lista(mostrar, prefixo="feed")

        falta_mostrar = len(candidatos) - len(mostrar)
        falta_janela = not st.session_state.cvm_ver_mais and len(base) > len(candidatos)
        if falta_mostrar > 0 or falta_janela:
            if st.button("VER MAIS", key="cvm_ver_mais_btn"):
                st.session_state.cvm_ver_mais = True
                st.session_state.cvm_limite += _LIMITE_PADRAO
                st.rerun()


def render_cvm_ticker(ticker: str, prefs: dict):
    """Bloco compacto com os documentos mais recentes de UM ticker, pra
    encaixar na aba EQUITY (ex: dentro de um st.container(border=True))."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">CVM</div>', unsafe_allow_html=True)

    documentos = obter_documentos_cvm(ticker)
    if documentos is None:
        st.warning("Fonte da CVM indisponível no momento.")
        return
    if not documentos:
        st.info("Nenhum documento recente da CVM encontrado.")
        return

    _renderizar_lista(documentos[:8], prefixo=f"eq-{ticker}")
