# -*- coding: utf-8 -*-
"""Workspace modular (MVP, 2026-10-01): painéis com posição e tamanho
LIVRES (arrastar/redimensionar com o mouse), sem lista fechada de
tamanhos (nada de 1/4, 1/2, 3/4, FULL - ver ui/paineis.py pro sistema
antigo, que continua valendo pras abas que ainda não migraram).

Arquitetura (Workspace -> Layout Manager -> Panel Container -> Panel
Content), decidida numa auditoria prévia com o Rodrigo antes de
implementar:

- O CONTEÚDO de cada painel (render_fn do REGISTRO_PAINEIS da aba) não
  muda NADA - não sabe e não precisa saber onde está, qual tamanho tem
  ou como foi arrastado. Só layout_efetivo/renderizar_workspace cuidam
  disso.
- Streamlit não tem drag/resize nativo, e o projeto decidiu não migrar
  pra nenhuma biblioteca de grid de terceiros (ex: streamlit-elements):
  o conteúdo dentro de um grid desses precisaria ser reescrito na árvore
  de elementos DELA (MUI/Nivo/etc.), não os st.plotly_chart/tabelas HTML
  que este app já usa - risco e esforço grandes demais, e violaria
  "mesmo conteúdo, novo sistema de layout". Em vez disso, Python continua
  renderizando os painéis exatamente como sempre (st.container(border=True,
  key=f"painel-outer-{aba_id}-{pid}"), mesmo padrão de ui/paineis.py) e
  so' adicionamos: (1) uma camada de CSS que posiciona cada painel de
  forma absoluta dentro de um workspace, calculada a partir da MESMA
  posição/tamanho salvos; (2) um script (via st.components.v1.html,
  SEM nenhuma lib JS nova) que manipula esses elementos reais (acessados
  via window.parent.document - mesma origem, mesma técnica que o CSS do
  projeto já depende implicitamente pra funcionar) pra permitir arrastar/
  redimensionar, e manda o resultado final de volta pro Python por uma
  ponte: um st.text_input oculto cujo valor é setado via JS (native
  setter + dispatchEvent) - truque padrão da comunidade Streamlit pra
  mandar dado de JS pro Python SEM precisar construir um componente
  bidirecional de verdade (sem build step, sem npm, sem pacote novo).

Unidades de posição/tamanho (decisão explicada ao Rodrigo antes de
implementar): x/w em PORCENTAGEM da largura do workspace (responsivo a
redimensionar a janela/sidebar - a mesma % sempre ocupa a fração certa
da tela, em qualquer resolução); y/h em REM (ritmo vertical consistente
com o resto do app, que já é inteiramente dimensionado em rem/variáveis
de densidade - não faz sentido a altura escalar com a LARGURA da janela,
só a altura de FONTE do usuário, que rem já acompanha).

Performance: a ponte só escreve (e só persiste no Supabase) QUANDO o
usuário SOLTA o mouse (fim do drag/resize) - durante o gesto, tudo é
local (JS muda o style inline do elemento direto, sem nenhum round-trip
com o Python)."""

import json

import streamlit as st

from ui.paineis import _esconder_painel, _pid_visivel_salvo, ordem_efetiva

_LARGURA_PADRAO_PCT = 100.0
_ALTURA_PADRAO_REM = 18.0
_LARGURA_MINIMA_PCT = 20.0
_ALTURA_MINIMA_REM = 8.0
_ESPACO_ENTRE_PADRAO_REM = 1.0

_CSS_BASE = """
/* popover "⚙" no canto do painel - mesmo visual de ui/paineis.py
   (duplicado aqui de propósito: conteúdo diferente - sem TAMANHO
   pré-definido, só RESTAURAR/OCULTAR - mas a mesma linguagem visual) */
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

/* header do painel = área de arrastar (pedido explícito: conteúdo
   continua 100% clicável/selecionável, só o título vira "pega") */
[class*="st-key-workspace_livre_"] .painel-titulo { cursor: grab; }
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"] {
    touch-action: none;
}
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"].workspace-arrastando {
    user-select: none;
    border-color: var(--destaque) !important;
}
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"].workspace-arrastando .painel-titulo {
    cursor: grabbing;
}

/* handle de resize: praticamente invisível parado, so' um cantinho
   sutil que acende no hover - decorativo (::after, nunca um nó de DOM
   novo - evita mexer na árvore que o React do Streamlit controla) */
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"] {
    position: relative; /* garante containing block mesmo antes do CSS por-painel carregar */
}
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"]::after {
    content: "";
    position: absolute; right: 2px; bottom: 2px; width: 9px; height: 9px;
    border-right: 2px solid var(--borda); border-bottom: 2px solid var(--borda);
    opacity: 0.35; pointer-events: none;
}
[class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"]:hover::after {
    border-color: var(--destaque); opacity: 0.8;
}

/* ponte oculta (st.text_input que o JS escreve pra mandar o layout novo
   pro Python) - fora da tela, nunca visível, mas presente no DOM/React */
div[class*="st-key-workspace_bridge_wrap_"] {
    position: fixed !important; top: -9999px !important; left: -9999px !important;
    width: 1px !important; height: 1px !important; overflow: hidden !important;
}

/* telas estreitas: workspace livre nao e' viavel (drag/resize exige
   espaco de verdade) - cai pra empilhado vertical, 1 coluna, largura
   total - mesmo principio do fallback mobile do header (ver style.css) */
@media (max-width: 640px) {
    [class*="st-key-workspace_livre_"] { min-height: 0 !important; }
    [class*="st-key-workspace_livre_"] [class*="st-key-painel-outer-"] {
        position: static !important;
        width: 100% !important;
        height: auto !important;
        left: auto !important;
        top: auto !important;
        margin-bottom: 0.6rem !important;
    }
}
"""


def _injetar_css_base():
    st.markdown(f"<style>{_CSS_BASE}</style>", unsafe_allow_html=True)


def _bridge_key(aba_id: str) -> str:
    return f"workspace_bridge_{aba_id}"


def _layout_valido(dados) -> bool:
    if not isinstance(dados, dict):
        return False
    return all(k in dados and isinstance(dados[k], (int, float)) for k in ("x", "y", "w", "h"))


def layout_efetivo(aba_id: str, registro: list, prefs: dict) -> dict:
    """pid -> {"x":pct, "y":rem, "w":pct, "h":rem}. Lê prefs["layout_paineis_livre"][aba_id];
    qualquer painel sem posição salva (primeira vez, ou painel novo no
    registro) recebe um layout padrão empilhado (1 coluna, largura
    total) calculado pela ORDEM dele no registro - nunca colide com
    painel vizinho, mesmo misturando painéis já personalizados com
    painéis ainda no padrão."""
    salvo = (prefs.get("layout_paineis_livre") or {}).get(aba_id, {})
    ordem = ordem_efetiva(aba_id, registro, prefs)
    layout = {}
    for indice, pid in enumerate(ordem):
        dados_salvos = salvo.get(pid)
        if _layout_valido(dados_salvos):
            layout[pid] = {k: float(dados_salvos[k]) for k in ("x", "y", "w", "h")}
        else:
            layout[pid] = {
                "x": 0.0,
                "y": indice * (_ALTURA_PADRAO_REM + _ESPACO_ENTRE_PADRAO_REM),
                "w": _LARGURA_PADRAO_PCT,
                "h": _ALTURA_PADRAO_REM,
            }
    return layout


def _gerar_css(aba_id: str, layout: dict, visiveis: set) -> str:
    alturas = [d["y"] + d["h"] for pid, d in layout.items() if pid in visiveis]
    altura_total = (max(alturas) if alturas else _ALTURA_PADRAO_REM) + 2.0
    regras = [
        f'div[class*="st-key-workspace_livre_{aba_id}"] {{ '
        f"position: relative; width: 100%; min-height: {altura_total:.2f}rem; }}"
    ]
    for pid, d in layout.items():
        if pid not in visiveis:
            continue
        regras.append(
            f'div[class*="st-key-painel-outer-{aba_id}-{pid}"] {{ '
            f'position: absolute; left: {d["x"]:.3f}%; top: {d["y"]:.3f}rem; '
            f'width: {d["w"]:.3f}%; height: {d["h"]:.3f}rem; '
            f"box-sizing: border-box; overflow: auto; margin: 0 !important; }}"
        )
    return "\n".join(regras)


def _aplicar_bridge(aba_id: str, ids_validos: list, prefs: dict, persistir_fn):
    """on_change do text_input oculto - roda ANTES do rerun principal.
    Nunca derruba a tela se o JSON vier inválido/incompleto (campo
    manipulado por JS de fora do controle normal do Streamlit - trata
    como entrada não confiável, valida tudo)."""
    bruto = st.session_state.get(_bridge_key(aba_id), "")
    if not bruto:
        return
    try:
        novo = json.loads(bruto)
    except (ValueError, TypeError):
        return
    if not isinstance(novo, dict):
        return

    limpo = {}
    for pid, dados in novo.items():
        if pid not in ids_validos or not isinstance(dados, dict):
            continue
        try:
            x = max(0.0, min(100.0, float(dados["x"])))
            y = max(0.0, float(dados["y"]))
            w = max(_LARGURA_MINIMA_PCT, min(100.0, float(dados["w"])))
            h = max(_ALTURA_MINIMA_REM, float(dados["h"]))
        except (KeyError, TypeError, ValueError):
            continue
        limpo[pid] = {"x": x, "y": y, "w": w, "h": h}

    if not limpo:
        return

    tabela = dict(prefs.get("layout_paineis_livre") or {})
    tabela[aba_id] = limpo
    prefs["layout_paineis_livre"] = tabela
    if persistir_fn:
        persistir_fn()


def _restaurar_layout_aba(aba_id: str, prefs: dict, persistir_fn):
    tabela = dict(prefs.get("layout_paineis_livre") or {})
    tabela.pop(aba_id, None)
    prefs["layout_paineis_livre"] = tabela
    if persistir_fn:
        persistir_fn()


def _restaurar_layout_painel(aba_id: str, pid: str, prefs: dict, persistir_fn):
    tabela = dict(prefs.get("layout_paineis_livre") or {})
    tabela_aba = dict(tabela.get(aba_id, {}))
    tabela_aba.pop(pid, None)
    tabela[aba_id] = tabela_aba
    prefs["layout_paineis_livre"] = tabela
    if persistir_fn:
        persistir_fn()


def _controle_rapido_workspace(aba_id: str, pid: str, registro: list, prefs: dict, persistir_fn):
    """Popover "⚙" no canto do painel: restaurar (só este painel, volta
    pro layout padrão empilhado) e ocultar (reusa ui/paineis.py -
    _esconder_painel, mesma estrutura de dados/prefs do sistema antigo,
    reexibir continua sendo em CONFIG, igual já funciona hoje)."""
    chave_wrap = f"painel-ctrl-{aba_id}-{pid}"
    with st.container(key=chave_wrap):
        with st.popover("⚙", use_container_width=False):
            if st.button("RESTAURAR TAMANHO/POSIÇÃO", key=f"{chave_wrap}-restaurar", width="stretch"):
                _restaurar_layout_painel(aba_id, pid, prefs, persistir_fn)
                st.rerun()
            if st.button("OCULTAR ESTE PAINEL", key=f"{chave_wrap}-ocultar", width="stretch"):
                _esconder_painel(aba_id, pid, registro, prefs, persistir_fn)
                st.rerun()
            st.caption("Pra reexibir depois: CONFIG → LAYOUT.")


def _script_js(aba_id: str, ordem: list, layout: dict) -> str:
    """Script injetado 1x por render (via st.components.v1.html) que da'
    vida ao drag/resize. Não cria NENHUM nó de DOM novo dentro da árvore
    que o React do Streamlit controla (só escuta eventos nos elementos
    que o próprio Streamlit já renderizou) - evita o erro clássico de
    "remover filho que o React não esperava" que acontece quando script
    externo insere elementos dentro de um container React administra.

    Limitação conhecida (documentada, aceitável pro MVP): se o Streamlit
    recriar este iframe (em vez de reaproveitar) entre reruns, os
    listeners anexados pela instância anterior podem ficar "mortos"
    (realm do iframe anterior destruído) - na prática, listeners novos
    de cada montagem continuam funcionando normalmente (múltiplos
    listeners no mesmo evento não se atrapalham; um morto no máximo gera
    um erro silencioso no console, não quebra o gesto atual)."""
    payload_layout = json.dumps(layout)
    payload_paineis = json.dumps(ordem)
    bridge_classe = f"st-key-workspace_bridge_wrap_{aba_id}"
    workspace_classe = f"st-key-workspace_livre_{aba_id}"

    return f"""
<script>
(function() {{
    const ABA_ID = {json.dumps(aba_id)};
    const PAINEIS = {payload_paineis};
    const BRIDGE_CLASSE = {json.dumps(bridge_classe)};
    const WORKSPACE_CLASSE = {json.dumps(workspace_classe)};
    const MIN_W_PCT = {_LARGURA_MINIMA_PCT};
    const MIN_H_REM = {_ALTURA_MINIMA_REM};
    const RESIZE_MARGEM_PX = 10;
    const doc = window.parent.document;

    function remPx() {{
        return parseFloat(window.parent.getComputedStyle(doc.documentElement).fontSize) || 16;
    }}
    function getEl(pid) {{
        return doc.querySelector('[class*="st-key-painel-outer-' + ABA_ID + '-' + pid + '"]');
    }}
    function getWorkspaceEl() {{
        return doc.querySelector('[class*="' + WORKSPACE_CLASSE + '"]');
    }}
    function getBridgeInput() {{
        const wrap = doc.querySelector('[class*="' + BRIDGE_CLASSE + '"]');
        return wrap ? wrap.querySelector('input') : null;
    }}
    function enviarLayout(layoutAtual) {{
        const input = getBridgeInput();
        if (!input) return;
        const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
        setter.call(input, JSON.stringify(layoutAtual));
        input.dispatchEvent(new Event('input', {{bubbles: true}}));
    }}

    let layoutAtual = JSON.parse({json.dumps(payload_layout)});
    let gesto = null;

    function detectarModo(el, evt) {{
        const rect = el.getBoundingClientRect();
        const pertoDireita = evt.clientX >= rect.right - RESIZE_MARGEM_PX;
        const pertoBaixo = evt.clientY >= rect.bottom - RESIZE_MARGEM_PX;
        if (pertoDireita && pertoBaixo) return 'resize-xy';
        if (pertoDireita) return 'resize-x';
        if (pertoBaixo) return 'resize-y';
        return null;
    }}

    function iniciarGesto(pid, modo, evt) {{
        const el = getEl(pid);
        const ws = getWorkspaceEl();
        if (!el || !ws) return;
        const rectEl = el.getBoundingClientRect();
        const rectWs = ws.getBoundingClientRect();
        gesto = {{
            pid: pid, modo: modo,
            startClientX: evt.clientX, startClientY: evt.clientY,
            startLeftPx: rectEl.left - rectWs.left,
            startTopPx: rectEl.top - rectWs.top,
            startWidthPx: rectEl.width, startHeightPx: rectEl.height,
            workspaceWidthPx: rectWs.width,
        }};
        el.classList.add('workspace-arrastando');
        el.style.zIndex = 50;
        try {{ el.setPointerCapture(evt.pointerId); }} catch (e) {{}}
    }}

    function aplicarGesto(evt) {{
        if (!gesto) return;
        const el = getEl(gesto.pid);
        if (!el) return;
        const dx = evt.clientX - gesto.startClientX;
        const dy = evt.clientY - gesto.startClientY;
        const px = remPx();
        const wsWidthPx = gesto.workspaceWidthPx;

        if (gesto.modo === 'drag') {{
            let novoLeftPx = Math.max(0, Math.min(gesto.startLeftPx + dx, wsWidthPx - gesto.startWidthPx));
            let novoTopPx = Math.max(0, gesto.startTopPx + dy);
            el.style.left = (novoLeftPx / wsWidthPx * 100).toFixed(3) + '%';
            el.style.top = (novoTopPx / px).toFixed(3) + 'rem';
        }} else {{
            if (gesto.modo === 'resize-x' || gesto.modo === 'resize-xy') {{
                let novaLarguraPx = Math.max(gesto.startWidthPx + dx, MIN_W_PCT / 100 * wsWidthPx);
                novaLarguraPx = Math.min(novaLarguraPx, wsWidthPx - gesto.startLeftPx);
                el.style.width = (novaLarguraPx / wsWidthPx * 100).toFixed(3) + '%';
            }}
            if (gesto.modo === 'resize-y' || gesto.modo === 'resize-xy') {{
                let novaAlturaPx = Math.max(gesto.startHeightPx + dy, MIN_H_REM * px);
                el.style.height = (novaAlturaPx / px).toFixed(3) + 'rem';
            }}
        }}
    }}

    function finalizarGesto() {{
        if (!gesto) return;
        const pid = gesto.pid;
        const el = getEl(pid);
        if (el) {{
            el.classList.remove('workspace-arrastando');
            el.style.zIndex = '';
            const ws = getWorkspaceEl();
            if (ws) {{
                const rectEl = el.getBoundingClientRect();
                const rectWs = ws.getBoundingClientRect();
                const px = remPx();
                layoutAtual[pid] = {{
                    x: (rectEl.left - rectWs.left) / rectWs.width * 100,
                    y: (rectEl.top - rectWs.top) / px,
                    w: rectEl.width / rectWs.width * 100,
                    h: rectEl.height / px,
                }};
                enviarLayout(layoutAtual);
            }}
        }}
        gesto = null;
    }}

    function ligarPainel(pid) {{
        const el = getEl(pid);
        if (!el || el.dataset.workspaceLigado === '1') return;
        el.dataset.workspaceLigado = '1';
        el.style.left = ''; el.style.top = ''; el.style.width = ''; el.style.height = '';

        el.addEventListener('pointerdown', function (evt) {{
            const titulo = evt.target.closest('.painel-titulo');
            let modo = null;
            if (titulo && el.contains(titulo)) {{
                modo = 'drag';
            }} else {{
                modo = detectarModo(el, evt);
            }}
            if (!modo) return;
            evt.preventDefault();
            iniciarGesto(pid, modo, evt);
        }});

        el.addEventListener('pointermove', function (evt) {{
            if (gesto && gesto.pid === pid) {{
                aplicarGesto(evt);
            }} else if (!gesto) {{
                const modo = detectarModo(el, evt);
                el.style.cursor = modo === 'resize-xy' ? 'nwse-resize'
                    : modo === 'resize-x' ? 'ew-resize'
                    : modo === 'resize-y' ? 'ns-resize' : '';
            }}
        }});

        el.addEventListener('pointerup', function (evt) {{
            if (gesto && gesto.pid === pid) finalizarGesto();
        }});
        el.addEventListener('pointercancel', function (evt) {{
            if (gesto && gesto.pid === pid) finalizarGesto();
        }});
    }}

    function ligarTodos() {{
        PAINEIS.forEach(ligarPainel);
    }}

    ligarTodos();

    const ws = getWorkspaceEl();
    if (ws) {{
        new MutationObserver(ligarTodos).observe(ws, {{childList: true, subtree: true}});
    }}
}})();
</script>
"""


def renderizar_workspace(aba_id: str, registro: list, prefs: dict, *args, persistir_fn=None, **kwargs):
    """Ponto de entrada do workspace modular (equivalente a
    ui/paineis.py:renderizar, mesma assinatura/convenção de args/kwargs
    repassados a cada render_fn) - posição/tamanho livres em vez de
    frações fixas. Hoje só MERCADO usa isso (ETAPA 1/MVP); as outras
    abas que adotam REGISTRO_PAINEIS continuam no ui/paineis.py antigo
    até a ETAPA 2 (expansão, só depois de validado)."""
    _injetar_css_base()
    ids_validos = [pid for pid, _, _ in registro]
    mapa = {pid: fn for pid, _, fn in registro}
    ordem = [pid for pid in ordem_efetiva(aba_id, registro, prefs) if _pid_visivel_salvo(aba_id, pid, prefs)]

    if not ordem:
        st.info("Nenhum painel visível nesta aba — ajuste em CONFIG, seção LAYOUT.")
        return

    col_aviso, col_restaurar = st.columns([5, 1.3])
    with col_aviso:
        st.markdown(
            "<div class='cinza' style='font-size:0.65rem; padding-top:0.4rem;'>"
            "Arraste pelo título pra mover · arraste a borda/canto inferior-direito pra redimensionar</div>",
            unsafe_allow_html=True,
        )
    with col_restaurar:
        if st.button("↺ RESTAURAR LAYOUT", key=f"restaurar_layout_{aba_id}", width="stretch"):
            _restaurar_layout_aba(aba_id, prefs, persistir_fn)
            st.rerun()

    bridge_key = _bridge_key(aba_id)
    with st.container(key=f"workspace_bridge_wrap_{aba_id}"):
        st.text_input(
            "workspace_bridge", key=bridge_key, label_visibility="collapsed",
            on_change=_aplicar_bridge, args=(aba_id, ids_validos, prefs, persistir_fn),
        )

    layout = layout_efetivo(aba_id, registro, prefs)
    st.markdown(f"<style>{_gerar_css(aba_id, layout, set(ordem))}</style>", unsafe_allow_html=True)

    with st.container(key=f"workspace_livre_{aba_id}"):
        for pid in ordem:
            with st.container(border=True, key=f"painel-outer-{aba_id}-{pid}"):
                _controle_rapido_workspace(aba_id, pid, registro, prefs, persistir_fn)
                mapa[pid](*args, **kwargs)

    # height=1: st.iframe não aceita 0 (exige positivo/"stretch"/"content");
    # o iframe só carrega o <script>, não tem conteúdo visível de verdade.
    st.iframe(_script_js(aba_id, ordem, layout), height=1)
