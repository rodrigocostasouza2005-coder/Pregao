# -*- coding: utf-8 -*-
"""Testes de ui/cvm_tab.py (modal de documento). Cobre 1 achado real da
auditoria 360 (2026-10-18, docs/auditoria-redesign-360.md): o modal
"DOCUMENTO CVM" mostra um resumo gerado por IA (data/cvm.py:
obter_resumo_documento, "baixa+extrai+resume via Groq, sempre em
palavras proprias") sob um rotulo so' "Resumo" - sem nenhuma indicacao
visivel de que o texto foi sintetizado por IA, logo acima do botao
"ABRIR DOCUMENTO" que leva ao documento oficial de verdade. Um usuario
pode ler o "resumo" como se fosse um trecho/sintese oficial do proprio
documento da CVM.

st.dialog preserva __wrapped__ (a funcao original, sem o decorador) -
mesmo padrao ja usado em tests/test_radar_tab_fontes_ui.py pra testar
_abrir_card sem precisar de uma sessao Streamlit real. st.markdown/
st.caption/st.spinner/st.link_button funcionam em "bare mode" sem
lancar excecao (mesmo padrao dos outros testes de UI deste projeto).

Uso: pytest tests/test_cvm_ui.py (venv do projeto)."""
from unittest.mock import patch

import ui.cvm_tab as cvm_tab_mod

_DOC = {
    "assunto": "Resultado do 3T26", "ticker": "PETR4", "data": "2026-10-10T10:00:00-03:00",
    "categoria_original": "Resultados", "tipo": "RESULTADOS", "tipo_label": "RESULTADOS",
    "link": "https://cvm.gov.br/doc/123",
}


def test_modal_cvm_rotula_o_resumo_como_gerado_por_ia():
    resumo = {"resumo": "A empresa reportou lucro liquido de R$ 1 bilhao no trimestre.", "motivo_indisponivel": None}
    capturado = []
    with patch.object(cvm_tab_mod, "obter_resumo_documento", return_value=resumo), \
         patch.object(cvm_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)), \
         patch.object(cvm_tab_mod.st, "caption"), patch.object(cvm_tab_mod.st, "link_button"), \
         patch.object(cvm_tab_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        cvm_tab_mod._abrir_card.__wrapped__(_DOC)
    rotulo = next((c for c in capturado if "esumo" in c and "cinza" in c), None)
    _checar_contem_ia = rotulo is not None and ("IA" in rotulo or "Inteligência Artificial" in rotulo.upper())
    assert rotulo is not None, f"rotulo do Resumo nao encontrado (capturado={capturado})"
    assert _checar_contem_ia, (
        "o rotulo do bloco de resumo precisa indicar que o texto foi gerado por IA "
        f"(achado real da auditoria 360) - rotulo atual: {rotulo!r}"
    )


def test_modal_cvm_sem_resumo_disponivel_nao_quebra():
    resumo = {"resumo": None, "motivo_indisponivel": "indisponivel"}
    with patch.object(cvm_tab_mod, "obter_resumo_documento", return_value=resumo), \
         patch.object(cvm_tab_mod.st, "markdown"), patch.object(cvm_tab_mod.st, "caption") as mock_caption, \
         patch.object(cvm_tab_mod.st, "link_button"), patch.object(cvm_tab_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        cvm_tab_mod._abrir_card.__wrapped__(_DOC)
    assert any("indisponível" in str(c.args[0]) for c in mock_caption.call_args_list)
