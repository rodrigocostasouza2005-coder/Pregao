# -*- coding: utf-8 -*-
"""PREGÃO - terminal de mercado pessoal. Interface principal (Streamlit)."""

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import auth
import config
from data import diagnostico
from data.prices import (
    calcular_retornos,
    dias_sem_pregao,
    obter_cotacao,
    obter_cotacao_indice,
    obter_historico,
    obter_historico_intraday,
    obter_indicadores,
    obter_nome_yf,
    validar_ticker,
)
from data.research import CASAS as CASAS_RESEARCH
from data.user_prefs import obter_prefs, salvar_prefs
from ui.macro_tab import render_macro
from ui.news_tab import render_news, render_news_ticker
from ui.research_tab import render_research
from ui.sistema_tab import render_sistema
from ui.top_mercado_tab import render_top_mercado

st.set_page_config(page_title="PREGÃO", layout="wide", initial_sidebar_state="expanded")

with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

FUSO_BR = ZoneInfo("America/Sao_Paulo")


# --- login obrigatorio: sem login, so a tela de apresentacao -------------
if not auth.logado():
    auth.tela_apresentacao()
    st.stop()

usuario = auth.dados_usuario()


def nome_empresa(ticker: str) -> str:
    """Nome da empresa: mapa local primeiro, senao busca no yfinance."""
    return config.TICKER_NOME.get(ticker) or obter_nome_yf(ticker)


# --- carregar preferencias (uma vez por sessao, ou se o usuario mudou) --
if st.session_state.get("prefs_sub") != usuario["sub"]:
    prefs, banco_ok = obter_prefs(usuario["sub"])
    st.session_state.prefs = prefs
    st.session_state.prefs_sub = usuario["sub"]
    st.session_state.banco_ok = banco_ok

prefs = st.session_state.prefs


def _persistir_prefs():
    """Tenta salvar no Supabase; se falhar, alteracoes valem so nesta sessao."""
    ok = salvar_prefs(usuario["sub"], usuario["email"], st.session_state.prefs)
    st.session_state.banco_ok = ok
    return ok


# --- migra abas novas (ex: TOP MERCADO) pras prefs de usuarios existentes -
# so adiciona em abas_visiveis o que o usuario AINDA NAO CONHECIA (nao
# reaparece uma aba que ele escondeu de proposito) - abas_conhecidas
# registra o que ja foi oferecido a ele, pra diferenciar "nunca vi essa
# aba" de "vi e escondi de proposito". So persiste quando ha algo novo
# (evita escrita no Supabase a toa em toda rerun).
_abas_novas = [a for a in config.ABAS_DISPONIVEIS if a not in prefs.get("abas_conhecidas", [])]
if _abas_novas:
    prefs["abas_visiveis"] = list(prefs.get("abas_visiveis", [])) + [
        a for a in _abas_novas if a not in prefs.get("abas_visiveis", [])
    ]
    prefs["abas_conhecidas"] = list(prefs.get("abas_conhecidas", [])) + _abas_novas
    _persistir_prefs()


def _escolha_estavel(chave_widget: str, opcoes: list, padrao):
    """Guarda a ultima escolha valida de um segmented_control (que pode voltar None ao desmarcar)."""
    chave_memoria = chave_widget + "_valido"
    ultimo_valido = st.session_state.get(chave_memoria, padrao)
    if ultimo_valido not in opcoes:
        ultimo_valido = padrao
    return ultimo_valido, chave_memoria


# --- aplicar tema escolhido como variaveis CSS ---------------------------
tema = config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])
_css_vars = (
    f":root {{"
    f"--bg:{tema['fundo']}; --painel-bg:{tema['painel']}; --borda:{tema['borda']}; "
    f"--destaque:{tema['destaque']}; --alta:{tema['alta']}; --baixa:{tema['baixa']}; "
    f"--neutro:{tema['neutro']}; --cinza:{tema['cinza']}; --ciano:{tema['ciano']}; "
    f"--padding-painel:{config.DENSIDADES.get(prefs['densidade'], '0.4rem')}; "
    f"--fonte-base:{config.FONTES.get(prefs['fonte'], '0.9rem')};"
    f"}}"
)
st.markdown(f"<style>{_css_vars}</style>", unsafe_allow_html=True)


# --- ticker tape: Ibovespa, dolar e a watchlist, atualiza no mesmo ritmo dos
# precos. Renderizada ANTES do cabecalho de proposito: fica dentro de uma
# faixa position:fixed no topo (ver .pregao-topo-fixo no style.css), que
# reserva o espaco de cima pro header nativo do Streamlit (onde mora a barra
# de Share/estrela/GitHub do Community Cloud - essa barra tem z-index muito
# maior que o nosso e sempre aparece por cima, nunca escondida). O resto do
# conteudo (cabecalho PREGAO, abas etc.) vem depois, em fluxo normal, com
# espaco reservado no padding-top do block-container.
@st.fragment(run_every=prefs["atualizacao_intervalo"])
def _ticker_tape():
    fmt = prefs["formato_numerico"]
    itens = []

    for nome_idx, symbol_idx in config.INDICES_TICKER_TAPE.items():
        cot = obter_cotacao_indice(nome_idx, symbol_idx)
        if cot.get("erro"):
            itens.append(f"<span class='cinza'>{nome_idx} --</span>")
        else:
            cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
            sinal = "+" if cot["variacao_pct"] >= 0 else ""
            itens.append(
                f"<span class='cinza'>{nome_idx}</span> "
                f"<span class='{cls}'>{config.formatar_numero(cot['preco'], 2, fmt)} "
                f"({sinal}{config.formatar_numero(cot['variacao_pct'], 2, fmt)}%)</span>"
            )

    for t in prefs["watchlist"]:
        cot = obter_cotacao(t)
        if cot.get("erro"):
            itens.append(f"<span style='color:var(--destaque);'>{t}</span> <span class='cinza'>--</span>")
        else:
            cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
            sinal = "+" if cot["variacao_pct"] >= 0 else ""
            itens.append(
                f"<span style='color:var(--destaque);'>{t}</span> "
                f"<span class='{cls}'>{sinal}{config.formatar_numero(cot['variacao_pct'], 2, fmt)}%</span>"
            )

    conteudo = " &nbsp;·&nbsp; ".join(itens)
    animado = prefs["ticker_tape_modo"] == "ANIMADO"

    if not animado:
        st.markdown(
            f"<div class='pregao-topo-fixo'><div class='ticker-tape-wrap fixo'><div class='ticker-tape-track'>"
            f"<span class='ticker-tape-set'>{conteudo}</span></div></div></div>",
            unsafe_allow_html=True,
        )
        return

    # velocidade constante: duracao da animacao escala com o tamanho do
    # conteudo (estimado pelo numero de caracteres visiveis, fonte mono),
    # senao a rolagem acelera visualmente quando a watchlist cresce
    velocidade_px_s = config.VELOCIDADES_TICKER_TAPE[prefs["ticker_tape_velocidade"]]
    texto_visivel = re.sub(r"<[^>]+>", "", conteudo)
    largura_estimada_px = len(texto_visivel) * 7.5
    duracao_s = max(largura_estimada_px / velocidade_px_s, 8)

    # animation-delay negativo: a animacao parece ter comecado no epoch e
    # estar rodando continuamente, entao o refresh do fragment (que troca o
    # elemento HTML inteiro) nao gera um "pulo" visivel de volta ao inicio
    atraso_s = -(time.time() % duracao_s)

    st.markdown(
        f"<div class='pregao-topo-fixo'><div class='ticker-tape-wrap'>"
        f"<div class='ticker-tape-track' style='animation-duration:{duracao_s:.1f}s; animation-delay:{atraso_s:.1f}s;'>"
        f"<span class='ticker-tape-set'>{conteudo}</span>"
        f"<span class='ticker-tape-set'>{conteudo}</span>"
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


_ticker_tape()

# --- cabecalho ------------------------------------------------------------
col_logo, col_email, col_sair = st.columns([6, 2, 1])
with col_logo:
    st.markdown('<div class="pregao-logo">PREGÃO</div>', unsafe_allow_html=True)
with col_email:
    st.markdown(
        f"<div class='cinza' style='text-align:right; padding-top:0.65rem; font-size:0.7rem; "
        f"white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='{usuario['email']}'>"
        f"{usuario['email']}</div>",
        unsafe_allow_html=True,
    )
with col_sair:
    if st.button("SAIR", width="stretch"):
        st.logout()

if not st.session_state.banco_ok:
    st.warning("Sem conexão com o Supabase — preferências e watchlist valem só para esta sessão.")

# --- secoes de navegacao: ordem/visibilidade vem das preferencias, CONFIG
# sempre por ultimo. So a secao ativa executa (diferente de st.tabs(), que
# roda o conteudo de TODAS as abas em toda rerun e so esconde por CSS) -
# alem de mais rapido, uma excecao numa secao nao derruba as outras (era
# o caso do bug que deixava RESEARCH e CONFIG em branco juntos).
abas_visiveis = [a for a in prefs["abas_visiveis"] if a in config.ABAS_DISPONIVEIS]
if not abas_visiveis:
    abas_visiveis = list(config.ABAS_DISPONIVEIS)
secoes = abas_visiveis + ["CONFIG"]
# SISTEMA: so pros e-mails admin, e so no menu deles - de proposito NAO
# entra em config.ABAS_DISPONIVEIS (isso faria abas_conhecidas oferecer
# a aba pra todo mundo, ver migracao de abas novas la em cima)
_eh_admin = usuario["email"] in config.obter_emails_admin()
if _eh_admin:
    secoes = secoes + ["SISTEMA"]
rotulos_secao = [f"{i + 1} {chave}" for i, chave in enumerate(secoes)]
mapa_rotulo_secao = dict(zip(rotulos_secao, secoes))

padrao_rotulo_secao, mem_secao = _escolha_estavel("secao_ativa", rotulos_secao, rotulos_secao[0])
with st.container(key="nav_secao"):
    sel_secao = st.segmented_control(
        "Seção", rotulos_secao, default=padrao_rotulo_secao,
        label_visibility="collapsed", key="secao_ativa",
    )
rotulo_secao_atual = sel_secao or padrao_rotulo_secao
st.session_state[mem_secao] = rotulo_secao_atual
secao_atual = mapa_rotulo_secao[rotulo_secao_atual]


# --- sidebar: gestao da watchlist ------------------------------------------
with st.sidebar:
    st.markdown('<div class="painel-titulo">WATCHLIST</div>', unsafe_allow_html=True)

    if "contador_input_ticker" not in st.session_state:
        st.session_state.contador_input_ticker = 0

    novo_ticker = st.text_input(
        "Adicionar ticker (ex: PETR4)",
        key=f"input_novo_ticker_{st.session_state.contador_input_ticker}",
        label_visibility="collapsed", placeholder="ADICIONAR TICKER (EX: PETR4)",
    ).strip().upper()

    if st.button("ADICIONAR", width="stretch"):
        if not novo_ticker:
            st.warning("Digite um ticker.")
        elif novo_ticker in prefs["watchlist"]:
            st.warning(f"{novo_ticker} já está na lista.")
        elif validar_ticker(novo_ticker):
            prefs["watchlist"].append(novo_ticker)
            _persistir_prefs()
            st.session_state.contador_input_ticker += 1  # forca campo vazio no rerun
            st.rerun()
        else:
            st.error(f"Ticker '{novo_ticker}' não encontrado no yfinance.")

    @st.fragment(run_every=prefs["atualizacao_intervalo"])
    def _fragmento_watchlist():
        for t in list(prefs["watchlist"]):
            cot = obter_cotacao(t)
            nome = nome_empresa(t)
            if cot.get("erro"):
                var_html = "<span class='cinza'>--</span>"
            else:
                cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
                sinal = "+" if cot["variacao_pct"] >= 0 else ""
                var_html = f"<span class='{cls}'>{sinal}{config.formatar_numero(cot['variacao_pct'], 2, prefs['formato_numerico'])}%</span>"

            col_info, col_remover = st.columns([4, 1])
            col_info.markdown(
                f"<div style='padding-bottom:0.35rem; margin-bottom:0.35rem; border-bottom:1px solid var(--borda);'>"
                f"<div style='display:flex; justify-content:space-between; align-items:baseline;'>"
                f"<span style='color:var(--destaque); font-weight:600;'>{t}</span>{var_html}</div>"
                f"<div class='cinza' style='font-size:0.66rem; margin-top:0.1rem;'>{nome}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if col_remover.button("x", key=f"remover_{t}"):
                prefs["watchlist"].remove(t)
                _persistir_prefs()
                st.rerun()

    _fragmento_watchlist()


# --- aba EQUITY --------------------------------------------------------------
if secao_atual == "EQUITY":
    with st.container():
        if not prefs["watchlist"]:
            st.info("Adicione um ticker na barra lateral para começar.")
        else:
            padrao_ticker, mem_ticker = _escolha_estavel("ticker_selecionado", prefs["watchlist"], prefs["watchlist"][0])
            sel = st.segmented_control(
                "Ticker", prefs["watchlist"], default=padrao_ticker,
                label_visibility="collapsed", key="ticker_selecionado",
            )
            ticker_selecionado = sel or padrao_ticker
            st.session_state[mem_ticker] = ticker_selecionado

            @st.fragment(run_every=prefs["atualizacao_intervalo"])
            def _painel_precos(ticker_sel):
                cotacao = obter_cotacao(ticker_sel)
                st.markdown('<div class="painel-titulo">PREÇOS</div>', unsafe_allow_html=True)

                if cotacao.get("erro"):
                    st.warning(f"Não foi possível obter a cotação de {ticker_sel}: {cotacao['erro']}")
                else:
                    fmt = prefs["formato_numerico"]
                    sinal_classe = "alta" if cotacao["variacao"] >= 0 else "baixa"
                    sinal_sim = "+" if cotacao["variacao"] >= 0 else ""
                    nome_empresa_sel = nome_empresa(ticker_sel)

                    def _num_ou_traco(valor, casas=2):
                        return config.formatar_numero(valor, casas, fmt) if valor is not None else "—"

                    max_min_dia = (
                        f"{_num_ou_traco(cotacao['maxima_dia'])} / {_num_ou_traco(cotacao['minima_dia'])}"
                        if cotacao["maxima_dia"] is not None or cotacao["minima_dia"] is not None else "—"
                    )

                    st.markdown(
                        f"""
                        <div style="overflow-x:auto; overflow-y:hidden;">
                        <table style="width:100%; border-collapse:collapse;">
                        <thead><tr>
                            <th style="text-align:left; font-weight:400; white-space:normal;" class="cinza">{ticker_sel} {nome_empresa_sel}</th>
                            <th class="cinza">VARIAÇÃO DIA</th>
                            <th class="cinza">MÁX/MÍN DIA</th>
                            <th class="cinza">VOLUME</th>
                            <th class="cinza">MÁX 52 SEM</th>
                            <th class="cinza">MÍN 52 SEM</th>
                        </tr></thead>
                        <tbody><tr>
                            <td style="text-align:left; font-size:1.15rem; font-weight:600;" class="{sinal_classe}">
                                R$ {_num_ou_traco(cotacao['preco'])}</td>
                            <td class="{sinal_classe}">{sinal_sim}{_num_ou_traco(cotacao['variacao'])}
                                ({sinal_sim}{_num_ou_traco(cotacao['variacao_pct'])}%)</td>
                            <td class="neutro">{max_min_dia}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['volume'], 0)}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['maxima_52s'])}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['minima_52s'])}</td>
                        </tr></tbody>
                        </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    # todas as janelas partem do mesmo preco atual do painel
                    # PRECOS (fast_info), nao do fechamento historico de
                    # ontem - senao cada janela podia comparar contra uma
                    # "foto" diferente do preco
                    preco_para_retornos = cotacao["preco"] if not cotacao.get("erro") else None
                    retornos = calcular_retornos(ticker_sel, preco_para_retornos) if preco_para_retornos else {}
                    # garante 1D identico a VARIACAO DIA por construcao,
                    # mesmo que o "fechamento de 1 dia atras" do historico
                    # caia numa data ligeiramente diferente do previousClose
                    # do fast_info
                    if retornos and not cotacao.get("erro"):
                        retornos["1D"] = cotacao["variacao_pct"]
                    if retornos:
                        partes = []
                        for rotulo in config.JANELAS_RETORNO:
                            valor = retornos.get(rotulo)
                            if valor is None:
                                partes.append(f"<span class='cinza'>{rotulo} —</span>")
                            else:
                                cls = "alta" if valor >= 0 else "baixa"
                                sinal = "+" if valor >= 0 else ""
                                partes.append(
                                    f"<span class='cinza'>{rotulo}</span> "
                                    f"<span class='{cls}'>{sinal}{config.formatar_numero(valor, 1, fmt)}%</span>"
                                )
                        st.markdown(
                            "<div style='display:flex; gap:0.9rem; flex-wrap:wrap; font-size:0.72rem; "
                            "margin-top:0.4rem; overflow-x:auto; overflow-y:hidden;'>" + "".join(partes) + "</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown(
                        f"<div class='cinza' style='font-size:0.65rem; margin-top:0.3rem;'>"
                        f"Última atualização {datetime.now(FUSO_BR).strftime('%H:%M:%S')} — "
                        f"cotação com atraso de ~15 min (fonte: Yahoo Finance)</div>",
                        unsafe_allow_html=True,
                    )

            with st.container(border=True):
                _painel_precos(ticker_selecionado)

            with st.container(border=True):
                st.markdown('<div class="painel-titulo">INDICADORES</div>', unsafe_allow_html=True)
                fmt = prefs["formato_numerico"]
                ind = obter_indicadores(ticker_selecionado)
                dy = ind["dividend_yield"]
                st.markdown(
                    f"""
                    <div style="overflow-x:auto; overflow-y:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                    <thead><tr>
                        <th class="cinza">VALOR DE MERCADO</th>
                        <th class="cinza">P/L</th>
                        <th class="cinza">P/VP</th>
                        <th class="cinza">DIV. YIELD (12M)</th>
                        <th class="cinza" title="cov(retornos semanais do papel, retornos semanais do Ibovespa) / var(retornos semanais do Ibovespa), 2 anos - calculado localmente, nao vem do yfinance">BETA (2A)</th>
                    </tr></thead>
                    <tbody><tr>
                        <td class="neutro">{config.formatar_valor_mercado(ind['valor_mercado'], fmt)}</td>
                        <td class="neutro">{config.formatar_numero(ind['pl'], 2, fmt) if ind['pl'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['pvp'], 2, fmt) if ind['pvp'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(dy, 2, fmt) + '%' if dy is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['beta'], 2, fmt) if ind['beta'] is not None else '—'}</td>
                    </tr></tbody>
                    </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.container(border=True):
                titulo_grafico = st.empty()
                titulo_grafico.markdown('<div class="painel-titulo">GRÁFICO</div>', unsafe_allow_html=True)

                periodos = config.PERIODOS_INTRADIARIOS + list(config.PERIODOS_GRAFICO.keys())
                padrao_periodo = prefs["grafico_periodo_padrao"] if prefs["grafico_periodo_padrao"] in periodos else "6M"
                padrao_periodo, mem_periodo = _escolha_estavel("periodo_grafico", periodos, padrao_periodo)
                sel_periodo = st.segmented_control(
                    "Período", periodos, default=padrao_periodo,
                    label_visibility="collapsed", key="periodo_grafico",
                )
                periodo = sel_periodo or padrao_periodo
                st.session_state[mem_periodo] = periodo
                eh_intraday = periodo in config.PERIODOS_INTRADIARIOS

                comparar_ibov = st.checkbox("Comparar com Ibovespa (base 100)", value=False, key="comparar_ibov")

                if eh_intraday:
                    df = obter_historico_intraday(ticker_selecionado, periodo)
                else:
                    df = obter_historico(ticker_selecionado, periodo)

                if eh_intraday and periodo == "1D" and df is not None and not df.empty:
                    data_pregao = df["Data"].iloc[-1].strftime("%d/%m")
                    titulo_grafico.markdown(
                        f'<div class="painel-titulo">GRÁFICO — PREGÃO DE {data_pregao}</div>',
                        unsafe_allow_html=True,
                    )

                def _layout_grafico_escuro(fig, altura=480):
                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor=tema["fundo"],
                        plot_bgcolor=tema["fundo"],
                        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
                        xaxis_rangeslider_visible=False,
                        height=altura,
                        margin=dict(l=10, r=10, t=10, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
                    )
                    fig.update_xaxes(gridcolor="#1A1A1A")
                    fig.update_yaxes(gridcolor="#1A1A1A")

                if df is None:
                    if eh_intraday:
                        st.warning(f"Não foi possível obter o histórico intradiário de {ticker_selecionado}.")
                    else:
                        st.warning(f"Não foi possível obter o histórico de {ticker_selecionado} para o período {periodo}.")
                elif comparar_ibov and not eh_intraday:
                    fig = go.Figure()
                    serie_acao = (df["Close"] / df["Close"].iloc[0]) * 100
                    fig.add_trace(go.Scatter(x=df["Data"], y=serie_acao, name=ticker_selecionado,
                                              line=dict(color=tema["destaque"], width=1.5)))

                    df_ibov = obter_historico(config.SIMBOLO_IBOVESPA, periodo)
                    if df_ibov is None:
                        st.warning("Não foi possível obter o histórico do Ibovespa para comparação.")
                    else:
                        serie_ibov = (df_ibov["Close"] / df_ibov["Close"].iloc[0]) * 100
                        fig.add_trace(go.Scatter(x=df_ibov["Data"], y=serie_ibov, name="IBOVESPA",
                                                  line=dict(color=tema["ciano"], width=1.5)))

                    _layout_grafico_escuro(fig)
                    fig.update_yaxes(title="Base 100")

                    _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
                    if intervalo_periodo == "1d":
                        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=dias_sem_pregao(df))])

                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
                else:
                    if comparar_ibov and eh_intraday:
                        st.info("Comparação com Ibovespa não disponível para períodos intradiários (1D/1S).")

                    fig = make_subplots(
                        rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.75, 0.25], vertical_spacing=0.03,
                    )

                    tipo_grafico = prefs["grafico_tipo"]
                    if tipo_grafico == "CANDLE":
                        fig.add_trace(
                            go.Candlestick(
                                x=df["Data"], open=df["Open"], high=df["High"],
                                low=df["Low"], close=df["Close"], name=ticker_selecionado,
                                increasing_line_color=tema["alta"], decreasing_line_color=tema["baixa"],
                            ),
                            row=1, col=1,
                        )
                    elif tipo_grafico == "AREA":
                        fig.add_trace(
                            go.Scatter(
                                x=df["Data"], y=df["Close"], name=ticker_selecionado, fill="tozeroy",
                                line=dict(color=tema["destaque"], width=1.5),
                            ),
                            row=1, col=1,
                        )
                    else:  # LINHA
                        fig.add_trace(
                            go.Scatter(
                                x=df["Data"], y=df["Close"], name=ticker_selecionado,
                                line=dict(color=tema["destaque"], width=1.5),
                            ),
                            row=1, col=1,
                        )

                    sufixo_mm = ""
                    if eh_intraday:
                        sufixo_mm = " (5 min)" if periodo == "1D" else " (30 min)"

                    # em CANDLE o preco vira barras alta/baixa (sem cor propria) - MM20
                    # pode usar --destaque sem colidir. Em LINHA/AREA o preco JA usa
                    # --destaque, entao MM20 precisa de outra cor pra nao ficar
                    # indistinguivel da linha de preco (ver BACKLOG.md)
                    cor_mm20 = tema["neutro"] if tipo_grafico in ("LINHA", "AREA") else tema["destaque"]
                    if prefs["mm20"] and df["MM20"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM20"], name=f"MM20{sufixo_mm}",
                                       line=dict(color=cor_mm20, width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm50"] and df["MM50"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM50"], name=f"MM50{sufixo_mm}",
                                       line=dict(color=tema["ciano"], width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm200"] and df["MM200"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM200"], name=f"MM200{sufixo_mm}",
                                       line=dict(color=tema["cinza"], width=1)),
                            row=1, col=1,
                        )

                    cores_volume = [
                        tema["alta"] if c >= o else tema["baixa"]
                        for o, c in zip(df["Open"], df["Close"])
                    ]
                    fig.add_trace(
                        go.Bar(x=df["Data"], y=df["Volume"], name="Volume",
                               marker_color=cores_volume, opacity=0.6),
                        row=2, col=1,
                    )

                    _layout_grafico_escuro(fig)

                    if eh_intraday:
                        # esconde fim de semana e fora do horario de pregao da B3
                        # (10h-17h, conferido nos dados intradiarios reais)
                        fig.update_xaxes(rangebreaks=[
                            dict(bounds=["sat", "mon"]),
                            dict(bounds=[17, 10], pattern="hour"),
                        ])
                    else:
                        # remove buracos de fim de semana/feriado no eixo X (so faz sentido em barras diarias)
                        _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
                        if intervalo_periodo == "1d":
                            feriados = dias_sem_pregao(df)
                            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=feriados)])

                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

            with st.container(border=True):
                render_news_ticker(ticker_selecionado, prefs)


# --- aba MACRO -----------------------------------------------------------
if secao_atual == "MACRO":
    with st.container():
        render_macro(prefs)


# --- aba RESEARCH ---------------------------------------------------------
if secao_atual == "RESEARCH":
    with st.container():
        render_research(prefs)


# --- aba NEWS --------------------------------------------------------------
if secao_atual == "NEWS":
    with st.container():
        render_news(prefs)


# --- aba TOP MERCADO --------------------------------------------------------
if secao_atual == "TOP MERCADO":
    with st.container():
        render_top_mercado(prefs)


# --- aba SISTEMA (so admin) -------------------------------------------------
if secao_atual == "SISTEMA":
    with st.container():
        render_sistema(prefs)


# --- abas futuras (placeholders) ------------------------------------------
_titulos_futuros = {"CVM": "Fase 5"}
if secao_atual in _titulos_futuros:
    with st.container():
        st.info(f"Painel {secao_atual} ainda não implementado ({_titulos_futuros[secao_atual]}).")


# --- aba CONFIG --------------------------------------------------------------
if secao_atual == "CONFIG":
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CONFIG</div>', unsafe_allow_html=True)

        with st.form("form_config"):
            c1, c2 = st.columns(2)
            with c1:
                novo_tema = st.selectbox("TEMA", list(config.TEMAS.keys()),
                                          index=list(config.TEMAS.keys()).index(prefs["tema"]))
                nova_densidade = st.selectbox("DENSIDADE", list(config.DENSIDADES.keys()),
                                               index=list(config.DENSIDADES.keys()).index(prefs["densidade"]))
                nova_fonte = st.selectbox("TAMANHO DA FONTE", list(config.FONTES.keys()),
                                           index=list(config.FONTES.keys()).index(prefs["fonte"]))
                novo_formato = st.selectbox("FORMATO NUMÉRICO", ["BR", "US"],
                                             index=["BR", "US"].index(prefs["formato_numerico"]))
                rotulos_intervalo = list(config.INTERVALOS_ATUALIZACAO.keys())
                valores_intervalo = list(config.INTERVALOS_ATUALIZACAO.values())
                idx_intervalo = valores_intervalo.index(prefs["atualizacao_intervalo"]) if prefs["atualizacao_intervalo"] in valores_intervalo else 1
                novo_rotulo_intervalo = st.selectbox("ATUALIZAÇÃO AUTOMÁTICA", rotulos_intervalo, index=idx_intervalo)
            with c2:
                novo_tipo_grafico = st.selectbox("TIPO DE GRÁFICO", ["CANDLE", "LINHA", "AREA"],
                                                  index=["CANDLE", "LINHA", "AREA"].index(prefs["grafico_tipo"]))
                novo_periodo_padrao = st.selectbox("PERÍODO PADRÃO", list(config.PERIODOS_GRAFICO.keys()),
                                                    index=list(config.PERIODOS_GRAFICO.keys()).index(prefs["grafico_periodo_padrao"]))
                novo_mm20 = st.checkbox("MÉDIA MÓVEL 20", value=prefs["mm20"])
                novo_mm50 = st.checkbox("MÉDIA MÓVEL 50", value=prefs["mm50"])
                novo_mm200 = st.checkbox("MÉDIA MÓVEL 200", value=prefs["mm200"])
                novo_tape_modo = st.selectbox("LETREIRO", ["ANIMADO", "FIXO"],
                                               index=["ANIMADO", "FIXO"].index(prefs["ticker_tape_modo"]))
                novo_tape_velocidade = st.selectbox("VELOCIDADE DO LETREIRO", list(config.VELOCIDADES_TICKER_TAPE.keys()),
                                                     index=list(config.VELOCIDADES_TICKER_TAPE.keys()).index(prefs["ticker_tape_velocidade"]))

            novas_abas = st.multiselect(
                "ABAS VISÍVEIS (a ordem de seleção define a ordem de exibição)",
                config.ABAS_DISPONIVEIS, default=abas_visiveis,
            )

            ids_casas_research = [c["id"] for c in CASAS_RESEARCH]
            nomes_casas_research = {c["id"]: c["nome"] for c in CASAS_RESEARCH}
            padrao_casas_research = [c for c in prefs.get("research_casas_ativas", []) if c in ids_casas_research]
            novas_casas_research = st.multiselect(
                "CASAS DE RESEARCH",
                ids_casas_research, default=padrao_casas_research,
                format_func=lambda cid: nomes_casas_research.get(cid, cid),
            )

            salvar = st.form_submit_button("SALVAR")
            if salvar:
                st.session_state.prefs.update({
                    "tema": novo_tema,
                    "densidade": nova_densidade,
                    "fonte": nova_fonte,
                    "formato_numerico": novo_formato,
                    "grafico_tipo": novo_tipo_grafico,
                    "grafico_periodo_padrao": novo_periodo_padrao,
                    "mm20": novo_mm20,
                    "mm50": novo_mm50,
                    "mm200": novo_mm200,
                    "abas_visiveis": novas_abas or list(config.ABAS_DISPONIVEIS),
                    "research_casas_ativas": novas_casas_research or list(config.PREFS_PADRAO["research_casas_ativas"]),
                    "atualizacao_intervalo": config.INTERVALOS_ATUALIZACAO[novo_rotulo_intervalo],
                    "ticker_tape_modo": novo_tape_modo,
                    "ticker_tape_velocidade": novo_tape_velocidade,
                })
                if _persistir_prefs():
                    st.success("Preferências salvas.")
                else:
                    st.warning("Preferências aplicadas nesta sessão (banco indisponível, não foram salvas).")
                st.rerun()

        if st.button("RESTAURAR PADRÃO"):
            watchlist_atual = st.session_state.prefs["watchlist"]
            st.session_state.prefs = dict(config.PREFS_PADRAO)
            st.session_state.prefs["watchlist"] = watchlist_atual
            if _persistir_prefs():
                st.success("Preferências restauradas ao padrão.")
            else:
                st.warning("Preferências restauradas nesta sessão (banco indisponível, não foram salvas).")
            st.rerun()

    # --- painel DIAGNOSTICO DE FONTES: so pro(s) e-mail(s) admin (config.obter_emails_admin) -
    # testa cada fonte de verdade, rodando neste servidor (local ou Streamlit Cloud),
    # pra saber o que funciona em producao sem depender do sandbox de desenvolvimento
    # (varios dominios ficam bloqueados por WAF/CDN so la - ver BACKLOG.md)
    if usuario["email"] in config.obter_emails_admin():
        with st.container(border=True):
            st.markdown('<div class="painel-titulo">DIAGNÓSTICO DE FONTES</div>', unsafe_allow_html=True)
            st.markdown(
                "<div class='cinza' style='font-size:0.7rem; margin-bottom:0.4rem;'>"
                "Testa cada fonte externa rodando aqui no servidor — mostra o que "
                "funciona de verdade em produção.</div>",
                unsafe_allow_html=True,
            )
            if st.button("TESTAR TODAS AS FONTES"):
                resultados = []
                with st.status("Testando fontes...", expanded=True) as status_box:
                    for fonte in diagnostico.FONTES:
                        st.write(f"Testando {fonte['nome']}...")
                        resultado = diagnostico.testar_fonte(fonte)
                        resultados.append(resultado)
                        sinal = "OK" if resultado["ok"] else "FALHOU"
                        st.write(f"→ {fonte['nome']}: {sinal} ({resultado['status']}, {resultado['tempo_ms']}ms)")
                    status_box.update(label="Diagnóstico concluído.", state="complete")

                linhas_html = "".join(
                    f"<tr><td style='text-align:left;' class='neutro'>{r['nome']}</td>"
                    f"<td class='{'alta' if r['ok'] else 'baixa'}'>{r['status']}</td>"
                    f"<td class='neutro'>{r['tempo_ms']}ms</td>"
                    f"<td class='neutro'>{r['tamanho_bytes']:,} bytes</td></tr>"
                    for r in resultados
                )
                st.markdown(
                    f"""
                    <div style="overflow-x:auto; overflow-y:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                    <thead><tr>
                        <th style="text-align:left; font-weight:400;" class="cinza">FONTE</th>
                        <th class="cinza">STATUS</th>
                        <th class="cinza">TEMPO</th>
                        <th class="cinza">TAMANHO</th>
                    </tr></thead>
                    <tbody>{linhas_html}</tbody>
                    </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
