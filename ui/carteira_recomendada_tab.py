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

/* ---- ESTADO DA TESE (missão "Radar inteligente e acompanhamento de
   teses", 2026-11-23) - badge + grid de acompanhamento + linha do tempo
   de eventos dentro do DETALHE POR ATIVO já existente. */
.cart-tese-topo { display:flex; align-items:baseline; gap:0.6rem; flex-wrap:wrap; margin:0.5rem 0 0.3rem 0; }
.cart-tese-badge { padding:0.1rem 0.5rem; font-size:0.66rem; font-weight:700; letter-spacing:0.03em; white-space:nowrap; }
.cart-tese-preservada { color:var(--cinza); border:1px solid var(--borda); }
.cart-tese-fortalecida { color:var(--alta); border:1px solid var(--alta); }
.cart-tese-enfraquecida { color:var(--destaque); border:1px solid var(--destaque); }
.cart-tese-em_revisao { color:var(--destaque); border:1px solid var(--destaque); border-style:dashed; }
.cart-tese-invalidada { color:var(--baixa); border:1px solid var(--baixa); }
.cart-tese-dados_insuficientes { color:var(--cinza); border:1px dashed var(--borda); }
.cart-tese-motivo { font-size:0.74rem; color:var(--cinza); margin-bottom:0.5rem; }
.cart-tese-grid { display:flex; flex-wrap:wrap; gap:0.9rem 1.6rem; font-size:0.74rem; margin:0.3rem 0 0.6rem 0; font-family:'IBM Plex Mono', monospace; }
.cart-tese-grid .cart-tese-rotulo { color:var(--cinza); display:block; font-size:0.62rem; letter-spacing:0.03em; text-transform:uppercase; font-family:'IBM Plex Mono', monospace; }
.cart-tese-diff { font-size:0.76rem; margin:0.25rem 0; line-height:1.6; }
.cart-tese-diff .cinza { color:var(--cinza); }
.cart-tese-eventos-scroll { overflow-x:auto; }
.cart-tese-eventos { width:100%; border-collapse:collapse; font-size:0.72rem; font-family:'IBM Plex Mono', monospace; min-width:560px; }
.cart-tese-eventos th { text-align:left; font-size:0.6rem; color:var(--cinza); letter-spacing:0.04em;
                        padding:0.25rem 0.45rem; border-bottom:1px solid var(--borda); white-space:nowrap; }
.cart-tese-eventos td { text-align:left; padding:0.25rem 0.45rem;
                        border-bottom:1px solid color-mix(in srgb, var(--borda) 60%, transparent); vertical-align:top; }
.cart-tese-avisos { font-size:0.66rem; color:var(--cinza); margin-top:0.3rem; line-height:1.5; }
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


# Mesmo limiar já estabelecido em data/radar.py (_LIMIAR_CONCENTRACAO_PCT,
# usado no RISCO DA CARTEIRA do RADAR pra concentração por ativo/setor da
# carteira REAL do usuário cadastrada em data/posicoes.py) - reaproveitado
# aqui pra responder "existe concentração excessiva?" na CARTEIRA
# RECOMENDADA, não um número novo inventado pra este painel.
_LIMIAR_CONCENTRACAO_SETOR_PCT = 25.0


def _nota_contextual(tag: str, texto: str):
    """[FATO]/[LEITURA] - mesmo padrão de rótulo explícito já usado em
    ui/mercado_tab.py:_nota_contextual e ui/macro_tab.py:
    _nota_contextual_macro (cópia local de propósito, mesma convenção já
    seguida no projeto pra módulos de UI que não se importam entre si)."""
    cor = "var(--cinza)" if tag == "FATO" else "var(--destaque)"
    st.markdown(
        f"<div style='font-size:0.66rem; color:var(--cinza); margin:0.15rem 0;'>"
        f"<b style='color:{cor};'>[{tag}]</b> {texto}</div>",
        unsafe_allow_html=True,
    )


def _leitura_carteira(carteira: dict, fmt: str):
    """LEITURA DA CARTEIRA (2026-11-18, missão "camada analítica"):
    responde "existe concentração ou risco excessivo?" e "qual posição
    merece atenção?" (pedido explícito do Rodrigo) - reaproveita SÓ dado
    já computado por montar_carteira_recomendada()
    (resumo['diversificacao_setorial'] e confianca_comite/riscos de cada
    item, ver data/carteira_recomendada.py) - zero cálculo novo, zero IA.

    "Merece atenção" usa SÓ confianca_comite == "BAIXA" (categoria já
    atribuída pelo Comitê, não inferida aqui) - NUNCA a mera presença de
    'riscos' (quase toda posição tem ao menos 1 "ponto contrário"
    listado pelo Comitê; tratar isso como sinal de atenção deixaria a
    nota sempre populada, o que o pedido proíbe - "nunca preenchida com
    algo genérico só pra não parecer vazia"). Nenhuma nota aparece se não
    houver concentração setorial acima do limiar nem posição com
    confiança BAIXA (estado vazio honesto)."""
    resumo = carteira.get("resumo") or {}
    itens = carteira.get("itens") or []
    notas = []

    diversificacao = resumo.get("diversificacao_setorial") or {}
    concentrados = sorted(
        ((setor, peso) for setor, peso in diversificacao.items() if peso > _LIMIAR_CONCENTRACAO_SETOR_PCT),
        key=lambda sp: -sp[1],
    )
    if concentrados:
        partes = ", ".join(
            f"{html.escape(setor)} ({config.formatar_numero(peso, 1, fmt)}%)" for setor, peso in concentrados
        )
        notas.append(("FATO",
            f"Concentração setorial acima de {_LIMIAR_CONCENTRACAO_SETOR_PCT:g}% da carteira: {partes}."))

    atencao = [item for item in itens if (item.get("confianca_comite") or "").upper() == "BAIXA"]
    if atencao:
        partes = []
        for item in atencao:
            n_riscos = len(item.get("riscos") or [])
            riscos_txt = f", {n_riscos} risco(s) listado(s) pelo Comitê" if n_riscos else ""
            partes.append(f"{html.escape(item.get('ticker') or '—')} (confiança BAIXA{riscos_txt})")
        notas.append(("FATO", "Posições que merecem atenção: " + "; ".join(partes) + "."))

    if not notas:
        return

    st.markdown(
        '<div class="painel-titulo" style="font-size:0.68rem; margin-top:0.6rem;">LEITURA DA CARTEIRA</div>',
        unsafe_allow_html=True,
    )
    for tag, texto in notas:
        _nota_contextual(tag, texto)


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


# ============================================================
# ESTADO DA TESE (missão "Radar inteligente e acompanhamento de teses",
# 2026-11-23) - responde, por ativo: por que entrou, tese/preço original,
# o que o Comitê já reavaliou desde então (eventos), como o preço evoluiu
# x Ibovespa e qual é o ESTADO da tese. 100% sobre
# data/carteira_recomendada.py:estado_tese() - zero cálculo novo aqui,
# só apresentação.
# ============================================================

_ROTULO_ESTADO_TESE = {
    "PRESERVADA": "TESE PRESERVADA", "FORTALECIDA": "TESE FORTALECIDA",
    "ENFRAQUECIDA": "TESE ENFRAQUECIDA", "EM_REVISAO": "EM REVISÃO",
    "INVALIDADA": "TESE INVALIDADA", "DADOS_INSUFICIENTES": "DADOS INSUFICIENTES",
}


def _badge_estado_tese(classificacao: str) -> str:
    classe = f"cart-tese-{(classificacao or '').lower()}"
    rotulo = _ROTULO_ESTADO_TESE.get(classificacao, classificacao or "—")
    return f"<span class='cart-tese-badge {classe}'>{html.escape(rotulo)}</span>"


def _linha_evento_tese_html(evento: dict) -> str:
    quando = html.escape(str(evento.get("registrado_em") or "—")[:10])
    campo = html.escape(str(evento.get("campo") or "—"))
    anterior = evento.get("valor_anterior")
    novo = evento.get("valor_novo")
    if campo == "entrada_na_carteira":
        transicao = "Entrou na carteira"
    elif campo == "saida_da_carteira":
        transicao = "Saiu da carteira"
    else:
        transicao = f"{html.escape(str(anterior) if anterior is not None else '—')} → {html.escape(str(novo) if novo is not None else '—')}"
    motivo = html.escape(str(evento.get("motivo") or "—"))
    return f"<tr><td>{quando}</td><td>{campo}</td><td>{transicao}</td><td>{motivo}</td></tr>"


def _secao_estado_tese(ticker: str, fmt: str, itens_atuais: list | None):
    """Seção de ACOMPANHAMENTO DE TESE de um ativo - chamada 1x por item
    dentro do expander de DETALHE POR ATIVO (ver render_visao_geral).
    `itens_atuais` pré-buscado uma única vez pelo chamador (não refaz a
    consulta da tabela inteira pra cada ticker - ver docstring de
    data.carteira_recomendada.estado_tese)."""
    from data.carteira_recomendada import estado_tese

    info = estado_tese(ticker, itens_atuais=itens_atuais)
    st.markdown('<div class="painel-titulo" style="font-size:0.7rem; margin-top:0.7rem;">ESTADO DA TESE</div>', unsafe_allow_html=True)
    if info is None:
        st.markdown(
            "<div class='cinza' style='font-size:0.72rem;'>Este ativo ainda não gerou histórico nem "
            "acompanhamento persistido (nunca passou por uma rodada completa da Carteira Recomendada "
            "antes de hoje) - sem dado suficiente pra montar a linha do tempo da tese.</div>",
            unsafe_allow_html=True,
        )
        return

    estado = info.get("estado") or {}
    st.markdown(
        "<div class='cart-tese-topo'>" + _badge_estado_tese(estado.get("classificacao")) + "</div>"
        f"<div class='cart-tese-motivo'>{html.escape(estado.get('motivo') or '—')}</div>",
        unsafe_allow_html=True,
    )

    def _campo(rotulo, valor):
        return f"<div><span class='cart-tese-rotulo'>{html.escape(rotulo)}</span>{valor}</div>"

    data_entrada = html.escape(str(info.get("data_entrada") or "—")[:10])
    preco_entrada_txt = _preco_html(info.get("preco_entrada"), fmt)
    preco_atual_txt = _preco_html(info.get("preco_atual"), fmt)
    retorno_txt = (variacao_html(info["retorno_acumulado_pct"], fmt, 1)
                   if info.get("retorno_acumulado_pct") is not None else "—")
    benchmark = info.get("benchmark")
    benchmark_txt = (variacao_html(benchmark["retorno_pct"], fmt, 1)
                     if benchmark and benchmark.get("retorno_pct") is not None else "—")
    relativo_txt = (variacao_html(info["retorno_relativo_pct"], fmt, 1)
                    if info.get("retorno_relativo_pct") is not None else "—")

    st.markdown(
        "<div class='cart-tese-grid'>"
        + _campo("Entrada", data_entrada)
        + _campo("Preço de entrada", preco_entrada_txt)
        + _campo("Preço atual", preco_atual_txt)
        + _campo("Retorno acumulado", retorno_txt)
        + _campo(f"IBOVESPA (mesmo período)", benchmark_txt)
        + _campo("Retorno relativo", relativo_txt)
        + "</div>",
        unsafe_allow_html=True,
    )

    tese_original = info.get("tese_original")
    tese_atual = info.get("tese_atual")
    if tese_original and tese_atual and tese_original != tese_atual:
        st.markdown(
            "<div class='cart-tese-diff'>"
            f"<span class='cinza'>Tese original (na entrada):</span> {html.escape(tese_original)}<br>"
            f"<span class='cinza'>Tese atual:</span> {html.escape(tese_atual)}"
            "</div>",
            unsafe_allow_html=True,
        )
    elif tese_original and not tese_atual:
        st.markdown(
            f"<div class='cart-tese-diff'><span class='cinza'>Tese original (na entrada):</span> "
            f"{html.escape(tese_original)}</div>",
            unsafe_allow_html=True,
        )

    eventos = info.get("eventos") or []
    if eventos:
        with st.expander(f"Linha do tempo ({len(eventos)} evento(s) desde a entrada)"):
            corpo = "".join(_linha_evento_tese_html(e) for e in eventos)
            st.markdown(
                "<div class='cart-tese-eventos-scroll'><table class='cart-tese-eventos'><thead><tr>"
                "<th>DATA</th><th>CAMPO</th><th>TRANSIÇÃO</th><th>MOTIVO</th>"
                f"</tr></thead><tbody>{corpo}</tbody></table></div>",
                unsafe_allow_html=True,
            )

    avisos = info.get("avisos") or []
    if avisos:
        st.markdown(
            "<div class='cart-tese-avisos'>" + "<br>".join(html.escape(a) for a in avisos) + "</div>",
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

    _leitura_carteira(carteira, fmt)

    st.markdown(_tabela_itens_html(itens, fmt), unsafe_allow_html=True)

    # itens_atuais buscado 1x FORA do loop (achado de performance, ver
    # docstring de data.carteira_recomendada.estado_tese) - sem isso,
    # cada ativo da carteira dispararia sua própria consulta da tabela
    # inteira só pra ler o PRÓPRIO item, repetindo o mesmo round-trip ao
    # Supabase até len(itens) vezes na mesma renderização.
    from data.carteira_recomendada import obter_ultima_carteira_persistida
    itens_atuais = obter_ultima_carteira_persistida()

    st.markdown('<div class="painel-titulo" style="font-size:0.68rem; margin-top:0.9rem;">DETALHE POR ATIVO</div>', unsafe_allow_html=True)
    for item in itens:
        with st.expander(f"{item['ticker']} · {html.escape(str(item.get('peso_pct')))}% · {item.get('sinal_comite') or '—'}"):
            _detalhe_item(item, fmt)
            _secao_estado_tese(item["ticker"], fmt, itens_atuais)


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
