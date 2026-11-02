# -*- coding: utf-8 -*-
"""Area ANALISES do PREGAO 2.0 (ui/navegacao.py). Empresas = a antiga
EQUITY (continua em app.py, intocada no miolo); aqui ficam a barra de
vinculos da empresa (empresa -> setor/noticias/radar/fundamentos) e a
subaba Fundamentos. Valuation/Teses vem de ui/radar_tab.py.

Fundamentos (ponto atual) so' mostra o que a fonte reporta HOJE
(data/prices.py:obter_indicadores, Yahoo Finance, cache de 12h). Série
histórica trimestral REAL de receita líquida/EBIT/lucro líquido/margem
bruta existe via Earnings Reviewer (data/earnings/reviewer.py:
serie_historica_br, só Brasil) e alimenta a CONCLUSÃO DE INVESTIMENTO
abaixo (2026-10-30) - mas ROIC, dívida líquida histórica, fluxo de caixa
operacional/livre, CAPEX e dividendos em série histórica ainda não têm
fonte integrada (ver seção "Lacunas de informação" da conclusão), e a
tela diz isso em vez de estimar."""

import html
from collections import Counter
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.earnings import reviewer as earnings_reviewer
from data.market_researcher import analise_ticker, consenso_research
from data.prices import obter_cotacao, obter_indicadores
from data.research.comparador import montar_relatorio_comparativo
from data.radar import (
    TIPO_CALCULO, TIPO_ESTIMATIVA_TERCEIRO, TIPO_FATO, TIPO_HIPOTESE, TIPO_INSUFICIENTE,
    comparaveis_setor,
)
from data.research.historico import historico_ticker
from data.research.tese import scorecard
from ui import navegacao
from ui.design_system import lista_compacta, subtitulo
from ui.setores_tab import ir_para_setor, setores_do_ticker

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _ir_noticias_do_ticker(ticker: str, watchlist: tuple):
    # o filtro de NOTICIAS > Empresas so' oferece tickers da watchlist
    if ticker in watchlist:
        st.session_state["news_pill_ticker"] = ticker
    navegacao.ir_para("noticias", "empresas")


def _ir_radar_do_ticker(ticker: str):
    st.session_state["rq_ticker"] = ticker
    navegacao.ir_para("radar", "alertas")


def barra_contexto_empresa(ticker: str, prefs: dict):
    """Vinculos contextuais da empresa selecionada. Setor so' aparece se o
    ticker estiver na lista curada de algum setor (data/news_setores) -
    nunca por semelhanca de nome."""
    setores = setores_do_ticker(ticker)
    botoes = [("Notícias ↗", _ir_noticias_do_ticker, (ticker, tuple(prefs.get("watchlist") or [])), "Notícias desta empresa (NOTÍCIAS › Empresas)"),
              ("Radar ↗", _ir_radar_do_ticker, (ticker,), "Alertas de queda deste ativo (RADAR › Alertas)"),
              ("Fundamentos ↗", navegacao.ir_para, ("analises", "fundamentos"), "ANÁLISES › Fundamentos"),
              ("Valuation ↗", navegacao.ir_para, ("analises", "valuation"), "ANÁLISES › Valuation")]
    botoes += [(f"Setor: {s} ↗", ir_para_setor, (s,), "SETORES › Visão por Setor") for s in setores]
    with st.container(key="empresa_contexto"):
        cols = st.columns(len(botoes))
        for i, (rotulo, fn, args, ajuda) in enumerate(botoes):
            with cols[i]:
                st.button(rotulo, key=f"empresa_ctx_{i}_{ticker}", on_click=fn, args=args, help=ajuda,
                          width="stretch")
    if not setores:
        st.caption("Setor: não classificado (ticker fora das listas curadas de data/news_setores.py).")


@st.cache_data(ttl=90, show_spinner=False)
def _analise_ticker_cacheada(ticker: str) -> dict:
    """Cache na camada de UI (data/market_researcher.py não importa
    Streamlit de propósito - usado também fora de sessão) - mesmo TTL
    de data/radar.py:linha_valuation (90s, o bloco mais sensível ao
    tempo dentro da análise agregada), evita recompor tudo a cada
    rerun do Streamlit (troca de widget na mesma página, etc)."""
    return analise_ticker(ticker)


# ============================================================
# COMPARATIVO SETORIAL DE MÚLTIPLOS (2026-10-27)
#
# ANÁLISES › Empresas mostrava P/L, P/VP, ROE e DÍV/EBITDA do ticker
# isolados, sem nenhum ponto de referência - o usuário precisava ir até
# RADAR › Valuation (ui/radar_tab.py:_dialog_comparaveis) pra ver a
# mediana do setor pro MESMO múltiplo, perdendo o contexto do ticker que
# estava analisando. Esta seção só CONSOME data/radar.py:comparaveis_setor
# (mesma função que RADAR já usa) - nenhuma consulta nova, nenhum cálculo
# novo, nenhuma chamada de IA. Sob demanda (botão), não no primeiro
# render - mesmo motivo de radar_tab.py: evita N consultas yfinance em
# cascata (1 por par do setor) a cada vez que a página abre.
# ============================================================

@st.dialog("COMPARATIVO SETORIAL DE MÚLTIPLOS", width="large")
def _dialog_comparativo_setor_empresa(ticker: str, prefs: dict):
    fmt = prefs["formato_numerico"]
    with st.spinner("Calculando medianas do setor (consulta ao vivo, pode levar alguns segundos)..."):
        try:
            comp = comparaveis_setor(ticker)
        except Exception:
            st.warning(f"Comparativo setorial de {ticker} indisponível agora (fonte não respondeu).")
            return
    if comp.get("insuficiente"):
        st.warning(f"Dado insuficiente pra comparação setorial de {ticker}: "
                    f"{comp.get('motivo', 'sem pares válidos')}.")
        return
    st.caption(f"Setor: {comp['setor']} · {comp['pares_considerados']} papéis no universo (Ibovespa)")
    for rotulo, chave, sufixo in (
        ("P/L", "pl_mediana", "x"), ("P/VP", "pvp_mediana", "x"), ("Dividend yield", "dy_mediana", "%"),
    ):
        valor = comp.get(chave)
        n = comp.get(f"{chave}_n", 0)
        if valor is None:
            st.markdown(f"**{rotulo}**: dado insuficiente (menos de 3 pares com valor válido - {n} disponível(is))")
        else:
            texto_valor = config.formatar_multiplo(valor, 2, fmt) if sufixo == "x" else (
                config.formatar_numero(valor, 2, fmt) + "%"
            )
            st.markdown(f"**{rotulo} mediano do setor**: {texto_valor} ({n} pares considerados)")
    st.caption(
        "Mediana calculada agora, sobre os múltiplos atuais do yfinance pros outros papéis do mesmo "
        "setor (classificação setorial própria do PREGÃO) - não é um índice oficial nem estimativa de "
        "analista, é um cálculo interno pra dar contexto relativo. Limitação: P/L e P/VP comparam preço "
        "contra lucro/patrimônio contábil do momento - empresas com margens, crescimento ou estrutura de "
        "capital diferentes dentro do mesmo setor podem justificar múltiplos diferentes; isto não é um "
        "preço justo nem uma recomendação."
    )


def render_equity_research_executivo(ticker: str, prefs: dict):
    """ANÁLISES › Empresas: síntese executiva de equity research pro
    ticker selecionado - agrega data/market_researcher.py:analise_ticker
    (fundamentos + catalisadores + mudança de tese/CVM + risco de
    indicador + cobertura de research entre casas), sem nenhuma consulta
    nova (tudo já calculado por RADAR/Market Makers/Market Researcher).
    Cada bloco mostra o que existe e diz explicitamente o que não existe
    - nunca inventa recomendação, preço-alvo ou conclusão do Pregão;
    preço-alvo/recomendação exibidos são sempre da casa de research que
    publicou (ESTIMATIVA DE TERCEIRO), nunca um cálculo próprio."""
    fmt = prefs["formato_numerico"]
    try:
        analise = _analise_ticker_cacheada(ticker)
    except Exception:
        st.warning(f"Análise executiva de {ticker} indisponível agora (fonte não respondeu).")
        return

    fundamentos = analise.get("fundamentos")
    catalisadores = analise.get("catalisadores")
    mudancas = analise.get("mudancas_tese")
    riscos = analise.get("riscos_indicadores")
    cobertura = analise.get("cobertura_research")
    indisponiveis = analise.get("fontes_indisponiveis") or []

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">EQUITY RESEARCH — SÍNTESE EXECUTIVA</div>', unsafe_allow_html=True)
        st.markdown(
            f"<div class='cinza' style='font-size:0.78rem;'>{ticker}: "
            f"{len(catalisadores) if catalisadores else 0} catalisador(es) nos próximos 60 dias · "
            f"{len(mudancas) if mudancas else 0} mudança(s) de tese/CVM recente(s) · "
            f"{len(riscos) if riscos else 0} alerta(s) de risco nos indicadores · "
            f"{len((cobertura or {}).get('cobertura') or [])} casa(s) de research com cobertura recente.</div>",
            unsafe_allow_html=True,
        )
        if indisponiveis:
            st.caption(f"Indisponível nesta execução: {', '.join(indisponiveis)}.")

        subtitulo("Momento da empresa")
        if fundamentos is None:
            st.caption("Fundamentos indisponíveis agora (fonte não respondeu).")
        else:
            blocos_ind = [
                ("P/L", _celula(fundamentos.get("pl"), lambda v: config.formatar_multiplo(v, 2, fmt))),
                ("P/VP", _celula(fundamentos.get("pvp"), lambda v: config.formatar_multiplo(v, 2, fmt))),
                ("ROE", _celula(fundamentos.get("roe"), lambda v: config.formatar_numero(v, 2, fmt) + "%")),
                ("DÍV/EBITDA", _celula(fundamentos.get("divida_liquida_ebitda"),
                                       lambda v: config.formatar_numero(v, 1, fmt) + "x")),
            ]
            st.markdown(
                "<div style='display:flex; flex-wrap:wrap; gap:1.4rem; margin:0.3rem 0 0.5rem 0;'>" + "".join(
                    f"<div><div class='cinza' style='font-size:0.6rem; letter-spacing:0.04em;'>{rot}</div>"
                    f"<div class='neutro' style='font-size:0.92rem; font-weight:700; margin-top:0.1rem;'>{val}</div></div>"
                    for rot, val in blocos_ind
                ) + "</div>",
                unsafe_allow_html=True,
            )
            for alerta in fundamentos.get("alerta_qualidade") or []:
                st.warning(alerta)
            if st.button("Comparar com o setor ↗", key=f"empresa_comp_setor_{ticker}",
                          help="P/L, P/VP e dividend yield mediano dos outros papéis do mesmo setor "
                               "(RADAR/data/radar.py:comparaveis_setor) - consulta ao vivo sob demanda."):
                _dialog_comparativo_setor_empresa(ticker, prefs)

        subtitulo("Catalisadores")
        if catalisadores is None:
            st.caption("Catalisadores indisponíveis agora.")
        elif not catalisadores:
            st.caption("Nenhum catalisador (resultado/proventos) identificado nos próximos 60 dias.")
        else:
            lista_compacta(
                f"{c['categoria']} em {c['data'].strftime('%d/%m/%Y')} ({'confirmado' if c.get('confirmado') else 'estimado/prazo regulatório'})"
                for c in catalisadores
            )

        subtitulo("Mudanças de tese e CVM")
        if mudancas is None:
            st.caption("Mudanças de tese indisponíveis agora.")
        elif not mudancas:
            st.caption("Nenhuma mudança de tese/CVM verificada recentemente.")
        else:
            def _linha_mudanca(m):
                if m.get("fonte_url"):
                    fonte = f" — <a href='{html.escape(m['fonte_url'], quote=True)}' target='_blank' style='color:var(--cinza);'>{html.escape(m.get('fonte_label') or 'fonte')}</a>"
                elif m.get("fonte_label"):
                    fonte = f" — {html.escape(m['fonte_label'])}"
                else:
                    fonte = ""
                return f"{m['data_evento'].strftime('%d/%m/%Y')}: {html.escape(m['descricao'])}{fonte}"
            lista_compacta(_linha_mudanca(m) for m in mudancas)

        subtitulo("Research das casas")
        # cobertura["cobertura"] é None quando o PRÓPRIO banco de research
        # está indisponível (ver data/market_researcher.py:cobertura_cruzada_casas)
        # - distinto de [] (banco respondeu, nenhuma casa publicou). Bug
        # real encontrado validando com WEGE3/PETR4 (23/10/2026, Fase 2):
        # a versão anterior tratava os dois como "nenhuma casa publicou",
        # escondendo que a fonte nem respondeu.
        if cobertura is None or cobertura.get("cobertura") is None:
            st.caption("Cobertura de research indisponível agora (banco fora do ar).")
        else:
            itens_cobertura = cobertura.get("cobertura") or []
            if not itens_cobertura:
                st.caption("Nenhuma casa monitorada publicou research recente sobre este ativo.")
            else:
                def _linha_cobertura(item):
                    rec = f" · {html.escape(item['recomendacao'])}" if item.get("recomendacao") else ""
                    return (
                        f"<b>{html.escape(item['casa'])}</b> ({str(item['data'])[:10]}){rec}: "
                        f"<a href='{html.escape(item['link'], quote=True)}' target='_blank' style='color:var(--ciano);'>"
                        f"{html.escape(item.get('titulo') or 'ver relatório')}</a>"
                    )
                lista_compacta(_linha_cobertura(item) for item in itens_cobertura)
            if cobertura.get("sem_cobertura"):
                st.caption(f"Sem cobertura recente: {', '.join(cobertura['sem_cobertura'])}.")
            if cobertura.get("divergencia"):
                por_casa = ", ".join(f"{k}: {v}" for k, v in cobertura["divergencia"]["por_casa"].items())
                st.warning(f"Recomendação diverge entre casas — {por_casa}.")

        st.caption(
            "Síntese objetiva a partir de dados já verificados (RADAR/Market Makers/Market Researcher) — "
            "nunca uma recomendação ou preço-alvo do Pregão. Preço-alvo/recomendação de casas de research são "
            "sempre ESTIMATIVA DE TERCEIRO, nunca um cálculo ou opinião própria do Pregão."
        )


# ============================================================
# CONCLUSÃO DE INVESTIMENTO (2026-10-23, reformulada em 14 seções 2026-10-30)
#
# Complemento de render_equity_research_executivo (acima): aquele painel
# já mostra momento/catalisadores/mudanças/research das casas - aqui
# sintetiza isso numa conclusão fundamentalista completa (resumo
# executivo, qualidade do negócio, crescimento/rentabilidade, estrutura
# de capital, geração de caixa, tese positiva/negativa, valuation,
# catalisadores, riscos/invalidação, consenso de research, cenários,
# confiança e lacunas). _montar_conclusao é função pura (sem Streamlit,
# sem IA): cada resposta cita só o que já está em `analise` (mesmo dict
# de analise_ticker, via _analise_ticker_cacheada - zero consulta nova)
# ou declara "dado insuficiente" explícito. Nunca emite recomendação de
# compra/venda - esse conceito não existe no retorno da função.
#
# Lacunas estruturais (ROIC, dívida líquida histórica, fluxo de caixa
# operacional/livre/CAPEX/dividendos históricos, EV/EBIT, DCF, série
# histórica internacional) são registradas UMA VEZ em `_TEXTOS_LACUNA` e
# só citadas por nome nas seções analíticas (nunca repetidas por
# extenso) - o texto completo mora só na seção 14 (Lacunas de
# informação), pedido explícito de não duplicar lacuna em várias seções.
# ============================================================

_ROTULO_TENDENCIA = {
    "RECUPERACAO": "recuperação", "DETERIORACAO": "deterioração", "ESTABILIDADE": "estabilidade",
}

_TEXTOS_LACUNA = {
    "roic": "ROIC: não calculado nesta versão - yfinance não reporta o indicador e calcular à mão "
            "viraria estimativa, não dado reportado; exigiria extrair o Balanço Patrimonial da CVM "
            "(capital investido), fora do escopo desta fase.",
    "divida_historica": "Dívida líquida em série histórica: só o ponto atual existe (yfinance) - série "
            "temporal exigiria Balanço Patrimonial histórico da CVM, fora do escopo desta fase.",
    "geracao_caixa": "Fluxo de caixa operacional isolado, CAPEX e dividendos pagos, e a série histórica "
            "do próprio fluxo de caixa livre: sem fonte integrada nesta versão (exigiria Demonstração de "
            "Fluxo de Caixa da CVM) - só o ponto atual de fluxo de caixa livre existe (yfinance), nenhum "
            "desses outros valores é estimado como substituto.",
    "ev_ebit": "EV/EBIT: EBIT trimestral isolado da CVM não cobre o 4º trimestre e não há EBIT anual "
            "consolidado ponto a ponto integrado nesta versão - aproximar via margem operacional "
            "seria estimativa, não dado reportado, por isso não foi calculado.",
    "dcf": "Valuation por fluxo de caixa descontado (DCF): bloqueado por falta de fluxo de caixa livre "
            "atual (ver lacuna de Geração de caixa) - quando o ponto existe, o DCF ainda depende de você "
            "informar taxa de crescimento e taxa de desconto no painel (nunca um padrão interno).",
    "historico_internacional": "Série histórica trimestral para empresas internacionais: calendário "
            "fiscal não é detectado automaticamente nesta versão - só empresas brasileiras (CVM) têm "
            "série histórica confiável hoje.",
}

_MOTIVO_FONTE_INDISPONIVEL = {
    "fundamentos": "Fundamentos (cotação/múltiplos) indisponíveis nesta checagem (fonte não respondeu).",
    "contexto_mercado": "Catalisadores/mudanças de tese/riscos de indicador indisponíveis nesta checagem.",
    "cobertura_research": "Cobertura de research entre casas indisponível nesta checagem (banco fora do ar).",
    "historico_fundamentos": "Histórico trimestral de fundamentos indisponível nesta checagem.",
    "comparativo_setorial": "Comparativo setorial de múltiplos indisponível nesta checagem.",
}


def _dcf_calculo(fcf_atual, taxa_crescimento_pct, taxa_desconto_pct, anos_projecao: int = 5,
                  valor_mercado=None) -> dict:
    """Fluxo de caixa descontado - TODAS as premissas (fcf_atual,
    taxa_crescimento_pct, taxa_desconto_pct) vêm de fora, nunca um
    padrão interno; None em qualquer uma bloqueia o cálculo com `motivo`
    explícito dizendo QUAL está faltando (nunca aproxima). Perpetuidade
    de Gordon pro valor terminal - exige taxa_desconto > taxa_crescimento
    (senão o denominador inverte de sinal, premissa inválida, não
    calculado). Função pura, testável isoladamente - não é chamada pela
    conclusão nesta versão porque fcf_atual nunca está disponível (ver
    _TEXTOS_LACUNA['dcf']); fica pronta pra quando essa fonte existir."""
    faltando = []
    if fcf_atual is None:
        faltando.append("fluxo de caixa livre atual")
    if taxa_crescimento_pct is None:
        faltando.append("taxa de crescimento esperada (premissa do usuário)")
    if taxa_desconto_pct is None:
        faltando.append("taxa de desconto / WACC (premissa do usuário)")
    if faltando:
        return {"calculavel": False, "motivo": f"faltando: {', '.join(faltando)}."}

    g, wacc = taxa_crescimento_pct / 100, taxa_desconto_pct / 100
    if wacc <= g:
        return {"calculavel": False,
                "motivo": "taxa de desconto precisa ser maior que a taxa de crescimento para o "
                          "valor terminal (perpetuidade de Gordon) ser matematicamente válido."}

    valor_presente_fluxos = 0.0
    fcf_projetado = fcf_atual
    for ano in range(1, anos_projecao + 1):
        fcf_projetado *= (1 + g)
        valor_presente_fluxos += fcf_projetado / ((1 + wacc) ** ano)
    valor_terminal = fcf_projetado * (1 + g) / (wacc - g)
    valor_presente_terminal = valor_terminal / ((1 + wacc) ** anos_projecao)
    valor_justo_estimado = valor_presente_fluxos + valor_presente_terminal

    resultado = {
        "calculavel": True,
        "premissas": {"fcf_atual": fcf_atual, "taxa_crescimento_pct": taxa_crescimento_pct,
                       "taxa_desconto_pct": taxa_desconto_pct, "anos_projecao": anos_projecao},
        "valor_presente_fluxos": valor_presente_fluxos,
        "valor_presente_terminal": valor_presente_terminal,
        "valor_justo_estimado": valor_justo_estimado,
    }
    if valor_mercado:
        resultado["potencial_pct"] = (valor_justo_estimado / valor_mercado - 1) * 100
    return resultado


def _secao_qualidade_negocio(historico: dict, lacunas_ativas: set) -> dict:
    if not (historico or {}).get("disponivel"):
        motivo = (historico or {}).get("motivo", "histórico trimestral indisponível nesta checagem.")
        if "internacional" in motivo or "calendário fiscal" in motivo:
            lacunas_ativas.add("historico_internacional")
        return {"pergunta": "Qualidade do negócio",
                "resposta": f"Dado insuficiente: {motivo}", "tipo_evidencia": TIPO_INSUFICIENTE}
    margem = historico.get("margem_bruta_pct", {})
    receita = historico.get("receita_liquida", {})
    tend_margem, tend_receita = margem.get("tendencia"), receita.get("tendencia")
    partes = []
    if tend_margem:
        partes.append(f"margem bruta em {_ROTULO_TENDENCIA[tend_margem]}")
    if tend_receita:
        partes.append(f"receita líquida em {_ROTULO_TENDENCIA[tend_receita]} (YoY)")
    periodos = f"{historico['periodos'][0]} a {historico['periodos'][-1]}"
    if partes:
        resposta = (f"{'; '.join(partes).capitalize()} nos trimestres observados ({periodos}, fonte "
                    "CVM - ITR, DRE consolidada).")
        tipo = TIPO_CALCULO
    else:
        resposta = (f"Trimestres disponíveis ({periodos}) insuficientes para apontar tendência (menos "
                    "de 2 pontos válidos de margem bruta ou receita).")
        tipo = TIPO_INSUFICIENTE
    return {"pergunta": "Qualidade do negócio", "resposta": resposta, "tipo_evidencia": tipo}


def _secao_crescimento_rentabilidade(fundamentos: dict, historico: dict, lacunas_ativas: set) -> dict:
    lacunas_ativas.add("roic")
    partes = []
    if (historico or {}).get("disponivel"):
        lucro_t = historico.get("lucro_liquido_consolidado", {}).get("tendencia")
        ebit_t = historico.get("ebit", {}).get("tendencia")
        if lucro_t:
            partes.append(f"lucro líquido em {_ROTULO_TENDENCIA[lucro_t]} (YoY)")
        if ebit_t:
            partes.append(f"EBIT em {_ROTULO_TENDENCIA[ebit_t]} (YoY)")
    roe = (fundamentos or {}).get("roe")
    if roe is not None:
        partes.append(f"ROE atual (ponto, yfinance): {roe:.1f}%")
    if partes:
        resposta = "; ".join(partes) + ". ROIC não calculado nesta versão (ver Lacunas)."
        tipo = TIPO_CALCULO
    else:
        resposta = "Dado insuficiente: sem histórico de lucro/EBIT nem ROE disponíveis agora (ver Lacunas)."
        tipo = TIPO_INSUFICIENTE
    return {"pergunta": "Crescimento e rentabilidade", "resposta": resposta, "tipo_evidencia": tipo}


def _secao_estrutura_capital(fundamentos: dict, lacunas_ativas: set) -> dict:
    lacunas_ativas.add("divida_historica")
    dl_ebitda = (fundamentos or {}).get("divida_liquida_ebitda")
    if dl_ebitda is None:
        return {"pergunta": "Estrutura de capital",
                "resposta": "Dado insuficiente: dívida líquida/EBITDA indisponível agora (ver Lacunas).",
                "tipo_evidencia": TIPO_INSUFICIENTE}
    leitura = "elevada" if dl_ebitda > 4 else ("moderada" if dl_ebitda > 2 else "baixa")
    return {"pergunta": "Estrutura de capital",
            "resposta": f"Dívida líquida/EBITDA atual (ponto, yfinance): {dl_ebitda:.1f}x ({leitura}). "
                        "Série histórica não disponível (ver Lacunas).",
            "tipo_evidencia": TIPO_FATO}


def _secao_geracao_caixa(fundamentos: dict, lacunas_ativas: set) -> dict:
    lacunas_ativas.add("geracao_caixa")
    fcf = (fundamentos or {}).get("fluxo_caixa_livre")
    if fcf is None:
        return {"pergunta": "Geração de caixa",
                "resposta": "Dado insuficiente: fluxo de caixa livre indisponível agora; fluxo de caixa "
                            "operacional, CAPEX e dividendos pagos não têm fonte integrada nesta versão "
                            "(ver Lacunas).",
                "tipo_evidencia": TIPO_INSUFICIENTE}
    return {"pergunta": "Geração de caixa",
            "resposta": f"Fluxo de caixa livre atual (ponto, yfinance): {_fmt_reais(fcf, 'BR')}. Fluxo de "
                        "caixa operacional isolado, CAPEX e dividendos pagos, e a série histórica deste "
                        "próprio fluxo de caixa livre, ainda não têm fonte integrada (ver Lacunas).",
            "tipo_evidencia": TIPO_FATO}


def _secao_tese_positiva(cobertura_lista: list) -> dict:
    """Só recomendação ESTRUTURADA de casa de research sustenta uma
    leitura positiva aqui - um catalisador futuro (resultado/proventos
    agendado) é FATO neutro de calendário, nunca um argumento bullish
    por si só (ver seção "Catalisadores", que já lista isso separado;
    regra explícita do pedido: não classificar evento futuro como
    argumento positivo automaticamente)."""
    recomendacoes = [c for c in (cobertura_lista or []) if c.get("recomendacao")]
    if not recomendacoes:
        return {"pergunta": "Tese positiva",
                "resposta": "Dado insuficiente: nenhuma recomendação estruturada identificada nas fontes "
                            "monitoradas (ver Catalisadores pros eventos futuros já agendados, que não são "
                            "argumento positivo por si só).",
                "tipo_evidencia": TIPO_INSUFICIENTE}
    partes = [f"{r['casa']}: {r['recomendacao']} ({str(r['data'])[:10]})" for r in recomendacoes]
    return {"pergunta": "Tese positiva", "resposta": "; ".join(partes) + ".", "tipo_evidencia": TIPO_FATO}


def _secao_tese_negativa(fundamentos: dict, divergencia, sem_cobertura: list) -> dict:
    contrarios = list((fundamentos or {}).get("alerta_qualidade") or [])
    if divergencia:
        contrarios.append(divergencia["descricao"])
    if sem_cobertura:
        contrarios.append(f"sem cobertura recente de: {', '.join(sem_cobertura)}")
    if not contrarios:
        return {"pergunta": "Tese negativa",
                "resposta": "Nenhum alerta de qualidade nos indicadores monitorados (P/L, margem, "
                            "dívida/EBITDA) nem divergência de recomendação entre casas.",
                "tipo_evidencia": TIPO_CALCULO if fundamentos else TIPO_INSUFICIENTE}
    return {"pergunta": "Tese negativa", "resposta": "; ".join(contrarios) + ".",
            "tipo_evidencia": TIPO_CALCULO if fundamentos else TIPO_INSUFICIENTE}


def _secao_valuation(fundamentos: dict, setorial: dict | None, lacunas_ativas: set) -> dict:
    lacunas_ativas.add("ev_ebit")
    if (fundamentos or {}).get("fluxo_caixa_livre") is None:
        lacunas_ativas.add("dcf")
    if not fundamentos or fundamentos.get("preco") is None:
        return {"pergunta": "Valuation",
                "resposta": "Dado insuficiente: sem cotação ou múltiplos disponíveis agora (ver Lacunas).",
                "tipo_evidencia": TIPO_INSUFICIENTE}

    pl, pvp, dy = fundamentos.get("pl"), fundamentos.get("pvp"), fundamentos.get("dividend_yield")
    ev_ebitda = fundamentos.get("ev_ebitda")
    partes = []
    if pl is not None:
        partes.append(f"P/L {pl:.1f}x")
    if pvp is not None:
        partes.append(f"P/VP {pvp:.2f}x")
    if dy is not None:
        partes.append(f"dividend yield {dy:.1f}%")
    if ev_ebitda is not None:
        partes.append(f"EV/EBITDA {ev_ebitda:.1f}x (cálculo interno)")
    texto_multiplos = ", ".join(partes) if partes else (
        "sem múltiplos comparáveis (lucro/patrimônio/EBITDA negativo ou indisponível)"
    )

    texto_setorial = ""
    if setorial and not setorial.get("insuficiente"):
        comp = []
        if setorial.get("pl_mediana") is not None and pl is not None:
            comp.append(f"P/L setor {setorial['pl_mediana']:.1f}x ({setorial['pl_mediana_n']} pares)")
        if setorial.get("pvp_mediana") is not None and pvp is not None:
            comp.append(f"P/VP setor {setorial['pvp_mediana']:.2f}x ({setorial['pvp_mediana_n']} pares)")
        if setorial.get("dy_mediana") is not None and dy is not None:
            comp.append(f"DY setor {setorial['dy_mediana']:.1f}% ({setorial['dy_mediana_n']} pares)")
        if comp:
            texto_setorial = f" Mediana do setor ({setorial.get('setor')}): {', '.join(comp)}."
    elif setorial and setorial.get("insuficiente"):
        texto_setorial = f" Comparação setorial indisponível ({setorial.get('motivo', 'sem pares suficientes')})."

    desatualizado = " Múltiplos desatualizados (mais de 24h sem coleta nova)." if fundamentos.get("desatualizado") else ""
    if fundamentos.get("fluxo_caixa_livre") is not None:
        texto_dcf = (" DCF: fluxo de caixa livre atual disponível - informe taxa de crescimento e taxa "
                     "de desconto no painel abaixo para calcular (nenhuma das duas é assumida por padrão).")
    else:
        texto_dcf = " Valuation por fluxo de caixa descontado (DCF) não calculado nesta checagem (ver Lacunas)."
    resposta = (f"Múltiplos reportados agora: {texto_multiplos}.{texto_setorial}{desatualizado} EV/EBIT não "
                f"calculado nesta checagem (ver Lacunas).{texto_dcf}")
    tipo = TIPO_CALCULO if ev_ebitda is not None else (TIPO_FATO if partes else TIPO_INSUFICIENTE)
    return {"pergunta": "Valuation", "resposta": resposta, "tipo_evidencia": tipo}


def _secao_catalisadores(catalisadores) -> dict:
    if catalisadores is None:
        return {"pergunta": "Catalisadores",
                "resposta": "Dado insuficiente: fonte de catalisadores indisponível nesta checagem.",
                "tipo_evidencia": TIPO_INSUFICIENTE}
    proximos = sorted([c for c in catalisadores if c["data"] >= date.today()], key=lambda c: c["data"])
    if not proximos:
        return {"pergunta": "Catalisadores",
                "resposta": "Nenhum catalisador (resultado corporativo/proventos) identificado nos "
                            "próximos 60 dias nas fontes monitoradas.",
                "tipo_evidencia": TIPO_FATO}
    partes = [f"{c['categoria']} em {c['data'].strftime('%d/%m/%Y')} "
              f"({'confirmado' if c.get('confirmado') else 'estimado/prazo regulatório'})" for c in proximos]
    tipo = TIPO_FATO if any(c.get("confirmado") for c in proximos) else TIPO_ESTIMATIVA_TERCEIRO
    return {"pergunta": "Catalisadores", "resposta": "; ".join(partes) + ".", "tipo_evidencia": tipo}


def _secao_riscos_invalidacao(riscos, tese: dict | None) -> dict:
    riscos_tese_usuario = (tese or {}).get("riscos") or []
    invalidadores = list(riscos or []) + list(riscos_tese_usuario)
    if not invalidadores:
        return {"pergunta": "Riscos e invalidação da tese",
                "resposta": "Dado insuficiente: nenhum risco estrutural identificado nos indicadores "
                            "monitorados; registre riscos específicos em RESEARCH › Minha Tese.",
                "tipo_evidencia": TIPO_INSUFICIENTE}
    origem = " (inclui riscos registrados na sua Tese própria)" if riscos_tese_usuario else ""
    return {"pergunta": "Riscos e invalidação da tese", "resposta": "; ".join(invalidadores) + f".{origem}",
            "tipo_evidencia": TIPO_CALCULO if riscos else TIPO_HIPOTESE}


def _secao_consenso_research(cobertura: dict | None) -> dict:
    consenso = consenso_research(cobertura)
    if not consenso.get("disponivel"):
        return {"pergunta": "Consenso de Research",
                "resposta": f"Dado insuficiente: {consenso.get('motivo')}", "tipo_evidencia": TIPO_INSUFICIENTE}
    itens = consenso["itens"]
    if not itens and not consenso["casas_sem_cobertura"]:
        return {"pergunta": "Consenso de Research",
                "resposta": "Nenhuma casa de research monitorada está cadastrada.", "tipo_evidencia": TIPO_INSUFICIENTE}
    partes = [f"{i['casa']}: {i.get('recomendacao') or 'sem recomendação estruturada'} "
              f"({str(i['data'])[:10]})" for i in itens]
    resumo = (f"{consenso['n_casas_cobrindo']} casa(s) com cobertura recente, "
              f"{consenso['n_casas_sem_cobertura']} sem cobertura ({', '.join(consenso['casas_sem_cobertura']) or '—'}). "
              "Ausência de cobertura não é lida como sinal positivo ou negativo.")
    texto = ("; ".join(partes) + f". {resumo}") if partes else resumo
    if consenso["divergencia"]:
        texto += f" {consenso['divergencia']['descricao']}"
    return {"pergunta": "Consenso de Research", "resposta": texto,
            "tipo_evidencia": TIPO_ESTIMATIVA_TERCEIRO if itens else TIPO_FATO}


def _montar_cenarios(historico: dict | None, catalisadores, riscos, cobertura: dict | None) -> dict:
    """3 leituras qualitativas (nunca preço-alvo nem probabilidade),
    combinando só o que já foi calculado nas seções acima: tendência de
    fundamentos (histórico real), catalisadores futuros confirmados,
    riscos/divergência já identificados. HIPÓTESE DO ANALISTA (do
    Pregão) - exercício de leitura de cenário, nunca previsão."""
    tendencias = []
    if (historico or {}).get("disponivel"):
        for rotulo, chave in (("receita líquida", "receita_liquida"), ("EBIT", "ebit"),
                               ("lucro líquido", "lucro_liquido_consolidado")):
            t = historico.get(chave, {}).get("tendencia")
            if t:
                tendencias.append((rotulo, t))
    confirmados = [c for c in (catalisadores or []) if c.get("confirmado") and c["data"] >= date.today()]
    n_riscos = len(riscos or [])
    divergencia = (cobertura or {}).get("divergencia")

    if not (tendencias or confirmados or n_riscos or divergencia):
        return {"pergunta": "Cenários (otimista, base e pessimista)",
                "resposta": "Dado insuficiente pros 3 cenários: nenhuma tendência histórica de "
                            "fundamentos, catalisador confirmado ou risco identificado para compor uma "
                            "leitura qualitativa (otimista, base ou pessimista) nesta checagem.",
                "tipo_evidencia": TIPO_INSUFICIENTE}

    recuperacao = [r for r, t in tendencias if t == "RECUPERACAO"]
    deterioracao = [r for r, t in tendencias if t == "DETERIORACAO"]
    estaveis = [r for r, t in tendencias if t == "ESTABILIDADE"]

    qualificadas = [f"{r} estável" for r in estaveis] + [f"{r} em recuperação" for r in recuperacao] + \
                   [f"{r} em deterioração" for r in deterioracao]
    base = "; ".join(qualificadas) or "sem tendência clara nos fundamentos disponíveis"
    if confirmados:
        base += f"; {len(confirmados)} catalisador(es) confirmado(s) nos próximos 60 dias"

    if recuperacao:
        otimista = f"se {', '.join(recuperacao)} continuar(em) em recuperação"
    else:
        otimista = "se a tendência atual de fundamentos se mantiver ou melhorar"
    if confirmados:
        otimista += (f" e os catalisadores confirmados ({', '.join(c['categoria'] for c in confirmados[:2])}) "
                      "se concretizarem favoravelmente")

    if deterioracao:
        pessimista = f"se {', '.join(deterioracao)} continuar(em) em deterioração"
    else:
        pessimista = "se a tendência de fundamentos piorar"
    pessimista += (f", considerando {n_riscos} risco(s) de indicador já identificado(s)" if n_riscos
                   else ", sem nenhum risco de indicador identificado ainda")
    if divergencia:
        pessimista += "; recomendação já diverge entre casas de research, reforçando a incerteza"

    resposta = (f"OTIMISTA: {otimista.capitalize()}. BASE: cenário apoiado em {base}. "
                f"PESSIMISTA: {pessimista.capitalize()}.")
    return {"pergunta": "Cenários (otimista, base e pessimista)", "resposta": resposta,
            "tipo_evidencia": TIPO_HIPOTESE}


_PESO_CONFIANCA_POR_TIPO = {
    TIPO_FATO: 1.0, TIPO_CALCULO: 0.9, TIPO_ESTIMATIVA_TERCEIRO: 0.7,
    TIPO_HIPOTESE: 0.4, TIPO_INSUFICIENTE: 0.0,
}


def _calcular_confianca(blocos_avaliados: list) -> dict:
    """Score 0-100 = média dos pesos de evidência das seções analíticas
    (2 a 12, nunca a própria seção de confiança/lacunas nem o resumo
    executivo) × 100. Pesos fixos e documentados - não é uma
    probabilidade estatística calibrada, é uma régua simples e auditável:
    FATO=1,0 · CÁLCULO INTERNO=0,9 · ESTIMATIVA DE TERCEIRO=0,7 ·
    HIPÓTESE DO ANALISTA=0,4 · DADO INSUFICIENTE=0,0. >=70 ALTA, >=40
    MÉDIA, caso contrário BAIXA."""
    if not blocos_avaliados:
        return {"nivel": "BAIXA", "score": 0, "motivo": "nenhuma seção avaliável."}
    pesos = [_PESO_CONFIANCA_POR_TIPO.get(b["tipo_evidencia"], 0.0) for b in blocos_avaliados]
    score = round(sum(pesos) / len(pesos) * 100)
    nivel = "ALTA" if score >= 70 else ("MÉDIA" if score >= 40 else "BAIXA")
    contagem = Counter(b["tipo_evidencia"] for b in blocos_avaliados)
    _rotulos_contagem = {**{k: v[0] for k, v in _ROTULO_EVIDENCIA.items()}, TIPO_INSUFICIENTE: "DADO INSUFICIENTE"}
    detalhe = ", ".join(f"{_rotulos_contagem.get(k, k)}: {v}" for k, v in contagem.items())
    motivo = (f"{len(blocos_avaliados)} seção(ões) avaliadas - {detalhe}. Score = média dos pesos de "
              "evidência (FATO=1,0 · CÁLCULO INTERNO=0,9 · ESTIMATIVA DE TERCEIRO=0,7 · HIPÓTESE DO "
              "ANALISTA=0,4 · DADO INSUFICIENTE=0,0) × 100.")
    return {"nivel": nivel, "score": score, "motivo": motivo}


def _montar_conclusao(analise: dict, tese: dict | None) -> list:
    """Lista de {pergunta, resposta, tipo_evidencia} com as 14 seções da
    Conclusão de Investimento - "dado insuficiente" é uma resposta
    honesta aqui, não um placeholder a esconder."""
    fundamentos = analise.get("fundamentos")
    catalisadores = analise.get("catalisadores")
    riscos = analise.get("riscos_indicadores")
    cobertura = analise.get("cobertura_research") or {}
    cobertura_lista = cobertura.get("cobertura")
    sem_cobertura = cobertura.get("sem_cobertura") or []
    divergencia = cobertura.get("divergencia")
    fontes_indisponiveis = analise.get("fontes_indisponiveis") or []
    historico = analise.get("fundamentos_historicos")
    setorial = analise.get("comparativo_setorial")
    proximos_cat = sorted(
        [c for c in (catalisadores or []) if c["data"] >= date.today()], key=lambda c: c["data"]
    )

    lacunas_ativas = set()

    secoes_analiticas = [
        _secao_qualidade_negocio(historico, lacunas_ativas),
        _secao_crescimento_rentabilidade(fundamentos, historico, lacunas_ativas),
        _secao_estrutura_capital(fundamentos, lacunas_ativas),
        _secao_geracao_caixa(fundamentos, lacunas_ativas),
        _secao_tese_positiva(cobertura_lista),
        _secao_tese_negativa(fundamentos, divergencia, sem_cobertura),
        _secao_valuation(fundamentos, setorial, lacunas_ativas),
        _secao_catalisadores(catalisadores),
        _secao_riscos_invalidacao(riscos, tese),
        _secao_consenso_research(cobertura if analise.get("cobertura_research") is not None else None),
        _montar_cenarios(historico, catalisadores, riscos, cobertura),
    ]

    confianca = _calcular_confianca(secoes_analiticas)
    bloco_confianca = {
        "pergunta": "Confiança da análise",
        "resposta": f"{confianca['nivel']} ({confianca['score']}/100). {confianca['motivo']}",
        "tipo_evidencia": TIPO_CALCULO,
    }

    textos_lacuna = [_TEXTOS_LACUNA[k] for k in sorted(lacunas_ativas)]
    textos_lacuna += list(dict.fromkeys(
        _MOTIVO_FONTE_INDISPONIVEL.get(f, f"Fonte '{f}' indisponível nesta checagem.")
        for f in fontes_indisponiveis
    ))
    bloco_lacunas = {
        "pergunta": "Lacunas de informação",
        "resposta": (("; ".join(textos_lacuna) + ".") if textos_lacuna else
                     "Nenhuma lacuna estrutural adicional identificada nesta checagem.") +
                    " Esta síntese organiza evidência real já coletada - não é e não substitui "
                    "recomendação de compra ou venda.",
        "tipo_evidencia": TIPO_INSUFICIENTE,
    }

    n_fatos_calculos = sum(1 for b in secoes_analiticas if b["tipo_evidencia"] in (TIPO_FATO, TIPO_CALCULO))
    resumo_partes = [f"{confianca['nivel']} confiança ({confianca['score']}/100)",
                     f"{n_fatos_calculos} de {len(secoes_analiticas)} seções com FATO ou CÁLCULO INTERNO"]
    if divergencia:
        resumo_partes.append("recomendação diverge entre casas de research")
    if proximos_cat:
        resumo_partes.append(f"{len(proximos_cat)} catalisador(es) nos próximos 60 dias")
    bloco_resumo = {
        "pergunta": "Resumo executivo",
        "resposta": "; ".join(resumo_partes) + ". Ver seções abaixo para a análise completa.",
        "tipo_evidencia": TIPO_CALCULO,
    }

    return [bloco_resumo] + secoes_analiticas + [bloco_confianca, bloco_lacunas]


# rótulo + cor por tipo de evidência (pedido do redesign institucional:
# "diferencie dados observados, conclusões dos agentes, hipóteses e
# alertas" - antes FATO/CALCULO/ESTIMATIVA/HIPOTESE renderizavam todos
# com o mesmo st.markdown, sem nenhuma pista visual da natureza de cada
# resposta). Mesma linguagem de tag monoespaçada já usada em
# ui/mercado_tab.py (_tag_fato_interpretacao) e ui/news_tab.py (selo-*).
_ROTULO_EVIDENCIA = {
    TIPO_FATO: ("FATO", "var(--cinza)"),
    TIPO_CALCULO: ("CÁLCULO INTERNO", "var(--ciano)"),
    TIPO_ESTIMATIVA_TERCEIRO: ("ESTIMATIVA DE TERCEIRO", "var(--destaque)"),
    TIPO_HIPOTESE: ("HIPÓTESE DO ANALISTA", "var(--destaque)"),
}


def _controle_dcf_inline(ticker: str, fundamentos: dict | None):
    """Controle INLINE (efeito imediato, no próprio painel - nunca um
    formulário separado) pra calcular o DCF só quando o usuário informar
    as duas premissas - o PREGÃO nunca assume taxa de crescimento nem
    taxa de desconto por padrão (number_input sem `value` fixo, começa
    vazio/None). Só aparece quando há fluxo de caixa livre atual pra
    descontar (ver _secao_valuation/_TEXTOS_LACUNA['dcf'])."""
    fcf = (fundamentos or {}).get("fluxo_caixa_livre")
    if fcf is None:
        return
    with st.container(key=f"dcf_inline_{ticker}"):
        cols = st.columns(2)
        crescimento = cols[0].number_input(
            "Taxa de crescimento esperada (% a.a., premissa sua)", value=None, step=0.5,
            key=f"dcf_crescimento_{ticker}", help="Obrigatória pro DCF - o PREGÃO nunca assume um valor padrão.",
        )
        desconto = cols[1].number_input(
            "Taxa de desconto / WACC (% a.a., premissa sua)", value=None, step=0.5,
            key=f"dcf_desconto_{ticker}", help="Obrigatória pro DCF - o PREGÃO nunca assume um valor padrão.",
        )
        if crescimento is None or desconto is None:
            st.caption("Informe as duas premissas acima para calcular o valor justo por DCF.")
            return
        resultado = _dcf_calculo(fcf, crescimento, desconto, valor_mercado=fundamentos.get("valor_mercado"))
        if not resultado["calculavel"]:
            st.warning(f"DCF não calculado: {resultado['motivo']}")
            return
        st.markdown(
            f"<span style='font-size:0.62rem; letter-spacing:0.04em; color:var(--ciano);'>"
            f"[CÁLCULO INTERNO sobre HIPÓTESE DO ANALISTA - informado por você]</span> "
            f"Valor justo estimado (DCF, 5 anos de projeção): {_fmt_reais(resultado['valor_justo_estimado'], 'BR')}"
            + (f" (potencial indicativo {resultado['potencial_pct']:+.1f}% vs. valor de mercado atual)."
               if resultado.get("potencial_pct") is not None else "."),
            unsafe_allow_html=True,
        )
        st.caption(
            f"Premissas: fluxo de caixa livre atual {_fmt_reais(fcf, 'BR')} (yfinance, ponto atual) · "
            f"crescimento {crescimento:.1f}% a.a. e desconto {desconto:.1f}% a.a. informados por você · "
            "projeção simplificada de 5 anos + perpetuidade de Gordon. Não é recomendação de compra ou venda."
        )


def render_conclusao_investimento(ticker: str, prefs: dict, usuario: dict):
    """Painel final de ANÁLISES › Empresas (depois de NOTÍCIAS/CVM, pra
    fechar a análise com uma síntese depois de ver todo o detalhe) -
    reaproveita o mesmo _analise_ticker_cacheada de
    render_equity_research_executivo (zero consulta nova) + a Tese
    própria do usuário, se existir (data/research/tese.py:scorecard)."""
    try:
        analise = _analise_ticker_cacheada(ticker)
    except Exception:
        st.warning(f"Conclusão de investimento para {ticker} indisponível agora (fonte não respondeu).")
        return
    tese = scorecard(usuario["sub"], ticker)

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CONCLUSÃO DE INVESTIMENTO</div>', unsafe_allow_html=True)
        gerado_em = analise.get("gerado_em")
        if gerado_em:
            try:
                quando = gerado_em.astimezone(TZ_SP).strftime("%d/%m/%Y %H:%M")
            except (AttributeError, ValueError, OverflowError):
                quando = str(gerado_em)[:16]
            st.caption(f"Data de referência desta análise: {quando} (horário de Brasília) - dados pontuais "
                       "podem ser mais antigos, ver aviso de cada seção.")
        for bloco in _montar_conclusao(analise, tese):
            subtitulo(bloco["pergunta"])
            tipo = bloco["tipo_evidencia"]
            if tipo == TIPO_INSUFICIENTE:
                st.caption(bloco["resposta"])
            else:
                rotulo, cor = _ROTULO_EVIDENCIA.get(tipo, (None, None))
                prefixo = f"<span style='color:{cor};'>[{rotulo}]</span> " if rotulo else ""
                st.markdown(
                    f"<div style='font-size:0.78rem; letter-spacing:0.02em;'>{prefixo}{html.escape(bloco['resposta'])}</div>",
                    unsafe_allow_html=True,
                )
            if bloco["pergunta"] == "Valuation":
                _controle_dcf_inline(ticker, analise.get("fundamentos"))
        if tese:
            st.caption(
                f"Você já registrou uma Tese própria para {ticker} em {str(tese['registrado_em'])[:10]} "
                f"({tese['n_versoes']} versão(ões)) — ver RESEARCH › Minha Tese."
            )
        else:
            st.caption("Você ainda não registrou uma Tese própria para este ativo — ver RESEARCH › Minha Tese.")


# ============================================================
# COMPARATIVO DE CASAS DE ANÁLISE (Fase D, 2026-10-30)
#
# Consome data/research/comparador.py:montar_relatorio_comparativo -
# le so' a biblioteca PERMANENTE de premissas/projecoes
# (research_premissas), ja' estruturada por outra pipeline
# (data/research/resumir.py). Nenhuma chamada de IA nesta integracao de
# UI (o modulo de origem e' 100% determinístico - ver docstring dele e
# o teste tests/test_research_comparador.py:test_modulo_nao_importa_
# nada_de_ia). Reaproveita exatamente o mesmo mecanismo de "ticker em
# foco" das demais secoes desta aba (parametro `ticker`, vindo de
# app.py:ticker_selecionado) - nenhum seletor novo e redundante.
#
# Riscos e indicadores adicionais (ROE/ROIC) sao gaps HONESTOS da
# pipeline de extracao atual (nunca inventados) - a secao mostra
# disponivel=False com o motivo, em vez de omitir ou estimar.
# ============================================================

@st.cache_data(ttl=90, show_spinner=False)
def _comparativo_casas_cacheado(ticker: str) -> dict:
    """Cache na camada de UI (data/research/comparador.py nao importa
    Streamlit de proposito - usado tambem fora de sessao) - mesmo TTL
    de _analise_ticker_cacheada acima."""
    return montar_relatorio_comparativo(ticker)


def _render_riscos_e_indicadores(relatorio: dict, fmt: str):
    """Riscos (POR CASA, extraidos do texto do relatorio - nunca
    inventados) + Indicadores adicionais (ROE real do yfinance, ROIC
    honestamente indisponivel, riscos_mercado deterministicos) -
    fechamento do gap (2026-11-01, pedido do Rodrigo). Renderiza o DADO
    REAL quando disponivel; cai pro motivo honesto quando nao."""
    cols2 = st.columns(2)
    with cols2[0]:
        subtitulo("Riscos")
        riscos = relatorio["riscos"]
        if riscos.get("disponivel"):
            st.caption(f"{riscos['n_casas_com_riscos_extraidos']} de {riscos['n_casas_total']} casa(s) "
                       "com risco extraido do relatorio mais recente — nunca inventado.")
            for casa, info in sorted(riscos["por_casa"].items()):
                link = info.get("link")
                rotulo = f"[{casa}]({link})" if link else casa
                itens = "; ".join(info["riscos"])
                st.markdown(f"- {rotulo} ({info.get('data_publicacao') or '—'}): {itens}", unsafe_allow_html=False)
        else:
            st.caption(riscos["motivo"])

    with cols2[1]:
        subtitulo("Indicadores adicionais (ROE/ROIC)")
        ind = relatorio["indicadores_adicionais"]
        if ind.get("disponivel"):
            roe = ind.get("roe")
            st.markdown(f"**ROE:** {config.formatar_numero(roe, 2, fmt) + '%' if roe is not None else '—'} "
                        "<span class='cinza' style='font-size:0.68rem;'>(FATO, yfinance)</span>", unsafe_allow_html=True)
            st.caption(f"ROIC: não disponível — {ind['roic_motivo']}")
            if ind.get("riscos_mercado"):
                st.markdown("**Riscos de mercado (determinístico, dados da empresa):**")
                for alerta in ind["riscos_mercado"]:
                    st.caption(f"- {alerta}")
        else:
            st.caption(ind.get("motivo") or "indicadores fundamentalistas indisponíveis agora.")


def render_comparativo_casas(ticker: str, prefs: dict):
    """ANÁLISES › Empresas: comparativo estruturado entre casas de
    research pro ticker selecionado - estado atual por casa, consenso/
    dispersao de preco-alvo, divergencias (numerica/qualitativa/
    premissas), evolucao historica e fontes/evidencias. Cada secao
    mostra o que existe e declara explicitamente amostra insuficiente/
    dado ausente - nunca uma conclusao do Pregão nem preco-alvo
    proprio; preco-alvo/recomendacao exibidos sao sempre ESTIMATIVA DE
    TERCEIRO (da casa que publicou), em BRL (ver nota de moeda em
    data/research/comparador.py)."""
    fmt = prefs["formato_numerico"]
    try:
        relatorio = _comparativo_casas_cacheado(ticker)
    except Exception:
        st.warning(f"Comparativo de casas de research para {ticker} indisponível agora (fonte não respondeu).")
        return

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">COMPARATIVO DE CASAS DE ANÁLISE</div>', unsafe_allow_html=True)

        if not relatorio.get("disponivel"):
            st.caption(f"Comparativo indisponível agora: {relatorio.get('motivo') or 'banco de research fora do ar'}.")
            return

        st.markdown(
            f"<div class='cinza' style='font-size:0.78rem;'>{relatorio['resumo_executivo']}</div>",
            unsafe_allow_html=True,
        )

        if not relatorio.get("tabela_comparativa"):
            st.caption("Nenhuma casa monitorada tem publicação estruturada sobre este ticker na biblioteca "
                       "permanente de research ainda.")
            # indicadores_adicionais (ROE real, yfinance) nunca depende de
            # cobertura de research - continua mostrado mesmo sem nenhuma
            # casa (achado real na validação visual, 2026-11-01: ROE
            # ficava escondido por este early-return, mesmo quando a
            # consulta real ao yfinance tinha dado disponível).
            _render_riscos_e_indicadores(relatorio, fmt)
            return

        subtitulo("Tabela comparativa (estado mais recente por casa)")
        linhas = []
        for linha in relatorio["tabela_comparativa"]:
            rec = (f"{linha['recomendacao_original']} ({linha['recomendacao_categoria']})"
                   if linha.get("recomendacao_original") else "—")
            linhas.append({
                "Casa": linha["casa"],
                "Data publicação": linha.get("data_publicacao") or "—",
                "Tipo de documento": linha.get("tipo_documento") or "—",
                "Recomendação (original/categoria)": rec,
                "Preço-alvo (BRL)": _fmt_reais(linha.get("preco_alvo"), fmt),
                "Projeção receita": linha.get("projecao_receita") or "—",
                "Projeção margem EBITDA": linha.get("projecao_ebitda_margem") or "—",
                "Projeção lucro": linha.get("projecao_lucro") or "—",
            })
        st.dataframe(linhas, hide_index=True, width="stretch")

        cols = st.columns(2)
        with cols[0]:
            subtitulo("Consenso de recomendação")
            consenso = relatorio["consenso"]
            if consenso["categoria_mais_comum"]:
                st.markdown(
                    f"{consenso['categoria_mais_comum']} "
                    f"({consenso['contagem_por_categoria'][consenso['categoria_mais_comum']]} de "
                    f"{consenso['n_casas_com_recomendacao_classificada']} casa(s) classificada(s))."
                )
            elif consenso["amostra_insuficiente"]:
                st.caption(
                    f"Amostra insuficiente ({consenso['n_casas_com_recomendacao_classificada']} de "
                    f"{consenso['n_casas_total']} casa(s) com recomendação classificada; mínimo de 2 exigido)."
                )
            else:
                st.caption("Empate entre categorias de recomendação — sem consenso claro.")

        with cols[1]:
            subtitulo("Dispersão de preço-alvo (BRL)")
            dispersao = relatorio["dispersao_precos_alvo"]
            if dispersao["amostra_insuficiente"]:
                st.caption(dispersao["resumo"])
            else:
                st.markdown(
                    f"Min {_fmt_reais(dispersao['minimo'], fmt)} · Máx {_fmt_reais(dispersao['maximo'], fmt)} · "
                    f"Média {_fmt_reais(dispersao['media'], fmt)} · Mediana {_fmt_reais(dispersao['mediana'], fmt)}"
                )
                st.caption(dispersao["resumo"])

        divergencias = relatorio["divergencias_premissas"]
        div_rec = divergencias["recomendacao"]
        subtitulo("Divergências")
        if div_rec["numerica"] or div_rec["qualitativa"]:
            partes = []
            if div_rec["numerica"]:
                partes.append("NUMÉRICA (preços-alvo distantes)")
            if div_rec["qualitativa"]:
                partes.append("QUALITATIVA (categorias de recomendação diferentes)")
            extra = ""
            if div_rec["casa_mais_otimista"]:
                extra = (f" Casa mais otimista: {div_rec['casa_mais_otimista']}. Casa mais cautelosa: "
                         f"{div_rec['casa_mais_cautelosa']} (critério: {div_rec['criterio_otimismo']}).")
            st.warning(f"Divergência {' e '.join(partes)} entre as casas.{extra}")
        else:
            st.caption("Nenhuma divergência numérica ou qualitativa detectada entre as casas com dado suficiente "
                       "pra comparar.")

        premissas_div = divergencias["premissas"]["premissas_divergentes"]
        if premissas_div:
            st.markdown("Premissas mencionadas por algumas casas e não por outras pro mesmo ticker "
                        "(fato observado, sem inferir o motivo):")
            for item in premissas_div:
                st.markdown(
                    f"- \"{item['premissa']}\" — mencionada por {', '.join(item['casas_que_mencionam'])}; "
                    f"não mencionada por {', '.join(item['casas_que_nao_mencionam'])}."
                )
        elif divergencias["premissas"]["amostra_insuficiente"]:
            st.caption("Amostra insuficiente pra comparar premissas entre casas (menos de 2 casas com premissas "
                       "extraídas pro estado mais recente).")
        else:
            st.caption("Nenhuma divergência de premissas identificada entre as casas.")

        subtitulo("Revisões recentes / evolução histórica")
        revisoes = relatorio["revisoes_recentes"]
        if not revisoes:
            st.caption("Sem evolução histórica disponível pra este ticker.")
        else:
            for casa, dados in sorted(revisoes.items()):
                texto_atual = f"**{casa}** — atual: {dados.get('recomendacao_atual') or '—'}"
                if dados.get("preco_alvo_atual") is not None:
                    texto_atual += f" · {_fmt_reais(dados['preco_alvo_atual'], fmt)}"
                if dados.get("data_publicacao_atual"):
                    texto_atual += f" ({dados['data_publicacao_atual']})"
                st.markdown(texto_atual)
                if dados.get("mudou_recomendacao_ou_alvo_hoje"):
                    st.caption("Mudança de recomendação/preço-alvo persistida hoje (ver histórico estruturado).")
                publicacoes_antigas = dados.get("publicacoes_historicas") or []
                if publicacoes_antigas:
                    with st.expander(f"Publicações anteriores de {casa} ({len(publicacoes_antigas)}) — histórico, nunca o estado atual"):
                        for pub in publicacoes_antigas:
                            rec = f" · {pub['recomendacao']}" if pub.get("recomendacao") else ""
                            alvo = f" · {_fmt_reais(pub['preco_alvo'], fmt)}" if pub.get("preco_alvo") is not None else ""
                            st.markdown(
                                f"- {pub.get('data_publicacao') or '—'}{rec}{alvo}: "
                                f"[{pub.get('titulo') or 'ver relatório'}]({pub.get('link')})"
                            )
                if not dados.get("historico_estruturado_disponivel"):
                    st.caption(f"{casa}: sem histórico estruturado de mudança de recomendação persistido "
                               "(ver data/research/historico.py) — não é erro, só ausência real dessa fonte "
                               "específica pra esta casa hoje.")

        _render_riscos_e_indicadores(relatorio, fmt)

        if relatorio.get("pontos_atencao"):
            subtitulo("Pontos de atenção")
            for aviso in relatorio["pontos_atencao"]:
                st.caption(f"- {aviso}")

        if relatorio.get("fontes_evidencias"):
            with st.expander(f"Fontes/evidências ({len(relatorio['fontes_evidencias'])})"):
                for fonte in relatorio["fontes_evidencias"]:
                    st.markdown(
                        f"- **{fonte['casa']}** ({fonte.get('data_publicacao') or '—'}): "
                        f"[{fonte.get('titulo') or 'ver relatório'}]({fonte.get('link')})"
                    )

        st.caption(
            "Comparativo determinístico sobre a biblioteca permanente de research (research_premissas) — "
            "nenhuma recomendação própria do PREGÃO, nenhuma chamada de IA nesta integração. Preço-alvo em "
            "BRL, sempre ESTIMATIVA DE TERCEIRO (da casa que publicou)."
        )


def _rotulo_coleta(ind: dict) -> str | None:
    """Quando o dado foi coletado (obter_indicadores guarda _coletado_em
    em toda coleta valida e o propaga no fallback). None = nenhum campo
    disponivel (fonte fora e sem coleta anterior)."""
    if not any(v is not None for k, v in ind.items() if not k.startswith("_") and k != "beta"):
        return None
    bruto = ind.get("_coletado_em")
    if not bruto:
        return "—"
    try:
        quando = datetime.fromisoformat(bruto)
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=TZ_SP)
        else:
            quando = quando.astimezone(TZ_SP)
    except (TypeError, ValueError, OverflowError):
        return "—"
    return quando.strftime("%d/%m %H:%M")


def _celula(valor, formatador):
    return formatador(valor) if valor is not None else "—"



# Mapeamento inicial explícito; fatores são indicadores relacionados, não
# uma estimativa automática de causalidade ou recomendação de investimento.
_UNIDADE_FATOR = {
    "BZ=F": "US$/barril",
    "CL=F": "US$/barril",
    "USDBRL=X": "R$/US$",
    "ZC=F": "¢/bushel",
    "ZS=F": "¢/bushel",
    "LE=F": "¢/lb",
    "HG=F": "¢/lb",
}

_FATORES_POR_TICKER = {
    "PETR3": [("Petróleo Brent", "BZ=F"), ("Petróleo WTI", "CL=F"), ("USD/BRL", "USDBRL=X")],
    "PETR4": [("Petróleo Brent", "BZ=F"), ("Petróleo WTI", "CL=F"), ("USD/BRL", "USDBRL=X")],
    "PRIO3": [("Petróleo Brent", "BZ=F"), ("Petróleo WTI", "CL=F"), ("USD/BRL", "USDBRL=X")],
    "BRAV3": [("Petróleo Brent", "BZ=F"), ("Petróleo WTI", "CL=F"), ("USD/BRL", "USDBRL=X")],
    "RECV3": [("Petróleo Brent", "BZ=F"), ("Petróleo WTI", "CL=F"), ("USD/BRL", "USDBRL=X")],
    "VALE3": [("Minério de ferro: série específica não validada", ""), ("USD/BRL", "USDBRL=X")],
    "SUZB3": [("Celulose: série específica não integrada", ""), ("USD/BRL", "USDBRL=X")],
    "KLBN11": [("Celulose: série específica não integrada", ""), ("USD/BRL", "USDBRL=X")],
    "JBSS3": [("Milho", "ZC=F"), ("Soja", "ZS=F"), ("Boi gordo (proxy)", "LE=F"), ("USD/BRL", "USDBRL=X")],
    "BEEF3": [("Milho", "ZC=F"), ("Soja", "ZS=F"), ("Boi gordo (proxy)", "LE=F"), ("USD/BRL", "USDBRL=X")],
    "MRFG3": [("Milho", "ZC=F"), ("Soja", "ZS=F"), ("Boi gordo (proxy)", "LE=F"), ("USD/BRL", "USDBRL=X")],
    "GGBR4": [("Minério de ferro: série específica não validada", ""), ("Sucata/aço: sem série integrada", ""), ("USD/BRL", "USDBRL=X")],
    "CSNA3": [("Minério de ferro: série específica não validada", ""), ("USD/BRL", "USDBRL=X")],
    "WEGE3": [("Cobre", "HG=F"), ("USD/BRL", "USDBRL=X")],
}

def _numero_finito(valor):
    """Converte valores externos em float finito; dados ruins viram indisponíveis."""
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return numero if numero == numero and abs(numero) != float("inf") else None


def _fmt_reais(valor, fmt):
    numero = _numero_finito(valor)
    if numero is None:
        return "—"
    return "R$ " + config.formatar_numero(numero, 2, fmt)


def _potencial_pct(preco_alvo, preco_atual):
    alvo = _numero_finito(preco_alvo)
    atual = _numero_finito(preco_atual)
    if alvo is None or atual is None or atual <= 0 or alvo <= 0:
        return None
    potencial = (alvo / atual - 1) * 100
    return potencial if _numero_finito(potencial) is not None else None


def _alvo_positivo(snapshot):
    """Preço-alvo do snapshot informado, sem recorrer a registros antigos."""
    if not isinstance(snapshot, dict):
        return None
    alvo = _numero_finito(snapshot.get("preco_alvo"))
    return alvo if alvo is not None and alvo > 0 else None


def _dias_desde_captura(valor, hoje=None):
    """Idade em dias do registro persistido; None se a data não for legível."""
    if not valor:
        return None
    try:
        texto = str(valor).strip()
        instante = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=TZ_SP)
        data_registro = instante.astimezone(TZ_SP).date()
    except (TypeError, ValueError, OverflowError):
        try:
            data_registro = date.fromisoformat(str(valor)[:10])
        except (TypeError, ValueError, OverflowError):
            return None
    referencia = hoje or datetime.now(TZ_SP).date()
    return (referencia - data_registro).days


def _render_research_e_fatores(ticker: str, fmt: str):
    """Mostra apenas alvos realmente persistidos e cotações de fatores mapeados."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">RESEARCH & FATORES DE MERCADO</div>', unsafe_allow_html=True)
        st.markdown(f"**{ticker}** · cobertura estruturada disponível")
        try:
            snapshots = historico_ticker("genial", ticker, limite=5)
        except Exception:
            snapshots = []
        validos = [
            s for s in snapshots
            if (_numero_finito(s.get("preco_alvo")) or 0) > 0
        ]
        ultimo = snapshots[0] if snapshots else None
        alvo_atual = _alvo_positivo(ultimo)
        if alvo_atual is not None:
            cot = obter_cotacao(ticker)
            preco = cot.get("preco") if not cot.get("erro") else None
            potencial = _potencial_pct(alvo_atual, preco)
            cols = st.columns(3)
            cols[0].metric("PREÇO-ALVO GENIAL", _fmt_reais(alvo_atual, fmt))
            cols[1].metric("PREÇO ATUAL", _fmt_reais(preco, fmt))
            cols[2].metric("POTENCIAL INDICATIVO", f"{potencial:+.1f}%" if potencial is not None else "—")
            st.caption("Preço do ativo consultado no Yahoo Finance; o atraso pode variar. O potencial é indicativo e usa o último preço retornado, não uma cotação executável.")
            captura = ultimo.get("capturado_em")
            st.caption(f"Último registro persistido: {captura or 'data indisponível'}. O histórico registra mudanças, não necessariamente o relatório mais recente.")
            idade_alvo = _dias_desde_captura(captura)
            if idade_alvo is not None and idade_alvo > 90:
                st.warning(f"Preço-alvo registrado há {idade_alvo} dias. Pode estar desatualizado; confirme a nota original da Genial antes de usar.")
        else:
            st.info("O registro mais recente não contém preço-alvo positivo válido. Um alvo histórico anterior não será apresentado como se fosse o atual.")
        st.caption("Fonte estruturada disponível nesta tela: Genial. Não há consenso multi-casa calculado enquanto os alvos comparáveis das demais casas não estiverem integrados.")
        if validos:
            subtitulo("Histórico recente de preço-alvo e recomendação")
            linhas = []
            for s in validos:
                linhas.append({
                    "Data de captura": str(s.get("capturado_em") or "—")[:10],
                    "Casa": str(s.get("casa") or "genial").upper(),
                    "Recomendação": s.get("recomendacao") or "—",
                    "Preço-alvo": _fmt_reais(s.get("preco_alvo"), fmt),
                })
            st.dataframe(linhas, hide_index=True, width="stretch")
        elif not snapshots:
            st.info("Ainda não há preço-alvo estruturado e persistido para este ticker.")
        fatores = _FATORES_POR_TICKER.get(ticker, [])
        if not fatores:
            st.caption("Ainda não há mapeamento curado de commodities/fatores para este ticker.")
            return
        subtitulo("Commodities e fatores relacionados")
        linhas_fatores = []
        for nome, simbolo in fatores:
            if not simbolo:
                linhas_fatores.append({"Fator": nome, "Contrato": "—", "Cotação": "—", "Unidade": "não integrada", "Variação": "—", "Fonte/status": "Sem série integrada"})
                continue
            dado = obter_cotacao(simbolo)
            if dado.get("erro"):
                linhas_fatores.append({"Fator": nome, "Contrato": simbolo, "Cotação": "—", "Unidade": _UNIDADE_FATOR.get(simbolo, "unidade não validada"), "Variação": "—", "Fonte/status": "Indisponível no provedor"})
                continue
            preco_fator = dado.get("preco")
            variacao_pct = _numero_finito(dado.get("variacao_pct"))
            numero_fator = _numero_finito(preco_fator)
            linhas_fatores.append({
                "Fator": nome,
                "Contrato": simbolo,
                "Cotação": _fmt_reais(numero_fator, fmt) if simbolo == "USDBRL=X" else (config.formatar_numero(numero_fator, 2, fmt) if numero_fator is not None else "—"),
                "Unidade": _UNIDADE_FATOR.get(simbolo, "unidade não validada"),
                "Variação": f"{variacao_pct:+.2f}%" if variacao_pct is not None else "—",
                "Fonte/status": "Yahoo Finance · pode haver atraso" if numero_fator is not None else "Cotação indisponível",
            })
        st.dataframe(linhas_fatores, hide_index=True, width="stretch")
        st.caption("Relações são um mapa inicial de exposição econômica, não prova de causalidade. Algumas séries são proxies e devem ser refinadas; cotações podem estar atrasadas ou indisponíveis.")

def render_fundamentos(prefs: dict):
    fmt = prefs["formato_numerico"]
    watchlist = prefs.get("watchlist") or []
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">FUNDAMENTOS — WATCHLIST</div>', unsafe_allow_html=True)
        if not watchlist:
            st.info("Adicione tickers na watchlist para comparar fundamentos.")
            return
        pct = lambda v: config.formatar_numero(v, 2, fmt) + "%"  # noqa: E731
        mult = lambda v: config.formatar_multiplo(v, 2, fmt)  # noqa: E731
        vm = lambda v: config.formatar_valor_mercado(v, fmt)  # noqa: E731
        colunas = [
            ("VALOR DE MERCADO", "valor_mercado", vm), ("P/L", "pl", mult), ("P/VP", "pvp", mult),
            ("DY 12M", "dividend_yield", pct), ("ROE", "roe", pct), ("M. LÍQUIDA", "margem_liquida", pct),
            ("M. OPERAC.", "margem_operacional", pct), ("M. EBITDA", "margem_ebitda", pct),
            ("FLUXO DE CAIXA LIVRE", "fluxo_caixa_livre", vm),
            ("DÍV. LÍQUIDA", "divida_liquida", vm),
            ("DL/EBITDA", "divida_liquida_ebitda", lambda v: config.formatar_numero(v, 1, fmt) + "x"),
        ]
        linhas = []
        for t in watchlist:
            ind = obter_indicadores(t)
            nome_t = f"<span style='color:var(--destaque); font-weight:600;'>{t}</span>"
            coleta = _rotulo_coleta(ind)
            if coleta is None:
                # nenhum campo veio (nem do fallback): fonte fora, nao "campo
                # nao informado" - linha inteira marcada como indisponivel
                linhas.append(f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'>{nome_t}</td>"
                              f"<td colspan='{len(colunas) + 1}' class='cinza' style='padding:0.2rem 0.4rem;'>"
                              f"indisponível agora (fonte não respondeu)</td></tr>")
                continue
            celulas = "".join(
                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>{_celula(ind.get(c), f)}</td>"
                for _, c, f in colunas
            )
            linhas.append(f"<tr><td style='padding:0.2rem 0.4rem 0.2rem 0;'>{nome_t}</td>{celulas}"
                          f"<td style='padding:0.2rem 0 0.2rem 0.4rem; text-align:right;' class='cinza'>{coleta}</td></tr>")
        cabecalho = "".join(f"<th style='text-align:right; padding:0 0.4rem 0.2rem;'>{r}</th>"
                            for r, _, _ in colunas)
        st.markdown(
            "<div style='overflow-x:auto; overflow-y:hidden;'><table style='width:100%; font-size:0.78rem; "
            "border-collapse:collapse;'><thead><tr class='cinza' style='font-size:0.66rem;'>"
            f"<th style='text-align:left; padding:0 0.4rem 0.2rem 0;'>TICKER</th>{cabecalho}"
            "<th style='text-align:right; padding:0 0 0.2rem 0.4rem;'>COLETA</th></tr>"
            f"</thead><tbody>{''.join(linhas)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Dados REPORTADOS pela fonte (Yahoo Finance, últimos 12 meses), atualizados a cada 12h; — = campo "
            "não informado pela fonte (nunca estimado). COLETA = quando o dado foi obtido (Brasília); se a fonte "
            "falhou agora, vale a última coleta bem-sucedida, com a data dela. Receita, lucro e fluxo de caixa em série histórica "
            "ainda não têm fonte integrada; documentos de resultado oficiais ficam em NOTÍCIAS › Documentos CVM."
        )
    if watchlist:
        ticker_foco = st.selectbox("AÇÃO PARA RESEARCH & FATORES", options=watchlist, key="fund_research_ticker")
        _render_research_e_fatores(ticker_foco, fmt)
    cols = st.columns(2)
    with cols[0]:
        navegacao.link("Documentos de resultado (CVM) ↗", "noticias", "documentos", chave="fund_cvm", width="stretch")
    with cols[1]:
        navegacao.link("Valuation por múltiplos ↗", "analises", "valuation", chave="fund_val", width="stretch")


# ============================================================
# REVISÃO DE RESULTADOS TRIMESTRAIS (2026-10-26)
#
# Integra o Earnings Reviewer (data/earnings/reviewer.py + cvm_dre.py/
# sec_xbrl.py) na aba ANÁLISES › Empresas - esses módulos já existiam
# prontos, testados e 100% determinísticos (zero IA), mas sem NENHUM
# consumidor de UI (confirmado por busca no repositório inteiro antes
# de começar esta integração: zero import de data.earnings em ui/*.py
# ou jobs/*.py). Esta seção só CONSOME o que reviewer.py já calcula -
# nenhuma conta nova, nenhuma estimativa, nenhuma chamada de IA.
#
# Isolamento de falha (mesmo padrão de data/sintese_mercado.py e
# data/market_researcher.py): _gerar_nota_earnings nunca deixa uma
# exceção da fonte (CVM/SEC fora do ar, dado malformado) escapar pra
# quem chama - devolve disponivel=False com motivo explícito. Isso
# garante que abrir a revisão de UM ticker nunca derruba a tela nem
# contamina a revisão de outro ticker chamado depois (mesma função,
# chamada de novo) - ver tests/test_analises_earnings_review_ui.py.
# ============================================================

_ROTULOS_METRICAS_EARNINGS = (
    ("receita_liquida", "Receita líquida"),
    ("resultado_bruto", "Resultado bruto"),
    ("ebit", "EBIT"),
    ("resultado_antes_tributos", "Resultado antes de tributos"),
    ("lucro_liquido_consolidado", "Lucro líquido consolidado"),
)
# lucro_liquido_controladora só existe no plano de contas da CVM
# (cvm_dre.CONTAS_DRE) - sec_xbrl.TAGS_POR_METRICA nunca tenta essa
# conta pra empresas internacionais, então essa linha é estrutural
# (não aplicável), nunca "fonte não respondeu" - por isso só entra na
# tabela quando pais_code == "BR" (ver _linhas_metricas_earnings).
_ROTULO_LUCRO_CONTROLADORA_BR = ("lucro_liquido_controladora", "Lucro líquido - controladora")

_PREFIXO_MOEDA_EARNINGS = {"REAL": "R$", "USD": "US$"}
_ESCALA_EARNINGS = {"MIL": 1_000.0, "MILHAO": 1_000_000.0}

# Movidos pra data/earnings/reviewer.py em 2026-10-30 (evolução da Conclusão
# de Investimento - data/market_researcher.py também precisa enumerar
# trimestres civis, sem acoplar em ui/). Alias mantido com o nome privado
# original - testes existentes (tests/test_analises_earnings_review_ui.py)
# chamam esses nomes direto neste módulo, zero mudança de comportamento.
_trimestres_candidatos_br = earnings_reviewer.trimestres_candidatos_br
_ultimo_trimestre_civil = earnings_reviewer.ultimo_trimestre_civil


def _mesmo_dia_ano_anterior(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)  # 29/02 em ano não bissexto


def _fmt_moeda_earnings(valor, moeda, escala_moeda=None, fmt="BR") -> str:
    """Valor monetário compacto (R$/US$ ... bi/mi), com sinal explícito
    pra prejuízo - mesma lógica de data/earnings/editorial.py:_fmt_moeda,
    reimplementada aqui (não importada) de propósito: a UI não deve
    depender de função privada (prefixo `_`) de outro módulo que pode
    mudar sem aviso - mesmo raciocínio de cvm_dre.py ao duplicar
    _baixar_csv_do_zip em vez de importar de data/cvm.py."""
    if valor is None:
        return "indisponível"
    absoluto = valor * _ESCALA_EARNINGS.get((escala_moeda or "").upper(), 1.0)
    prefixo = _PREFIXO_MOEDA_EARNINGS.get((moeda or "").upper(), f"{moeda or ''} ")
    grandeza = abs(absoluto)
    if grandeza >= 1_000_000_000:
        texto = f"{prefixo}{config.formatar_numero(grandeza / 1_000_000_000, 1, fmt)} bi"
    elif grandeza >= 1_000_000:
        texto = f"{prefixo}{config.formatar_numero(grandeza / 1_000_000, 1, fmt)} mi"
    else:
        texto = f"{prefixo}{config.formatar_numero(grandeza, 0, fmt)}"
    return ("-" if absoluto < 0 else "") + texto


def _fmt_variacao_pct_earnings(pct, limiar: float = 1.0) -> str:
    """'indisponível' (nunca 0/estimado) quando a fonte não devolveu o
    número; caso contrário, sempre mostra o valor REAL, rotulando
    'estável' quando |pct| < limiar - estável é um FATO (variação
    pequena/neutra), nunca confundido com dado ausente."""
    if pct is None:
        return "indisponível"
    rotulo = "alta" if pct > limiar else ("queda" if pct < -limiar else "estável")
    return f"{pct:+.1f}% ({rotulo})"


def _linhas_metricas_earnings(nota: dict, pais_code: str, fmt: str) -> list:
    moeda, escala = nota.get("moeda"), nota.get("escala_moeda")
    rotulos = list(_ROTULOS_METRICAS_EARNINGS)
    if pais_code == "BR":
        rotulos.append(_ROTULO_LUCRO_CONTROLADORA_BR)
    linhas = []
    for chave, rotulo in rotulos:
        valores = nota.get("metricas", {}).get(chave)
        if valores is None:
            linhas.append({"Conta": rotulo, "Valor atual": "indisponível",
                            "Variação YoY": "indisponível", "Variação QoQ": "indisponível"})
            continue
        # QoQ nao e' calculado NA NOTA INTERNACIONAL (montar_nota_internacional
        # nunca adiciona qoq_variacao_pct - ver docstring de reviewer.py) -
        # distinto de "fonte nao respondeu": e' uma limitacao estrutural
        # desta chamada, por isso o rotulo e' diferente de "indisponivel".
        qoq_texto = ("não calculado nesta nota (ver Limitações)" if pais_code != "BR"
                     else _fmt_variacao_pct_earnings(valores.get("qoq_variacao_pct")))
        linhas.append({
            "Conta": rotulo,
            "Valor atual": _fmt_moeda_earnings(valores.get("atual"), moeda, escala, fmt),
            "Variação YoY": _fmt_variacao_pct_earnings(valores.get("yoy_variacao_pct")),
            "Variação QoQ": qoq_texto,
        })
    return linhas


def _fmt_gerado_em(valor: str) -> str:
    if not valor:
        return "—"
    try:
        instante = datetime.fromisoformat(str(valor))
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        return instante.astimezone(TZ_SP).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError, OverflowError):
        return str(valor)[:10]


def _gerar_nota_earnings(ticker: str, pais_code: str, periodo: dict) -> dict:
    """Gera a nota do Earnings Reviewer pra 1 ticker, isolada por
    try/except (mesmo padrão de data/sintese_mercado.py e
    data/market_researcher.py): qualquer falha na consulta à fonte
    (CVM/SEC fora do ar, dado malformado, exceção inesperada) vira
    disponivel=False com motivo explícito - NUNCA propaga, nunca
    derruba a tela, nunca afeta a revisão de outro ticker chamado
    depois nesta mesma sessão. Persistência (salvar_versao) também é
    best-effort: se o Supabase falhar na gravação, a nota JÁ CALCULADA
    ainda é mostrada (falha de persistência não é falha de exibição)."""
    try:
        if pais_code == "BR":
            nota = earnings_reviewer.montar_nota_br(ticker, periodo["ano"], periodo["trimestre"])
        else:
            nota = earnings_reviewer.montar_nota_internacional(
                ticker, periodo["inicio"], periodo["fim"], periodo["inicio_ant"], periodo["fim_ant"],
            )
    except Exception:
        # nunca expõe tipo/mensagem bruta da exceção na tela (mesmo
        # principio de data/research/resumir.py:_log_erro_ia - detalhe
        # tecnico fica so' no log, aqui nem logado por falta de logger
        # dedicado nesta integracao, so' nunca mostrado ao usuario).
        return {
            "ticker": ticker.upper(), "pais": pais_code, "disponivel": False,
            "motivo": "falha ao consultar a fonte agora (CVM/SEC indisponível ou dado malformado).",
        }
    if nota.get("disponivel"):
        try:
            earnings_reviewer.salvar_versao(nota)
        except Exception:
            pass
    return nota


def _historico_revisao_earnings(nota: dict) -> dict:
    """{'anterior': conteudo_da_ultima_nota_persistida|None, 'mudancas':
    list} - NUNCA sobrescreve nem apaga a versão anterior (só lê, via
    reviewer.obter_ultima_versao); isolado por try/except pra uma falha
    de leitura do histórico não derrubar a revisão atual, que já foi
    calculada com sucesso."""
    if not nota.get("disponivel"):
        return {"anterior": None, "mudancas": []}
    try:
        anterior = earnings_reviewer.obter_ultima_versao(
            nota["ticker"], nota["pais"], excluir_periodo=nota.get("periodo_label"),
        )
    except Exception:
        anterior = None
    try:
        mudancas = earnings_reviewer.comparar_com_versao_anterior(nota, anterior)
    except Exception:
        mudancas = []
    return {"anterior": anterior, "mudancas": mudancas}


def _bloco_interpretacao_earnings(texto: str):
    """Bloco visualmente separado pra [INTERPRETAÇÃO] (nunca misturado
    na mesma linha de um FATO sem rótulo) - borda lateral colorida,
    mesmo princípio visual de data/research resumos (_bloco_resumo em
    ui/research_tab.py), cor diferente pra não confundir com fato."""
    st.markdown(
        f"<div style='border-left:3px solid var(--destaque); padding:0.25rem 0 0.25rem 0.6rem; "
        f"margin:0.3rem 0; font-size:0.78rem; background:color-mix(in srgb, var(--neutro) 3%, transparent);'>{html.escape(texto)}</div>",
        unsafe_allow_html=True,
    )


def _bloco_educacao_financeira_earnings(texto: str):
    """Bloco visualmente separado pra [O QUE ISSO SIGNIFICA] (educação
    financeira determinística, data/earnings/reviewer.py:
    _nota_educativa_receita_vs_lucro) - cor diferente da usada em
    [INTERPRETAÇÃO] (var(--destaque) acima) de propósito: aqui é um
    conceito geral de finanças ancorado no número desta empresa, nunca
    uma leitura do resultado dela nem recomendação."""
    st.markdown(
        f"<div style='border-left:3px solid var(--ciano); padding:0.25rem 0 0.25rem 0.6rem; "
        f"margin:0.3rem 0; font-size:0.78rem; background:color-mix(in srgb, var(--neutro) 3%, transparent);'>{html.escape(texto)}</div>",
        unsafe_allow_html=True,
    )


def render_revisao_resultados(ticker: str, prefs: dict):
    """ANÁLISES › Empresas: nota estruturada de resultado trimestral
    (Earnings Reviewer) pro ticker selecionado - só números já
    normalizados por cvm_dre.py (Brasil) ou sec_xbrl.py (EUA/registrados
    em config.ATIVOS_CADASTRO_US), ZERO chamada de IA/estimativa nesta
    integração (reaproveita só o que data/earnings/reviewer.py já
    calcula). Reaproveita o versionamento append-only já existente
    (salvar_versao/comparar_com_versao_anterior) - nunca sobrescreve a
    nota anterior do mesmo ticker/período.

    Período: para empresas brasileiras, a UI já sabe enumerar
    trimestres civis (1T/2T/3T - Q4 fora de escopo, ver cvm_dre.py) e
    oferece o mais recente por padrão, com os anteriores disponíveis no
    seletor (controle inline, efeito imediato). Para empresas
    internacionais, o calendário fiscal real não é detectado
    automaticamente (limitação já documentada em reviewer.py) - a UI
    oferece um ponto de partida editável (trimestre civil) e pede
    confirmação das datas exatas do 10-Q/10-K antes de consultar."""
    fmt = prefs["formato_numerico"]
    hoje = datetime.now(TZ_SP).date()
    pais_cfg = config.info_ativo(ticker).get("pais")
    pais_code = "BR" if pais_cfg == "Brasil" else "US"

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">REVISÃO DE RESULTADOS TRIMESTRAIS</div>', unsafe_allow_html=True)
        st.caption(
            "Nota determinística a partir de dados oficiais (CVM/SEC) - nunca gerada por IA. "
            "FATOS (números e variações já calculadas) ficam no corpo do texto; blocos destacados "
            "marcados [INTERPRETAÇÃO] são leituras derivadas só dos deltas já calculados, nunca texto livre."
        )

        if pais_code == "BR":
            candidatos = _trimestres_candidatos_br(hoje)
            if not candidatos:
                st.info("Nenhum trimestre civil (1T-3T) já encerrado ainda para calcular.")
                return
            rotulos = [f"{tri}T{ano}" for ano, tri in candidatos]
            escolha = st.selectbox(
                "Trimestre", rotulos, index=0, key=f"earnings_periodo_br_{ticker}",
                help="Trimestre civil já encerrado - a disponibilidade real depende da CVM já ter publicado o ITR correspondente.",
            )
            ano, tri = candidatos[rotulos.index(escolha)]
            periodo = {"ano": ano, "trimestre": tri}
        else:
            inicio_padrao, fim_padrao = _ultimo_trimestre_civil(hoje)
            col1, col2 = st.columns(2)
            inicio = col1.date_input("Início do trimestre reportado", value=inicio_padrao,
                                      key=f"earnings_inicio_us_{ticker}")
            fim = col2.date_input("Fim do trimestre reportado", value=fim_padrao,
                                   key=f"earnings_fim_us_{ticker}")
            st.caption(
                "Empresa internacional: o PREGÃO não detecta o calendário fiscal automaticamente (pode ser "
                "diferente do calendário civil) - confirme as datas exatas do período reportado no 10-Q/10-K "
                "antes de consultar. A comparação anual usa a mesma data um ano antes."
            )
            inicio_ant, fim_ant = _mesmo_dia_ano_anterior(inicio), _mesmo_dia_ano_anterior(fim)
            periodo = {
                "inicio": inicio.isoformat(), "fim": fim.isoformat(),
                "inicio_ant": inicio_ant.isoformat(), "fim_ant": fim_ant.isoformat(),
            }

        nota = _gerar_nota_earnings(ticker, pais_code, periodo)

        if not nota.get("disponivel"):
            st.info(f"Revisão indisponível para {ticker} neste período: "
                    f"{nota.get('motivo') or 'motivo não especificado'}.")
            return

        nomes_fonte = ", ".join(dict.fromkeys(f.get("nome") for f in (nota.get("fontes") or []) if f.get("nome")))
        st.markdown(f"**{nota.get('empresa') or ticker}** ({nota['ticker']}) · {nota['periodo_label']}")
        st.caption(
            f"Análise gerada em {_fmt_gerado_em(nota.get('gerado_em'))} · "
            f"fonte: {nomes_fonte or 'não identificada'} ({'CVM' if pais_code == 'BR' else 'SEC'})."
        )

        st.dataframe(_linhas_metricas_earnings(nota, pais_code, fmt), hide_index=True, width="stretch")

        if nota.get("margem_bruta_pct") is not None:
            texto_margem = f"Margem bruta: {config.formatar_numero(nota['margem_bruta_pct'], 1, fmt)}%"
            anterior_pct = nota.get("margem_bruta_yoy_anterior_pct")
            if anterior_pct is not None:
                delta = nota["margem_bruta_pct"] - anterior_pct
                texto_margem += (f" · mesmo período ano anterior: {config.formatar_numero(anterior_pct, 1, fmt)}% "
                                  f"({delta:+.1f} p.p.)")
            else:
                texto_margem += " · sem margem bruta do mesmo período do ano anterior pra comparar"
            st.markdown(texto_margem)
        else:
            st.caption("Margem bruta: indisponível (receita líquida ou resultado bruto não reportados no trimestre isolado).")

        interpretacoes = nota.get("interpretacoes") or []
        if interpretacoes:
            for texto in interpretacoes:
                _bloco_interpretacao_earnings(texto)
        else:
            st.caption("Nenhuma [INTERPRETAÇÃO] gerada nesta nota (variação de margem bruta abaixo do limiar de "
                       "1 p.p., ou dado insuficiente pra calculá-la).")

        for texto_educativo in nota.get("educacao_financeira") or []:
            _bloco_educacao_financeira_earnings(texto_educativo)

        historico = _historico_revisao_earnings(nota)
        anterior, mudancas = historico["anterior"], historico["mudancas"]
        if anterior is None:
            st.caption("Primeira revisão registrada para este ticker (sem versão anterior persistida pra comparar).")
        elif mudancas:
            for m in mudancas:
                st.warning(
                    f"{m['metrica']}: mudou de {m['direcao_anterior']} pra {m['direcao_atual']} (YoY) entre "
                    f"{m['periodo_anterior']} e {m['periodo_atual']}."
                )
        else:
            st.caption(f"Nenhuma métrica mudou de direção (YoY) desde a última revisão persistida "
                       f"({anterior.get('periodo_label', '—')}).")

        with st.expander("Limitações desta nota"):
            for lim in nota.get("limitacoes") or []:
                st.caption(f"- {lim}")
