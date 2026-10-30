# -*- coding: utf-8 -*-
"""Reset de zoom reutilizável pros gráficos Plotly do projeto (pedido no
redesign do terminal - ver PROGRESSO.md). Sem componente JS novo: cada
gráfico recebe uma `key=` que muda quando o usuário clica em RESET ou
quando os parâmetros que definem o gráfico mudam (ticker/período/
comparação/etc) - o Streamlit remonta o componente Plotly do zero nesses
casos, o que reseta qualquer zoom aplicado (estado é guardado no
client, atrelado à key do componente) automaticamente.

`displayModeBar` fica desligado de propósito em todo o projeto (barra
de ferramentas nativa do Plotly escondida, visual mais limpo) - o botão
de reset visível por isso é um `st.button` comum, não o ícone nativo do
Plotly. Duplo clique continua funcionando sozinho: é comportamento
padrão do Plotly (`doubleClick: 'reset+autosize'`), independente de
`displayModeBar`."""

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from data.prices import dias_sem_pregao, obter_historico, obter_historico_intraday


def zoom_key(chave_base: str, *partes_estado) -> str:
    """Renderiza um botão pequeno "↺" alinhado à direita (chamar logo
    ANTES do st.plotly_chart correspondente) e retorna a `key=` pra
    passar pro gráfico. `partes_estado`: qualquer valor que, ao mudar
    (ticker, período, comparar_ibov, tipo de gráfico...), já deve por si
    só resetar o zoom - entram na key junto com o contador do botão,
    então tanto "trocar filtro" quanto "clicar em reset" produzem uma
    key nova, forçando o Streamlit a remontar o gráfico com o range
    original. Nenhuma coleta de dado nova acontece por causa disso - é
    só remontagem do componente com o `fig` já calculado no mesmo rerun."""
    contador_key = f"_zoom_reset_{chave_base}"
    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0
    _vazio, col_botao = st.columns([12, 1])
    with col_botao:
        if st.button("↺", key=f"{contador_key}_btn", help="Resetar zoom do gráfico"):
            st.session_state[contador_key] += 1
    sufixo_estado = "_".join(str(p) for p in partes_estado)
    return f"{chave_base}_{sufixo_estado}_{st.session_state[contador_key]}"


def renderizar_grafico_preco(
    ticker: str,
    prefs: dict,
    tema: dict,
    key_prefix: str,
    periodos: list,
    periodo_padrao: str = "6M",
    altura: int = 420,
    permitir_comparar_ibov: bool = False,
    permitir_mm: bool = False,
    mostrar_stats_periodo: bool = True,
) -> None:
    """Componente de gráfico de preço compartilhado (candle/linha/área +
    volume), extraído em 2026-10-30 da aba ANÁLISES > Empresas (lógica
    que já existia lá, inline, não-reutilizável) pra também alimentar o
    gráfico principal da VISÃO GERAL - mesma função de dado
    (obter_historico/obter_historico_intraday), zero requisição nova,
    zero lógica duplicada entre as duas telas. `permitir_comparar_ibov`/
    `permitir_mm` desligados por padrão (telas mais compactas, tipo
    VISÃO GERAL, não precisam desses controles extras - EQUITY liga os
    dois explicitamente)."""
    chave_memoria_periodo = f"{key_prefix}_periodo_valido"
    padrao = st.session_state.get(chave_memoria_periodo, periodo_padrao)
    if padrao not in periodos:
        padrao = periodo_padrao if periodo_padrao in periodos else periodos[0]
    sel_periodo = st.segmented_control(
        "Período", periodos, default=padrao, label_visibility="collapsed", key=f"{key_prefix}_periodo",
    )
    periodo = sel_periodo or padrao
    st.session_state[chave_memoria_periodo] = periodo
    eh_intraday = periodo in config.PERIODOS_INTRADIARIOS

    comparar_ibov = False
    if permitir_comparar_ibov:
        comparar_ibov = st.checkbox(
            "Comparar com Ibovespa (base 100)", value=False, key=f"{key_prefix}_comparar_ibov",
        )

    if eh_intraday:
        df = obter_historico_intraday(ticker, periodo)
    else:
        df = obter_historico(ticker, periodo)

    def _layout_grafico_escuro(fig):
        fig.update_layout(
            template="plotly_dark", paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
            font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
            xaxis_rangeslider_visible=False, height=altura,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
        )
        fig.update_xaxes(gridcolor=tema["borda"])
        fig.update_yaxes(gridcolor=tema["borda"])

    if df is None or df.empty:
        if eh_intraday:
            st.warning(f"Não foi possível obter o histórico intradiário de {ticker}.")
        else:
            st.warning(f"Não foi possível obter o histórico de {ticker} para o período {periodo}.")
        return

    if comparar_ibov and not eh_intraday:
        fig = go.Figure()
        serie_ativo = (df["Close"] / df["Close"].iloc[0]) * 100
        fig.add_trace(go.Scatter(x=df["Data"], y=serie_ativo, name=ticker,
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
        chave_zoom = zoom_key(f"{key_prefix}_comparativo", ticker, periodo)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave_zoom)
        return

    if permitir_comparar_ibov and comparar_ibov and eh_intraday:
        st.info("Comparação com Ibovespa não disponível para períodos intradiários (1D/1S).")

    tem_ohlc = {"Open", "High", "Low"}.issubset(df.columns) and df[["Open", "High", "Low"]].notna().all(axis=None)
    tipo_grafico = prefs.get("grafico_tipo", "LINHA")
    if tipo_grafico == "CANDLE" and not tem_ohlc:
        tipo_grafico = "LINHA"

    tem_volume = "Volume" in df.columns and df["Volume"].notna().any()
    if tem_volume:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
    else:
        fig = make_subplots(rows=1, cols=1)

    if tipo_grafico == "CANDLE":
        fig.add_trace(
            go.Candlestick(
                x=df["Data"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name=ticker,
                increasing_line_color=tema["alta"], decreasing_line_color=tema["baixa"],
            ),
            row=1, col=1,
        )
    elif tipo_grafico == "AREA":
        fig.add_trace(
            go.Scatter(x=df["Data"], y=df["Close"], name=ticker, fill="tozeroy",
                       line=dict(color=tema["destaque"], width=1.5)),
            row=1, col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(x=df["Data"], y=df["Close"], name=ticker, line=dict(color=tema["destaque"], width=1.5)),
            row=1, col=1,
        )

    if permitir_mm:
        sufixo_mm = ""
        if eh_intraday:
            sufixo_mm = " (5 min)" if periodo == "1D" else " (30 min)"
        cor_mm20 = tema["neutro"] if tipo_grafico in ("LINHA", "AREA") else tema["destaque"]
        if prefs.get("mm20") and "MM20" in df.columns and df["MM20"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM20"], name=f"MM20{sufixo_mm}",
                                      line=dict(color=cor_mm20, width=1)), row=1, col=1)
        if prefs.get("mm50") and "MM50" in df.columns and df["MM50"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM50"], name=f"MM50{sufixo_mm}",
                                      line=dict(color=tema["ciano"], width=1)), row=1, col=1)
        if prefs.get("mm200") and "MM200" in df.columns and df["MM200"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM200"], name=f"MM200{sufixo_mm}",
                                      line=dict(color=tema["cinza"], width=1)), row=1, col=1)

    if tem_volume:
        if tem_ohlc:
            cores_volume = [tema["alta"] if c >= o else tema["baixa"] for o, c in zip(df["Open"], df["Close"])]
        else:
            cores_volume = tema["destaque"]
        fig.add_trace(
            go.Bar(x=df["Data"], y=df["Volume"], name="Volume", marker_color=cores_volume, opacity=0.6),
            row=2, col=1,
        )

    _layout_grafico_escuro(fig)

    if eh_intraday:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[17, 10], pattern="hour")])
    else:
        _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
        if intervalo_periodo == "1d":
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=dias_sem_pregao(df))])

    chave_zoom = zoom_key(f"{key_prefix}_grafico", ticker, periodo, tipo_grafico, comparar_ibov)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave_zoom)

    if not mostrar_stats_periodo:
        return

    fmt = prefs.get("formato_numerico")
    abertura = float(df["Close"].iloc[0])
    fechamento = float(df["Close"].iloc[-1])
    maxima = float(df["High"].max()) if tem_ohlc else float(df["Close"].max())
    minima = float(df["Low"].min()) if tem_ohlc else float(df["Close"].min())
    var_periodo = (fechamento - abertura) / abertura * 100 if abertura else None
    cls_var = "alta" if (var_periodo or 0) >= 0 else "baixa"
    stats = [
        ("ÚLTIMO", config.formatar_numero(fechamento, 2, fmt), "neutro"),
        ("MÁXIMA DO PERÍODO", config.formatar_numero(maxima, 2, fmt), "neutro"),
        ("MÍNIMA DO PERÍODO", config.formatar_numero(minima, 2, fmt), "neutro"),
    ]
    if var_periodo is not None:
        sinal = "+" if var_periodo >= 0 else ""
        stats.append(("VARIAÇÃO NO PERÍODO", f"{sinal}{config.formatar_numero(var_periodo, 2, fmt)}%", cls_var))
    blocos = [
        f"<div style='margin-right:1.3rem;'><div class='cinza' style='font-size:0.6rem;'>{rot}</div>"
        f"<div class='{cls}' style='font-size:0.76rem; font-weight:700; margin-top:0.1rem;'>{val}</div></div>"
        for rot, val, cls in stats
    ]
    st.markdown(
        f"<div style='display:flex; flex-wrap:wrap; margin-top:0.5rem; padding-top:0.5rem; "
        f"border-top:1px solid var(--borda);'>{''.join(blocos)}</div>",
        unsafe_allow_html=True,
    )
