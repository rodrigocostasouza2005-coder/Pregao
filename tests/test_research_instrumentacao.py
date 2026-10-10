# -*- coding: utf-8 -*-
"""Testes da instrumentacao de SAUDE DOS DADOS (data.coletores_status.
registrar_tentativa) nos 3 coletores de research que so' rodam de
verdade via coletor_local.py (Genial Analisa/XP Investimentos/Genial
Lives) - auditoria 2026-10-10 (ver data/saude_dados.py). Mocka
`obter_relatorios`/`store.salvar_itens`/`registrar_tentativa`, nunca
faz chamada de rede nem toca Supabase de verdade.

Uso: python tests/test_research_instrumentacao.py (python do .venv do
projeto)."""
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


def _casa_fake(nome="Casa Fake", fonte="fonte-fake.com", itens=None, falha=False):
    return {
        "id": "fake", "nome": nome, "fonte": fonte,
        "obter_relatorios": lambda: (None if falha else (itens or [])),
    }


def test_1a_sucesso_registra_execucao_ok_e_persistencia_ok():
    itens = [{"link": "https://x/1"}, {"link": "https://x/2"}]
    casa = _casa_fake(nome="Genial Analisa", fonte="analisa.genialinvestimentos.com.br", itens=itens)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=True):
        n, ok = research_mod.coletar_casa(casa)
    _checar("1a retorna (2, True)", (n, ok) == (2, True), f"(n={n}, ok={ok})")
    _checar("1a chamou registrar_tentativa exatamente 1x", mock_reg.call_count == 1)
    args, kwargs = mock_reg.call_args
    _checar("1a nome da casa correto", args[0] == "Genial Analisa", f"(args={args})")
    _checar("1a fonte correta", args[1] == "analisa.genialinvestimentos.com.br", f"(args={args})")
    _checar("1a execucao_ok=True", kwargs.get("execucao_ok") is True, f"(kwargs={kwargs})")
    _checar("1a persistencia_ok=True (store.salvar_itens OK)", kwargs.get("persistencia_ok") is True, f"(kwargs={kwargs})")
    _checar("1a registros_novos=2 (itens coletados nesta execucao)", kwargs.get("registros_novos") == 2, f"(kwargs={kwargs})")


def test_1b_persistencia_falha_registra_persistencia_ok_false():
    casa = _casa_fake(nome="XP Investimentos", fonte="conteudos.xpi.com.br (WP REST)", itens=[{"link": "https://x/1"}])
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens", return_value=False):
        n, ok = research_mod.coletar_casa(casa)
    _checar("1b retorna (1, False) - fonte respondeu, gravacao falhou", (n, ok) == (1, False), f"(n={n}, ok={ok})")
    _, kwargs = mock_reg.call_args
    _checar("1b execucao_ok=True (a fonte respondeu)", kwargs.get("execucao_ok") is True, f"(kwargs={kwargs})")
    _checar("1b persistencia_ok=False (upsert falhou)", kwargs.get("persistencia_ok") is False, f"(kwargs={kwargs})")


def test_1c_falha_na_fonte_registra_execucao_ok_false_com_erro():
    casa = _casa_fake(nome="Genial (Lives)", fonte="YouTube RSS (canal Genial Analisa)", falha=True)
    with patch.object(research_mod, "registrar_tentativa") as mock_reg, \
         patch.object(research_mod.store, "salvar_itens") as mock_salvar:
        n, ok = research_mod.coletar_casa(casa)
    _checar("1c retorna (0, False)", (n, ok) == (0, False), f"(n={n}, ok={ok})")
    _checar("1c nunca chama salvar_itens quando a fonte falhou (nada pra persistir)", mock_salvar.call_count == 0)
    _, kwargs = mock_reg.call_args
    _checar("1c execucao_ok=False", kwargs.get("execucao_ok") is False, f"(kwargs={kwargs})")
    _checar("1c erro preenchido (nunca None numa falha)", bool(kwargs.get("erro")), f"(kwargs={kwargs})")
    _checar("1c categoria='Research'", kwargs.get("categoria") == "Research", f"(kwargs={kwargs})")


def test_1d_casas_reais_tem_campo_fonte_preenchido():
    """As 3 casas que rodam so' via coletor_local.py (genial/xp/genial_lives)
    precisam do campo 'fonte' preenchido - sem ele, coletar_casa cairia no
    fallback (usar o proprio nome como fonte), perdendo a info real
    mostrada em SAUDE DOS DADOS."""
    casas_locais = {c["id"]: c for c in research_mod.CASAS if c["id"] in ("genial", "xp", "genial_lives")}
    for id_casa, casa in casas_locais.items():
        _checar(f"1d {id_casa} tem 'fonte' nao-vazia", bool(casa.get("fonte")), f"(casa={casa.get('fonte')})")


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
    print("TODOS OS TESTES DE INSTRUMENTACAO DE RESEARCH (SAUDE DOS DADOS) PASSARAM")
