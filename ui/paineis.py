# -*- coding: utf-8 -*-
"""Sistema de "painéis registrados": abas que adotam isso declaram uma
lista de (id, rótulo, função_render) na ordem padrão; o usuário pode
REORDENAR, esconder e escolher a LARGURA de cada painel (não
arrastar/redimensionar livremente - ver decisão original registrada em
PROGRESSO.md, seção FILA2-T5, e a extensão dela na ETAPA 7) via
controles dentro do formulário de CONFIG. Tudo persistido em
prefs["ordem_paineis"]/["paineis_visiveis"]/["tamanho_paineis"],
chaveado por aba_id - reaproveita a tabela user_prefs que já existe,
sem tabela nova no Supabase.

Por que largura fixa (1/4, 1/2, 3/4, FULL) em vez de redimensionar livre
com o mouse: Streamlit não tem componente nativo de drag-resize, e o
projeto não usa nenhum componente de terceiros em lugar nenhum hoje - um
componente desses seria uma dependência nova e mais pesada de manter.
Larguras fixas cobrem o pedido comum ("quero X e Y lado a lado, menores")
usando só `st.columns()`, sem HTML/JS customizado. Os painéis de uma
linha são empacotados na ordem escolhida: cada um entra na linha atual
até a soma das larguras estourar 1.0, aí uma linha nova começa - um
painel FULL (1.0) sempre fica sozinho na própria linha.

Hoje só MACRO e MERCADO adotam esse registro (ver REGISTRO_PAINEIS em
ui/macro_tab.py e ui/mercado_tab.py) - as outras abas (EQUITY, CVM,
NEWS, RESEARCH, TOP MERCADO, VISÃO GERAL) renderizam do jeito
monolítico de sempre e não têm reordenar/visibilidade/tamanho
configurável. Migrar todas pra esse sistema é um trabalho maior à parte
(redesenhar cada painel de cada aba pra funcionar dentro de uma coluna
mais estreita) - fora do escopo desta rodada."""

import streamlit as st

TAMANHOS = ["1/4", "1/2", "3/4", "FULL"]
_FRACOES = {"1/4": 0.25, "1/2": 0.5, "3/4": 0.75, "FULL": 1.0}
_TAMANHO_PADRAO = "FULL"

_CSS_PAINEIS = """
[data-testid="stButtonGroup"] { flex-wrap: wrap !important; row-gap: 0.3rem; }
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_PAINEIS}</style>", unsafe_allow_html=True)


def ordem_efetiva(aba_id: str, registro: list, prefs: dict) -> list:
    """registro: lista de (id, rotulo, render_fn). Retorna a lista de ids
    na ordem em que devem ser renderizados: a ordem salva em
    prefs["ordem_paineis"][aba_id], filtrada pra só ids que ainda existem
    no registro (painel removido do código some sem erro) + qualquer
    painel NOVO do registro que o usuário ainda não tinha salvo (entra no
    fim, mesma lógica de migração de abas novas em app.py)."""
    ids_registro = [pid for pid, _, _ in registro]
    salva = (prefs.get("ordem_paineis") or {}).get(aba_id, [])
    ordem = [pid for pid in salva if pid in ids_registro]
    for pid in ids_registro:
        if pid not in ordem:
            ordem.append(pid)
    return ordem


def _pid_visivel_salvo(aba_id: str, pid: str, prefs: dict) -> bool:
    """None salvo (usuário nunca configurou visibilidade pra essa aba) =
    tudo visível por padrão; lista salva (mesmo vazia) = exatamente
    essa lista - permite o usuário escolher esconder tudo de propósito."""
    salvo = (prefs.get("paineis_visiveis") or {}).get(aba_id)
    return True if salvo is None else pid in salvo


def _tamanho_efetivo(aba_id: str, pid: str, prefs: dict) -> str:
    salvo = (prefs.get("tamanho_paineis") or {}).get(aba_id, {}).get(pid)
    return salvo if salvo in TAMANHOS else _TAMANHO_PADRAO


def _empacotar_linhas(ids: list, fracoes: dict) -> list:
    """Agrupa ids em 'linhas' (cada uma vira um st.columns) somando as
    frações de largura na ordem dada - estourou 1.0, comeca linha nova.
    Retorna lista de linhas, cada linha uma lista de (id, fracao)."""
    linhas, atual, soma = [], [], 0.0
    for pid in ids:
        fracao = fracoes[pid]
        if atual and soma + fracao > 1.0 + 1e-6:
            linhas.append(atual)
            atual, soma = [], 0.0
        atual.append((pid, fracao))
        soma += fracao
    if atual:
        linhas.append(atual)
    return linhas


def renderizar(aba_id: str, registro: list, prefs: dict, *args, **kwargs):
    """Renderiza cada painel visível do registro, na ordem efetiva,
    empacotados em linhas conforme a largura configurada de cada um
    (ver _empacotar_linhas) - painel FULL sozinho vira um
    st.container(border=True) simples (mesmo comportamento de sempre,
    zero mudança visual pra quem nunca configurou tamanho/visibilidade).
    args/kwargs extras são repassados pra cada render_fn (ex: o ticker
    selecionado numa aba tipo EQUITY)."""
    mapa = {pid: fn for pid, _, fn in registro}
    ordem = [pid for pid in ordem_efetiva(aba_id, registro, prefs) if _pid_visivel_salvo(aba_id, pid, prefs)]

    if not ordem:
        st.info("Nenhum painel visível nesta aba — ajuste em CONFIG, seção LAYOUT.")
        return

    fracoes = {pid: _FRACOES[_tamanho_efetivo(aba_id, pid, prefs)] for pid in ordem}

    for linha in _empacotar_linhas(ordem, fracoes):
        if len(linha) == 1 and linha[0][1] == 1.0:
            with st.container(border=True):
                mapa[linha[0][0]](*args, **kwargs)
            continue
        cols = st.columns([fracao for _, fracao in linha], gap="small")
        for col, (pid, _) in zip(cols, linha):
            with col:
                with st.container(border=True):
                    mapa[pid](*args, **kwargs)


def controle_ordem_config(aba_id: str, aba_rotulo: str, registro: list, prefs: dict) -> list:
    """Widget pra usar dentro do formulário de CONFIG: multiselect onde a
    ORDEM DE SELEÇÃO vira a ordem de exibição (mesmo padrão já usado em
    'ABAS VISÍVEIS'). Retorna a nova lista de ids escolhida - quem chama
    grava isso em prefs['ordem_paineis'][aba_id] ao salvar o formulário."""
    mapa_rotulo_id = {rotulo: pid for pid, rotulo, _ in registro}
    mapa_id_rotulo = {pid: rotulo for pid, rotulo, _ in registro}
    rotulos_atuais = [mapa_id_rotulo[pid] for pid in ordem_efetiva(aba_id, registro, prefs)]
    escolha = st.multiselect(
        f"ORDEM DOS PAINÉIS — {aba_rotulo} (ordem de seleção = ordem de exibição)",
        [rotulo for _, rotulo, _ in registro], default=rotulos_atuais,
        key=f"ordem_paineis_{aba_id}",
    )
    novos_ids = [mapa_rotulo_id[r] for r in escolha]
    # selecao vazia (usuario limpou sem querer) volta pra ordem padrao do
    # registro em vez de nao renderizar nenhum painel
    return novos_ids or [pid for pid, _, _ in registro]


def controle_layout_config(aba_id: str, aba_rotulo: str, registro: list, prefs: dict) -> tuple:
    """Widget pra usar dentro do formulário de CONFIG, logo após
    controle_ordem_config: uma linha por painel (na ordem atual) com
    checkbox de visibilidade + pills de largura (1/4, 1/2, 3/4, FULL).
    Retorna (visiveis: list[str], tamanhos: dict[str,str]) - quem chama
    grava em prefs['paineis_visiveis'][aba_id] e
    prefs['tamanho_paineis'][aba_id] ao salvar o formulário."""
    _injetar_css()
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin:0.5rem 0 0.2rem 0;'>LAYOUT — {aba_rotulo}"
        f" (visibilidade e largura de cada painel)</div>",
        unsafe_allow_html=True,
    )
    mapa_id_rotulo = {pid: rotulo for pid, rotulo, _ in registro}

    visiveis, tamanhos = [], {}
    for pid in ordem_efetiva(aba_id, registro, prefs):
        rotulo = mapa_id_rotulo[pid]
        col_check, col_tam = st.columns([2, 3], vertical_alignment="center")
        with col_check:
            marcado = st.checkbox(
                rotulo, value=_pid_visivel_salvo(aba_id, pid, prefs),
                key=f"layout_visivel_{aba_id}_{pid}",
            )
        with col_tam:
            padrao_tamanho = _tamanho_efetivo(aba_id, pid, prefs)
            escolha = st.pills(
                "Tamanho", TAMANHOS, default=padrao_tamanho, selection_mode="single",
                label_visibility="collapsed", key=f"layout_tamanho_{aba_id}_{pid}",
            ) or padrao_tamanho
        if marcado:
            visiveis.append(pid)
        tamanhos[pid] = escolha

    return visiveis, tamanhos
