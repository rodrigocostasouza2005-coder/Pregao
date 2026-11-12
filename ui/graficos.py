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

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from data.prices import dias_sem_pregao, obter_historico, obter_historico_intraday
from ui import design_system


def _rgba(cor_hex: str, alfa: float) -> str:
    """'#RRGGBB' -> 'rgba(r,g,b,alfa)' (grade/etiquetas translucidas que
    acompanham o tema escolhido, sem cor fixa)."""
    c = cor_hex.lstrip("#")
    if len(c) != 6:
        return cor_hex
    return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{alfa})"


# === Indicadores técnicos (RSI/MACD/Bandas de Bollinger) ===================
#
# Calculados aqui (não em data/prices.py) de propósito: dependem só da
# coluna "Close" que obter_historico/obter_historico_intraday já devolvem
# (mesmo df usado pro candle/linha/volume/MM) - nenhuma requisição nova,
# nenhum dado novo buscado. São funções puras (só pandas, zero st.*) pra
# poderem ter teste unitário determinístico sem precisar de uma sessão
# Streamlit real (ver tests/test_graficos.py).

def calcular_rsi(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    """RSI (Índice de Força Relativa) de Wilder sobre o fechamento (Close).
    A suavização clássica de Wilder é matematicamente equivalente a uma
    média móvel exponencial com alfa=1/periodo (adjust=False) - é o que
    `.ewm(alpha=1/periodo, adjust=False)` calcula abaixo, sem precisar
    reimplementar a recursão à mão.

    Casos de borda (sem eles o RSI teria 0/0 = NaN espalhado pela série):
    - só ganhos na janela (nenhuma perda) -> RSI = 100 (força máxima);
    - nenhum movimento na janela (ganho E perda = 0) -> RSI = 50 (neutro,
      não "máxima força" nem "mínima força")."""
    delta = df["Close"].diff()
    ganho = delta.clip(lower=0)
    perda = -delta.clip(upper=0)
    media_ganho = ganho.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()
    media_perda = perda.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()

    sem_perda = media_perda == 0
    rs = media_ganho / media_perda.where(~sem_perda, other=pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.astype(float)
    rsi = rsi.where(~sem_perda, 100.0)
    rsi = rsi.where(~(sem_perda & (media_ganho == 0)), 50.0)
    return rsi


def calcular_macd(df: pd.DataFrame, rapida: int = 12, lenta: int = 26, sinal: int = 9) -> pd.DataFrame:
    """MACD clássico (12/26/9): EMA rápida - EMA lenta = linha MACD; EMA da
    própria linha MACD = linha de sinal; MACD - sinal = histograma."""
    ema_rapida = df["Close"].ewm(span=rapida, adjust=False).mean()
    ema_lenta = df["Close"].ewm(span=lenta, adjust=False).mean()
    macd = ema_rapida - ema_lenta
    linha_sinal = macd.ewm(span=sinal, adjust=False).mean()
    return pd.DataFrame({"MACD": macd, "MACD_SINAL": linha_sinal, "MACD_HIST": macd - linha_sinal})


def calcular_bollinger(df: pd.DataFrame, periodo: int = 20, n_desvios: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger: média móvel simples +/- N desvios-padrão
    (população, ddof=0 - mesmo critério do indicador clássico de Bollinger,
    não a amostra) do próprio fechamento, na janela `periodo`."""
    media = df["Close"].rolling(window=periodo).mean()
    desvio = df["Close"].rolling(window=periodo).std(ddof=0)
    return pd.DataFrame({
        "BB_MEDIA": media,
        "BB_SUPERIOR": media + n_desvios * desvio,
        "BB_INFERIOR": media - n_desvios * desvio,
    })


def estilo_terminal(fig, tema: dict, altura: int, legenda: bool = True, serie_temporal: bool = True) -> None:
    """Estilo unico dos graficos Plotly do app (terminal financeiro):
    grade pontilhada quase invisivel, sem linhas de eixo pesadas, eixo de
    preco a DIREITA (como nos terminais), mira (crosshair) com hover
    unificado e tipografia mono pequena. `serie_temporal=False` (barras
    horizontais com nomes no eixo Y): mantem o eixo a esquerda, sem mira. Antes eram 3 copias de
    _layout_grafico_escuro (preco, macro, mercado) com o tema padrao do
    plotly_dark - grade cheia, eixo a esquerda, sem mira. Acompanha o tema
    escolhido (cores vem de `tema`)."""
    grade = _rgba(tema["borda"], 0.55)
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=10), height=altura,
        xaxis_rangeslider_visible=False,
        margin=dict(l=6, r=6, t=8, b=6), hovermode="x unified" if serie_temporal else "closest", showlegend=legenda,
        hoverlabel=dict(bgcolor=tema["painel"], bordercolor=tema["borda"],
                        font=dict(family="IBM Plex Mono", size=11, color=tema["neutro"])),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=10)),
    )
    fig.update_xaxes(
        showgrid=False, showline=True, linecolor=tema["borda"], ticks="outside", tickcolor=tema["borda"],
        ticklen=3, showspikes=serie_temporal, spikemode="across", spikethickness=1, spikecolor=tema["cinza"],
        spikedash="dot", spikesnap="cursor",
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=grade, griddash="dot", gridwidth=1, zeroline=False, showline=False,
        side="right" if serie_temporal else "left", showspikes=serie_temporal, spikemode="across",
        spikethickness=1, spikecolor=tema["cinza"], spikedash="dot", spikesnap="cursor",
    )


def marcar_ultimo(fig, valor: float, texto: str, cor: str, fundo: str, linha: int = 1) -> None:
    """Etiqueta do ultimo valor presa ao eixo direito + linha pontilhada
    (padrao de terminal): o numero que importa fica sempre visivel, sem
    precisar passar o mouse."""
    fig.add_hline(y=valor, line_dash="dot", line_width=1, line_color=_rgba(cor, 0.6), row=linha, col=1)
    fig.add_annotation(
        x=1, xref="x domain" if linha == 1 else "paper", y=valor, yref="y" if linha == 1 else "y",
        text=f"<b>{texto}\u00a0</b>", showarrow=False, xanchor="left", xshift=3, align="left",
        font=dict(color=fundo, size=10, family="IBM Plex Mono"), bgcolor=cor, borderpad=2,
        row=linha, col=1,
    )


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
    dois explicitamente).

    Indicadores técnicos (RSI/MACD/Bandas de Bollinger, 2026-11-11):
    disponíveis em QUALQUER chamador, sem flag nova - é um controle
    inline do próprio gráfico (`st.pills`, efeito imediato), não um
    parâmetro de configuração de tela. Desligados por padrão (nenhum
    dos três aparece sem o usuário escolher) - não existia nenhum
    indicador real além das médias móveis antes disso."""
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
        # legenda so' quando ha mais de uma serie que o usuario escolhe ver (MMs)
        estilo_terminal(fig, tema, altura, legenda=permitir_mm)

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

    # Indicadores técnicos (RSI/MACD/Bandas de Bollinger) - controle inline,
    # efeito imediato (pedido explícito do Rodrigo: ajuste no próprio
    # elemento, nunca num formulário à parte), todos DESLIGADOS por padrão
    # pra não poluir o gráfico de quem só quer ver preço/volume. `st.pills`
    # (mesmo widget já usado pro filtro de SETOR em ui/mercado_tab.py) em
    # vez de 3 checkboxes separadas - mais compacto numa única linha.
    sel_indicadores = st.pills(
        "Indicadores técnicos", ["BANDAS DE BOLLINGER", "RSI", "MACD"], selection_mode="multi",
        default=[], label_visibility="collapsed", key=f"{key_prefix}_indicadores",
    ) or []
    # len(df) >= 5 (não 0): com poucas barras (ex: início de um papel recém-
    # listado) um indicador de janela 14/20/26 períodos não tem dado
    # suficiente pra dizer nada - mostrar a linha vazia só confundiria.
    dado_suficiente = len(df) >= 5
    mostrar_boll = "BANDAS DE BOLLINGER" in sel_indicadores and dado_suficiente
    mostrar_rsi = "RSI" in sel_indicadores and dado_suficiente
    mostrar_macd = "MACD" in sel_indicadores and dado_suficiente

    tem_ohlc = {"Open", "High", "Low"}.issubset(df.columns) and df[["Open", "High", "Low"]].notna().all(axis=None)
    tipo_grafico = prefs.get("grafico_tipo", "LINHA")
    if tipo_grafico == "CANDLE" and not tem_ohlc:
        tipo_grafico = "LINHA"

    tem_volume = "Volume" in df.columns and df["Volume"].notna().any()

    # Estrutura de subplots MONTADA DINAMICAMENTE: preço sempre na linha 1;
    # volume/RSI/MACD entram como linhas extras só quando aplicável. Sem
    # nenhum indicador de subplot ligado, isto reproduz EXATAMENTE o layout
    # de antes (1 ou 2 linhas, 0.75/0.25) - mudança aditiva, zero regressão
    # pros callers que não tocam nos novos controles (EQUITY/VISÃO GERAL).
    linhas = ["preco"]
    alturas_px = {"preco": altura * 0.75 if tem_volume else altura}
    if tem_volume:
        linhas.append("volume")
        alturas_px["volume"] = altura * 0.25
    if mostrar_rsi:
        linhas.append("rsi")
        alturas_px["rsi"] = 90.0
    if mostrar_macd:
        linhas.append("macd")
        alturas_px["macd"] = 110.0

    altura_total = sum(alturas_px.values())
    row_heights = [alturas_px[nome] / altura_total for nome in linhas]
    row_idx = {nome: i + 1 for i, nome in enumerate(linhas)}
    row_preco = row_idx["preco"]

    fig = make_subplots(
        rows=len(linhas), cols=1, shared_xaxes=True, row_heights=row_heights, vertical_spacing=0.045,
    )

    if tipo_grafico == "CANDLE":
        fig.add_trace(
            go.Candlestick(
                x=df["Data"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name=ticker,
                increasing_line_color=tema["alta"], decreasing_line_color=tema["baixa"],
            ),
            row=row_preco, col=1,
        )
    elif tipo_grafico == "AREA":
        fig.add_trace(
            go.Scatter(x=df["Data"], y=df["Close"], name=ticker, fill="tozeroy",
                       line=dict(color=tema["destaque"], width=1.5)),
            row=row_preco, col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(x=df["Data"], y=df["Close"], name=ticker, line=dict(color=tema["destaque"], width=1.5)),
            row=row_preco, col=1,
        )

    if mostrar_boll:
        bb = calcular_bollinger(df)
        if bb["BB_SUPERIOR"].notna().any():
            cor_banda = _rgba(tema["cinza"], 0.75)
            # ordem importa: SUPERIOR primeiro (sem fill), INFERIOR depois
            # com fill="tonexty" - preenche a área ENTRE as duas (semântica
            # do Plotly: tonexty fecha contra a trace anterior no mesmo
            # eixo). MÉDIA por último, sem fill, só a linha pontilhada.
            fig.add_trace(go.Scatter(x=df["Data"], y=bb["BB_SUPERIOR"], name="BB SUPERIOR", showlegend=False,
                                      line=dict(color=cor_banda, width=1, dash="dot")), row=row_preco, col=1)
            fig.add_trace(go.Scatter(x=df["Data"], y=bb["BB_INFERIOR"], name="BANDAS DE BOLLINGER",
                                      line=dict(color=cor_banda, width=1, dash="dot"),
                                      fill="tonexty", fillcolor=_rgba(tema["cinza"], 0.08)), row=row_preco, col=1)
            fig.add_trace(go.Scatter(x=df["Data"], y=bb["BB_MEDIA"], name="BB MÉDIA", showlegend=False,
                                      line=dict(color=_rgba(tema["destaque"], 0.55), width=1, dash="dash")),
                          row=row_preco, col=1)

    if permitir_mm:
        sufixo_mm = ""
        if eh_intraday:
            sufixo_mm = " (5 min)" if periodo == "1D" else " (30 min)"
        cor_mm20 = tema["neutro"] if tipo_grafico in ("LINHA", "AREA") else tema["destaque"]
        if prefs.get("mm20") and "MM20" in df.columns and df["MM20"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM20"], name=f"MM20{sufixo_mm}",
                                      line=dict(color=cor_mm20, width=1)), row=row_preco, col=1)
        if prefs.get("mm50") and "MM50" in df.columns and df["MM50"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM50"], name=f"MM50{sufixo_mm}",
                                      line=dict(color=tema["ciano"], width=1)), row=row_preco, col=1)
        if prefs.get("mm200") and "MM200" in df.columns and df["MM200"].notna().any():
            fig.add_trace(go.Scatter(x=df["Data"], y=df["MM200"], name=f"MM200{sufixo_mm}",
                                      line=dict(color=tema["cinza"], width=1)), row=row_preco, col=1)

    if tem_volume:
        if tem_ohlc:
            cores_volume = [tema["alta"] if c >= o else tema["baixa"] for o, c in zip(df["Open"], df["Close"])]
        else:
            cores_volume = tema["destaque"]
        fig.add_trace(
            go.Bar(x=df["Data"], y=df["Volume"], name="Volume", marker_color=cores_volume, opacity=0.6),
            row=row_idx["volume"], col=1,
        )

    if mostrar_rsi:
        rsi = calcular_rsi(df)
        if rsi.notna().any():
            row_rsi = row_idx["rsi"]
            fig.add_trace(go.Scatter(x=df["Data"], y=rsi, name="RSI", line=dict(color=tema["destaque"], width=1.2)),
                          row=row_rsi, col=1)
            fig.add_hline(y=70, line_dash="dot", line_width=1, line_color=_rgba(tema["baixa"], 0.45),
                          row=row_rsi, col=1)
            fig.add_hline(y=30, line_dash="dot", line_width=1, line_color=_rgba(tema["alta"], 0.45),
                          row=row_rsi, col=1)
            fig.update_yaxes(range=[0, 100], title=dict(text="RSI", font=dict(size=9)), row=row_rsi, col=1)

    if mostrar_macd:
        macd_df = calcular_macd(df)
        if macd_df["MACD"].notna().any():
            row_macd = row_idx["macd"]
            cores_hist = [tema["alta"] if v >= 0 else tema["baixa"] for v in macd_df["MACD_HIST"].fillna(0)]
            fig.add_trace(go.Bar(x=df["Data"], y=macd_df["MACD_HIST"], name="HISTOGRAMA MACD",
                                  marker_color=cores_hist, opacity=0.5), row=row_macd, col=1)
            fig.add_trace(go.Scatter(x=df["Data"], y=macd_df["MACD"], name="MACD",
                                      line=dict(color=tema["destaque"], width=1.2)), row=row_macd, col=1)
            fig.add_trace(go.Scatter(x=df["Data"], y=macd_df["MACD_SINAL"], name="SINAL",
                                      line=dict(color=tema["ciano"], width=1.2)), row=row_macd, col=1)
            fig.update_yaxes(title=dict(text="MACD", font=dict(size=9)), row=row_macd, col=1)

    # legenda liga sozinha quando ha' mais de 1 serie pra distinguir (MMs
    # OU qualquer indicador novo ligado) - mesmo criterio de antes, so'
    # estendido aos indicadores novos.
    legenda_grafico = permitir_mm or mostrar_boll or mostrar_rsi or mostrar_macd
    estilo_terminal(fig, tema, altura_total, legenda=legenda_grafico)
    ultimo_preco = float(df["Close"].iloc[-1])
    primeiro_preco = float(df["Close"].iloc[0])
    marcar_ultimo(
        fig, ultimo_preco,
        # sem centavos acima de mil (mesmo critério do eixo): etiqueta curta nunca corta
        config.formatar_numero(ultimo_preco, 0 if abs(ultimo_preco) >= 1000 else 2, prefs.get("formato_numerico")),
        tema["alta"] if ultimo_preco >= primeiro_preco else tema["baixa"], tema["fundo"],
        linha=row_preco,
    )
    fig.update_layout(margin=dict(l=6, r=84, t=8, b=6))

    if eh_intraday:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[17, 10], pattern="hour")])
    else:
        _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
        if intervalo_periodo == "1d":
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=dias_sem_pregao(df))])

    chave_zoom = zoom_key(
        f"{key_prefix}_grafico", ticker, periodo, tipo_grafico, comparar_ibov, mostrar_boll, mostrar_rsi, mostrar_macd,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave_zoom)

    if not mostrar_stats_periodo:
        return

    fmt = prefs.get("formato_numerico")
    abertura = float(df["Close"].iloc[0])
    fechamento = float(df["Close"].iloc[-1])
    maxima = float(df["High"].max()) if tem_ohlc else float(df["Close"].max())
    minima = float(df["Low"].min()) if tem_ohlc else float(df["Close"].min())
    var_periodo = (fechamento - abertura) / abertura * 100 if abertura else None
    # numero_financeiro_html (design_system) em vez do numero formatado +
    # classe na mao - mesma fundacao do design system ja usada no resto do
    # app (ver docstring de ui/design_system.py). ÚLTIMO/MÁXIMA/MÍNIMA
    # continuam sem cor de sinal (nao sao uma variacao, sao um preco em si -
    # mesmo criterio documentado em numero_financeiro_html).
    stats = [
        ("ÚLTIMO", design_system.numero_financeiro_html(fechamento, 2, fmt), None),
        ("MÁXIMA DO PERÍODO", design_system.numero_financeiro_html(maxima, 2, fmt), None),
        ("MÍNIMA DO PERÍODO", design_system.numero_financeiro_html(minima, 2, fmt), None),
    ]
    if var_periodo is not None:
        cls_var = design_system.classe_sinal(var_periodo)
        stats.append((
            "VARIAÇÃO NO PERÍODO",
            design_system.numero_financeiro_html(var_periodo, 2, fmt, sufixo="%", com_sinal=True), cls_var,
        ))
    blocos = [
        f"<div style='margin-right:1.3rem;'><div class='cinza' style='font-size:0.6rem;'>{rot}</div>"
        f"<div class='{cls or 'neutro'}' style='font-size:0.76rem; font-weight:700; margin-top:0.1rem;'>{val}</div></div>"
        for rot, val, cls in stats
    ]
    st.markdown(
        f"<div style='display:flex; flex-wrap:wrap; margin-top:0.5rem; padding-top:0.5rem; "
        f"border-top:1px solid var(--borda);'>{''.join(blocos)}</div>",
        unsafe_allow_html=True,
    )
