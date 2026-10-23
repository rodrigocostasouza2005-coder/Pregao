# -*- coding: utf-8 -*-
"""Teste de integração do gate de fidelidade (data/research/qualidade.py)
dentro do fluxo real de `resumir.py:_gerar_resumo` - garante que um
resumo reprovado NUNCA é persistido (`store.salvar_resumo` não é
chamado) e que o motivo exposto à UI é sempre o bucket genérico seguro
('indisponivel'), nunca o texto detalhado do gate (que pode citar um
trecho do resumo). Mesmo padrão de mock de `tests/test_research.py`
(Supabase indisponível -> ia_cache cai direto pro fluxo de geração).

Uso: pytest tests/test_research_resumir_gate.py"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.resumir as resumir_mod
from data.research.resumir import obter_resumo

_TEXTO_ORIGINAL = (
    "A Petrobras divulgou lucro líquido de R$ 12,50 bilhões no terceiro trimestre, "
    "impulsionado por maior produção no pré-sal."
)


def test_resumo_com_numero_inventado_nao_e_persistido():
    chamadas_salvar = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_ORIGINAL, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("A Petrobras reportou lucro recorde de R$ 999,00 bilhões.", None, {"modelo": "modelo-x"})), \
         patch.object(resumir_mod.store, "salvar_resumo", side_effect=lambda *a, **k: chamadas_salvar.append(a)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        resultado = obter_resumo("https://exemplo.com/1", "Petrobras", casa="X", tipo="ACOES")

    assert resultado["resumo"] is None
    assert resultado["motivo_indisponivel"] == "indisponivel"
    assert chamadas_salvar == []


def test_resumo_fiel_passa_normalmente_e_e_persistido():
    chamadas_salvar = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_ORIGINAL, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("A Petrobras reportou lucro de R$ 12,50 bilhões, impulsionado pelo pré-sal.", None, {"modelo": "modelo-x"})), \
         patch.object(resumir_mod.store, "salvar_resumo", side_effect=lambda *a, **k: chamadas_salvar.append(a)) as salvar_mock, \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        resultado = obter_resumo("https://exemplo.com/1", "Petrobras", casa="X", tipo="ACOES")

    assert resultado["resumo"] is not None
    assert resultado["motivo_indisponivel"] is None
    assert salvar_mock.call_count == 1


def test_motivo_detalhado_do_gate_nunca_vaza_pra_ui():
    """O motivo exposto no retorno (o que a UI eventualmente mostra)
    nunca pode conter o trecho citado internamente pelo gate - só o
    bucket genérico 'indisponivel'."""
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(_TEXTO_ORIGINAL, None)), \
         patch.object(resumir_mod, "resumir_com_groq",
                       return_value=("Lucro de R$ 999,00 bilhões, um número claramente inventado.", None, {"modelo": "modelo-x"})), \
         patch.object(resumir_mod.store, "salvar_resumo"), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        resultado = obter_resumo("https://exemplo.com/2", "Petrobras", casa="X", tipo="ACOES")

    assert "999" not in (resultado.get("motivo_indisponivel") or "")
