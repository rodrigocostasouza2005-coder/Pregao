# -*- coding: utf-8 -*-
"""Area ANALISES do PREGAO 2.0 (ui/navegacao.py). Empresas = a antiga
EQUITY (continua em app.py, intocada no miolo); aqui ficam a barra de
vinculos da empresa (empresa -> setor/noticias/radar/fundamentos) e a
subaba Fundamentos. Valuation/Teses vem de ui/radar_tab.py.

Fundamentos so' mostra o que a fonte reporta HOJE (data/prices.py:
obter_indicadores, Yahoo Finance, cache de 12h) - receita, lucro e fluxo
de caixa em serie historica nao existem em nenhuma fonte integrada, e a
tela diz isso em vez de estimar."""

import html
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.earnings import reviewer as earnings_reviewer
from data.market_researcher import analise_ticker
from data.prices import obter_cotacao, obter_indicadores
from data.radar import (
    TIPO_CALCULO, TIPO_ESTIMATIVA_TERCEIRO, TIPO_FATO, TIPO_HIPOTESE, TIPO_INSUFICIENTE,
    comparaveis_setor,
)
from data.research.historico import historico_ticker
from data.research.tese import scorecard
from ui import navegacao
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

        st.markdown("**Momento da empresa**")
        if fundamentos is None:
            st.caption("Fundamentos indisponíveis agora (fonte não respondeu).")
        else:
            cols = st.columns(4)
            cols[0].metric("P/L", _celula(fundamentos.get("pl"), lambda v: config.formatar_multiplo(v, 2, fmt)))
            cols[1].metric("P/VP", _celula(fundamentos.get("pvp"), lambda v: config.formatar_multiplo(v, 2, fmt)))
            cols[2].metric("ROE", _celula(fundamentos.get("roe"), lambda v: config.formatar_numero(v, 2, fmt) + "%"))
            cols[3].metric("DÍV/EBITDA", _celula(fundamentos.get("divida_liquida_ebitda"),
                                                  lambda v: config.formatar_numero(v, 1, fmt) + "x"))
            for alerta in fundamentos.get("alerta_qualidade") or []:
                st.warning(alerta)
            if st.button("Comparar com o setor ↗", key=f"empresa_comp_setor_{ticker}",
                          help="P/L, P/VP e dividend yield mediano dos outros papéis do mesmo setor "
                               "(RADAR/data/radar.py:comparaveis_setor) - consulta ao vivo sob demanda."):
                _dialog_comparativo_setor_empresa(ticker, prefs)

        st.markdown("**Catalisadores**")
        if catalisadores is None:
            st.caption("Catalisadores indisponíveis agora.")
        elif not catalisadores:
            st.caption("Nenhum catalisador (resultado/proventos) identificado nos próximos 60 dias.")
        else:
            for c in catalisadores:
                selo = "confirmado" if c.get("confirmado") else "estimado/prazo regulatório"
                st.markdown(f"- {c['categoria']} em {c['data'].strftime('%d/%m/%Y')} ({selo})")

        st.markdown("**Mudanças de tese e CVM**")
        if mudancas is None:
            st.caption("Mudanças de tese indisponíveis agora.")
        elif not mudancas:
            st.caption("Nenhuma mudança de tese/CVM verificada recentemente.")
        else:
            for m in mudancas:
                if m.get("fonte_url"):
                    fonte = f" — [{m.get('fonte_label') or 'fonte'}]({m['fonte_url']})"
                elif m.get("fonte_label"):
                    fonte = f" — {m['fonte_label']}"
                else:
                    fonte = ""
                st.markdown(f"- {m['data_evento'].strftime('%d/%m/%Y')}: {m['descricao']}{fonte}")

        st.markdown("**Research das casas**")
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
                for item in itens_cobertura:
                    rec = f" · {item['recomendacao']}" if item.get("recomendacao") else ""
                    st.markdown(f"- **{item['casa']}** ({str(item['data'])[:10]}){rec}: "
                                f"[{item.get('titulo') or 'ver relatório'}]({item['link']})")
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
# CONCLUSÃO DE INVESTIMENTO (2026-10-23)
#
# Complemento de render_equity_research_executivo (acima): aquele painel
# já mostra momento/catalisadores/mudanças/research das casas - aqui só
# falta sintetizar isso numa conclusão que responda as 7 perguntas de
# equity research (qualidade do negócio, momento, tese a favor/contra,
# avaliação, o que monitorar, o que invalidaria). _montar_conclusao é
# função pura (sem Streamlit, sem IA): cada resposta cita só o que já
# está em `analise` (mesmo dict de analise_ticker, via
# _analise_ticker_cacheada - zero consulta nova) ou declara "dado
# insuficiente" explícito. Nunca emite recomendação de compra/venda -
# esse conceito não existe no retorno da função.
# ============================================================

def _montar_conclusao(analise: dict, tese: dict | None) -> list:
    """Lista de {pergunta, resposta, tipo_evidencia} - "dado insuficiente"
    é uma resposta honesta aqui, não um placeholder a esconder."""
    fundamentos = analise.get("fundamentos")
    catalisadores = analise.get("catalisadores")
    mudancas = analise.get("mudancas_tese")
    riscos = analise.get("riscos_indicadores")
    cobertura = analise.get("cobertura_research") or {}
    cobertura_lista = cobertura.get("cobertura")
    sem_cobertura = cobertura.get("sem_cobertura") or []
    divergencia = cobertura.get("divergencia")
    fontes_indisponiveis = analise.get("fontes_indisponiveis") or []
    proximos_cat = sorted(
        [c for c in (catalisadores or []) if c["data"] >= date.today()], key=lambda c: c["data"]
    )

    blocos = [{
        "pergunta": "Qualidade do negócio",
        "resposta": "Dado insuficiente: o PREGÃO ainda não integra receita, margem ou fluxo de caixa em série "
                    "histórica (só os múltiplos pontuais do período mais recente, em Avaliação abaixo) - não dá "
                    "pra avaliar a qualidade do negócio em si com o que está disponível hoje.",
        "tipo_evidencia": TIPO_INSUFICIENTE,
    }]

    if mudancas:
        m = mudancas[0]
        blocos.append({
            "pergunta": "Momento atual",
            "resposta": f"{m['categoria']}: {m['descricao']} ({m['data_evento'].strftime('%d/%m/%Y')}).",
            "tipo_evidencia": m.get("tipo_evidencia", TIPO_FATO),
        })
    elif mudancas is not None:
        blocos.append({
            "pergunta": "Momento atual",
            "resposta": "Nenhuma mudança de tese ou fato relevante verificado nas fontes monitoradas na janela "
                        "recente.",
            "tipo_evidencia": TIPO_FATO,
        })
    else:
        blocos.append({
            "pergunta": "Momento atual",
            "resposta": "Dado insuficiente: fonte de catalisadores/mudanças de tese indisponível nesta checagem.",
            "tipo_evidencia": TIPO_INSUFICIENTE,
        })

    recomendacoes = [c for c in (cobertura_lista or []) if c.get("recomendacao")]
    if recomendacoes or proximos_cat:
        partes = [f"{r['casa']}: {r['recomendacao']} ({str(r['data'])[:10]})" for r in recomendacoes]
        partes += [f"{c['categoria']} em {c['data'].strftime('%d/%m/%Y')} ({c['status_label']})"
                   for c in proximos_cat[:2]]
        blocos.append({
            "pergunta": "O que sustenta uma leitura positiva",
            "resposta": "; ".join(partes) + ".",
            "tipo_evidencia": TIPO_FATO if recomendacoes else TIPO_ESTIMATIVA_TERCEIRO,
        })
    else:
        blocos.append({
            "pergunta": "O que sustenta uma leitura positiva",
            "resposta": "Dado insuficiente: nenhuma recomendação estruturada nem catalisador futuro identificado "
                        "nas fontes monitoradas.",
            "tipo_evidencia": TIPO_INSUFICIENTE,
        })

    contrarios = list((fundamentos or {}).get("alerta_qualidade") or [])
    if divergencia:
        contrarios.append(divergencia["descricao"])
    if sem_cobertura:
        contrarios.append(f"sem cobertura recente de: {', '.join(sem_cobertura)}")
    if contrarios:
        blocos.append({
            "pergunta": "Principais argumentos contrários / lacunas de cobertura",
            "resposta": "; ".join(contrarios) + ".",
            "tipo_evidencia": TIPO_CALCULO if fundamentos else TIPO_INSUFICIENTE,
        })
    else:
        blocos.append({
            "pergunta": "Principais argumentos contrários / lacunas de cobertura",
            "resposta": "Nenhum alerta de qualidade nos indicadores monitorados (P/L, margem, dívida/EBITDA) nem "
                        "divergência de recomendação entre casas.",
            "tipo_evidencia": TIPO_CALCULO if fundamentos else TIPO_INSUFICIENTE,
        })

    if fundamentos and fundamentos.get("preco") is not None:
        pl, pvp = fundamentos.get("pl"), fundamentos.get("pvp")
        partes_val = []
        if pl is not None:
            partes_val.append(f"P/L {pl:.1f}x")
        if pvp is not None:
            partes_val.append(f"P/VP {pvp:.2f}x")
        texto_val = ", ".join(partes_val) if partes_val else (
            "sem P/L ou P/VP comparável (lucro ou patrimônio negativo, ou empresa fora do modelo tradicional)"
        )
        blocos.append({
            "pergunta": "Avaliação (caro ou barato)",
            "resposta": f"Múltiplos reportados agora: {texto_val}. Sem comparação com a mediana do setor nesta "
                        "síntese e sem valor justo calculado pelo PREGÃO (modelo próprio ainda não existe).",
            "tipo_evidencia": TIPO_FATO if partes_val else TIPO_INSUFICIENTE,
        })
    else:
        blocos.append({
            "pergunta": "Avaliação (caro ou barato)",
            "resposta": "Dado insuficiente: sem cotação ou múltiplos disponíveis agora.",
            "tipo_evidencia": TIPO_INSUFICIENTE,
        })

    monitorar = [f"{c['categoria']} em {c['data'].strftime('%d/%m/%Y')}" for c in proximos_cat[:3]]
    if sem_cobertura:
        monitorar.append(f"cobertura ainda ausente: {', '.join(sem_cobertura)}")
    blocos.append({
        "pergunta": "O que monitorar a seguir",
        "resposta": ("; ".join(monitorar) + ".") if monitorar else
                    "Nenhum catalisador identificado nos próximos 60 dias nas fontes monitoradas.",
        "tipo_evidencia": TIPO_FATO if monitorar else TIPO_INSUFICIENTE,
    })

    riscos_tese_usuario = (tese or {}).get("riscos") or []
    invalidadores = list(riscos or []) + list(riscos_tese_usuario)
    if invalidadores:
        origem = " (inclui riscos registrados na sua Tese própria)" if riscos_tese_usuario else ""
        blocos.append({
            "pergunta": "O que invalidaria a tese",
            "resposta": "; ".join(invalidadores) + f".{origem}",
            "tipo_evidencia": TIPO_CALCULO if riscos else TIPO_HIPOTESE,
        })
    else:
        blocos.append({
            "pergunta": "O que invalidaria a tese",
            "resposta": "Dado insuficiente: nenhum risco estrutural identificado nos indicadores monitorados; "
                        "registre riscos específicos em RESEARCH › Minha Tese.",
            "tipo_evidencia": TIPO_INSUFICIENTE,
        })

    lacunas = list(fontes_indisponiveis) + ["receita/margem em série histórica (sem fonte integrada ainda)"]
    blocos.append({
        "pergunta": "Confiança e lacunas desta análise",
        "resposta": f"Lacunas conhecidas: {', '.join(lacunas)}. Esta síntese organiza evidência real já "
                    "coletada - não é e não substitui recomendação de compra ou venda.",
        "tipo_evidencia": TIPO_INSUFICIENTE,
    })

    return blocos


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
        for bloco in _montar_conclusao(analise, tese):
            st.markdown(f"**{bloco['pergunta']}**")
            if bloco["tipo_evidencia"] == TIPO_INSUFICIENTE:
                st.caption(bloco["resposta"])
            else:
                st.markdown(bloco["resposta"])
        if tese:
            st.caption(
                f"Você já registrou uma Tese própria para {ticker} em {str(tese['registrado_em'])[:10]} "
                f"({tese['n_versoes']} versão(ões)) — ver RESEARCH › Minha Tese."
            )
        else:
            st.caption("Você ainda não registrou uma Tese própria para este ativo — ver RESEARCH › Minha Tese.")


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
            st.markdown("**Histórico recente de preço-alvo e recomendação**")
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
        st.markdown("**Commodities e fatores relacionados**")
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
        cabecalho = "".join(f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>{r}</th>"
                            for r, _, _ in colunas)
        st.markdown(
            "<div style='overflow-x:auto; overflow-y:hidden;'><table style='width:100%; font-size:0.78rem; "
            "border-collapse:collapse;'><thead><tr class='cinza' style='font-size:0.66rem;'>"
            f"<th style='text-align:left; font-weight:400; padding:0 0.4rem 0.2rem 0;'>TICKER</th>{cabecalho}"
            "<th style='text-align:right; font-weight:400; padding:0 0 0.2rem 0.4rem;'>COLETA</th></tr>"
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

_FIM_TRIMESTRE_CIVIL = {1: (3, 31), 2: (6, 30), 3: (9, 30)}
_INICIO_TRIMESTRE_CIVIL = {1: 1, 2: 4, 3: 7}
_PREFIXO_MOEDA_EARNINGS = {"REAL": "R$", "USD": "US$"}
_ESCALA_EARNINGS = {"MIL": 1_000.0, "MILHAO": 1_000_000.0}


def _trimestres_candidatos_br(hoje: date, n: int = 6) -> list:
    """Últimos `n` trimestres CIVIS (1-3, nunca o 4º - cvm_dre.py não
    calcula Q4 isolado, ver docstring do módulo) com data-fim <= hoje,
    do mais recente pro mais antigo. Só diz que o trimestre já FECHOU
    no calendário - quem diz se o número já foi PUBLICADO pela CVM é
    reviewer.montar_nota_br (disponivel/motivo), nunca esta função."""
    candidatos = []
    ano = hoje.year
    limite = hoje.year - 6
    while len(candidatos) < n and ano > limite:
        for tri in (3, 2, 1):
            mes, dia = _FIM_TRIMESTRE_CIVIL[tri]
            if date(ano, mes, dia) <= hoje:
                candidatos.append((ano, tri))
        ano -= 1
    return candidatos[:n]


def _ultimo_trimestre_civil(hoje: date) -> tuple:
    """(início, fim) do trimestre civil mais recente já encerrado - só
    um PONTO DE PARTIDA editável pro seletor de empresas internacionais
    (o calendário fiscal real da empresa pode ser diferente do civil;
    reviewer.montar_nota_internacional já documenta que detectar o
    calendário fiscal automaticamente está fora do escopo desta
    versão - por isso a UI pede confirmação em vez de assumir)."""
    ano, tri = _trimestres_candidatos_br(hoje, n=1)[0]
    mes_fim, dia_fim = _FIM_TRIMESTRE_CIVIL[tri]
    fim = date(ano, mes_fim, dia_fim)
    inicio = date(ano, _INICIO_TRIMESTRE_CIVIL[tri], 1)
    return inicio, fim


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
        f"margin:0.3rem 0; font-size:0.78rem; background:rgba(255,255,255,0.03);'>{html.escape(texto)}</div>",
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
