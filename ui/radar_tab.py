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
import urllib.parse
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

/* ---- RADAR DE QUEDAS (revisao 2026-10-18) ---------------------------- */
.rq-regra { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.9rem 0; line-height: 1.5; }
.rq-regra b { color: var(--neutro); font-weight: 600; }
.rq-bloco {
    font-size: 0.7rem; color: var(--cinza); letter-spacing: 0.06em; font-weight: 600;
    display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; flex-wrap: wrap;
    border-bottom: 1px solid var(--borda); padding-bottom: 0.25rem; margin: 1.1rem 0 0.35rem 0;
}
.rq-bloco span.rq-bloco-meta { font-weight: 400; letter-spacing: 0; }
.rq-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.rq-tabela {
    width: 100%; border-collapse: collapse; font-family: 'IBM Plex Mono', monospace;
    font-size: 0.76rem; font-variant-numeric: tabular-nums;
}
.rq-tabela th {
    color: var(--cinza); font-size: 0.62rem; font-weight: 500; letter-spacing: 0.05em;
    text-align: right; padding: 0.3rem 0.55rem; border-bottom: 1px solid var(--borda); white-space: nowrap;
}
.rq-tabela td {
    text-align: right; padding: 0.32rem 0.55rem; border-bottom: 1px solid var(--borda);
    white-space: nowrap; vertical-align: baseline;
}
.rq-tabela th, .rq-tabela td { border-left: none !important; border-right: none !important; border-top: none !important; }
.rq-tabela .rq-esq { text-align: left; }
.rq-tabela .rq-sub { margin-left: 0.45rem; }
.rq-tabela tr.rq-linha-alerta td { background: color-mix(in srgb, var(--baixa) 9%, transparent); }
.rq-ticker { color: var(--destaque); font-weight: 700; }
/* achado P1 da auditoria 360 (docs/auditoria-redesign-360.md secao 4):
   .rq-ticker ja tinha o tratamento visual de "isto e' clicavel", mas
   era so' <span> sem destino - agora e' <a href="?ticker=X"> (link
   direto, lido em app.py via ui.navegacao.ticker_da_url). Especificidade
   maior que ".rq-tabela a" (regra generica dos links de FONTE abaixo)
   pra manter a cor/peso de destaque em vez de virar cinza. */
.rq-tabela a.rq-ticker { color: var(--destaque); font-weight: 700; text-decoration: none; }
.rq-tabela a.rq-ticker:hover { text-decoration: underline; }
.rq-sub { color: var(--cinza); font-size: 0.66rem; }
.rq-baixa { color: var(--baixa); }
.rq-alta { color: var(--alta); }
.rq-cinza { color: var(--cinza); }
.rq-estado {
    display: inline-block; font-size: 0.6rem; letter-spacing: 0.05em; padding: 0.05rem 0.35rem;
    border: 1px solid var(--borda); color: var(--cinza);
}
.rq-estado-ALERTA, .rq-estado-FALHOU, .rq-estado-INDISPONIVEL { color: var(--baixa); border-color: var(--baixa); }
.rq-estado-ATENCAO, .rq-estado-PENDENTE, .rq-estado-DESATUALIZADA { color: var(--destaque); border-color: var(--destaque); }
.rq-estado-ATUALIZADA, .rq-estado-ENVIADO { color: var(--alta); border-color: var(--alta); }
.rq-tabela a { color: var(--cinza); text-decoration: none; }
.rq-tabela a:hover { color: var(--destaque); }
.rq-nota { color: var(--cinza); font-size: 0.66rem; margin-top: 0.35rem; line-height: 1.5; }
.rq-vazio { color: var(--cinza); font-size: 0.76rem; padding: 0.5rem 0; }
.radar-separador {
    font-size: 0.78rem; color: var(--destaque); letter-spacing: 0.04em; font-weight: 600;
    border-top: 1px solid var(--borda); padding-top: 0.8rem; margin-top: 1.6rem; margin-bottom: 0.9rem;
}
/* Celular: some com as colunas secundarias (cada tabela continua com
   ticker, variacao e estado) em vez de forcar rolagem lateral. */
@media (max-width: 640px) {
    .rq-tabela .rq-sec { display: none; }
    .rq-tabela th, .rq-tabela td { padding: 0.3rem 0.35rem; }
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
        st.caption(f"+{len(futuros) - 10} catalisador(es) adicional(is) - veja MERCADO › Agenda pra lista completa.")


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
# G. RADAR DE QUEDAS - carteiras recomendadas (revisao 2026-10-18)
# ============================================================

_ROTULO_ESTADO = {"ALERTA": "ALERTA", "ATENCAO": "ATENÇÃO", "NORMAL": "NORMAL", "SEM_COTACAO": "SEM COTAÇÃO"}
_ROTULO_EMAIL = {"ENVIADO": ("ENVIADO", "ENVIADO"), "PENDENTE_ENVIO": ("PENDENTE", "PENDENTE"),
                 "FALHA_ENVIO": ("FALHOU", "FALHOU")}
_PERIODOS_ALERTAS = {"HOJE": 1, "7 DIAS": 7, "30 DIAS": 30, "90 DIAS": 90}


def _chip(classe: str, rotulo: str) -> str:
    return f"<span class='rq-estado rq-estado-{classe}'>{html.escape(rotulo)}</span>"


def _pct(valor, prefs, sinal=True) -> str:
    if valor is None:
        return "—"
    txt = config.formatar_numero(valor, 2, prefs["formato_numerico"])
    return f"{'+' if sinal and valor > 0 else ''}{txt}%"


def _classe_var(valor) -> str:
    if valor is None:
        return "rq-cinza"
    return "rq-baixa" if valor < 0 else ("rq-alta" if valor > 0 else "")


def _data_br(valor) -> str:
    """'2026-10-16' / ISO com hora -> '16/10' (ano so' quando nao e' o atual)."""
    if not valor:
        return "—"
    texto = str(valor)[:10]
    try:
        d = date.fromisoformat(texto)
    except ValueError:
        return html.escape(texto)
    return d.strftime("%d/%m") if d.year == date.today().year else d.strftime("%d/%m/%Y")


def _hora_sp(valor_iso) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        quando = datetime.fromisoformat(str(valor_iso).replace("Z", "+00:00"))
        return quando.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return "—"


def _tabela_cobertura_html(resumo_fontes, casas_monitoradas) -> str:
    linhas = []
    for casa in casas_monitoradas:
        info = (resumo_fontes or {}).get(casa)
        if info is None:
            estado = _chip("INDISPONIVEL", "INDISPONÍVEL")
            carteiras, ativos, confirmacao, referencia = "—", "—", "—", "—"
        else:
            estado = (_chip("DESATUALIZADA", "DESATUALIZADA") if info["desatualizada"]
                      else _chip("ATUALIZADA", "ATUALIZADA"))
            carteiras = html.escape(", ".join(info.get("carteiras") or []) or "—")
            ativos = str(info["ativos"])
            confirmacao = _hora_sp(info.get("verificado_em")) if info.get("verificado_em") else "—"
            referencia = _data_br(info.get("data_publicacao"))
        linhas.append(
            f"<tr><td class='rq-esq'>{html.escape(casa)}</td>"
            f"<td class='rq-esq rq-sec'>{carteiras}</td><td>{ativos}</td>"
            f"<td class='rq-sec'>{referencia}</td><td class='rq-sec'>{confirmacao}</td><td>{estado}</td></tr>"
        )
    return (
        "<div class='rq-scroll'><table class='rq-tabela'><thead><tr>"
        "<th class='rq-esq'>CASA</th><th class='rq-esq rq-sec'>CARTEIRA</th><th>ATIVOS</th>"
        "<th class='rq-sec'>REFERÊNCIA</th><th class='rq-sec'>ÚLT. CONFIRMAÇÃO</th><th>FONTE</th>"
        f"</tr></thead><tbody>{''.join(linhas)}</tbody></table></div>"
    )


def _tabela_monitorados_html(linhas, prefs) -> str:
    corpo = []
    for l in linhas:
        classe_linha = " class='rq-linha-alerta'" if l["estado"] == "ALERTA" else ""
        dist = "—" if l["distancia_gatilho_pp"] is None else (
            "atingido" if l["estado"] == "ALERTA"
            else f"{config.formatar_numero(l['distancia_gatilho_pp'], 2, prefs['formato_numerico'])} p.p."
        )
        origem = html.escape(" · ".join(l["casas"]))
        link_ticker = urllib.parse.quote(l["ticker"])
        corpo.append(
            f"<tr{classe_linha}><td class='rq-esq'><a class='rq-ticker' href='?ticker={link_ticker}'>{html.escape(l['ticker'])}</a>"
            f"<span class='rq-sub rq-sec'>{html.escape(l['empresa'] or '')}</span></td>"
            f"<td class='rq-esq rq-sec rq-cinza'>{origem}</td>"
            f"<td class='rq-sec'>{_fmt_num(l['fechamento_anterior'], 2, prefs)}</td>"
            f"<td>{_fmt_num(l['preco'], 2, prefs)}</td>"
            f"<td class='{_classe_var(l['variacao_pct'])}'>{_pct(l['variacao_pct'], prefs)}</td>"
            f"<td class='rq-sec rq-cinza'>{dist}</td>"
            f"<td>{_chip(l['estado'], _ROTULO_ESTADO[l['estado']])}</td></tr>"
        )
    return (
        "<div class='rq-scroll'><table class='rq-tabela'><thead><tr>"
        "<th class='rq-esq'>ATIVO</th><th class='rq-esq rq-sec'>CASA</th><th class='rq-sec'>FECH. ANT.</th>"
        "<th>ÚLTIMO</th><th>VAR. DIA</th><th class='rq-sec'>ATÉ O GATILHO</th><th>ESTADO</th>"
        f"</tr></thead><tbody>{''.join(corpo)}</tbody></table></div>"
    )


def _tabela_alertas_html(alertas, prefs) -> str:
    corpo = []
    for a in alertas:
        variacao = float(a.get("variacao_pct") or 0)
        rotulo_email, classe_email = _ROTULO_EMAIL.get(a.get("status") or "", (a.get("status") or "—", ""))
        origem = " · ".join(
            f"{c}" for c in (a.get("casas") or [])
        ) + (f" — {', '.join(a.get('carteiras') or [])}" if a.get("carteiras") else "")
        fontes = " ".join(
            f"<a href='{html.escape(u, quote=True)}' target='_blank' rel='noopener'>↗</a>"
            for u in (a.get("fontes") or []) if str(u).startswith("https://")
        ) or "—"
        link_ticker = urllib.parse.quote(a.get("ticker", ""))
        corpo.append(
            f"<tr><td class='rq-esq'>{_data_br(a.get('pregao'))}</td>"
            f"<td class='rq-esq'><a class='rq-ticker' href='?ticker={link_ticker}'>{html.escape(a.get('ticker', ''))}</a>"
            f"<span class='rq-sub rq-sec'>{html.escape(a.get('empresa') or '')}</span></td>"
            f"<td class='rq-baixa'>{_pct(variacao, prefs)}</td>"
            f"<td class='rq-sec'>{_fmt_num(a.get('fechamento_anterior'), 2, prefs)}</td>"
            f"<td class='rq-sec'>{_fmt_num(a.get('preco_atual'), 2, prefs)}</td>"
            f"<td class='rq-esq rq-sec rq-cinza'>{html.escape(origem)}</td>"
            f"<td class='rq-sec rq-cinza'>{_hora_sp(a.get('alertado_em'))}</td>"
            f"<td>{_chip(classe_email, rotulo_email)}</td>"
            f"<td class='rq-sec'>{fontes}</td></tr>"
        )
    return (
        "<div class='rq-scroll'><table class='rq-tabela'><thead><tr>"
        "<th class='rq-esq'>PREGÃO</th><th class='rq-esq'>ATIVO</th><th>VAR. DIA</th>"
        "<th class='rq-sec'>FECH. ANT.</th><th class='rq-sec'>PREÇO NO ALERTA</th>"
        "<th class='rq-esq rq-sec'>RECOMENDADO POR</th><th class='rq-sec'>DETECTADO</th>"
        "<th>E-MAIL</th><th class='rq-sec'>FONTE</th>"
        f"</tr></thead><tbody>{''.join(corpo)}</tbody></table></div>"
    )


def _bloco_regra_quedas():
    st.markdown('<div class="radar-pergunta">RADAR DE QUEDAS — CARTEIRAS RECOMENDADAS</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='rq-regra'>Alerta quando um ativo de carteira recomendada cai <b>mais de 4,00% no dia</b> "
        "(preço atual vs. fechamento do pregão anterior; −4,00% exato não alerta). Um alerta por ativo e pregão, "
        "mesmo que esteja em várias carteiras. Cotação Yahoo Finance, com atraso.</div>",
        unsafe_allow_html=True,
    )


def _bloco_cobertura(prefs: dict) -> bool:
    """Estado de cada casa monitorada; False = banco indisponivel (quem
    chama para ai, os outros blocos tambem dependem do banco)."""
    from data import radar_quedas as rq

    # --- 1. cobertura -----------------------------------------------------
    resumo_fontes = rq.resumo_fontes_vigentes()
    if resumo_fontes is None:
        st.markdown(
            "<div class='rq-vazio'>Banco indisponível: não foi possível ler as carteiras vigentes "
            "(confira a conexão e a migration sql/radar_research.sql).</div>",
            unsafe_allow_html=True,
        )
        return False
    casas = list(rq.CASAS_MONITORADAS) + sorted(c for c in resumo_fontes if c not in rq.CASAS_MONITORADAS)
    ativas = sum(1 for c in casas if c in resumo_fontes)
    st.markdown(
        f"<div class='rq-bloco'><span>COBERTURA</span>"
        f"<span class='rq-bloco-meta'>{ativas} de {len(casas)} casas com carteira vigente</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(_tabela_cobertura_html(resumo_fontes, casas), unsafe_allow_html=True)
    st.markdown(
        "<div class='rq-nota'>ATUALIZADA = fonte confirmou a carteira nas últimas "
        f"{rq.IDADE_FRESCA_HORAS}h · DESATUALIZADA = carteira ainda vigente, mas sem confirmação recente · "
        f"INDISPONÍVEL = sem carteira vigente (fonte bloqueada, nunca coletada ou expirada após "
        f"{rq.IDADE_MAXIMA_CARTEIRA_DIAS} dias). XP, BTG e outras casas não entram: não há carteira "
        "recomendada pública acessível.</div>",
        unsafe_allow_html=True,
    )

    return True


def _bloco_monitorados(prefs: dict):
    from data import radar_quedas as rq

    # --- 2. ativos monitorados agora -------------------------------------
    monitorados = rq.painel_monitorados()
    if monitorados:
        n_alerta = sum(1 for l in monitorados if l["estado"] == "ALERTA")
        n_atencao = sum(1 for l in monitorados if l["estado"] == "ATENCAO")
        destaque = []
        if n_alerta:
            destaque.append(f"<span class='rq-baixa'>{n_alerta} abaixo do gatilho</span>")
        if n_atencao:
            destaque.append(f"<span style='color:var(--destaque)'>{n_atencao} em atenção</span>")
        meta = " · ".join(destaque + [f"{len(monitorados)} ativos"])
        st.markdown(
            f"<div class='rq-bloco'><span>MONITORADOS AGORA</span><span class='rq-bloco-meta'>{meta}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(_tabela_monitorados_html(monitorados, prefs), unsafe_allow_html=True)
        st.markdown(
            f"<div class='rq-nota'>Ordenado pela maior queda do dia. ATENÇÃO = queda de "
            f"{config.formatar_numero(abs(rq.LIMIAR_ATENCAO), 1, prefs['formato_numerico'])}% ou mais, ainda sem "
            "alerta (não envia e-mail). Cotação consultada agora (cache de até 1 min); o alerta é registrado "
            "pelo monitor agendado, não por esta tela.</div>",
            unsafe_allow_html=True,
        )
    elif monitorados == []:
        st.markdown("<div class='rq-vazio'>Nenhuma carteira vigente: nada sendo monitorado agora.</div>",
                    unsafe_allow_html=True)


def _bloco_alertas(prefs: dict):
    from data import radar_quedas as rq

    # --- 3. alertas registrados ------------------------------------------
    st.markdown("<div class='rq-bloco'><span>ALERTAS REGISTRADOS</span></div>", unsafe_allow_html=True)
    col_p, col_c, col_t = st.columns([2.2, 1.2, 1], vertical_alignment="bottom")
    with col_p:
        periodo = st.pills("Período", list(_PERIODOS_ALERTAS), default="7 DIAS",
                           key="rq_periodo", label_visibility="collapsed") or "7 DIAS"
    alertas = rq.alertas_periodo(_PERIODOS_ALERTAS[periodo])
    if alertas is None:
        st.markdown("<div class='rq-vazio'>Histórico indisponível (banco fora do ar).</div>", unsafe_allow_html=True)
        return
    with col_c:
        casas_opcoes = sorted({c for a in alertas for c in (a.get("casas") or [])})
        filtro_casa = st.selectbox("Casa", ["TODAS AS CASAS"] + casas_opcoes, key="rq_casa",
                                   label_visibility="collapsed")
    with col_t:
        filtro_ticker = st.text_input("Ticker", key="rq_ticker", placeholder="TICKER",
                                      label_visibility="collapsed").strip().upper()
    filtrados = [a for a in alertas
                 if (not filtro_ticker or filtro_ticker in str(a.get("ticker", "")).upper())
                 and (filtro_casa == "TODAS AS CASAS" or filtro_casa in (a.get("casas") or []))]
    if filtrados:
        st.markdown(_tabela_alertas_html(filtrados, prefs), unsafe_allow_html=True)
        st.markdown(
            "<div class='rq-nota'>PREÇO NO ALERTA = cotação no momento em que o monitor detectou a queda "
            "(não é o fechamento do dia). E-MAIL: ENVIADO, PENDENTE (será reenviado) ou FALHOU.</div>",
            unsafe_allow_html=True,
        )
    elif alertas:
        st.markdown("<div class='rq-vazio'>Nenhum alerta corresponde aos filtros.</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='rq-vazio'>Nenhuma queda acima de 4% em ativo monitorado no período "
            f"({periodo.lower()}). Ausência de alerta não é falha do monitor: veja o estado das fontes acima.</div>",
            unsafe_allow_html=True,
        )


def _secao_radar_quedas(prefs: dict):
    _bloco_regra_quedas()
    if not _bloco_cobertura(prefs):
        return
    _bloco_monitorados(prefs)
    _bloco_alertas(prefs)


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

    # Radar de quedas em carteiras recomendadas e independente da watchlist.
    _secao_radar_quedas(prefs)

    st.markdown('<div class="radar-separador">INTELIGÊNCIA DA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na watchlist (barra lateral) para o restante do RADAR analisar os ativos.")
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


# ============================================================
# Subabas do PREGAO 2.0 (ui/navegacao.py) - mesmas secoes de render_radar
# acima, so' redistribuidas: RADAR > Alertas/Carteiras/Oportunidades/
# Acompanhamento e ANALISES > Valuation/Teses. render_radar continua
# existindo (composicao completa, usada pelos testes de UI).
# ============================================================

_AVISO_SINAL = (
    "<div class='rq-nota'>Sinais para investigar, não recomendações: uma queda expressiva ou um múltiplo "
    "descontado não constitui, por si só, motivo de compra. Confirme fundamentos, notícias e riscos "
    "antes de qualquer decisão.</div>"
)


def _escopo_watchlist(prefs: dict, com_janela: bool = True):
    """Pills de janela/escopo compartilhados pelas subabas que analisam a
    watchlist - mesmas keys de render_radar, entao o filtro escolhido
    numa subaba vale nas outras. None = watchlist vazia (aviso ja dado)."""
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na watchlist (barra lateral ou busca global) para analisar os ativos.")
        return None
    janela = "7 DIAS"
    if com_janela:
        col_janela, col_escopo = st.columns(2)
        with col_janela:
            janela = st.pills(
                "Janela", list(radar.JANELAS_DIAS.keys()), default="7 DIAS",
                key="radar_janela", label_visibility="collapsed",
            ) or "7 DIAS"
    else:
        col_escopo = st.container()
    with col_escopo:
        escopo = st.pills("Escopo", ["WATCHLIST"] + watchlist, default="WATCHLIST",
                          key="radar_escopo", label_visibility="collapsed")
    tickers = watchlist if escopo in (None, "WATCHLIST") else [escopo]
    return tickers, janela, watchlist


@st.fragment
def render_radar_alertas(prefs: dict):
    _injetar_css()
    _bloco_regra_quedas()
    if not _bloco_cobertura_compacta():
        return
    _bloco_alertas(prefs)
    _bloco_monitorados(prefs)
    st.markdown(_AVISO_SINAL, unsafe_allow_html=True)


def _bloco_cobertura_compacta() -> bool:
    """Alertas dependem do banco: sem ele, mesma mensagem da cobertura
    completa (que vive em Carteiras Recomendadas)."""
    from data import radar_quedas as rq

    if rq.resumo_fontes_vigentes() is None:
        st.markdown(
            "<div class='rq-vazio'>Banco indisponível: não foi possível ler as carteiras vigentes "
            "(confira a conexão e a migration sql/radar_research.sql).</div>",
            unsafe_allow_html=True,
        )
        return False
    return True


@st.fragment
def render_radar_carteiras(prefs: dict):
    """Cobertura das carteiras recomendadas monitoradas. O feed de research
    (casas, recomendacoes, relatorios) vem logo abaixo, em app.py, pelo
    render_research ja existente - nao e' reimplementado aqui."""
    _injetar_css()
    st.markdown('<div class="radar-pergunta">CARTEIRAS RECOMENDADAS — FONTES MONITORADAS</div>',
                unsafe_allow_html=True)
    _bloco_cobertura(prefs)


@st.fragment
def render_radar_oportunidades(prefs: dict):
    _injetar_css()
    st.markdown('<div class="radar-pergunta">ONDE VALE INVESTIGAR</div>', unsafe_allow_html=True)
    st.markdown(_AVISO_SINAL, unsafe_allow_html=True)
    escopo = _escopo_watchlist(prefs)
    if escopo is None:
        return
    tickers, janela, watchlist = escopo
    _secao_mudancas_tese(tickers, janela, prefs)
    with st.expander("Próximos catalisadores", expanded=True):
        _secao_catalisadores(tickers)
    with st.expander("Research com evidências", expanded=False):
        _secao_evidencias(tickers, watchlist)


@st.fragment
def render_radar_acompanhamento(prefs: dict):
    """Historico de alertas dos ativos DA WATCHLIST + risco da carteira.
    Itens salvos/anotacoes pessoais nao existem no banco hoje (exigiria
    tabela nova - migration fora do escopo desta reorganizacao)."""
    from data import radar_quedas as rq

    _injetar_css()
    st.markdown('<div class="radar-pergunta">ACOMPANHAMENTO DA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    alertas = rq.alertas_periodo(90)
    st.markdown("<div class='rq-bloco'><span>ALERTAS ANTERIORES — ATIVOS DA WATCHLIST (90 DIAS)</span></div>",
                unsafe_allow_html=True)
    if alertas is None:
        st.markdown("<div class='rq-vazio'>Histórico indisponível (banco fora do ar).</div>", unsafe_allow_html=True)
    else:
        da_watchlist = [a for a in alertas if str(a.get("ticker", "")).upper() in set(watchlist)]
        if da_watchlist:
            st.markdown(_tabela_alertas_html(da_watchlist, prefs), unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='rq-vazio'>Nenhum alerta de queda registrado para ativos da sua watchlist nos "
                "últimos 90 dias (o monitor só cobre ativos de carteiras recomendadas).</div>",
                unsafe_allow_html=True,
            )
    with st.expander("O QUE PODE DAR ERRADO — Risco da carteira", expanded=True):
        _secao_risco(prefs)
    st.markdown(
        "<div class='rq-nota'>Itens salvos e anotações pessoais ainda não existem: exigem uma tabela nova no "
        "banco (desenvolvimento posterior, ver docs/arquitetura-pregao-2.md).</div>",
        unsafe_allow_html=True,
    )


@st.fragment
def render_valuation(prefs: dict):
    _injetar_css()
    st.markdown('<div class="painel-titulo">VALUATION</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='rq-nota'>Múltiplos reportados pela fonte (Yahoo Finance) comparados com pares do setor. "
        "Não é preço-alvo nem modelo de fluxo de caixa descontado: cenários, premissas e sensibilidade "
        "ainda não têm modelo próprio no PREGÃO (desenvolvimento posterior).</div>",
        unsafe_allow_html=True,
    )
    escopo = _escopo_watchlist(prefs, com_janela=False)
    if escopo is None:
        return
    _secao_valuation(escopo[0], prefs)


@st.fragment
def render_teses(prefs: dict):
    _injetar_css()
    st.markdown('<div class="painel-titulo">TESES</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='rq-nota'>Base de evidências e copiloto de research já existentes. O registro persistente "
        "de teses próprias (premissas, riscos, histórico de alterações) ainda não existe — exige tabela nova "
        "no banco (desenvolvimento posterior, ver docs/arquitetura-pregao-2.md).</div>",
        unsafe_allow_html=True,
    )
    escopo = _escopo_watchlist(prefs, com_janela=False)
    if escopo is None:
        return
    tickers, _janela, watchlist = escopo
    with st.expander("RESEARCH COM EVIDÊNCIAS", expanded=True):
        _secao_evidencias(tickers, watchlist)
    with st.expander("COPILOTO DE RESEARCH", expanded=False):
        _secao_copiloto(tickers)
