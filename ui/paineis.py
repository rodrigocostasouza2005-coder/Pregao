# -*- coding: utf-8 -*-
"""Sistema de "painéis registrados": abas que adotam isso declaram uma
lista de (id, rótulo, função_render) na ordem padrão; o usuário pode
REORDENAR (não arrastar/redimensionar - ver decisão registrada em
PROGRESSO.md, seção FILA2-T5) via um multiselect em CONFIG, mesmo padrão
já usado em "ABAS VISÍVEIS" (a ordem de seleção vira a ordem de
exibição). A ordem escolhida é persistida em
prefs["ordem_paineis"][aba_id] - reaproveita a tabela user_prefs que já
existe, sem tabela nova no Supabase.

Por que reordenar em vez de arrastar/redimensionar de verdade: Streamlit
não tem componente nativo de drag-and-drop, e o projeto não usa nenhum
componente de terceiros em lugar nenhum hoje - um componente desses
seria uma dependência nova e mais pesada de manter. Reordenar via
multiselect cobre o pedido mais comum ("quero ver X antes de Y") sem
esse custo. Se um dia for pra frente com arrastar/redimensionar de
verdade, esse módulo já isola a "ordem efetiva" de onde ela é usada -
trocar só a função `renderizar` por uma versão com componente de
terceiros não exige mexer nas abas que já adotaram o registro."""

import streamlit as st


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


def renderizar(aba_id: str, registro: list, prefs: dict, *args, **kwargs):
    """Renderiza cada painel do registro, na ordem efetiva (ver
    ordem_efetiva), cada um dentro do seu próprio st.container(border=True).
    args/kwargs extras são repassados pra cada render_fn (ex: o ticker
    selecionado numa aba tipo EQUITY)."""
    mapa = {pid: fn for pid, _, fn in registro}
    for pid in ordem_efetiva(aba_id, registro, prefs):
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
