# -*- coding: utf-8 -*-
"""Testes de jobs/checar_env.py - checagem de secrets usada pelos
workflows (nuvem Linux e runner self-hosted Windows do PC de casa).

Uso: python tests/test_checar_env.py (python do .venv do projeto)."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from jobs import checar_env


def test_todos_presentes_retorna_0():
    with patch.dict(os.environ, {"A_TESTE": "x", "B_TESTE": "y"}):
        assert checar_env.main(["A_TESTE", "B_TESTE"]) == 0


def test_ausente_ou_vazio_retorna_1_e_anota_erro():
    with patch.dict(os.environ, {"A_TESTE": "x", "B_TESTE": ""}):
        os.environ.pop("C_TESTE", None)
        assert checar_env.faltando(["A_TESTE", "B_TESTE", "C_TESTE"]) == ["B_TESTE", "C_TESTE"]
        assert checar_env.main(["A_TESTE", "B_TESTE", "C_TESTE"]) == 1


if __name__ == "__main__":
    test_todos_presentes_retorna_0()
    test_ausente_ou_vazio_retorna_1_e_anota_erro()
    print("[OK] checar_env")
