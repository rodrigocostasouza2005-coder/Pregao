# -*- coding: utf-8 -*-
"""Aba RADAR - inteligência de investimentos (2026-10-09). Página central
que responde 3 perguntas: (1) O que mudou? (2) Onde vale investigar?
(3) O que pode dar errado? Zero coleta/lógica de dado própria - é
composição sobre data/radar.py (camada de agregação pura, que por sua
vez só combina o que data/research/historico.py, data/cvm.py,
data/eventos.py e data/prices.py já coletam) e reaproveita os dialogs
já existentes de NEWS/CVM (ui.news_tab.abrir_card_noticia/
ui.cvm_tab.abrir_card_documento) em vez de duplicar.

Carregamento sob demanda (pedido explícito - nunca tudo no primeiro
render): Mudanças de Tese e Catalisadores são baratos (leem dado já
persistido/cacheado) e aparecem direto; Valuation Radar mostra só os
indicadores já cacheados por ticker (nenhuma consulta NOVA), e o
comparativo setorial (que itera ~10-15 pares) só roda dentro de um
@st.dialog, aberto por um botão explícito - mesmo mecanismo de "resumo
por IA sob demanda" que o projeto já usa em RESEARCH/NEWS/CVM."""

import html
from datetime import date

import streamlit as st

import config
from data import radar
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM
from ui.cvm_tab import abrir_card_documento
from ui.news_tab import abrir_card_noticia

_CSS_RADAR = """
.radar-subtitulo { color: var(--cinza); font-size: 0.72rem; margin: 0.1rem 0 0.8rem 0; }
.radar-pergunta {
    font-size: 0.78rem; color: var(--destaque); letter-spacing: 0.04em; font-weight: 600;
    border-top: 1px solid var(--borda); padding-top: 0.8rem; margin-top: 1rem; margin-bottom: 0.5rem;
}
.radar-pergunta:first-of-type { border-top: none; margin-top: 0; }
.radar-alerta {
    border: 1px solid var(--borda); padding: 0.5rem 0.65rem; margin-bottom: 0.5rem;
    font-family: 'IBM Plex Mono', monospace;
}
.radar-alerta-topo { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.radar-ticker { color: var(--destaque); font-weight: 700; font-size: 0.85rem; }
.radar-categoria { color: var(--cinza); font-size: 0.68rem; letter-spacing: 0.03em; }
.radar-descricao { font-size: 0.82rem; margin-top: 0.3rem; line-height: 1.5; }
.radar-relevancia { color: var(--cinza); font-size: 0.72rem; margin-top: 0.25rem; line-height: 1.5; }
.radar-meta { color: var(--cinza); font-size: 0.64rem; margin-top: 0.35rem; }
.radar-meta a { color: var(--cinza); text-decoration: none; }
.radar-selo { font-size: 0.6rem; letter-spacing: 0.03em; padding: 0.1rem 0.4rem; border: 1px solid var(--borda); white-space: nowrap; }
.radar-selo-fato { color: var(--alta); border-color: var(--alta); }
.radar-selo-calculo { color: var(--destaque); border-color: var(--destaque); }
.radar-selo-insuficiente { color: var(--cinza); }
.radar-vazio { color: var(--cinza); font-size: 0.78rem; padding: 0.6rem 0; }
.radar-tabela { width: 100%; font-size: 0.76rem; border-collapse: collapse; }
.radar-tabela th { text-align: right; color: var(--cinza); font-size: 0.64rem; letter-spacing: 0.03em; padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda); }
.radar-tabela th:first-child, .radar-tabela td:first-child { text-align: left; }
.radar-tabela td { text-align: right; padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda); }
.radar-desatualizado { color: var(--cinza); font-size: 0.62rem; }
.radar-flag { color: var(--destaque); font-size: 0.64rem; display: block; text-align: left; margin-top: 0.15rem; }
.radar-stub { border: 1px solid var(--borda); padding: 0.8rem; font-size: 0.8rem; line-height: 1.6; color: var(--cinza); }
/* BUG REAL confirmado em screenshot + medicao de DOM (Playwright,
   2026-10-09): o wrapper interno que o proprio Streamlit gera ao redor
   de um st.markdown com HTML customizado (unsafe_allow_html=True) media
   uma altura ~16px MENOR que o conteudo real (confirmado via
   getBoundingClientRect em ambos) quando ha quebra de linha dupla (2x
   "br" seguidos) dentro de uma div com padding/borda propria - o proximo
   elemento (st.caption logo abaixo, ver _secao_risco) nascia nessa
   altura "errada", sobrepondo visualmente o fim do texto da caixa.
   margin-bottom na propria .radar-stub NAO resolve (testado e
   descartado) - o wrapper do Streamlit nao repassa a altura do filho
   pro pai nesse caso especifico; o fix real e' dar respiro no elemento
   SEGUINTE (o irmao stElementContainer logo depois do que contem a
   .radar-stub), que ai' sim empurra o proprio container pra baixo. */
div[data-testid="stElementContainer"]:has(.radar-stub) + div[data-testid="stElementContainer"] {
    margin-top: 1.1rem;
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_RADAR}</style>", unsafe_allow_html=True)


def _fmt_num(valor, casas, prefs, sufixo=""):
    if valor is None:
        return "—"
    return f"{config.formatar_numero(valor, casas, prefs['formato_numerico'])}{sufixo}"


def _selo_evidencia(tipo: str) -> str:
    classe = {
        radar.TIPO_FATO: "radar-selo-fato",
        radar.TIPO_CALCULO: "radar-selo-calculo",
        radar.TIPO_INSUFICIENTE: "radar-selo-insuficiente",
    }.get(tipo, "radar-selo-insuficiente")
    rotulo = {
        radar.TIPO_FATO: "FATO",
        radar.TIPO_CALCULO: "CÁLCULO INTERNO",
        radar.TIPO_INSUFICIENTE: "DADO INSUFICIENTE",
    }.get(tipo, tipo)
    return f"<span class='radar-selo {classe}'>{rotulo}</span>"


# ============================================================
# A. MUDANÇAS DE TESE
# ============================================================

def _linha_alerta(a: dict, prefs: dict):
    fonte_html = html.escape(a["fonte_label"] or "—")
    if a.get("fonte_url"):
        fonte_html = f"<a href='{html.escape(a['fonte_url'])}' target='_blank'>{fonte_html}</a>"
    horario = f" · coletado {a['horario_coleta'].strftime('%d/%m %H:%M')}" if a.get("horario_coleta") else ""

    potencial_txt = ""
    if a.get("potencial_pct_fonte") is not None:
        potencial_txt = f" · potencial (fonte): {_fmt_num(a['potencial_pct_fonte'], 1, prefs, '%')}"
    elif a.get("potencial_pct_calculado") is not None:
        potencial_txt = f" · potencial recalculado agora: {_fmt_num(a['potencial_pct_calculado'], 1, prefs, '%')} (cálculo interno, não é número da fonte)"

    st.markdown(
        f"<div class='radar-alerta'>"
        f"<div class='radar-alerta-topo'>"
        f"<span><span class='radar-ticker'>{a['ticker']}</span> "
        f"<span class='radar-categoria'>{html.escape(a['categoria'])}</span></span>"
        f"{_selo_evidencia(a['tipo_evidencia'])}"
        f"</div>"
        f"<div class='radar-descricao'>{html.escape(a['descricao'])}</div>"
        f"<div class='radar-relevancia'>{html.escape(a['relevancia'])}</div>"
        f"<div class='radar-meta'>evento em {a['data_evento'].strftime('%d/%m/%Y')}{horario}{potencial_txt} · fonte: {fonte_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _secao_mudancas_tese(tickers: list, janela: str, prefs: dict):
    st.markdown('<div class="radar-pergunta">O QUE MUDOU?</div>', unsafe_allow_html=True)
    alertas = radar.mudancas_tese(tuple(tickers), janela)
    if not alertas:
        st.markdown(
            f"<div class='radar-vazio'>Nenhuma mudança de tese verificada na janela "
            f"\"{janela.lower()}\" pros ativos selecionados. Isso significa que nada de novo foi "
            f"detectado nas fontes monitoradas - não que a tese está confirmada.</div>",
            unsafe_allow_html=True,
        )
        return
    for a in alertas:
        _linha_alerta(a, prefs)


# ============================================================
# B. VALUATION RADAR
# ============================================================

@st.dialog("COMPARÁVEIS DO SETOR", width="large")
def _dialog_comparaveis(ticker: str, prefs: dict):
    with st.spinner("Calculando medianas do setor (consulta ao vivo, pode levar alguns segundos)..."):
        comp = radar.comparaveis_setor(ticker)
    if comp.get("insuficiente"):
        st.warning(f"Dado insuficiente pra comparação setorial de {ticker}: {comp.get('motivo', 'sem pares válidos')}.")
        return
    st.caption(f"Setor: {comp['setor']} · {comp['pares_considerados']} papéis no universo (Ibovespa)")
    for rotulo, chave in (("P/L", "pl_mediana"), ("P/VP", "pvp_mediana"), ("Dividend yield", "dy_mediana")):
        valor = comp.get(chave)
        n = comp.get(f"{chave}_n", 0)
        if valor is None:
            st.markdown(f"**{rotulo}**: dado insuficiente (menos de 3 pares com valor válido - {n} disponível(is))")
        else:
            sufixo = "%" if chave == "dy_mediana" else "x"
            st.markdown(f"**{rotulo} mediano do setor**: {_fmt_num(valor, 2, prefs, sufixo)} ({n} pares considerados)")
    st.caption(
        "Mediana calculada agora, sobre os múltiplos atuais do yfinance pros outros papéis do "
        "mesmo setor (classificação setorial própria do PREGÃO) - não é um índice oficial nem "
        "estimativa de analista, é um cálculo interno pra dar contexto relativo."
    )


def _linha_valuation_html(linha: dict, prefs: dict) -> str:
    moeda_prefixo = config.PREFIXO_MOEDA.get(linha["moeda"], linha["moeda"])
    preco_txt = "—" if linha["preco"] is None else f"{moeda_prefixo} {_fmt_num(linha['preco'], 2, prefs)}"
    desatualizado = " <span class='radar-desatualizado'>(desatualizado)</span>" if linha["desatualizado"] else ""
    flags = "".join(f"<span class='radar-flag'>⚠ {html.escape(f)}</span>" for f in (linha.get("alerta_qualidade") or []))
    return (
        "<tr>"
        f"<td>{linha['ticker']}<br><span class='radar-desatualizado'>{html.escape(linha['setor'] or '—')}</span></td>"
        f"<td>{preco_txt}{desatualizado}</td>"
        f"<td>{_fmt_num(linha['pl'], 1, prefs)}</td>"
        f"<td>{_fmt_num(linha['pvp'], 2, prefs)}</td>"
        f"<td>{_fmt_num(linha['dividend_yield'], 2, prefs, '%')}</td>"
        f"<td>{_fmt_num(linha['roe'], 1, prefs, '%')}</td>"
        f"<td>{_fmt_num(linha['margem_liquida'], 1, prefs, '%')}</td>"
        f"<td>{_fmt_num(linha['divida_liquida_ebitda'], 1, prefs, 'x')}</td>"
        f"<td>{config.formatar_valor_mercado(linha['valor_mercado'], prefs['formato_numerico'], linha['moeda'])}{flags}</td>"
        "</tr>"
    )


def _secao_valuation(tickers: list, prefs: dict):
    linhas = radar.valuation_radar(tuple(tickers))
    linhas_validas = [l for l in linhas if l["preco"] is not None]
    if not linhas_validas:
        st.markdown("<div class='radar-vazio'>Sem cotação disponível pros ativos selecionados agora.</div>", unsafe_allow_html=True)
        return
    cabecalho = (
        "<tr><th>Ativo</th><th>Preço</th><th>P/L</th><th>P/VP</th><th>DY</th><th>ROE</th>"
        "<th>Margem líq.</th><th>Dív/EBITDA</th><th>Valor de mercado</th></tr>"
    )
    corpo = "".join(_linha_valuation_html(l, prefs) for l in linhas_validas)
    st.markdown(f"<table class='radar-tabela'>{cabecalho}{corpo}</table>", unsafe_allow_html=True)
    st.caption(
        "Preços consultados ~agora (cache de 90s) · múltiplos via yfinance, cache de 12h "
        "(\"desatualizado\" = última coleta válida tem mais de 24h) · sem P/L/P-VP válido pra "
        "empresa com prejuízo, bancos, seguradoras (lucro negativo ou modelo contábil diferente)."
    )
    cols = st.columns(min(len(linhas_validas), 6) or 1)
    for i, l in enumerate(linhas_validas):
        with cols[i % len(cols)]:
            if st.button(f"Comparar {l['ticker']} com o setor ↗", key=f"radar_comp_{l['ticker']}", width="stretch"):
                _dialog_comparaveis(l["ticker"], prefs)


# ============================================================
# C. CATALISADORES
# ============================================================

_COR_STATUS = {STATUS_CONFIRMADO: "var(--alta)", STATUS_ESTIMADO: "var(--destaque)", STATUS_PRAZO_CVM: "var(--cinza)"}


def _linha_catalisador(c: dict):
    cor = _COR_STATUS.get(c["status"], "var(--cinza)")
    fonte_html = ""
    if c.get("fonte_url"):
        fonte_html = f" · <a href='{html.escape(c['fonte_url'])}' target='_blank' style='color:var(--cinza);'>{html.escape(c['fonte_label'] or 'fonte')}</a>"
    elif c.get("fonte_label"):
        fonte_html = f" · {html.escape(c['fonte_label'])}"
    st.markdown(
        f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
        f"<span><span class='radar-ticker'>{c['ticker']}</span> <span class='radar-categoria'>{html.escape(c['categoria'])}</span></span>"
        f"<span style='color:{cor}; font-size:0.68rem;'>● {html.escape(c['status_label'])}</span>"
        f"</div><div class='radar-meta'>{c['data'].strftime('%d/%m/%Y')}{fonte_html}</div></div>",
        unsafe_allow_html=True,
    )


def _secao_catalisadores(tickers: list):
    eventos = radar.catalisadores(tuple(tickers))
    hoje = date.today()
    futuros = [e for e in eventos if e["data"] >= hoje]
    if not futuros:
        st.markdown("<div class='radar-vazio'>Nenhum catalisador (resultado/proventos) nos próximos 60 dias pros ativos selecionados.</div>", unsafe_allow_html=True)
        return
    for e in futuros[:10]:
        _linha_catalisador(e)
    if len(futuros) > 10:
        st.caption(f"+{len(futuros) - 10} catalisador(es) adicional(is) - veja a aba CALENDÁRIO pra lista completa.")


# ============================================================
# D. RISCO DA CARTEIRA - stub honesto (sem cadastro de posições hoje)
# ============================================================

def _secao_risco(prefs: dict):
    info = radar.risco_carteira(prefs)
    st.markdown(
        f"<div class='radar-stub'>{html.escape(info['motivo'])}<br><br>{html.escape(info['o_que_falta'])}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Sua watchlist tem {info['watchlist_tamanho']} ativo(s) - isso é uma lista de acompanhamento, "
        "não uma carteira (sem quantidade/preço médio cadastrado, não dá pra calcular concentração, "
        "exposição ou cenário de estresse de verdade)."
    )


# ============================================================
# E. RESEARCH COM EVIDÊNCIAS
# ============================================================

def _linha_evidencia(item: dict, watchlist: list):
    tipo = item["_tipo_item"]
    payload = item["_payload"]
    if tipo == "noticia":
        data_txt = payload["data"][:10]
        titulo = payload["titulo"]
        ticker_txt = ", ".join(payload.get("tickers") or [])
        chave = f"radar_ev_news_{abs(hash(payload['link']))}"
    else:
        data_txt = payload["data"][:10]
        titulo = payload["assunto"]
        ticker_txt = payload["ticker"]
        chave = f"radar_ev_cvm_{abs(hash(payload['link']))}"

    col_txt, col_btn = st.columns([5, 1], vertical_alignment="center")
    with col_txt:
        st.markdown(
            f"<div class='radar-meta'>[{data_txt}] {html.escape(ticker_txt)}</div>"
            f"<div class='radar-descricao'>{html.escape(titulo)}</div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("Abrir ↗", key=chave, width="stretch"):
            if tipo == "noticia":
                abrir_card_noticia(payload, watchlist)
            else:
                abrir_card_documento(payload)


def _secao_evidencias(tickers: list, watchlist: list):
    itens = radar.evidencias_recentes(tuple(tickers))
    if not itens:
        st.markdown("<div class='radar-vazio'>Nenhuma notícia ou documento recente pros ativos selecionados.</div>", unsafe_allow_html=True)
        return
    for item in itens:
        _linha_evidencia(item, watchlist)


# ============================================================
# F. COPILOTO DE RESEARCH
# ============================================================

def _secao_copiloto(tickers: list):
    if not tickers:
        return
    ticker_copiloto = st.selectbox("Ativo", tickers, key="radar_copiloto_ticker", label_visibility="collapsed")
    cols = st.columns(2)
    for i, pergunta in enumerate(radar.PERGUNTAS_SUGERIDAS):
        with cols[i % 2]:
            if st.button(pergunta, key=f"radar_pergunta_{i}", width="stretch"):
                st.session_state["radar_copiloto_resposta"] = radar.responder_copiloto(pergunta, ticker_copiloto)
                st.session_state["radar_copiloto_pergunta"] = pergunta

    resposta = st.session_state.get("radar_copiloto_resposta")
    pergunta_atual = st.session_state.get("radar_copiloto_pergunta")
    if resposta and st.session_state.get("radar_copiloto_ticker_resp") != ticker_copiloto:
        # ticker mudou desde a ultima pergunta respondida - resposta antiga
        # nao vale mais pro ativo atual, limpa pra nao mostrar dado trocado
        resposta = None
    if ticker_copiloto:
        st.session_state["radar_copiloto_ticker_resp"] = ticker_copiloto
    if resposta:
        st.markdown(
            f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
            f"<span class='radar-categoria'>{html.escape(pergunta_atual or '')}</span>"
            f"{_selo_evidencia(resposta['tipo'])}</div>"
            f"<div class='radar-descricao'>{html.escape(resposta['resposta'])}</div></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Resposta construída só a partir dos dados já agregados nas seções acima "
            "(sem chamada de IA nova) - datas/fontes reais quando houver, ou declara que "
            "não há evidência suficiente."
        )


# ============================================================
# Entrada da aba
# ============================================================

@st.fragment
def render_radar(prefs: dict):
    """Ponto de entrada da aba RADAR, chamado pelo app.py."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">RADAR</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='radar-subtitulo'>O que mudou · onde vale investigar · o que pode dar errado</div>",
        unsafe_allow_html=True,
    )

    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na watchlist (barra lateral) para o RADAR ter o que analisar.")
        return

    col_janela, col_escopo = st.columns(2)
    with col_janela:
        janela = st.pills(
            "Janela", list(radar.JANELAS_DIAS.keys()), default="7 DIAS",
            key="radar_janela", label_visibility="collapsed",
        ) or "7 DIAS"
    with col_escopo:
        opcoes_escopo = ["WATCHLIST"] + watchlist
        escopo = st.pills("Escopo", opcoes_escopo, default="WATCHLIST", key="radar_escopo", label_visibility="collapsed")
    tickers_escopo = watchlist if escopo in (None, "WATCHLIST") else [escopo]

    _secao_mudancas_tese(tickers_escopo, janela, prefs)

    with st.expander("ONDE VALE INVESTIGAR — Valuation Radar", expanded=False):
        _secao_valuation(tickers_escopo, prefs)
    with st.expander("ONDE VALE INVESTIGAR — Próximos catalisadores", expanded=False):
        _secao_catalisadores(tickers_escopo)
    with st.expander("O QUE PODE DAR ERRADO — Risco da carteira", expanded=False):
        _secao_risco(prefs)
    with st.expander("RESEARCH COM EVIDÊNCIAS", expanded=False):
        _secao_evidencias(tickers_escopo, watchlist)
    with st.expander("COPILOTO DE RESEARCH", expanded=False):
        _secao_copiloto(tickers_escopo)
