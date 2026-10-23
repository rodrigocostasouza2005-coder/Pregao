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
from datetime import date, datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data import market_researcher
from data.prices import obter_cotacao, obter_indicadores
from data.radar import TIPO_CALCULO, TIPO_ESTIMATIVA_TERCEIRO, TIPO_FATO, TIPO_HIPOTESE, TIPO_INSUFICIENTE
from data.research.historico import historico_ticker
from data.research.tese import scorecard
from ui import navegacao
from ui.market_makers_tab import _linha_catalisador, _linha_mudanca
from ui.radar_tab import _dialog_comparaveis, _injetar_css, _selo_evidencia
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
# SÍNTESE EXECUTIVA + RESEARCH DAS CASAS + CONCLUSÃO (2026-10-23)
#
# Agrega, pro ticker que o usuário REALMENTE abriu em ANÁLISES >
# Empresas (não só os da watchlist, como Fundamentos/RESEARCH faziam),
# a inteligência que já existia espalhada em telas paralelas (RADAR,
# MARKET MAKERS, RESEARCH > Casas de Análise). data.market_researcher.
# analise_ticker() já compõe linha_valuation + contexto_ticker +
# cobertura_cruzada_casas numa única chamada (1 consulta por fonte,
# testado em tests/test_market_researcher.py) - zero coletor novo, zero
# consulta duplicada; aqui só falta a apresentação. _montar_conclusao é
# função pura (sem Streamlit): nunca chama IA, nunca inventa frase -
# cada resposta cita o dado estruturado já calculado acima ou declara
# "dado insuficiente" explicitamente. Nunca gera recomendação de compra/
# venda - esse conceito não existe no retorno da função.
# ============================================================

def _card_cobertura_casa(item: dict, fmt: str) -> str:
    recomendacao = f" · {html.escape(item['recomendacao'])}" if item.get("recomendacao") else ""
    alvo = ""
    preco_alvo = item.get("preco_alvo")
    if preco_alvo:
        try:
            alvo = f" · alvo R$ {config.formatar_numero(float(preco_alvo), 2, fmt)}"
        except (TypeError, ValueError):
            alvo = ""
    data_txt = html.escape(str(item.get("data") or "—")[:10])
    link = item.get("link")
    titulo = html.escape(item.get("titulo") or "ver relatório")
    corpo = (f"<a href='{html.escape(link, quote=True)}' target='_blank' rel='noopener'>{titulo}</a>"
             if link else titulo)
    return (
        "<div class='radar-meta' style='margin-bottom:0.35rem; font-size:0.72rem;'>"
        f"<span class='radar-ticker' style='font-size:0.78rem;'>{html.escape(item['casa'])}</span> "
        f"({data_txt}){recomendacao}{alvo} — {corpo}</div>"
    )


def render_sintese_executiva(ticker: str, prefs: dict):
    """Painel compacto logo abaixo da barra de contexto: responde rápido
    "o que mudar agora" pra este ticker - interpretação (quando há
    evidência FATO na janela), até 2 mudanças recentes e o próximo
    catalisador. Reaproveita os mesmos cards HTML já usados em MARKET
    MAKERS (.radar-alerta, _linha_mudanca/_linha_catalisador) - zero
    estilo novo."""
    _injetar_css()
    try:
        analise = market_researcher.analise_ticker(ticker)
    except Exception as exc:
        st.caption(f"Síntese executiva indisponível agora ({exc!r}).")
        return

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">SÍNTESE EXECUTIVA</div>', unsafe_allow_html=True)
        interpretacao = analise.get("interpretacao_movimento")
        if interpretacao:
            st.markdown(
                f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
                f"<span class='radar-ticker'>{html.escape(ticker)}</span>"
                f"{_selo_evidencia(interpretacao.get('tipo_evidencia', TIPO_FATO))}</div>"
                f"<div class='radar-descricao'>{html.escape(interpretacao['texto'])}</div></div>",
                unsafe_allow_html=True,
            )
        mudancas = (analise.get("mudancas_tese") or [])[:2]
        for m in mudancas:
            st.markdown(_linha_mudanca(m), unsafe_allow_html=True)
        proximos = sorted(
            [c for c in (analise.get("catalisadores") or []) if c["data"] >= date.today()],
            key=lambda c: c["data"],
        )[:1]
        for c in proximos:
            st.markdown(_linha_catalisador(c), unsafe_allow_html=True)
        if not interpretacao and not mudancas and not proximos:
            if analise.get("fontes_indisponiveis"):
                st.markdown(
                    f"<div class='radar-vazio'>Síntese parcial: "
                    f"{html.escape(', '.join(analise['fontes_indisponiveis']))} indisponível(is) nesta checagem.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='radar-vazio'>Nenhuma mudança de tese ou catalisador verificado na janela de "
                    "7 dias para este ativo.</div>",
                    unsafe_allow_html=True,
                )


def _montar_conclusao(analise: dict, tese: dict | None) -> list:
    """Monta a conclusão de investimento (lista de {pergunta, resposta,
    tipo_evidencia}) só a partir do que já está em `analise`
    (data.market_researcher.analise_ticker) e, se existir, da Tese
    própria do usuário (data.research.tese.scorecard). "Dado
    insuficiente" é uma resposta honesta aqui, não um placeholder a
    esconder - e nunca há recomendação de compra/venda nesse retorno."""
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
                        "síntese (use \"Comparar com o setor ↗\" abaixo) e sem valor justo calculado pelo "
                        "PREGÃO (modelo próprio ainda não existe).",
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


def render_pesquisa_e_conclusao(ticker: str, prefs: dict, usuario: dict):
    """RESEARCH DAS CASAS (cobertura cruzada + histórico de preço-alvo já
    existente em _render_research_e_fatores) + RISCOS/CATALISADORES +
    CONCLUSÃO - chamado ao final do bloco de ANÁLISES > Empresas (depois
    de NOTÍCIAS/CVM), pra fechar a análise com uma síntese, não só a
    cotação."""
    _injetar_css()
    fmt = prefs["formato_numerico"]
    try:
        analise = market_researcher.analise_ticker(ticker)
    except Exception as exc:
        st.warning(f"Pesquisa e conclusão indisponíveis agora ({exc!r}).")
        return

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">RESEARCH DAS CASAS</div>', unsafe_allow_html=True)
        cobertura = analise.get("cobertura_research") or {}
        cobertura_lista = cobertura.get("cobertura")
        if cobertura_lista is None:
            st.markdown(
                "<div class='radar-vazio'>Banco indisponível: não foi possível checar a cobertura das casas "
                "agora.</div>", unsafe_allow_html=True,
            )
        elif cobertura_lista:
            for item in cobertura_lista:
                st.markdown(_card_cobertura_casa(item, fmt), unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='radar-vazio'>Nenhuma casa monitorada publicou algo recente sobre este ativo.</div>",
                unsafe_allow_html=True,
            )
        if cobertura.get("sem_cobertura"):
            st.caption("Sem cobertura recente: " + ", ".join(cobertura["sem_cobertura"]) + ".")
        if cobertura.get("divergencia"):
            por_casa = ", ".join(f"{k}: {v}" for k, v in cobertura["divergencia"]["por_casa"].items())
            st.markdown(
                f"<div class='baixa' style='font-size:0.78rem; margin-top:0.3rem;'>⚠ Recomendação diverge entre "
                f"casas — {html.escape(por_casa)}.</div>", unsafe_allow_html=True,
            )

    # fora do container acima DE PROPOSITO (nao aninhado): _render_research_e_fatores
    # ja' abre o proprio st.container(border=True) - aninhar criaria "card
    # dentro de card", exatamente o visual generico que o redesign do
    # RADAR > ACOMPANHAMENTO evitou (ver PR #149).
    _render_research_e_fatores(ticker, fmt)

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">RISCOS E CATALISADORES</div>', unsafe_allow_html=True)
        riscos = analise.get("riscos_indicadores")
        if riscos:
            st.markdown(
                f"<div class='radar-alerta'><div class='radar-descricao'>{html.escape('; '.join(riscos))}</div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='radar-vazio'>Nenhum alerta de qualidade nos indicadores monitorados.</div>",
                unsafe_allow_html=True,
            )
        proximos = sorted(
            [c for c in (analise.get("catalisadores") or []) if c["data"] >= date.today()], key=lambda c: c["data"]
        )
        for c in proximos[:5]:
            st.markdown(_linha_catalisador(c), unsafe_allow_html=True)
        fundamentos = analise.get("fundamentos")
        if fundamentos and fundamentos.get("preco") is not None:
            if st.button("Comparar com o setor ↗", key=f"empresa_comp_setor_{ticker}"):
                _dialog_comparaveis(ticker, prefs)

    tese = scorecard(usuario["sub"], ticker)
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CONCLUSÃO</div>', unsafe_allow_html=True)
        for bloco in _montar_conclusao(analise, tese):
            st.markdown(
                f"<div class='radar-alerta'><div class='radar-alerta-topo'>"
                f"<span class='radar-categoria'>{html.escape(bloco['pergunta'])}</span>"
                f"{_selo_evidencia(bloco['tipo_evidencia'])}</div>"
                f"<div class='radar-descricao'>{html.escape(bloco['resposta'])}</div></div>",
                unsafe_allow_html=True,
            )
        if tese:
            st.caption(
                f"Você já registrou uma Tese própria para {ticker} em {str(tese['registrado_em'])[:10]} "
                f"({tese['n_versoes']} versão(ões)) — ver RESEARCH › Minha Tese."
            )
        else:
            st.caption("Você ainda não registrou uma Tese própria para este ativo — ver RESEARCH › Minha Tese.")
