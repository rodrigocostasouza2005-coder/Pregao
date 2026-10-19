# -*- coding: utf-8 -*-
"""Testes de UI do redesign editorial do card de NEWS (2026-10-19,
ui/news_tab.py:_abrir_card) - pedido do Rodrigo: resumo "visualmente
ruim" e sem análise suficientemente útil. Cobre os cenários pedidos:

1. resumo completo (RESUMO + POR QUE IMPORTA + LEITURA DE MERCADO) -
   rótulo "gerado por IA", seção "Por que importa" e seção "Impacto
   potencial" (nome exibido pro bloco LEITURA DE MERCADO) aparecem.
2. resumo sem POR QUE IMPORTA (fonte não sustentava relevância à parte,
   OU resumo no formato antigo já cacheado antes desta mudança) - seção
   simplesmente não aparece, nunca um rótulo vazio.
3. resumo sem LEITURA DE MERCADO (notícia sem impacto financeiro claro)
   - seção "Impacto potencial" não aparece.
4. resumo ausente (falha do provedor de IA/extração) - motivo exibido,
   nunca quebra.
5. notícia com empresas/tickers identificados - contexto de research e
   vínculos aparecem normalmente (nenhuma mudança de comportamento).

st.dialog preserva __wrapped__ (função original, sem o decorador) -
mesmo padrão já usado em tests/test_cvm_ui.py e
tests/test_radar_tab_fontes_ui.py pra testar um modal sem precisar de
uma sessão Streamlit real (bare mode).

Uso: pytest tests/test_news_card_editorial_v5.py (venv do projeto)."""
from unittest.mock import patch

import ui.news_tab as news_tab_mod

_ITEM_BASE = {
    "titulo": "Alfa revisa plano de investimentos",
    "titulos": ["Alfa revisa plano de investimentos"],
    "veiculos": ["InfoMoney"],
    "fontes": [{"veiculo": "InfoMoney", "link": "https://news.google.com/alfa"}],
    "fontes_count": 1,
    "data": "2026-10-19T10:00:00-03:00",
    "link": "https://news.google.com/alfa",
    "score": 70,
    "selo": "PROVÁVEL",
    "regras": [],
    "cvm_confirmacao": None,
    "tickers": [],
}

_RESUMO_3_BLOCOS = (
    "RESUMO:\nA empresa Alfa anunciou revisão do plano de investimentos para "
    "2027, com corte de capex de R$ 12 bilhões para R$ 9,5 bilhões.\n\n"
    "POR QUE IMPORTA:\nA Alfa responde por 15% da produção nacional da "
    "commodity, então o corte tende a influenciar a oferta agregada do "
    "setor.\n\n"
    "LEITURA DE MERCADO:\nA revisão pode pressionar a margem de fornecedores "
    "da Alfa no curto prazo, a depender do cronograma revisado."
)


def _renderizar(item, resultado_resumo, tickers_watchlist=None):
    """Chama _abrir_card de verdade (sem o decorador @st.dialog) com as
    dependências de rede/IA mockadas - retorna todo o HTML passado a
    st.markdown, concatenado em uma lista (1 string por chamada)."""
    capturado = []
    with patch.object(news_tab_mod, "obter_resumo_grupo", return_value=resultado_resumo), \
         patch.object(news_tab_mod, "_renderizar_capa"), \
         patch.object(news_tab_mod, "obter_recomendacoes", return_value=[]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)), \
         patch.object(news_tab_mod.st, "caption") as mock_caption, \
         patch.object(news_tab_mod.st, "link_button"), \
         patch.object(news_tab_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        news_tab_mod._abrir_card.__wrapped__(item, tickers_watchlist or [])
    return capturado, mock_caption


# ============================================================
# 1. resumo completo com os 3 blocos
# ============================================================

def test_1a_resumo_completo_mostra_rotulo_gerado_por_ia():
    resultado = {"resumo": _RESUMO_3_BLOCOS, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "news-resumo-rotulo" in texto, "rótulo do RESUMO não encontrado"
    rotulo = next(c for c in capturado if "news-resumo-rotulo" in c)
    assert "gerado por ia" in rotulo.lower(), f"rótulo não indica que o texto foi gerado por IA: {rotulo!r}"


def test_1b_resumo_completo_mostra_secao_por_que_importa():
    resultado = {"resumo": _RESUMO_3_BLOCOS, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "Por que importa" in texto
    assert "15% da produção nacional" in texto


def test_1c_resumo_completo_mostra_secao_impacto_potencial_com_nota_de_interpretacao():
    resultado = {"resumo": _RESUMO_3_BLOCOS, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "Impacto potencial" in texto
    assert "Leitura de mercado" not in texto, "rótulo antigo não deveria mais aparecer na UI"
    assert "pressionar a margem de fornecedores" in texto
    assert "não é" in texto and "fato confirmado" in texto, "nota de classificação (interpretação, não fato) ausente"


def test_1d_resumo_completo_mostra_sintese_factual_do_resumo():
    resultado = {"resumo": _RESUMO_3_BLOCOS, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "R$ 9,5 bilhões" in texto


# ============================================================
# 2. resumo sem POR QUE IMPORTA (fonte sem base, ou formato antigo)
# ============================================================

def test_2a_sem_por_que_importa_secao_nao_aparece():
    resumo_sem_importa = (
        "RESUMO:\nA empresa Beta anunciou mudança na diretoria.\n\n"
        "LEITURA DE MERCADO:\nA mudança pode sinalizar reposicionamento "
        "estratégico da companhia."
    )
    resultado = {"resumo": resumo_sem_importa, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "Por que importa" not in texto
    assert "Impacto potencial" in texto, "LEITURA DE MERCADO do formato antigo ainda deve aparecer, renomeada"


def test_2b_formato_antigo_sem_nenhum_marcador_novo_nao_quebra():
    """Resumo cacheado ANTES desta mudança (2026-10-19) - só RESUMO, sem
    LEITURA DE MERCADO nem POR QUE IMPORTA. Precisa renderizar normalmente,
    sem seções extras inventadas."""
    resumo_legado = "RESUMO:\nA empresa Gama é notícia hoje por motivos operacionais."
    resultado = {"resumo": resumo_legado, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "Por que importa" not in texto
    assert "Impacto potencial" not in texto
    assert "motivos operacionais" in texto


# ============================================================
# 3. resumo sem LEITURA DE MERCADO (notícia sem impacto financeiro claro)
# ============================================================

def test_3a_sem_impacto_claro_secao_impacto_potencial_nao_aparece():
    resumo_sem_leitura = (
        "RESUMO:\nA empresa Delta divulgou calendário de pagamento de "
        "dividendos para o próximo trimestre.\n\n"
        "POR QUE IMPORTA:\nO calendário formaliza a data de corte pra quem "
        "detém as ações na data-base."
    )
    resultado = {"resumo": resumo_sem_leitura, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "Por que importa" in texto
    assert "Impacto potencial" not in texto


# ============================================================
# 4. resumo ausente (falha do provedor de IA/extração) - nunca quebra
# ============================================================

def test_4a_resumo_ausente_mostra_motivo_sem_quebrar():
    resultado = {"resumo": None, "imagem": None, "motivo_indisponivel": "GROQ_API_KEY não configurada em st.secrets"}
    capturado, mock_caption = _renderizar(_ITEM_BASE, resultado)
    assert any("news-resumo-rotulo" not in c for c in capturado) or not capturado
    assert any("GROQ_API_KEY" in str(c.args[0]) for c in mock_caption.call_args_list), \
        "motivo da indisponibilidade não foi exibido"


def test_4b_resumo_ausente_sem_motivo_usa_fallback_generico():
    resultado = {"resumo": None, "imagem": None, "motivo_indisponivel": None}
    _, mock_caption = _renderizar(_ITEM_BASE, resultado)
    assert any("motivo desconhecido" in str(c.args[0]) for c in mock_caption.call_args_list)


# ============================================================
# 5. notícia com empresas/tickers identificados - comportamento preservado
# ============================================================

def test_5a_tickers_identificados_nao_afetam_renderizacao_do_resumo():
    item_com_tickers = dict(_ITEM_BASE, tickers=["PETR4", "VALE3"])
    resultado = {"resumo": _RESUMO_3_BLOCOS, "imagem": None, "parcial": False, "motivo_indisponivel": None}
    with patch.object(news_tab_mod, "_vinculos_noticia") as mock_vinculos:
        capturado, _ = _renderizar(item_com_tickers, resultado)
    texto = " ".join(capturado)
    assert "Por que importa" in texto
    assert "Impacto potencial" in texto
    assert mock_vinculos.called, "vínculos (empresa/setor) deveriam ser renderizados quando há tickers"


# ============================================================
# 6. nota de síntese parcial (fallback de manchetes) continua aparecendo
# ============================================================

def test_6a_resumo_parcial_mostra_nota_de_sintese_parcial():
    resumo_parcial = "RESUMO:\nFontes diferentes reportam mudança na diretoria da empresa Épsilon."
    resultado = {"resumo": resumo_parcial, "imagem": None, "parcial": True, "motivo_indisponivel": None}
    capturado, _ = _renderizar(_ITEM_BASE, resultado)
    texto = " ".join(capturado)
    assert "texto completo da matéria não foi acessado" in texto
