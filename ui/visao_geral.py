# -*- coding: utf-8 -*-
"""Aba "0 VISÃO GERAL" - home do PREGÃO (redesign do terminal, ver
PROGRESSO.md). Objetivo: em ~10 segundos, entender o que está
acontecendo no mercado. NÃO tem coleta/lógica de dado própria - é
composição de painéis/funções que já existem em outras abas (MERCADO,
MACRO, NEWS), reaproveitados diretamente (mesmo cache, sem nenhuma
consulta nova). Onde a função original já é "pesada demais" pra um
resumo (a lista completa de notícias, por exemplo), usa a mesma função
de dado com um limite de itens menor, não uma cópia da lógica."""

from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

import config
from data.ibovespa import obter_composicao_oficial
from data.macro import obter_cdi
from data.mercado import obter_cotacoes_lote, obter_mercados_globais
from data.news import obter_top_mercado_tudo
from data.prices import (
    obter_cotacao, obter_cotacao_indice, obter_historico, obter_historico_intraday, rotulo_cotacao_em_cache,
)
from data.sintese_mercado import obter_sintese_mercado
from ui import graficos, workspace
from ui.calendario_tab import _painel_proximos_watchlist
from ui.mercado_tab import _painel_altas_baixas, _painel_globais, _painel_mais_negociados, _painel_setorial
from ui.news_tab import _injetar_css, _prontos_para_lista, _renderizar_lista

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


def _card_mercado(rotulo: str, preco, variacao_pct, prefs, casas_preco: int = 2, status: str | None = None):
    """Card compacto de mercado; cotações reaproveitadas ficam explicitamente sinalizadas."""
    status_html = f"<div class='card-mercado-status'>{status}</div>" if status else ""
    if preco is None or variacao_pct is None:
        st.markdown(
            f"<div class='card-mercado-agora'>"
            f"<div class='card-mercado-rotulo'>{rotulo}</div>"
            f"<div class='card-mercado-valor indisponivel'>—</div>"
            f"<div class='card-mercado-variacao cinza'>SEM DADO</div>{status_html}</div>",
            unsafe_allow_html=True,
        )
        return
    cls = "alta" if variacao_pct >= 0 else "baixa"
    st.markdown(
        f"<div class='card-mercado-agora'>"
        f"<div class='card-mercado-rotulo'>{rotulo}</div>"
        f"<div class='card-mercado-valor'>{config.formatar_numero(preco, casas_preco, prefs['formato_numerico'])}</div>"
        f"<div class='card-mercado-variacao {cls}'>{_fmt_pct(variacao_pct, prefs)}</div>{status_html}</div>",
        unsafe_allow_html=True,
    )

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


def _aviso_fontes_indisponiveis(fontes: list):
    if not fontes:
        return
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin-top:0.3rem;'>"
        f"Fontes indisponíveis nesta leitura: {'; '.join(fontes)}.</div>",
        unsafe_allow_html=True,
    )


def _painel_analista_resumo(prefs):
    """(A) Resumo executivo do mercado - ANALISTA DE MERCADO. Camada de
    INTERPRETAÇÃO sobre dados já coletados (ver data/sintese_mercado.py)
    - nunca um dado novo. Três estados honestos, nunca disfarçados: sem
    síntese (ok=False), síntese anterior usada como fallback (atual=
    False, rotulada), síntese desta rodada (atual=True)."""
    st.markdown('<div class="painel-titulo">RESUMO EXECUTIVO DO MERCADO</div>', unsafe_allow_html=True)
    resultado = obter_sintese_mercado()
    if not resultado.get("ok"):
        st.markdown(
            f"<div class='cinza' style='font-size:0.78rem;'>Análise indisponível no momento "
            f"({resultado.get('motivo') or 'sem detalhe'}). Os dados de mercado abaixo continuam "
            f"atualizados normalmente.</div>",
            unsafe_allow_html=True,
        )
        return

    dados = resultado["dados"]
    resumo = dados["resumo_executivo"]
    rotulo_tempo = _tempo_relativo(resultado.get("gerado_em"))
    if resultado.get("atual"):
        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin-bottom:0.4rem;'>Atualizado {rotulo_tempo} "
            f"· modelo {resultado.get('modelo') or '—'}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='alerta' style='font-size:0.68rem; margin-bottom:0.4rem; font-weight:600;'>"
            f"ANÁLISE ANTERIOR (atualizada {rotulo_tempo}) - a rodada atual não pôde ser gerada"
            f"{' (' + resultado['motivo_atual_indisponivel'] + ')' if resultado.get('motivo_atual_indisponivel') else ''}."
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown(f"<div style='font-size:0.86rem; line-height:1.5;'>{resumo['texto']}</div>", unsafe_allow_html=True)
    if resumo.get("ressalvas"):
        st.markdown(
            f"<div class='cinza' style='font-size:0.74rem; margin-top:0.4rem;'>Ressalvas: {resumo['ressalvas']}</div>",
            unsafe_allow_html=True,
        )
    nao_sabemos = dados.get("o_que_nao_sabemos") or []
    if nao_sabemos:
        st.markdown(
            "<div class='cinza' style='font-size:0.72rem; margin-top:0.5rem;'>O que ainda não sabemos: "
            + "; ".join(nao_sabemos) + "</div>",
            unsafe_allow_html=True,
        )
    _aviso_fontes_indisponiveis(resultado.get("fontes_indisponiveis") or [])


def _painel_analista_movimentos(prefs):
    """(B) O que está movendo o mercado - lista priorizada pela própria
    IA (máx. 6, ver _PROMPT_SISTEMA), cada item com fonte/evidência
    citada. Nunca mostra confiança numérica (só qualitativa+motivo)."""
    st.markdown('<div class="painel-titulo">O QUE ESTÁ MOVENDO O MERCADO</div>', unsafe_allow_html=True)
    resultado = obter_sintese_mercado()
    if not resultado.get("ok"):
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Sem leitura analítica disponível no momento.</div>",
            unsafe_allow_html=True,
        )
        return
    movimentos = resultado["dados"].get("movimentos") or []
    if not movimentos:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nenhum movimento com evidência suficiente nesta rodada.</div>",
            unsafe_allow_html=True,
        )
        return
    for item in movimentos:
        fonte = item.get("fonte") or "fonte não informada"
        data_fonte = f" · {item['data_fonte']}" if item.get("data_fonte") else ""
        st.markdown(
            f"<div style='padding:0.45rem 0; border-bottom:1px solid var(--borda);'>"
            f"<div style='font-size:0.84rem; font-weight:600;'>{item.get('evento') or ''}</div>"
            f"<div class='cinza' style='font-size:0.68rem; margin:0.1rem 0 0.25rem 0;'>{fonte}{data_fonte}"
            f" · confiança {item.get('confianca') or '—'}</div>"
            f"<div style='font-size:0.78rem;'>{item.get('por_que_importa') or ''}</div>"
            + (f"<div class='cinza' style='font-size:0.74rem; margin-top:0.15rem;'>Possível impacto: "
               f"{item['impacto_possivel']}</div>" if item.get("impacto_possivel") else "")
            + (f"<div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>Horizonte: {item['horizonte']}"
               f"</div>" if item.get("horizonte") else "")
            + f"</div>",
            unsafe_allow_html=True,
        )
    _aviso_fontes_indisponiveis(resultado.get("fontes_indisponiveis") or [])


def _painel_analista_oportunidades(prefs):
    """(C) Oportunidades e riscos para investigar - NUNCA recomendação
    de compra/venda nem preço-alvo (ver _PROMPT_SISTEMA e a mesma regra
    já aplicada em RESEARCH > Casas de Análise)."""
    st.markdown('<div class="painel-titulo">PARA INVESTIGAR</div>', unsafe_allow_html=True)
    resultado = obter_sintese_mercado()
    if not resultado.get("ok"):
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Sem leitura analítica disponível no momento.</div>",
            unsafe_allow_html=True,
        )
        return
    itens = resultado["dados"].get("oportunidades_riscos") or []
    if not itens:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nada com evidência suficiente para destacar nesta rodada.</div>",
            unsafe_allow_html=True,
        )
        return
    for item in itens:
        fonte = item.get("fonte") or "fonte não informada"
        data_fonte = f" · {item['data_fonte']}" if item.get("data_fonte") else ""
        st.markdown(
            f"<div style='padding:0.45rem 0; border-bottom:1px solid var(--borda);'>"
            f"<div style='font-size:0.84rem; font-weight:600;'>{item.get('ativo_ou_setor') or ''}</div>"
            f"<div class='cinza' style='font-size:0.68rem; margin:0.1rem 0 0.25rem 0;'>{fonte}{data_fonte}</div>"
            f"<div style='font-size:0.78rem;'>Catalisador: {item.get('catalisador') or '—'}</div>"
            f"<div style='font-size:0.76rem; margin-top:0.15rem;'><span class='alta'>A favor:</span> "
            f"{item.get('argumento_favoravel') or '—'}</div>"
            f"<div style='font-size:0.76rem; margin-top:0.1rem;'><span class='baixa'>Contra:</span> "
            f"{item.get('argumento_contrario') or '—'}</div>"
            + (f"<div class='cinza' style='font-size:0.68rem; margin-top:0.15rem;'>Acompanhar: "
               f"{item['acompanhar']}</div>" if item.get("acompanhar") else "")
            + f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div class='cinza' style='font-size:0.66rem; margin-top:0.4rem;'>\"Para investigar\" não é "
        "recomendação de compra/venda - não há preço-alvo nem indicação de operação aqui.</div>",
        unsafe_allow_html=True,
    )
    _aviso_fontes_indisponiveis(resultado.get("fontes_indisponiveis") or [])


def _painel_mercado_agora(prefs):
    st.markdown('<div class="painel-titulo">MERCADO AGORA</div>', unsafe_allow_html=True)
    # achado real (2026-10-08): VISAO GERAL reaproveita _painel_altas_baixas/
    # _painel_setorial de ui/mercado_tab.py, mas NAO _painel_termometro -
    # que e' onde mora o unico aviso visivel de "B3 indisponivel, usando
    # lista curada de fallback". Quem so' abre a VISAO GERAL nunca via
    # esse aviso e nunca saberia que a base mudou. Mesma checagem
    # (barata, cacheada) exposta aqui pra nao degradar silenciosamente.
    if not obter_composicao_oficial():
        st.caption(
            f"B3 indisponível no momento - altas/baixas e desempenho setorial usam lista curada de "
            f"fallback ({len(config.IBOVESPA_SETORES)} papéis)."
        )
    globais = {g["nome"]: g for g in obter_mercados_globais()}
    cdi_df = obter_cdi(dias_historico=5)
    cdi_atual = float(cdi_df["cdi_anualizado_pct"].iloc[-1]) if cdi_df is not None and not cdi_df.empty else None
    # variacao real (p.p.) entre a ultima leitura e a anterior do CDI
    # anualizado - achado real (2026-10-08): antes era "0.0" fixo (nunca
    # calculado), fazendo o card sempre pintar verde e mostrar "+0,00%"
    # mesmo quando a taxa de fato mudou no dia. None (nunca 0.0) quando
    # so' ha' 1 leitura - sem dado suficiente pra comparar, o card mostra
    # "—" (ver _card_mercado), nunca uma variacao inventada.
    cdi_variacao = None
    if cdi_df is not None and len(cdi_df) >= 2:
        anterior = float(cdi_df["cdi_anualizado_pct"].iloc[-2])
        cdi_variacao = cdi_atual - anterior if cdi_atual is not None else None

    ibov = obter_cotacao_indice("IBOVESPA", "^BVSP")
    dolar = obter_cotacao_indice("DOLAR", "USDBRL=X")
    petr4 = obter_cotacao("PETR4")
    vale3 = obter_cotacao("VALE3")

    with st.container(key="visao_geral_mercado_agora_cols"):
        cols = st.columns(7)
        with cols[0]:
            _card_mercado("IBOV", None if ibov.get("erro") else ibov["preco"], None if ibov.get("erro") else ibov["variacao_pct"], prefs, 0, _status_cotacao_indice(ibov))
        with cols[1]:
            _card_mercado("DÓLAR", None if dolar.get("erro") else dolar["preco"], None if dolar.get("erro") else dolar["variacao_pct"], prefs, status=_status_cotacao_indice(dolar))
        with cols[2]:
            _card_mercado("DI (CDI anual.)", cdi_atual, cdi_variacao, prefs)
        with cols[3]:
            sp500 = globais.get("S&P 500")
            _card_mercado("S&P 500", sp500["preco"] if sp500 else None, sp500["variacao_pct"] if sp500 else None, prefs, 0)
        with cols[4]:
            nasdaq = globais.get("Nasdaq")
            _card_mercado("NASDAQ", nasdaq["preco"] if nasdaq else None, nasdaq["variacao_pct"] if nasdaq else None, prefs, 0)
        with cols[5]:
            _card_mercado("PETR4", None if petr4.get("erro") else petr4["preco"], None if petr4.get("erro") else petr4["variacao_pct"], prefs)
        with cols[6]:
            _card_mercado("VALE3", None if vale3.get("erro") else vale3["preco"], None if vale3.get("erro") else vale3["variacao_pct"], prefs)


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
        height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
    )
    # tema["borda"] (nao "#1A1A1A" fixo, achado da auditoria visual
    # 2026-10-16): acompanha o tema CLARO tambem, nao so' os temas escuros.
    fig.update_xaxes(gridcolor=tema["borda"])
    fig.update_yaxes(gridcolor=tema["borda"])
    chave = graficos.zoom_key("vg_ibov", periodo)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)


def _painel_noticias_resumo(prefs):
    _injetar_css()
    st.markdown('<div class="painel-titulo">MARKET NEWS <span class="cinza" style="font-size:0.68rem;font-weight:400;">ÚLTIMAS 4</span></div>', unsafe_allow_html=True)
    itens = obter_top_mercado_tudo("TODOS")
    if not itens:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Sem notícias disponíveis.</div>", unsafe_allow_html=True)
        return
    # A visão geral é um resumo executivo, não o feed completo: quatro manchetes
    # no máximo, sem texto longo nem contexto extra. O feed completo fica em NEWS.
    prontos = _prontos_para_lista(itens[:_QTD_NOTICIAS])
    _renderizar_lista(itens[:_QTD_NOTICIAS], mostrar_ticker=True, prefixo="vg", watchlist=prefs.get("watchlist") or [],
                      resumos_prontos=prontos)


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


# paineis registrados (ver ui/paineis.py/ui/workspace.py) - ETAPA 5
# (2026-10-01): VISÃO GERAL migra pro workspace modular, mesma mecanica
# ja' validada em MERCADO/MACRO. Conteúdo de cada painel intocado (3
# reaproveitados direto de ui/mercado_tab.py, já registrados lá também -
# pid local aqui não colide, cada aba_id tem sua própria tabela de
# ordem/visibilidade/layout em prefs). Ordem abaixo = ordem padrão atual
# (mesma sequência que render_visao_geral já tinha antes da migração).
REGISTRO_PAINEIS = [
    # ANALISTA DE MERCADO (síntese/interpretação, 2026-10-26): síntese
    # primeiro, evidências depois, detalhes técnicos por último -
    # ordem padrão pensada pra "o que preciso entender sobre o mercado
    # hoje" vir antes dos números crus que já existiam. Usuário pode
    # reordenar livremente (workspace modular já suporta isso).
    ("analista_resumo", "Resumo executivo do mercado", _painel_analista_resumo),
    ("analista_movimentos", "O que está movendo o mercado", _painel_analista_movimentos),
    ("analista_oportunidades", "Para investigar", _painel_analista_oportunidades),
    ("mercado_agora", "Mercado agora", _painel_mercado_agora),
    ("ibov_grafico", "Ibovespa", _painel_ibov_grafico),
    ("altas_baixas", "Maiores altas/baixas", _painel_altas_baixas),
    ("mais_negociados", "Mais negociados", _painel_mais_negociados),
    ("setorial", "Desempenho setorial", _painel_setorial),
    ("noticias_resumo", "Market news", _painel_noticias_resumo),
    ("globais", "Mercados globais", _painel_globais),
    ("watchlist_compacta", "Minha watchlist", _painel_watchlist_compacta),
    ("agenda_watchlist", "Agenda do mercado", _painel_proximos_watchlist),
]


def render_visao_geral(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba VISÃO GERAL, chamado pelo app.py.
    `persistir_fn` (opcional): ver ui/workspace.py:renderizar_workspace."""
    workspace.renderizar_workspace("VISÃO GERAL", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn)
