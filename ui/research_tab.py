# -*- coding: utf-8 -*-
"""Interface da aba RESEARCH: chamada de render_research(prefs) pelo app.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

import html

import streamlit as st

import config
from data.news import obter_noticias
from data.research import CASAS, coletar_pendentes, preparar_leitura, ultimas_coletas_formatadas
from data.research.genial import obter_recomendacoes, obter_swing_trade
from data.research.historico import historico_ticker, processar_recomendacoes
from data.research.resumir import obter_resumo

_TIPO_LABEL = {
    "ACOES": "AÇÕES",
    "ESTRATEGIA": "ESTRATÉGIA",
    "MACRO": "MACRO",
    "NEWSLETTER": "NEWSLETTER",
    "ANALISE_TECNICA": "ANÁLISE TÉCNICA",
    "LIVE": "LIVE/VÍDEO",
}

_AVISO_COTA = "Cota gratuita de resumo por IA esgotada por enquanto — os links continuam disponíveis normalmente."
# motivo="indisponivel" (resiliencia 2026-10-01, ver data/research/resumir.py:
# _chamar_groq_com_fallback) = principal E fallback falharam por erro
# tecnico (nao cota) - mensagem curta de proposito, nunca expõe HTTP/
# excecao/detalhe interno (isso fica so' no log, ver _log_erro_ia).
_AVISO_IA_INDISPONIVEL = "Resumo por IA temporariamente indisponível — os links continuam disponíveis normalmente."

# casa -> funcao (link)->(texto, motivo_falha) pra gerar resumo; None usa
# o generico (baixa a pagina publica do relatorio) - ver CASAS em
# data/research/__init__.py
_EXTRATOR_POR_CASA = {c["nome"]: c["extrator_texto"] for c in CASAS}

# pills de filtro (Casa/Tipo/Ticker) quebram linha em vez de forcar
# rolagem horizontal em telas estreitas - correcao centralizada em
# style.css (2026-10-08, auditoria de responsividade); este modulo nao
# tem mais CSS proprio pra injetar.


# recomendacoes/swing trade da Genial sao SEMPRE ao vivo (obter_recomendacoes/
# obter_swing_trade so' tem cache em memoria de processo, TTL_COLETA - nunca
# passam pelo Supabase nem pelo gate tentar_coleta_automatica de
# coletar_pendentes) - sem essa checagem aqui, o painel de watchlist ia
# tentar buscar da Genial de novo a cada estouro do cache, mesmo com a
# coleta automatica desligada pra ela (ver data/research/__init__.py).
_GENIAL_COLETA_AUTOMATICA = next(
    (c.get("tentar_coleta_automatica", True) for c in CASAS if c["id"] == "genial"), True
)


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


_LIMITE_CONTEXTO_NEWS = 5


def _bloco_contexto_news(tickers: list):
    """"CONTEXTO RECENTE" (Rodrigo, fase RESEARCH<->NEWS 2026-10-01): so'
    aparece junto de um resumo JA' ABERTO (chamado logo apos
    _bloco_resumo, nunca na lista inteira do feed) - por isso nunca gera
    N+1: no maximo 1 ticker (raramente 2-3) por vez, so' quando o usuario
    de fato abriu aquele item.

    Reaproveita data.news.obter_noticias(ticker) - MESMA funcao/cache/
    identificador (ticker) que a aba NEWS ja usa pra tudo; nao cria
    nenhum sistema de identificacao de ativo novo, nao busca nada que
    essa funcao (cache de 20min, retencao de 5 dias, ja' filtrada por
    relevancia) nao buscasse de qualquer forma se o usuario abrisse NEWS.
    NUNCA chama resumo de IA (so' titulo/data/link, que obter_noticias ja
    retorna sem precisar resumir nada) e NUNCA afirma causalidade - so'
    lista os fatos lado a lado, nunca "subiu por causa de"."""
    if not tickers:
        return

    itens = []
    for ticker in tickers:
        noticias_ticker = obter_noticias(ticker)
        if noticias_ticker:
            itens.extend(noticias_ticker)
    if not itens:
        return  # fonte indisponivel ou sem noticia - secao nem aparece (pedido explicito)

    vistos = set()
    unicos = []
    for n in sorted(itens, key=lambda n: n["data"], reverse=True):
        if n["link"] in vistos:
            continue
        vistos.add(n["link"])
        unicos.append(n)
    unicos = unicos[:_LIMITE_CONTEXTO_NEWS]

    st.markdown(
        "<div style='font-size:0.65rem; color:var(--cinza); letter-spacing:0.05em; "
        "margin:0.5rem 0 0.3rem 0.6rem; padding-top:0.4rem; border-top:1px solid var(--borda);'>"
        "CONTEXTO RECENTE · NEWS</div>",
        unsafe_allow_html=True,
    )
    for n in unicos:
        st.markdown(
            f"<div style='font-size:0.74rem; padding:0.08rem 0 0.08rem 0.6rem;'>"
            f"<span class='cinza'>[{_fmt_data(n['data'])}]</span> "
            f"<a href='{n['link']}' target='_blank' style='color:var(--neutro); text-decoration:none;'>{n['titulo']}</a>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _resumo_formato_antigo(resumo: str) -> bool:
    """Resumos salvos no Supabase ANTES da reescrita do prompt (ficha
    tecnica TESE/NUMEROS-CHAVE/RECOMENDACAO/RISCOS, com 'nao informado')
    ficam presos em cache pra sempre se a gente so' checar "ja tem
    resumo?" - preciso detectar o formato velho e forcar regeracao."""
    cabeca = resumo.strip()[:30].upper()
    if cabeca.startswith("TESE"):
        return True
    alvo = resumo.upper()
    return "NAO INFORMADO" in alvo or "NÃO INFORMADO" in alvo or "NUMEROS-CHAVE" in alvo or "NÚMEROS-CHAVE" in alvo


@st.dialog("RESUMO", width="large")
def _abrir_resumo_live(rel: dict, extrator):
    """Card/modal do resumo de uma Live (Morning Call/Resumo da Manha/
    Fechamento etc) - reusa rel['resumo'] se ja carregado E no formato
    novo (nunca gera de novo so' por abrir o card); regenera se o item
    ainda nao tinha resumo salvo OU se o resumo salvo e' do formato antigo
    (ficha tecnica, de antes da reescrita do prompt - ver
    _resumo_formato_antigo)."""
    st.markdown(f"**{rel['titulo']}**")
    meta = " · ".join(filter(None, [rel["casa"], rel.get("autor") or "", _fmt_data(rel["data"])]))
    st.caption(meta)
    st.markdown("<div style='border-bottom:1px solid var(--borda); margin:0.4rem 0 0.6rem 0;'></div>", unsafe_allow_html=True)

    resumo = rel.get("resumo")
    if resumo and _resumo_formato_antigo(resumo):
        resumo = None
    motivo = None
    if not resumo:
        extrator_item = extrator or _EXTRATOR_POR_CASA.get(rel["casa"])
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator_item, casa=rel["casa"], tipo=rel["tipo"])
        resumo = resultado["resumo"]
        motivo = resultado["motivo_indisponivel"]

    if resumo:
        _bloco_resumo(resumo)
        _bloco_contexto_news(rel.get("tickers") or [])
    elif motivo == "cota":
        st.warning(_AVISO_COTA)
    elif motivo == "indisponivel":
        st.warning(_AVISO_IA_INDISPONIVEL)
    else:
        st.caption(f"Resumo indisponível ({motivo}).")


def _linha_relatorio(rel: dict, permitir_resumo_auto: bool, mostrar_contexto_news: bool = True) -> bool:
    """Retorna True se um resumo foi exibido (cacheado ou gerado agora) -
    usado por _painel_watchlist (mostrar_contexto_news=False aqui) pra
    saber se deve mostrar o bloco CONTEXTO RECENTE · NEWS 1x por TICKER,
    depois do loop de relatorios, em vez de 1x por RELATORIO (bug real
    corrigido 2026-10-08: um ticker com 3-4 relatorios com resumo ja
    cacheado repetia o MESMO bloco de noticias 3-4 vezes na tela -
    contrariava a propria promessa do docstring de _bloco_contexto_news,
    'so aparece 1x junto do resumo')."""
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

    extrator = _EXTRATOR_POR_CASA.get(rel["casa"])

    # Lives (Morning Call/Resumo da Manha/Fechamento/etc - tipo "LIVE") vao
    # pra um card/modal em vez de mostrar o resumo inteiro direto na lista
    # (pedido explicito do Rodrigo, 2026-09-28: a lista ficava "espalhada"
    # com resumo de 150-250 palavras embaixo de cada item). So' esse tipo -
    # research normal (ACOES/MACRO/etc) continua com o comportamento de antes.
    if rel["tipo"] == "LIVE":
        chave_botao = f"research_ver_resumo_{abs(hash(rel['link']))}"
        if st.button("VER RESUMO", key=chave_botao):
            _abrir_resumo_live(rel, extrator)
        return False

    if rel.get("resumo"):
        _bloco_resumo(rel["resumo"])
        if mostrar_contexto_news:
            _bloco_contexto_news(rel.get("tickers") or [])
        return True

    if permitir_resumo_auto:
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator, casa=rel["casa"], tipo=rel["tipo"])
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
            if mostrar_contexto_news:
                _bloco_contexto_news(rel.get("tickers") or [])
            return True
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        elif resultado["motivo_indisponivel"] == "indisponivel":
            st.warning(_AVISO_IA_INDISPONIVEL)
        # outros motivos (login/PDF ilegivel/conteudo curto): so titulo+link mesmo, sem aviso por item
        return False

    chave_botao = f"research_resumir_{abs(hash(rel['link']))}"
    if st.button("RESUMIR", key=chave_botao):
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator, casa=rel["casa"], tipo=rel["tipo"])
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
            if mostrar_contexto_news:
                _bloco_contexto_news(rel.get("tickers") or [])
            return True
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        elif resultado["motivo_indisponivel"] == "indisponivel":
            st.warning(_AVISO_IA_INDISPONIVEL)
        else:
            st.caption(f"Resumo indisponível ({resultado['motivo_indisponivel']}).")
    return False


def _fmt_capturado_em(valor: str) -> str:
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except Exception:
        return str(valor)[:10]


def _expander_historico_recomendacao(ticker: str, fmt: str):
    """Evolução de recomendação/preço-alvo da Genial pro ticker ao longo
    do tempo (data/research/historico.py:historico_ticker - existia so'
    na camada de dado, nunca exposto na UI; so' 'O QUE MUDOU' pontual
    aparecia, achado real 2026-10-08). So' 1 chamada por ticker, dentro
    de um expander FECHADO por padrão (nunca N+1 - mesmo tickers com
    history vazio custam so' 1 consulta cacheada)."""
    historico = historico_ticker("Genial Analisa", ticker, limite=5)
    if len(historico) < 2:
        return  # 0 ou 1 snapshot -> nao ha' "evolucao" nenhuma pra mostrar
    with st.expander(f"Histórico de recomendação · {ticker} ({len(historico)} registros)"):
        for h in historico:
            rec = h.get("recomendacao") or "—"
            preco_alvo = h.get("preco_alvo")
            preco_txt = f"R$ {config.formatar_numero(preco_alvo, 2, fmt)}" if preco_alvo is not None else "—"
            st.markdown(
                f"<div style='font-size:0.74rem; padding:0.1rem 0;'>"
                f"<span class='cinza'>[{_fmt_capturado_em(h.get('capturado_em', ''))}]</span> "
                f"<b>{html.escape(str(rec))}</b> · preço-alvo {preco_txt}</div>",
                unsafe_allow_html=True,
            )


def _formatar_valor_mudanca(campo: str, valor, fmt: str) -> str:
    if valor is None:
        return "—"
    if campo == "preco_alvo":
        return f"R$ {config.formatar_numero(valor, 2, fmt)}"
    return str(valor)


def _bloco_o_que_mudou(mudancas: list, fmt: str):
    """'O QUE MUDOU' (Rodrigo, fase RESEARCH 2026-10-01): so' aparece
    quando historico.processar_recomendacoes detectou uma mudanca REAL
    (preco-alvo e/ou recomendacao diferentes do ultimo snapshot salvo) -
    nunca um "resumo do dia" generico. Cada linha cita a CASA
    explicitamente (nunca vira "o mercado mudou") - ver
    data/research/historico.py pra garantia de que isso e' sempre
    comparacao com um valor real anterior, nunca inventado."""
    if not mudancas:
        return
    st.markdown(
        "<div style='font-size:0.7rem; color:var(--destaque); font-weight:600; "
        "letter-spacing:0.04em; margin:0.3rem 0 0.4rem 0;'>O QUE MUDOU</div>",
        unsafe_allow_html=True,
    )
    for m in mudancas:
        linhas_campo = []
        for campo, rotulo in (("recomendacao", "Recomendação"), ("preco_alvo", "Preço-alvo")):
            de = m["de"].get(campo)
            para = m["para"].get(campo)
            if de == para:
                continue
            linhas_campo.append(
                f"{rotulo}: {_formatar_valor_mudanca(campo, de, fmt)} → "
                f"<b>{_formatar_valor_mudanca(campo, para, fmt)}</b>"
            )
        if not linhas_campo:
            continue
        st.markdown(
            f"<div style='font-size:0.78rem; padding:0.3rem 0.5rem; margin-bottom:0.3rem; "
            f"border-left:2px solid var(--destaque);'>"
            f"<span style='color:var(--destaque); font-weight:600;'>{m['ticker']}</span>"
            f" · {m['casa']} · " + " · ".join(linhas_campo) + "</div>",
            unsafe_allow_html=True,
        )


def _painel_watchlist(prefs: dict, relatorios: list, recomendacoes: list, swing: list, mudancas_todas: list):
    st.markdown('<div class="painel-titulo">NA SUA WATCHLIST</div>', unsafe_allow_html=True)
    watchlist = prefs.get("watchlist") or []
    if not watchlist:
        st.info("Adicione tickers na barra lateral para ver research direcionado.")
        return

    fmt = prefs["formato_numerico"]
    mudancas_watchlist = [m for m in mudancas_todas if m["ticker"] in watchlist]
    _bloco_o_que_mudou(mudancas_watchlist, fmt)

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
            # so' classifica alta/baixa quando ha' potencial REAL - achado
            # real (2026-10-08): "(potencial or 0) >= 0" fazia o "—" (sem
            # dado ainda coletado) aparecer dentro de um <span> verde
            # (classe 'alta'), sugerindo uma tendencia positiva inexistente.
            sinal = ("alta" if potencial >= 0 else "baixa") if potencial is not None else ""
            preco_alvo = recomendacao_ticker.get("preco_alvo")
            potencial_txt = f"{config.formatar_numero(potencial, 1, fmt)}%" if potencial is not None else "—"
            preco_alvo_txt = f"R$ {config.formatar_numero(preco_alvo, 2, fmt)}" if preco_alvo is not None else "—"
            st.markdown(
                f"<div style='font-size:0.78rem;'>Genial: <b>{html.escape(str(recomendacao_ticker['recomendacao']))}</b>"
                f" · potencial <span class='{sinal}'>{potencial_txt}</span>"
                f" · preço-alvo {preco_alvo_txt}</div>",
                unsafe_allow_html=True,
            )
            _expander_historico_recomendacao(ticker, fmt)

        for s in swing_ticker:
            st.markdown(
                f"<div style='font-size:0.78rem;'>Swing trade: <b>{html.escape((s['recomendacao'] or '').upper())}</b>"
                f" ({html.escape(str(s['status']))}) · <a href='{s['link']}' target='_blank' style='color:var(--ciano);'>ver oportunidade</a></div>",
                unsafe_allow_html=True,
            )

        exibiu_resumo = False
        for rel in relatorios_ticker:
            if _linha_relatorio(rel, permitir_resumo_auto=True, mostrar_contexto_news=False):
                exibiu_resumo = True
        if exibiu_resumo:
            _bloco_contexto_news([ticker])

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
        filtro_casa = st.pills(
            "Casa", casas_no_feed, default=casas_no_feed, selection_mode="multi", key="research_filtro_casa",
        ) or []
    with col2:
        filtro_tipo = st.pills(
            "Tipo", tipos_no_feed, default=tipos_no_feed, selection_mode="multi",
            format_func=lambda t: _TIPO_LABEL.get(t, t), key="research_filtro_tipo",
        ) or []
    with col3:
        filtro_ticker = st.pills(
            "Ticker", ["Todos"] + tickers_no_feed, default="Todos", selection_mode="single",
            key="research_filtro_ticker",
        ) or "Todos"

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


def _status_mudanca(mudanca: dict) -> str:
    if mudanca["de"].get("recomendacao") != mudanca["para"].get("recomendacao"):
        return "MUDANÇA DE RECOMENDAÇÃO"
    return "MUDANÇA DE TARGET"


def _painel_radar(relatorios: list, mudancas_todas: list):
    """Research Radar (Rodrigo, fase RESEARCH 2026-10-01): visão
    compacta CASA|TICKER|TIPO|DATA|STATUS. So' usa 2 sinais REAIS já
    existentes no sistema - nunca inventa um "resumo do dia":
    - NOVO: relatório cuja DATA DE PUBLICAÇÃO (não coletado_em, que muda
      toda vez que a fonte é re-raspada mesmo pra um relatório antigo
      que continua listado - usaria "novo" errado) é hoje;
    - MUDANÇA DE TARGET / MUDANÇA DE RECOMENDAÇÃO: vem de
      historico.processar_recomendacoes (comparação real com snapshot
      salvo anteriormente, nunca inventada - ver data/research/historico.py)."""
    st.markdown('<div class="painel-titulo">RESEARCH RADAR</div>', unsafe_allow_html=True)

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")
    linhas = [
        {"casa": m["casa"], "ticker": m["ticker"], "tipo": "RECOMENDAÇÃO", "data": "hoje", "status": _status_mudanca(m)}
        for m in mudancas_todas
    ]
    for r in relatorios:
        if r.get("data") != hoje:
            continue
        for ticker in (r.get("tickers") or []):
            linhas.append({
                "casa": r["casa"], "ticker": ticker, "tipo": _TIPO_LABEL.get(r["tipo"], r["tipo"]),
                "data": _fmt_data(r["data"]), "status": "NOVO",
            })

    if not linhas:
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>Nenhuma mudança de recomendação/preço-alvo nem "
            "relatório novo hoje.</div>",
            unsafe_allow_html=True,
        )
        return

    linhas_html = "".join(
        f"<tr style='border-bottom:1px solid var(--borda);'>"
        f"<td style='padding:0.25rem 0.4rem 0.25rem 0;'>{l['casa']}</td>"
        f"<td style='padding:0.25rem 0.4rem; color:var(--destaque); font-weight:600;'>{l['ticker']}</td>"
        f"<td style='padding:0.25rem 0.4rem;'>{l['tipo']}</td>"
        f"<td style='padding:0.25rem 0.4rem;'>{l['data']}</td>"
        f"<td style='padding:0.25rem 0 0.25rem 0.4rem;'>{l['status']}</td></tr>"
        for l in linhas[:30]
    )
    st.markdown(
        "<table style='width:100%; font-size:0.78rem; border-collapse:collapse;'>"
        "<thead><tr class='cinza' style='text-align:left; font-size:0.65rem; letter-spacing:0.04em;'>"
        "<th style='padding:0 0.4rem 0.3rem 0;'>CASA</th><th style='padding:0 0.4rem 0.3rem;'>TICKER</th>"
        "<th style='padding:0 0.4rem 0.3rem;'>TIPO</th><th style='padding:0 0.4rem 0.3rem;'>DATA</th>"
        "<th style='padding:0 0.4rem 0.3rem;'>STATUS</th></tr></thead>"
        f"<tbody>{linhas_html}</tbody></table>",
        unsafe_allow_html=True,
    )


@st.fragment
def render_research(prefs: dict):
    """Ponto de entrada da aba RESEARCH, chamado pelo app.py.

    @st.fragment (perf, 2026-10-01): pills de casa/tipo/ticker em
    _painel_feed disparavam rerun da pagina inteira a cada clique
    (sintoma: tela pula pro topo). Mesmo padrao de CVM/NEWS/TOP MERCADO.
    coletar_pendentes/st.rerun() internos continuam funcionando igual
    dentro do fragment (rerun fica escopado ao fragment, que e' o
    comportamento certo aqui tambem).

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

    if _GENIAL_COLETA_AUTOMATICA:
        recomendacoes = obter_recomendacoes() or []
        swing = obter_swing_trade() or []
    else:
        recomendacoes, swing = [], []
    # processar_recomendacoes e' cacheado (ttl=TTL_COLETA) - so' bate no
    # Supabase de verdade 1x por janela de atualizacao, nao a cada rerun
    # da aba (ver data/research/historico.py). Calculado 1x aqui e
    # reaproveitado pelo watchlist (filtrado) e pelo radar (completo) -
    # evita processar a mesma lista duas vezes com escopos diferentes.
    mudancas_todas = processar_recomendacoes("Genial Analisa", recomendacoes) if recomendacoes else []

    with st.container(border=True):
        _painel_watchlist(prefs, relatorios, recomendacoes, swing, mudancas_todas)

    with st.container(border=True):
        _painel_radar(relatorios, mudancas_todas)

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
