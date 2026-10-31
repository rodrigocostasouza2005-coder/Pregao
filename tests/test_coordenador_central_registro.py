# -*- coding: utf-8 -*-
"""Registro central de especialistas (data/coordenador_central/registro.py,
Coordenador Central - Fase E). Confirma que o catálogo está completo e
que cada especialista tem todos os campos do contrato (ver docstring do
módulo) - nenhuma chamada de rede/Supabase/IA aqui, só inspeção de
metadado."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.coordenador_central import registro


def test_todos_os_especialistas_esperados_estao_registrados():
    esperados = {
        "comparador", "memoria_research", "analise_ticker", "noticias",
        "calendario", "catalisadores", "resultados_corporativos", "radar_x",
    }
    assert esperados <= set(registro.REGISTRO.keys())


def test_cada_especialista_tem_todos_os_campos_obrigatorios():
    for especialista_id, especialista in registro.REGISTRO.items():
        assert especialista.id == especialista_id
        assert isinstance(especialista.nome, str) and especialista.nome
        assert isinstance(especialista.descricao, str) and especialista.descricao
        assert isinstance(especialista.capacidades, tuple)
        assert isinstance(especialista.pre_requisitos, tuple)
        assert isinstance(especialista.entradas_aceitas, dict)
        assert callable(especialista.funcao)
        assert callable(especialista.extrator_saida)


def test_listar_especialistas_ordenado_por_id():
    lista = registro.listar_especialistas()
    assert [e.id for e in lista] == sorted(e.id for e in lista)


def test_obter_especialista_existente_e_inexistente():
    assert registro.obter_especialista("comparador") is not None
    assert registro.obter_especialista("nao-existe") is None


def test_radar_x_sem_pre_requisito_nunca_removido_do_registro():
    """radar_x está desligado hoje (sem X_BEARER_TOKEN, decisão
    deliberada de custo) - mas continua registrado como especialista
    real, com pre_requisito documentado."""
    radar_x = registro.obter_especialista("radar_x")
    assert radar_x is not None
    assert "X_BEARER_TOKEN" in radar_x.pre_requisitos


def test_memoria_research_declara_pre_requisito_gemini():
    memoria = registro.obter_especialista("memoria_research")
    assert "GEMINI_API_KEY" in memoria.pre_requisitos


def test_comparador_nao_declara_nenhum_pre_requisito():
    comparador = registro.obter_especialista("comparador")
    assert comparador.pre_requisitos == ()


# ============================================================
# Extratores de saída - adaptação do retorno bruto pro contrato comum
# ============================================================

def test_extrator_comparador_indisponivel():
    bruto = {"disponivel": False, "motivo": "banco indisponível"}
    saida = registro._extrair_comparador(bruto)
    assert saida["disponivel"] is False
    assert saida["motivo_indisponivel"] == "banco indisponível"
    assert saida["evidencias"] == []


def test_extrator_comparador_disponivel_com_fontes():
    bruto = {
        "disponivel": True, "resumo_executivo": "resumo x",
        "fontes_evidencias": [{"casa": "Genial", "data_publicacao": "2026-10-01", "link": "l1", "titulo": "t1"}],
    }
    saida = registro._extrair_comparador(bruto)
    assert saida["disponivel"] is True
    assert saida["evidencias"] == [{"fonte": "Genial", "data": "2026-10-01", "link": "l1", "titulo": "t1"}]


def test_extrator_memoria_research_banco_indisponivel():
    bruto = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": "banco de research indisponivel no momento"}
    saida = registro._extrair_memoria_research(bruto)
    assert saida["disponivel"] is False
    assert saida["motivo_indisponivel"] == "banco de research indisponivel no momento"


def test_extrator_memoria_research_sem_publicacoes_mas_banco_ok():
    """Ausência de publicações (banco respondeu, 0 resultado) nunca é
    tratada como indisponibilidade do especialista."""
    bruto = {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}
    saida = registro._extrair_memoria_research(bruto)
    assert saida["disponivel"] is True
    assert saida["evidencias"] == []
    assert "Nenhuma publicação" in saida["resumo"]


def test_extrator_memoria_research_gemini_indisponivel_degrada_sem_quebrar():
    """Sem GEMINI_API_KEY, buscar() ainda devolve resultado
    estrutural/lexical - o especialista continua disponível=True, só com
    o aviso de degradação propagado (nunca motivo_indisponivel=False)."""
    bruto = {
        "resultados": [{"casa": "XP", "data_publicacao": "2026-10-20", "link": "l2", "titulo": "t2", "recomendacao": "COMPRA"}],
        "confianca": "ALTA",
        "aviso": "busca semantica indisponivel - GEMINI_API_KEY nao configurada, mostrando so resultado estrutural/lexical",
    }
    saida = registro._extrair_memoria_research(bruto)
    assert saida["disponivel"] is True
    assert len(saida["evidencias"]) == 1
    assert "GEMINI_API_KEY" in saida["motivo_indisponivel"]


def test_extrator_analise_ticker_todas_fontes_falharam():
    bruto = {"ticker": "PETR4", "fundamentos": None, "catalisadores": [], "cobertura_research": None,
             "fontes_indisponiveis": ["fundamentos", "contexto_mercado", "cobertura_research"]}
    saida = registro._extrair_analise_ticker(bruto)
    assert saida["disponivel"] is False
    assert "fundamentos" in saida["motivo_indisponivel"]


def test_extrator_analise_ticker_parcialmente_disponivel_nunca_inventa_dado_ausente():
    bruto = {
        "ticker": "PETR4", "fundamentos": None, "catalisadores": [],
        "cobertura_research": {"cobertura": [{"casa": "Genial", "data": "2026-10-01", "link": "l", "titulo": "t"}]},
        "fontes_indisponiveis": ["fundamentos"],
    }
    saida = registro._extrair_analise_ticker(bruto)
    assert saida["disponivel"] is True
    assert len(saida["evidencias"]) == 1
    # fundamentos indisponível não aparece como zero/valor inventado em nenhum lugar da saída
    assert 0 not in saida.values()


def test_extrator_noticias_fonte_indisponivel_vs_sem_noticia():
    assert registro._extrair_noticias(None)["disponivel"] is False
    vazio = registro._extrair_noticias([])
    assert vazio["disponivel"] is True
    assert vazio["evidencias"] == []


def test_extrator_calendario_none_e_disponivel():
    indisponivel = registro._extrair_calendario(None)
    assert indisponivel["disponivel"] is False

    disponivel = registro._extrair_calendario({"periodo": "3T26", "status": "PRAZO_CVM", "data": "2026-11-14", "fonte": "CVM", "origem_url": None})
    assert disponivel["disponivel"] is True
    assert disponivel["evidencias"][0]["titulo"] == "3T26"


def test_extrator_resultados_corporativos_indisponivel():
    bruto = {"ticker": "MELI34", "pais": "BR", "disponivel": False, "motivo": "sem CNPJ mapeado"}
    saida = registro._extrair_resultados_corporativos(bruto)
    assert saida["disponivel"] is False
    assert saida["motivo_indisponivel"] == "sem CNPJ mapeado"


def test_extrator_radar_x_sempre_indisponivel_sem_credencial():
    bruto = {"ok": False, "motivo": "sem X_BEARER_TOKEN", "estado": "sem_credencial", "sinais_novos": 0}
    saida = registro._extrair_radar_x(bruto)
    assert saida["disponivel"] is False
    assert saida["motivo_indisponivel"] == "sem X_BEARER_TOKEN"


def test_wrapper_resultados_corporativos_deriva_trimestre_anterior_ao_pendente():
    with patch.object(registro.eventos, "periodo_pendente", return_value=(2026, 3)), \
         patch.object(registro.earnings_reviewer, "montar_nota_br") as mock_nota:
        mock_nota.return_value = {"disponivel": True, "periodo_label": "2T2026"}
        registro._chamar_resultados_corporativos(ticker="PETR4")
        mock_nota.assert_called_once_with("PETR4", 2026, 2)


def test_wrapper_resultados_corporativos_sem_periodo_pendente_nunca_inventa():
    with patch.object(registro.eventos, "periodo_pendente", return_value=None):
        resultado = registro._chamar_resultados_corporativos(ticker="MELI34")
    assert resultado["disponivel"] is False
    assert "período de resultado não identificável" in resultado["motivo"]


def test_wrapper_catalisadores_converte_ticker_em_tupla():
    with patch.object(registro.radar, "catalisadores") as mock_cat:
        mock_cat.return_value = []
        registro._chamar_catalisadores(ticker="vale3")
        mock_cat.assert_called_once_with(("VALE3",), dias_passado=7, dias_futuro=60)
