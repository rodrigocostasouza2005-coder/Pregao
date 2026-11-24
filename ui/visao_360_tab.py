# -*- coding: utf-8 -*-
"""ANÁLISES > Visão 360 (missão visao-360-empresa-20261124, pedido do
Rodrigo): 1 tela só por ticker respondendo "como a empresa ganha dinheiro,
quanto custa agora, quanto deveria custar e o que o Comitê acha disso" -
hoje essa jornada está espalhada em ANÁLISES > Empresas/Fundamentos/Perfil
da Empresa, VALUATION > Parecer do Comitê/Simulador DCF e COMITÊ, cada
uma com seu próprio seletor de ticker desconectado das outras. Resolve o
item de BACKLOG.md "EQUITY não é 'Company 360'".

ESTE MÓDULO NÃO CALCULA NADA NOVO - é uma camada de COMPOSIÇÃO pura sobre
4 peças já existentes e testadas em produção, cada uma com seu próprio
módulo/teste dedicado:
- data/empresa_perfil.py:obter_perfil_empresa (via
  ui/coordenador_tab.py:render_perfil_empresa_tab, chamado direto - zero
  lógica de perfil duplicada aqui).
- data/radar.py:linha_valuation (múltiplos rápidos) +
  ui/analises_tab.py:controle_dcf_inline (preço-alvo DCF com cenários,
  motor corrigido na PR #353 - este módulo NUNCA recalcula FCF/WACC/
  crescimento, só repassa o dict que linha_valuation já devolve).
- data/coordenador_central/persistencia.py:listar_analises_por_ticker/
  obter_analise + ui/coordenador_tab.py:render_consolidado (veredito do
  Comitê já persistido, se existir).
- data/prices.py:obter_cotacao (preço atual + variação do dia).

PRINCÍPIO (testado em tests/test_visao_360_tab.py): dado ausente em
QUALQUER seção degrada com motivo explícito - nunca inventa número, nunca
fica em silêncio vazio/sem explicação. Em especial, "nunca analisado pelo
Comitê" (listar_analises_por_ticker devolve []) e "não foi possível checar
se já foi analisado" (Supabase indisponível, devolve None) são avisos
DISTINTOS - confundir os dois diria a um usuário que um ticker nunca visto
pelo Comitê foi conferido e está limpo, quando na verdade a conferência
nem rodou."""

import html

import streamlit as st

import config
from data.coordenador_central.persistencia import listar_analises_por_ticker, obter_analise
from data.prices import obter_cotacao, obter_nome_yf
from data.radar import linha_valuation
from ui import design_system as ds
from ui import navegacao
from ui.analises_tab import controle_dcf_inline
from ui.coordenador_tab import render_consolidado, render_perfil_empresa_tab


# ============================================================
# Cabeçalho: ticker + nome + preço atual/variação do dia.
# ============================================================

def _nome_empresa(ticker: str) -> str | None:
    """Mesma cascata já usada em ui/coordenador_tab.py:_nome_empresa_exibicao
    (config.TICKER_NOME primeiro - cadastro manual, grátis -, fallback
    obter_nome_yf - cacheado 24h) - não importa a função privada de lá
    (módulo de UI diferente), só replica a mesma regra já documentada."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    try:
        nome = config.TICKER_NOME.get(ticker) or obter_nome_yf(ticker)
    except Exception:
        return None
    return nome or None


def _render_cabecalho(ticker: str, prefs: dict):
    nome = _nome_empresa(ticker)
    titulo = html.escape(ticker) + (f" — {html.escape(nome)}" if nome else "")
    try:
        cot = obter_cotacao(ticker)
    except Exception as exc:
        cot = {"erro": repr(exc)}

    st.markdown(f'<div class="painel-titulo">{titulo}</div>', unsafe_allow_html=True)
    if cot.get("erro"):
        st.markdown("<div style='font-size:1.3rem; font-weight:700;'>—</div>", unsafe_allow_html=True)
        st.caption(f"Preço atual indisponível agora: {html.escape(str(cot['erro']))}.")
        return

    fmt = prefs["formato_numerico"]
    preco_html = ds.numero_financeiro_html(cot["preco"], 2, fmt, prefixo="R$ ")
    variacao_html = ds.variacao_html(cot["variacao_pct"], fmt)
    st.markdown(
        f"<div style='font-size:1.3rem; font-weight:700;'>{preco_html} "
        f"<span style='font-size:0.85rem;'>{variacao_html}</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Cotação: {cot.get('tipo_cotacao') or 'Yahoo Finance'}.")


# ============================================================
# Valuation: múltiplos rápidos (linha_valuation) + preço-alvo DCF
# (controle_dcf_inline, reaproveitando o MESMO dict de linha_valuation
# como `fundamentos` - ele já traz fluxo_caixa_livre/divida_liquida/
# valor_mercado/preco, os únicos campos que controle_dcf_inline lê de
# `fundamentos`; `historico` é None de propósito - o motor de DCF desta
# tela nunca usou o acumulado YTD da CVM, ver docstring de
# ui/analises_tab.py:_fcf_para_dcf).
# ============================================================

def _numero_ou_traco(valor, fmt: str, casas: int = 2, sufixo: str = "", prefixo: str = "") -> str:
    if not isinstance(valor, (int, float)):
        return "—"
    return ds.numero_financeiro_html(valor, casas, fmt, prefixo=prefixo, sufixo=sufixo)


def _render_valuation(ticker: str, prefs: dict):
    st.markdown('<div class="painel-titulo" style="font-size:0.78rem;">VALUATION</div>', unsafe_allow_html=True)
    try:
        linha = linha_valuation(ticker)
    except Exception as exc:
        st.warning(f"Múltiplos e valuation indisponíveis agora: {exc!r}")
        return

    fmt = prefs["formato_numerico"]
    metricas = [
        ("P/L", _numero_ou_traco(linha.get("pl"), fmt)),
        ("P/VP", _numero_ou_traco(linha.get("pvp"), fmt)),
        ("DIV. YIELD", _numero_ou_traco(linha.get("dividend_yield"), fmt, sufixo="%")),
        ("ROE", _numero_ou_traco(linha.get("roe"), fmt, sufixo="%")),
        ("MARGEM LÍQ.", _numero_ou_traco(linha.get("margem_liquida"), fmt, sufixo="%")),
        ("DÍV.LÍQ./EBITDA", _numero_ou_traco(linha.get("divida_liquida_ebitda"), fmt, sufixo="x")),
        ("FCF", _numero_ou_traco(linha.get("fluxo_caixa_livre"), fmt, casas=0, prefixo="R$ ")),
    ]
    st.markdown(
        "<div style='display:flex; flex-wrap:wrap; gap:1.2rem; margin:0.2rem 0 0.4rem 0;'>" + "".join(
            f"<div><div class='cinza' style='font-size:0.6rem; letter-spacing:0.04em;'>{html.escape(rot)}</div>"
            f"<div style='font-size:0.88rem; font-weight:700;'>{val}</div></div>"
            for rot, val in metricas
        ) + "</div>",
        unsafe_allow_html=True,
    )

    if linha.get("preco_erro"):
        st.caption(f"Cotação usada nos múltiplos indisponível agora: {html.escape(str(linha['preco_erro']))}.")
    if linha.get("desatualizado"):
        st.caption("Fundamentos usados aqui podem estar desatualizados (fallback de coleta anterior).")
    for alerta in (linha.get("alerta_qualidade") or []):
        st.caption(f"Alerta de qualidade: {html.escape(str(alerta))}.")

    st.markdown(
        '<div class="painel-titulo" style="font-size:0.74rem; margin-top:0.6rem;">PREÇO-ALVO (DCF)</div>',
        unsafe_allow_html=True,
    )
    if linha.get("fluxo_caixa_livre") is None:
        st.caption(
            "Preço-alvo por DCF indisponível para este ticker: fluxo de caixa livre (yfinance) não encontrado."
        )
        return
    try:
        controle_dcf_inline(ticker, linha, None)
    except Exception as exc:
        st.warning(f"Não foi possível calcular o DCF agora: {exc!r}")


# ============================================================
# O que o Comitê acha: última análise persistida pra este ticker (se
# houver) + atalhos de navegação (nunca recalcula nem resume de novo -
# só exibe o que já existe, via render_consolidado).
# ============================================================

def _cta_executar_comite(ticker: str):
    navegacao.link(
        "Executar Comitê para este ticker ↗", "comite", "visao-geral",
        chave=f"v360_executar_comite_{ticker}", ticker=ticker,
    )


def _render_comite(ticker: str):
    st.markdown(
        '<div class="painel-titulo" style="font-size:0.78rem;">O QUE O COMITÊ ACHA</div>',
        unsafe_allow_html=True,
    )
    try:
        analises = listar_analises_por_ticker(ticker, limite=1)
    except Exception:
        analises = None

    if analises is None:
        st.warning(
            f"Não foi possível verificar se {html.escape(ticker)} já foi analisado pelo Comitê agora "
            "(Supabase indisponível no momento) — isto é diferente de 'nunca analisado': a conferência "
            "não rodou, não se sabe ainda se existe uma análise ou não."
        )
        _cta_executar_comite(ticker)
        return

    if not analises:
        st.info(f"O Comitê ainda não analisou {html.escape(ticker)} nesta instalação.")
        _cta_executar_comite(ticker)
        return

    analise_id = analises[0].get("id")
    analise = obter_analise(analise_id) if analise_id else None
    if analise is None:
        st.warning("Não foi possível carregar os detalhes da análise mais recente agora (Supabase indisponível no momento).")
        _cta_executar_comite(ticker)
        return

    if analise.get("status") == "ERRO":
        st.error(f"A análise mais recente deste ticker terminou em erro: {analise.get('erro') or 'motivo não especificado'}.")
        _cta_executar_comite(ticker)
        return

    resultado = analise.get("resultado")
    if not resultado:
        st.info("A análise mais recente deste ticker ainda não tem resultado consolidado (pode estar em andamento).")
        _cta_executar_comite(ticker)
        return

    render_consolidado(resultado)
    navegacao.link(
        "Ver histórico completo deste ticker ↗", "comite", "historico",
        chave=f"v360_historico_comite_{ticker}", ticker=ticker,
    )


# ============================================================
# Composição final.
# ============================================================

def render_visao_360(ticker: str, prefs: dict):
    ticker = (ticker or "").strip().upper()
    if not ticker:
        st.info("Selecione um ticker para ver a Visão 360.")
        return

    with st.container(border=True):
        _render_cabecalho(ticker, prefs)

    render_perfil_empresa_tab(ticker)

    with st.container(border=True):
        _render_valuation(ticker, prefs)

    with st.container(border=True):
        _render_comite(ticker)
