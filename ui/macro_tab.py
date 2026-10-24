# -*- coding: utf-8 -*-
"""Interface da aba MACRO: chamada de render_macro(prefs) pelo app.py."""

from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from data.macro import (
    TZ,
    obter_cdi,
    obter_cenario_global,
    obter_curva_pre,
    obter_focus_ipca,
    obter_focus_selic,
    obter_ipca,
    obter_selic_meta,
    obter_selic_meta_copom,
)
from data.prices import rotulo_cotacao_em_cache
from ui import graficos, workspace

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
    # tema["borda"] (nao "#1A1A1A" fixo, achado da auditoria visual
    # 2026-10-16): acompanha o tema CLARO tambem, nao so' os temas escuros.
    fig.update_xaxes(gridcolor=tema["borda"])
    fig.update_yaxes(gridcolor=tema["borda"])


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

    QUANTIDADE_ANOS_FOCUS = 3

    def _linha_focus(nome, df):
        if df is None or df.empty:
            faltando.append(f"Focus {nome}")
            return "<td class='cinza'>—</td>" * QUANTIDADE_ANOS_FOCUS
        celulas = ""
        for _, linha in df.iterrows():
            celulas += (
                f"<td class='neutro'>{int(linha['ano_referencia'])}: "
                f"<span style='font-weight:600;'>{_fmt(linha['mediana_pct'], 2, prefs)}%</span></td>"
            )
        celulas += "<td class='cinza'>—</td>" * (QUANTIDADE_ANOS_FOCUS - df.shape[0])
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
            <th colspan="{QUANTIDADE_ANOS_FOCUS}" style="text-align:left; font-weight:400;" class="cinza">FOCUS IPCA (mediana)</th>
            <th colspan="{QUANTIDADE_ANOS_FOCUS}" style="text-align:left; font-weight:400;" class="cinza">FOCUS SELIC (mediana)</th>
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
    # date.today() usa o fuso do servidor (UTC no Streamlit Cloud) - entre
    # 21h e 23h59 no horario de Brasilia isso já é "amanhã" em UTC, o que
    # rotulava a publicação de hoje da ANBIMA como "Última" por engano e
    # deslocava as janelas de "1 semana"/"1 mês atrás" em 1 dia (achado
    # real, 2026-10-08 - mesma classe de bug já corrigida em app.py/
    # data/eventos.py para outros usos de data "hoje").
    hoje = datetime.now(TZ).date()

    curva_hoje = obter_curva_pre()
    curva_semana = obter_curva_pre(hoje - timedelta(days=7))
    curva_mes = obter_curva_pre(hoje - timedelta(days=30))

    if curva_hoje is None:
        st.warning("Curva pré indisponível no momento (fonte ANBIMA fora do ar ou sem publicação hoje).")
        return

    # a ANBIMA publica a ETTJ so' ao FIM do dia - antes disso (ou num fim
    # de semana/feriado), obter_curva_pre() ainda retorna a ultima
    # publicacao disponivel, que pode ser de um dia anterior. Rotular
    # isso de "Hoje" seria enganoso - "Última" com a data real deixa
    # claro que pode nao ser a publicacao de hoje.
    data_ref_hoje = curva_hoje["data_referencia"].iloc[0]
    eh_hoje = hasattr(data_ref_hoje, "date") and data_ref_hoje.date() == hoje
    rotulo_hoje = "Hoje" if eh_hoje else "Última"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curva_hoje["dias_uteis"] / 252, y=curva_hoje["taxa_aa_pct"],
        name=f"{rotulo_hoje} ({_fmt_data(data_ref_hoje)})",
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
    chave = graficos.zoom_key("macro_curva_pre", data_ref_hoje)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)

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
    fig.update_yaxes(title_text="Mensal (%)", secondary_y=False, gridcolor=tema["borda"])

    # eixo do 12m com range fixo (nao autorange): sem isso, o shape da
    # meta (1.5 a 4.5) entra no calculo do autorange do Plotly junto com
    # os dados e produz um range/ticks esquisitos (ex: 2.462/3.633/4.804)
    # que faziam a faixa parecer cobrir o grafico quase todo
    piso = min(0.0, float(df["ipca_12m_pct"].min()) - 1.0, META_IPCA_CENTRO - META_IPCA_TOLERANCIA - 1.0)
    teto = max(6.0, float(df["ipca_12m_pct"].max()) + 1.0, META_IPCA_CENTRO + META_IPCA_TOLERANCIA + 1.0)
    ticks_1_5 = [v * 1.5 for v in range(0, 20) if piso - 0.01 <= v * 1.5 <= teto + 0.01]
    fig.update_yaxes(
        title_text="12 meses (%)", secondary_y=True, gridcolor=tema["borda"],
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
    chave = graficos.zoom_key("macro_ipca", df["data"].iloc[-1] if not df.empty else "")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)
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
    chave = graficos.zoom_key("macro_selic_cdi", periodo)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)

    faltando = []
    if selic_df is None:
        faltando.append("Selic meta")
    if cdi_df is None:
        faltando.append("CDI")
    if faltando:
        st.warning("Indisponível no momento: " + ", ".join(faltando) + ".")


_UNIDADES_CENARIO_GLOBAL = {
    "Ouro": "US$/oz t",
    "Brent": "US$/barril",
    "WTI": "US$/barril",
    "Minério de Ferro": "US$/ton",
    "Treasuries 10A": "% a.a.",
    "VIX": "pts",
}


def _fmt_pct(valor, prefs):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{config.formatar_numero(valor, 2, prefs['formato_numerico'])}%"


def _painel_cenario_global(prefs):
    st.markdown('<div class="painel-titulo">CENÁRIO GLOBAL</div>', unsafe_allow_html=True)
    dados = obter_cenario_global()
    if not dados:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    partes = []
    for d in dados:
        cls = "alta" if d["variacao_pct"] >= 0 else "baixa"
        unidade = _UNIDADES_CENARIO_GLOBAL.get(d["nome"], "")
        partes.append(
            f"<div style='min-width:9rem;'><span class='cinza' style='font-size:0.7rem;'>{d['nome']}</span><br>"
            f"<span class='neutro' style='font-size:0.85rem;'>{config.formatar_numero(d['preco'], 2, prefs['formato_numerico'])}</span> "
            f"<span class='cinza' style='font-size:0.62rem;'>{unidade}</span><br>"
            f"<span class='{cls}' style='font-size:0.78rem;'>{_fmt_pct(d['variacao_pct'], prefs)}</span></div>"
        )
    st.markdown(
        "<div style='display:flex; flex-wrap:wrap; gap:1rem;'>" + "".join(partes) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Fonte: Yahoo Finance (futuros/índices) — cotação com atraso típico de mercado, uso informativo."
    )


# paineis registrados (ver ui/paineis.py) - ordem reorganizavel por
# usuario em CONFIG. RESUMO fica de fora do registro de proposito:
# funciona como abertura fixa da aba, sempre em primeiro (mesmo padrao
# do TERMOMETRO em ui/mercado_tab.py).
REGISTRO_PAINEIS = [
    ("curva_pre", "Curva pré (ETTJ ANBIMA)", _painel_curva_pre),
    ("ipca", "IPCA", _painel_ipca),
    ("selic_cdi", "Selic x CDI", _painel_selic_cdi),
    ("cenario_global", "Cenário global", _painel_cenario_global),
]

# altura padrao (workspace.layout_efetivo) MAIOR que o generico
# (18rem/288px) pros 3 paineis com grafico Plotly de altura=380px (ver
# _layout_grafico_escuro) + cabecalho do painel - bug real corrigido
# 2026-10-10 (confirmado por screenshot real do Playwright): com o
# padrao generico, o grafico nao cabia no painel (que usa overflow:auto,
# nao hidden) e ficava com o rodape cortado/so' acessivel rolando DENTRO
# do painel, inclusive o titulo do eixo Y ("Mensal (%)"/"% a.a."), ate' o
# usuario redimensionar manualmente. "cenario_global" (cards, nao
# grafico) fica de fora - cabe no padrao generico sem desperdicar
# espaco.
# selic_cdi precisa de mais altura que os outros 2: unico painel com uma
# linha extra de UI (segmented_control de periodo) ACIMA do grafico.
_ALTURAS_PADRAO = {"curva_pre": 28.0, "ipca": 28.0, "selic_cdi": 30.0}


def render_macro(prefs, persistir_fn=None):
    """Ponto de entrada da aba MACRO. Chamar dentro de `with aba_macro:`.
    `persistir_fn` (opcional): ver ui/workspace.py:renderizar_workspace.

    MACRO migra pro workspace modular (ETAPA 2, 2026-10-01) depois da
    ETAPA 1 (MERCADO) validada em produção - mesmo REGISTRO_PAINEIS de
    antes, só troca `ui.paineis.renderizar` por
    `ui.workspace.renderizar_workspace` (API idêntica)."""
    with st.container(border=True):
        _painel_resumo(prefs)

    workspace.renderizar_workspace(
        "MACRO", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn, alturas_padrao=_ALTURAS_PADRAO,
    )


# ============================================================
# Subabas do PREGAO 2.0 (ui/navegacao.py): MACRO > Indicadores e' o
# workspace completo acima (render_macro, personalizacao preservada);
# as demais subabas reaproveitam os MESMOS paineis, sem coleta nova.
# ============================================================

def setores_sensiveis_a_juros() -> list:
    """Setores cujo texto editorial fixo (data/radar_setorial.CATALOGO,
    o mesmo do Morning Call) cita juros/Selic como fator - a relacao vem
    de um texto ja' revisado, nao e' inferida na hora."""
    from data.radar_setorial import CATALOGO

    termos = ("juros", "selic", "copom")
    return [setor for setor, cfg in CATALOGO.items()
            if any(t in (cfg.get("importa", "") + " " + cfg.get("acompanhar", "")).lower() for t in termos)]


def render_macro_juros(prefs):
    from ui.setores_tab import ir_para_setor

    with st.container(border=True):
        _painel_selic_cdi(prefs)
    with st.container(border=True):
        _painel_curva_pre(prefs)
    with st.container(border=True):
        _painel_expectativas(prefs)
    sensiveis = setores_sensiveis_a_juros()
    if sensiveis:
        st.markdown(
            "<div class='cinza' style='font-size:0.7rem; margin:0.2rem 0;'>Setores cujo texto editorial cita "
            "juros/Selic como fator (interpretação do catálogo setorial, não correlação calculada):</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(min(len(sensiveis), 5))
        for i, setor in enumerate(sensiveis):
            with cols[i % len(cols)]:
                st.button(f"{setor} ↗", key=f"macro_juros_setor_{i}", on_click=ir_para_setor, args=(setor,),
                          width="stretch", help="Abrir em SETORES › Visão por Setor")


def render_macro_cambio_commodities(prefs):
    """Dolar e moedas vem do letreiro/MERCADO; aqui o painel de
    commodities/Treasuries/VIX (config.CENARIO_GLOBAL) + dolar do
    proprio ticker tape (config.INDICES_TICKER_TAPE), mesma fonte."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CÂMBIO</div>', unsafe_allow_html=True)
        cambio = {nome: simbolo for nome, simbolo in config.INDICES_TICKER_TAPE.items() if simbolo.endswith("=X")}
        partes = []
        for nome, simbolo in cambio.items():
            cot = _cotacao_cambio(nome, simbolo)
            if cot.get("erro"):
                partes.append(f"<div style='min-width:9rem;'><span class='cinza' style='font-size:0.7rem;'>{nome}</span><br>"
                              f"<span class='cinza'>indisponível</span></div>")
                continue
            em_cache = rotulo_cotacao_em_cache(cot)
            cls = "cinza" if em_cache else ("alta" if cot["variacao_pct"] >= 0 else "baixa")
            partes.append(
                f"<div style='min-width:9rem;'><span class='cinza' style='font-size:0.7rem;'>{nome}</span><br>"
                f"<span class='neutro' style='font-size:0.85rem;'>{_fmt(cot['preco'], 4, prefs)}</span> "
                f"<span class='{cls}' style='font-size:0.78rem;'>{_fmt_pct(cot['variacao_pct'], prefs)}</span>"
                + (f"<br><span class='cinza' style='font-size:0.6rem;'>{em_cache}</span>" if em_cache else "")
                + "</div>"
            )
        if partes:
            st.markdown("<div style='display:flex; flex-wrap:wrap; gap:1rem;'>" + "".join(partes) + "</div>",
                        unsafe_allow_html=True)
            st.caption("Fonte: Yahoo Finance — cotação com atraso típico de mercado.")
    with st.container(border=True):
        _painel_cenario_global(prefs)


@st.cache_data(ttl=60, show_spinner=False)
def _cotacao_cambio(nome, simbolo):
    # data/prices.py:obter_cotacao_indice ja tem cache proprio (ttl=30,
    # achado/corrigido na auditoria de performance 2026-10-23) - este
    # wrapper com ttl=60 continua aqui so' pra nao mudar o ritmo de
    # atualizacao desta subaba especifica, nao por falta de cache na fonte.
    from data.prices import obter_cotacao_indice

    return obter_cotacao_indice(nome, simbolo)


@st.cache_data(ttl=1800, show_spinner=False)
def _copom_vigente():
    # obter_selic_meta_copom nao tem cache proprio (e' plano B do job do
    # Morning Call, roda 1x/dia la') - aqui a tela pode rerodar muito
    return obter_selic_meta_copom()


def _painel_expectativas(prefs):
    """Focus (expectativa, NAO dado realizado) - separado do realizado de
    proposito, com data de calculo e numero de respondentes."""
    st.markdown('<div class="painel-titulo">EXPECTATIVAS DE MERCADO (FOCUS/BC)</div>', unsafe_allow_html=True)
    linhas = []
    data_calculo = None
    for nome, df in (("IPCA", obter_focus_ipca()), ("Selic (fim de ano)", obter_focus_selic())):
        if df is None or df.empty:
            linhas.append(f"<tr><td style='text-align:left;' class='neutro'>{nome}</td>"
                          f"<td colspan='3' class='cinza'>indisponível no momento</td></tr>")
            continue
        data_calculo = data_calculo or df["data_calculo"].iloc[0]
        for _, r in df.iterrows():
            linhas.append(
                f"<tr><td style='text-align:left;' class='neutro'>{nome} {int(r['ano_referencia'])}</td>"
                f"<td class='neutro'>{_fmt(r['mediana_pct'], 2, prefs)}%</td>"
                f"<td class='cinza'>{_fmt(r['media_pct'], 2, prefs)}%</td>"
                f"<td class='cinza'>{int(r['numero_respondentes'])}</td></tr>"
            )
    st.markdown(
        "<div style='overflow-x:auto; overflow-y:hidden;'><table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr><th style='text-align:left; font-weight:400;' class='cinza'>PROJEÇÃO</th>"
        "<th class='cinza'>MEDIANA</th><th class='cinza'>MÉDIA</th><th class='cinza'>RESPONDENTES</th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "PROJEÇÃO, não dado realizado — Boletim Focus (Banco Central)"
        + (f", calculado em {_fmt_data(data_calculo)}." if data_calculo is not None else ".")
    )


def render_macro_calendario(prefs):
    """Calendario economico: o PREGAO ainda NAO tem fonte de agenda de
    divulgacoes (IBGE/BC/Fed) - mostra o que existe de verdade (ultima
    decisao do Copom, datas de referencia de cada serie, projecoes Focus)
    e declara o resto como indisponivel, sem inventar datas."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">ÚLTIMA DECISÃO DO COPOM (REALIZADO)</div>', unsafe_allow_html=True)
        copom = _copom_vigente()
        if copom is None:
            # motivo tecnico (excecao crua) fica no log/SAUDE DOS DADOS, nao na tela
            st.markdown(
                "<div class='cinza' style='font-size:0.78rem;'>Indisponível no momento: o histórico de "
                "decisões do Copom (bcb.gov.br) não respondeu. Nenhum valor anterior é exibido como atual.</div>",
                unsafe_allow_html=True,
            )
        else:
            reuniao = f"{copom['reuniao']}ª reunião · " if copom.get("reuniao") else ""
            st.markdown(
                f"<div style='font-size:1.05rem; font-weight:600; color:var(--destaque);'>"
                f"Meta Selic {_fmt(copom['valor'], 2, prefs)}% a.a.</div>"
                f"<div class='cinza' style='font-size:0.7rem;'>{reuniao}vigente desde "
                f"{copom['vigente_desde'].strftime('%d/%m/%Y')} · fonte: histórico de taxas do Copom (bcb.gov.br)</div>",
                unsafe_allow_html=True,
            )
    with st.container(border=True):
        _painel_expectativas(prefs)
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">PRÓXIMAS DIVULGAÇÕES</div>', unsafe_allow_html=True)
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Agenda de divulgações (IPCA, PIB, payroll, "
            "decisões futuras do Copom/Fed) <b>indisponível</b>: o PREGÃO ainda não tem uma fonte confiável "
            "integrada para datas de divulgação — nenhuma data é estimada aqui. Resultados corporativos "
            "ficam em MERCADO › Agenda.</div>",
            unsafe_allow_html=True,
        )
