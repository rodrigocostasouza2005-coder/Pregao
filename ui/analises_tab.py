# -*- coding: utf-8 -*-
"""Area ANALISES do PREGAO 2.0 (ui/navegacao.py). Empresas = a antiga
EQUITY (continua em app.py, intocada no miolo); aqui ficam a barra de
vinculos da empresa (empresa -> setor/noticias/radar/fundamentos) e a
subaba Fundamentos. Valuation/Teses vem de ui/radar_tab.py.

Fundamentos so' mostra o que a fonte reporta HOJE (data/prices.py:
obter_indicadores, Yahoo Finance, cache de 12h) - receita, lucro e fluxo
de caixa em serie historica nao existem em nenhuma fonte integrada, e a
tela diz isso em vez de estimar."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.prices import obter_cotacao, obter_indicadores
from data.research.historico import historico_ticker
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
        quando = datetime.fromisoformat(bruto).astimezone(TZ_SP)
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
    return (alvo / atual - 1) * 100


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
