# -*- coding: utf-8 -*-
"""Interface da aba MERCADO: visão ampla do pregão (não é sobre um papel
específico, ao contrário de EQUITY) - altas/baixas, mais negociados,
termômetro, mapa de calor setorial e mercados globais. Dados vêm de
data/mercado.py, sobre a composição oficial do Ibovespa direto da B3
(com fallback pra lista curada estática se a B3 falhar - ver aviso fixo
no topo da aba e o comentário em data/ibovespa.py)."""

import html
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data.ibovespa import obter_composicao_oficial
from data.macro import obter_cdi
from data.mercado import (
    CAMPO_VARIACAO_POR_JANELA, obter_altas_baixas, obter_desempenho_setorial,
    obter_mais_negociados, obter_mercados_globais, obter_momento_panorama,
    obter_panorama_ibovespa, obter_termometro,
)
from data.news import obter_top_mercado_tudo
from data.prices import obter_cotacao_indice, rotulo_cotacao_em_cache
from ui import graficos, navegacao, workspace
from ui.news_tab import _injetar_css as _injetar_css_news
# helpers do renderer PROPRIO de noticias (ver _painel_noticias_resumo) e do
# vinculo noticia<->ticker em _painel_destaques - mesmo padrao ja usado por
# ui/visao_geral.py (grade fixa, 2026-10-27): _renderizar_lista e' "wire
# denso" (st.columns de peso fixo pensado pra largura cheia) e quebra numa
# coluna estreita de grade (achado real, badge sobrepondo manchete) - por
# isso o renderer proprio usa so' estes campos/helpers, nunca o componente
# compartilhado inteiro.
from ui.news_tab import (
    _CLASSE_SELO, _fmt_hora, _plural_fontes, _texto_tag, _tickers_do_item, _tooltip_regras, _truncar,
)

# MAPA DO MERCADO: _painel_treemap e' COMPARTILHADO com SETORES
# (ui/setores_tab.py importa a funcao direto, la' renderizada em largura
# cheia) - a altura default (_ALTURA_TREEMAP_PX) NAO muda, pra nao
# regredir o fix de "mapa pequeno" ja validado la' (2026-10-26).
# _ALTURA_TREEMAP_PX_GRADE e' so' pro Painel (redesign em grade,
# 2026-10-27): saiu do workspace livre e virou secao FIXA (ver
# render_mercado) - 1 das 3 colunas da Regiao 2, nao mais "praticamente
# toda a largura util" (pedido anterior, revisado pelo Rodrigo: "evitar
# que o mapa domine a pagina") - calibrada pra uma coluna de ~40% da
# largura em vez de quase-total, mantendo altura ampla (nao um card
# pequeno). Nenhum dos dois depende mais de _ALTURAS_PADRAO do workspace
# (so' existia pros paineis AINDA arrastaveis).
_ALTURA_TREEMAP_PX = 580
_ALTURA_TREEMAP_PX_GRADE = 460

_JANELAS_DESEMPENHO = ["DIA", "SEMANA", "MÊS"]
_JANELA_ROTULO_PARA_CHAVE = {"DIA": "dia", "SEMANA": "semana", "MÊS": "mes"}

# quantidade de manchetes no painel NOTÍCIAS desta aba - 3 (nao 4): coluna
# mais estreita na grade fixa do Painel (redesign 2026-10-27), ver
# _painel_noticias_resumo. Mesma fonte (data/news.py:obter_top_mercado_tudo)
# ja usada em ui/visao_geral.py:_painel_noticias_resumo, nenhuma consulta nova.
_QTD_NOTICIAS_MERCADO = 3

# --- ranking de retornos (MAIORES ALTAS/BAIXAS), estilo "member ranked
# returns" de terminal financeiro - linha de controles inline (periodo/
# quantidade/setor, efeito imediato, sem formulario separado - pedido
# explicito do Rodrigo) + lista unica numerada (melhores primeiro,
# subtitulo, depois piores) com barra horizontal por linha, escala
# independente por grupo (altas/baixas) com referencia de zero na borda
# junto da coluna central. Dado 100% real (data/mercado.py, mesma fonte
# de sempre) - nenhum valor inventado aqui, so' filtro/corte/apresentacao.
_QTD_RANKING_OPCOES = ["5", "10", "15", "20"]
_QTD_RANKING_PADRAO = "10"
_POOL_RANKING = 60  # busca um pool grande (maioria do Ibovespa) pra filtro de setor nao esvaziar a lista


def _nome_papel(ticker: str) -> str:
    """Nome curto curado (config.NOMES_ATIVOS_BUSCA/TICKER_NOME) - string
    vazia (nao o ticker repetido) se nao houver curadoria pra esse papel,
    pra nunca inventar nome de empresa."""
    return config.NOMES_ATIVOS_BUSCA.get(ticker) or config.TICKER_NOME.get(ticker) or ""


def _badge_ticker(ticker: str, tema: dict) -> str:
    """Selo compacto com as iniciais do ticker - substituto leve de logo
    de empresa (pedido do Rodrigo, redesign do Painel 2026-10-27): nao
    existe mecanismo de logo real por ticker no projeto hoje (conferido -
    so' ha' logica pra REJEITAR logo/favicon de noticia, nunca pra buscar
    logo de empresa da B3). Gerar um exigiria CDN novo ou banco de assets
    mantido manualmente - fora do que reaproveita infraestrutura
    existente, e inventaria uma URL que a regra de dado real proibe. CSS
    puro, derivado do proprio ticker, sem dado inventado.

    Duplicado de ui/visao_geral.py:_badge_ticker (identico) - nao
    importavel de la' sem import circular (visao_geral.py importa paineis
    deste modulo, ver topo do arquivo)."""
    iniciais = ("".join(c for c in ticker if c.isalpha())[:2] or ticker[:2]).upper()
    return (
        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
        f"width:1.5rem; height:1.5rem; min-width:1.5rem; border-radius:4px; "
        f"background:{tema['destaque']}22; color:{tema['destaque']}; "
        f"font-size:0.58rem; font-weight:700; margin-right:0.35rem; vertical-align:middle;'>"
        f"{html.escape(iniciais)}</span>"
    )


def _ir_para_equity(ticker: str, prefs: dict):
    """Callback (on_click) do botao de ticker do ranking - reaproveita o
    MESMO mecanismo de navegacao da busca global (app.py:_ir_com_ticker,
    ui/navegacao.py:ir_para): abre ANALISES > Empresas (antiga EQUITY)
    com esse ticker pre-selecionado.
    Precisa ser on_click (nao escrita direta no corpo do script): o
    segmented_control da navegacao (key="secao_ativa") ja foi instanciado
    mais acima no MESMO run (MERCADO/VISAO GERAL renderizam depois do nav
    no app.py) - escrever na chave de um widget depois dele ja ter sido
    instanciado neste run derruba com StreamlitWidgetAlreadyInstantiatedError;
    um callback de on_click roda ANTES do proximo rerun começar, entao o
    valor novo já está lá quando o nav for instanciado de novo."""
    if "EQUITY" not in (prefs.get("abas_visiveis") or []):
        navegacao.avisar("ANÁLISES › Empresas está oculta nas suas preferências (MAIS › Configurações).")
        return
    if ticker not in prefs["watchlist"]:
        prefs["watchlist"].append(ticker)
    navegacao.ir_para_legado("EQUITY", ticker)


def _tema_atual(prefs):
    return config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])


def _fmt_pct(valor, prefs):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{config.formatar_numero(valor, 2, prefs['formato_numerico'])}%"


def _escolha_estavel_mercado(chave_widget, opcoes, padrao):
    """Igual ao helper de app.py/ui/macro_tab.py (nao importavel de la) -
    guarda a ultima escolha valida de um segmented_control entre reruns."""
    chave_memoria = "mercado_" + chave_widget + "_valido"
    ultimo_valido = st.session_state.get(chave_memoria, padrao)
    if ultimo_valido not in opcoes:
        ultimo_valido = padrao
    return ultimo_valido, chave_memoria


def _seletor_janela(chave_widget: str) -> str:
    """Segmented control DIA/SEMANA/MÊS reutilizado pelos paineis que
    aceitam `janela` (altas/baixas, termometro, setorial) - cada painel
    tem sua PROPRIA escolha independente (chave_widget diferencia), pra
    poder ver ex. "altas/baixas da semana" com "setorial" ainda no dia,
    sem um selecionar afetar o outro. Retorna a chave interna
    (dia/semana/mes - ver CAMPO_VARIACAO_POR_JANELA), nao o rotulo."""
    padrao, mem = _escolha_estavel_mercado(chave_widget, _JANELAS_DESEMPENHO, "DIA")
    sel = st.segmented_control(
        "Período", _JANELAS_DESEMPENHO, default=padrao,
        label_visibility="collapsed", key=f"mercado_{chave_widget}",
    )
    rotulo = sel or padrao
    st.session_state[mem] = rotulo
    return _JANELA_ROTULO_PARA_CHAVE[rotulo]


def _layout_grafico_escuro(fig, tema, altura=340):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=tema["fundo"],
        plot_bgcolor=tema["fundo"],
        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
        height=altura,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    # tema["borda"] (nao "#1A1A1A" fixo, achado da auditoria visual
    # 2026-10-16): acompanha o tema CLARO tambem, nao so' os temas escuros.
    fig.update_xaxes(gridcolor=tema["borda"])
    fig.update_yaxes(gridcolor=tema["borda"])


# --- painéis novos (auditoria visual vs. protótipo pregao_mercado_
# prototipo.html, 2026-10-27): o protótipo é só referência ILUSTRATIVA de
# hierarquia/espaçamento (métricas no topo -> gráfico -> altas/baixas +
# mais negociados -> setorial, depois leitura rápida/notícias/globais) -
# nenhum valor dele (176.045, MGLU3 +9,43% etc.) foi copiado; todo dado
# abaixo vem das MESMAS funções de data/mercado.py, data/prices.py,
# data/macro.py e data/news.py já usadas no resto desta aba/em
# ui/visao_geral.py, reaproveitadas (nunca uma consulta de rede nova).
def _card_metrica(rotulo: str, preco, variacao, prefs, casas_preco: int, status: str | None,
                   rodape: str, unidade_variacao: str = "%"):
    """Card do topo (reaproveita .card-mercado-agora, já usado em
    ui/visao_geral.py - borda superior âmbar, mesmo visual do protótipo) -
    `unidade_variacao` troca "%" por "p.p." pro card de DI (a variação do
    CDI anualizado é em pontos percentuais, não percentual relativo)."""
    status_html = f"<div class='card-mercado-status'>{status}</div>" if status else ""
    if preco is None or variacao is None:
        st.markdown(
            f"<div class='card-mercado-agora'>"
            f"<div class='card-mercado-rotulo'>{rotulo}</div>"
            f"<div class='card-mercado-valor indisponivel'>—</div>"
            f"<div class='card-mercado-variacao cinza'>SEM DADO</div>{status_html}</div>",
            unsafe_allow_html=True,
        )
        return
    cls = "alta" if variacao >= 0 else "baixa"
    seta = "▲" if variacao >= 0 else "▼"
    sinal = "+" if variacao >= 0 else ""
    valor_variacao = f"{sinal}{config.formatar_numero(variacao, 2, prefs['formato_numerico'])}{unidade_variacao}"
    st.markdown(
        f"<div class='card-mercado-agora'>"
        f"<div class='card-mercado-rotulo'>{rotulo}</div>"
        f"<div class='card-mercado-valor'>{config.formatar_numero(preco, casas_preco, prefs['formato_numerico'])}</div>"
        f"<div class='card-mercado-variacao {cls}'>{seta} {valor_variacao}</div>"
        f"<div class='cinza' style='font-size:0.6rem;'>{rodape}</div>{status_html}</div>",
        unsafe_allow_html=True,
    )


def _painel_metricas_principais(prefs):
    """(novo) 4 cards de topo - IBOVESPA/DÓLAR/DI/S&P 500 - mesma
    hierarquia "VISÃO GERAL DO MERCADO" do protótipo. Reaproveita
    exatamente as mesmas fontes já usadas em ui/visao_geral.py:
    _painel_mercado_agora (obter_cotacao_indice, data/macro.py:obter_cdi,
    obter_mercados_globais) - nenhuma chamada nova."""
    st.markdown('<div class="painel-titulo">VISÃO GERAL DO MERCADO</div>', unsafe_allow_html=True)
    ibov = obter_cotacao_indice("IBOVESPA", config.SIMBOLO_IBOVESPA)
    dolar = obter_cotacao_indice("DÓLAR", "USDBRL=X")

    cdi_df = obter_cdi(dias_historico=5)
    cdi_atual = float(cdi_df["cdi_anualizado_pct"].iloc[-1]) if cdi_df is not None and not cdi_df.empty else None
    # None (nunca 0.0) com so' 1 leitura disponivel - sem dado suficiente
    # pra comparar, o card mostra "SEM DADO" (ver _card_metrica), nunca
    # uma variacao inventada (mesmo criterio de ui/visao_geral.py).
    cdi_variacao = None
    if cdi_df is not None and len(cdi_df) >= 2:
        anterior = float(cdi_df["cdi_anualizado_pct"].iloc[-2])
        cdi_variacao = cdi_atual - anterior if cdi_atual is not None else None

    globais = {g["nome"]: g for g in obter_mercados_globais()}
    sp500 = globais.get("S&P 500")

    with st.container(key="mercado_metricas_cols"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _card_metrica(
                "IBOVESPA", None if ibov.get("erro") else ibov["preco"],
                None if ibov.get("erro") else ibov["variacao_pct"], prefs, 0,
                rotulo_cotacao_em_cache(ibov), "Índice · pontos",
            )
        with c2:
            _card_metrica(
                "DÓLAR / BRL", None if dolar.get("erro") else dolar["preco"],
                None if dolar.get("erro") else dolar["variacao_pct"], prefs, 2,
                rotulo_cotacao_em_cache(dolar), "Câmbio · R$",
            )
        with c3:
            _card_metrica("DI (CDI anual.)", cdi_atual, cdi_variacao, prefs, 2, None,
                          "Taxa indicativa", unidade_variacao=" p.p.")
        with c4:
            _card_metrica(
                "S&P 500", sp500["preco"] if sp500 else None,
                sp500["variacao_pct"] if sp500 else None, prefs, 0, None, "Mercado global",
            )


def _painel_leitura_rapida(prefs):
    """(novo) LEITURA RÁPIDA - NÃO é um resumo gerado por IA (ver TAREFA:
    sem fonte real pra prosa editorial aqui): é só interpolação de número
    real (cotação do Ibovespa, maior alta do dia, pior setor do dia,
    status B3 oficial/fallback + cotação em cache) num template fixo,
    reaproveitando exatamente as mesmas funções já usadas no resto desta
    aba (obter_cotacao_indice/obter_altas_baixas/obter_desempenho_
    setorial/obter_composicao_oficial) - nenhum texto fixo nem dado
    inventado, nenhuma chamada nova."""
    st.markdown('<div class="painel-titulo">LEITURA RÁPIDA</div>', unsafe_allow_html=True)

    ibov = obter_cotacao_indice("IBOVESPA", config.SIMBOLO_IBOVESPA)
    if ibov.get("erro"):
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Cotação do Ibovespa indisponível no "
            "momento - leitura rápida depende dela.</div>",
            unsafe_allow_html=True,
        )
        return

    variacao = ibov["variacao_pct"]
    cls_dir = "alta" if variacao >= 0 else "baixa"
    if variacao > 0.15:
        direcao = "Pressão compradora"
    elif variacao < -0.15:
        direcao = "Pressão vendedora"
    else:
        direcao = "Sessão estável"
    st.markdown(
        f"<div class='cinza' style='font-size:0.66rem;'>DIREÇÃO DO ÍNDICE</div>"
        f"<div style='font-size:0.92rem; font-weight:700; margin-top:0.15rem;'>{direcao} "
        f"<span class='{cls_dir}'>{_fmt_pct(variacao, prefs)}</span></div>"
        f"<div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>Ibovespa "
        f"{'em alta' if variacao >= 0 else 'em queda'} no pregão de hoje.</div>",
        unsafe_allow_html=True,
    )

    altas, _baixas = obter_altas_baixas(1, "dia")
    if altas:
        p = altas[0]
        nome = _nome_papel(p["ticker"])
        st.markdown(
            f"<div style='border-top:1px solid var(--borda); padding-top:0.5rem; margin-top:0.5rem;'>"
            f"<div class='cinza' style='font-size:0.66rem;'>DESTAQUE POSITIVO</div>"
            f"<div style='margin-top:0.15rem;'><b class='alta'>{html.escape(p['ticker'])} "
            f"{_fmt_pct(p['variacao_pct'], prefs)}</b>"
            + (f" <span class='cinza' style='font-size:0.74rem;'>· {html.escape(nome)}</span>" if nome else "")
            + "</div><div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>"
            + "Maior alta do dia no Ibovespa.</div></div>",
            unsafe_allow_html=True,
        )

    setores = obter_desempenho_setorial("dia")
    if setores:
        pior = setores[-1]
        cls_setor = "alta" if pior["variacao_media_pct"] >= 0 else "baixa"
        st.markdown(
            f"<div style='border-top:1px solid var(--borda); padding-top:0.5rem; margin-top:0.5rem;'>"
            f"<div class='cinza' style='font-size:0.66rem;'>PONTO DE ATENÇÃO</div>"
            f"<div style='margin-top:0.15rem;'><b class='{cls_setor}'>{html.escape(pior['setor'])} "
            f"{_fmt_pct(pior['variacao_media_pct'], prefs)}</b></div>"
            f"<div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>Setor com a pior "
            f"variação média no dia ({pior['n_papeis']} papel(éis)) - verificar se é movimento "
            f"concentrado ou disseminado.</div></div>",
            unsafe_allow_html=True,
        )

    composicao = obter_composicao_oficial()
    status_cache = rotulo_cotacao_em_cache(ibov)
    if composicao and not status_cache:
        cls_qualidade, rotulo_qualidade = "alta", "Dados ao vivo"
        detalhe_qualidade = f"Composição oficial da B3 ({len(composicao)} papéis) · cotação ao vivo."
    elif composicao:
        cls_qualidade, rotulo_qualidade = "cinza", "Atenção à fonte"
        detalhe_qualidade = f"Composição oficial da B3, mas {status_cache.lower()}."
    else:
        cls_qualidade, rotulo_qualidade = "cinza", "Atenção à fonte"
        detalhe_qualidade = (
            f"B3 indisponível no momento - usando lista curada de fallback "
            f"({len(config.IBOVESPA_SETORES)} papéis)."
        )
    st.markdown(
        f"<div style='border-top:1px solid var(--borda); padding-top:0.5rem; margin-top:0.5rem;'>"
        f"<div class='cinza' style='font-size:0.66rem;'>QUALIDADE DOS DADOS</div>"
        f"<div class='{cls_qualidade}' style='margin-top:0.15rem;'>● {rotulo_qualidade}</div>"
        f"<div class='cinza' style='font-size:0.68rem; margin-top:0.1rem;'>{detalhe_qualidade}</div></div>",
        unsafe_allow_html=True,
    )


def _linha_destaque(rotulo: str, ticker: str | None, tema: dict, linha1_html: str, porque: str, catalisador: str | None):
    """Uma linha do painel DESTAQUES: monograma (ou espaço reservado,
    quando o destaque é setorial, não de 1 ticker) | rótulo do critério |
    linha principal | motivo em 1 frase | catalisador opcional (só
    quando há evidência estrutural - ver _painel_destaques)."""
    badge = _badge_ticker(ticker, tema) if ticker else (
        "<span style='display:inline-block; width:1.5rem; min-width:1.5rem;'></span>"
    )
    extra = (
        f"<div class='cinza' style='font-size:0.62rem; margin-top:0.15rem; "
        f"border-top:1px dashed var(--borda); padding-top:0.15rem;'>{catalisador}</div>"
        if catalisador else ""
    )
    st.markdown(
        f"<div style='display:flex; gap:0.4rem; align-items:flex-start; margin-bottom:0.5rem;'>{badge}"
        f"<div style='flex:1; min-width:0;'>"
        f"<div class='cinza' style='font-size:0.58rem; letter-spacing:0.02em;'>{html.escape(rotulo)}</div>"
        f"<div style='font-size:0.78rem; font-weight:700; margin-top:0.08rem;'>{linha1_html}</div>"
        f"<div style='font-size:0.66rem; color:#a8a8a8; margin-top:0.1rem;'>{html.escape(porque)}</div>"
        f"{extra}</div></div>",
        unsafe_allow_html=True,
    )


def _painel_destaques(prefs):
    """DESTAQUES (novo, redesign do Painel em grade, 2026-10-27): 3 itens
    com critério explícito (maior alta do dia / maior volume financeiro /
    pior setor do dia) - reaproveita exatamente as mesmas fontes já
    buscadas em _painel_leitura_rapida/_painel_mais_negociados/
    _painel_setorial, nenhuma consulta nova. Quando o ticker do destaque
    também aparece no pool de notícias já buscado ao lado (NOTÍCIAS,
    data/news.py:obter_top_mercado_tudo, campo 'tickers' estruturado -
    ver ui/news_tab.py:_tickers_do_item), sinaliza a menção: é um [FATO]
    estrutural (o mesmo ticker aparece nas duas fontes), nunca uma causa
    inventada pro movimento - por isso o texto é sempre "menção, não
    causa comprovada", nunca "por causa de"."""
    st.markdown('<div class="painel-titulo">DESTAQUES</div>', unsafe_allow_html=True)
    tema = _tema_atual(prefs)

    noticias = obter_top_mercado_tudo("TODOS") or []
    tickers_nas_noticias = {t for n in noticias for t in _tickers_do_item(n)}

    def _catalisador(ticker: str) -> str | None:
        if ticker in tickers_nas_noticias:
            return "📰 Também citado em Notícias (ver ao lado) — menção, não causa comprovada."
        return None

    itens_renderizados = 0

    altas, _baixas = obter_altas_baixas(1, "dia")
    if altas:
        p = altas[0]
        nome = _nome_papel(p["ticker"])
        linha1 = (
            f"<span style='color:var(--destaque);'>{html.escape(p['ticker'])}</span> "
            f"<span class='alta'>{_fmt_pct(p['variacao_pct'], prefs)}</span>"
            + (f" <span class='cinza' style='font-size:0.68rem; font-weight:400;'>· {html.escape(nome)}</span>" if nome else "")
        )
        _linha_destaque(
            "MAIOR ALTA DO DIA", p["ticker"], tema, linha1,
            "Maior variação positiva do Ibovespa na janela DIA.", _catalisador(p["ticker"]),
        )
        itens_renderizados += 1

    negociados = obter_mais_negociados(1)
    if negociados:
        p = negociados[0]
        linha1 = (
            f"<span style='color:var(--destaque);'>{html.escape(p['ticker'])}</span> "
            f"R$ {config.formatar_numero(p['volume_financeiro'] / 1_000_000, 1, prefs['formato_numerico'])} mi"
        )
        _linha_destaque(
            "MAIOR VOLUME FINANCEIRO", p["ticker"], tema, linha1,
            "Maior volume negociado no dia — proxy de atenção do mercado.", _catalisador(p["ticker"]),
        )
        itens_renderizados += 1

    setores = obter_desempenho_setorial("dia")
    if setores:
        pior = setores[-1]
        cls_setor = "alta" if pior["variacao_media_pct"] >= 0 else "baixa"
        linha1 = f"<span class='{cls_setor}'>{html.escape(pior['setor'])} {_fmt_pct(pior['variacao_media_pct'], prefs)}</span>"
        _linha_destaque(
            "PONTO DE ATENÇÃO SETORIAL", None, tema, linha1,
            f"Pior variação média do dia entre os setores ({pior['n_papeis']} papel(éis)).", None,
        )
        itens_renderizados += 1

    if itens_renderizados == 0:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Sem dado suficiente para destacar agora.</div>", unsafe_allow_html=True)
        return

    _nota_contextual(
        "LEITURA",
        "critério de cada item é explícito (variação/volume/média setorial) — observação, não recomendação.",
    )


def _painel_noticias_resumo(prefs):
    """NOTÍCIAS · TOP 3 - renderer PRÓPRIO (não `ui.news_tab._renderizar_
    lista`), mesma troca e mesmo motivo já validados em ui/visao_geral.py
    (grade fixa, 2026-10-27): aquele componente é "wire denso" (st.columns
    de peso fixo pra selo/hora/manchete/fonte, pensado pra largura cheia
    de TOP MERCADO/EQUITY) - numa coluna de ~33% da grade do Painel o selo
    sobrepunha o início da manchete (mesmo bug real já achado lá). Esta
    versão é 1 bloco HTML empilhado por item - mesma fonte/mesmo recorte
    de sempre (data/news.py:obter_top_mercado_tudo), link/fonte/horário
    preservados, nunca manchete inventada. 3 (não 4): coluna mais estreita
    que a versão anterior (aba inteira) - 1 manchete menos evita que este
    módulo fique desproporcionalmente mais alto que Desempenho Setorial/
    Mais Negociados ao lado."""
    _injetar_css_news()
    st.markdown(
        '<div class="painel-titulo">NOTÍCIAS <span class="cinza" '
        'style="font-size:0.68rem;font-weight:400;">TOP 3</span></div>',
        unsafe_allow_html=True,
    )
    itens = obter_top_mercado_tudo("TODOS")
    if not itens:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>Sem notícias disponíveis.</div>", unsafe_allow_html=True)
        return
    watchlist = prefs.get("watchlist") or []
    blocos = []
    for n in itens[:_QTD_NOTICIAS_MERCADO]:
        classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
        tooltip = html.escape(_tooltip_regras(n))
        titulo = html.escape(_truncar(n["titulo"], 68))
        tickers = _tickers_do_item(n)
        tags_ticker = "".join(
            f"<span class='w-ticker-tag{' w-ticker-tag-watch' if t in watchlist else ''}' "
            f"style='margin-left:0.3rem;'>{html.escape(t)}</span>"
            for t in tickers[:3]
        )
        blocos.append(
            f"<div style='padding:0.35rem 0; border-bottom:1px solid var(--borda);'>"
            f"<span class='selo-tag {classe_selo}' title='{tooltip}' style='font-size:0.58rem;'>"
            f"{_texto_tag(n)}</span>{tags_ticker}"
            f"<a href='{n['link']}' target='_blank' style='display:block; margin-top:0.25rem; "
            f"font-size:0.72rem; font-weight:600; color:var(--neutro); text-decoration:none; "
            f"line-height:1.3;'>{titulo}</a>"
            f"<div class='cinza' style='font-size:0.6rem; margin-top:0.12rem;'>"
            f"{_fmt_hora(n['data'])} · {_plural_fontes(n['fontes_count'])}</div></div>"
        )
    st.markdown("".join(blocos), unsafe_allow_html=True)


def _painel_termometro(prefs):
    st.markdown('<div class="painel-titulo">MERCADO</div>', unsafe_allow_html=True)
    composicao = obter_composicao_oficial()
    if composicao:
        st.caption(f"Composição oficial do Ibovespa, direto da B3 ({len(composicao)} papéis). Ver MANUAL.md.")
    else:
        st.caption(
            "B3 indisponível no momento - usando lista curada de fallback "
            f"({len(config.IBOVESPA_SETORES)} papéis). Ver MANUAL.md."
        )
    janela = _seletor_janela("termometro")
    term = obter_termometro(janela)
    if term["total"] == 0:
        st.warning("Dados de mercado indisponíveis no momento (fonte fora do ar ou bloqueada).")
        return False

    tema = _tema_atual(prefs)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div style='text-align:center;'><div class='alta' style='font-size:1.6rem; font-weight:700;'>{term['alta']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>EM ALTA</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='text-align:center;'><div class='baixa' style='font-size:1.6rem; font-weight:700;'>{term['baixa']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>EM BAIXA</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div style='text-align:center;'><div class='neutro' style='font-size:1.6rem; font-weight:700;'>{term['estavel']}</div>"
            f"<div class='cinza' style='font-size:0.7rem;'>ESTÁVEIS</div></div>",
            unsafe_allow_html=True,
        )

    pct_alta = term["alta"] / term["total"] * 100
    pct_baixa = term["baixa"] / term["total"] * 100
    pct_estavel = 100 - pct_alta - pct_baixa
    st.markdown(
        f"<div style='display:flex; height:8px; margin-top:0.6rem; overflow:hidden;'>"
        f"<div style='width:{pct_alta:.1f}%; background:{tema['alta']};'></div>"
        f"<div style='width:{pct_estavel:.1f}%; background:{tema['cinza']};'></div>"
        f"<div style='width:{pct_baixa:.1f}%; background:{tema['baixa']};'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    return True


def _linha_ranking(p: dict, campo: str, prefs: dict, tema: dict):
    """Uma linha do ranking: monograma (substituto leve de logo, ver
    _badge_ticker) | botao do ticker (navega pra EQUITY, mesmo mecanismo
    da busca global) | nome + retorno.

    REDESENHADO (grade do Painel, 2026-10-27): a versao anterior tinha
    4 colunas (numero/ticker/nome+valor/barra horizontal) pensadas pra
    largura cheia da aba. Nesta largura nova (1/3 da pagina - a grade
    tem Altas/Baixas ao lado de Destaques e Mapa do Mercado, nao mais a
    aba inteira) 4 colunas arriscava o mesmo "wire denso" ja encontrado
    em VISAO GERAL (botao/texto espremido ao ponto de sobrepor). Numero
    e barra eram decorativos (a ordem ja' vem certa da API; a barra so'
    repetia visualmente o % que a coluna seguinte ja mostra em texto) -
    cortados pra abrir espaco pro monograma, pedido explicito do
    Rodrigo. Botao do ticker (unico elemento interativo da linha) e'
    preservado - clicar nele continua abrindo ANALISES > Empresas."""
    valor = p[campo]
    cor_var = "var(--alta)" if valor >= 0 else "var(--baixa)"
    nome = _nome_papel(p["ticker"])

    col_badge, col_ticker, col_nome_valor = st.columns(
        [0.14, 0.32, 0.54], gap="small", vertical_alignment="center",
    )
    with col_badge:
        st.markdown(_badge_ticker(p["ticker"], tema), unsafe_allow_html=True)
    with col_ticker:
        st.button(
            p["ticker"], key=f"rank_ticker_{p['ticker']}", width="stretch",
            on_click=_ir_para_equity, args=(p["ticker"], prefs),
            help=f"Abrir {p['ticker']} em ANÁLISES › Empresas",
        )
    with col_nome_valor:
        st.markdown(
            f"<div class='rank-nome-valor'><span class='rank-nome' title='{html.escape(nome or p['ticker'])}'>"
            f"{html.escape(nome) if nome else '&nbsp;'}</span>"
            f"<span class='rank-valor' style='color:{cor_var};'>{_fmt_pct(valor, prefs)}</span></div>",
            unsafe_allow_html=True,
        )


def _subtitulo_ranking(texto: str):
    st.markdown(f"<div class='rank-subtitulo'>{texto}</div>", unsafe_allow_html=True)


def _nota_contextual(tag: str, texto: str):
    """Anotacao curta de inteligencia contextual, com rotulo explicito
    [FATO] (contagem/comparacao computada direto do dado ja buscado,
    sem interpretacao) ou [LEITURA] (framing qualitativo - mesmo
    criterio ja usado em _painel_leitura_rapida). Pedido explicito do
    Rodrigo (redesign do Painel, 2026-10-27): diferenciar fato de
    interpretacao, nunca misturar os dois sem rotulo."""
    cor = "var(--cinza)" if tag == "FATO" else "var(--destaque)"
    st.markdown(
        f"<div style='margin-top:0.4rem; padding-top:0.35rem; border-top:1px solid var(--borda); "
        f"font-size:0.66rem; color:#a8a8a8;'><b style='color:{cor};'>[{tag}]</b> {texto}</div>",
        unsafe_allow_html=True,
    )


def _concentracao_setorial(papeis: list, rotulo_grupo: str) -> str | None:
    """[FATO] computado sobre o proprio pool ja buscado (nenhuma consulta
    nova): quando mais da metade de um grupo (altas OU baixas) pertence
    ao MESMO setor, sinaliza concentracao - sem isso o usuario nao sabe
    se um movimento e' um fenomeno setorial ou so' papeis isolados. Nunca
    aparece quando nao ha' concentracao de verdade (nunca um texto
    generico so' pra nao parecer vazio - regra explicita do Rodrigo)."""
    if len(papeis) < 2:
        return None
    contagem: dict = {}
    for p in papeis:
        contagem[p["setor"]] = contagem.get(p["setor"], 0) + 1
    setor_top, qtd_top = max(contagem.items(), key=lambda kv: kv[1])
    if qtd_top < 2 or qtd_top <= len(papeis) / 2:
        return None
    return (
        f"{qtd_top} de {len(papeis)} {rotulo_grupo} são do setor {html.escape(setor_top)} — "
        f"movimento concentrado, não disseminado."
    )


def _painel_altas_baixas(prefs):
    st.markdown('<div class="painel-titulo">MAIORES ALTAS/BAIXAS</div>', unsafe_allow_html=True)

    # cabecalho do indice (IBOVESPA + cotacao + variacao) - mesma funcao ja
    # usada no header/VISAO GERAL (data/prices.py:obter_cotacao_indice),
    # so' reaproveitada aqui, nenhuma chamada nova a fonte externa alem da
    # que ja existia.
    ibov = obter_cotacao_indice("IBOVESPA", config.SIMBOLO_IBOVESPA)
    if not ibov.get("erro"):
        cls_ibov = "alta" if ibov["variacao_pct"] >= 0 else "baixa"
        st.markdown(
            f"<div class='rank-header-indice'>"
            f"<span class='rank-header-indice-nome'>IBOVESPA</span>"
            f"<span class='rank-header-indice-valor'>{config.formatar_numero(ibov['preco'], 0, prefs['formato_numerico'])}</span>"
            f"<span class='{cls_ibov}' style='font-weight:600;'>{_fmt_pct(ibov['variacao_pct'], prefs)}</span>"
            + (f"<span class='cinza' style='font-size:0.62rem;'>{rotulo_cotacao_em_cache(ibov)}</span>"
               if rotulo_cotacao_em_cache(ibov) else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    # linha de controles inline (efeito imediato, sem formulario separado) -
    # periodo e quantidade por grupo sao controles curtos (3-4 opcoes
    # cada), ficam juntos numa linha compacta. O filtro de SETOR vai pra
    # LINHA PROPRIA, largura total (2a passada da auditoria visual
    # 2026-10-17, achado especifico: config.IBOVESPA_SETORES tem 21
    # setores unicos + "TODOS" = 22 pills, varias com rotulo longo -
    # "Bancos e Serviços Financeiros" (29 caracteres), "Bens de Capital e
    # Industrial" (28) - apertado nos 56% de largura que sobravam ao lado
    # de periodo/qtd (como era antes), essas pills quebravam em varias
    # linhas e deixavam aquela coluna MUITO mais alta que periodo/qtd ao
    # lado - um filtro visualmente desproporcional em relacao aos vizinhos
    # na mesma linha. Label "SETOR" explicito acima, mesmo padrao ja usado
    # em CVM/CALENDARIO (rotulo cinza pequeno acima do grupo de pills).
    col_periodo, col_qtd = st.columns(2, gap="small")
    with col_periodo:
        janela = _seletor_janela("altas_baixas")
    with col_qtd:
        padrao_qtd, mem_qtd = _escolha_estavel_mercado("altas_baixas_qtd", _QTD_RANKING_OPCOES, _QTD_RANKING_PADRAO)
        sel_qtd = st.segmented_control(
            "Qtd/grupo", _QTD_RANKING_OPCOES, default=padrao_qtd,
            label_visibility="collapsed", key="mercado_altas_baixas_qtd",
        )
        qtd_rotulo = sel_qtd or padrao_qtd
        st.session_state[mem_qtd] = qtd_rotulo
        qtd = int(qtd_rotulo)

    campo = CAMPO_VARIACAO_POR_JANELA[janela]
    altas_pool, baixas_pool = obter_altas_baixas(_POOL_RANKING, janela)
    setores_disponiveis = ["TODOS"] + sorted({p["setor"] for p in altas_pool + baixas_pool})
    st.markdown(
        "<div class='cinza' style='font-size:0.68rem; margin:0.4rem 0 0.15rem 0;'>SETOR</div>",
        unsafe_allow_html=True,
    )
    padrao_setor, mem_setor = _escolha_estavel_mercado("altas_baixas_setor", setores_disponiveis, "TODOS")
    sel_setor = st.pills(
        "Setor", setores_disponiveis, default=padrao_setor, selection_mode="single",
        label_visibility="collapsed", key="mercado_altas_baixas_setor",
    )
    setor = sel_setor or padrao_setor
    st.session_state[mem_setor] = setor

    if setor != "TODOS":
        altas_pool = [p for p in altas_pool if p["setor"] == setor]
        baixas_pool = [p for p in baixas_pool if p["setor"] == setor]

    composicao = obter_composicao_oficial()
    total_universo = len(composicao) if composicao else len(config.IBOVESPA_SETORES)
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0 0.5rem 0;'>"
        f"UNIVERSO: IBOVESPA · {total_universo} PAPÉIS"
        + (f" · SETOR: {setor}" if setor != "TODOS" else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    altas = altas_pool[:qtd]
    baixas = list(reversed(baixas_pool[:qtd]))  # menor queda primeiro, maior queda por ultimo (mesma ordem do terminal de referencia)

    if not altas and not baixas:
        rotulo_setor = "" if setor == "TODOS" else f" no setor {setor}"
        st.markdown(f"<div class='cinza' style='font-size:0.78rem;'>Nenhum papel com dado válido{rotulo_setor} nesta janela.</div>", unsafe_allow_html=True)
        return

    tema = _tema_atual(prefs)
    with st.container(key="mercado_ranking_lista"):
        if altas:
            _subtitulo_ranking("MAIORES ALTAS")
            for p in altas:
                _linha_ranking(p, campo, prefs, tema)
        if baixas:
            _subtitulo_ranking("MAIORES BAIXAS")
            for p in baixas:
                _linha_ranking(p, campo, prefs, tema)

    # inteligencia contextual (pedido explicito do Rodrigo, redesign do
    # Painel 2026-10-27): concentracao setorial computada no MESMO pool
    # ja buscado acima - prioriza o grupo com mais papeis (normalmente o
    # filtrado/mais relevante na tela), nunca os dois textos juntos pra
    # nao virar um bloco grande.
    nota = _concentracao_setorial(baixas, "maiores baixas") or _concentracao_setorial(altas, "maiores altas")
    if nota:
        _nota_contextual("FATO", nota)


def _painel_mais_negociados(prefs):
    st.markdown('<div class="painel-titulo">MAIS NEGOCIADOS</div>', unsafe_allow_html=True)
    st.caption("Por volume financeiro estimado no dia (preço × volume em ações) - proxy de liquidez/atenção do mercado.")
    negociados = obter_mais_negociados(10)
    if not negociados:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    # ticker vira um st.button de verdade (on_click=_ir_para_equity, mesmo
    # mecanismo ja' usado no ranking de altas/baixas acima) - achado real
    # da auditoria 360 (docs/auditoria-redesign-360.md): antes era so'
    # <td>{ticker}</td> cru dentro de uma tabela HTML, sem nenhum jeito de
    # ir direto pro ticker em EQUITY a partir daqui.
    #
    # margin-bottom MAIOR que o row-gap global entre colunas empilhadas
    # (0.7rem, style.css, breakpoint 640px) - mesmo bug real encontrado e
    # corrigido no painel MINHA WATCHLIST (ui/visao_geral.py, auditoria
    # 2026-10-18): sem isso, abaixo de 640px as 3 colunas quebram
    # empilhadas e a linha de volume/variacao de UM ticker fica mais perto
    # do botao do ticker SEGUINTE do que do seu proprio, ambiguo sobre a
    # quem pertence.
    st.markdown(
        "<style>div[class*='st-key-mn_linha_']{margin-bottom:1.1rem;}</style>",
        unsafe_allow_html=True,
    )
    tema = _tema_atual(prefs)
    for p in negociados:
        with st.container(key=f"mn_linha_{p['ticker']}"):
            col_badge, col_ticker, col_volume, col_var = st.columns(
                [0.32, 0.9, 1.3, 1], vertical_alignment="center",
            )
            with col_badge:
                st.markdown(_badge_ticker(p["ticker"], tema), unsafe_allow_html=True)
            with col_ticker:
                st.button(
                    p["ticker"], key=f"mn_ticker_{p['ticker']}", width="stretch",
                    on_click=_ir_para_equity, args=(p["ticker"], prefs),
                    help=f"Abrir {p['ticker']} em ANÁLISES › Empresas",
                )
            with col_volume:
                st.markdown(
                    f"<div class='neutro' style='text-align:right; font-size:0.8rem;'>"
                    f"R$ {config.formatar_numero(p['volume_financeiro'] / 1_000_000, 1, prefs['formato_numerico'])} mi</div>",
                    unsafe_allow_html=True,
                )
            with col_var:
                cls = "alta" if p["variacao_pct"] >= 0 else "baixa"
                st.markdown(
                    f"<div class='{cls}' style='text-align:right; font-size:0.8rem;'>{_fmt_pct(p['variacao_pct'], prefs)}</div>",
                    unsafe_allow_html=True,
                )


def _painel_setorial(prefs):
    st.markdown('<div class="painel-titulo">DESEMPENHO SETORIAL</div>', unsafe_allow_html=True)
    janela = _seletor_janela("setorial")
    setores = obter_desempenho_setorial(janela)
    if not setores:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    tema = _tema_atual(prefs)
    df = pd.DataFrame(setores)
    cores = [tema["alta"] if v >= 0 else tema["baixa"] for v in df["variacao_media_pct"]]
    fig = go.Figure(go.Bar(
        x=df["variacao_media_pct"], y=df["setor"], orientation="h",
        marker_color=cores, text=df["variacao_media_pct"].map(lambda v: _fmt_pct(v, prefs)),
        textposition="outside", cliponaxis=False,
    ))
    # automargin=True (achado real, Playwright a 768/1280px): sem isso o
    # nome de setor mais comprido ("Petróleo e Gás", "Materiais Básicos")
    # cortava na borda ESQUERDA do painel ("'etróleo e Gás") - o
    # margin.l:10 fixo de _layout_grafico_escuro nunca foi pensado pra
    # reservar espaco pro rotulo de categoria (so' pra folga extra alem
    # dele); automargin manda o Plotly calcular esse espaco de verdade a
    # partir do texto mais largo, em vez de confiar num numero fixo.
    fig.update_yaxes(autorange="reversed", automargin=True)
    _layout_grafico_escuro(fig, tema, altura=max(240, 28 * len(setores)))
    # BUG REAL confirmado em screenshot + medicao de DOM (Playwright
    # contra o app rodando de verdade, 2026-10-09): mesmo com
    # automargin=True (acima), dentro de um painel redimensionavel do
    # workspace (MERCADO e' a aba piloto desse sistema) o container do
    # grafico as vezes NAO cresce o suficiente pra acomodar a margem que
    # o automargin calculou - confirmado medindo getBoundingClientRect:
    # o texto do rotulo mais comprido ("Bancos e Serviços Financeiros")
    # renderizava ~52px pra ESQUERDA do proprio container do grafico,
    # cortado pelo overflow:hidden nativo do Plotly. Margem esquerda
    # MINIMA explicita (estimativa de largura de caractere da fonte
    # monoespacada do terminal) garante espaco reservado de verdade,
    # independente do automargin conseguir redimensionar o container.
    margem_l = max(60, 7.3 * max(len(s) for s in df["setor"]) + 16)
    # margem direita fixa (nao so' folga de x-range - testado e
    # descartado: aumentar so' o range ESCALA a barra E o espaco vazio
    # juntos, mas o texto do rotulo "+X,XX%" tem largura em PIXELS fixa
    # (nao encolhe com a escala), entao em telas estreitas um range
    # maior sozinho nunca fecha a conta - confirmado ainda cortando
    # mesmo com folga de 110% sobre o maior valor) - 50px e' espaco de
    # sobra real pro rotulo mais largo possivel aqui ("+99,99%").
    fig.update_layout(margin=dict(l=margem_l, r=50))
    # achado real (2026-10-08, Playwright a 390px): o rotulo "+X,XX%" de
    # cada barra (textposition="outside") cortava na borda do grafico em
    # telas estreitas - o container fica tao estreito (~300px uteis,
    # descontado o espaco dos nomes de setor no eixo Y) que o autorange
    # padrao do eixo X nao sobra espaco pro texto depois da ultima barra.
    # Folga de 35% sobre o maior valor absoluto (pra ambos os lados, ja
    # que setor pode estar em alta OU baixa) da' espaco extra pra barra
    # nao encostar na borda; cliponaxis=False acima + margem direita
    # fixa (comentario acima) e' quem realmente garante espaco pro
    # texto do rotulo em si.
    maior_abs = max(df["variacao_media_pct"].abs().max(), 0.5)
    fig.update_xaxes(range=[-maior_abs * 1.35, maior_abs * 1.35])
    chave = graficos.zoom_key("mercado_setorial", janela)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)

    # inteligencia contextual (pedido explicito do Rodrigo, redesign do
    # Painel 2026-10-27): divergencia do setor mais destoante vs o proprio
    # Ibovespa - so' na janela DIA, unica em que a cotacao do indice
    # (obter_cotacao_indice) e' comparavel 1:1 com a variacao MEDIA do
    # setor (SEMANA/MES do setor nao tem um equivalente direto aqui sem
    # buscar historico novo do indice, fora do escopo desta etapa). Limiar
    # de 0.5pp evita apontar "divergencia" quando tudo so' acompanha o
    # indice de perto (nunca um padrao inventado quando nao ha').
    # `janela` já é a chave interna ("dia"/"semana"/"mes") devolvida por
    # _seletor_janela - indexar o dicionário de RÓTULOS com ela dava
    # KeyError: 'dia' e derrubava a aba MERCADO inteira (29/10/2026)
    if janela == "dia":
        ibov = obter_cotacao_indice("IBOVESPA", config.SIMBOLO_IBOVESPA)
        if not ibov.get("erro"):
            destaque_divergencia = max(setores, key=lambda s: abs(s["variacao_media_pct"] - ibov["variacao_pct"]))
            diferenca = destaque_divergencia["variacao_media_pct"] - ibov["variacao_pct"]
            if abs(diferenca) >= 0.5:
                _nota_contextual(
                    "FATO",
                    f"{html.escape(destaque_divergencia['setor'])} diverge do Ibovespa: "
                    f"{_fmt_pct(destaque_divergencia['variacao_media_pct'], prefs)} no setor vs. "
                    f"{_fmt_pct(ibov['variacao_pct'], prefs)} no índice.",
                )


def _cor_treemap(variacao_pct: float, limite: float, tema: dict) -> str:
    """Interpola linearmente entre baixa/cinza/alta (mesma logica de 3
    pontas de _painel_setorial, so' que devolve a cor HEX final em vez de
    deixar o Plotly interpolar - necessario pra colorir os nos manualmente
    (ver _painel_treemap: go.Treemap direto, nao px.treemap - ver
    comentario la' do motivo)."""
    def _hex_pra_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def _rgb_pra_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))

    t = max(-1.0, min(1.0, variacao_pct / limite)) if limite else 0.0
    c_baixa, c_cinza, c_alta = (_hex_pra_rgb(tema[k]) for k in ("baixa", "cinza", "alta"))
    if t >= 0:
        a, b, f = c_cinza, c_alta, t
    else:
        a, b, f = c_cinza, c_baixa, -t
    return _rgb_pra_hex(tuple(a[i] + (b[i] - a[i]) * f for i in range(3)))


def _tempo_relativo(dt: datetime | None) -> str:
    """'há Xmin'/'há Xh' a partir de um datetime real (UTC) - nunca um
    rótulo fixo tipo 'agora': None (momento indisponível) vira texto
    explícito, nunca um horário inventado."""
    if dt is None:
        return "horário indisponível"
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta_min = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except (TypeError, ValueError):
        return "horário indisponível"
    if delta_min < 1:
        return "agora mesmo"
    if delta_min < 60:
        return f"há {delta_min}min"
    return f"há {delta_min // 60}h{delta_min % 60:02d}"


def _painel_treemap(prefs, altura_px: int = _ALTURA_TREEMAP_PX):
    st.markdown('<div class="painel-titulo">MAPA DO MERCADO</div>', unsafe_allow_html=True)
    st.caption("Tamanho do retângulo = volume financeiro no dia · cor = variação % no dia.")
    papeis = [p for p in obter_panorama_ibovespa() if p["volume_financeiro"] > 0]
    if not papeis:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return

    rotulo_momento = _tempo_relativo(obter_momento_panorama())
    st.markdown(
        f"<div class='cinza' style='font-size:0.66rem; margin:-0.1rem 0 0.3rem 0;'>Atualizado {rotulo_momento} "
        f"· {len(papeis)} papéis</div>",
        unsafe_allow_html=True,
    )

    tema = _tema_atual(prefs)
    fmt = prefs["formato_numerico"]
    limite = max(max(abs(p["variacao_pct"]) for p in papeis), 0.5)

    # go.Treemap DIRETO (nao px.treemap): px.treemap gera automaticamente
    # os nos agregados de setor/raiz calculando sozinho um "color" pra
    # eles (media dos filhos) - em alguns casos essa agregacao automatica
    # vem NaN, e o texttemplate aplicado a TODO no (raiz/setor/ticker)
    # entao mostrava "+NaN%" nos blocos de setor/raiz (bug real relatado).
    # Construindo cada no a mao (ids/parents/values/colors/hovertext
    # explicitos, sem nada "automatico" do Plotly) elimina essa classe de
    # bug de vez, alem de dar controle total sobre o hover (o hover
    # padrao do px.treemap mostra os nomes tecnicos das colunas, tipo
    # "labels=MGLU3, tamanho=204910656.2, parent=Varejo" - tambem
    # reportado como problema).
    por_setor: dict = {}
    for p in papeis:
        por_setor.setdefault(p["setor"], []).append(p)

    ids, labels, parents, values, colors, textos, hovertextos = [], [], [], [], [], [], []
    # medias por setor guardadas pra' inteligencia contextual (nota [FATO]
    # no fim da funcao) - mesma media_setor ja calculada abaixo pra' colorir
    # o bloco, nenhuma conta nova.
    medias_setor: dict = {}

    ids.append("IBOVESPA"); labels.append("IBOVESPA"); parents.append("")
    values.append(sum(p["volume_financeiro"] for p in papeis))
    colors.append(tema["cinza"]); textos.append("")
    hovertextos.append(f"<b>IBOVESPA</b><br>{len(papeis)} papéis no mapa")

    for setor, papeis_setor in por_setor.items():
        id_setor = f"IBOVESPA/{setor}"
        volume_setor = sum(p["volume_financeiro"] for p in papeis_setor)
        variacao_media_setor = sum(p["variacao_pct"] for p in papeis_setor) / len(papeis_setor)
        medias_setor[setor] = variacao_media_setor
        ids.append(id_setor); labels.append(setor); parents.append("IBOVESPA")
        values.append(volume_setor)
        colors.append(_cor_treemap(variacao_media_setor, limite, tema))
        textos.append(setor)
        hovertextos.append(
            f"<b>{html.escape(setor)}</b><br>{len(papeis_setor)} papel(éis)<br>"
            f"Variação média: {config.formatar_numero(variacao_media_setor, 2, fmt)}%"
        )
        for p in papeis_setor:
            ids.append(f"{id_setor}/{p['ticker']}")
            labels.append(p["ticker"])
            parents.append(id_setor)
            values.append(p["volume_financeiro"])
            colors.append(_cor_treemap(p["variacao_pct"], limite, tema))
            textos.append(f"{p['ticker']}<br>{_fmt_pct(p['variacao_pct'], prefs)}")
            hovertextos.append(
                f"<b>{p['ticker']}</b><br>{html.escape(setor)}<br><br>"
                f"Variação: {_fmt_pct(p['variacao_pct'], prefs)}<br>"
                f"Preço: R$ {config.formatar_numero(p['preco'], 2, fmt)}<br>"
                f"Volume financeiro: R$ {config.formatar_numero(p['volume_financeiro'] / 1_000_000, 1, fmt)} mi"
            )

    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values,
        branchvalues="total",
        marker=dict(colors=colors, line=dict(width=1.5, color=tema["fundo"]), pad=dict(t=22, l=2, r=2, b=2)),
        text=textos, textinfo="text", textposition="middle center",
        textfont=dict(size=13, family="IBM Plex Mono"),
        # texto do bloco (ticker+%) e' SEMPRE o par real coletado (nunca
        # logo/imagem: o projeto nao tem nenhuma fonte legitima de logo
        # de empresa da B3 hoje - ver PROGRESSO.md - e inventar URL de
        # CDN de logo externo pra cada ticker violaria a mesma regra de
        # "nunca URL inventada" que o resto do painel ja segue. O
        # proprio ticker em destaque (textfont acima) E' o "fallback
        # elegante" pedido - aqui ele e' o estado normal, nao so' um
        # caso de erro.
        hovertext=hovertextos, hoverinfo="text",
        hovertemplate="%{hovertext}<extra></extra>",
        root_color=tema["fundo"],
    ))
    fig.update_layout(
        paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["neutro"], family="IBM Plex Mono", size=12),
        height=altura_px, margin=dict(l=4, r=4, t=4, b=4),
    )
    chave = graficos.zoom_key("mercado_treemap")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave)

    st.markdown(
        f"<div style='display:flex; align-items:center; gap:0.4rem; margin-top:0.3rem; font-size:0.68rem;' class='cinza'>"
        f"<span>{config.formatar_numero(-limite, 1, fmt)}%</span>"
        f"<div style='flex:1; height:6px; background:linear-gradient(90deg, {tema['baixa']}, {tema['cinza']}, {tema['alta']});'></div>"
        f"<span>+{config.formatar_numero(limite, 1, fmt)}%</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # inteligencia contextual (pedido explicito do Rodrigo, redesign do
    # Painel 2026-10-27): concentracao de setores em alta/baixa, computada
    # nas MESMAS medias_setor ja calculadas acima pra colorir o mapa -
    # nenhuma consulta nova. "2+ papeis caindo >3%" e' o mesmo limiar
    # qualitativo ja usado em _painel_leitura_rapida pra "pressao
    # vendedora" - nunca um padrao inventado quando nao ha'.
    n_alta = sum(1 for v in medias_setor.values() if v >= 0)
    setores_com_queda_relevante = [
        setor for setor, papeis_setor in por_setor.items()
        if sum(1 for p in papeis_setor if p["variacao_pct"] <= -3.0) >= 2
    ]
    partes_nota = [f"{n_alta} de {len(medias_setor)} setores em alta"]
    if len(setores_com_queda_relevante) == 1:
        partes_nota.append(f"{setores_com_queda_relevante[0]} é o único com 2+ papéis caindo acima de 3%")
    elif len(setores_com_queda_relevante) > 1:
        partes_nota.append(
            f"{len(setores_com_queda_relevante)} setores têm 2+ papéis caindo acima de 3% "
            f"({', '.join(setores_com_queda_relevante)})"
        )
    _nota_contextual("FATO", "; ".join(partes_nota) + ".")


def _painel_globais(prefs):
    st.markdown('<div class="painel-titulo">MERCADOS GLOBAIS</div>', unsafe_allow_html=True)
    globais = obter_mercados_globais()
    if not globais:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return
    partes = []
    for g in globais:
        cls = "alta" if g["variacao_pct"] >= 0 else "baixa"
        partes.append(
            f"<div style='min-width:9rem;'><span class='cinza' style='font-size:0.7rem;'>{g['nome']}</span><br>"
            f"<span class='neutro' style='font-size:0.85rem;'>{config.formatar_numero(g['preco'], 0, prefs['formato_numerico'])}</span> "
            f"<span class='{cls}' style='font-size:0.78rem;'>{_fmt_pct(g['variacao_pct'], prefs)}</span></div>"
        )
    st.markdown(
        "<div style='display:flex; flex-wrap:wrap; gap:1rem;'>" + "".join(partes) + "</div>",
        unsafe_allow_html=True,
    )


# TERMOMETRO fica de fora do registro reordenavel de proposito: alem de
# ser o painel de abertura da aba, ele tambem funciona como "gate" (se
# nao tem dado nenhum, os outros nem tentam renderizar - ver
# render_mercado). Os demais sao os que fazem sentido reordenar (ver
# ui/paineis.py, adotado pela primeira vez aqui).
#
# REGISTRO reduzido (redesign em grade, 2026-10-27 - mesma correção já
# validada em ui/visao_geral.py, PR #186): metricas_principais/
# altas_baixas/mais_negociados/setorial/treemap/noticias_resumo/destaques
# saem daqui e viram SEÇÕES FIXAS em render_mercado (st.columns, mesmo
# padrão já usado por TERMÔMETRO) - só assim a Região 2/3 vira grade
# horizontal de verdade; o workspace livre empilha todo painel sem
# posição salva em largura total (x=0,w=100%), não existe "posição
# padrão lado a lado" nele. Trade-off aceito explicitamente (perdem
# drag/resize/ocultar individual - mesmo trade-off já aceito pelo
# Rodrigo em VISÃO GERAL). IBOVESPA · TRAJETÓRIA saiu de vez (duplicava
# o gráfico que já é o canônico de VISÃO GERAL, ui/visao_geral.py:
# _painel_ibov_grafico) - não fica nem fixo nem livre. Só leitura_rapida/
# globais continuam arrastáveis/ocultáveis de verdade.
REGISTRO_PAINEIS = [
    ("leitura_rapida", "Leitura rápida", _painel_leitura_rapida),
    ("globais", "Mercados globais", _painel_globais),
]


def render_mercado(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba MERCADO (= MERCADO › PAINEL), chamado pelo
    app.py. `persistir_fn` (opcional): ver ui/workspace.py:
    renderizar_workspace.

    Composição FIXA (redesign em grade, 2026-10-27, mesmo padrão já
    validado em ui/visao_geral.py:render_visao_geral) - TERMÔMETRO sozinho,
    depois 2 linhas de 3 colunas lado a lado: (1) Maiores altas/baixas +
    Destaques + Mapa do mercado, (2) Desempenho setorial + Mais negociados
    + Notícias. Essas seções NÃO são arrastáveis/redimensionáveis
    individualmente (trade-off aceito explicitamente - ver REGISTRO_
    PAINEIS acima). st.columns do Streamlit já reflow pra empilhado em
    telas estreitas (mesmo CSS global usado nas outras abas), sem
    precisar de nenhuma regra nova aqui.

    O restante (REGISTRO_PAINEIS, hoje só leitura_rapida/globais) continua
    no workspace modular normal, abaixo desta composição fixa."""
    with st.container(border=True):
        tem_dados = _painel_termometro(prefs)

    if not tem_dados:
        return

    with st.container(border=True):
        _painel_metricas_principais(prefs)

    with st.container(key="painel_grid_linha1"):
        col_ab, col_destaques, col_mapa = st.columns([0.33, 0.24, 0.43], gap="small")
        with col_ab:
            with st.container(border=True):
                _painel_altas_baixas(prefs)
        with col_destaques:
            with st.container(border=True):
                _painel_destaques(prefs)
        with col_mapa:
            with st.container(border=True):
                _painel_treemap(prefs, altura_px=_ALTURA_TREEMAP_PX_GRADE)

    with st.container(key="painel_grid_linha2"):
        col_setorial, col_negociados, col_noticias = st.columns([0.36, 0.3, 0.34], gap="small")
        with col_setorial:
            with st.container(border=True):
                _painel_setorial(prefs)
        with col_negociados:
            with st.container(border=True):
                _painel_mais_negociados(prefs)
        with col_noticias:
            with st.container(border=True):
                _painel_noticias_resumo(prefs)

    # 1o prefs: pra workspace.renderizar_workspace calcular ordem/
    # visibilidade/layout salvos do usuario. 2o prefs: repassado como
    # argumento pra cada _painel_*(prefs) do registro acima (todos tem
    # essa mesma assinatura de 1 argumento).
    workspace.renderizar_workspace("MERCADO", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn)
