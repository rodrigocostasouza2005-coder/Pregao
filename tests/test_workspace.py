# -*- coding: utf-8 -*-
"""Cobertura de ui/workspace.py (ate' 2026-10-18 esse modulo nao tinha
NENHUM teste automatizado - auditoria 360, docs/auditoria-redesign-360.md,
achado P2: "ui/workspace.py sem teste automatizado" - validado so'
manualmente em producao, com harness Playwright dedicado de sessoes
anteriores - ver PROGRESSO.md). Cobre so' a logica PURA (sem JS/DOM/
browser): layout_efetivo/_layout_valido (calculo de posicao/tamanho
padrao e normalizacao de dado salvo) e _aplicar_bridge (parse + validacao
do JSON que o JS do workspace manda de volta pro Python, "entrada nao
confiavel" por design - ver docstring da propria funcao).

Isso e' so' metade da superficie (o script JS continua sem cobertura
automatizada - precisaria de um harness Playwright, nao pytest), mas
cobre exatamente as garantias de robustez que o proprio codigo documenta
e que nunca tinham sido comprovadas por teste: dado salvo corrompido
nunca quebra a tela, sempre e' clampado pros limites atuais."""
import json
import math

import ui.workspace as workspace_mod

_REGISTRO = [("p1", "Painel 1", lambda: None), ("p2", "Painel 2", lambda: None)]


def _prefs(layout_salvo=None):
    return {"layout_paineis_livre": ({"ABA": layout_salvo} if layout_salvo else {}), "ordem_paineis": {}}


# ============================================================
# _layout_valido
# ============================================================

def test_layout_valido_aceita_dict_com_xywh_numerico():
    assert workspace_mod._layout_valido({"x": 0, "y": 0.5, "w": 100, "h": 18.0}) is True


def test_layout_valido_rejeita_nao_dict():
    assert workspace_mod._layout_valido(None) is False
    assert workspace_mod._layout_valido([1, 2, 3]) is False
    assert workspace_mod._layout_valido("x=1") is False


def test_layout_valido_rejeita_campo_faltando_ou_nao_numerico():
    assert workspace_mod._layout_valido({"x": 0, "y": 0, "w": 100}) is False  # falta "h"
    assert workspace_mod._layout_valido({"x": "0", "y": 0, "w": 100, "h": 18}) is False  # "x" string


# ============================================================
# layout_efetivo
# ============================================================

def test_layout_efetivo_sem_dado_salvo_empilha_na_ordem_com_altura_padrao():
    layout = workspace_mod.layout_efetivo("ABA", _REGISTRO, _prefs())
    assert layout["p1"] == {"x": 0.0, "y": 0.0, "w": 100.0, "h": workspace_mod._ALTURA_PADRAO_REM}
    # p2 comeca onde p1 termina + espaco entre paineis
    y_esperado_p2 = workspace_mod._ALTURA_PADRAO_REM + workspace_mod._ESPACO_ENTRE_PADRAO_REM
    assert layout["p2"]["y"] == y_esperado_p2
    assert layout["p2"]["x"] == 0.0 and layout["p2"]["w"] == 100.0


def test_layout_efetivo_respeita_altura_padrao_customizada_por_painel():
    layout = workspace_mod.layout_efetivo("ABA", _REGISTRO, _prefs(), alturas_padrao={"p1": 30.0})
    assert layout["p1"]["h"] == 30.0
    assert layout["p2"]["y"] == 30.0 + workspace_mod._ESPACO_ENTRE_PADRAO_REM


def test_layout_efetivo_usa_dado_salvo_valido_sem_alterar():
    salvo = {"p1": {"x": 10.0, "y": 5.0, "w": 50.0, "h": 20.0}}
    layout = workspace_mod.layout_efetivo("ABA", _REGISTRO, _prefs(salvo))
    assert layout["p1"] == {"x": 10.0, "y": 5.0, "w": 50.0, "h": 20.0}


def test_layout_efetivo_clampa_dado_salvo_corrompido_nunca_quebra():
    """Achado real documentado no proprio codigo (ui/workspace.py:184-189,
    layout_efetivo): layout salvo com largura/altura fora dos limites
    ATUAIS da aba (ex: versao antiga do app com minimos diferentes, ou
    valor manipulado) precisa ser normalizado NA LEITURA, nao so' no
    proximo resize manual - nunca testado ate' esta sessao."""
    salvo = {
        "p1": {"x": -999.0, "y": -50.0, "w": 500.0, "h": -10.0},  # tudo fora dos limites
    }
    layout = workspace_mod.layout_efetivo("ABA", _REGISTRO, _prefs(salvo))
    d = layout["p1"]
    assert d["w"] == 100.0, "largura clampada no maximo (100%)"
    assert d["h"] == workspace_mod._ALTURA_MINIMA_REM, "altura clampada no minimo"
    assert d["x"] == 0.0, "x clampado pra nao estourar a largura (100 - w = 0)"
    assert d["y"] == 0.0, "y negativo vira 0 (nunca sobe acima do topo do workspace)"


def test_layout_efetivo_dado_salvo_invalido_cai_pro_padrao_empilhado():
    """Campo faltando/nao-numerico (_layout_valido=False) - nunca tenta
    usar o dado quebrado, cai pro mesmo caminho de 'nunca configurado'."""
    salvo = {"p1": {"x": 0, "y": 0, "w": "muito"}}  # "h" falta, "w" nao numerico
    layout = workspace_mod.layout_efetivo("ABA", _REGISTRO, _prefs(salvo))
    assert layout["p1"] == {"x": 0.0, "y": 0.0, "w": 100.0, "h": workspace_mod._ALTURA_PADRAO_REM}


# ============================================================
# _aplicar_bridge
# ============================================================

def _rodar_bridge(valor_bruto, ids_validos=("p1", "p2"), prefs=None, persistir_fn=None):
    prefs = prefs if prefs is not None else {}
    chamadas_persistir = []
    fn = persistir_fn or (lambda: chamadas_persistir.append(1))
    workspace_mod.st.session_state[workspace_mod._bridge_key("ABA")] = valor_bruto
    workspace_mod._aplicar_bridge("ABA", list(ids_validos), prefs, fn)
    return prefs, chamadas_persistir


def test_bridge_valor_vazio_nao_faz_nada():
    prefs, chamadas = _rodar_bridge("")
    assert prefs == {}
    assert chamadas == []


def test_bridge_json_invalido_nao_quebra_e_nao_altera_prefs():
    prefs, chamadas = _rodar_bridge("{nao e json valido")
    assert "layout_paineis_livre" not in prefs
    assert chamadas == []


def test_bridge_json_valido_mas_nao_e_dict_e_ignorado():
    prefs, chamadas = _rodar_bridge(json.dumps([1, 2, 3]))
    assert "layout_paineis_livre" not in prefs
    assert chamadas == []


def test_bridge_filtra_pid_que_nao_esta_nos_ids_validos():
    bruto = json.dumps({"p1": {"x": 0, "y": 0, "w": 50, "h": 10}, "fantasma": {"x": 0, "y": 0, "w": 50, "h": 10}})
    prefs, chamadas = _rodar_bridge(bruto, ids_validos=("p1",))
    salvo = prefs["layout_paineis_livre"]["ABA"]
    assert set(salvo.keys()) == {"p1"}
    assert chamadas == [1]


def test_bridge_rejeita_valores_infinitos_ou_nan():
    """Achado real documentado no proprio codigo (ui/workspace.py:244-250):
    min/max podem transformar Infinity num limite aparentemente valido
    (ex: min(100, Infinity) = 100) se nao checar isfinite ANTES de
    clampar - nunca testado ate' esta sessao."""
    bruto = json.dumps({
        "p1": {"x": 0, "y": 0, "w": "Infinity", "h": 10},
        "p2": {"x": 0, "y": 0, "w": 50, "h": 10},
    })
    prefs, chamadas = _rodar_bridge(bruto)
    salvo = prefs.get("layout_paineis_livre", {}).get("ABA", {})
    assert "p1" not in salvo, "largura infinita descartada, nunca vira 100% silenciosamente"
    assert salvo.get("p2") == {"x": 0.0, "y": 0.0, "w": 50.0, "h": 10.0}


def test_bridge_clampa_valores_finitos_fora_dos_limites():
    bruto = json.dumps({"p1": {"x": -999, "y": -1, "w": 9999, "h": -5}})
    prefs, chamadas = _rodar_bridge(bruto)
    salvo = prefs["layout_paineis_livre"]["ABA"]["p1"]
    assert salvo["w"] == 100.0
    assert salvo["h"] == workspace_mod._ALTURA_MINIMA_REM
    assert salvo["x"] == 0.0
    assert salvo["y"] == 0.0


def test_bridge_nenhum_pid_valido_nao_toca_prefs_nem_persiste():
    bruto = json.dumps({"fantasma": {"x": 0, "y": 0, "w": 50, "h": 10}})
    prefs, chamadas = _rodar_bridge(bruto, ids_validos=("p1", "p2"))
    assert "layout_paineis_livre" not in prefs
    assert chamadas == []


def test_bridge_preserva_layout_de_outras_abas_ja_salvo():
    prefs = {"layout_paineis_livre": {"OUTRA_ABA": {"px": {"x": 1, "y": 1, "w": 1, "h": 1}}}}
    bruto = json.dumps({"p1": {"x": 0, "y": 0, "w": 50, "h": 10}})
    prefs, chamadas = _rodar_bridge(bruto, prefs=prefs)
    assert "OUTRA_ABA" in prefs["layout_paineis_livre"]
    assert "ABA" in prefs["layout_paineis_livre"]
    assert chamadas == [1]
