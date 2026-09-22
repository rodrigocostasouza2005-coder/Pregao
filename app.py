# -*- coding: utf-8 -*-
"""PREGÃO - terminal de mercado pessoal. Interface principal (Streamlit)."""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import auth
import config
from data.prices import dias_sem_pregao, obter_cotacao, obter_historico, obter_nome_yf, validar_ticker
from data.user_prefs import obter_prefs, salvar_prefs

st.set_page_config(page_title="PREGÃO", layout="wide", initial_sidebar_state="expanded")

with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


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

# --- abas: ordem/visibilidade vem das preferencias, CONFIG sempre por ultimo
abas_visiveis = [a for a in prefs["abas_visiveis"] if a in config.ABAS_DISPONIVEIS]
if not abas_visiveis:
    abas_visiveis = list(config.ABAS_DISPONIVEIS)
rotulos = [f"{i + 1} {chave}" for i, chave in enumerate(abas_visiveis)] + [f"{len(abas_visiveis) + 1} CONFIG"]
abas = st.tabs(rotulos)
abas_por_chave = dict(zip(abas_visiveis, abas))
aba_config = abas[-1]


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
                f"<div style='display:flex; justify-content:space-between; align-items:baseline;'>"
                f"<span style='color:var(--destaque); font-weight:600;'>{t}</span>{var_html}</div>"
                f"<div class='cinza' style='font-size:0.66rem;'>{nome}</div>",
                unsafe_allow_html=True,
            )
            if col_remover.button("x", key=f"remover_{t}"):
                prefs["watchlist"].remove(t)
                _persistir_prefs()
                st.rerun()

    _fragmento_watchlist()


# --- aba EQUITY --------------------------------------------------------------
if "EQUITY" in abas_por_chave:
    with abas_por_chave["EQUITY"]:
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

                    st.markdown(
                        f"""
                        <table style="width:100%; border-collapse:collapse;">
                        <thead><tr>
                            <th style="text-align:left; font-weight:400;" class="cinza">{ticker_sel} {nome_empresa_sel}</th>
                            <th class="cinza">VARIAÇÃO DIA</th>
                            <th class="cinza">MÁX/MÍN DIA</th>
                            <th class="cinza">VOLUME</th>
                            <th class="cinza">MÁX 52 SEM</th>
                            <th class="cinza">MÍN 52 SEM</th>
                        </tr></thead>
                        <tbody><tr>
                            <td style="text-align:left; font-size:1.15rem; font-weight:600;" class="{sinal_classe}">
                                R$ {config.formatar_numero(cotacao['preco'], 2, fmt)}</td>
                            <td class="{sinal_classe}">{sinal_sim}{config.formatar_numero(cotacao['variacao'], 2, fmt)}
                                ({sinal_sim}{config.formatar_numero(cotacao['variacao_pct'], 2, fmt)}%)</td>
                            <td class="neutro">{config.formatar_numero(cotacao['maxima_dia'], 2, fmt)} /
                                {config.formatar_numero(cotacao['minima_dia'], 2, fmt)}</td>
                            <td class="neutro">{config.formatar_numero(cotacao['volume'], 0, fmt)}</td>
                            <td class="neutro">{config.formatar_numero(cotacao['maxima_52s'], 2, fmt)}</td>
                            <td class="neutro">{config.formatar_numero(cotacao['minima_52s'], 2, fmt)}</td>
                        </tr></tbody>
                        </table>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div class='cinza' style='font-size:0.65rem; margin-top:0.3rem;'>"
                        f"Última atualização {datetime.now().strftime('%H:%M:%S')} — "
                        f"cotação com atraso de ~15 min (fonte: Yahoo Finance)</div>",
                        unsafe_allow_html=True,
                    )

            with st.container(border=True):
                _painel_precos(ticker_selecionado)

            with st.container(border=True):
                st.markdown('<div class="painel-titulo">GRÁFICO</div>', unsafe_allow_html=True)

                periodos = list(config.PERIODOS_GRAFICO.keys())
                padrao_periodo = prefs["grafico_periodo_padrao"] if prefs["grafico_periodo_padrao"] in periodos else "6M"
                padrao_periodo, mem_periodo = _escolha_estavel("periodo_grafico", periodos, padrao_periodo)
                sel_periodo = st.segmented_control(
                    "Período", periodos, default=padrao_periodo,
                    label_visibility="collapsed", key="periodo_grafico",
                )
                periodo = sel_periodo or padrao_periodo
                st.session_state[mem_periodo] = periodo

                df = obter_historico(ticker_selecionado, periodo)

                if df is None:
                    st.warning(f"Não foi possível obter o histórico de {ticker_selecionado} para o período {periodo}.")
                else:
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

                    if prefs["mm20"]:
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM20"], name="MM20",
                                       line=dict(color=tema["destaque"], width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm50"]:
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM50"], name="MM50",
                                       line=dict(color=tema["ciano"], width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm200"]:
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM200"], name="MM200",
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

                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor=tema["fundo"],
                        plot_bgcolor=tema["fundo"],
                        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
                        xaxis_rangeslider_visible=False,
                        height=480,
                        margin=dict(l=10, r=10, t=10, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
                    )

                    # remove buracos de fim de semana/feriado no eixo X (so faz sentido em barras diarias)
                    _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
                    if intervalo_periodo == "1d":
                        feriados = dias_sem_pregao(df)
                        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=feriados)])

                    fig.update_xaxes(gridcolor="#1A1A1A")
                    fig.update_yaxes(gridcolor="#1A1A1A")

                    st.plotly_chart(fig, width="stretch")


# --- abas futuras (placeholders) ------------------------------------------
_titulos_futuros = {"MACRO": "Fase 2", "RESEARCH": "Fase 4", "NEWS": "Fase 3", "CVM": "Fase 5"}
for chave, fase in _titulos_futuros.items():
    if chave in abas_por_chave:
        with abas_por_chave[chave]:
            st.info(f"Painel {chave} ainda não implementado ({fase}).")


# --- aba CONFIG --------------------------------------------------------------
with aba_config:
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

            novas_abas = st.multiselect(
                "ABAS VISÍVEIS (a ordem de seleção define a ordem de exibição)",
                config.ABAS_DISPONIVEIS, default=abas_visiveis,
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
                    "atualizacao_intervalo": config.INTERVALOS_ATUALIZACAO[novo_rotulo_intervalo],
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
