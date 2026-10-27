# -*- coding: utf-8 -*-
"""Aba "0 VISÃO GERAL" - home do PREGÃO.

Redesign terminal (2026-10-27, seguindo conceito visual aprovado pelo
Rodrigo, inspirado em terminal Bloomberg): cockpit único e fixo (sem
drag/resize por painel - trade-off aceito explicitamente, ver PR #186) -
leitura do pregão primeiro, depois indicadores, gráfico+investigação,
grade de exploração compacta (altas/baixas, notícias, setorial),
desempenho+agenda, globais+watchlist. Inteligência DISTRIBUÍDA nos
módulos (chips DADO/NOTÍCIA/AGENDA na leitura do pregão, "para
investigar" condensado ao lado do gráfico, flags inline em setorial) em
vez de 4 blocos de texto separados (resumo executivo/movimentos/
oportunidades/cenários) - mesma função de síntese (obter_sintese_mercado,
cache já existente), zero sistema de IA paralelo.

NÃO tem coleta/lógica de dado própria - é composição de funções que já
existem em outras abas (MERCADO, MACRO, NEWS, RESEARCH, AGENDA),
reaproveitadas diretamente (mesmo cache, sem nenhuma consulta nova)."""

import html
from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

import config
from data.eventos import STATUS_LABEL, calcular_calendario_cacheado
from data.ibovespa import obter_composicao_oficial
from data.macro import obter_cdi
from data.mercado import (
    obter_altas_baixas, obter_cotacoes_lote, obter_desempenho_setorial, obter_mais_negociados,
    obter_mercados_globais,
)
from data.news import obter_top_mercado_tudo
from data.prices import (
    obter_cotacao, obter_cotacao_indice, obter_historico, obter_historico_intraday, rotulo_cotacao_em_cache,
)
from data.research import preparar_leitura
from data.sintese_mercado import obter_sintese_mercado
from ui import graficos
from ui.calendario_tab import _painel_proximos_watchlist
from ui.mercado_tab import _painel_globais
from ui.news_tab import (
    _CLASSE_SELO, _fmt_hora, _injetar_css, _plural_fontes, _texto_tag, _tooltip_regras, _truncar,
)
from ui.research_tab import _casas_ativas

_PERIODOS_IBOV = ["1D", "1S", "1M", "3M", "6M", "1A", "5A"]
_QTD_NOTICIAS = 4


def _tema_atual(prefs):
    return config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])


def _fmt_pct(valor, prefs):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{config.formatar_numero(valor, 2, prefs['formato_numerico'])}%"


def _status_cotacao_indice(cotacao: dict) -> str | None:
    """Identifica fallback sem confundir hora da tentativa com hora da coleta valida."""
    return rotulo_cotacao_em_cache(cotacao)


def _tempo_relativo(iso: str | None) -> str:
    """'há Xmin'/'há Xh' a partir de um ISO 8601 (UTC) real - nunca um
    rótulo fixo tipo 'agora': se o parse falhar ou vier vazio, mostra
    'horário indisponível' em vez de inventar um tempo."""
    if not iso:
        return "horário indisponível"
    try:
        dt = datetime.fromisoformat(str(iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta_min = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except (ValueError, TypeError):
        return "horário indisponível"
    if delta_min < 1:
        return "agora mesmo"
    if delta_min < 60:
        return f"há {delta_min}min"
    return f"há {delta_min // 60}h{delta_min % 60:02d}"


def _badge_ticker(ticker: str, tema: dict, tamanho: str = "1.5rem") -> str:
    """Selo compacto com as iniciais do ticker - substituto leve de logo
    de empresa: não existe mecanismo de logo real por ticker no projeto
    hoje (nenhum serviço externo configurado) - gerar um exigiria CDN
    novo ou banco de assets mantido manualmente. CSS puro, derivado do
    próprio ticker, sem imagem inventada."""
    iniciais = ("".join(c for c in ticker if c.isalpha())[:2] or ticker[:2]).upper()
    return (
        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
        f"width:{tamanho}; height:{tamanho}; min-width:{tamanho}; border-radius:3px; "
        f"background:{tema['destaque']}22; color:{tema['destaque']}; "
        f"font-size:0.56rem; font-weight:700; margin-right:0.35rem; vertical-align:middle;'>"
        f"{html.escape(iniciais)}</span>"
    )


# ===================== indicadores essenciais (faixa densa) =====================

def _item_ticker_html(rotulo: str, preco, variacao_pct, casas: int, prefs, status: str | None = None) -> str:
    if preco is None or variacao_pct is None:
        return (
            f"<div style='padding:0.5rem 0.8rem; border-right:1px solid var(--borda); flex:1 1 0; min-width:7rem;'>"
            f"<div class='cinza' style='font-size:0.6rem; letter-spacing:0.04em;'>{rotulo}</div>"
            f"<div class='cinza' style='font-size:0.88rem; font-weight:700; margin-top:0.1rem;'>—</div>"
            f"<div class='cinza' style='font-size:0.64rem; margin-top:0.1rem;'>SEM DADO</div></div>"
        )
    cls = "alta" if variacao_pct >= 0 else "baixa"
    seta = "▲" if variacao_pct >= 0 else "▼"
    status_html = (
        f"<div class='cinza' style='font-size:0.54rem; margin-top:0.1rem;'>{html.escape(status)}</div>"
        if status else ""
    )
    return (
        f"<div style='padding:0.5rem 0.8rem; border-right:1px solid var(--borda); flex:1 1 0; min-width:7rem;'>"
        f"<div class='cinza' style='font-size:0.6rem; letter-spacing:0.04em;'>{rotulo}</div>"
        f"<div class='neutro' style='font-size:0.88rem; font-weight:700; margin-top:0.1rem;'>"
        f"{config.formatar_numero(preco, casas, prefs['formato_numerico'])}</div>"
        f"<div class='{cls}' style='font-size:0.66rem; font-weight:600; margin-top:0.1rem;'>{seta} {_fmt_pct(variacao_pct, prefs)}</div>"
        f"{status_html}</div>"
    )


def _painel_indicadores(prefs):
    """Faixa densa de indicadores essenciais (estilo terminal - rótulo/
    valor/variação empilhados, divisórias finas, sem cards grandes).
    Mesmos dados/funções de sempre (obter_cotacao_indice/obter_cdi/
    obter_mercados_globais/obter_cotacao), zero consulta nova."""
    if not obter_composicao_oficial():
        st.caption(
            f"B3 indisponível no momento - altas/baixas e desempenho setorial usam lista curada de "
            f"fallback ({len(config.IBOVESPA_SETORES)} papéis)."
        )
    globais = {g["nome"]: g for g in obter_mercados_globais()}
    cdi_df = obter_cdi(dias_historico=5)
    cdi_atual = float(cdi_df["cdi_anualizado_pct"].iloc[-1]) if cdi_df is not None and not cdi_df.empty else None
    cdi_variacao = None
    if cdi_df is not None and len(cdi_df) >= 2:
        anterior = float(cdi_df["cdi_anualizado_pct"].iloc[-2])
        cdi_variacao = cdi_atual - anterior if cdi_atual is not None else None

    ibov = obter_cotacao_indice("IBOVESPA", "^BVSP")
    dolar = obter_cotacao_indice("DOLAR", "USDBRL=X")
    petr4 = obter_cotacao("PETR4")
    vale3 = obter_cotacao("VALE3")
    sp500 = globais.get("S&P 500")
    nasdaq = globais.get("Nasdaq")

    blocos = [
        _item_ticker_html("IBOVESPA", None if ibov.get("erro") else ibov["preco"], None if ibov.get("erro") else ibov["variacao_pct"], 0, prefs, _status_cotacao_indice(ibov)),
        _item_ticker_html("DÓLAR", None if dolar.get("erro") else dolar["preco"], None if dolar.get("erro") else dolar["variacao_pct"], 2, prefs, _status_cotacao_indice(dolar)),
        _item_ticker_html("DI (CDI ANUAL.)", cdi_atual, cdi_variacao, 2, prefs),
        _item_ticker_html("S&P 500", sp500["preco"] if sp500 else None, sp500["variacao_pct"] if sp500 else None, 0, prefs),
        _item_ticker_html("NASDAQ", nasdaq["preco"] if nasdaq else None, nasdaq["variacao_pct"] if nasdaq else None, 0, prefs),
        _item_ticker_html("PETR4", None if petr4.get("erro") else petr4["preco"], None if petr4.get("erro") else petr4["variacao_pct"], 2, prefs),
        _item_ticker_html("VALE3", None if vale3.get("erro") else vale3["preco"], None if vale3.get("erro") else vale3["variacao_pct"], 2, prefs),
    ]
    st.markdown(f"<div style='display:flex; flex-wrap:wrap;'>{''.join(blocos)}</div>", unsafe_allow_html=True)


# ===================== leitura do pregão (inteligência, condensada) =====================

def _concentracao_setorial(janela: str = "dia", n: int = 6):
    """DADO real (não interpretação): quantos dos maiores movimentos do
    dia (altas+baixas) pertencem ao mesmo setor - conta direto a partir
    de obter_altas_baixas (campo 'setor' já vem na origem), zero IA,
    zero consulta nova. None se não houver concentração clara (<3)."""
    altas, baixas = obter_altas_baixas(n, janela)
    papeis = altas + baixas
    if not papeis:
        return None
    contagem: dict = {}
    for p in papeis:
        contagem[p["setor"]] = contagem.get(p["setor"], 0) + 1
    setor, qtd = max(contagem.items(), key=lambda kv: kv[1])
    if qtd < 3:
        return None
    return setor, qtd, len(papeis)


def _proximo_evento_watchlist(prefs):
    """Evento mais próximo (resultado confirmado/estimado OU prazo CVM)
    entre os tickers da watchlist - mesma função cacheada já usada pelo
    painel AGENDA (data/eventos.py:calcular_calendario_cacheado)."""
    watchlist = list(prefs.get("watchlist") or [])
    if not watchlist:
        return None
    eventos = calcular_calendario_cacheado(watchlist)
    if not eventos:
        return None
    return min(eventos, key=lambda e: e["data"])


def _chip_html(tipo: str, texto_html: str) -> str:
    cor = {"DADO": "#7fb8ff", "NOTÍCIA": "var(--destaque)", "AGENDA": "var(--cinza)"}.get(tipo, "var(--cinza)")
    return (
        f"<span style='font-size:0.68rem; border:1px solid var(--borda); border-radius:2px; "
        f"padding:0.22rem 0.55rem; display:inline-flex; align-items:center; gap:0.4rem; "
        f"margin:0.15rem 0.35rem 0.15rem 0;'>"
        f"<em style='font-style:normal; font-weight:700; font-size:0.56rem; letter-spacing:0.03em; color:{cor};'>{tipo}</em>"
        f"<span class='neutro'>{texto_html}</span></span>"
    )


def _painel_leitura_pregao(prefs):
    """"LEITURA DO PREGÃO" - inteligência condensada no topo da aba,
    reaproveitando data/sintese_mercado.py (mesmo cache, mesma função já
    usada pelos antigos painéis RESUMO EXECUTIVO/O QUE ESTÁ MOVENDO O
    MERCADO - essa UI parou de existir como 4 blocos separados, viraram
    chips tipados aqui + versão condensada em _painel_para_investigar,
    ver docstring do módulo). Fatos (DADO/AGENDA) vêm DIRETO dos dados,
    funcionam mesmo se a síntese por IA estiver indisponível - nunca
    degrada silenciosamente."""
    st.markdown(
        '<div class="painel-titulo" style="color:var(--destaque);">LEITURA DO PREGÃO</div>',
        unsafe_allow_html=True,
    )
    resultado = obter_sintese_mercado()

    chips = []
    concentracao = _concentracao_setorial()
    if concentracao:
        setor, qtd, total = concentracao
        chips.append(_chip_html("DADO", f"<b>{html.escape(setor)}</b> concentra {qtd} dos {total} maiores movimentos do dia"))

    negociados = obter_mais_negociados(1)
    if negociados:
        p = negociados[0]
        vol_mi = config.formatar_numero(p["volume_financeiro"] / 1_000_000, 0, prefs["formato_numerico"])
        chips.append(_chip_html("DADO", f"Maior volume financeiro do dia: <b>{p['ticker']}</b> (R$ {vol_mi} mi)"))

    evento = _proximo_evento_watchlist(prefs)
    if evento:
        rotulo_status = STATUS_LABEL.get(evento["status"], evento["status"])
        chips.append(_chip_html(
            "AGENDA",
            f"<b>{html.escape(evento['ticker'])}</b> — {html.escape(rotulo_status)} em {evento['data'].strftime('%d/%m')}",
        ))

    headline = None
    if resultado.get("ok"):
        movimentos = resultado["dados"].get("movimentos") or []
        if movimentos:
            m = movimentos[0]
            fonte = html.escape(m.get("fonte") or "fonte não informada")
            chips.append(_chip_html("NOTÍCIA", f"{html.escape(m.get('evento') or '')} <span class='cinza'>— {fonte}</span>"))
        headline = resultado["dados"]["resumo_executivo"]["texto"]
        rotulo_tempo = _tempo_relativo(resultado.get("gerado_em"))
        meta = f"atualizado {rotulo_tempo}" + ("" if resultado.get("atual") else " · análise anterior, rodada atual indisponível")
    else:
        meta = f"síntese por IA indisponível no momento ({resultado.get('motivo') or 'sem detalhe'}) - fatos abaixo vêm direto dos dados"

    st.markdown(f"<div class='cinza' style='font-size:0.62rem; margin-bottom:0.3rem;'>{meta}</div>", unsafe_allow_html=True)
    if headline:
        st.markdown(
            f"<div style='font-size:0.86rem; font-weight:600; margin-bottom:0.5rem; line-height:1.4; max-width:92ch;'>{headline}</div>",
            unsafe_allow_html=True,
        )
    if not chips:
        st.markdown("<div class='cinza' style='font-size:0.76rem;'>Sem fatos com evidência suficiente nesta rodada.</div>", unsafe_allow_html=True)
        return
    st.markdown("".join(chips), unsafe_allow_html=True)


def _painel_para_investigar(prefs):
    """Versão CONDENSADA de "oportunidades/riscos" + cenário principal
    (antes 2 painéis grandes separados: PARA INVESTIGAR e CENÁRIOS E O
    QUE OBSERVAR) - mesma função de dado (obter_sintese_mercado, mesmo
    cache), só os 2 itens mais relevantes em vez da lista completa.
    Nunca recomendação de compra/venda nem preço-alvo."""
    st.markdown('<div class="painel-titulo">PARA INVESTIGAR</div>', unsafe_allow_html=True)
    resultado = obter_sintese_mercado()
    if not resultado.get("ok"):
        st.markdown("<div class='cinza' style='font-size:0.76rem;'>Sem leitura analítica disponível no momento.</div>", unsafe_allow_html=True)
        return
    dados = resultado["dados"]
    itens = (dados.get("oportunidades_riscos") or [])[:2]
    cenarios = dados.get("cenarios") or []
    principal = next((c for c in cenarios if c.get("tipo") == "principal"), None)

    blocos = []
    for item in itens:
        blocos.append(
            f"<div style='padding:0.4rem 0; border-bottom:1px solid var(--borda);'>"
            f"<div class='cinza' style='font-size:0.58rem; font-weight:700; letter-spacing:0.03em;'>A FAVOR · CONTRA</div>"
            f"<div style='font-size:0.78rem; font-weight:600; margin-top:0.1rem;'>{html.escape(item.get('ativo_ou_setor') or '')}</div>"
            f"<div class='cinza' style='font-size:0.68rem; margin-top:0.15rem;'>"
            f"<span class='alta'>A favor:</span> {html.escape(item.get('argumento_favoravel') or '—')}</div>"
            f"<div class='cinza' style='font-size:0.68rem;'>"
            f"<span class='baixa'>Contra:</span> {html.escape(item.get('argumento_contrario') or '—')}</div></div>"
        )
    if principal:
        sinalizador = (
            f"<div class='cinza' style='font-size:0.64rem; margin-top:0.1rem;'>Sinalizador: {html.escape(principal['sinalizadores'])}</div>"
            if principal.get("sinalizadores") else ""
        )
        blocos.append(
            f"<div style='padding:0.4rem 0;'>"
            f"<div class='alta' style='font-size:0.58rem; font-weight:700; letter-spacing:0.03em;'>CENÁRIO PRINCIPAL</div>"
            f"<div style='font-size:0.78rem; font-weight:600; margin-top:0.1rem;'>{html.escape(principal.get('cenario') or '')}</div>"
            f"{sinalizador}</div>"
        )
    if not blocos:
        st.markdown("<div class='cinza' style='font-size:0.76rem;'>Nada com evidência suficiente para destacar nesta rodada.</div>", unsafe_allow_html=True)
        return
    st.markdown("".join(blocos), unsafe_allow_html=True)
    st.markdown(
        "<div class='cinza' style='font-size:0.58rem; margin-top:0.3rem;'>Não é recomendação de compra/venda - "
        "sem preço-alvo nem indicação de operação.</div>",
        unsafe_allow_html=True,
    )


def _painel_ibov_grafico(prefs):
    st.markdown('<div class="painel-titulo">IBOVESPA</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)

    padrao = st.session_state.get("vg_periodo_ibov_valido", "6M")
    if padrao not in _PERIODOS_IBOV:
        padrao = "6M"
    sel = st.segmented_control(
        "Período", _PERIODOS_IBOV, default=padrao, label_visibility="collapsed", key="vg_periodo_ibov",
    )
    periodo = sel or padrao
    st.session_state["vg_periodo_ibov_valido"] = periodo

    # causa raiz real (2026-10-08): _PERIODOS_IBOV inclui "1D"/"1S", mas so'
    # PERIODOS_GRAFICO (periodos diarios/semanais) tem esses rotulos - os
    # intradiarios sao' outra tabela (PERIODOS_INTRADIARIOS / obter_historico_
    # intraday), igual ja' tratado no grafico de MERCADO (app.py). Sem esse
    # branch, selecionar "1D"/"1S" aqui ia pra obter_historico() e estourava
    # KeyError em PERIODOS_GRAFICO[periodo_label] (data/prices.py).
    if periodo in config.PERIODOS_INTRADIARIOS:
        df = obter_historico_intraday(config.SIMBOLO_IBOVESPA, periodo)
    else:
        df = obter_historico(config.SIMBOLO_IBOVESPA, periodo)
    if df is None or df.empty:
        st.warning("Não foi possível obter o histórico do Ibovespa.")
        return

    fig = go.Figure(go.Scatter(
        x=df["Data"], y=df["Close"], mode="lines",
        line=dict(color=tema["destaque"], width=1.8), fill="tozeroy",
        fillcolor=tema["destaque"] + "18",
    ))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
        height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
    )
    # tema["borda"] (nao "#1A1A1A" fixo, achado da auditoria visual
    # 2026-10-16): acompanha o tema CLARO tambem, nao so' os temas escuros.
    fig.update_xaxes(gridcolor=tema["borda"])
    fig.update_yaxes(gridcolor=tema["borda"])
    chave = graficos.zoom_key("vg_ibov", periodo)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)

    # estatisticas do periodo (NOVO, redesign terminal): reaproveita o
    # MESMO df ja' buscado pro grafico acima - zero consulta nova.
    if not df.empty:
        abertura = float(df["Close"].iloc[0])
        maxima = float(df["Close"].max())
        minima = float(df["Close"].min())
        var_periodo = (float(df["Close"].iloc[-1]) - abertura) / abertura * 100 if abertura else None
        cls_var = "alta" if (var_periodo or 0) >= 0 else "baixa"
        stats = [
            ("INÍCIO DO PERÍODO", config.formatar_numero(abertura, 0, prefs["formato_numerico"]), "neutro"),
            ("MÁXIMA", config.formatar_numero(maxima, 0, prefs["formato_numerico"]), "neutro"),
            ("MÍNIMA", config.formatar_numero(minima, 0, prefs["formato_numerico"]), "neutro"),
        ]
        if var_periodo is not None:
            stats.append(("VARIAÇÃO NO PERÍODO", _fmt_pct(var_periodo, prefs), cls_var))
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


# ===================== grade de exploração =====================

def _painel_altas_baixas_resumo(prefs):
    """Versão compacta de "Maiores altas/baixas" - 2 colunas lado a lado
    (altas | baixas), top 4 do dia, com barra de magnitude (proporcional
    à maior variação do próprio grupo). Sem filtros/controles (esses
    ficam na versão completa, MERCADO › PAINEL). Mesma função de dado
    (data/mercado.py:obter_altas_baixas), zero consulta nova."""
    st.markdown('<div class="painel-titulo">PRINCIPAIS ALTAS E BAIXAS</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)
    altas, baixas = obter_altas_baixas(4, "dia")

    def _coluna(titulo, papeis, cls):
        st.markdown(f"<div class='{cls}' style='font-size:0.68rem; font-weight:700; margin-bottom:0.25rem;'>{titulo}</div>", unsafe_allow_html=True)
        if not papeis:
            st.markdown("<div class='cinza' style='font-size:0.74rem;'>—</div>", unsafe_allow_html=True)
            return
        maior = max(abs(p["variacao_pct"]) for p in papeis) or 1.0
        cor = tema["alta"] if cls == "alta" else tema["baixa"]
        linhas = []
        for p in papeis:
            largura = max(8, round(abs(p["variacao_pct"]) / maior * 100))
            linhas.append(
                f"<div style='padding:0.16rem 0; white-space:nowrap;'>"
                f"{_badge_ticker(p['ticker'], tema, '1.3rem')}"
                f"<span style='font-weight:600; font-size:0.72rem;'>{p['ticker']}</span>"
                f"<span class='{cls}' style='float:right; font-size:0.72rem;'>{_fmt_pct(p['variacao_pct'], prefs)}</span>"
                f"<div style='height:2px; background:var(--borda); margin-top:0.2rem;'>"
                f"<div style='height:100%; width:{largura}%; background:{cor};'></div></div></div>"
            )
        st.markdown("".join(linhas), unsafe_allow_html=True)

    with st.container(key="vg_altas_baixas_resumo_cols"):
        col_altas, col_baixas = st.columns(2, gap="small")
        with col_altas:
            _coluna("ALTAS", altas, "alta")
        with col_baixas:
            _coluna("BAIXAS", baixas, "baixa")


def _painel_noticias_resumo(prefs):
    """Renderer PRÓPRIO (não `ui.news_tab._renderizar_lista`, que é "wire
    denso" pensado pra largura cheia de TOP MERCADO/EQUITY) - achado real
    (redesign em grade, 2026-10-27): `_renderizar_lista` usa `st.columns`
    com pesos fixos pra selo/hora/manchete/fontes/link; numa coluna
    estreita essas colunas espremiam a ponto do selo (badge) sobrepor o
    início da manchete - texto ilegível. Esta versão é 1 bloco HTML
    empilhado por item (sem múltiplas colunas), mesma função de dado
    (obter_top_mercado_tudo) e mesmos campos/selo já usados lá - zero
    dado novo, só layout diferente pra caber estreito."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">DESTAQUES DO DIA <span class="cinza" style="font-size:0.68rem;font-weight:400;">ÚLTIMAS 4</span></div>', unsafe_allow_html=True)
    itens = obter_top_mercado_tudo("TODOS")
    if not itens:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Sem notícias disponíveis.</div>", unsafe_allow_html=True)
        return
    # A visão geral é um resumo executivo, não o feed completo: quatro manchetes
    # no máximo, sem texto longo nem contexto extra. O feed completo fica em NEWS.
    blocos = []
    for n in itens[:_QTD_NOTICIAS]:
        classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
        tooltip = html.escape(_tooltip_regras(n))
        titulo = html.escape(_truncar(n["titulo"], 68))
        blocos.append(
            f"<div style='padding:0.4rem 0; border-bottom:1px solid var(--borda);'>"
            f"<span class='selo-tag {classe_selo}' title='{tooltip}' style='font-size:0.58rem;'>"
            f"{_texto_tag(n)}</span>"
            f"<a href='{n['link']}' target='_blank' style='display:block; margin-top:0.25rem; "
            f"font-size:0.76rem; font-weight:600; color:var(--neutro); text-decoration:none; "
            f"line-height:1.3;'>{titulo}</a>"
            f"<div class='cinza' style='font-size:0.64rem; margin-top:0.15rem;'>"
            f"{_fmt_hora(n['data'])} · {_plural_fontes(n['fontes_count'])}</div></div>"
        )
    st.markdown("".join(blocos), unsafe_allow_html=True)


def _painel_mapa_setorial_compacto(prefs):
    """"Mapa setorial" compacto - grade de blocos coloridos (6 setores),
    NÃO o treemap completo de MERCADO › PAINEL (que segue intocado) -
    aqui é um painel secundário, não o protagonista da tela. Flag de
    "maior dispersão" calculada sobre a lista COMPLETA de setores (não
    só os 6 exibidos) - mesma função de dado (obter_desempenho_setorial),
    zero consulta nova."""
    st.markdown('<div class="painel-titulo">MAPA SETORIAL</div>', unsafe_allow_html=True)
    setores = obter_desempenho_setorial("dia")
    if not setores:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    tema = _tema_atual(prefs)
    blocos = []
    # 6 (nao todos) em grade 2 por linha: coluna estreita, secundario de
    # proposito - metade dos setores, nao todos.
    for s in setores[:6]:
        v = s["variacao_media_pct"]
        cor = tema["alta"] if v >= 0 else tema["baixa"]
        blocos.append(
            f"<div style='flex:1 1 44%; min-width:6rem; border:1px solid {cor}55; "
            f"background:{cor}1c; border-radius:3px; padding:0.35rem 0.45rem;'>"
            f"<div class='neutro' style='font-size:0.62rem; font-weight:600; white-space:nowrap; "
            f"overflow:hidden; text-overflow:ellipsis;'>{html.escape(s['setor'])}</div>"
            f"<div style='color:{cor}; font-size:0.76rem; font-weight:700; margin-top:0.1rem;'>"
            f"{_fmt_pct(v, prefs)}</div></div>"
        )
    st.markdown(
        f"<div style='display:flex; flex-wrap:wrap; gap:0.35rem;'>{''.join(blocos)}</div>",
        unsafe_allow_html=True,
    )
    maior_dispersao = max(setores, key=lambda s: abs(s["variacao_media_pct"]))
    st.markdown(
        f"<div class='cinza' style='font-size:0.6rem; margin-top:0.4rem; padding-top:0.35rem; "
        f"border-top:1px solid var(--borda);'>Maior dispersão: "
        f"<b style='color:var(--destaque);'>{html.escape(maior_dispersao['setor'])}</b> "
        f"({maior_dispersao['n_papeis']} papel(éis), {_fmt_pct(maior_dispersao['variacao_media_pct'], prefs)} méd.)</div>",
        unsafe_allow_html=True,
    )


# ===================== desempenho + agenda/teses =====================

def _painel_desempenho_tabela(prefs):
    """"Desempenho do Ibovespa" - tabela com Ativo/Setor/Preço/Var.%/
    Volume pros papéis mais negociados do dia. Mesma função de dado de
    MERCADO › PAINEL (obter_mais_negociados) - Empresa vem de mapa
    estático já existente (config.TICKER_NOME), setor já vem no próprio
    dict - nenhum dado novo, nenhuma consulta nova."""
    st.markdown('<div class="painel-titulo">DESEMPENHO DO IBOVESPA</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)
    papeis = obter_mais_negociados(6)
    if not papeis:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    cabecalho = (
        "<tr style='font-size:0.62rem; color:var(--cinza);'>"
        "<td style='padding:0 0.3rem 0.25rem 0;'>ATIVO</td><td style='padding:0 0.3rem 0.25rem;'>SETOR</td>"
        "<td style='padding:0 0.3rem 0.25rem; text-align:right;'>PREÇO</td>"
        "<td style='padding:0 0.3rem 0.25rem; text-align:right;'>VAR. %</td>"
        "<td style='padding:0 0 0.25rem 0.3rem; text-align:right;'>VOL. (R$ MI)</td></tr>"
    )
    linhas = [cabecalho]
    for p in papeis:
        cls = "alta" if p["variacao_pct"] >= 0 else "baixa"
        nome = config.TICKER_NOME.get(p["ticker"], p["ticker"])
        linhas.append(
            f"<tr style='font-size:0.76rem;'>"
            f"<td style='padding:0.2rem 0.3rem 0.2rem 0; white-space:nowrap;'>"
            f"{_badge_ticker(p['ticker'], tema)}<b>{p['ticker']}</b> "
            f"<span class='cinza' style='font-size:0.64rem;'>{html.escape(nome)}</span></td>"
            f"<td style='padding:0.2rem 0.3rem;' class='cinza'>{html.escape(p['setor'])}</td>"
            f"<td style='padding:0.2rem 0.3rem; text-align:right;' class='neutro'>"
            f"{config.formatar_numero(p['preco'], 2, prefs['formato_numerico'])}</td>"
            f"<td style='padding:0.2rem 0.3rem; text-align:right;' class='{cls}'>{_fmt_pct(p['variacao_pct'], prefs)}</td>"
            f"<td style='padding:0.2rem 0 0.2rem 0.3rem; text-align:right;' class='neutro'>"
            f"{config.formatar_numero(p['volume_financeiro'] / 1_000_000, 1, prefs['formato_numerico'])}</td></tr>"
        )
    st.markdown(
        f"<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse;'>"
        f"{''.join(linhas)}</table></div>",
        unsafe_allow_html=True,
    )


def _teses_research_watchlist(prefs) -> list:
    """Teses/recomendações JÁ COLETADAS (data/research, mesmo mecanismo
    de RESEARCH › Casas de Análise) pra tickers da watchlist - só leitura
    do que já está salvo (ui.research_tab.preparar_leitura, sem coleta
    nova), respeitando as casas ativas escolhidas pelo usuário em CONFIG.
    Recomendação/preço-alvo vêm DA CASA (atribuídos, nunca gerados pelo
    PREGÃO) - só aparece se já existir uma recomendação real salva."""
    watchlist = list(prefs.get("watchlist") or [])
    if not watchlist:
        return []
    casas_ativas = _casas_ativas(prefs)
    if not casas_ativas:
        return []
    relatorios, _falhas, _, _ = preparar_leitura(casas_ativas)
    if not relatorios:
        return []
    itens = []
    for ticker in watchlist:
        candidatos = [r for r in relatorios if ticker in (r.get("tickers") or []) and r.get("recomendacao")]
        if candidatos:
            itens.append((ticker, candidatos[0]))
    return itens


def _painel_agenda_e_teses(prefs):
    """AGENDA (reaproveita ui.calendario_tab._painel_proximos_watchlist,
    intocado) + TESES DE RESEARCH da watchlist logo abaixo - mesmo
    módulo, evita abrir mais uma seção separada só pra isso."""
    _painel_proximos_watchlist(prefs)
    teses = _teses_research_watchlist(prefs)
    if not teses:
        return
    st.markdown(
        "<div class='cinza' style='font-size:0.58rem; letter-spacing:0.05em; margin-top:0.6rem; "
        "padding-top:0.5rem; border-top:1px dashed var(--borda);'>TESES DE RESEARCH · WATCHLIST</div>",
        unsafe_allow_html=True,
    )
    linhas = []
    for ticker, item in teses:
        recomendacao = item.get("recomendacao") or ""
        cor = "alta" if "COMPRA" in recomendacao.upper() else ("baixa" if "VENDA" in recomendacao.upper() else "cinza")
        alvo = (
            f" · R$ {config.formatar_numero(item['preco_alvo'], 2, prefs['formato_numerico'])}"
            if item.get("preco_alvo") else ""
        )
        linhas.append(
            f"<div style='display:flex; justify-content:space-between; align-items:baseline; "
            f"font-size:0.7rem; padding:0.22rem 0;'>"
            f"<span><b>{html.escape(ticker)}</b> <span class='cinza' style='font-size:0.6rem;'>"
            f"· {html.escape(item['casa'])}</span></span>"
            f"<span class='{cor}' style='font-weight:700; font-size:0.62rem;'>{html.escape(recomendacao)}{alvo}</span></div>"
        )
    st.markdown("".join(linhas), unsafe_allow_html=True)


# ===================== globais + watchlist =====================

def _painel_watchlist_compacta(prefs):
    st.markdown('<div class="painel-titulo">MINHA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Adicione tickers na barra lateral.</div>", unsafe_allow_html=True)
        return
    linhas = []
    # obter_cotacoes_lote (N+1 real corrigido, 2026-10-08): 1 UNICA
    # requisicao em lote pra watchlist inteira, em vez de 1
    # yf.Ticker().fast_info POR TICKER (obter_cotacao) - com watchlist
    # grande e cache expirado, essa tela ficava bloqueada numa sequencia
    # de round-trips sequenciais ao Yahoo.
    cotacoes = obter_cotacoes_lote(tuple(watchlist))
    for t in watchlist:
        cot = cotacoes.get(t, {"erro": "sem dado"})
        if cot.get("erro"):
            linhas.append(f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'>{t}</td><td colspan='2' class='cinza'>—</td></tr>")
            continue
        cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
        linhas.append(
            f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'><span style='color:var(--destaque); font-weight:600;'>{t}</span></td>"
            f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>R$ {config.formatar_numero(cot['preco'], 2, prefs['formato_numerico'])}</td>"
            f"<td style='padding:0.2rem 0 0.2rem 0.4rem; text-align:right;' class='{cls}'>{_fmt_pct(cot['variacao_pct'], prefs)}</td></tr>"
        )
    st.markdown(f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>{''.join(linhas)}</table>", unsafe_allow_html=True)


# ===================== composição fixa (cockpit) =====================
# Workspace modular (arrastar/redimensionar por painel) FOI RETIRADO
# desta aba no redesign terminal (2026-10-27): todo o conteúdo virou
# seções fixas (mesmo padrão já usado por TERMÔMETRO em MERCADO ›
# PAINEL, estendido aqui pra aba inteira) - um cockpit único e coeso,
# não um conjunto de blocos reordenáveis pelo usuário. MERCADO › PAINEL
# continua com drag/resize normalmente, intocado. REGISTRO_PAINEIS fica
# vazio (não removido) só pra não quebrar import/CONFIG em app.py.
REGISTRO_PAINEIS = []


def render_visao_geral(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba VISÃO GERAL, chamado pelo app.py.
    `persistir_fn` não é mais usado aqui (sem painel arrastável/
    configurável nesta aba) - mantido no parâmetro só pra manter a
    mesma assinatura que app.py já chama."""
    with st.container(border=True):
        _painel_leitura_pregao(prefs)

    with st.container(border=True):
        _painel_indicadores(prefs)

    with st.container(key="vg_grid_principal"):
        col_grafico, col_investigar = st.columns([0.7, 0.3], gap="small")
        with col_grafico:
            with st.container(border=True):
                _painel_ibov_grafico(prefs)
        with col_investigar:
            with st.container(border=True):
                _painel_para_investigar(prefs)

    with st.container(key="vg_grid_exploracao"):
        col_ab, col_news, col_setor = st.columns([0.36, 0.36, 0.28], gap="small")
        with col_ab:
            with st.container(border=True):
                _painel_altas_baixas_resumo(prefs)
        with col_news:
            with st.container(border=True):
                _painel_noticias_resumo(prefs)
        with col_setor:
            with st.container(border=True):
                _painel_mapa_setorial_compacto(prefs)

    with st.container(key="vg_grid_desempenho"):
        col_desemp, col_agenda = st.columns([0.6, 0.4], gap="small")
        with col_desemp:
            with st.container(border=True):
                _painel_desempenho_tabela(prefs)
        with col_agenda:
            with st.container(border=True):
                _painel_agenda_e_teses(prefs)

    with st.container(key="vg_grid_globais"):
        col_globais, col_watchlist = st.columns([0.55, 0.45], gap="small")
        with col_globais:
            with st.container(border=True):
                _painel_globais(prefs)
        with col_watchlist:
            with st.container(border=True):
                _painel_watchlist_compacta(prefs)
