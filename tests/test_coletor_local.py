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
    resultado = coletor_local._universo_rotativo([], offset=0)
    _checar("1a lista vazia -> lista vazia (sem ZeroDivisionError)", resultado == [])


def test_1b_offset_explicito_e_deterministico():
    tickers = [f"T{i}" for i in range(10)]
    r1 = coletor_local._universo_rotativo(tickers, offset=3)
    r2 = coletor_local._universo_rotativo(tickers, offset=3)
    _checar("1b mesmo offset -> mesma rotacao (deterministico)", r1 == r2, f"(r1={r1}, r2={r2})")
    _checar("1b offset=3 comeca em T3", r1[0] == "T3", f"(r1={r1})")
    _checar("1b conteudo preservado", sorted(r1) == sorted(tickers))


def test_1c_offsets_diferentes_comecam_de_tickers_diferentes():
    tickers = [f"T{i}" for i in range(10)]
    r0 = coletor_local._universo_rotativo(tickers, offset=0)
    r1 = coletor_local._universo_rotativo(tickers, offset=1)
    _checar("1c offset seguinte comeca de um ticker diferente", r0[0] != r1[0], f"(r0[0]={r0[0]}, r1[0]={r1[0]})")
    _checar("1c conteudo preservado (so' rotaciona, nunca perde/duplica ticker)",
             sorted(r0) == sorted(tickers) and sorted(r1) == sorted(tickers))


def test_1d_offset_maior_que_o_tamanho_do_universo_nao_quebra():
    tickers = [f"T{i}" for i in range(5)]
    resultado = coletor_local._universo_rotativo(tickers, offset=12)  # 12 % 5 == 2
    _checar("1d offset fora do range faz modulo, nunca IndexError", resultado[0] == "T2", f"(resultado={resultado})")


# ============================================================
# _ler_e_avancar_checkpoint: checkpoint persistido (arquivo local) -
# bug real corrigido (auditoria 2026-10-10, ver docstring de
# _universo_rotativo): a rotacao anterior derivava o offset do relogio,
# o que so' garante cobertura completa do universo pra certos tamanhos
# (coincidencia pro N=84 atual) - um contador persistido que sempre
# avanca +1 cobre QUALQUER tamanho de universo em N execucoes.
# ============================================================

def test_3a_primeira_execucao_sem_arquivo_comeca_do_offset_0():
    with patch.object(coletor_local, "_ARQUIVO_CHECKPOINT_CALENDARIO") as mock_arquivo:
        mock_arquivo.read_text.side_effect = OSError("arquivo nao existe ainda")
        offset = coletor_local._ler_e_avancar_checkpoint(10)
    _checar("2a sem arquivo -> comeca do offset 0", offset == 0)
    _checar("2a grava o PROXIMO offset (1) pra proxima execucao", mock_arquivo.write_text.call_args[0][0] == "1",
             f"(write_text call={mock_arquivo.write_text.call_args})")


def test_3b_arquivo_corrompido_degradada_pro_offset_0_sem_lancar():
    with patch.object(coletor_local, "_ARQUIVO_CHECKPOINT_CALENDARIO") as mock_arquivo:
        mock_arquivo.read_text.return_value = "nao-e-um-numero"
        offset = coletor_local._ler_e_avancar_checkpoint(10)
    _checar("2b arquivo corrompido -> offset 0, nunca lanca excecao", offset == 0)


def test_3c_falha_ao_escrever_nao_quebra_a_leitura():
    with patch.object(coletor_local, "_ARQUIVO_CHECKPOINT_CALENDARIO") as mock_arquivo:
        mock_arquivo.read_text.return_value = "5"
        mock_arquivo.write_text.side_effect = OSError("disco cheio/sem permissao")
        offset = coletor_local._ler_e_avancar_checkpoint(10)
    _checar("2c falha ao gravar o checkpoint nao impede retornar o offset lido", offset == 5)


def test_3d_avanca_exatamente_1_por_execucao_e_da_a_volta_completa():
    """O nucleo da correcao: simulando N execucoes consecutivas com um
    arquivo real (tmp), todo offset de 0 a N-1 aparece EXATAMENTE 1 vez
    (nao so' 'pelo menos 1 vez', ja' que agora e' um contador exato) -
    prova a cobertura completa que a rotacao por relogio so' garantia
    por coincidencia pra certos tamanhos de universo."""
    import tempfile
    tamanho_universo = 7
    offsets_vistos = []
    with tempfile.TemporaryDirectory() as tmp:
        arquivo_tmp = Path(tmp) / "checkpoint.txt"
        with patch.object(coletor_local, "_ARQUIVO_CHECKPOINT_CALENDARIO", arquivo_tmp):
            for _ in range(tamanho_universo):
                offsets_vistos.append(coletor_local._ler_e_avancar_checkpoint(tamanho_universo))
    _checar(
        "2d N execucoes -> todos os offsets 0..N-1 aparecem, cada 1 exatamente 1x",
        sorted(offsets_vistos) == list(range(tamanho_universo)), f"(offsets_vistos={offsets_vistos})",
    )


def test_3e_mudanca_de_tamanho_do_universo_nunca_lanca_indexerror():
    """O universo pode crescer/encolher entre execucoes (tickers
    adicionados/removidos de config.IBOVESPA_SETORES) - o checkpoint
    salvo pro tamanho ANTIGO precisa continuar seguro mesmo que o novo
    tamanho seja menor (offset salvo >= novo tamanho)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        arquivo_tmp = Path(tmp) / "checkpoint.txt"
        arquivo_tmp.write_text("50", encoding="utf-8")  # offset de um universo que tinha 80+ tickers
        with patch.object(coletor_local, "_ARQUIVO_CHECKPOINT_CALENDARIO", arquivo_tmp):
            offset = coletor_local._ler_e_avancar_checkpoint(10)  # universo encolheu pra 10
    _checar("2e offset salvo maior que o novo tamanho -> modulo, nunca IndexError", offset == 0, f"(offset={offset})")


def _rodar_main_mockado(stats_eventos: dict, snapshot_ok: bool):
    """Roda coletor_local.main() com toda dependencia de rede/Supabase
    mockada - retorna os kwargs da chamada registrar_tentativa('CALENDARIO', ...).
    resultado/historico vazios de proposito (nao e' o que este teste cobre)."""
    with patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
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


def test_4a_calendario_tudo_ok_persistencia_ok_true():
    stats = {"processados": 10, "confirmados": 2, "estimados": 1, "mantidos_prazo_cvm": 7,
              "tempo_esgotado": False, "tabela_disponivel": True}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("2a registrar_tentativa('CALENDARIO', ...) foi chamado", kwargs is not None)
    _checar("2a execucao_ok=True", kwargs.get("execucao_ok") is True, f"({kwargs})")
    _checar("2a persistencia_ok=True (tabela OK + snapshot OK)", kwargs.get("persistencia_ok") is True, f"({kwargs})")
    _checar("2a registros_novos=3 (2 confirmados + 1 estimado)", kwargs.get("registros_novos") == 3, f"({kwargs})")
    _checar("2a sem erro", kwargs.get("erro") is None, f"({kwargs})")
    _checar("2a parcial=False (orcamento nao esgotou)", kwargs.get("parcial") is False, f"({kwargs})")


def test_4b_calendario_tabela_ausente_marca_persistencia_falsa_com_erro():
    stats = {"processados": 5, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 5,
              "tempo_esgotado": False, "tabela_disponivel": False}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("2b persistencia_ok=False (tabela eventos_resultados ausente)", kwargs.get("persistencia_ok") is False, f"({kwargs})")
    _checar("2b erro cita a tabela ausente", "eventos_resultados" in (kwargs.get("erro") or ""), f"({kwargs})")


def test_4c_calendario_supabase_fora_do_ar_mas_execucao_ok():
    stats = {"processados": 5, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 5,
              "tempo_esgotado": False, "tabela_disponivel": None}
    kwargs = _rodar_main_mockado(stats, snapshot_ok=False)
    _checar("2c execucao_ok continua True (pipeline RI/NEWS roda independente do Supabase)", kwargs.get("execucao_ok") is True, f"({kwargs})")
    _checar("2c persistencia_ok=False (Supabase fora do ar)", kwargs.get("persistencia_ok") is False, f"({kwargs})")
    _checar("2c erro cita Supabase E snapshot (2 causas reais, nao so' 1)", kwargs.get("erro", "").count(";") == 1, f"({kwargs})")


def test_4d_calendario_tempo_esgotado_marca_parcial():
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
