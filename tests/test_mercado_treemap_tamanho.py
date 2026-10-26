# -*- coding: utf-8 -*-
"""Testes do fix de tamanho/layout do MAPA DO MERCADO (treemap,
ui/mercado_tab.py) - auditoria 2026-10-26. Causa raiz CONFIRMADA por
screenshot real via Playwright (ver docs/evidencias/heatmap-profissional-
20261026): sem `alturas_padrao` repassado pra ui/workspace.py:
renderizar_workspace, o painel "treemap" caia no `_ALTURA_PADRAO_REM`
genérico (18rem/288px) - bem menor que a altura real da figura Plotly
(420px), recortando a maior parte do mapa atrás de scroll interno
(overflow:auto da div absoluta do painel). Este arquivo cobre só a
LÓGICA (constantes consistentes entre si, wiring do alturas_padrao,
horário relativo nunca inventado, painel não quebra com dado real/
vazio) - a validação visual (tamanho de verdade, legibilidade dos
blocos, legenda) foi feita com Playwright contra o app rodando de
verdade (ver docs/evidencias/heatmap-profissional-20261026/LEIA.md),
não repetida aqui (mesma divisão já usada no resto do projeto entre
teste automatizado de lógica e evidência visual real).

st.markdown/st.plotly_chart funcionam em "bare mode" (fora de
ScriptRunContext real) sem lançar exceção - mesmo padrão dos outros
testes de UI deste projeto (ver tests/test_calendario_ui.py,
tests/test_mercado_ranking_ui.py).

Uso: python tests/test_mercado_treemap_tamanho.py (python do .venv do
projeto) ou `pytest tests/test_mercado_treemap_tamanho.py`."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.mercado_tab as mercado_tab_mod
from ui.workspace import _ALTURA_PADRAO_REM

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _papel(ticker, setor, variacao_pct, preco=10.0, volume_financeiro=1_000_000.0):
    return {"ticker": ticker, "setor": setor, "preco": preco, "variacao_pct": variacao_pct, "volume_financeiro": volume_financeiro}


def test_altura_padrao_do_treemap_e_bem_maior_que_a_generica_do_workspace():
    # regressao direta do bug: sem isso, o painel "treemap" cai no
    # _ALTURA_PADRAO_REM generico (18rem) - bem menor que a altura real
    # da figura Plotly, causando o recorte/scroll interno reportado.
    _checar(
        "'treemap' está em _ALTURAS_PADRAO_MERCADO",
        "treemap" in mercado_tab_mod._ALTURAS_PADRAO_MERCADO,
    )
    altura_treemap_rem = mercado_tab_mod._ALTURAS_PADRAO_MERCADO["treemap"]
    _checar(
        "altura padrão do treemap é bem maior que o genérico do workspace",
        altura_treemap_rem > _ALTURA_PADRAO_REM * 2,
        f"(treemap={altura_treemap_rem}rem, genérico={_ALTURA_PADRAO_REM}rem)",
    )


def test_altura_em_px_da_figura_cabe_dentro_do_container_em_rem():
    # a figura Plotly (_ALTURA_TREEMAP_PX) tem que ser MENOR que o
    # container (_ALTURA_TREEMAP_REM * 16px/rem) - sobra pro título do
    # painel, a legenda "atualizado há Xmin", a caption e a barra de
    # escala abaixo do gráfico. Se os dois voltarem a divergir, o bug
    # original (recorte via overflow:auto) volta.
    container_px = mercado_tab_mod._ALTURA_TREEMAP_REM * 16
    figura_px = mercado_tab_mod._ALTURA_TREEMAP_PX
    _checar("figura cabe dentro do container", figura_px < container_px,
            f"(figura={figura_px}px, container={container_px:.0f}px)")
    sobra_px = container_px - figura_px
    _checar("sobra chrome suficiente pro título/caption/legenda (>=80px)", sobra_px >= 80, f"(sobra={sobra_px:.0f}px)")


def test_render_mercado_repassa_alturas_padrao_pro_workspace():
    with patch.object(mercado_tab_mod, "_painel_termometro", return_value=True), \
         patch.object(mercado_tab_mod.workspace, "renderizar_workspace") as mock_ws:
        mercado_tab_mod.render_mercado(_PREFS)
    assert mock_ws.called
    _, kwargs = mock_ws.call_args
    _checar("alturas_padrao repassado é exatamente _ALTURAS_PADRAO_MERCADO",
            kwargs.get("alturas_padrao") == mercado_tab_mod._ALTURAS_PADRAO_MERCADO)


def test_tempo_relativo_sem_dado_e_explicito_nunca_inventado():
    _checar("None vira texto explícito", mercado_tab_mod._tempo_relativo(None) == "horário indisponível")


def test_tempo_relativo_recente_nao_lanca_excecao():
    agora = datetime.now(timezone.utc)
    resultado = mercado_tab_mod._tempo_relativo(agora)
    _checar("datetime recente não lança exceção e não é vazio", bool(resultado))
    _checar("datetime recente é 'agora mesmo'", resultado == "agora mesmo")


def test_tempo_relativo_minutos_atras():
    passado = datetime.now(timezone.utc) - timedelta(minutes=12)
    _checar("12min atrás formata como 'há 12min'", mercado_tab_mod._tempo_relativo(passado) == "há 12min")


def test_painel_treemap_sem_dado_nao_lanca_excecao():
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=[]):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap sem dado não lança exceção", True)


def test_painel_treemap_com_dado_real_nao_lanca_excecao_e_mostra_horario():
    papeis = [
        _papel("PETR4", "Petróleo e Gás", -2.5),
        _papel("VALE3", "Mineração e Siderurgia", 1.8),
        _papel("ITUB4", "Bancos", 0.3),
    ]
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=datetime.now(timezone.utc)):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap com dado real não lança exceção", True)


def test_painel_treemap_com_momento_indisponivel_nao_lanca_excecao():
    papeis = [_papel("PETR4", "Petróleo e Gás", -2.5)]
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=None):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap com momento indisponível não lança exceção", True)


if __name__ == "__main__":
    test_altura_padrao_do_treemap_e_bem_maior_que_a_generica_do_workspace()
    test_altura_em_px_da_figura_cabe_dentro_do_container_em_rem()
    test_render_mercado_repassa_alturas_padrao_pro_workspace()
    test_tempo_relativo_sem_dado_e_explicito_nunca_inventado()
    test_tempo_relativo_recente_nao_lanca_excecao()
    test_tempo_relativo_minutos_atras()
    test_painel_treemap_sem_dado_nao_lanca_excecao()
    test_painel_treemap_com_dado_real_nao_lanca_excecao_e_mostra_horario()
    test_painel_treemap_com_momento_indisponivel_nao_lanca_excecao()
    if _FALHAS:
        print(f"\n{len(_FALHAS)} falha(s): {_FALHAS}")
        sys.exit(1)
    print("\nTodos os testes passaram.")
