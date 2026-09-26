# -*- coding: utf-8 -*-
"""Sistema de "painéis registrados": abas que adotam isso declaram uma
lista de (id, rótulo, função_render) na ordem padrão; o usuário pode
REORDENAR (via CONFIG), esconder (via CONFIG - é a forma de RESTAURAR
um painel escondido, já que um painel escondido não tem cabeçalho pra
clicar em lugar nenhum) e escolher a LARGURA de cada painel DIRETO NA
ABA, num popover "⚙" no canto do próprio painel (pedido explícito do
Rodrigo, 2026-09-26: "queria escolher na aba mesmo" - a primeira versão
desta ETAPA 7 só deixava escolher tamanho dentro do formulário de
CONFIG, longe do painel que estava sendo redimensionado, sem feedback
visual imediato). Tudo persistido em
prefs["ordem_paineis"]/["paineis_visiveis"]/["tamanho_paineis"],
chaveado por aba_id - reaproveita a tabela user_prefs que já existe,
sem tabela nova no Supabase.

Não é redimensionamento livre com o mouse: Streamlit não tem componente
nativo de drag-resize, e o projeto não usa nenhum componente de
terceiros em lugar nenhum hoje - um componente desses seria uma
dependência nova e mais pesada de manter. Larguras fixas (1/4, 1/2, 3/4,
FULL) cobrem o pedido comum ("quero X e Y lado a lado, menores") usando
só `st.columns()`, sem HTML/JS customizado. Os painéis de uma linha são
empacotados na ordem escolhida: cada um entra na linha atual até a soma
das larguras estourar 1.0, aí uma linha nova começa - um painel FULL
(1.0) sempre fica sozinho na própria linha.

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

/* popover de controle rapido (tamanho/esconder) no canto do painel -
   o container externo (com key) precisa de position:relative pra virar
   a referencia do position:absolute do popover */
div[class*="st-key-painel-outer-"] { position: relative; }
div[class*="st-key-painel-ctrl-"] {
    position: absolute; top: 0.4rem; right: 0.6rem; z-index: 20; width: auto;
}
div[class*="st-key-painel-ctrl-"] button {
    background-color: transparent !important; border: 1px solid var(--borda) !important;
    color: var(--cinza) !important; font-size: 0.68rem !important;
    padding: 0.05rem 0.4rem !important; min-height: 22px !important;
    border-radius: 2px !important; box-shadow: none !important;
}
div[class*="st-key-painel-ctrl-"] button:hover { border-color: var(--destaque) !important; color: var(--destaque) !important; }
div[class*="st-key-painel-popover-"] button[disabled] {
    background-color: var(--destaque) !important; color: #000000 !important;
    border-color: var(--destaque) !important; opacity: 1 !important; font-weight: 700 !important;
}
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


def _salvar_tamanho(aba_id: str, pid: str, tamanho: str, prefs: dict, persistir_fn):
    """Muta prefs em memoria (efeito imediato na mesma sessao - toda
    render_fn le' prefs pela mesma referencia) e persiste de verdade se
    um persistir_fn foi passado (ver renderizar())."""
    tabela = dict(prefs.get("tamanho_paineis") or {})
    tabela[aba_id] = {**tabela.get(aba_id, {}), pid: tamanho}
    prefs["tamanho_paineis"] = tabela
    if persistir_fn:
        persistir_fn()


def _esconder_painel(aba_id: str, pid: str, registro: list, prefs: dict, persistir_fn):
    ids_registro = [p for p, _, _ in registro]
    visiveis_atuais = [p for p in ids_registro if _pid_visivel_salvo(aba_id, p, prefs) and p != pid]
    tabela = dict(prefs.get("paineis_visiveis") or {})
    tabela[aba_id] = visiveis_atuais
    prefs["paineis_visiveis"] = tabela
    if persistir_fn:
        persistir_fn()


def _controle_rapido_painel(aba_id: str, pid: str, registro: list, prefs: dict, persistir_fn):
    """Popover "⚙" no canto do painel (posicionado via CSS - ver
    _CSS_PAINEIS) com tamanho (efeito imediato, sem formulário) e um
    atalho pra esconder o painel. Reexibir um painel escondido continua
    sendo em CONFIG (não tem cabeçalho pra clicar num painel que não
    está sendo renderizado)."""
    chave_wrap = f"painel-ctrl-{aba_id}-{pid}"
    tamanho_atual = _tamanho_efetivo(aba_id, pid, prefs)
    with st.container(key=chave_wrap):
        with st.popover("⚙", use_container_width=False):
            st.markdown(
                "<div class='cinza' style='font-size:0.65rem; margin-bottom:0.3rem;'>TAMANHO</div>",
                unsafe_allow_html=True,
            )
            with st.container(key=f"painel-popover-{aba_id}-{pid}"):
                cols = st.columns(len(TAMANHOS), gap="small")
                for i, tamanho in enumerate(TAMANHOS):
                    with cols[i]:
                        if st.button(
                            tamanho, key=f"{chave_wrap}-tam-{tamanho}",
                            disabled=(tamanho == tamanho_atual), width="stretch",
                        ):
                            _salvar_tamanho(aba_id, pid, tamanho, prefs, persistir_fn)
                            st.rerun()
            st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
            if st.button("ESCONDER ESTE PAINEL", key=f"{chave_wrap}-esconder", width="stretch"):
                _esconder_painel(aba_id, pid, registro, prefs, persistir_fn)
                st.rerun()
            st.caption("Pra reexibir depois: CONFIG → LAYOUT.")


def renderizar(aba_id: str, registro: list, prefs: dict, *args, persistir_fn=None, **kwargs):
    """Renderiza cada painel visível do registro, na ordem efetiva,
    empacotados em linhas conforme a largura configurada de cada um
    (ver _empacotar_linhas), cada um com um popover "⚙" no canto pra
    ajustar tamanho/visibilidade sem sair da aba. `persistir_fn`
    (opcional, ex: app.py:_persistir_prefs) é chamado sempre que o
    popover muda algo - se omitido, a mudança só vale na sessão atual
    (ainda assim com efeito imediato, já que `prefs` é mutado em
    memória). args/kwargs extras são repassados pra cada render_fn (ex:
    o ticker selecionado numa aba tipo EQUITY)."""
    _injetar_css()
    mapa = {pid: fn for pid, _, fn in registro}
    ordem = [pid for pid in ordem_efetiva(aba_id, registro, prefs) if _pid_visivel_salvo(aba_id, pid, prefs)]

    if not ordem:
        st.info("Nenhum painel visível nesta aba — ajuste em CONFIG, seção LAYOUT.")
        return

    fracoes = {pid: _FRACOES[_tamanho_efetivo(aba_id, pid, prefs)] for pid in ordem}

    def _painel(pid):
        with st.container(border=True, key=f"painel-outer-{aba_id}-{pid}"):
            _controle_rapido_painel(aba_id, pid, registro, prefs, persistir_fn)
            mapa[pid](*args, **kwargs)

    for linha in _empacotar_linhas(ordem, fracoes):
        if len(linha) == 1 and linha[0][1] == 1.0:
            _painel(linha[0][0])
            continue
        cols = st.columns([fracao for _, fracao in linha], gap="small")
        for col, (pid, _) in zip(cols, linha):
            with col:
                _painel(pid)


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


def controle_visibilidade_config(aba_id: str, aba_rotulo: str, registro: list, prefs: dict) -> list:
    """Widget pra usar dentro do formulário de CONFIG, logo após
    controle_ordem_config: um checkbox por painel (na ordem atual).
    Único jeito de REEXIBIR um painel escondido (o popover "⚙" na aba só
    esconde - um painel escondido não renderiza, então não tem
    cabeçalho/popover pra clicar). Tamanho NÃO está mais aqui - virou
    controle direto no painel (ver _controle_rapido_painel) depois do
    pedido do Rodrigo (2026-09-26) pra escolher tamanho "na aba mesmo",
    com feedback visual imediato, em vez de num formulário separado.
    Retorna a lista de ids visíveis - quem chama grava em
    prefs['paineis_visiveis'][aba_id] ao salvar o formulário."""
    st.markdown(
        f"<div class='cinza' style='font-size:0.68rem; margin:0.5rem 0 0.2rem 0;'>PAINÉIS VISÍVEIS — {aba_rotulo}"
        f" (tamanho de cada painel se ajusta direto na aba, no ⚙ do canto)</div>",
        unsafe_allow_html=True,
    )
    mapa_id_rotulo = {pid: rotulo for pid, rotulo, _ in registro}

    visiveis = []
    for pid in ordem_efetiva(aba_id, registro, prefs):
        marcado = st.checkbox(
            mapa_id_rotulo[pid], value=_pid_visivel_salvo(aba_id, pid, prefs),
            key=f"layout_visivel_{aba_id}_{pid}",
        )
        if marcado:
            visiveis.append(pid)
    return visiveis
