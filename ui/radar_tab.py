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
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data import posicoes as posicoes_mod
from data import radar
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM
from data.prices import validar_ticker
from data.research import tese
from data.research.historico import ultimo_snapshot
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
.radar-selo-estimativa { color: var(--ciano); border-color: var(--ciano); }
.radar-selo-hipotese { color: var(--destaque); border-color: var(--destaque); border-style: dashed; }
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

/* ---- ACOMPANHAMENTO DA WATCHLIST (redesign visual 2026-10-23) --------
   Escopado só às classes abaixo (nenhuma regra compartilhada do RADAR DE
   QUEDAS/cobertura foi alterada) - MINHAS POSIÇÕES precisava do mesmo
   alinhamento rígido ticker/quantidade/preço/variação que as tabelas já
   usam, mas como lista (sem <table>, cada linha tem o botão "remover"
   nativo do Streamlit ao lado - mesmo padrão de app.py:_fragmento_watchlist,
   só que a´ ainda era frase corrida em vez de colunas alinhadas). */
.acomp-posicao {
    display: flex; justify-content: space-between; align-items: baseline; gap: 0.6rem;
    padding: 0.3rem 0; border-bottom: 1px solid var(--borda);
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; flex-wrap: wrap;
}
.acomp-posicao-ativo { color: var(--destaque); font-weight: 700; margin-right: 0.6rem; }
.acomp-posicao-detalhe { color: var(--cinza); font-size: 0.72rem; }
.acomp-posicao-lucro { font-variant-numeric: tabular-nums; white-space: nowrap; }
@media (max-width: 640px) {
    .acomp-posicao { font-size: 0.74rem; }
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
        radar.TIPO_ESTIMATIVA_TERCEIRO: "radar-selo-estimativa",
        radar.TIPO_HIPOTESE: "radar-selo-hipotese",
    }.get(tipo, "radar-selo-insuficiente")
    rotulo = {
        radar.TIPO_FATO: "FATO",
        radar.TIPO_CALCULO: "CÁLCULO INTERNO",
        radar.TIPO_INSUFICIENTE: "DADO INSUFICIENTE",
        radar.TIPO_ESTIMATIVA_TERCEIRO: "ESTIMATIVA DE TERCEIRO",
        radar.TIPO_HIPOTESE: "HIPÓTESE DO ANALISTA",
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
# D. RISCO DA CARTEIRA - cadastro de posições (quantidade + preço médio,
# ver data/posicoes.py) + cálculo real de risco quando há posição (ver
# data/radar.py:risco_carteira); aviso honesto, sem calcular nada, pra
# quem não cadastrou nenhuma posição ainda - watchlist nunca é usada
# como proxy de carteira.
# ============================================================

def _formulario_posicao(sub: str):
    """Cadastro/edição de 1 posição - cadastrar de novo o mesmo ticker
    ATUALIZA quantidade/preço médio (upsert, ver
    data/posicoes.py:salvar_posicao), nunca duplica linha. Widgets soltos
    (sem st.form) de propósito - mesmo padrão do cadastro de watchlist em
    app.py:_adicionar_ticker (contador na key força campos vazios após
    salvar, ver st.session_state.contador_form_posicao abaixo)."""
    sufixo = st.session_state.get("contador_form_posicao", 0)
    col_ticker, col_qtd, col_preco, col_data = st.columns([2, 1, 1, 1.3])
    ticker = col_ticker.text_input(
        "Ticker", key=f"posicao_ticker_{sufixo}", placeholder="TICKER (EX: PETR4)", label_visibility="collapsed",
    ).strip().upper()
    quantidade = col_qtd.number_input(
        "Quantidade", key=f"posicao_qtd_{sufixo}", min_value=0.0, step=1.0, format="%.0f", label_visibility="collapsed",
    )
    preco_medio = col_preco.number_input(
        "Preço médio (R$)", key=f"posicao_preco_{sufixo}", min_value=0.0, step=0.01, format="%.2f", label_visibility="collapsed",
    )
    data_ref = col_data.date_input(
        "Data de referência", key=f"posicao_data_{sufixo}", value=date.today(), label_visibility="collapsed",
    )

    if not st.button("CADASTRAR / ATUALIZAR POSIÇÃO", key=f"posicao_salvar_{sufixo}", width="stretch"):
        return
    if not ticker:
        st.warning("Informe o ticker.")
    elif not posicoes_mod.posicao_valida(quantidade, preco_medio):
        st.warning("Quantidade e preço médio precisam ser maiores que zero.")
    elif not validar_ticker(ticker):
        st.error(f"Ticker '{ticker}' não encontrado no yfinance.")
    elif posicoes_mod.salvar_posicao(sub, ticker, quantidade, preco_medio, data_ref):
        st.success(f"Posição em {ticker} salva.")
        st.session_state.contador_form_posicao = sufixo + 1  # forca campos vazios no rerun
        st.rerun()
    else:
        st.error("Não foi possível salvar agora (banco indisponível) - tente de novo em alguns instantes.")


def _linha_posicao_gerenciar(sub: str, posicao: dict, valores_atuais: dict, prefs: dict):
    """1 linha de posição cadastrada com botão de remover - mesmo padrão
    de app.py:_fragmento_watchlist (coluna de info + coluna de remover)."""
    ticker = posicao["ticker"]
    extra = valores_atuais.get(ticker) or {}
    lucro = extra.get("lucro_pct")
    if lucro is None:
        lucro_txt = "<span class='acomp-posicao-detalhe'>variação indisponível</span>"
    else:
        sinal = "+" if lucro >= 0 else ""
        lucro_txt = (
            f"<span class='acomp-posicao-lucro {_classe_var(lucro)}'>"
            f"{sinal}{config.formatar_numero(lucro, 2, prefs['formato_numerico'])}%</span>"
        )

    col_info, col_remover = st.columns([5, 1])
    col_info.markdown(
        f"<div class='acomp-posicao'>"
        f"<span><span class='acomp-posicao-ativo'>{html.escape(ticker)}</span>"
        f"<span class='acomp-posicao-detalhe'>"
        f"{config.formatar_numero(posicao['quantidade'], 0, prefs['formato_numerico'])} cotas × "
        f"R$ {config.formatar_numero(float(posicao['preco_medio']), 2, prefs['formato_numerico'])}</span></span>"
        f"{lucro_txt}</div>",
        unsafe_allow_html=True,
    )
    if col_remover.button("x", key=f"remover_posicao_{ticker}"):
        if posicoes_mod.remover_posicao(sub, ticker):
            st.rerun()
        else:
            st.error("Não foi possível remover agora (banco indisponível) - tente de novo em alguns instantes.")


def _tabela_concentracao_html(itens: list, limiar_pct: float, prefs: dict) -> str:
    linhas = []
    for item in itens:
        flag = f"<span class='radar-flag'>⚠ acima de {limiar_pct:g}%</span>" if item["peso_pct"] > limiar_pct else ""
        linhas.append(
            f"<tr><td class='rq-esq'>{html.escape(item['nome'])}{flag}</td>"
            f"<td>{config.formatar_numero(item['peso_pct'], 1, prefs['formato_numerico'])}%</td></tr>"
        )
    return (
        "<div class='rq-scroll'><table class='rq-tabela'><thead><tr>"
        "<th class='rq-esq'>ATIVO/SETOR</th><th>PESO NA CARTEIRA</th>"
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
    )


def _tabela_correlacao_html(correlacao: dict, prefs: dict) -> str:
    tickers = list(correlacao.keys())
    cabecalho = "".join(f"<th>{html.escape(t)}</th>" for t in tickers)
    linhas = []
    for t_linha in tickers:
        celulas = "".join(
            f"<td>{config.formatar_numero(correlacao[t_coluna][t_linha], 2, prefs['formato_numerico'])}</td>"
            for t_coluna in tickers
        )
        linhas.append(f"<tr><td class='rq-esq'>{html.escape(t_linha)}</td>{celulas}</tr>")
    return (
        f"<div class='rq-scroll'><table class='rq-tabela'><thead><tr><th class='rq-esq'>&nbsp;</th>{cabecalho}</tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody></table></div>"
    )


def _secao_risco_calculado(info: dict, prefs: dict):
    periodo = info["periodo_historico"]
    st.markdown(
        f"<div class='rq-bloco'><span>CONCENTRAÇÃO POR ATIVO</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(_tabela_concentracao_html(info["concentracao_ativo"], info["limiar_concentracao_pct"], prefs), unsafe_allow_html=True)

    st.markdown("<div class='rq-bloco'><span>CONCENTRAÇÃO POR SETOR</span></div>", unsafe_allow_html=True)
    st.markdown(_tabela_concentracao_html(info["concentracao_setor"], info["limiar_concentracao_pct"], prefs), unsafe_allow_html=True)

    st.markdown(
        f"<div class='rq-bloco'><span>VOLATILIDADE E DRAWDOWN</span>"
        f"<span class='rq-bloco-meta'>janela de {html.escape(periodo)}</span></div>",
        unsafe_allow_html=True,
    )
    col_vol, col_dd, col_queda = st.columns(3)
    col_vol.metric("VOLATILIDADE ANUALIZADA",
                   f"{config.formatar_numero(info['volatilidade_anual_pct'], 1, prefs['formato_numerico'])}%"
                   if info["volatilidade_anual_pct"] is not None else "—")
    col_dd.metric("DRAWDOWN MÁXIMO",
                  f"{config.formatar_numero(info['drawdown_pct'], 1, prefs['formato_numerico'])}%"
                  if info["drawdown_pct"] is not None else "—")
    col_queda.metric("MAIOR QUEDA DIÁRIA",
                      f"{config.formatar_numero(info['maior_queda_diaria_pct'], 1, prefs['formato_numerico'])}%"
                      if info["maior_queda_diaria_pct"] is not None else "—")

    if info["correlacao"]:
        st.markdown("<div class='rq-bloco'><span>CORRELAÇÃO ENTRE OS ATIVOS (RETORNOS DIÁRIOS)</span></div>", unsafe_allow_html=True)
        st.markdown(_tabela_correlacao_html(info["correlacao"], prefs), unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='rq-vazio'>Correlação indisponível: é preciso pelo menos 2 ativos com histórico de preço "
            "suficiente na carteira.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='rq-bloco'><span>CENÁRIO DE ESTRESSE — SE O IBOVESPA CAIR</span></div>", unsafe_allow_html=True)
    cenario = info["cenario_beta"]
    if cenario is None:
        st.markdown(
            "<div class='rq-vazio'>Cenário indisponível: nenhum ativo da carteira tem beta calculável agora.</div>",
            unsafe_allow_html=True,
        )
    else:
        linhas_cenario = "".join(
            f"<tr><td class='rq-esq'>Ibovespa {choque:+g}%</td>"
            f"<td class='rq-baixa'>{config.formatar_numero(impacto, 1, prefs['formato_numerico'])}%</td></tr>"
            for choque, impacto in cenario["impacto_pct"].items()
        )
        st.markdown(
            "<div class='rq-scroll'><table class='rq-tabela'><thead><tr>"
            "<th class='rq-esq'>CENÁRIO</th><th>IMPACTO ESTIMADO NA CARTEIRA</th>"
            f"</tr></thead><tbody>{linhas_cenario}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='rq-nota'>Estimativa (CÁLCULO INTERNO, não é previsão) a partir do beta histórico de cada "
            f"ativo contra o Ibovespa (beta ponderado da carteira: "
            f"{config.formatar_numero(cenario['beta_carteira'], 2, prefs['formato_numerico'])}). "
            + (f"Sem beta calculável: {', '.join(cenario['tickers_sem_beta'])}." if cenario["tickers_sem_beta"] else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    avisos = []
    if info["tickers_sem_preco"]:
        avisos.append(f"sem cotação agora: {', '.join(info['tickers_sem_preco'])} (fora do cálculo)")
    if info["tickers_sem_historico"]:
        avisos.append(f"sem histórico de preço suficiente: {', '.join(info['tickers_sem_historico'])} (fora de correlação/volatilidade/drawdown)")
    if avisos:
        st.markdown(f"<div class='rq-nota'>{html.escape('; '.join(avisos))}.</div>", unsafe_allow_html=True)


def _secao_risco(prefs: dict, sub: str):
    st.markdown("<div class='rq-bloco'><span>MINHAS POSIÇÕES</span></div>", unsafe_allow_html=True)
    _formulario_posicao(sub)

    posicoes_brutas = posicoes_mod.obter_posicoes(sub)
    if posicoes_brutas is None:
        st.markdown("<div class='rq-vazio'>Banco indisponível: não foi possível ler suas posições agora.</div>", unsafe_allow_html=True)
    elif posicoes_brutas:
        info_valores = radar.risco_carteira(sub, prefs)
        valores_atuais = {p["ticker"]: p for p in info_valores.get("posicoes", [])}
        for posicao in posicoes_brutas:
            _linha_posicao_gerenciar(sub, posicao, valores_atuais, prefs)
    else:
        st.markdown("<div class='rq-vazio'>Nenhuma posição cadastrada ainda.</div>", unsafe_allow_html=True)

    info = radar.risco_carteira(sub, prefs)
    st.markdown("<div class='rq-bloco' style='margin-top:1.3rem;'><span>ANÁLISE DE RISCO</span></div>", unsafe_allow_html=True)

    if info["carteira_cadastrada"] is not True:
        st.markdown(
            f"<div class='radar-stub'>{html.escape(info['motivo'])}"
            + (f"<br><br>{html.escape(info['o_que_falta'])}" if info.get("o_que_falta") else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        if "watchlist_tamanho" in info:
            st.caption(
                f"Sua watchlist tem {info['watchlist_tamanho']} ativo(s) - isso é uma lista de acompanhamento, "
                "não uma carteira (sem posição cadastrada, não dá pra calcular concentração, correlação, "
                "volatilidade, drawdown ou cenário de estresse de verdade)."
            )
        return
    if info.get("sem_cotacao"):
        st.markdown(f"<div class='radar-stub'>{html.escape(info['motivo'])}</div>", unsafe_allow_html=True)
        return
    _secao_risco_calculado(info, prefs)


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


def _bloco_contexto_alertas(alertas: list):
    """MARKET MAKERS (data/market_makers.py): contexto do movimento pra
    cada alerta, quando há evidência real (mudança de tese/CVM ou
    catalisador na mesma janela) - nunca inventa um motivo quando não
    há evidência, só não mostra nada pra esse ticker (requisito
    explícito: só explicar "quando houver evidência")."""
    from data.market_makers import contexto_ticker

    tickers = sorted({a.get("ticker") for a in alertas if a.get("ticker")})
    contextos = []
    for ticker in tickers:
        try:
            ctx = contexto_ticker(ticker)
        except Exception as exc:
            print(f"[radar_tab] contexto de mercado indisponível para {ticker}: {exc!r}")
            continue
        if ctx["interpretacao"] or ctx["riscos"]:
            contextos.append(ctx)
    if not contextos:
        return
    with st.expander(f"CONTEXTO DO MOVIMENTO — MARKET MAKERS ({len(contextos)} ativo(s) com evidência)"):
        for ctx in contextos:
            interpretacao = ctx["interpretacao"]
            if interpretacao:
                fonte_html = ""
                if interpretacao.get("fonte_url"):
                    fonte_html = f" · <a href='{html.escape(interpretacao['fonte_url'])}' target='_blank'>{html.escape(interpretacao.get('fonte_label') or 'fonte')}</a>"
                elif interpretacao.get("fonte_label"):
                    fonte_html = f" · {html.escape(interpretacao['fonte_label'])}"
                st.markdown(
                    f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
                    f"<span class='radar-ticker'>{html.escape(ctx['ticker'])}</span>"
                    f"{_selo_evidencia(interpretacao['tipo_evidencia'])}</div>"
                    f"<div class='radar-descricao'>{html.escape(interpretacao['texto'])}</div>"
                    f"<div class='radar-meta'>{fonte_html}</div></div>",
                    unsafe_allow_html=True,
                )
            for risco in ctx["riscos"]:
                st.markdown(
                    f"<div class='rq-nota'>⚠ {html.escape(ctx['ticker'])}: {html.escape(risco)}</div>",
                    unsafe_allow_html=True,
                )
        st.caption(
            "Contexto construído só a partir de evidência já verificada (mudança de tese/CVM real ou "
            "catalisador de calendário) - sem chamada de IA nova. Ativo sem evidência nesta janela não "
            "aparece aqui (não significa que não há nada acontecendo, só que não há evidência rastreável)."
        )


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
        _bloco_contexto_alertas(filtrados)
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
def render_radar(prefs: dict, sub: str):
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
        _secao_risco(prefs, sub)
    with st.expander("RESEARCH COM EVIDÊNCIAS", expanded=False):
        _secao_evidencias(tickers_escopo, watchlist)
    with st.expander("COPILOTO DE RESEARCH", expanded=False):
        _secao_copiloto(tickers_escopo)


# ============================================================
# G. MINHA TESE (registro persistido, ver data/research/tese.py) -
# integração Market Researcher/equity-research da Anthropic
# (2026-10-22, ver docs/market-researcher-integracao.md): adaptação do
# skill "thesis-tracker" oficial. Só na subaba nova (ANÁLISES › Teses) -
# render_radar (composição legada) não ganha esta seção de propósito.
# ============================================================

_TZ_SP = ZoneInfo("America/Sao_Paulo")

_CSS_TESE = """
.tese-secao {
    font-size: 0.68rem; color: var(--cinza); letter-spacing: 0.06em; font-weight: 600;
    text-transform: uppercase; border-bottom: 1px solid var(--borda); padding-bottom: 0.25rem;
    margin: 1.1rem 0 0.5rem 0;
}
.tese-secao:first-of-type { margin-top: 0.2rem; }
.tese-cabecalho { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.tese-empresa { color: var(--destaque); font-weight: 700; font-size: 0.95rem; }
.tese-meta { color: var(--cinza); font-size: 0.68rem; letter-spacing: 0.03em; }
.tese-corpo { font-size: 0.85rem; line-height: 1.6; margin: 0.5rem 0 0.9rem 0; }
.tese-precos { margin-bottom: 0.6rem; }
.tese-coluna-titulo {
    font-size: 0.66rem; color: var(--cinza); letter-spacing: 0.05em; font-weight: 600;
    margin: 0.5rem 0 0.3rem 0; border-top: 1px solid var(--borda); padding-top: 0.5rem;
}
.tese-diff { color: var(--destaque); font-size: 0.66rem; margin-left: 0.4rem; }
/* mesmo bug ja documentado em .radar-stub (ver acima): wrapper do
   Streamlit ao redor de um st.markdown com HTML custom mede a altura
   do bloco errado quando o conteudo tem elementos empilhados sem
   altura fixa - da' respiro no elemento SEGUINTE em vez de tentar
   margin-bottom no proprio bloco. Confirmado de novo aqui (screenshot
   Playwright real, 2026-10-22): um <div> vazio com padding-top sozinho
   NAO reserva espaco visivel quando colado a um st.columns() - so' o
   elemento IRMAO seguinte empurrando pra baixo funciona de verdade. */
div[data-testid="stElementContainer"]:has(.tese-corpo) + * {
    margin-top: 0.4rem;
}
div[data-testid="stElementContainer"]:has(.tese-rodape) {
    margin-top: 0.6rem;
}
/* o proximo irmao pode ser stElementContainer OU stLayoutWrapper
   (envolve expanders/outros widgets "de bloco") - seletor universal
   de proposito, pra nao depender do testid exato do que vem depois. */
div[data-testid="stElementContainer"]:has(.tese-rodape) + * {
    margin-top: 1.4rem;
}
"""


def _nome_empresa_tese(ticker: str) -> str:
    """Mesmo padrao de app.py:nome_empresa - mapa local primeiro, senao
    yfinance (cache de 24h, obter_nome_yf) - nunca inventa nome."""
    from data.prices import obter_nome_yf
    return config.TICKER_NOME.get(ticker) or obter_nome_yf(ticker) or ticker


def _fmt_data_hora_brt(valor: str, so_data: bool = False) -> str:
    """Converte timestamptz (UTC, como o Postgres grava) pro fuso do
    projeto (America/Sao_Paulo) antes de formatar - sem isso a hora
    exibida fica adiantada ~3h em relacao ao horario real de Brasilia
    (mesmo padrao de fuso de data/radar.py:_TZ_SP)."""
    try:
        momento = datetime.fromisoformat(valor)
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        momento_sp = momento.astimezone(_TZ_SP)
        return momento_sp.strftime("%d/%m/%Y") if so_data else momento_sp.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)[:10] or "—"


def _linha_lista_tese(itens: list) -> str:
    if not itens:
        return "<span class='cinza'>nenhuma registrada</span>"
    return "".join(f"<div style='padding:0.05rem 0;'>• {html.escape(str(i))}</div>" for i in itens)


def _cartao_tese_atual(sc: dict, prefs: dict):
    conviccao = sc.get("conviccao") or "—"
    posicao = sc.get("posicao") or "—"
    registrado_fmt = _fmt_data_hora_brt(sc.get("registrado_em", ""))
    empresa = _nome_empresa_tese(sc["ticker"])

    st.markdown(
        f"<div class='tese-cabecalho'>"
        f"<span class='tese-empresa'>{html.escape(sc['ticker'])}</span>"
        f"<span class='tese-meta'>{html.escape(empresa)} · {html.escape(posicao)} · convicção {html.escape(conviccao)} · "
        f"atualizada em {registrado_fmt}</span></div>"
        f"<div class='tese-corpo'>{html.escape(sc['tese_atual'] or '')}</div>",
        unsafe_allow_html=True,
    )

    preco_tese = sc.get("preco_alvo_tese")
    snapshot_casa = ultimo_snapshot("Genial Analisa", sc["ticker"])
    tem_preco_casa = snapshot_casa and snapshot_casa.get("preco_alvo") is not None
    if preco_tese is not None or tem_preco_casa:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if preco_tese is not None:
                st.markdown(
                    f"<div class='tese-precos'>Preço-alvo da tese: <b>R$ {_fmt_num(preco_tese, 2, prefs)}</b> "
                    f"{_selo_evidencia(radar.TIPO_HIPOTESE)}</div>",
                    unsafe_allow_html=True,
                )
        with col_p2:
            if tem_preco_casa:
                st.markdown(
                    f"<div class='tese-precos'>Genial Analisa: <b>R$ {_fmt_num(snapshot_casa['preco_alvo'], 2, prefs)}</b> "
                    f"{_selo_evidencia(radar.TIPO_ESTIMATIVA_TERCEIRO)}</div>",
                    unsafe_allow_html=True,
                )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"<div class='tese-coluna-titulo'>PREMISSAS</div>{_linha_lista_tese(sc['premissas'])}", unsafe_allow_html=True)
    with col_b:
        st.markdown(f"<div class='tese-coluna-titulo'>RISCOS</div>{_linha_lista_tese(sc['riscos'])}", unsafe_allow_html=True)
    with col_c:
        st.markdown(f"<div class='tese-coluna-titulo'>CATALISADORES</div>{_linha_lista_tese(sc['catalisadores'])}", unsafe_allow_html=True)
    st.markdown(
        f"<div class='tese-rodape' style='color:var(--cinza); font-size:0.72rem;'>"
        f"{sc['n_versoes']} versão(ões) registrada(s) · leitura pessoal, não compartilhada entre usuários.</div>",
        unsafe_allow_html=True,
    )


def _diferencas_entre_versoes(atual: dict, anterior: dict | None) -> str:
    """Compara so' campos objetivos (convicção/posição/preço-alvo) entre
    duas versões reais JÁ PERSISTIDAS - nunca infere mudança de texto
    livre (tese/premissas/riscos), que exigiria julgamento de conteúdo
    e poderia "inventar" uma mudança que não houve. Vazio se não houver
    versão anterior pra comparar (primeira versão conhecida) ou se nada
    objetivo mudou - nunca um texto de mudança sem uma comparação real."""
    if anterior is None:
        return ""
    partes = []
    if atual.get("conviccao") != anterior.get("conviccao"):
        partes.append(f"convicção {anterior.get('conviccao') or '—'} → {atual.get('conviccao') or '—'}")
    if atual.get("posicao") != anterior.get("posicao"):
        partes.append(f"posição {anterior.get('posicao') or '—'} → {atual.get('posicao') or '—'}")
    if atual.get("preco_alvo_tese") != anterior.get("preco_alvo_tese"):
        partes.append("preço-alvo atualizado")
    if not partes:
        return ""
    return f"<span class='tese-diff'>[mudou: {html.escape(' · '.join(partes))}]</span>"


def _linha_historico_tese(h: dict, anterior: dict | None, prefs: dict):
    data_fmt = _fmt_data_hora_brt(h.get("registrado_em", ""))
    preco = h.get("preco_alvo_tese")
    preco_txt = f" · preço-alvo R$ {_fmt_num(preco, 2, prefs)}" if preco is not None else ""
    diff_html = _diferencas_entre_versoes(h, anterior)
    st.markdown(
        f"<div style='font-size:0.74rem; padding:0.2rem 0; border-bottom:1px solid var(--borda);'>"
        f"<span class='cinza'>[{data_fmt}]</span> convicção {html.escape(h.get('conviccao') or '—')}{preco_txt}{diff_html}"
        f"<div style='margin-top:0.1rem; color:var(--cinza);'>{html.escape(h.get('tese') or '')}</div></div>",
        unsafe_allow_html=True,
    )


def _limpar_campos_formulario_tese(ticker: str):
    """Chamado so' depois de um salvamento BEM-SUCEDIDO - em falha, as
    chaves nao sao tocadas, e o Streamlit resubstitui os mesmos valores
    digitados no proximo rerun (comportamento nativo de widget com
    `key=`, sem precisar de nenhum cache manual pra preservar o que o
    usuario escreveu)."""
    for sufixo in ("texto", "premissas", "riscos", "catalisadores", "preco"):
        st.session_state.pop(f"tese_{sufixo}_{ticker}", None)


def _formulario_nova_tese(ticker: str, usuario_sub: str):
    with st.form(key=f"tese_form_{ticker}", border=False):
        st.markdown("<div class='tese-secao'>Identificação da tese</div>", unsafe_allow_html=True)
        col_pos, col_conv = st.columns(2)
        with col_pos:
            posicao = st.selectbox("Posição", ["LONG", "SHORT", "WATCHLIST"], key=f"tese_posicao_{ticker}")
        with col_conv:
            conviccao = st.selectbox("Convicção", ["ALTA", "MEDIA", "BAIXA"], key=f"tese_conviccao_{ticker}")

        st.markdown("<div class='tese-secao'>Tese de investimento</div>", unsafe_allow_html=True)
        texto_tese = st.text_area(
            "Tese (1 a 3 parágrafos)", key=f"tese_texto_{ticker}", height=130,
            placeholder=(
                "Por que esta empresa pode gerar retorno? Quais fatores sustentam essa visão "
                "(ex: posição competitiva, resultado recente, ciclo do setor)? Qual o horizonte "
                "considerado (ex: 12-18 meses)?"
            ),
        )

        st.markdown("<div class='tese-secao'>Fundamentos e evidências</div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            premissas_txt = st.text_area(
                "Premissas principais (uma por linha)", key=f"tese_premissas_{ticker}", height=100,
                placeholder="Ex: margem deve expandir com o novo contrato",
            )
            catalisadores_txt = st.text_area(
                "Catalisadores (um por linha)", key=f"tese_catalisadores_{ticker}", height=90,
                placeholder="Ex: resultado do 4T sai em fevereiro",
            )
        with col2:
            riscos_txt = st.text_area(
                "Riscos que invalidariam a tese (um por linha)", key=f"tese_riscos_{ticker}", height=100,
                placeholder="Ex: alavancagem acima do covenant do BNDES",
            )
            preco_alvo_txt = st.text_input(
                "Preço-alvo da tese (opcional, R$) — estimativa pessoal, não é cotação de mercado",
                key=f"tese_preco_{ticker}",
            )

        st.caption("Cada registro cria uma versão nova; as versões anteriores continuam no histórico, nunca são apagadas.")
        enviado = st.form_submit_button("REGISTRAR NOVA VERSÃO DA TESE", width="stretch", type="primary")

    if not enviado:
        return
    preco_alvo_tese = None
    if preco_alvo_txt.strip():
        try:
            preco_alvo_tese = float(preco_alvo_txt.strip().replace(",", "."))
        except ValueError:
            st.error("Preço-alvo inválido — use só números (ex: 42.50).")
            return
    try:
        salvo = tese.registrar_versao(
            usuario_sub=usuario_sub, ticker=ticker, tese=texto_tese,
            premissas=[p.strip() for p in premissas_txt.splitlines() if p.strip()],
            riscos=[r.strip() for r in riscos_txt.splitlines() if r.strip()],
            catalisadores=[c.strip() for c in catalisadores_txt.splitlines() if c.strip()],
            conviccao=conviccao, posicao=posicao, preco_alvo_tese=preco_alvo_tese,
        )
    except ValueError as e:
        st.error(str(e))
        return
    if salvo is None:
        st.error(
            "Não foi possível gravar a tese agora (banco indisponível) — o que você escreveu "
            "continua preenchido, tente novamente em alguns instantes."
        )
    else:
        _limpar_campos_formulario_tese(ticker)
        st.success("Tese registrada — veja a versão nova no histórico abaixo.")
        st.rerun(scope="fragment")


def _secao_tese(tickers: list, usuario_sub: str, prefs: dict):
    st.markdown(f"<style>{_CSS_TESE}</style>", unsafe_allow_html=True)
    if not tickers:
        return
    ticker = st.selectbox("Ativo", tickers, key="radar_tese_ticker", label_visibility="collapsed")
    sc = tese.scorecard(usuario_sub, ticker)
    if sc is not None:
        _cartao_tese_atual(sc, prefs)
        historico = tese.historico_tese(usuario_sub, ticker, limite=10)
        if len(historico) > 1:
            with st.expander(f"Histórico de versões ({len(historico)})"):
                for i, h in enumerate(historico):
                    anterior = historico[i + 1] if i + 1 < len(historico) else None
                    _linha_historico_tese(h, anterior, prefs)
    else:
        empresa = _nome_empresa_tese(ticker)
        st.markdown(
            f"<div class='radar-vazio'>Nenhuma tese registrada ainda para {html.escape(ticker)} "
            f"({html.escape(empresa)}).</div>",
            unsafe_allow_html=True,
        )
    with st.expander("Registrar nova versão da tese", expanded=(sc is None)):
        _formulario_nova_tese(ticker, usuario_sub)


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
def render_radar_acompanhamento(prefs: dict, usuario: dict):
    """Historico de alertas dos ativos DA WATCHLIST + cadastro de posicoes
    e risco real da carteira (ver data/posicoes.py, data/radar.py:
    risco_carteira). Itens salvos/anotacoes pessoais nao existem no banco
    hoje (exigiria tabela nova - fora do escopo desta feature)."""
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
        _secao_risco(prefs, usuario["sub"])
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
def render_teses(prefs: dict, usuario: dict):
    _injetar_css()
    st.markdown('<div class="painel-titulo">TESES</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='rq-nota'>Base de evidências e copiloto de research já existentes. Registro persistente "
        "de tese própria (premissas, riscos, catalisadores, convicção) com histórico de versões — pessoal, "
        "não compartilhado entre usuários.</div>",
        unsafe_allow_html=True,
    )
    escopo = _escopo_watchlist(prefs, com_janela=False)
    if escopo is None:
        return
    tickers, _janela, watchlist = escopo
    with st.expander("MINHA TESE", expanded=True):
        _secao_tese(tickers, usuario["sub"], prefs)
    with st.expander("RESEARCH COM EVIDÊNCIAS", expanded=False):
        _secao_evidencias(tickers, watchlist)
    with st.expander("COPILOTO DE RESEARCH", expanded=False):
        _secao_copiloto(tickers)


def render_preferencias(prefs: dict, usuario: dict, persistir_fn):
    """Mesmo toggle de efeito imediato de ui/morning_call_tab.py:
    render_preferencias (default DESLIGADO, opt-in explicito - ver
    config.PREFS_PADRAO e data/user_prefs.py:listar_assinantes_radar_
    quedas). Preferência própria e separada da do Morning Call: ligar
    uma nunca liga a outra. Só muda a preferência do próprio usuário;
    nunca dispara envio."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">PREFERÊNCIAS DE RECEBIMENTO</div>', unsafe_allow_html=True)
        ativo = st.toggle(
            "RECEBER ALERTAS DO RADAR POR E-MAIL",
            value=prefs.get("radar_quedas_email_ativo", False),
            help=(
                "Envia um e-mail sempre que um ativo monitorado pelo Radar de Quedas cair "
                f"mais de 4% no dia, para {usuario['email']}. "
                "Pode ser desligado a qualquer momento - efeito imediato."
            ),
            key="toggle_radar_quedas_email",
        )
        if ativo != prefs.get("radar_quedas_email_ativo", False):
            prefs["radar_quedas_email_ativo"] = ativo
            if persistir_fn():
                st.toast(
                    "Preferência de alertas do Radar por e-mail salva." if ativo
                    else "Você não vai mais receber alertas do Radar por e-mail.",
                )
            else:
                st.warning("Preferência aplicada nesta sessão (banco indisponível, não foi salva).")
            st.rerun()
