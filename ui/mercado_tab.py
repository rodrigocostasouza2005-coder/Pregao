# -*- coding: utf-8 -*-
"""Interface da aba MERCADO: visão ampla do pregão (não é sobre um papel
específico, ao contrário de EQUITY) - altas/baixas, mais negociados,
termômetro, mapa de calor setorial e mercados globais. Dados vêm de
data/mercado.py, sobre a composição oficial do Ibovespa direto da B3
(com fallback pra lista curada estática se a B3 falhar - ver aviso fixo
no topo da aba e o comentário em data/ibovespa.py)."""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from data.ibovespa import obter_composicao_oficial
from data.mercado import (
    CAMPO_VARIACAO_POR_JANELA, obter_altas_baixas, obter_desempenho_setorial,
    obter_mais_negociados, obter_mercados_globais, obter_panorama_ibovespa, obter_termometro,
)
from data.prices import obter_cotacao_indice, rotulo_cotacao_em_cache
from ui import graficos, navegacao, workspace

_JANELAS_DESEMPENHO = ["DIA", "SEMANA", "MÊS"]
_JANELA_ROTULO_PARA_CHAVE = {"DIA": "dia", "SEMANA": "semana", "MÊS": "mes"}

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


def _linha_ranking(numero: int, p: dict, campo: str, prefs: dict, max_abs: float):
    """Uma linha do ranking unico: numero | botao do ticker (navega pra
    EQUITY, mesmo mecanismo da busca global) | nome + retorno | barra
    horizontal unica, crescendo a partir do zero (borda esquerda da
    coluna da barra), colorida conforme o sinal. Escala relativa ao
    MAIOR valor absoluto do PROPRIO grupo (altas entre si, baixas entre
    si) - cada linha chamada aqui pertence a UM grupo so' (ver
    _painel_altas_baixas: altas e baixas sao secoes separadas, cada uma
    com seu subtitulo), entao nunca precisa reservar espaco pra uma
    barra no sentido contrario que nunca vai aparecer naquela secao.
    REDESENHADO (auditoria visual 2026-10-16): a versao anterior
    reservava DUAS colunas de barra (positiva E negativa) em TODA linha,
    mas cada linha so' preenche uma delas (alta preenche so' a positiva,
    baixa so' a negativa) - a outra ficava sempre vazia, desperdicando
    ~20% da largura da linha em trilho cinza sem funcao nenhuma. Uma
    unica coluna de barra (maior, mais precisa) elimina essa area morta."""
    valor = p[campo]
    cls_barra = "rank-barra-pos" if valor >= 0 else "rank-barra-neg"
    cor_var = "var(--alta)" if valor >= 0 else "var(--baixa)"
    largura = min(100.0, (abs(valor) / max_abs * 100.0)) if max_abs > 0 else 0.0
    nome = _nome_papel(p["ticker"])

    # vertical_alignment="center" (2a passada da auditoria visual
    # 2026-10-17): sem isso (default "top"), as 4 colunas tem alturas de
    # conteudo bem diferentes - botao do ticker (~22-26px) vs 1 linha de
    # texto (~13-14px) vs a barra (10px) - e cada uma nascia encostada no
    # TOPO da linha, sem alinhar com o centro visual do botao. A versao
    # anterior tentava compensar isso com padding-top fixo por classe
    # (ver style.css), um numero "no olho" calibrado so' pra 1 combinacao
    # de fonte/densidade - centralizar de verdade (mesmo padrao ja usado
    # em ui/cvm_tab.py:_linha_documento) resolve pra qualquer preferencia
    # de FONTE (P/M/G) sem precisar recalibrar nada.
    col_num, col_ticker, col_nome_valor, col_barra = st.columns(
        [0.06, 0.14, 0.38, 0.42], gap="small", vertical_alignment="center",
    )
    with col_num:
        st.markdown(f"<div class='rank-numero'>{numero}</div>", unsafe_allow_html=True)
    with col_ticker:
        st.button(
            p["ticker"], key=f"rank_ticker_{numero}_{p['ticker']}", width="stretch",
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
    with col_barra:
        st.markdown(
            f"<div class='rank-barra-trilho'><div class='rank-barra-fill {cls_barra}' "
            f"style='width:{largura:.1f}%;'></div></div>",
            unsafe_allow_html=True,
        )


def _subtitulo_ranking(texto: str):
    st.markdown(f"<div class='rank-subtitulo'>{texto}</div>", unsafe_allow_html=True)


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

    max_pos = max((p[campo] for p in altas), default=0.0) or 1.0
    max_neg_abs = max((abs(p[campo]) for p in baixas), default=0.0) or 1.0

    with st.container(key="mercado_ranking_lista"):
        numero = 1
        if altas:
            _subtitulo_ranking("MAIORES ALTAS")
            for p in altas:
                _linha_ranking(numero, p, campo, prefs, max_pos)
                numero += 1
        if baixas:
            _subtitulo_ranking("MAIORES BAIXAS")
            for p in baixas:
                _linha_ranking(numero, p, campo, prefs, max_neg_abs)
                numero += 1


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
    for p in negociados:
        with st.container(key=f"mn_linha_{p['ticker']}"):
            col_ticker, col_volume, col_var = st.columns([1.1, 1.3, 1], vertical_alignment="center")
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


def _painel_treemap(prefs):
    st.markdown('<div class="painel-titulo">MAPA DO MERCADO</div>', unsafe_allow_html=True)
    st.caption("Tamanho do retângulo = volume financeiro no dia · cor = variação % no dia.")
    papeis = [p for p in obter_panorama_ibovespa() if p["volume_financeiro"] > 0]
    if not papeis:
        st.markdown("<div class='cinza' style='font-size:0.78rem;'>—</div>", unsafe_allow_html=True)
        return

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

    ids.append("IBOVESPA"); labels.append("IBOVESPA"); parents.append("")
    values.append(sum(p["volume_financeiro"] for p in papeis))
    colors.append(tema["cinza"]); textos.append("")
    hovertextos.append(f"<b>IBOVESPA</b><br>{len(papeis)} papéis no mapa")

    for setor, papeis_setor in por_setor.items():
        id_setor = f"IBOVESPA/{setor}"
        volume_setor = sum(p["volume_financeiro"] for p in papeis_setor)
        variacao_media_setor = sum(p["variacao_pct"] for p in papeis_setor) / len(papeis_setor)
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
        marker=dict(colors=colors, line=dict(width=1, color=tema["fundo"])),
        text=textos, textinfo="text", textposition="middle center",
        hovertext=hovertextos, hoverinfo="text",
        hovertemplate="%{hovertext}<extra></extra>",
        root_color=tema["fundo"],
    ))
    fig.update_layout(
        paper_bgcolor=tema["fundo"], plot_bgcolor=tema["fundo"],
        font=dict(color=tema["neutro"], family="IBM Plex Mono", size=11),
        height=420, margin=dict(l=4, r=4, t=4, b=4),
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
# nao tem dado nenhum, os outros 5 nem tentam renderizar - ver
# render_mercado). Os outros 5 sao os que fazem sentido reordenar (ver
# ui/paineis.py, adotado pela primeira vez aqui).
REGISTRO_PAINEIS = [
    ("altas_baixas", "Maiores altas/baixas", _painel_altas_baixas),
    ("mais_negociados", "Mais negociados", _painel_mais_negociados),
    ("setorial", "Desempenho setorial", _painel_setorial),
    ("treemap", "Mapa do mercado", _painel_treemap),
    ("globais", "Mercados globais", _painel_globais),
]


def render_mercado(prefs: dict, persistir_fn=None):
    """Ponto de entrada da aba MERCADO, chamado pelo app.py.
    `persistir_fn` (opcional): ver ui/workspace.py:renderizar_workspace.

    MERCADO é a aba piloto (MVP, 2026-10-01) do workspace modular com
    drag & drop + resize livre (ui/workspace.py) - antes usava
    ui/paineis.py (larguras fixas 1/4-1/2-3/4-FULL). MACRO continua no
    sistema antigo até essa ETAPA 1 ser validada (ver PROGRESSO.md)."""
    with st.container(border=True):
        tem_dados = _painel_termometro(prefs)

    if not tem_dados:
        return

    # 1o prefs: pra workspace.renderizar_workspace calcular ordem/
    # visibilidade/layout salvos do usuario. 2o prefs: repassado como
    # argumento pra cada _painel_*(prefs) do registro acima (todos tem
    # essa mesma assinatura de 1 argumento).
    workspace.renderizar_workspace("MERCADO", REGISTRO_PAINEIS, prefs, prefs, persistir_fn=persistir_fn)
