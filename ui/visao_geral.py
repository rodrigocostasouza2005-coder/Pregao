# -*- coding: utf-8 -*-
"""Aba "0 VISÃO GERAL" - home do PREGÃO (redesign do terminal, ver
PROGRESSO.md). Objetivo: em ~10 segundos, entender o que está
acontecendo no mercado. NÃO tem coleta/lógica de dado própria - é
composição de painéis/funções que já existem em outras abas (MERCADO,
MACRO, NEWS), reaproveitados diretamente (mesmo cache, sem nenhuma
consulta nova). Onde a função original já é "pesada demais" pra um
resumo (a lista completa de notícias, por exemplo), usa a mesma função
de dado com um limite de itens menor, não uma cópia da lógica."""

import html
from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

import config
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
from data.sintese_mercado import obter_sintese_mercado
from ui import graficos, workspace
from ui.calendario_tab import _painel_proximos_watchlist
from ui.mercado_tab import _painel_globais, _painel_leitura_rapida
from ui.news_tab import (
    _CLASSE_SELO, _fmt_hora, _injetar_css, _plural_fontes, _texto_tag, _tooltip_regras, _truncar,
)

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


def _painel_analista_cenarios(prefs):
    """(D) Cenários e o que observar - adaptação do skill oficial
    "market-researcher"/"competitive-analysis" (bull/base/bear +
    catalisadores/signposts), ver data/sintese_mercado.py. Cenário
    'principal' é a leitura mais consistente com os fatos coletados
    agora; 'alternativo' é o que os MESMOS fatos também sustentam, com
    menos peso - nunca uma probabilidade numérica (isso seria
    inventado). 'O que observar' lista só catalisadores que já vieram
    da agenda/movimentos/oportunidades já coletados, nunca um evento
    novo inventado pela IA."""
    st.markdown('<div class="painel-titulo">CENÁRIOS E O QUE OBSERVAR</div>', unsafe_allow_html=True)
    resultado = obter_sintese_mercado()
    if not resultado.get("ok"):
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Sem leitura analítica disponível no momento.</div>",
            unsafe_allow_html=True,
        )
        return
    dados = resultado["dados"]
    cenarios = dados.get("cenarios") or []
    observar = dados.get("observar_proximas_sessoes") or []
    if not cenarios and not observar:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Sem evidência suficiente nesta rodada para "
            "projetar cenário ou apontar o que observar.</div>",
            unsafe_allow_html=True,
        )
        return

    for item in cenarios:
        rotulo = "CENÁRIO PRINCIPAL" if item.get("tipo") == "principal" else "CENÁRIO ALTERNATIVO"
        cor = "alta" if item.get("tipo") == "principal" else "cinza"
        st.markdown(
            f"<div style='padding:0.45rem 0; border-bottom:1px solid var(--borda);'>"
            f"<div class='{cor}' style='font-size:0.64rem; font-weight:700; letter-spacing:0.03em;'>{rotulo}</div>"
            f"<div style='font-size:0.84rem; font-weight:600; margin-top:0.1rem;'>{item.get('cenario') or ''}</div>"
            + (f"<div style='font-size:0.76rem; margin-top:0.15rem;'>Condição: {item['condicao']}</div>"
               if item.get("condicao") else "")
            + (f"<div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>Sinalizadores a observar: "
               f"{item['sinalizadores']}</div>" if item.get("sinalizadores") else "")
            + "</div>",
            unsafe_allow_html=True,
        )
    if cenarios:
        st.markdown(
            "<div class='cinza' style='font-size:0.66rem; margin-top:0.2rem;'>Cenários não têm "
            "probabilidade numérica - são leituras qualitativas sobre os mesmos fatos coletados, nunca uma "
            "previsão de preço.</div>",
            unsafe_allow_html=True,
        )

    if observar:
        st.markdown(
            "<div style='font-size:0.72rem; font-weight:600; margin-top:0.6rem;'>O que observar nas "
            "próximas sessões</div>",
            unsafe_allow_html=True,
        )
        for item in observar:
            fonte = item.get("fonte") or "fonte não informada"
            data_fonte = f" · {item['data_fonte']}" if item.get("data_fonte") else ""
            st.markdown(
                f"<div style='padding:0.3rem 0; border-bottom:1px solid var(--borda);'>"
                f"<div style='font-size:0.78rem;'>{item.get('item') or ''}</div>"
                + (f"<div class='cinza' style='font-size:0.68rem;'>{item['motivo']}</div>"
                   if item.get("motivo") else "")
                + f"<div class='cinza' style='font-size:0.64rem; margin-top:0.1rem;'>{fonte}{data_fonte}</div>"
                + "</div>",
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
    """Renderer PRÓPRIO (não `ui.news_tab._renderizar_lista`, que é "wire
    denso" pensado pra largura cheia de TOP MERCADO/EQUITY) - achado real
    (redesign em grade, 2026-10-27): `_renderizar_lista` usa `st.columns`
    com pesos fixos pra selo/hora/manchete/fontes/link; numa coluna
    estreita (~36% da página, grade de 3) essas colunas espremiam a ponto
    do selo (badge) sobrepor o início da manchete - texto ilegível. Esta
    versão é 1 bloco HTML empilhado por item (sem múltiplas colunas),
    mesma função de dado (obter_top_mercado_tudo) e mesmos campos/selo já
    usados lá - zero dado novo, só layout diferente pra caber estreito."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">MARKET NEWS <span class="cinza" style="font-size:0.68rem;font-weight:400;">ÚLTIMAS 4</span></div>', unsafe_allow_html=True)
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


def _badge_ticker(ticker: str, tema: dict) -> str:
    """Selo compacto com as iniciais do ticker - substituto leve de logo
    de empresa (pedido do Rodrigo, redesign 2026-10-27): não existe
    mecanismo de logo real por ticker no projeto hoje (nenhum serviço
    externo configurado) - gerar um exigiria CDN novo ou banco de
    assets mantido manualmente, fora do que reaproveita infraestrutura
    existente. CSS puro, derivado do próprio ticker, sem dado inventado."""
    iniciais = ("".join(c for c in ticker if c.isalpha())[:2] or ticker[:2]).upper()
    return (
        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
        f"width:1.5rem; height:1.5rem; min-width:1.5rem; border-radius:4px; "
        f"background:{tema['destaque']}22; color:{tema['destaque']}; "
        f"font-size:0.58rem; font-weight:700; margin-right:0.35rem; vertical-align:middle;'>"
        f"{html.escape(iniciais)}</span>"
    )


def _painel_altas_baixas_resumo(prefs):
    """(NOVO, 2026-10-27) Versão compacta de "Maiores altas/baixas" pra
    VISÃO GERAL - 2 colunas lado a lado (altas | baixas), top 5 do dia,
    sem filtros/controles (esses ficam na versão completa, MERCADO ›
    PAINEL). Mesma função de dado (data/mercado.py:obter_altas_baixas),
    zero consulta nova - só um recorte menor, mesmo padrão já usado
    pelos outros painéis "resumo" desta aba (ver docstring do módulo)."""
    st.markdown('<div class="painel-titulo">PRINCIPAIS ALTAS E BAIXAS</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)
    # 4 (nao 5): coluna estreita na grade de 3 (redesign 2026-10-27) - 5
    # linhas por lado deixava a linha mais larga que MARKET NEWS/MAPA
    # SETORIAL ao lado, quebrando o alinhamento da linha inteira.
    altas, baixas = obter_altas_baixas(4, "dia")

    def _coluna(titulo, papeis, cls):
        st.markdown(f"<div class='{cls}' style='font-size:0.68rem; font-weight:700; margin-bottom:0.25rem;'>{titulo}</div>", unsafe_allow_html=True)
        if not papeis:
            st.markdown("<div class='cinza' style='font-size:0.74rem;'>—</div>", unsafe_allow_html=True)
            return
        linhas = []
        for p in papeis:
            linhas.append(
                f"<tr><td style='padding:0.16rem 0.2rem 0.16rem 0; white-space:nowrap;'>"
                f"{_badge_ticker(p['ticker'], tema)}<span style='font-weight:600; font-size:0.72rem;'>{p['ticker']}</span></td>"
                f"<td style='padding:0.16rem 0 0.16rem 0.2rem; text-align:right;' class='{cls}'>"
                f"{_fmt_pct(p['variacao_pct'], prefs)}</td></tr>"
            )
        st.markdown(
            f"<table style='width:100%; font-size:0.74rem; border-collapse:collapse;'>{''.join(linhas)}</table>",
            unsafe_allow_html=True,
        )

    with st.container(key="vg_altas_baixas_resumo_cols"):
        col_altas, col_baixas = st.columns(2, gap="small")
        with col_altas:
            _coluna("ALTAS", altas, "alta")
        with col_baixas:
            _coluna("BAIXAS", baixas, "baixa")


def _painel_mapa_setorial_compacto(prefs):
    """(NOVO, 2026-10-27) "Mapa setorial" compacto pra VISÃO GERAL -
    grade de blocos coloridos (até 9 setores), NÃO o treemap completo
    de MERCADO › PAINEL (que segue intocado) - aqui é um painel
    secundário, não o protagonista da tela. Mesma função de dado
    (data/mercado.py:obter_desempenho_setorial), zero consulta nova."""
    st.markdown('<div class="painel-titulo">MAPA SETORIAL</div>', unsafe_allow_html=True)
    setores = obter_desempenho_setorial("dia")
    if not setores:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    tema = _tema_atual(prefs)
    blocos = []
    # 6 (nao 9) em grade 2 por linha (nao 3): esta coluna agora e' so' ~28%
    # da pagina (grade de 3, redesign 2026-10-27) - 3 por linha nessa
    # largura deixava o nome de setor cortado/sem espaco pro numero.
    # Secundario de proposito: metade dos setores, nao todos.
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


def _painel_desempenho_tabela(prefs):
    """(NOVO, 2026-10-27) "Desempenho do Ibovespa" - tabela com
    Código/Empresa/Setor/Preço/Var.%/Volume pros papéis mais negociados
    do dia. Mesma função de dado de MERCADO › PAINEL (mais_negociados,
    data/mercado.py:obter_mais_negociados) - Empresa/Setor vêm de mapas
    estáticos já existentes (config.TICKER_NOME, e "setor" já vem no
    próprio dict de obter_mais_negociados) - nenhum dado novo, nenhuma
    consulta nova."""
    st.markdown('<div class="painel-titulo">DESEMPENHO DO IBOVESPA</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)
    # 6 (nao 8): compacto na grade lado a lado com AGENDA (redesign
    # 2026-10-27) - evita bloco alto/espaco vazio desproporcional ao
    # lado da agenda, que normalmente tem menos linhas.
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


# paineis registrados (ver ui/paineis.py/ui/workspace.py) - ETAPA 5
# (2026-10-01): VISÃO GERAL migra pro workspace modular, mesma mecanica
# ja' validada em MERCADO/MACRO. Conteúdo de cada painel intocado (3
# reaproveitados direto de ui/mercado_tab.py, já registrados lá também -
# pid local aqui não colide, cada aba_id tem sua própria tabela de
# ordem/visibilidade/layout em prefs). Ordem abaixo = ordem padrão atual
# (mesma sequência que render_visao_geral já tinha antes da migração).
REGISTRO_PAINEIS = [
    # ORDEM PADRAO (redesign 2026-10-27, referencia visual fornecida pelo
    # Rodrigo) - detalhes/interpretacao mais profunda depois do "resumo em
    # ~10s" fixo (ver render_visao_geral: MERCADO AGORA + as 2 linhas em
    # grade NAO estao mais aqui, viraram secoes FIXAS fora do workspace
    # arrastavel - mesmo padrao ja usado por TERMOMETRO em MERCADO >
    # PAINEL - pra reproduzir o layout lado-a-lado da referencia de
    # verdade, nao só empilhado). Usuario pode reordenar o que sobra
    # livremente (workspace modular).
    ("ibov_grafico", "Ibovespa", _painel_ibov_grafico),
    # LEITURA RÁPIDA (2026-10-27): reaproveitado de ui/mercado_tab.py -
    # introduzido originalmente na aba PAINEL (PR #182), mas o pedido real
    # do Rodrigo era aqui em VISÃO GERAL (os outros 3 painéis daquele PR -
    # métricas/gráfico/notícias - já tinham equivalente aqui antes, só
    # esse faltava).
    ("leitura_rapida", "Leitura rápida", _painel_leitura_rapida),
    # ANALISTA DE MERCADO (síntese/interpretação, 2026-10-26): leitura mais
    # profunda, fica depois do resumo "em ~10s" acima.
    ("analista_resumo", "Resumo executivo do mercado", _painel_analista_resumo),
    ("analista_movimentos", "O que está movendo o mercado", _painel_analista_movimentos),
    ("analista_oportunidades", "Para investigar", _painel_analista_oportunidades),
    ("analista_cenarios", "Cenários e o que observar", _painel_analista_cenarios),
    ("globais", "Mercados globais", _painel_globais),
    ("watchlist_compacta", "Minha watchlist", _painel_watchlist_compacta),
]


def render_visao_geral(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba VISÃO GERAL, chamado pelo app.py.
    `persistir_fn` (opcional): ver ui/workspace.py:renderizar_workspace.

    Composição FIXA no topo (redesign 2026-10-27, seguindo referência
    visual fornecida pelo Rodrigo) - 3 seções lado a lado (reproduz o
    grid da imagem de verdade, não uma lista empilhada): MERCADO AGORA
    sozinho, depois ALTAS/BAIXAS + NOTÍCIAS + MAPA SETORIAL numa linha
    de 3 colunas, depois DESEMPENHO + AGENDA numa linha de 2 colunas.
    Mesmo padrão já usado por TERMOMETRO em MERCADO > PAINEL (fora do
    REGISTRO_PAINEIS de propósito) - essas seções NÃO são arrastáveis/
    redimensionáveis individualmente (trade-off aceito explicitamente
    pelo Rodrigo pra bater com a referência). st.columns do Streamlit já
    reflow pra empilhado em telas estreitas (mesmo CSS global usado em
    MERCADO/outras abas), sem precisar de nenhuma regra nova aqui.

    O restante (REGISTRO_PAINEIS) continua no workspace modular normal,
    abaixo desta composição fixa."""
    with st.container(border=True):
        _painel_mercado_agora(prefs)

    with st.container(key="vg_grid_linha1"):
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

    with st.container(key="vg_grid_linha2"):
        col_desemp, col_agenda = st.columns([0.6, 0.4], gap="small")
        with col_desemp:
            with st.container(border=True):
                _painel_desempenho_tabela(prefs)
        with col_agenda:
            with st.container(border=True):
                _painel_proximos_watchlist(prefs)

    workspace.renderizar_workspace("VISÃO GERAL", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn)
