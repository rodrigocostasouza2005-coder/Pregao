# -*- coding: utf-8 -*-
"""Interface da aba MACRO: chamada de render_macro(prefs) pelo app.py."""

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from data.macro import (
    obter_cdi,
    obter_curva_pre,
    obter_focus_ipca,
    obter_focus_selic,
    obter_ipca,
    obter_selic_meta,
)

# Meta de inflacao vigente (Banco Central / CMN): centro 3,0% a.a.,
# tolerancia +-1,5 p.p. (banda 1,5% a 4,5%). Nao da pra importar de
# config.py nesta tarefa (outra sessao esta editando esse arquivo), entao
# a constante fica aqui.
META_IPCA_CENTRO = 3.0
META_IPCA_TOLERANCIA = 1.5

_MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _eixo_x_mes_ano(fig, datas):
    """Ticks do eixo X em 'mês/ano' abreviado PT-BR (ex: 'ago/2026') - o
    Plotly.js nao tem locale PT-BR embutido pro tickformat de datas (so
    ingles por padrao), entao os rotulos sao montados na mao a partir dos
    meses distintos da serie. Amostra no maximo ~10 rotulos pra nao lotar
    o eixo em series longas."""
    meses_unicos = sorted({d.replace(day=1) for d in datas})
    passo = max(1, len(meses_unicos) // 10)
    tickvals = meses_unicos[::passo]
    ticktext = [f"{_MESES_ABREV[d.month - 1]}/{d.year}" for d in tickvals]
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)


_PERIODOS_SELIC_CDI = {
    "3M": 90,
    "6M": 180,
    "1A": 365,
    "3A": 1095,
    "5A": 1825,
}


def _tema_atual(prefs):
    return config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])


def _fmt(valor, casas, prefs):
    if valor is None:
        return "—"
    return config.formatar_numero(valor, casas, prefs["formato_numerico"])


def _fmt_data(timestamp):
    if timestamp is None:
        return "—"
    return timestamp.strftime("%d/%m/%Y")


def _layout_grafico_escuro(fig, tema, altura=380):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=tema["fundo"],
        plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
        height=altura,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor="#1A1A1A")
    fig.update_yaxes(gridcolor="#1A1A1A")


def _escolha_estavel_macro(chave_widget, opcoes, padrao):
    """Igual ao helper de app.py (nao importavel dali): guarda a ultima
    escolha valida de um segmented_control entre reruns."""
    chave_memoria = "macro_" + chave_widget + "_valido"
    ultimo_valido = st.session_state.get(chave_memoria, padrao)
    if ultimo_valido not in opcoes:
        ultimo_valido = padrao
    return ultimo_valido, chave_memoria


def _painel_resumo(prefs):
    st.markdown('<div class="painel-titulo">RESUMO</div>', unsafe_allow_html=True)
    faltando = []

    selic_df = obter_selic_meta(dias_historico=20)
    cdi_df = obter_cdi(dias_historico=20)
    ipca_df = obter_ipca(dias_historico=120)
    focus_ipca_df = obter_focus_ipca()
    focus_selic_df = obter_focus_selic()

    selic_meta = selic_df["selic_meta_pct"].iloc[-1] if selic_df is not None else None
    selic_data = selic_df["data"].iloc[-1] if selic_df is not None else None
    if selic_df is None:
        faltando.append("Selic meta (SGS)")

    cdi_aa = cdi_df["cdi_anualizado_pct"].iloc[-1] if cdi_df is not None else None
    cdi_data = cdi_df["data"].iloc[-1] if cdi_df is not None else None
    if cdi_df is None:
        faltando.append("CDI (SGS)")

    ipca_12m = ipca_df["ipca_12m_pct"].dropna().iloc[-1] if ipca_df is not None and not ipca_df["ipca_12m_pct"].dropna().empty else None
    ipca_data = ipca_df["data"].iloc[-1] if ipca_df is not None else None
    if ipca_df is None:
        faltando.append("IPCA (SGS)")

    juro_real = None
    if cdi_aa is not None and ipca_12m is not None:
        juro_real = ((1 + cdi_aa / 100) / (1 + ipca_12m / 100) - 1) * 100

    st.markdown(
        f"""
        <table style="width:100%; border-collapse:collapse;">
        <thead><tr>
            <th style="text-align:left; font-weight:400;" class="cinza">SELIC META</th>
            <th class="cinza">CDI (a.a.)</th>
            <th class="cinza">IPCA 12M</th>
            <th class="cinza">JURO REAL EX-POST</th>
        </tr></thead>
        <tbody><tr>
            <td style="text-align:left; font-size:1.05rem; font-weight:600; color:var(--destaque);">{_fmt(selic_meta, 2, prefs)}%
                <div class="cinza" style="font-size:0.62rem; font-weight:400;">{_fmt_data(selic_data)}</div></td>
            <td class="neutro" style="font-size:1.05rem; font-weight:600;">{_fmt(cdi_aa, 2, prefs)}%
                <div class="cinza" style="font-size:0.62rem; font-weight:400;">{_fmt_data(cdi_data)}</div></td>
            <td class="neutro" style="font-size:1.05rem; font-weight:600;">{_fmt(ipca_12m, 2, prefs)}%
                <div class="cinza" style="font-size:0.62rem; font-weight:400;">{_fmt_data(ipca_data)}</div></td>
            <td class="neutro" style="font-size:1.05rem; font-weight:600;">{_fmt(juro_real, 2, prefs)}%
                <div class="cinza" style="font-size:0.62rem; font-weight:400;">CDI vs IPCA 12m</div></td>
        </tr></tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    def _linha_focus(nome, df):
        if df is None or df.empty:
            faltando.append(f"Focus {nome}")
            return "<td class='cinza'>—</td><td class='cinza'>—</td>"
        celulas = ""
        for _, linha in df.iterrows():
            celulas += (
                f"<td class='neutro'>{int(linha['ano_referencia'])}: "
                f"<span style='font-weight:600;'>{_fmt(linha['mediana_pct'], 2, prefs)}%</span></td>"
            )
        celulas += "<td class='cinza'>—</td>" * (2 - df.shape[0])
        return celulas

    data_calculo_focus = None
    if focus_ipca_df is not None and not focus_ipca_df.empty:
        data_calculo_focus = focus_ipca_df["data_calculo"].iloc[0]
    elif focus_selic_df is not None and not focus_selic_df.empty:
        data_calculo_focus = focus_selic_df["data_calculo"].iloc[0]

    st.markdown(
        f"""
        <table style="width:100%; border-collapse:collapse; margin-top:0.3rem;">
        <thead><tr>
            <th colspan="2" style="text-align:left; font-weight:400;" class="cinza">FOCUS IPCA (mediana)</th>
            <th colspan="2" style="text-align:left; font-weight:400;" class="cinza">FOCUS SELIC (mediana)</th>
        </tr></thead>
        <tbody><tr>
            {_linha_focus("IPCA", focus_ipca_df)}
            {_linha_focus("Selic", focus_selic_df)}
        </tr></tbody>
        </table>
        <div class="cinza" style="font-size:0.62rem; margin-top:0.2rem;">
            Pesquisa Focus/BC de {_fmt_data(data_calculo_focus)}</div>
        """,
        unsafe_allow_html=True,
    )

    if faltando:
        st.warning("Indisponível no momento: " + ", ".join(faltando) + ".")


def _painel_curva_pre(prefs):
    st.markdown('<div class="painel-titulo">CURVA PRÉ (ETTJ ANBIMA)</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)
    hoje = date.today()

    curva_hoje = obter_curva_pre()
    curva_semana = obter_curva_pre(hoje - timedelta(days=7))
    curva_mes = obter_curva_pre(hoje - timedelta(days=30))

    if curva_hoje is None:
        st.warning("Curva pré indisponível no momento (fonte ANBIMA fora do ar ou sem publicação hoje).")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curva_hoje["dias_uteis"] / 252, y=curva_hoje["taxa_aa_pct"],
        name=f"Hoje ({_fmt_data(curva_hoje['data_referencia'].iloc[0])})",
        mode="lines+markers", line=dict(color=tema["destaque"], width=2),
    ))
    if curva_semana is not None:
        fig.add_trace(go.Scatter(
            x=curva_semana["dias_uteis"] / 252, y=curva_semana["taxa_aa_pct"],
            name=f"1 semana atrás ({_fmt_data(curva_semana['data_referencia'].iloc[0])})",
            mode="lines+markers", line=dict(color=tema["ciano"], width=1.5, dash="dot"),
        ))
    if curva_mes is not None:
        fig.add_trace(go.Scatter(
            x=curva_mes["dias_uteis"] / 252, y=curva_mes["taxa_aa_pct"],
            name=f"1 mês atrás ({_fmt_data(curva_mes['data_referencia'].iloc[0])})",
            mode="lines+markers", line=dict(color=tema["cinza"], width=1.5, dash="dash"),
        ))

    _layout_grafico_escuro(fig, tema)
    fig.update_xaxes(
        title="Prazo", tickvals=[1, 2, 5, 10],
        ticktext=["1A", "2A", "5A", "10A"],
    )
    fig.update_yaxes(title="% a.a.")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    if curva_mes is None:
        st.warning(
            "Comparação de 1 mês atrás indisponível: o endpoint da ANBIMA usado aqui só mantém "
            "~1 semana útil de histórico (testado na prática)."
        )


def _painel_ipca(prefs):
    st.markdown('<div class="painel-titulo">IPCA</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)

    df = obter_ipca(dias_historico=760)
    if df is None:
        st.warning("IPCA indisponível no momento (fonte SGS/BC fora do ar).")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    cores_barras = [tema["alta"] if v >= 0 else tema["baixa"] for v in df["ipca_mensal_pct"]]
    fig.add_trace(
        go.Bar(x=df["data"], y=df["ipca_mensal_pct"], name="IPCA mensal (%)", marker_color=cores_barras, opacity=0.7),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df["data"], y=df["ipca_12m_pct"], name="IPCA 12 meses (%)",
                   line=dict(color=tema["destaque"], width=2)),
        secondary_y=True,
    )

    _layout_grafico_escuro(fig, tema)
    fig.update_yaxes(title_text="Mensal (%)", secondary_y=False, gridcolor="#1A1A1A")

    # eixo do 12m com range fixo (nao autorange): sem isso, o shape da
    # meta (1.5 a 4.5) entra no calculo do autorange do Plotly junto com
    # os dados e produz um range/ticks esquisitos (ex: 2.462/3.633/4.804)
    # que faziam a faixa parecer cobrir o grafico quase todo
    piso = min(0.0, float(df["ipca_12m_pct"].min()) - 1.0, META_IPCA_CENTRO - META_IPCA_TOLERANCIA - 1.0)
    teto = max(6.0, float(df["ipca_12m_pct"].max()) + 1.0, META_IPCA_CENTRO + META_IPCA_TOLERANCIA + 1.0)
    ticks_1_5 = [v * 1.5 for v in range(0, 20) if piso - 0.01 <= v * 1.5 <= teto + 0.01]
    fig.update_yaxes(
        title_text="12 meses (%)", secondary_y=True, gridcolor="#1A1A1A",
        range=[piso, teto], tickvals=ticks_1_5,
    )

    # faixa da meta de inflacao (centro +- tolerancia), plotada no eixo do
    # acumulado 12m, que e o que a meta efetivamente mede
    fig.add_shape(
        type="rect", xref="paper", yref="y2",
        x0=0, x1=1,
        y0=META_IPCA_CENTRO - META_IPCA_TOLERANCIA, y1=META_IPCA_CENTRO + META_IPCA_TOLERANCIA,
        fillcolor=tema["ciano"], opacity=0.08, line_width=0, layer="below",
    )

    _eixo_x_mes_ano(fig, df["data"])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown(
        f"<div class='cinza' style='font-size:0.62rem;'>Faixa sombreada: meta de inflação "
        f"{_fmt(META_IPCA_CENTRO, 1, prefs)}% ± {_fmt(META_IPCA_TOLERANCIA, 1, prefs)} p.p. (Banco Central/CMN)</div>",
        unsafe_allow_html=True,
    )


def _painel_selic_cdi(prefs):
    st.markdown('<div class="painel-titulo">SELIC x CDI</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)

    periodos = list(_PERIODOS_SELIC_CDI.keys())
    padrao, mem = _escolha_estavel_macro("periodo_selic_cdi", periodos, "1A")
    sel = st.segmented_control(
        "Período", periodos, default=padrao,
        label_visibility="collapsed", key="macro_periodo_selic_cdi",
    )
    periodo = sel or padrao
    st.session_state[mem] = periodo
    dias = _PERIODOS_SELIC_CDI[periodo]

    selic_df = obter_selic_meta(dias_historico=dias)
    cdi_df = obter_cdi(dias_historico=dias)

    if selic_df is None and cdi_df is None:
        st.warning("Selic e CDI indisponíveis no momento (fonte SGS/BC fora do ar).")
        return

    fig = go.Figure()
    if selic_df is not None:
        fig.add_trace(go.Scatter(x=selic_df["data"], y=selic_df["selic_meta_pct"], name="Selic meta",
                                  line=dict(color=tema["destaque"], width=1.5)))
    if cdi_df is not None:
        fig.add_trace(go.Scatter(x=cdi_df["data"], y=cdi_df["cdi_anualizado_pct"], name="CDI anualizado",
                                  line=dict(color=tema["ciano"], width=1.5)))

    _layout_grafico_escuro(fig, tema)
    fig.update_yaxes(title="% a.a.")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    faltando = []
    if selic_df is None:
        faltando.append("Selic meta")
    if cdi_df is None:
        faltando.append("CDI")
    if faltando:
        st.warning("Indisponível no momento: " + ", ".join(faltando) + ".")


def render_macro(prefs):
    """Ponto de entrada da aba MACRO. Chamar dentro de `with aba_macro:`."""
    with st.container(border=True):
        _painel_resumo(prefs)

    with st.container(border=True):
        _painel_curva_pre(prefs)

    with st.container(border=True):
        _painel_ipca(prefs)

    with st.container(border=True):
        _painel_selic_cdi(prefs)
