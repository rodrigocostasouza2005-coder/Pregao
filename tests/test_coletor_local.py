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
import pytest

_STATS_IMAGENS_VAZIO = {"grupos_considerados": 0, "ja_com_imagem": 0, "avaliados": 0, "salvos": 0,
                        "falhas": 0, "tempo_esgotado": False, "por_status": {}, "tabela_disponivel": True}


@pytest.fixture(autouse=True)
def mock_pregerar_imagens():
    """Nenhum teste deste arquivo pode executar a etapa REAL de imagens de
    NEWS (consultaria o Supabase e baixaria feeds/páginas se a máquina
    tiver credenciais) - os testes que a cobrem usam este mock."""
    with patch.object(coletor_local, "pregerar_imagens_news", return_value=dict(_STATS_IMAGENS_VAZIO)) as m:
        yield m


@pytest.fixture(autouse=True)
def mock_universo_calendario():
    """Reforma estrutural do CALENDARIO (2026-10-24): main() agora chama
    data.eventos.universo_calendario() (CVM/FCA + BDRs + watchlists
    reais) ANTES de coletar_eventos_universo/salvar_snapshot_calendario.
    Nenhum teste deste arquivo pode disparar a chamada REAL (rede pra
    CVM + leitura paginada do Supabase) - fixa um universo pequeno e
    deterministico, consistente com os testes que ja existiam antes
    desta reforma (eles nao testam o CONTEUDO do universo, so' a
    orquestracao de main())."""
    with patch.object(coletor_local, "universo_calendario", return_value=["PETR4", "VALE3"]) as m:
        yield m

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


_STATS_NEWS_VAZIO = {"grupos_considerados": 0, "ja_cacheados": 0, "gerados": 0, "falhas": 0,
                     "tempo_esgotado": False, "tabela_disponivel": True}


def _rodar_main_mockado(stats_eventos: dict, snapshot_ok: bool, stats_news: dict = None):
    """Roda coletor_local.main() com toda dependencia de rede/Supabase
    mockada - retorna os kwargs da chamada registrar_tentativa('CALENDARIO', ...).
    resultado/historico vazios de proposito (nao e' o que este teste cobre)."""
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news or _STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=snapshot_ok), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        coletor_local.main()
    for args, kwargs in mock_reg.call_args_list:
        if args[0] == "CALENDARIO":
            return kwargs
    return None


def _kwargs_registrar(mock_reg, nome: str):
    for args, kwargs in mock_reg.call_args_list:
        if args[0] == nome:
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


def test_4a2_calendario_universo_calculado_1x_e_reaproveitado_no_snapshot(mock_universo_calendario):
    """Reforma estrutural (2026-10-24): universo_calendario() precisa ser
    calculado 1 vez por execucao de main() e reaproveitado tanto na
    coleta de eventos quanto no snapshot - 2 leituras completas de
    user_prefs/CVM por rodada seria desperdicio (ambas @st.cache_data,
    mas o ponto e' a orquestracao em si nunca pedir 2x por acidente)."""
    stats = {"processados": 2, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 2,
              "tempo_esgotado": False, "tabela_disponivel": True}
    _rodar_main_mockado(stats, snapshot_ok=True)
    _checar("4a2 universo_calendario chamado exatamente 1x por execucao",
            mock_universo_calendario.call_count == 1, f"(call_count={mock_universo_calendario.call_count})")


def test_4a3_documentos_cvm_rodam_pro_universo_inteiro_sem_rotacao(mock_universo_calendario):
    """Achado real (auditoria 2026-10-30): obter_documentos_watchlist so'
    era chamada pelo app Streamlit ao vivo (ui/cvm_tab.py), nunca por um
    workflow agendado - coletor_local.py precisa chamar pro universo
    INTEIRO (sem _universo_rotativo: e' barato, so' baixa o IPE 1x/ano e
    filtra em memoria, nao e' 1 requisicao de rede por ticker)."""
    stats = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
              "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])) as mock_cvm, \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        coletor_local.main()
    _checar("4a3 obter_documentos_watchlist foi chamado exatamente 1x", mock_cvm.call_count == 1)
    _checar("4a3 recebeu o universo INTEIRO (nao rotacionado)", mock_cvm.call_args[0][0] == ["PETR4", "VALE3"],
            f"(recebido={mock_cvm.call_args[0][0]})")


def test_4a4_falha_inesperada_em_documentos_cvm_nao_derruba_a_execucao(mock_universo_calendario):
    """Isolamento (pedido explicito, Fase 4): uma excecao inesperada em
    obter_documentos_watchlist (fora do try/except por-ticker que ela ja
    tem) nao pode impedir eventos/snapshot/news de rodar nem travar
    main() com uma excecao nao tratada."""
    stats = {"processados": 1, "confirmados": 1, "estimados": 0, "mantidos_prazo_cvm": 0,
              "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", side_effect=RuntimeError("falha inesperada")), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats) as mock_eventos, \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        codigo = coletor_local.main()
    _checar("4a4 main() nao lanca excecao (retorna exit code normal)", codigo == 0, f"(codigo={codigo})")
    _checar("4a4 coletar_eventos_universo ainda roda depois da falha", mock_eventos.call_count == 1)


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


def test_4e_timeout_calendario_retorna_codigo_erro_ao_agendador():
    """O timeout e' parcial recuperavel, mas nao pode ser exit code 0:
    o Agendador do Windows precisa sinalizar que o universo ficou incompleto."""
    stats = {"processados": 3, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 3,
             "falhas": 0, "tempo_esgotado": True, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        codigo = coletor_local.main()
    _checar("2e timeout -> exit code 1 (execucao incompleta visivel ao Agendador)", codigo == 1,
            f"(codigo={codigo})")


# ============================================================
# pre-processamento de NEWS (reformulacao editorial, 2026-10-15, ver
# data/news.py:pregerar_resumos_news) - checkpoint PROPRIO (nao o do
# CALENDARIO) e registro de SAUDE DOS DADOS.
# ============================================================

def test_5a_news_usa_checkpoint_proprio_em_arquivo_calendario_usa_checkpoint_supabase():
    """Reforma 2026-10-31 (ver docstring de _ler_checkpoint_calendario em
    coletor_local.py): _universo_rotativo (arquivo local/GITHUB_RUN_NUMBER)
    continua em uso SO' pelo NEWS - o CALENDARIO passou a rotacionar via
    checkpoint persistido no Supabase (_ler_checkpoint_calendario/
    _avancar_checkpoint_calendario), que avanca pelo trabalho REAL feito
    (nao mais +1 fixo por execucao, que levava ~18 dias uteis pra cobrir
    o universo de 481 tickers de hoje)."""
    stats = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
              "tempo_esgotado": False, "tabela_disponivel": True}
    chamadas = []

    def _fake_rotativo(tickers, offset=None, arquivo_checkpoint=None):
        chamadas.append(arquivo_checkpoint)
        return [f"T{i}" for i in range(30)]  # universo grande o bastante pra testar o corte

    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", side_effect=_fake_rotativo), \
         patch.object(coletor_local, "_ler_checkpoint_calendario", return_value=0) as mock_ler_cal, \
         patch.object(coletor_local, "_avancar_checkpoint_calendario") as mock_avancar_cal, \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO) as mock_pregen, \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        coletor_local.main()
    _checar("5a _universo_rotativo e' chamado 1x (so' NEWS - CALENDARIO usa o checkpoint do Supabase)",
            len(chamadas) == 1, f"(chamadas={chamadas})")
    _checar("5b a chamada de NEWS usa o checkpoint proprio do NEWS", chamadas == [coletor_local._ARQUIVO_CHECKPOINT_NEWS],
            f"(chamadas={chamadas})")
    _checar("5b2 o CALENDARIO le o checkpoint do Supabase (nao o arquivo local)", mock_ler_cal.called)
    _checar("5b3 o CALENDARIO avanca o checkpoint do Supabase apos processar", mock_avancar_cal.called)
    _checar("5d pregerar_resumos_news foi chamado exatamente 1x", mock_pregen.call_count == 1)
    _checar("5e pregerar_resumos_news recebeu exatamente _QTD_TICKERS_NEWS_POR_EXECUCAO tickers (universo fake tem 30)",
            len(mock_pregen.call_args[0][0]) == coletor_local._QTD_TICKERS_NEWS_POR_EXECUCAO,
            f"(recebido={len(mock_pregen.call_args[0][0])})")


def test_5a2_checkpoint_calendario_avanca_pelo_trabalho_real_processado():
    """O nucleo do fix (2026-10-31): o offset gravado de volta e'
    offset_lido + processados (mod tamanho do universo), nao offset+1 -
    prova que a rotacao agora cobre o universo em ceil(N/K) execucoes em
    vez de N (ver docstring do bloco em coletor_local.py)."""
    universo_fake = [f"T{i}" for i in range(10)]
    stats = {"processados": 4, "confirmados": 1, "estimados": 0, "mantidos_prazo_cvm": 3,
              "tempo_esgotado": False, "tabela_disponivel": True}

    with patch.object(coletor_local, "universo_calendario", return_value=universo_fake), \
         patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "_ler_checkpoint_calendario", return_value=3), \
         patch.object(coletor_local, "_avancar_checkpoint_calendario") as mock_avancar, \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats) as mock_coletar, \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        coletor_local.main()

    _checar("5a2a universo passado a coletar_eventos_universo comeca no offset lido (3)",
            mock_coletar.call_args[0][0][0] == "T3", f"(chamado com={mock_coletar.call_args[0][0]})")
    _checar("5a2b checkpoint avancado = offset(3) + processados(4) = 7, nao 3+1=4",
            mock_avancar.call_args[0][0] == 7, f"(avancado para={mock_avancar.call_args[0][0]})")


def test_5a3_checkpoint_calendario_nunca_trava_girando_no_mesmo_lugar_se_processar_0():
    """Se coletar_eventos_universo processar 0 (ex: tempo esgotado antes
    do 1o ticker, caso raro), o avanco minimo e' 1 - nunca grava o MESMO
    offset de volta (travaria a rotacao pra sempre no mesmo ponto)."""
    universo_fake = [f"T{i}" for i in range(5)]
    stats = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
              "tempo_esgotado": True, "tabela_disponivel": True}

    with patch.object(coletor_local, "universo_calendario", return_value=universo_fake), \
         patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "_ler_checkpoint_calendario", return_value=2), \
         patch.object(coletor_local, "_avancar_checkpoint_calendario") as mock_avancar, \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        coletor_local.main()
    _checar("5a3 avanco minimo de 1 mesmo com processados=0", mock_avancar.call_args[0][0] == 3,
            f"(avancado para={mock_avancar.call_args[0][0]})")


def test_5a4_ler_checkpoint_calendario_sem_supabase_degrada_pro_offset_0():
    with patch.object(coletor_local, "obter_cliente", return_value=None):
        offset = coletor_local._ler_checkpoint_calendario()
    _checar("5a4 sem Supabase -> offset 0, nunca lanca", offset == 0)


def test_5a5_avancar_checkpoint_calendario_sem_supabase_nao_lanca():
    with patch.object(coletor_local, "obter_cliente", return_value=None):
        coletor_local._avancar_checkpoint_calendario(42)  # nao deve lancar


def test_5f_registra_saude_dados_news_resumos():
    stats_news = {"grupos_considerados": 8, "ja_cacheados": 3, "gerados": 5, "falhas": 0,
                  "tempo_esgotado": False, "tabela_disponivel": True}
    stats_eventos = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
                      "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        coletor_local.main()
    kwargs = _kwargs_registrar(mock_reg, "NEWS (resumos)")
    _checar("5g registrar_tentativa('NEWS (resumos)', ...) foi chamado", kwargs is not None)
    _checar("5h registros_novos reflete 'gerados'", kwargs.get("registros_novos") == 5, f"({kwargs})")
    _checar("5i execucao_ok=True (pre-processamento nunca derruba o coletor)", kwargs.get("execucao_ok") is True)
    _checar("5j parcial=False (nem tempo esgotado nem falha)", kwargs.get("parcial") is False, f"({kwargs})")


def test_5k_news_tempo_esgotado_marca_parcial_mas_nao_falha_exit_code():
    stats_news = {"grupos_considerados": 20, "ja_cacheados": 0, "gerados": 25, "falhas": 0,
                  "tempo_esgotado": True, "tabela_disponivel": True}
    stats_eventos = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
                      "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        codigo = coletor_local.main()
    kwargs = _kwargs_registrar(mock_reg, "NEWS (resumos)")
    _checar("5l orcamento de NEWS esgotado -> parcial=True", kwargs.get("parcial") is True, f"({kwargs})")
    _checar("5m mas isso NUNCA derruba o exit code do coletor (pre-processamento e' soft)", codigo == 0,
            f"(codigo={codigo})")


def test_5n_news_sem_groq_api_key_aparece_como_erro_na_saude_dos_dados():
    """Achado real 2026-10-18 (run 39088619143): sem GROQ_API_KEY o painel
    registrava NEWS (resumos) como execucao OK. Agora: execucao_ok=False e
    erro citando a chave - sem derrubar o exit code (o resto do coletor
    continua valido)."""
    stats_news = {"grupos_considerados": 0, "ja_cacheados": 0, "gerados": 0, "indisponiveis": 0,
                  "falhas": 0, "tempo_esgotado": False, "tabela_disponivel": True, "groq_configurado": False}
    stats_eventos = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
                      "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        codigo = coletor_local.main()
    kwargs = _kwargs_registrar(mock_reg, "NEWS (resumos)")
    _checar("5n execucao_ok=False sem GROQ_API_KEY", kwargs.get("execucao_ok") is False, f"({kwargs})")
    _checar("5n erro cita GROQ_API_KEY", "GROQ_API_KEY" in (kwargs.get("erro") or ""), f"({kwargs})")
    _checar("5n exit code continua 0 (resto da coleta valido)", codigo == 0, f"(codigo={codigo})")


def test_6a_main_chama_self_test_de_persistencia_antes_de_qualquer_coletor():
    """Regressao 2026-10-15 (auditoria do secret errado em producao):
    main() precisa rodar diagnosticar_persistencia() ANTES de
    coletar_todas_disponiveis/coletar_eventos_universo/etc - sem isso, a
    1a pista de uma credencial sem privilegio de escrita so' aparecia
    como N excecoes "42501" espalhadas, 1 por coletor, nunca 1
    diagnostico unico e claro na raiz."""
    chamadas_diagnostico = []
    with patch.object(coletor_local, "diagnosticar_persistencia",
                       side_effect=lambda: chamadas_diagnostico.append(1) or {"ok": False, "etapa": "ESCRITA", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value={"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0, "tempo_esgotado": False, "tabela_disponivel": True}), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        coletor_local.main()
    _checar("6a diagnosticar_persistencia chamado exatamente 1x", len(chamadas_diagnostico) == 1, f"({chamadas_diagnostico})")


def test_6b_persistencia_quebrada_pula_pregen_de_news_sem_gastar_cota_de_ia():
    """Regressao real encontrada na auditoria pos-16h: diagnosticar_persistencia()
    sendo chamado (ver teste 6a) nao bastava por si so' - nada usava o
    resultado pra EVITAR pregerar_resumos_news, que voltava a queimar
    cota real do Groq (25 chamadas/execucao) mesmo com a escrita
    confirmada quebrada. main() precisa pular o pre-processamento
    inteiro (zero chamadas) quando diagnostico['ok'] for False."""
    with patch.object(coletor_local, "diagnosticar_persistencia",
                       return_value={"ok": False, "etapa": "ESCRITA", "detalhe": "new row violates row-level security policy"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news") as mock_pregen, \
         patch.object(coletor_local, "coletar_eventos_universo",
                       return_value={"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0, "tempo_esgotado": False, "tabela_disponivel": True}), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        codigo = coletor_local.main()
    _checar("6b pregerar_resumos_news NUNCA chamado (zero cota de IA gasta)", mock_pregen.call_count == 0)
    kwargs = _kwargs_registrar(mock_reg, "NEWS (resumos)")
    _checar("6c persistencia_ok=False propagado pro SAUDE DOS DADOS", kwargs.get("persistencia_ok") is False, f"({kwargs})")
    _checar("6d erro cita a etapa do self-test", "ESCRITA" in (kwargs.get("erro") or ""), f"({kwargs})")
    _checar("6e registros_novos=0 (nada foi gerado)", kwargs.get("registros_novos") == 0, f"({kwargs})")
    _checar("6f execucao_ok continua True e exit code nao quebra (soft)", kwargs.get("execucao_ok") is True and codigo == 0,
            f"(kwargs={kwargs}, codigo={codigo})")


def test_6g_persistencia_ok_roda_pregen_normalmente():
    """Confirma que o guard so' bloqueia quando diagnostico falha - com
    persistencia OK, pregerar_resumos_news continua rodando normalmente
    (nenhuma regressao introduzida por este guard)."""
    stats_news = {"grupos_considerados": 5, "ja_cacheados": 2, "gerados": 3, "falhas": 0, "tempo_esgotado": False}
    with patch.object(coletor_local, "diagnosticar_persistencia",
                       return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news) as mock_pregen, \
         patch.object(coletor_local, "coletar_eventos_universo",
                       return_value={"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0, "tempo_esgotado": False, "tabela_disponivel": True}), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa") as mock_reg:
        coletor_local.main()
    _checar("6h pregerar_resumos_news chamado normalmente", mock_pregen.call_count == 1)
    kwargs = _kwargs_registrar(mock_reg, "NEWS (resumos)")
    _checar("6i persistencia_ok=True", kwargs.get("persistencia_ok") is True, f"({kwargs})")
    _checar("6j registros_novos reflete o que pregerar_resumos_news devolveu", kwargs.get("registros_novos") == 3, f"({kwargs})")


# ============================================================
# _falha_critica/exit code do bloco de research (auditoria 2026-10-18):
# antes, QUALQUER casa de research falhando marcava exit code 1, mesmo
# bloqueio externo cronico e ja documentado (Akamai na Genial/XP) -
# o workflow 'Coletores na nuvem' e o Agendador do Windows apareciam
# sempre com erro mesmo sem nenhuma regressao real. Ver
# coletor_local._falha_critica e data.research._classificar_falha.
# ============================================================

def _rodar_main_com_resultado_research(resultado: dict) -> int:
    """Roda main() com CALENDARIO/NEWS "limpos" (sem contribuir pro exit
    code) e o resultado de coletar_todas_disponiveis() fixado em
    `resultado` - isola o efeito do bloco de research no exit code
    final. Retorna o exit code de main()."""
    stats_eventos = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
                      "falhas": 0, "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia", return_value={"ok": True, "etapa": "OK", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value=resultado), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=_STATS_NEWS_VAZIO), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        return coletor_local.main()


def test_7a_falha_critica_sucesso_nunca_e_critica():
    _checar("7a ok=True -> nunca critica", coletor_local._falha_critica({"ok": True, "categoria_falha": None}) is False)


def test_7b_falha_critica_sem_categoria_falha_e_critica():
    _checar("7b ok=False sem categoria_falha -> critica", coletor_local._falha_critica({"ok": False, "categoria_falha": None}) is True)


def test_7c_falha_critica_bloqueio_externo_conhecido_nao_e_critica():
    _checar("7c ok=False com 'bloqueio_externo_conhecido' -> nao critica", coletor_local._falha_critica({"ok": False, "categoria_falha": "bloqueio_externo_conhecido"}) is False)


def test_7d_falha_critica_categoria_erro_e_critica():
    _checar("7d ok=False com categoria 'erro' -> critica", coletor_local._falha_critica({"ok": False, "categoria_falha": "erro"}) is True)


def test_8a_xp_bloqueio_conhecido_resto_ok_exit_0():
    """Item 1 da missao: XP falhando com o padrao de bloqueio externo
    conhecido, resto das casas OK -> exit code 0."""
    resultado = {
        "XP Investimentos": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
        "BTG Pactual Research": {"coletados": 26, "ok": True, "categoria_falha": None},
        "Genial (Lives)": {"coletados": 6, "ok": True, "categoria_falha": None},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8a XP bloqueada (conhecido) + resto OK -> exit 0", codigo == 0, f"(codigo={codigo})")


def test_8b_genial_analisa_bloqueio_conhecido_resto_ok_exit_0():
    """Item 2 da missao: mesmo principio aplicado a Genial Analisa."""
    resultado = {
        "Genial Analisa": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
        "BTG Pactual Research": {"coletados": 26, "ok": True, "categoria_falha": None},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8b Genial Analisa bloqueada (conhecido) + resto OK -> exit 0", codigo == 0, f"(codigo={codigo})")


def test_8c_xp_erro_novo_tipo_http_500_exit_1():
    """Item 3 da missao: XP com um erro DIFERENTE do padrao Akamai
    conhecido (ex: comecou a devolver HTTP 500) -> categoria 'erro' ->
    exit code 1, sinalizando a mudanca em vez de mascarar."""
    resultado = {
        "XP Investimentos": {"coletados": 0, "ok": False, "categoria_falha": "erro"},
        "BTG Pactual Research": {"coletados": 26, "ok": True, "categoria_falha": None},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8c XP com erro novo (nao-Akamai) -> exit 1", codigo == 1, f"(codigo={codigo})")


def test_8d_genial_lives_falha_generica_sem_classificacao_exit_1():
    """Item 4 da missao: Genial Lives falhando com motivo generico/nao
    classificado (categoria_falha ausente no resultado, igual
    coletar_todas_disponiveis produz quando a casa nao expoe
    'categoria_falha') -> exit code 1."""
    resultado = {
        "Genial (Lives)": {"coletados": 0, "ok": False, "categoria_falha": "erro"},
        "BTG Pactual Research": {"coletados": 26, "ok": True, "categoria_falha": None},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8d Genial Lives falha generica -> exit 1", codigo == 1, f"(codigo={codigo})")


def test_8e_falha_de_persistencia_sempre_exit_1_independente_da_classificacao():
    """Item 5 da missao: falha de persistencia (itens coletados,
    'salvou=False') tem que SEMPRE derrubar o exit code, independente de
    qualquer classificacao de erro de coleta - aqui simulada com
    categoria_falha='erro' (o valor real que coletar_todas_disponiveis
    produziria pra essa casa, ja' que o FETCH teve sucesso - ver
    test_research_classificacao_falha.py:test_2d, que prova isso usando
    o modulo xp.py de verdade)."""
    resultado = {
        "XP Investimentos": {"coletados": 5, "ok": False, "categoria_falha": "erro"},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8e falha de persistencia -> exit 1", codigo == 1, f"(codigo={codigo})")


def test_8f_todas_as_casas_falham_so_com_bloqueio_externo_conhecido_exit_0():
    """Item 7 da missao: TODAS as casas falhando, mas EXCLUSIVAMENTE com
    motivo classificado como bloqueio externo ja documentado -> exit
    code 0, coerente com a politica definida (nenhuma regressao real,
    so' os bloqueios cronicos de sempre)."""
    resultado = {
        "XP Investimentos": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
        "Genial Analisa": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8f todas bloqueadas (conhecido) -> exit 0", codigo == 0, f"(codigo={codigo})")


def test_8g_sucesso_do_btg_e_outras_casas_sem_regressao_exit_0():
    """Item 8 da missao: caminho feliz (BTG implementado nesta auditoria
    + XP/Genial Analisa bloqueadas como sempre + Genial Lives OK) ->
    exit 0, sem regressao no caso tipico de producao."""
    resultado = {
        "BTG Pactual Research": {"coletados": 26, "ok": True, "categoria_falha": None},
        "Genial (Lives)": {"coletados": 6, "ok": True, "categoria_falha": None},
        "XP Investimentos": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
        "Genial Analisa": {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"},
    }
    codigo = _rodar_main_com_resultado_research(resultado)
    _checar("8g caminho tipico de producao -> exit 0", codigo == 0, f"(codigo={codigo})")


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


def _rodar_main_news(stats_news: dict, diagnostico_ok: bool = True) -> int:
    stats_eventos = {"processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
                     "tempo_esgotado": False, "tabela_disponivel": True}
    with patch.object(coletor_local, "diagnosticar_persistencia",
                      return_value={"ok": diagnostico_ok, "etapa": "OK" if diagnostico_ok else "INSERT", "detalhe": "x"}), \
         patch.object(coletor_local, "coletar_todas_disponiveis", return_value={}), \
         patch.object(coletor_local, "obter_documentos_watchlist", return_value=([], [])), \
         patch.object(coletor_local, "_universo_rotativo", return_value=[]), \
         patch.object(coletor_local, "apagar_itens_antigos", return_value=0), \
         patch.object(coletor_local, "coletar_snapshot_genial", return_value=(0, 0)), \
         patch.object(coletor_local, "pregerar_resumos_news", return_value=stats_news), \
         patch.object(coletor_local, "coletar_eventos_universo", return_value=stats_eventos), \
         patch.object(coletor_local, "salvar_snapshot_calendario", return_value=True), \
         patch.object(coletor_local, "registrar_tentativa"):
        return coletor_local.main()


def test_8a_imagens_de_news_rodam_mesmo_sem_groq(mock_pregerar_imagens):
    """2026-10-19: a etapa de fotos não depende da IA - sem GROQ_API_KEY
    (resumos pulados) ela continua rodando."""
    stats_news = dict(_STATS_NEWS_VAZIO, indisponiveis=0, groq_configurado=False)
    codigo = _rodar_main_news(stats_news)
    _checar("8a pregerar_imagens_news chamado sem Groq", mock_pregerar_imagens.call_count == 1)
    _checar("8b exit code 0", codigo == 0, f"(codigo={codigo})")


def test_8c_imagens_nao_rodam_com_persistencia_quebrada(mock_pregerar_imagens):
    _rodar_main_news(dict(_STATS_NEWS_VAZIO), diagnostico_ok=False)
    _checar("8c sem persistência, etapa de imagens não roda (nada pra gravar)", mock_pregerar_imagens.call_count == 0)


def test_8d_excecao_nas_imagens_nao_derruba_o_coletor(mock_pregerar_imagens):
    mock_pregerar_imagens.side_effect = RuntimeError("falha inesperada")
    codigo = _rodar_main_news(dict(_STATS_NEWS_VAZIO, indisponiveis=0))
    _checar("8d exceção na etapa de imagens não muda o exit code", codigo == 0, f"(codigo={codigo})")
