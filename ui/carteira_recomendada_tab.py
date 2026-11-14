# -*- coding: utf-8 -*-
"""Aba CARTEIRA RECOMENDADA (Visão Geral + Histórico).

Correção de inconsistência visual (2026-11-13, auditoria "revisão de
interface Bloomberg"): antes, app.py tinha um render MÍNIMO funcional
direto no dispatcher (st.title/st.caption/st.write/st.expander puro,
zero classe_sinal/numero_financeiro_html/painel-titulo) — era a única
área de conteúdo do app sem nenhum traço do design system (ver
ui/design_system.py), destoando do resto do terminal (preto/âmbar,
monoespaçado, denso). Esta reescrita é só de APRESENTAÇÃO: zero campo
novo, zero cálculo novo — mesmo shape estável de
montar_carteira_recomendada()/listar_historico_alteracoes()
(data/carteira_recomendada.py, documentado lá), só reorganizado em
tabela densa (1 linha por ativo, sempre visível) + métricas de resumo +
expander de DETALHE por ativo (tese/riscos/cenários/critério de saída —
suplementar, nunca escondendo a decisão primária, que já está na
tabela: ticker/peso/sinal/confiança/preço/retorno — mesmo princípio já
usado em MORNING CALL › Edição Atual)."""

import html

import streamlit as st

import config
from ui.design_system import numero_financeiro_html, variacao_html

_CSS_CARTEIRA = """
.cart-metricas { display:flex; flex-wrap:wrap; gap:1.2rem; margin:0.4rem 0 0.9rem 0; }
.cart-metrica { min-width:130px; }
.cart-metrica-valor { font-size:1.3rem; font-weight:600; color:var(--destaque); font-family:'IBM Plex Mono', monospace; }
.cart-metrica-rotulo { font-size:0.64rem; color:var(--cinza); letter-spacing:0.03em; text-transform:uppercase; }

.cart-scroll { overflow-x:auto; margin-top:0.8rem; }
.cart-tabela { width:100%; border-collapse:collapse; font-size:0.78rem; font-family:'IBM Plex Mono', monospace; min-width:720px; }
.cart-tabela th { text-align:right; font-size:0.62rem; color:var(--cinza); letter-spacing:0.05em;
                  padding:0.3rem 0.5rem; border-bottom:1px solid var(--borda); white-space:nowrap; }
.cart-tabela td { text-align:right; padding:0.3rem 0.5rem;
                  border-bottom:1px solid color-mix(in srgb, var(--borda) 60%, transparent); white-space:nowrap; }
.cart-tabela th.cart-esq, .cart-tabela td.cart-esq { text-align:left; white-space:normal; }
.cart-ticker { color:var(--destaque); font-weight:700; }
.cart-setor { color:var(--cinza); font-size:0.66rem; display:block; margin-top:0.1rem; }

.cart-badge { padding:0.05rem 0.45rem; font-size:0.62rem; letter-spacing:0.03em; font-weight:700; white-space:nowrap; }
.cart-badge-alta { color:var(--alta); border:1px solid var(--alta); }
.cart-badge-baixa { color:var(--baixa); border:1px solid var(--baixa); }
.cart-badge-neutro { color:var(--cinza); border:1px solid var(--borda); }

.cart-divgrid { display:flex; flex-wrap:wrap; gap:0.5rem 1.4rem; font-size:0.74rem; margin:0.2rem 0 0.1rem 0; }
.cart-divgrid .cart-setor-nome { color:var(--cinza); }

.cart-macro { display:flex; flex-wrap:wrap; gap:1.4rem; font-size:0.74rem; margin-top:0.1rem; }
.cart-macro .cart-macro-rotulo { color:var(--cinza); margin-right:0.3rem; }

.cart-detalhe { font-size:0.8rem; line-height:1.75; }
.cart-detalhe .cinza { color:var(--cinza); }
.cart-cenarios { display:flex; flex-wrap:wrap; gap:1.2rem; margin:0.4rem 0; font-family:'IBM Plex Mono', monospace; }
.cart-cenario-rotulo { font-size:0.62rem; color:var(--cinza); letter-spacing:0.03em; text-transform:uppercase; }
.cart-cenario-valor { font-size:0.9rem; }

.cart-hist-scroll { overflow-x:auto; }
.cart-hist-tabela { width:100%; border-collapse:collapse; font-size:0.78rem; font-family:'IBM Plex Mono', monospace; min-width:620px; }
.cart-hist-tabela th { text-align:left; font-size:0.62rem; color:var(--cinza); letter-spacing:0.05em;
                       padding:0.3rem 0.5rem; border-bottom:1px solid var(--borda); white-space:nowrap; }
.cart-hist-tabela td { text-align:left; padding:0.3rem 0.5rem;
                       border-bottom:1px solid color-mix(in srgb, var(--borda) 60%, transparent); vertical-align:top; }
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_CARTEIRA}</style>", unsafe_allow_html=True)


def _metrica_html(valor, rotulo: str) -> str:
    return (
        f"<div class='cart-metrica'><div class='cart-metrica-valor'>{html.escape(str(valor))}</div>"
        f"<div class='cart-metrica-rotulo'>{html.escape(rotulo)}</div></div>"
    )


def _badge_sinal(sinal: str) -> str:
    classe = {"COMPRA": "cart-badge-alta", "VENDA": "cart-badge-baixa"}.get(sinal, "cart-badge-neutro")
    return f"<span class='cart-badge {classe}'>{html.escape(sinal or '—')}</span>"


def _preco_html(valor, fmt: str):
    if valor is None:
        return "—"
    return numero_financeiro_html(valor, 2, fmt, prefixo="R$ ")


def _linha_tabela_html(item: dict, fmt: str) -> str:
    ticker = html.escape(item.get("ticker") or "—")
    setor = html.escape(item.get("setor") or "não classificado")
    peso = numero_financeiro_html(item.get("peso_pct") or 0.0, 1, fmt, sufixo="%")
    cenarios = item.get("cenarios") or {}
    base = cenarios.get("base") or {}
    retorno_base = base.get("retorno_pct")
    retorno_html = variacao_html(retorno_base, fmt, 1) if retorno_base is not None else "—"
    return (
        "<tr>"
        f"<td class='cart-esq'><span class='cart-ticker'>{ticker}</span><span class='cart-setor'>{setor}</span></td>"
        f"<td>{peso}</td>"
        f"<td>{_badge_sinal(item.get('sinal_comite'))}</td>"
        f"<td class='cart-esq'>{html.escape(item.get('confianca_comite') or '—')}</td>"
        f"<td>{_preco_html(item.get('preco_referencia'), fmt)}</td>"
        f"<td>{_preco_html(item.get('preco_alvo'), fmt)}</td>"
        f"<td>{retorno_html}</td>"
        f"<td class='cart-esq'>{html.escape(str(item.get('data_revisao') or '—'))}</td>"
        "</tr>"
    )


def _tabela_itens_html(itens: list, fmt: str) -> str:
    corpo = "".join(_linha_tabela_html(item, fmt) for item in itens)
    return (
        "<div class='cart-scroll'><table class='cart-tabela'><thead><tr>"
        "<th class='cart-esq'>ATIVO / SETOR</th><th>PESO</th><th>SINAL</th>"
        "<th class='cart-esq'>CONFIANÇA</th><th>PREÇO REF.</th><th>PREÇO-ALVO</th>"
        "<th>RETORNO (CEN. BASE)</th><th class='cart-esq'>PRÓXIMA REVISÃO</th>"
        f"</tr></thead><tbody>{corpo}</tbody></table></div>"
    )


def _resumo(resumo: dict, fmt: str):
    st.markdown(
        "<div class='cart-metricas'>"
        + _metrica_html(resumo.get("n_ativos", 0), "Ativos")
        + _metrica_html(f"{config.formatar_numero(resumo.get('peso_total_pct') or 0.0, 1, fmt)}%", "Peso total")
        + _metrica_html(resumo.get("setores_cobertos", 0), "Setores cobertos")
        + _metrica_html(f"{config.formatar_numero(resumo.get('concentracao_maxima_pct') or 0.0, 1, fmt)}%", "Concentração máx. por ativo")
        + "</div>",
        unsafe_allow_html=True,
    )

    diversificacao = resumo.get("diversificacao_setorial") or {}
    if diversificacao:
        st.markdown('<div class="painel-titulo" style="font-size:0.68rem;">DIVERSIFICAÇÃO SETORIAL</div>', unsafe_allow_html=True)
        itens = "".join(
            f"<div><span class='cart-setor-nome'>{html.escape(setor)}</span> "
            f"{config.formatar_numero(peso, 1, fmt)}%</div>"
            for setor, peso in sorted(diversificacao.items(), key=lambda kv: -kv[1])
        )
        st.markdown(f"<div class='cart-divgrid'>{itens}</div>", unsafe_allow_html=True)

    cenario_macro = resumo.get("cenario_macro") or {}

    # `cenario_macro` é um dict {nome_indicador: {"valor","unidade",
    # "referencia","detalhe","erro"}} - já o valor MAIS RECENTE de cada
    # série (ver data/carteira_recomendada.py:_contexto_macro, corrigido
    # na PR #313), nunca um DataFrame cru. Indicador que falhou na coleta
    # entra com valor=None (motivo em "erro") e é simplesmente omitido
    # aqui - melhor esforço, nunca derruba o resto do resumo.
    linhas_macro = [
        f"<span><span class='cart-macro-rotulo'>{html.escape(nome.upper())}</span>"
        f"{config.formatar_numero(dado['valor'], 2, fmt)}{html.escape(dado.get('unidade') or '')}</span>"
        for nome, dado in cenario_macro.items()
        if isinstance(dado, dict) and dado.get("valor") is not None
    ]
    if linhas_macro:
        st.markdown('<div class="painel-titulo" style="font-size:0.68rem;">CENÁRIO MACRO</div>', unsafe_allow_html=True)
        st.markdown(f"<div class='cart-macro'>{''.join(linhas_macro)}</div>", unsafe_allow_html=True)

    horizonte = resumo.get("horizonte")
    if horizonte:
        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin:0.5rem 0 1rem 0;'>Horizonte: {html.escape(horizonte)}</div>",
            unsafe_allow_html=True,
        )


def _cenario_item(rotulo: str, cenario: dict, fmt: str) -> str:
    preco = cenario.get("preco")
    retorno = cenario.get("retorno_pct")
    preco_txt = config.formatar_numero(preco, 2, fmt) if preco is not None else "—"
    retorno_html = variacao_html(retorno, fmt, 1) if retorno is not None else ""
    return (
        f"<div><div class='cart-cenario-rotulo'>{html.escape(rotulo)}</div>"
        f"<div class='cart-cenario-valor'>R$ {preco_txt} ({retorno_html})</div></div>"
    )


def _detalhe_item(item: dict, fmt: str):
    st.markdown(
        f"<div class='cart-detalhe'>"
        f"<div><span class='cinza'>Setor:</span> {html.escape(item.get('setor') or 'não classificado')} · "
        f"<span class='cinza'>Método do preço-alvo:</span> {html.escape(item.get('metodo_preco_alvo') or '—')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    cenarios = item.get("cenarios")
    if cenarios:
        st.markdown(
            "<div class='cart-cenarios'>"
            + _cenario_item("CONSERVADOR", cenarios.get("conservador") or {}, fmt)
            + _cenario_item("BASE", cenarios.get("base") or {}, fmt)
            + _cenario_item("OTIMISTA", cenarios.get("otimista") or {}, fmt)
            + "</div>",
            unsafe_allow_html=True,
        )
        aviso = cenarios.get("aviso")
        if aviso:
            st.markdown(f"<div class='cinza' style='font-size:0.68rem;'>{html.escape(aviso)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='cart-detalhe' style='margin-top:0.5rem;'>"
        f"<div><span class='cinza'>Tese:</span> {html.escape(item.get('tese') or 'sem resumo disponível')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    riscos = item.get("riscos") or []
    if riscos:
        st.markdown(
            "<div class='cart-detalhe'><span class='cinza'>Riscos:</span> "
            + html.escape("; ".join(riscos)) + "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        f"<div class='cart-detalhe'><span class='cinza'>Critério de saída:</span> "
        f"{html.escape(item.get('criterio_saida') or '—')}</div>",
        unsafe_allow_html=True,
    )
    liquidez = item.get("liquidez")
    if liquidez and liquidez.get("volume") is not None:
        st.markdown(
            f"<div class='cinza' style='font-size:0.7rem; margin-top:0.3rem;'>Volume (última sessão): "
            f"{config.formatar_numero(liquidez['volume'], 0, fmt)}</div>",
            unsafe_allow_html=True,
        )


def render_visao_geral(carteira: dict, prefs: dict):
    """Ponto de entrada de CARTEIRA RECOMENDADA › Visão Geral. `carteira`
    é o dict de retorno de data/carteira_recomendada.py:
    montar_carteira_recomendada() — shape documentado lá, nunca
    recalculado aqui."""
    fmt = prefs.get("formato_numerico", "BR")
    _injetar_css()
    st.markdown('<div class="painel-titulo">CARTEIRA RECOMENDADA</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='cinza' style='font-size:0.72rem; margin-bottom:0.5rem;'>Construída a partir do Comitê de "
        "Investimentos (coordenador_analises) — informativa, não é recomendação personalizada nem garante "
        "rentabilidade.</div>",
        unsafe_allow_html=True,
    )
    for aviso in carteira.get("avisos") or []:
        st.warning(aviso)

    itens = carteira.get("itens") or []
    resumo = carteira.get("resumo")
    if not itens:
        st.info("Nenhum ativo elegível no momento (ver avisos acima).")
        return

    if resumo:
        _resumo(resumo, fmt)

    st.markdown(_tabela_itens_html(itens, fmt), unsafe_allow_html=True)

    st.markdown('<div class="painel-titulo" style="font-size:0.68rem; margin-top:0.9rem;">DETALHE POR ATIVO</div>', unsafe_allow_html=True)
    for item in itens:
        with st.expander(f"{item['ticker']} · {html.escape(str(item.get('peso_pct')))}% · {item.get('sinal_comite') or '—'}"):
            _detalhe_item(item, fmt)


def _linha_historico_html(linha: dict) -> str:
    campo = html.escape(str(linha.get("campo") or "—"))
    anterior = html.escape(str(linha.get("valor_anterior") if linha.get("valor_anterior") is not None else "—"))
    novo = html.escape(str(linha.get("valor_novo") if linha.get("valor_novo") is not None else "—"))
    motivo = html.escape(str(linha.get("motivo") or "—"))
    registrado_em = html.escape(str(linha.get("registrado_em") or "—")[:19].replace("T", " "))
    ticker = html.escape(str(linha.get("ticker") or "—"))
    return (
        "<tr>"
        f"<td>{registrado_em}</td><td class='cart-ticker'>{ticker}</td><td>{campo}</td>"
        f"<td>{anterior}</td><td>{novo}</td><td>{motivo}</td>"
        "</tr>"
    )


def render_historico(historico: list | None):
    """Ponto de entrada de CARTEIRA RECOMENDADA › Histórico. `historico`
    é o retorno de data/carteira_recomendada.py:listar_historico_alteracoes()
    — None (Supabase/tabela indisponível), [] (sem alteração ainda) ou
    lista de linhas (ver shape no módulo de dados)."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">CARTEIRA RECOMENDADA — HISTÓRICO</div>', unsafe_allow_html=True)
    if historico is None:
        st.info(
            "Histórico ainda não disponível (persistência proposta em sql/carteira_recomendada.sql, "
            "não aplicada em produção)."
        )
        return
    if not historico:
        st.info("Nenhuma alteração registrada ainda.")
        return

    corpo = "".join(_linha_historico_html(linha) for linha in historico)
    st.markdown(
        "<div class='cart-hist-scroll'><table class='cart-hist-tabela'><thead><tr>"
        "<th>REGISTRADO EM</th><th>ATIVO</th><th>CAMPO</th><th>VALOR ANTERIOR</th>"
        "<th>VALOR NOVO</th><th>MOTIVO</th>"
        f"</tr></thead><tbody>{corpo}</tbody></table></div>",
        unsafe_allow_html=True,
    )
