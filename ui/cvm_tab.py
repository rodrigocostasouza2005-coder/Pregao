# -*- coding: utf-8 -*-
"""Interface da aba CVM: documentos oficiais (fato relevante, comunicado
ao mercado, resultados, proventos, calendário) das empresas da watchlist.
Tabela DATA | TICKER | TIPO | DOCUMENTO/ASSUNTO, FATO RELEVANTE com badge
em destaque. Busca textual + filtros por ticker/tipo, tudo em memória
sobre os documentos já coletados (ver data/cvm.py) - nunca dispara nova
consulta à CVM ao digitar/filtrar/paginar. Clique no assunto abre um
card com resumo por IA (sob demanda) e botão pra abrir o documento
original.

Auto-contido (CSS próprio, não importa nada de ui/news_tab.py) - mesma
decisão de isolamento já documentada aqui antes.

Correção de raiz desta revisão: `st.columns([88, 62, 118, 1])` (versão
anterior) faz TODOS os números funcionarem como pesos relativos do MESMO
tipo - a coluna de assunto recebia 1/269 da largura (~0,4%), não "o
resto da tela" como o comentário antigo sugeria. Essa era a causa real
do conteúdo cortado à direita (não a truncagem em si, que já existia e
funcionava, mas a coluna que a continha era minúscula)."""

import html
from datetime import datetime
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

_TRUNCA_ASSUNTO = 200  # so' rede de seguranca - a CSS ellipsis (largura real
# da coluna) e' quem faz o corte visual de verdade; maior assunto real
# medido nos dados (2026-09-25, 653 docs de PETR4/VALE3/ITUB4) tem 139
# caracteres, entao 200 praticamente nunca aciona.
_TAMANHO_PAGINA = 50
_JANELA_PAGINACAO = 2  # paginas visiveis pra cada lado da atual, ver _paginacao

# pesos relativos (nao pixels - ver st.columns) pra DATA/TICKER/TIPO/ASSUNTO.
# ASSUNTO domina a largura de proposito (pedido explicito: "deve ocupar a
# maior parte da tela").
_COLS = [9, 8, 16, 55]

_CSS_CVM = """
.cvm-desc-principal { color:var(--neutro); font-size:0.82rem; margin-bottom:0.15rem; }
.cvm-desc-secundaria { color:var(--cinza); font-size:0.65rem; margin-bottom:0.7rem; }

.cvm-cabecalho { color:var(--cinza); font-size:10.5px; font-weight:600; letter-spacing:0.04em;
    text-transform:uppercase; padding-bottom:0.3rem; }
.cvm-cabecalho-divider { border-bottom:1px solid var(--borda); margin-bottom:0.15rem; }

.cvm-data { color:var(--cinza); white-space:nowrap; font-size:12.5px; }
.cvm-ticker { color:var(--destaque); font-weight:700; white-space:nowrap; font-size:12.5px; }
.cvm-tipo {
    display:inline-block; padding:0.15rem 0.45rem; border-radius:2px;
    font-size:10px; font-weight:700; letter-spacing:0.03em; white-space:nowrap;
    line-height:1.3;
}
.cvm-tipo-destaque { background:var(--destaque); color:var(--bg); }
.cvm-tipo-normal { background:transparent; color:var(--cinza); border:1px solid var(--borda); }
.cvm-divider { border-bottom:1px solid #1A1A1A; margin:0.15rem 0; }

div[class*="st-key-cvm-row-"] { border-radius:3px; transition:background-color 0.1s ease; }
div[class*="st-key-cvm-row-"]:hover { background-color:rgba(255,160,40,0.06); }
div[class*="st-key-cvm-row-"] { padding:0.28rem 0.3rem; }

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

.cvm-contador { color:var(--cinza); font-size:0.7rem; margin:0.4rem 0 0.5rem 0; }

div[class*="st-key-cvm-paginacao"] { margin-top:0.6rem; }
.cvm-paginacao-info { color:var(--cinza); font-size:0.68rem; margin:0 0 0.3rem 0; }

div[class*="st-key-cvm-pg-"] button, div[class*="st-key-cvm-nav-"] button {
    background-color:var(--painel-bg) !important; border:1px solid var(--borda) !important;
    color:var(--cinza) !important; border-radius:2px !important; font-size:0.72rem !important;
    padding:0.1rem 0.55rem !important; min-height:26px !important; box-shadow:none !important;
}
div[class*="st-key-cvm-pg-atual-"] button {
    background-color:var(--destaque) !important; border-color:var(--destaque) !important;
    color:#000000 !important; font-weight:700 !important;
}

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


def _truncar(texto: str, limite: int = _TRUNCA_ASSUNTO) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _normalizar_busca(texto: str) -> str:
    """minusculo + sem acento, pra busca textual simples (substring) sem
    diferenciar maiusculas/acentuacao - mesma ideia de data/cvm.py:_sem_acento,
    reimplementada aqui (funcao pequena, evita acoplar a interface a um
    helper privado de outro modulo so' por isso)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _combina_busca(d: dict, termo_normalizado: str) -> bool:
    if not termo_normalizado:
        return True
    campos = (d["ticker"], d["assunto"], d["tipo_label"], d.get("categoria_original") or "")
    alvo = _normalizar_busca(" ".join(campos))
    return termo_normalizado in alvo


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


def _cabecalho_tabela():
    col_data, col_ticker, col_tipo, col_assunto = st.columns(_COLS, gap="small")
    with col_data:
        st.markdown("<div class='cvm-cabecalho'>DATA</div>", unsafe_allow_html=True)
    with col_ticker:
        st.markdown("<div class='cvm-cabecalho'>TICKER</div>", unsafe_allow_html=True)
    with col_tipo:
        st.markdown("<div class='cvm-cabecalho'>TIPO</div>", unsafe_allow_html=True)
    with col_assunto:
        st.markdown("<div class='cvm-cabecalho'>DOCUMENTO / ASSUNTO</div>", unsafe_allow_html=True)
    st.markdown("<div class='cvm-cabecalho-divider'></div>", unsafe_allow_html=True)


def _linha_documento(d: dict, idx: int, prefixo: str):
    with st.container(key=f"cvm-row-{prefixo}-{idx}"):
        col_data, col_ticker, col_tipo, col_assunto = st.columns(_COLS, gap="small", vertical_alignment="center")

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


def _renderizar_lista(itens: list, prefixo: str, com_cabecalho: bool = True):
    if com_cabecalho:
        _cabecalho_tabela()
    for idx, d in enumerate(itens):
        _linha_documento(d, idx, prefixo)


def _paginacao(total_itens: int, chave_pagina: str) -> int:
    """Navegação por página (Anterior/Próxima + janela de números ao redor
    da atual) sobre `total_itens` já filtrados. Retorna a página atual
    (1-based). Só fatia a lista em memória - nenhuma consulta nova."""
    total_paginas = max(1, -(-total_itens // _TAMANHO_PAGINA))  # ceil sem importar math
    pagina = st.session_state.get(chave_pagina, 1)
    pagina = min(max(1, pagina), total_paginas)
    st.session_state[chave_pagina] = pagina

    if total_paginas <= 1:
        return pagina

    inicio = (pagina - 1) * _TAMANHO_PAGINA + 1
    fim = min(pagina * _TAMANHO_PAGINA, total_itens)

    st.markdown(
        f"<div class='cvm-paginacao-info'>{inicio}–{fim} de {total_itens}</div>",
        unsafe_allow_html=True,
    )

    # janela de numeros ao redor da pagina atual + primeira/ultima sempre
    # visiveis, com "…" no lugar do que ficou de fora - mesma ideia visual
    # do wireframe pedido, sem exigir um widget de paginacao pronto (o
    # projeto nao usa nenhum ate' hoje)
    numeros = sorted({
        1, total_paginas, pagina,
        *range(max(1, pagina - _JANELA_PAGINACAO), min(total_paginas, pagina + _JANELA_PAGINACAO) + 1),
    })

    n_botoes = len(numeros) + 2  # + Anterior/Proxima
    cols = st.columns(n_botoes, gap="small")

    with cols[0]:
        if st.button("‹ Anterior", key=f"cvm-nav-ant-{chave_pagina}", disabled=pagina <= 1):
            st.session_state[chave_pagina] = pagina - 1
            st.rerun()

    anterior_numero = None
    for i, num in enumerate(numeros):
        with cols[i + 1]:
            if anterior_numero is not None and num - anterior_numero > 1:
                st.markdown("<div class='cinza' style='text-align:center;'>…</div>", unsafe_allow_html=True)
            else:
                chave_botao = f"cvm-pg-atual-{chave_pagina}" if num == pagina else f"cvm-pg-{chave_pagina}-{num}"
                if st.button(str(num), key=chave_botao, disabled=(num == pagina)):
                    st.session_state[chave_pagina] = num
                    st.rerun()
        anterior_numero = num

    with cols[-1]:
        if st.button("Próxima ›", key=f"cvm-nav-prox-{chave_pagina}", disabled=pagina >= total_paginas):
            st.session_state[chave_pagina] = pagina + 1
            st.rerun()

    return pagina


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

        st.markdown(
            "<div class='cvm-desc-principal'>Fatos relevantes, comunicados, resultados, proventos e "
            "eventos divulgados pela CVM.</div>"
            "<div class='cvm-desc-secundaria'>Atualização periódica · dados públicos da CVM · clique no "
            "documento para ver o resumo</div>",
            unsafe_allow_html=True,
        )

        busca = st.text_input(
            "Buscar", placeholder="Buscar documentos...", label_visibility="collapsed", key="cvm_busca",
        )
        termo_busca = _normalizar_busca(busca.strip()) if busca else ""

        tickers_no_feed = ["TODOS"] + sorted({d["ticker"] for d in documentos})
        tipos_no_feed = ["TODOS"] + [t for t in _ORDEM_TIPOS if t in {d["tipo"] for d in documentos}]

        st.markdown("<div class='cinza' style='font-size:0.68rem; margin-bottom:0.1rem;'>TICKER</div>", unsafe_allow_html=True)
        filtro_ticker = st.pills(
            "Ticker", tickers_no_feed, default="TODOS", selection_mode="single",
            label_visibility="collapsed", key="cvm_pill_ticker",
        ) or "TODOS"

        st.markdown("<div class='cinza' style='font-size:0.68rem; margin:0.4rem 0 0.1rem 0;'>TIPO</div>", unsafe_allow_html=True)
        filtro_tipo = st.pills(
            "Tipo", tipos_no_feed, default="TODOS", selection_mode="single",
            format_func=lambda t: TIPO_LABEL.get(t, t), label_visibility="collapsed", key="cvm_pill_tipo",
        ) or "TODOS"

        base = [
            d for d in documentos
            if (filtro_ticker == "TODOS" or d["ticker"] == filtro_ticker)
            and (filtro_tipo == "TODOS" or d["tipo"] == filtro_tipo)
            and _combina_busca(d, termo_busca)
        ]

        # reseta pra pagina 1 sempre que o CONJUNTO filtrado mudar de
        # identidade (ticker/tipo/busca) - sem isso, trocar de filtro
        # com a pagina 3 selecionada podia deixar a tela vazia (pagina
        # que nao existe mais no novo total)
        fingerprint_filtro = (filtro_ticker, filtro_tipo, termo_busca)
        if st.session_state.get("cvm_fingerprint_filtro") != fingerprint_filtro:
            st.session_state["cvm_fingerprint_filtro"] = fingerprint_filtro
            st.session_state["cvm_pagina"] = 1

        if not base:
            st.markdown(
                "<div class='cvm-contador'>0 resultados encontrados</div>", unsafe_allow_html=True,
            )
            st.info("Nenhum documento com esses filtros.")
            return

        total_geral = len(documentos)
        if len(base) == total_geral:
            texto_contador = f"{total_geral} documentos"
        else:
            texto_contador = f"{len(base)} resultados · {total_geral} documentos"
        st.markdown(f"<div class='cvm-contador'>{texto_contador}</div>", unsafe_allow_html=True)

        pagina = st.session_state.get("cvm_pagina", 1)
        inicio = (pagina - 1) * _TAMANHO_PAGINA
        mostrar = base[inicio: inicio + _TAMANHO_PAGINA]

        _renderizar_lista(mostrar, prefixo="feed")

        with st.container(key="cvm-paginacao"):
            _paginacao(len(base), chave_pagina="cvm_pagina")


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

    _renderizar_lista(documentos[:8], prefixo=f"eq-{ticker}", com_cabecalho=False)
