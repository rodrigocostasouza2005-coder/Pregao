# -*- coding: utf-8 -*-
"""Testes de data/macro.py:obter_curva_pre (curva pre/ETTJ, ANBIMA) -
bug real corrigido (auditoria 2026-10-10): uma resposta NAO-vazia mas
malformada pra UM dos 7 dias tentados (layout mudou, mensagem de erro/
manutencao no lugar do CSV) lancava excecao (StopIteration/ValueError)
de dentro do loop de fallback - como nao havia try/except por iteracao,
isso escapava pro try/except EXTERNO e abortava a tentativa nos outros
6 dias, mesmo que algum deles tivesse publicacao valida. Mocka
_buscar_ettj_anbima - nunca faz chamada de rede.

Uso: python tests/test_macro.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.macro as macro_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


_CSV_VALIDO = "\n".join([
    "10/10/2026",
    "PREFIXADOS (CIRCULAR 3.361)",
    "header (ignorada)",
    "21;13,3917",
    "42;13,2000",
    "",  # linha vazia real (splitlines() so reconhece como item separado
    "fim do bloco",  # se houver conteudo depois - string.splitlines() nao
])  # gera elemento vazio final so por terminar em "\n"


def test_1_dia_malformado_nao_aborta_tentativa_dos_dias_anteriores():
    """volta=0 (hoje) vem com texto NAO-vazio mas sem o bloco PREFIXADOS
    (layout mudou/mensagem de erro) - antes da correcao isso abortava o
    loop inteiro; agora deve cair pro volta=1 (CSV valido) sem lancar."""
    from datetime import date

    macro_mod.obter_curva_pre.clear()

    def _fake_buscar(dt_ref_str):
        if dt_ref_str == date(2026, 10, 10).strftime("%d%m%Y"):
            return "pagina de manutencao, sem o bloco PREFIXADOS esperado"
        return _CSV_VALIDO

    with patch.object(macro_mod, "_buscar_ettj_anbima", side_effect=_fake_buscar), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("1a nao retorna None (achou um dia valido apos o malformado)", df is not None, f"(df={df})")
    _checar("1b DataFrame tem os 2 vertices do dia valido", df is not None and len(df) == 2, f"(df={df})")
    _checar("1c registra execucao_ok=True (achou publicacao valida)",
            mock_reg.call_args is not None and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")


def test_2_todos_os_dias_malformados_resulta_em_falha_registrada():
    from datetime import date

    macro_mod.obter_curva_pre.clear()
    with patch.object(macro_mod, "_buscar_ettj_anbima", return_value="sem bloco PREFIXADOS nenhum"), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("2a todos os 7 dias malformados -> None (nunca inventa curva)", df is None)
    _checar("2b registra execucao_ok=False", mock_reg.call_args.kwargs.get("execucao_ok") is False, f"({mock_reg.call_args})")


def test_3_dias_vazios_continuam_pulados_normalmente():
    """Garante que a correcao nao mudou o comportamento ja existente pra
    dia sem publicacao (texto vazio, ex: fim de semana) - continua so'
    pulando pro dia anterior, sem tentar parsear."""
    from datetime import date

    macro_mod.obter_curva_pre.clear()
    chamadas = []

    def _fake_buscar(dt_ref_str):
        chamadas.append(dt_ref_str)
        if len(chamadas) <= 2:
            return ""  # dias sem publicacao
        return _CSV_VALIDO

    with patch.object(macro_mod, "_buscar_ettj_anbima", side_effect=_fake_buscar), \
         patch.object(macro_mod, "registrar_tentativa"):
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("3a acha o CSV valido apos pular os 2 dias vazios", df is not None and len(df) == 2, f"(df={df})")
    _checar("3b tentou exatamente 3 dias (2 vazios + 1 valido, nao os 7)", len(chamadas) == 3, f"(chamadas={chamadas})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE MACRO.PY (CURVA PRE/ANBIMA) PASSARAM")
