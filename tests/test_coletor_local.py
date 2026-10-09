# -*- coding: utf-8 -*-
"""Testes de coletor_local.py - so a parte pura/testavel sem rede nem
Supabase (_universo_rotativo). Bug real corrigido (2026-10-09, FASE 8):
ver docstring de _universo_rotativo no proprio coletor_local.py.

Uso: python tests/test_coletor_local.py (python do .venv do projeto)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import coletor_local

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def test_1a_lista_vazia_nao_quebra():
    resultado = coletor_local._universo_rotativo([])
    _checar("1a lista vazia -> lista vazia (sem ZeroDivisionError)", resultado == [])


def test_1b_sem_rotacao_na_mesma_janela_retorna_ordem_original():
    tickers = [f"T{i}" for i in range(10)]
    agora = 1_000_000.0  # qualquer instante fixo
    r1 = coletor_local._universo_rotativo(tickers, agora=agora)
    r2 = coletor_local._universo_rotativo(tickers, agora=agora + 60)  # mesma janela de 30min
    _checar("1b mesma janela de 30min -> mesmo ponto de partida (deterministico)", r1 == r2, f"(r1={r1}, r2={r2})")


def test_1c_janelas_diferentes_avancam_o_ponto_de_partida():
    tickers = [f"T{i}" for i in range(10)]
    r0 = coletor_local._universo_rotativo(tickers, agora=0.0)
    r1 = coletor_local._universo_rotativo(tickers, agora=coletor_local._JANELA_ROTACAO_S)
    _checar(
        "1c janela seguinte (+30min) comeca de um ticker diferente (nao estagna sempre no mesmo T0)",
        r0[0] != r1[0] or r0 != r1, f"(r0[0]={r0[0]}, r1[0]={r1[0]})",
    )
    _checar("1c conteudo preservado (so' rotaciona, nunca perde/duplica ticker)",
             sorted(r0) == sorted(tickers) and sorted(r1) == sorted(tickers))


def test_1d_ao_longo_de_varias_janelas_todo_ticker_vira_o_primeiro_pelo_menos_1x():
    """Reproduz o cenario real: orcamento de rede so' cobre os primeiros N
    tickers por execucao - sem rotacao, os tickers do fim da lista (ex:
    config.IBOVESPA_SETORES, ordem fixa) NUNCA seriam o primeiro da vez e
    ficariam permanentemente fora do orcamento. Com rotacao, varrendo
    janelas suficientes (1 por ticker), todo ticker passa pela posicao 0
    pelo menos uma vez."""
    tickers = [f"T{i}" for i in range(12)]
    primeiros = set()
    for janela in range(len(tickers)):
        agora = janela * coletor_local._JANELA_ROTACAO_S
        primeiros.add(coletor_local._universo_rotativo(tickers, agora=agora)[0])
    _checar(
        "1d todo ticker do universo chega a ser o 1o da lista em alguma janela (nenhum fica permanentemente fora)",
        primeiros == set(tickers), f"(primeiros={primeiros})",
    )


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO COLETOR LOCAL PASSARAM")
