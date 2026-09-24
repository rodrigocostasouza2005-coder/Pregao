# -*- coding: utf-8 -*-
"""Interface da aba RESEARCH: chamada de render_research(prefs) pelo app.py."""

import streamlit as st

import config
from data.research import CASAS, coletar_pendentes, preparar_leitura, ultimas_coletas_formatadas
from data.research.genial import obter_recomendacoes, obter_swing_trade
from data.research.resumir import obter_resumo

_TIPO_LABEL = {
    "ACOES": "AÇÕES",
    "ESTRATEGIA": "ESTRATÉGIA",
    "MACRO": "MACRO",
    "NEWSLETTER": "NEWSLETTER",
    "ANALISE_TECNICA": "ANÁLISE TÉCNICA",
}

_AVISO_COTA = "Cota gratuita de resumo por IA esgotada por enquanto — os links continuam disponíveis normalmente."

# casa -> funcao (link)->(texto, motivo_falha) pra gerar resumo; None usa
# o generico (baixa a pagina publica do relatorio) - ver CASAS em
# data/research/__init__.py
_EXTRATOR_POR_CASA = {c["nome"]: c["extrator_texto"] for c in CASAS}


def _casas_ativas(prefs):
    """Le prefs['research_casas_ativas'] (gravada pelo multiselect "CASAS
    DE RESEARCH" na aba CONFIG) - se vazia/ausente, usa o padrao de cada
    casa (CASAS[i]['ativa_por_padrao'])."""
    escolhidas = prefs.get("research_casas_ativas")
    if escolhidas:
        return escolhidas
    return [c["id"] for c in CASAS if c["ativa_por_padrao"]]


def _fmt_data(data_iso):
    if not data_iso:
        return "—"
    try:
        ano, mes, dia = data_iso.split("-")
        return f"{dia}/{mes}/{ano}"
    except Exception:
        return data_iso


def _tickers_disponiveis(relatorios):
    tickers = set()
    for r in relatorios:
        tickers.update(r.get("tickers", []))
    return sorted(tickers)


def _bloco_resumo(resumo: str):
    st.markdown(
        f"<div class='cinza' style='font-size:0.72rem; white-space:pre-line; padding:0.25rem 0 0.5rem 0.6rem; "
        f"border-left:2px solid var(--borda); margin-top:0.15rem;'>{resumo}</div>",
        unsafe_allow_html=True,
    )


def _linha_relatorio(rel: dict, permitir_resumo_auto: bool):
    tickers_html = " ".join(
        f"<span style='color:var(--destaque);'>{t}</span>" for t in rel.get("tickers", [])
    )
    meta = " · ".join(filter(None, [
        rel["casa"], _TIPO_LABEL.get(rel["tipo"], rel["tipo"]), _fmt_data(rel["data"]),
        rel.get("autor") or "", tickers_html or "",
    ]))

    st.markdown(
        f"""
        <div style="padding:0.35rem 0; border-bottom:1px solid var(--borda);">
            <a href="{rel['link']}" target="_blank"
               style="color:var(--neutro); font-weight:600; text-decoration:none; font-size:0.85rem;">
                {rel['titulo']}
            </a>
            <div class="cinza" style="font-size:0.68rem; margin-top:0.15rem;">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if rel.get("resumo"):
        _bloco_resumo(rel["resumo"])
        return

    extrator = _EXTRATOR_POR_CASA.get(rel["casa"])

    if permitir_resumo_auto:
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator)
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        # outros motivos (login/PDF ilegivel/conteudo curto): so titulo+link mesmo, sem aviso por item
        return

    chave_botao = f"research_resumir_{abs(hash(rel['link']))}"
    if st.button("RESUMIR", key=chave_botao):
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator)
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        else:
            st.caption(f"Resumo indisponível ({resultado['motivo_indisponivel']}).")


def _painel_watchlist(prefs: dict, relatorios: list):
    st.markdown('<div class="painel-titulo">NA SUA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na barra lateral para ver research direcionado.")
        return

    recomendacoes = obter_recomendacoes() or []
    swing = obter_swing_trade() or []
    fmt = prefs["formato_numerico"]

    mostrou_algo = False
    for ticker in watchlist:
        relatorios_ticker = [r for r in relatorios if ticker in r.get("tickers", [])]
        recomendacao_ticker = next((r for r in recomendacoes if r["ticker"] == ticker), None)
        swing_ticker = [
            s for s in swing
            if s["ticker"] == ticker and "aberto" in (s.get("status") or "").lower()
        ]

        if not relatorios_ticker and not recomendacao_ticker and not swing_ticker:
            continue
        mostrou_algo = True

        st.markdown(
            f"<div style='color:var(--destaque); font-weight:600; margin-top:0.6rem; font-size:0.85rem;'>{ticker}</div>",
            unsafe_allow_html=True,
        )

        if recomendacao_ticker:
            potencial = recomendacao_ticker.get("potencial_pct")
            sinal = "alta" if (potencial or 0) >= 0 else "baixa"
            preco_alvo = recomendacao_ticker.get("preco_alvo")
            potencial_txt = f"{config.formatar_numero(potencial, 1, fmt)}%" if potencial is not None else "—"
            preco_alvo_txt = f"R$ {config.formatar_numero(preco_alvo, 2, fmt)}" if preco_alvo is not None else "—"
            st.markdown(
                f"<div style='font-size:0.78rem;'>Genial: <b>{recomendacao_ticker['recomendacao']}</b>"
                f" · potencial <span class='{sinal}'>{potencial_txt}</span>"
                f" · preço-alvo {preco_alvo_txt}</div>",
                unsafe_allow_html=True,
            )

        for s in swing_ticker:
            st.markdown(
                f"<div style='font-size:0.78rem;'>Swing trade: <b>{(s['recomendacao'] or '').upper()}</b>"
                f" ({s['status']}) · <a href='{s['link']}' target='_blank' style='color:var(--ciano);'>ver oportunidade</a></div>",
                unsafe_allow_html=True,
            )

        for rel in relatorios_ticker:
            _linha_relatorio(rel, permitir_resumo_auto=True)

    if not mostrou_algo:
        st.info("Nenhum relatório, recomendação ou swing trade encontrado para os tickers da sua watchlist no momento.")


def _painel_feed(prefs: dict, relatorios: list, falhas: list):
    st.markdown('<div class="painel-titulo">FEED DE RESEARCH</div>', unsafe_allow_html=True)

    if falhas:
        st.warning("Indisponível no momento: " + "; ".join(falhas) + ".")

    if not relatorios:
        st.info("Nenhum relatório disponível no momento.")
        return

    casas_no_feed = sorted({r["casa"] for r in relatorios})
    tipos_no_feed = sorted({r["tipo"] for r in relatorios})
    tickers_no_feed = _tickers_disponiveis(relatorios)

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_casa = st.multiselect("Casa", casas_no_feed, default=casas_no_feed, key="research_filtro_casa")
    with col2:
        filtro_tipo = st.multiselect(
            "Tipo", tipos_no_feed, default=tipos_no_feed,
            format_func=lambda t: _TIPO_LABEL.get(t, t), key="research_filtro_tipo",
        )
    with col3:
        filtro_ticker = st.selectbox("Ticker", ["Todos"] + tickers_no_feed, key="research_filtro_ticker")

    filtrados = [
        r for r in relatorios
        if r["casa"] in filtro_casa and r["tipo"] in filtro_tipo
        and (filtro_ticker == "Todos" or filtro_ticker in r.get("tickers", []))
    ]
    filtrados.sort(key=lambda r: r.get("data", ""), reverse=True)

    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin:0.2rem 0;'>{len(filtrados)} relatório(s)</div>",
        unsafe_allow_html=True,
    )

    for rel in filtrados[:60]:
        _linha_relatorio(rel, permitir_resumo_auto=False)


def render_research(prefs: dict):
    """Ponto de entrada da aba RESEARCH, chamado pelo app.py.

    Mostra o cabecalho e o que ja esta salvo no Supabase imediatamente
    (leitura rapida, preparar_leitura) - so DEPOIS, se alguma casa estiver
    desatualizada (>30min), tenta coletar da fonte com timeout por
    requisicao e orcamento total de tempo (coletar_pendentes, ver
    data/research/base.py). Se a coleta atualizar algo, um st.rerun()
    reexibe a tela com os dados novos; se falhar, fica com o que ja tinha
    mostrado + um aviso de uma linha - nunca trava a tela."""
    st.markdown('<div class="painel-titulo">RESEARCH</div>', unsafe_allow_html=True)

    casas_ativas = _casas_ativas(prefs)
    relatorios, falhas, casas_para_coletar, _ = preparar_leitura(casas_ativas)

    texto_coletas = ultimas_coletas_formatadas(casas_ativas)
    if texto_coletas:
        st.markdown(
            f"<div class='cinza' style='font-size:0.65rem; margin-bottom:0.3rem;'>última coleta: {texto_coletas}</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        _painel_watchlist(prefs, relatorios)

    with st.container(border=True):
        _painel_feed(prefs, relatorios, falhas)

    if casas_para_coletar:
        with st.spinner("Coletando relatórios novos..."):
            falhas_coleta = coletar_pendentes(casas_para_coletar)
        if len(falhas_coleta) < len(casas_para_coletar):
            # pelo menos uma casa atualizou - vale reler do banco. Reler
            # so quando algo mudou evita loop de rerun se a coleta falhar
            # sempre (coletado_em so avanca em coleta bem-sucedida).
            st.rerun()
        elif falhas_coleta:
            st.warning("Nem tudo pôde ser atualizado agora: " + "; ".join(falhas_coleta) + ".")
