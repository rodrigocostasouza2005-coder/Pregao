# -*- coding: utf-8 -*-
"""Testes de coletor_local.py - a parte pura/testavel sem rede nem
Supabase (_universo_rotativo) e a orquestracao de main() com todas as
dependencias reais mockadas (coleta de research/eventos/snapshot e o
registro de SAUDE DOS DADOS do CALENDARIO, auditoria 2026-10-10 - ver
docstring do bloco de registrar_tentativa dentro de main()).

Uso: python tests/test_coletor_local.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import coletor_local

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


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


def _rodar_main_mockado(stats_eventos: dict, snapshot_ok: bool):
    """Roda coletor_local.main() com toda dependencia de rede/Supabase
    mockada - retorna os kwargs da chamada registrar_tentativa('CALENDARIO', ...).
    resultado/historico vazios de proposito (nao e' o que este teste cobre)."""
    with patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=snapshot_ok), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        coletor_local.main()
    for args, kwargs in mock_reg.call_args_list:
        if args[0] == "CALENDARIO":
            return kwargs
    return None


def test_2a_calendario_tudo_ok_persistencia_ok_true():
    stats = {"processados": 10, "confirmados": 2, "estimados": 1, "mantidos_prazo_cvm": 7,
              "tempo_esgotado": False, "tabela_disponivel": True}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("2a registrar_tentativa('CALENDARIO', ...) foi chamado", kwargs is not None)
    _checar("2a execucao_ok=True", kwargs.get("execucao_ok") is True, f"({kwargs})")
    _checar("2a persistencia_ok=True (tabela OK + snapshot OK)", kwargs.get("persistencia_ok") is True, f"({kwargs})")
    _checar("2a registros_novos=3 (2 confirmados + 1 estimado)", kwargs.get("registros_novos") == 3, f"({kwargs})")
    _checar("2a sem erro", kwargs.get("erro") is None, f"({kwargs})")
    _checar("2a parcial=False (orcamento nao esgotou)", kwargs.get("parcial") is False, f"({kwargs})")


def test_2b_calendario_tabela_ausente_marca_persistencia_falsa_com_erro():
    stats = {"processados": 5, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 5,
              "tempo_esgotado": False, "tabela_disponivel": False}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("2b persistencia_ok=False (tabela eventos_resultados ausente)", kwargs.get("persistencia_ok") is False, f"({kwargs})")
    _checar("2b erro cita a tabela ausente", "eventos_resultados" in (kwargs.get("erro") or ""), f"({kwargs})")


def test_2c_calendario_supabase_fora_do_ar_mas_execucao_ok():
    stats = {"processados": 5, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 5,
              "tempo_esgotado": False, "tabela_disponivel": None}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=False)
    _checar("2c execucao_ok continua True (pipeline RI/NEWS roda independente do Supabase)", kwargs.get("execucao_ok") is True, f"({kwargs})")
    _checar("2c persistencia_ok=False (Supabase fora do ar)", kwargs.get("persistencia_ok") is False, f"({kwargs})")
    _checar("2c erro cita Supabase E snapshot (2 causas reais, nao so' 1)", kwargs.get("erro", "").count(";") == 1, f"({kwargs})")


def test_2d_calendario_tempo_esgotado_marca_parcial():
    stats = {"processados": 3, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 3,
              "tempo_esgotado": True, "tabela_disponivel": True}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("2d orcamento esgotado -> parcial=True", kwargs.get("parcial") is True, f"({kwargs})")


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
    print("TODOS OS TESTES DO COLETOR LOCAL PASSARAM")
