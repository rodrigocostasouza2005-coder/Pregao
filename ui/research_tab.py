# -*- coding: utf-8 -*-
"""Interface da aba RESEARCH: chamada de render_research(prefs) pelo app.py."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import html

import streamlit as st

import config
from data.news import obter_noticias
from data.research import CASAS, coletar_pendentes, preparar_leitura, ultimas_coletas_formatadas
from data.research import embeddings, store
from data.research.base import TTL_COLETA
from data.research.casas_status import obter_status_casas
from data.research.genial import obter_recomendacoes, obter_swing_trade
from data.research.historico import historico_ticker, mudancas_hoje, processar_recomendacoes, ultimo_snapshot
from data.research.resumir import obter_resumo
from data.market_researcher import cobertura_cruzada_casas
from data.x_radar import CATEGORIAS_PUBLICACAO, CONTAS_MONITORADAS
from data.x_radar.store import listar_sinais, saude_conector
from ui.saude_dados_tab import _COR_POR_ESTADO, _idade_formatada

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
# motivo="sem_credencial" (achado real, investigacao 2026-10-19):
# GROQ_API_KEY ausente/vazia no ambiente (ex: nao configurada nos
# secrets do GitHub Actions) - caso DIFERENTE de "indisponivel"
# (aquele e' falha tecnica temporaria do Groq em si, este e' config
# faltando; "temporariamente indisponível" seria impreciso aqui).
# Nunca expõe nenhum valor de credencial, so' informa que ela falta.
_AVISO_SEM_CREDENCIAL = "Resumo por IA não configurado neste ambiente — os links continuam disponíveis normalmente."

# casa -> funcao (link)->(texto, motivo_falha) pra gerar resumo; None usa
# o generico (baixa a pagina publica do relatorio) - ver CASAS em
# data/research/__init__.py
_EXTRATOR_POR_CASA = {c["nome"]: c["extrator_texto"] for c in CASAS}

# pills de filtro (Casa/Tipo/Ticker) quebram linha em vez de forcar
# rolagem horizontal em telas estreitas - correcao centralizada em
# style.css (2026-10-08, auditoria de responsividade). O CONTAINER das 3
# colunas (Casa/Tipo/Ticker) tem key="research_filtros_feed" so' pra
# essa regra de mobile em style.css poder mirar nele sem afetar outro
# st.columns(3) do app (bug real corrigido 2026-10-10: cada coluna
# ficava estreita demais pra caber uma pilula so' tipo "Genial
# (Lives)", que cortava sem reticencias).


# recomendacoes/swing trade da Genial sao SEMPRE ao vivo (obter_recomendacoes/
# obter_swing_trade so' tem cache em memoria de processo, TTL_COLETA - nunca
# passam pelo Supabase nem pelo gate tentar_coleta_automatica de
# coletar_pendentes) - sem essa checagem aqui, o painel de watchlist ia
# tentar buscar da Genial de novo a cada estouro do cache, mesmo com a
# coleta automatica desligada pra ela (ver data/research/__init__.py).
_GENIAL_COLETA_AUTOMATICA = next(
    (c.get("tentar_coleta_automatica", True) for c in CASAS if c["id"] == "genial"), True
)


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _ultimo_snapshot_cacheado(ticker: str) -> dict | None:
    """Wrapper cacheado de historico.ultimo_snapshot, so' pra uso da UI
    (_painel_watchlist) - 1 consulta por ticker da watchlist por janela
    de atualizacao, nao a cada rerun da aba. NAO cacheia a funcao
    original (data/research/historico.py:ultimo_snapshot) porque
    registrar_se_mudou depende dela pra comparar com o valor MAIS
    RECENTE de verdade antes de decidir se grava um snapshot novo -
    cachear ali poderia fazer o coletor perder uma mudanca real."""
    return ultimo_snapshot("Genial Analisa", ticker)


def _casas_ativas(prefs):
    """Le prefs['research_casas_ativas'] (gravada pelo multiselect "CASAS
    DE RESEARCH" na aba CONFIG) - se vazia/ausente, usa o padrao de cada
    casa (CASAS[i]['ativa_por_padrao'])."""
    escolhidas = prefs.get("research_casas_ativas")
    if escolhidas:
        return escolhidas
    return [c["id"] for c in CASAS if c["ativa_por_padrao"]]


def _fmt_data(data_iso):
    """Aceita tanto 'YYYY-MM-DD' quanto um datetime ISO completo com hora/
    timezone (ex: NEWS manda `datetime.isoformat()`, que no fuso de
    Brasilia termina em '-03:00') - bug real corrigido, 2026-10-10
    (confirmado por screenshot real do Playwright, bloco "CONTEXTO
    RECENTE · NEWS" da aba RESEARCH): `data_iso.split("-")` sem recortar
    so' a data antes contava o "-03:00" do offset como mais um separador,
    estourando o unpack de 3 valores - caia no except e mostrava o ISO
    cru (ou, pra um offset sem "-", tipo "+00:00", nem chegava a dar
    excecao: o unpack "funcionava" errado e remontava a string trocada
    (ex: "09T18:30:12.655291+00:00/10/2026"). Recortar os 10 primeiros
    caracteres ('YYYY-MM-DD') ANTES de dividir resolve os dois casos."""
    if not data_iso:
        return "—"
    try:
        ano, mes, dia = data_iso[:10].split("-")
        return f"{dia}/{mes}/{ano}"
    except Exception:
        return data_iso


def _tickers_disponiveis(relatorios):
    tickers = set()
    for r in relatorios:
        tickers.update(r.get("tickers", []))
    return sorted(tickers)


def _bloco_resumo(resumo: str):
    # rotulo explicita "gerado por IA" (achado da auditoria 360,
    # docs/auditoria-redesign-360.md - mesmo principio do achado ja
    # corrigido no modal de documento da CVM, PR #77): obter_resumo
    # (data/research/resumir.py) sempre sintetiza o texto via Groq -
    # sem essa indicacao visivel, o bloco podia passar a impressao de
    # ser um trecho oficial do proprio relatorio, nao um texto gerado
    # por modelo de linguagem.
    st.markdown(
        f"<div style='border-left:2px solid var(--borda); padding:0.25rem 0 0.5rem 0.6rem; margin-top:0.15rem;'>"
        f"<div class='cinza' style='font-size:0.62rem; text-transform:uppercase; margin-bottom:0.15rem;'>"
        f"Resumo (gerado por IA)</div>"
        f"<div class='cinza' style='font-size:0.72rem; white-space:pre-line;'>{resumo}</div>"
        f"</div>",
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
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator_item, casa=rel["casa"], tipo=rel["tipo"], tickers=rel.get("tickers"), data_publicacao=rel.get("data"))
        resumo = resultado["resumo"]
        motivo = resultado["motivo_indisponivel"]
        if resumo:
            # Sincroniza o dict EM MEMORIA (mesma referencia usada pelo
            # card na lista, ver _cartao_live/_montar_feed - nunca uma
            # copia) com o que acabou de ser persistido (store.salvar_resumo,
            # dentro de obter_resumo) - bug real corrigido (2026-10-09): sem
            # isso, o card por tras deste dialogo continuava mostrando
            # "Resumo ainda nao gerado" no MESMO clique (so' sumia no
            # proximo rerun da pagina, nao neste), mesmo o resumo ja' tendo
            # sido gerado e salvo com sucesso agora mesmo.
            rel["resumo"] = resumo

    if resumo:
        _bloco_resumo(resumo)
        _bloco_contexto_news(rel.get("tickers") or [])
    elif motivo == "cota":
        st.warning(_AVISO_COTA)
    elif motivo == "indisponivel":
        st.warning(_AVISO_IA_INDISPONIVEL)
    elif motivo == "sem_credencial":
        st.warning(_AVISO_SEM_CREDENCIAL)
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
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator, casa=rel["casa"], tipo=rel["tipo"], tickers=rel.get("tickers"), data_publicacao=rel.get("data"))
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
            if mostrar_contexto_news:
                _bloco_contexto_news(rel.get("tickers") or [])
            return True
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        elif resultado["motivo_indisponivel"] == "indisponivel":
            st.warning(_AVISO_IA_INDISPONIVEL)
        elif resultado["motivo_indisponivel"] == "sem_credencial":
            st.warning(_AVISO_SEM_CREDENCIAL)
        # outros motivos (login/PDF ilegivel/conteudo curto): so titulo+link mesmo, sem aviso por item
        return False

    chave_botao = f"research_resumir_{abs(hash(rel['link']))}"
    if st.button("RESUMIR", key=chave_botao):
        with st.spinner("Resumindo..."):
            resultado = obter_resumo(rel["link"], rel["titulo"], extrator_texto=extrator, casa=rel["casa"], tipo=rel["tipo"], tickers=rel.get("tickers"), data_publicacao=rel.get("data"))
        if resultado["resumo"]:
            _bloco_resumo(resultado["resumo"])
            if mostrar_contexto_news:
                _bloco_contexto_news(rel.get("tickers") or [])
            return True
        elif resultado["motivo_indisponivel"] == "cota":
            st.warning(_AVISO_COTA)
        elif resultado["motivo_indisponivel"] == "indisponivel":
            st.warning(_AVISO_IA_INDISPONIVEL)
        elif resultado["motivo_indisponivel"] == "sem_credencial":
            st.warning(_AVISO_SEM_CREDENCIAL)
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
        if recomendacao_ticker is None:
            # fallback pro ultimo snapshot PERSISTIDO (ver
            # data/research/historico.py:ultimo_snapshot) - cobre
            # producao, onde a Genial tem tentar_coleta_automatica=False
            # (recomendacoes ao vivo sempre []) e a UNICA fonte de
            # "recomendacao atual" e' o que coletor_local.py ja' gravou
            # em research_recomendacoes_historico. Mesmo formato de
            # campos (ticker/recomendacao/preco_alvo/potencial_pct) - a
            # linha abaixo so' preenche quando o live ja nao achou nada.
            snap = _ultimo_snapshot_cacheado(ticker)
            if snap is not None:
                recomendacao_ticker = {
                    "ticker": ticker, "recomendacao": snap.get("recomendacao"),
                    "preco_alvo": snap.get("preco_alvo"), "potencial_pct": snap.get("potencial_pct"),
                    # achado real (auditoria 2026-10-18): capturado_em existe
                    # no snapshot (ultimo_snapshot ORDENA por ele) mas nunca
                    # era copiado pra ca - a linha "Genial: COMPRA..." nunca
                    # mostrava NENHUMA data, e _expander_historico_recomendacao
                    # so' aparece com 2+ snapshots (o caso mais comum, 1
                    # snapshot so', ficava sem data visivel em lugar nenhum).
                    "capturado_em": snap.get("capturado_em"),
                }
        swing_ticker = [
            s for s in swing
            if s["ticker"] == ticker and "aberto" in (s.get("status") or "").lower()
        ]

        if not relatorios_ticker and not recomendacao_ticker and not swing_ticker:
            continue
        mostrou_algo = True

        link_ticker = html.escape(ticker, quote=True)
        st.markdown(
            f"<div style='margin-top:0.6rem;'><a href='?ticker={link_ticker}' "
            f"style='color:var(--destaque); font-weight:600; font-size:0.85rem; text-decoration:none;'>"
            f"{html.escape(ticker)}</a></div>",
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
            # capturado_em so' existe no fallback de snapshot persistido (ver
            # acima) - recomendacao AO VIVO da Genial nunca teve data nenhuma
            # exposta pela fonte, entao aqui nao mostra nada (nunca inventa
            # data que a propria fonte nao da').
            capturado_em = recomendacao_ticker.get("capturado_em")
            data_txt = f" · atualizado em {_fmt_capturado_em(capturado_em)}" if capturado_em else ""
            st.markdown(
                f"<div style='font-size:0.78rem;'>Genial: <b>{html.escape(str(recomendacao_ticker['recomendacao']))}</b>"
                f" · potencial <span class='{sinal}'>{potencial_txt}</span>"
                f" · preço-alvo {preco_alvo_txt}"
                f"<span class='cinza'>{data_txt}</span></div>",
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

    with st.container(key="research_filtros_feed"):
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

    # Sem style= por célula (achado da auditoria institucional 2026-10-29):
    # os valores batiam quase exatamente com o `table`/`th`/`td` globais de
    # style.css, só com um padding/tamanho levemente diferente sem motivo -
    # essa era a única tabela do RESEARCH com alinhamento sutilmente distinto
    # das outras do app. Herda o padrão global; só o ticker continua com
    # cor/peso próprios (destaque real, não coberto pela regra genérica).
    linhas_html = "".join(
        f"<tr><td>{l['casa']}</td>"
        f"<td><a href='?ticker={html.escape(l['ticker'], quote=True)}' "
        f"style='color:var(--destaque); font-weight:600; text-decoration:none;'>{html.escape(l['ticker'])}</a></td>"
        f"<td>{l['tipo']}</td><td>{l['data']}</td><td>{l['status']}</td></tr>"
        for l in linhas[:30]
    )
    st.markdown(
        "<table><thead><tr>"
        "<th>CASA</th><th>TICKER</th><th>TIPO</th><th>DATA</th><th>STATUS</th>"
        f"</tr></thead><tbody>{linhas_html}</tbody></table>",
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
    #
    # Combina com mudancas_hoje (le o historico JA' PERSISTIDO, sem
    # precisar de recomendacoes ao vivo) - bug real corrigido
    # (2026-10-09): em producao _GENIAL_COLETA_AUTOMATICA e' False,
    # entao processar_recomendacoes(recomendacoes) sozinho SEMPRE
    # retornava [] la' (recomendacoes ao vivo tambem sempre []), mesmo
    # com coletor_local.py alimentando o historico com dado real - o
    # Research Radar/'O QUE MUDOU' nunca tinham como mostrar nada pra
    # Genial em producao. Dedup por (ticker,casa): se os dois
    # detectarem a mesma mudanca (dev local, onde a coleta ao vivo
    # tambem funciona), mantem so' 1.
    mudancas_vivas = processar_recomendacoes("Genial Analisa", recomendacoes) if recomendacoes else []
    mudancas_persistidas = mudancas_hoje("Genial Analisa")
    vistos = {(m["ticker"], m["casa"]) for m in mudancas_vivas}
    mudancas_todas = mudancas_vivas + [m for m in mudancas_persistidas if (m["ticker"], m["casa"]) not in vistos]

    # grade (achado da auditoria de redesign 2026-10-30): watchlist+radar
    # empilhados em largura total desperdicavam espaco - radar e' uma
    # tabela compacta (CASA/TICKER/TIPO/DATA/STATUS, ver _painel_radar),
    # nao precisa da largura inteira. Mesmo padrao de grade ja' validado
    # em VISAO GERAL (grafico+"para investigar"), sem mudar nenhum dado/
    # logica dos dois paineis.
    with st.container(key="research_grid_watchlist_radar"):
        col_watchlist, col_radar = st.columns([0.62, 0.38], gap="small")
        with col_watchlist:
            with st.container(border=True):
                _painel_watchlist(prefs, relatorios, recomendacoes, swing, mudancas_todas)
        with col_radar:
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


# ============================================================
# CASAS DE ANÁLISE (Fase 3, 2026-10-23 -> reformulação 2026-10-24: painel
# de teses de investimento). Duas áreas:
# A. TESES E PUBLICAÇÕES (principal) - o que cada casa publicou, de
#    verdade, a partir do MESMO dado já persistido que o FEED usa
#    (data/research/store.py:listar_itens, via preparar_leitura) - zero
#    coletor novo, zero tabela nova, zero normalização além do que
#    store.py:_linha_para_item já faz. recomendacao/preco_alvo só
#    existem DEPOIS que o resumo por IA já foi gerado pra aquele item
#    (extraídos do próprio resumo, ver data/research/resumir.py:
#    _extrair_dados_estruturados) - por isso NUNCA são mostrados antes
#    disso: item sem resumo ainda não tem como saber se a casa publicou
#    recomendação/preço-alvo ou não (estado "ainda não verificado", bem
#    diferente de "a casa não publicou").
# B. COBERTURA E SAÚDE DAS CASAS (secundária, num expander fechado por
#    padrão pra não dominar a tela) - leitura pura de
#    data/research/casas_status.py (CASAS + saude_dados, categoria
#    Research) + a cobertura cruzada por ticker que já existia
#    (data/market_researcher.py). Nunca coleta nada nem dispara rede nova
#    aqui dentro.
# ============================================================

_CSS_CASAS = """
.casas-nota { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.8rem 0; line-height: 1.5; }
.casas-tabela { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.casas-tabela th {
    text-align: left; color: var(--cinza); font-size: 0.64rem; letter-spacing: 0.03em;
    padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda);
}
.casas-tabela td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--borda); vertical-align: top; }
.casas-nome { color: var(--destaque); font-weight: 600; }
.casas-acesso { color: var(--cinza); font-size: 0.68rem; }
.casas-badge {
    display: inline-block; border: 1px solid var(--borda); border-radius: 3px; padding: 0 6px;
    font-size: 0.6rem; letter-spacing: 0.04em; font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 0.3rem;
}
.casas-badge-ok { border-color: var(--destaque); color: var(--destaque); }
.casas-badge-meta { color: var(--cinza); }
.casas-rec { font-size: 0.76rem; margin: 0.2rem 0 0.3rem 0; }
"""


# --- núcleo puro (sem Streamlit, testável direto) --------------------------

def _dedupe_teses(itens: list) -> list:
    """Dedup por link - mesma chave única que data/research/store.py usa
    no upsert (on_conflict='link'); defensivo contra o mesmo relatório
    aparecendo 2x se duas casas monitoradas apontarem pro mesmo link."""
    vistos = set()
    unicos = []
    for item in itens:
        link = item.get("link")
        if link in vistos:
            continue
        vistos.add(link)
        unicos.append(item)
    return unicos


def _item_tem_data(item: dict) -> bool:
    return bool((item.get("data") or "").strip())


def _texto_busca(item: dict) -> str:
    """Haystack pra busca textual: título, casa, ticker(s), autor e o
    resumo JÁ GERADO (quando existir) - nunca busca no texto original (não
    é persistido, ver data/research/store.py)."""
    partes = [
        item.get("titulo") or "", item.get("casa") or "",
        " ".join(item.get("tickers") or []), item.get("autor") or "", item.get("resumo") or "",
    ]
    return " ".join(partes).casefold()


_SEM_RECOMENDACAO = "SEM RECOMENDAÇÃO IDENTIFICADA"


def _chave_recomendacao(item: dict) -> str:
    """Valor usado pro filtro de Recomendação - item sem recomendacao
    IDENTIFICADA (ainda não resumido OU resumido sem recomendação
    explícita) cai no mesmo rótulo _SEM_RECOMENDACAO, nunca em None
    (None não pode ser comparado contra um set de opções de pill)."""
    return item.get("recomendacao") or _SEM_RECOMENDACAO


def _filtrar_teses(itens: list, *, casas=None, tipos=None, ticker: str = "Todos",
                    recomendacoes=None, busca: str = "") -> list:
    """Filtro puro sobre dado real já carregado - casas/tipos/recomendacoes
    None = sem filtro (nenhum item excluído por esse critério); conjunto
    vazio = exclui tudo (pills sem nenhuma opção marcada). ACHADO REAL
    (validação com Playwright, 24/10/2026): com `recomendacoes` sendo o
    conjunto de valores REAIS vistos (ex: {"COMPRA","MANTER"}), todo item
    SEM recomendação identificada (maioria do painel - macro, não
    resumido ainda etc.) desaparecia da tela por padrão, mesmo sem o
    usuário tocar no filtro - comparar contra _chave_recomendacao(item)
    (que mapeia None pro rótulo _SEM_RECOMENDACAO, também oferecido como
    opção de pill) corrige isso: filtro "todo mundo marcado" = mostra
    tudo de verdade."""
    busca_norm = (busca or "").strip().casefold()
    resultado = []
    for item in itens:
        if casas is not None and item.get("casa") not in casas:
            continue
        if tipos is not None and item.get("tipo") not in tipos:
            continue
        if ticker != "Todos" and ticker not in (item.get("tickers") or []):
            continue
        if recomendacoes is not None and _chave_recomendacao(item) not in recomendacoes:
            continue
        if busca_norm and busca_norm not in _texto_busca(item):
            continue
        resultado.append(item)
    return resultado


def _aplicar_periodo(itens: list, dias: int | None, hoje=None) -> tuple:
    """(itens_dentro_do_periodo, quantos_sem_data_confirmada_ficaram_fora).
    dias=None ('Tudo') nunca exclui nada - inclusive item sem data, que só
    fica de fora quando um período específico é escolhido (nunca inventa
    uma data pra decidir se ele "está" na janela)."""
    if dias is None:
        return list(itens), 0
    hoje = hoje or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    dentro = []
    sem_data = 0
    for item in itens:
        if not _item_tem_data(item):
            sem_data += 1
            continue
        try:
            data_item = datetime.strptime(item["data"][:10], "%Y-%m-%d").date()
        except ValueError:
            sem_data += 1
            continue
        if (hoje - data_item).days <= dias:
            dentro.append(item)
    return dentro, sem_data


def _ordenar_teses(itens: list) -> list:
    """Mais recente primeiro pela DATA REAL de publicação (campo 'data',
    nunca 'coletado_em' - mesmo cuidado de _painel_radar). Item sem data
    confirmada vai pro final da lista, nunca misturado como se fosse
    recente nem descartado."""
    com_data = [i for i in itens if _item_tem_data(i)]
    sem_data = [i for i in itens if not _item_tem_data(i)]
    com_data.sort(key=lambda i: i["data"], reverse=True)
    return com_data + sem_data


def _quantidade_por_casa(itens: list) -> dict:
    """Publicações disponíveis (persistidas) por casa, a partir dos itens
    JÁ carregados em memória (preparar_leitura) - zero consulta nova ao
    banco só pra contar."""
    contagem = {}
    for item in itens:
        contagem[item["casa"]] = contagem.get(item["casa"], 0) + 1
    return contagem


def _badge_disponibilidade(rel: dict) -> str:
    if rel.get("resumo"):
        return "<span class='casas-badge casas-badge-ok'>RESUMO (IA) DISPONÍVEL</span>"
    return "<span class='casas-badge casas-badge-meta'>SOMENTE METADADOS</span>"


def _linha_recomendacao(rel: dict, fmt: str) -> str | None:
    """None antes do resumo existir (ver comentário no topo da seção CASAS
    DE ANÁLISE) - recomendacao/preco_alvo só têm significado DEPOIS que o
    resumo já tentou extraí-los; mostrar "não informado" nesse estágio
    confundiria "ainda não verificado" com "a casa não publicou"."""
    if not rel.get("resumo"):
        return None
    recomendacao = rel.get("recomendacao")
    preco_alvo = rel.get("preco_alvo")
    if not recomendacao and preco_alvo is None:
        return "<div class='casas-rec cinza'>Recomendação/preço-alvo: não identificados no texto.</div>"
    rec_txt = html.escape(str(recomendacao)) if recomendacao else "não identificada"
    preco_txt = f"R$ {config.formatar_numero(preco_alvo, 2, fmt)}" if preco_alvo is not None else "não informado"
    return (
        f"<div class='casas-rec'>Recomendação: <b>{rec_txt}</b> · "
        f"Preço-alvo: <b>{preco_txt}</b></div>"
    )


def _card_tese(rel: dict, fmt: str, permitir_resumo_auto: bool):
    """Card de 1 publicação: disponibilidade (resumo IA vs. só metadados),
    recomendação/preço-alvo quando aplicável, e o resto (título/link,
    meta, resumo sob demanda) via _linha_relatorio - mesma lógica/cache
    do FEED, sem duplicar a chamada de IA nem o fluxo de resumo."""
    with st.container(border=True):
        st.markdown(_badge_disponibilidade(rel), unsafe_allow_html=True)
        linha_rec = _linha_recomendacao(rel, fmt)
        if linha_rec:
            st.markdown(linha_rec, unsafe_allow_html=True)
        _linha_relatorio(rel, permitir_resumo_auto=permitir_resumo_auto, mostrar_contexto_news=True)


def _secao_teses(prefs: dict, relatorios: list, falhas: list):
    """Área principal (A): teses/publicações reais, com filtro e busca
    sobre o que já foi carregado (preparar_leitura) - nenhuma consulta
    nova aqui dentro."""
    st.markdown('<div class="painel-titulo">TESES E PUBLICAÇÕES</div>', unsafe_allow_html=True)

    if falhas:
        st.warning("Falha de coleta: " + "; ".join(falhas) + ".")

    itens = _dedupe_teses(relatorios)
    if not itens:
        if not falhas:
            st.info("Nenhuma publicação disponível no momento.")
        return

    casas_disp = sorted({i["casa"] for i in itens})
    tipos_disp = sorted({i["tipo"] for i in itens})
    tickers_disp = _tickers_disponiveis(itens)
    valores_recomendacao = sorted({i["recomendacao"] for i in itens if i.get("recomendacao")})
    recomendacoes_disp = valores_recomendacao + [_SEM_RECOMENDACAO] if valores_recomendacao else []

    with st.container(key="casas_filtros_teses"):
        filtro_casa = st.pills(
            "Casa", casas_disp, default=casas_disp, selection_mode="multi", key="casas_filtro_casa",
        ) or []
        filtro_tipo = st.pills(
            "Tipo", tipos_disp, default=tipos_disp, selection_mode="multi",
            format_func=lambda t: _TIPO_LABEL.get(t, t), key="casas_filtro_tipo",
        ) or []
        col1, col2 = st.columns(2)
        with col1:
            filtro_ticker = st.pills(
                "Ticker ou empresa", ["Todos"] + tickers_disp, default="Todos",
                selection_mode="single", key="casas_filtro_ticker",
            ) or "Todos"
        with col2:
            if recomendacoes_disp:
                filtro_recomendacao = st.pills(
                    "Recomendação", recomendacoes_disp, default=recomendacoes_disp,
                    selection_mode="multi", key="casas_filtro_recomendacao",
                ) or []
            else:
                filtro_recomendacao = None
        col3, col4 = st.columns([1, 2])
        with col3:
            periodo_label = st.pills(
                "Período", ["7 dias", "30 dias", "90 dias", "Tudo"], default="Tudo",
                selection_mode="single", key="casas_filtro_periodo",
            ) or "Tudo"
        with col4:
            busca = st.text_input(
                "Buscar por título, ticker, empresa ou conteúdo",
                key="casas_busca_texto", placeholder="ex: PETR4, dividendos, Genial...",
            )

    dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "Tudo": None}[periodo_label]
    recomendacoes_filtro = set(filtro_recomendacao) if recomendacoes_disp else None

    filtrados = _filtrar_teses(
        itens, casas=set(filtro_casa), tipos=set(filtro_tipo), ticker=filtro_ticker,
        recomendacoes=recomendacoes_filtro, busca=busca,
    )
    filtrados, sem_data_ocultas = _aplicar_periodo(filtrados, dias)
    filtrados = _ordenar_teses(filtrados)

    aviso_sem_data = (
        f" · +{sem_data_ocultas} sem data confirmada (fora deste filtro de período)" if sem_data_ocultas else ""
    )
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0;'>{len(filtrados)} publicação(ões)"
        f"{aviso_sem_data}</div>",
        unsafe_allow_html=True,
    )

    if not filtrados:
        st.info("Nenhuma publicação disponível para os filtros selecionados.")
        return

    fmt = prefs["formato_numerico"]
    for rel in filtrados[:60]:
        _card_tese(rel, fmt, permitir_resumo_auto=False)


def _secao_cobertura_saude(prefs: dict, contagem_por_casa: dict):
    """Área secundária (B): saúde/cobertura técnica das casas - nunca
    misturada com a área de teses (uma casa com falha na ÚLTIMA coleta
    pode continuar com publicações antigas disponíveis; a contagem de
    publicações vem do que já está carregado em memória, não de uma
    consulta nova). Dentro de um expander fechado por padrão pra não
    disputar espaço com a área principal."""
    with st.expander("COBERTURA E SAÚDE DAS CASAS", expanded=False):
        st.markdown(
            "<div class='casas-nota'>Estado real de cada casa coletada hoje pelo PREGÃO — nunca mostra "
            "uma fonte como funcionando sem evidência de coleta bem-sucedida. Candidatas investigadas e "
            "bloqueadas (Itaú BBA, Safra, Rico, Ágora, BB Investalk e outras) estão documentadas em "
            "<code>docs/research-fontes-20261022.md</code>, fora desta lista.</div>",
            unsafe_allow_html=True,
        )

        linhas_html = ""
        for item in obter_status_casas():
            cor = _COR_POR_ESTADO.get(item["codigo_estado"], "neutro")
            acesso = (
                "coleta automática (Cloud + local)" if item["coleta_automatica_cloud"]
                else "só via coletor_local.py (bloqueada no Streamlit Cloud)"
            )
            ultimo_sucesso = _idade_formatada(item["ultimo_sucesso_em"])
            registros = item["registros_novos_ultima_coleta"]
            registros_fmt = "—" if registros is None else str(registros)
            publicacoes_fmt = str(contagem_por_casa.get(item["nome"], 0))
            linhas_html += (
                "<tr>"
                f"<td class='casas-nome'>{html.escape(item['nome'])}</td>"
                f"<td class='cinza'>{html.escape(item['fonte'])}</td>"
                f"<td class='casas-acesso'>{acesso}</td>"
                f"<td class='{cor}'>{html.escape(item['rotulo_estado'])}</td>"
                f"<td class='cinza'>{ultimo_sucesso}</td>"
                f"<td class='cinza'>{registros_fmt}</td>"
                f"<td class='cinza'>{publicacoes_fmt}</td>"
                "</tr>"
            )
        st.markdown(
            "<div style='overflow-x:auto;'><table class='casas-tabela'>"
            "<thead><tr><th>CASA</th><th>FONTE</th><th>ACESSO</th><th>ESTADO</th>"
            "<th>ÚLTIMO SUCESSO</th><th>ITENS NA ÚLTIMA COLETA</th><th>PUBLICAÇÕES DISPONÍVEIS</th></tr></thead>"
            f"<tbody>{linhas_html}</tbody></table></div>",
            unsafe_allow_html=True,
        )

        # MARKET RESEARCHER (data/market_researcher.py): cobertura cruzada
        # por ticker da watchlist - quem cobriu, quem não cobriu (fato), e
        # recomendação estruturada divergente entre casas quando o dado
        # permite (nunca inferida de título). Zero coletor/tabela nova.
        watchlist = prefs.get("watchlist") or []
        if watchlist:
            st.markdown('<div class="painel-titulo" style="margin-top:1rem; font-size:.78rem;">COBERTURA CRUZADA — WATCHLIST</div>', unsafe_allow_html=True)
            for ticker in watchlist:
                resultado = cobertura_cruzada_casas(ticker)
                if resultado["cobertura"] is None:
                    st.markdown(f"<div class='casas-acesso'>{html.escape(ticker)}: banco indisponível, sem checagem.</div>", unsafe_allow_html=True)
                    continue
                if not resultado["cobertura"] and not resultado["divergencia"]:
                    continue  # nenhuma casa cobriu - sem achado, não polui a tela
                with st.container(border=True):
                    st.markdown(f"<span class='casas-nome'>{html.escape(ticker)}</span>", unsafe_allow_html=True)
                    for c in resultado["cobertura"]:
                        rec = f" · {html.escape(c['recomendacao'])}" if c.get("recomendacao") else ""
                        st.markdown(
                            f"<div class='cinza' style='font-size:0.7rem;'>{html.escape(c['casa'])} "
                            f"({html.escape(str(c['data'])[:10])}){rec} — "
                            f"<a href='{html.escape(c['link'], quote=True)}' target='_blank' rel='noopener'>{html.escape(c['titulo'] or 'ver relatório')}</a></div>",
                            unsafe_allow_html=True,
                        )
                    if resultado["sem_cobertura"]:
                        st.markdown(
                            f"<div class='casas-acesso'>Sem cobertura recente: {html.escape(', '.join(resultado['sem_cobertura']))}.</div>",
                            unsafe_allow_html=True,
                        )
                    if resultado["divergencia"]:
                        por_casa = ", ".join(f"{k}: {v}" for k, v in resultado["divergencia"]["por_casa"].items())
                        st.markdown(f"<div class='baixa' style='font-size:0.72rem;'>⚠ {html.escape(por_casa)}</div>", unsafe_allow_html=True)


@st.fragment
def render_casas_analise(prefs: dict):
    """Ponto de entrada da subaba RESEARCH › Casas de Análise (chamado por
    app.py): painel de teses de investimento das casas de research.

    Mesmo padrão de leitura/coleta de render_research (preparar_leitura
    primeiro, rápido, só o que já está no Supabase; coletar_pendentes
    SÓ para casas desatualizadas há >30min, com orçamento de tempo) -
    reaproveitado aqui, não duplicado: mesmas funções, mesmo gate,
    mesmo cooldown de falha (data/research/__init__.py)."""
    st.markdown(f"<style>{_CSS_CASAS}</style>", unsafe_allow_html=True)
    st.markdown('<div class="painel-titulo">CASAS DE ANÁLISE</div>', unsafe_allow_html=True)

    casas_ativas = _casas_ativas(prefs)
    relatorios, falhas, casas_para_coletar, _ = preparar_leitura(casas_ativas)

    texto_coletas = ultimas_coletas_formatadas(casas_ativas)
    if texto_coletas:
        st.markdown(
            f"<div class='cinza' style='font-size:0.65rem; margin-bottom:0.3rem;'>última coleta: {texto_coletas}</div>",
            unsafe_allow_html=True,
        )

    _secao_teses(prefs, relatorios, falhas)

    itens_dedup = _dedupe_teses(relatorios)
    # cobertura cruzada por watchlist (data/market_researcher.py) já vive
    # DENTRO de _secao_cobertura_saude (ver acima) - não duplicar aqui
    # (achado real reconciliando com origin/main: a versão antiga, sem
    # área de teses, tinha essa mesma chamada inline no corpo de
    # render_casas_analise; a versão nova já absorveu isso na área B).
    _secao_cobertura_saude(prefs, _quantidade_por_casa(itens_dedup))

    if casas_para_coletar:
        with st.spinner("Coletando publicações novas..."):
            falhas_coleta = coletar_pendentes(casas_para_coletar)
        if len(falhas_coleta) < len(casas_para_coletar):
            st.rerun()
        elif falhas_coleta:
            st.warning("Nem tudo pôde ser atualizado agora: " + "; ".join(falhas_coleta) + ".")


# ============================================================
# MEMÓRIA DE RESEARCH (Fase C - RAG, 2026-10-30, pedido do Rodrigo):
# busca em linguagem natural + filtros estruturais sobre a biblioteca
# PERMANENTE de premissas/projeções (research_premissas, ver
# sql/research_premissas.sql) - toda a lógica de busca/combinação
# (estrutural + semântica + lexical) vive em data/research/embeddings.py
# e já retorna 100% ESTRUTURADO/determinístico; esta seção SÓ renderiza
# os campos recebidos (link/casa/título/data/tickers/premissas/projeções/
# recomendação/preço-alvo/origem_match), nunca sintetiza uma frase nova
# "inventada" a partir do resultado.
# ============================================================

_TIPO_DOCUMENTO_LABEL = {
    "INICIACAO_COBERTURA": "Iniciação de Cobertura",
    "ATUALIZACAO_COBERTURA": "Atualização de Cobertura",
    "ATUALIZACAO_RESULTADOS": "Atualização de Resultados",
    "RELATORIO_SETORIAL": "Relatório Setorial",
    "ESTRATEGIA_INVESTIMENTOS": "Estratégia de Investimentos",
    "CARTEIRA_RECOMENDADA": "Carteira Recomendada",
    "REVISAO_PRECO_ALVO": "Revisão de Preço-Alvo",
    "MUDANCA_RECOMENDACAO": "Mudança de Recomendação",
    "VALUATION": "Valuation",
    "COMENTARIO_RESULTADO_TRIMESTRAL": "Comentário de Resultado Trimestral",
}

_ORIGEM_MATCH_LABEL = {
    "semantico": "busca semântica", "lexical": "palavra-chave",
    "ambos": "semântica + palavra-chave", "estrutural": "filtro estrutural",
}

# badges de confiança reaproveitam a classe base '.casas-badge' (já
# definida em _CSS_CASAS, injetado por render_casas_analise) - esta
# subaba roda isolada (so' a subaba ativa é renderizada, ver
# ui/navegacao.py), então injeta o MESMO bloco de novo aqui (harmless,
# so' reafirma as mesmas regras) mais as 4 variações de cor por nível de
# confiança.
_CSS_MEMORIA = _CSS_CASAS + """
.memoria-badge-alta { border-color: var(--alta); color: var(--alta); }
.memoria-badge-media { border-color: var(--destaque); color: var(--destaque); }
.memoria-badge-baixa { border-color: var(--cinza); color: var(--cinza); }
.memoria-badge-sem { border-color: var(--baixa); color: var(--baixa); }
"""

_BADGE_CONFIANCA = {
    "ALTA": ("memoria-badge-alta", "CONFIANÇA ALTA"),
    "MEDIA": ("memoria-badge-media", "CONFIANÇA MÉDIA"),
    "BAIXA": ("memoria-badge-baixa", "CONFIANÇA BAIXA"),
    "SEM_EVIDENCIA": ("memoria-badge-sem", "SEM EVIDÊNCIA"),
}

_AVISO_MEMORIA_SEM_CREDENCIAL = (
    "Busca semântica (linguagem natural) não configurada neste ambiente — "
    "GEMINI_API_KEY ausente. A busca por ticker/casa/tipo/palavra-chave "
    "continua funcionando normalmente."
)


# --- núcleo puro (sem Streamlit, testável direto) --------------------------

def _opcoes_filtro_memoria(premissas: list) -> dict:
    """{'casas':[...], 'tipos':[...], 'tickers':[...]} a partir do que já
    está carregado em memória - pura, sem rede/Streamlit, testável
    direto. Listas ordenadas e sem duplicata/None."""
    casas = sorted({p.get("casa") for p in premissas if p.get("casa")})
    tipos = sorted({p.get("tipo_documento") for p in premissas if p.get("tipo_documento")})
    tickers = sorted({t for p in premissas for t in (p.get("tickers") or [])})
    return {"casas": casas, "tipos": tipos, "tickers": tickers}


def _badge_confianca_html(confianca: str) -> str:
    classe, rotulo = _BADGE_CONFIANCA.get(confianca, ("memoria-badge-sem", confianca or "—"))
    return f"<span class='casas-badge {classe}'>{rotulo}</span>"


def _card_resultado_memoria(item: dict, fmt: str) -> str:
    """HTML de 1 resultado de embeddings.buscar() - renderiza SÓ os
    campos já estruturados que vieram no dict (link/casa/titulo/data/
    tickers/tipo_documento/premissas/projecoes/recomendacao/preco_alvo/
    origem_match); nunca sintetiza uma frase nova. link/casa/data sempre
    citados explicitamente (rastreabilidade até a publicação original)."""
    tickers_html = " ".join(
        f"<span style='color:var(--destaque);'>{html.escape(t)}</span>" for t in (item.get("tickers") or [])
    )
    tipo_doc = item.get("tipo_documento")
    tipo_label = _TIPO_DOCUMENTO_LABEL.get(tipo_doc, tipo_doc) if tipo_doc else None
    origem_label = _ORIGEM_MATCH_LABEL.get(item.get("origem_match"), item.get("origem_match"))
    meta = " · ".join(filter(None, [
        html.escape(item.get("casa") or ""), _fmt_data(item.get("data_publicacao")),
        tipo_label, tickers_html or "",
        f"origem: {origem_label}" if origem_label else "",
    ]))

    premissas_html = ""
    if item.get("premissas"):
        itens_html = "".join(
            f"<li class='cinza' style='font-size:0.74rem;'>{html.escape(p)}</li>" for p in item["premissas"]
        )
        premissas_html = f"<ul style='margin:0.2rem 0 0.3rem 1rem; padding:0;'>{itens_html}</ul>"

    projecoes_html = ""
    if item.get("projecoes"):
        partes = "; ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in item["projecoes"].items())
        projecoes_html = f"<div class='cinza' style='font-size:0.72rem;'>Projeções: {partes}</div>"

    recomendacao = item.get("recomendacao")
    preco_alvo = item.get("preco_alvo")
    rec_html = ""
    if recomendacao or preco_alvo is not None:
        rec_txt = html.escape(str(recomendacao)) if recomendacao else "não identificada"
        preco_txt = f"R$ {config.formatar_numero(preco_alvo, 2, fmt)}" if preco_alvo is not None else "não informado"
        rec_html = f"<div class='casas-rec'>Recomendação: <b>{rec_txt}</b> · Preço-alvo: <b>{preco_txt}</b></div>"

    link = item.get("link")
    titulo = html.escape(item.get("titulo") or "(sem título)")
    link_html = (
        f"<a href='{html.escape(link, quote=True)}' target='_blank' rel='noopener' "
        f"style='color:var(--neutro); font-weight:600; text-decoration:none; font-size:0.85rem;'>{titulo}</a>"
        if link else f"<span style='font-weight:600; font-size:0.85rem;'>{titulo}</span>"
    )

    return (
        "<div style='padding:0.35rem 0; border-bottom:1px solid var(--borda);'>"
        f"{link_html}"
        f"<div class='cinza' style='font-size:0.68rem; margin-top:0.15rem;'>{meta}</div>"
        f"{premissas_html}{projecoes_html}{rec_html}"
        "</div>"
    )


# --- leitura cacheada (so' pra montar as opcoes de filtro) ------------------

@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _premissas_para_opcoes_cacheado() -> list:
    """Cache curto (TTL_COLETA, mesmo padrão de _ultimo_snapshot_cacheado
    no topo deste arquivo) só pra montar as OPÇÕES de filtro (casa/tipo/
    ticker) - evita reconsultar o Supabase a cada rerun da aba só pra
    isso. A busca de verdade (embeddings.buscar, chamada abaixo) sempre
    lê o dado mais recente, sem cache."""
    return store.listar_premissas() or []


@st.fragment
def render_memoria_research(prefs: dict):
    """Ponto de entrada da subaba RESEARCH › Memória de Research
    (chamado por app.py): busca em linguagem natural + filtros sobre a
    biblioteca permanente de premissas/projeções (RAG, Fase C).

    Controles inline (sem formulário/botão separado - pills/selectbox já
    disparam rerun no próprio clique, texto dispara no Enter/blur, mesmo
    padrão do resto do app): mudar um filtro ou a pergunta já refaz a
    busca na hora. embeddings.buscar() só gera embedding (chamada de
    rede ao Gemini) quando `pergunta` não está vazia - filtrar só por
    ticker/casa/tipo/período nunca bate na API de IA.

    Se GEMINI_API_KEY não estiver configurada, mostra aviso claro e a
    busca cai pra lexical/estrutural (embeddings.buscar já trata isso
    internamente - aqui só repassamos pra tela)."""
    st.markdown(f"<style>{_CSS_MEMORIA}</style>", unsafe_allow_html=True)
    st.markdown('<div class="painel-titulo">MEMÓRIA DE RESEARCH</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='casas-nota'>Busca em linguagem natural + filtros sobre tudo que já foi extraído das "
        "publicações das casas de research (biblioteca permanente, nunca apaga) — toda citação traz "
        "fonte/data/casa, nunca sintetiza uma conclusão nova.</div>",
        unsafe_allow_html=True,
    )

    api_key, _ = config.obter_credenciais_gemini()
    if not api_key:
        st.warning(_AVISO_MEMORIA_SEM_CREDENCIAL)

    premissas_todas = _premissas_para_opcoes_cacheado()
    opcoes = _opcoes_filtro_memoria(premissas_todas)

    with st.container(key="memoria_filtros"):
        pergunta = st.text_input(
            "Pergunta em linguagem natural (opcional)", key="memoria_pergunta",
            placeholder="ex: qual a tese da Genial pra WEGE3?",
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_ticker = st.selectbox("Ticker", ["Todos"] + opcoes["tickers"], key="memoria_filtro_ticker")
        with col2:
            filtro_casa = st.selectbox("Casa", ["Todas"] + opcoes["casas"], key="memoria_filtro_casa")
        with col3:
            filtro_tipo = st.selectbox(
                "Tipo de documento", ["Todos"] + opcoes["tipos"], key="memoria_filtro_tipo",
                format_func=lambda t: _TIPO_DOCUMENTO_LABEL.get(t, t),
            )
        periodo_label = st.pills(
            "Período", ["7 dias", "30 dias", "90 dias", "Tudo"], default="Tudo",
            selection_mode="single", key="memoria_filtro_periodo",
        ) or "Tudo"

    dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "Tudo": None}[periodo_label]
    data_inicio = None
    if dias is not None:
        data_inicio = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=dias)).strftime("%Y-%m-%d")

    resultado = embeddings.buscar(
        pergunta=pergunta or None,
        ticker=None if filtro_ticker == "Todos" else filtro_ticker,
        casa=None if filtro_casa == "Todas" else filtro_casa,
        tipo_documento=None if filtro_tipo == "Todos" else filtro_tipo,
        data_inicio=data_inicio,
        top_k=10,
    )

    if resultado.get("aviso"):
        st.warning(resultado["aviso"])

    st.markdown(_badge_confianca_html(resultado["confianca"]), unsafe_allow_html=True)

    if not resultado["resultados"]:
        st.info("Nenhuma evidência encontrada para essa busca/filtros.")
        return

    fmt = prefs.get("formato_numerico", "BR")
    for item in resultado["resultados"]:
        st.markdown(_card_resultado_memoria(item, fmt), unsafe_allow_html=True)
# RADAR X — INTELIGÊNCIA SOCIAL (2026-10-30, pedido explícito do
# Rodrigo) - leitura pura de data/x_radar/store.py. Conector
# (data/x_signals.py) permanece desligado sem X_BEARER_TOKEN (ver
# docs/x-radar-inteligencia-social-20261030.md) - esta seção nunca
# esconde isso: mostra a saúde real do conector sempre no topo.
# ============================================================

_CSS_RADAR_X = """
.radarx-nota { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.8rem 0; line-height: 1.5; }
.radarx-tabela { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.radarx-tabela th {
    text-align: left; color: var(--cinza); font-size: 0.63rem; letter-spacing: 0.03em;
    padding: 0.3rem 0.5rem; border-bottom: 1px solid var(--borda);
}
.radarx-tabela td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--borda); vertical-align: top; }
.radarx-autor { color: var(--destaque); font-weight: 600; }
.radarx-badge { display: inline-block; padding: 0.05rem 0.4rem; border-radius: 3px; font-size: 0.62rem; font-weight: 600; }
.radarx-sub { color: var(--cinza); font-size: 0.68rem; }
"""

_COR_NIVEL_EVIDENCIA = {
    "nivel_3_confirmado_fonte_confiavel": "alta",
    "nivel_2_corroboracao_parcial": "alerta",
    "nivel_1_sinal_social": "cinza",
}

_LABEL_CATEGORIA = {
    "fato_confirmado": "FATO CONFIRMADO", "opiniao_analista": "OPINIÃO DE ANALISTA",
    "tese_investimento": "TESE DE INVESTIMENTO", "estimativa_projecao": "ESTIMATIVA/PROJEÇÃO",
    "rumor_nao_confirmado": "RUMOR NÃO CONFIRMADO", "noticia": "NOTÍCIA",
    "comentario_macro": "COMENTÁRIO MACRO", "sem_relevancia": "SEM RELEVÂNCIA",
}


def _radarx_filtros(prefs: dict) -> dict:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        dias = st.selectbox("Período", [1, 3, 7, 14, 30], index=2, key="radarx_dias", format_func=lambda d: f"{d}d")
    with col2:
        ticker = st.text_input("Ticker", key="radarx_ticker", placeholder="ex: PETR4").strip().upper() or None
    with col3:
        categoria = st.selectbox("Categoria", ["Todas"] + list(CATEGORIAS_PUBLICACAO), key="radarx_categoria")
        categoria = None if categoria == "Todas" else categoria
    with col4:
        confirmado = st.selectbox("Evidência", ["Todas", "Confirmado", "Em verificação", "Não confirmado"], key="radarx_confirmado")
    estado_map = {"Confirmado": "confirmado", "Em verificação": "em_verificacao", "Não confirmado": "detectado"}
    return {"dias": dias, "ticker": ticker, "categoria": categoria, "estado": estado_map.get(confirmado)}


def _radarx_linha_tabela(s: dict) -> str:
    cor_nivel = _COR_NIVEL_EVIDENCIA.get(s.get("nivel_evidencia"), "cinza")
    categoria_label = _LABEL_CATEGORIA.get(s.get("categoria"), s.get("categoria") or "—")
    relevancia = s.get("relevancia")
    relevancia_fmt = f"{relevancia}" if relevancia is not None else "—"
    credibilidade = s.get("credibilidade")
    credibilidade_fmt = f"{credibilidade}" if credibilidade is not None else "s/ histórico"
    ticker = html.escape(s.get("ticker") or "—")
    verificado = " ✓" if s.get("conta_verificada") else ""
    resumo = html.escape((s.get("texto") or "")[:140])
    link = html.escape(s.get("link_original") or "#", quote=True)
    return (
        "<tr>"
        f"<td class='radarx-autor'>{html.escape(s.get('autor') or '—')}{verificado}</td>"
        f"<td class='cinza'>{ticker}</td>"
        f"<td class='cinza'>{html.escape(categoria_label)}</td>"
        f"<td class='{cor_nivel}'>{html.escape((s.get('nivel_evidencia') or '').replace('nivel_1_sinal_social', 'SINAL SOCIAL').replace('nivel_2_corroboracao_parcial', 'EM VERIFICAÇÃO').replace('nivel_3_confirmado_fonte_confiavel', 'CONFIRMADO'))}</td>"
        f"<td class='cinza'>{relevancia_fmt}</td>"
        f"<td class='cinza'>{credibilidade_fmt}</td>"
        f"<td class='radarx-sub'><a href='{link}' target='_blank' rel='noopener'>{resumo}…</a></td>"
        "</tr>"
    )


@st.fragment
def render_radar_x(prefs: dict):
    """RADAR X — INTELIGÊNCIA SOCIAL: publicações classificadas do X
    cruzadas com research/news já existentes (data/x_radar/). Conector
    (data/x_signals.py) fica desligado sem X_BEARER_TOKEN - a saúde real
    do conector aparece SEMPRE no topo, nunca escondida atrás de uma
    tela vazia sem explicação (pedido explícito da seção 8: 'saúde do
    conector' é um dos 9 itens)."""
    st.markdown(f"<style>{_CSS_RADAR_X}</style>", unsafe_allow_html=True)
    st.markdown('<div class="painel-titulo">RADAR X — INTELIGÊNCIA SOCIAL</div>', unsafe_allow_html=True)

    saude = saude_conector()
    status_cred = saude["status_credencial"]
    with st.container(border=True):
        st.markdown('<div class="radarx-sub" style="font-weight:600; margin-bottom:0.3rem;">SAÚDE DO CONECTOR</div>', unsafe_allow_html=True)
        if status_cred["estado"] == "ok":
            st.markdown(f"<span class='alta radarx-badge'>CONECTADO</span>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"<span class='baixa radarx-badge'>DESLIGADO</span> "
                f"<span class='radarx-sub'>({html.escape(status_cred['estado'])})</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div class='radarx-nota'>{html.escape(status_cred['motivo'] or '')}</div>", unsafe_allow_html=True)
        total = saude.get("total_sinais")
        ultima = _idade_formatada(saude.get("ultima_captura")) if saude.get("ultima_captura") else "nunca"
        st.markdown(
            f"<div class='radarx-sub'>{total if total is not None else '—'} sinal(is) persistido(s) · última captura: {ultima}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Contas e termos monitorados", expanded=False):
        contas_fmt = ", ".join(f"@{c['handle']}" for c in CONTAS_MONITORADAS)
        st.markdown(f"<div class='radarx-sub'>Contas: {html.escape(contas_fmt)}</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='radarx-sub'>Universo completo (tickers/setores/macro) configurável em "
            "<code>data/x_radar/__init__.py</code>, sem precisar de migração.</div>",
            unsafe_allow_html=True,
        )

    if status_cred["estado"] != "ok":
        st.markdown(
            "<div class='radarx-nota' style='margin-top:0.6rem;'>Sem publicações pra mostrar - o conector "
            "está desligado (ver saúde acima). Nenhum dado é simulado nesta seção.</div>",
            unsafe_allow_html=True,
        )
        return

    filtros = _radarx_filtros(prefs)
    sinais = listar_sinais(ticker=filtros["ticker"], categoria=filtros["categoria"],
                            estado=filtros["estado"], dias=filtros["dias"])

    if sinais is None:
        st.warning("Banco indisponível - não foi possível carregar os sinais agora.")
        return
    if not sinais:
        st.markdown("<div class='radarx-sub'>Nenhuma publicação no filtro atual.</div>", unsafe_allow_html=True)
        return

    mais_relevantes = sorted(sinais, key=lambda s: s.get("relevancia") or 0, reverse=True)[:20]
    st.markdown('<div class="painel-titulo" style="font-size:0.78rem; margin-top:0.8rem;">PUBLICAÇÕES MAIS RELEVANTES</div>', unsafe_allow_html=True)
    linhas = "".join(_radarx_linha_tabela(s) for s in mais_relevantes)
    st.markdown(
        "<div style='overflow-x:auto;'><table class='radarx-tabela'>"
        "<thead><tr><th>AUTOR</th><th>TICKER</th><th>CATEGORIA</th><th>EVIDÊNCIA</th>"
        "<th>RELEVÂNCIA</th><th>CREDIBILIDADE</th><th>RESUMO</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table></div>",
        unsafe_allow_html=True,
    )

    catalisadores = [s for s in sinais if s.get("catalisador")]
    if catalisadores:
        st.markdown('<div class="painel-titulo" style="font-size:0.78rem; margin-top:1rem;">CATALISADORES IDENTIFICADOS</div>', unsafe_allow_html=True)
        for s in catalisadores[:10]:
            st.markdown(
                f"<div class='radarx-sub'><span class='radarx-autor'>{html.escape(s.get('ticker') or s.get('autor') or '')}</span> — "
                f"{html.escape(s['catalisador'])}</div>",
                unsafe_allow_html=True,
            )

    nao_corroboradas = [s for s in sinais if s.get("nivel_evidencia") == "nivel_1_sinal_social"]
    if nao_corroboradas:
        st.markdown('<div class="painel-titulo" style="font-size:0.78rem; margin-top:1rem;">AINDA NÃO CORROBORADAS</div>', unsafe_allow_html=True)
        st.markdown(f"<div class='radarx-sub'>{len(nao_corroboradas)} publicação(ões) sem confirmação de outra fonte - exibidas na tabela acima com evidência 'SINAL SOCIAL'.</div>", unsafe_allow_html=True)

    por_ticker: dict[str, list] = {}
    for s in sinais:
        if s.get("ticker"):
            por_ticker.setdefault(s["ticker"], []).append(s)
    if por_ticker:
        st.markdown('<div class="painel-titulo" style="font-size:0.78rem; margin-top:1rem;">POR TICKER</div>', unsafe_allow_html=True)
        for ticker, itens in sorted(por_ticker.items(), key=lambda kv: -len(kv[1])):
            sentimentos = {i.get("sentimento") for i in itens if i.get("sentimento")}
            divergente = " ⚠ opiniões divergentes" if len(sentimentos) > 1 else ""
            st.markdown(
                f"<div class='radarx-sub'><span class='radarx-autor'>{html.escape(ticker)}</span>: "
                f"{len(itens)} publicação(ões){divergente}</div>",
                unsafe_allow_html=True,
            )
