# -*- coding: utf-8 -*-
"""Testes de data.research._classificar_falha e coletar_todas_disponiveis
(campo 'categoria_falha' no resultado) - auditoria 2026-10-18, correcao
do exit code de coletor_local.py (ver _falha_critica la').

Regra sob teste: uma falha de casa so' pode virar 'bloqueio_externo_
conhecido' (o que deixa de derrubar o exit code) quando a PROPRIA casa
expoe 'categoria_falha' (callable) E ele devolve exatamente essa string -
campo ausente, excecao ao chamar, ou qualquer valor diferente sempre
volta 'erro'. Nunca mocka rede de verdade; mocka so' CASAS/obter_motivo.

Uso: python tests/test_research_classificacao_falha.py (python do
.venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research as research_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def test_1a_casa_sem_categoria_falha_e_erro():
    """Campo 'categoria_falha' ausente na casa -> sempre 'erro', nunca
    'bloqueio_externo_conhecido' por omissao."""
    casa = {"nome": "X"}
    resultado = research_mod._classificar_falha(casa)
    _checar("1a casa sem categoria_falha -> 'erro'", resultado == "erro", f"(resultado={resultado!r})")


def test_1b_categoria_falha_devolve_bloqueio_externo_conhecido():
    casa = {"nome": "X", "categoria_falha": lambda: "bloqueio_externo_conhecido"}
    resultado = research_mod._classificar_falha(casa)
    _checar("1b categoria_falha() == 'bloqueio_externo_conhecido' -> respeitado", resultado == "bloqueio_externo_conhecido", f"(resultado={resultado!r})")


def test_1c_categoria_falha_devolve_string_diferente_e_erro():
    """Qualquer valor que NAO seja exatamente 'bloqueio_externo_conhecido'
    (ex: typo, outra categoria futura) vira 'erro' - nunca assume bloqueio
    conhecido por padrao."""
    casa = {"nome": "X", "categoria_falha": lambda: "algo_generico"}
    resultado = research_mod._classificar_falha(casa)
    _checar("1c valor desconhecido -> 'erro'", resultado == "erro", f"(resultado={resultado!r})")


def test_1d_categoria_falha_devolve_none_e_erro():
    casa = {"nome": "X", "categoria_falha": lambda: None}
    resultado = research_mod._classificar_falha(casa)
    _checar("1d categoria_falha() == None -> 'erro'", resultado == "erro", f"(resultado={resultado!r})")


def test_1e_categoria_falha_levanta_excecao_e_erro_sem_propagar():
    casa = {"nome": "X", "categoria_falha": lambda: 1 / 0}
    resultado = research_mod._classificar_falha(casa)
    _checar("1e excecao ao chamar categoria_falha -> 'erro' (nao propaga)", resultado == "erro", f"(resultado={resultado!r})")


def test_1f_categoria_falha_string_vazia_e_erro():
    """Item 6 da missao: mensagem/motivo vazio nunca classificado como
    bloqueio conhecido."""
    casa = {"nome": "X", "categoria_falha": lambda: ""}
    resultado = research_mod._classificar_falha(casa)
    _checar("1f categoria_falha() == '' -> 'erro'", resultado == "erro", f"(resultado={resultado!r})")


# ============================================================
# coletar_todas_disponiveis() - 'categoria_falha' so' aparece no
# resultado quando ok=False, e usa exatamente _classificar_falha.
# ============================================================

def _casa_mock(nome, ok, coletados=0, categoria_falha=None):
    casa = {
        "id": nome.lower(),
        "nome": nome,
        "fonte": nome,
        "disponivel": True,
        "obter_relatorios": lambda: ([{"link": "https://x/1"}] if ok else None),
        "motivo_falha": None,
    }
    if categoria_falha is not None:
        casa["categoria_falha"] = categoria_falha
    return casa


def test_2a_sucesso_nao_tem_categoria_falha_no_resultado():
    """Item 8 da missao: sucesso de uma casa continua com
    categoria_falha=None - sem regressao no caminho feliz."""
    casa = _casa_mock("BTG Pactual Research", ok=True)
    with patch.object(research_mod, "CASAS", [casa]), \
         patch.object(research_mod.store, "salvar_itens", return_value=True), \
         patch.object(research_mod, "registrar_tentativa"):
        resultado = research_mod.coletar_todas_disponiveis()
    _checar("2a ok=True", resultado["BTG Pactual Research"]["ok"] is True)
    _checar("2a categoria_falha=None no sucesso", resultado["BTG Pactual Research"]["categoria_falha"] is None)


def test_2b_falha_classificada_como_bloqueio_externo_conhecido_aparece_no_resultado():
    casa = _casa_mock("XP Investimentos", ok=False, categoria_falha=lambda: "bloqueio_externo_conhecido")
    with patch.object(research_mod, "CASAS", [casa]), \
         patch.object(research_mod, "registrar_tentativa"):
        resultado = research_mod.coletar_todas_disponiveis()
    _checar("2b ok=False", resultado["XP Investimentos"]["ok"] is False)
    _checar("2b categoria_falha='bloqueio_externo_conhecido'", resultado["XP Investimentos"]["categoria_falha"] == "bloqueio_externo_conhecido")


def test_2c_falha_sem_categoria_falha_registrada_e_erro():
    """Genial (Lives): falha intermitente SEM padrao externo documentado
    (nao expoe categoria_falha) -> 'erro' no resultado (item 4 da
    missao)."""
    casa = _casa_mock("Genial (Lives)", ok=False)
    with patch.object(research_mod, "CASAS", [casa]), \
         patch.object(research_mod, "registrar_tentativa"):
        resultado = research_mod.coletar_todas_disponiveis()
    _checar("2c categoria_falha='erro' (sem padrao documentado)", resultado["Genial (Lives)"]["categoria_falha"] == "erro")


def test_2d_falha_de_persistencia_com_coleta_ok_usa_categoria_real_do_modulo_e_e_erro():
    """Item 5 da missao: falha de PERSISTENCIA (itens coletados com
    sucesso, upsert no Supabase falhou) tem que continuar 'erro', nunca
    'bloqueio_externo_conhecido' - mesmo numa casa (XP) que EXPOE
    categoria_falha. Usa o modulo xp.py DE VERDADE (nao um mock
    generico): o fetch tem sucesso (_ultimo_motivo_falha fica None), por
    isso xp.categoria_ultima_falha() corretamente devolve 'erro' - a
    invariante nao depende de coletar_todas_disponiveis tratar esse caso
    como especial, depende de cada modulo so' reportar
    'bloqueio_externo_conhecido' quando O PROPRIO FETCH falhou com o
    padrao documentado."""
    import data.research.xp as xp_mod
    xp_mod._ultimo_motivo_falha = None  # simula ultimo fetch bem-sucedido

    casa = {
        "id": "xp", "nome": "XP Investimentos", "fonte": "XP",
        "disponivel": True,
        "obter_relatorios": lambda: [{"link": "https://x/1"}],  # fetch OK
        "motivo_falha": xp_mod.motivo_ultima_falha,
        "categoria_falha": xp_mod.categoria_ultima_falha,
    }
    with patch.object(research_mod, "CASAS", [casa]), \
         patch.object(research_mod.store, "salvar_itens", return_value=False), \
         patch.object(research_mod, "registrar_tentativa"):
        resultado = research_mod.coletar_todas_disponiveis()
    _checar("2d ok=False (persistencia falhou)", resultado["XP Investimentos"]["ok"] is False)
    _checar(
        "2d categoria_falha='erro' (fetch teve sucesso - categoria real do modulo nao aponta bloqueio)",
        resultado["XP Investimentos"]["categoria_falha"] == "erro",
        f"(resultado={resultado['XP Investimentos']})",
    )


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
