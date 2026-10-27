# -*- coding: utf-8 -*-
"""ANÁLISES › Empresas - síntese executiva de equity research
(ui/analises_tab.py:render_equity_research_executivo, integra
data/market_researcher.py:analise_ticker). Bare mode (sem
ScriptRunContext), mesmo padrão de tests/test_radar_tab_fontes_ui.py."""
from datetime import date
from unittest.mock import MagicMock, patch

import ui.analises_tab as analises_mod

_PREFS = {"formato_numerico": "BR"}


def _analise(fundamentos=None, catalisadores=None, mudancas=None, riscos=None,
             cobertura=None, fontes_indisponiveis=None):
    return {
        "ticker": "WEGE3", "fundamentos": fundamentos, "catalisadores": catalisadores,
        "mudancas_tese": mudancas, "riscos_indicadores": riscos,
        "cobertura_research": cobertura, "fontes_indisponiveis": fontes_indisponiveis or [],
    }


def _capturar_render(analise=None, levanta=None):
    blocos = []
    col_mock = MagicMock()

    with patch.object(analises_mod, "_analise_ticker_cacheada",
                       side_effect=levanta if levanta else lambda t: analise), \
         patch.object(analises_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "caption", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "warning", side_effect=lambda texto, **_k: blocos.append(str(texto))), \
         patch.object(analises_mod.st, "columns", return_value=[col_mock] * 4), \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_equity_research_executivo("WEGE3", _PREFS)
    return "\n".join(blocos), col_mock


def test_fonte_indisponivel_avisa_e_nunca_lanca_excecao():
    html_render, _ = _capturar_render(levanta=lambda t: (_ for _ in ()).throw(RuntimeError("Supabase fora do ar")))
    assert "indisponível agora" in html_render


def test_tudo_ausente_mostra_estados_honestos_sem_inventar():
    analise = _analise()
    html_render, col_mock = _capturar_render(analise)
    assert "Fundamentos indisponíveis agora" in html_render
    assert "Catalisadores indisponíveis agora" in html_render
    assert "Mudanças de tese indisponíveis agora" in html_render
    assert "Cobertura de research indisponível agora" in html_render
    col_mock.metric.assert_not_called()


def test_listas_vazias_sao_diferentes_de_indisponivel():
    """[] (fonte respondeu, sem dado) é um estado diferente de None
    (fonte indisponível) - nunca a mesma mensagem pros dois."""
    analise = _analise(catalisadores=[], mudancas=[], riscos=[],
                       cobertura={"cobertura": [], "sem_cobertura": ["BTG Research"], "divergencia": None})
    html_render, _ = _capturar_render(analise)
    assert "Nenhum catalisador" in html_render
    assert "Nenhuma mudança de tese/CVM verificada" in html_render
    assert "Nenhuma casa monitorada publicou research recente" in html_render
    assert "Sem cobertura recente: BTG Research" in html_render
    assert "indisponível" not in html_render.lower().replace("recente", "")  # nao confunde "sem dado" com "fonte fora"


def test_cobertura_com_banco_indisponivel_nunca_aparece_como_sem_pesquisa():
    """Regressão (Fase 2, validação real com WEGE3/PETR4 - 23/10/2026):
    cobertura_research["cobertura"] é None quando o PRÓPRIO banco de
    research está fora do ar (ver data/market_researcher.py:
    cobertura_cruzada_casas) - a 1ª versão confundia isso com "nenhuma
    casa publicou", escondendo que a fonte nem respondeu. Reproduzido
    de verdade: Supabase indisponível no ambiente de teste fazia
    cobertura_research vir {"cobertura": None, ...} com os outros 3
    blocos (fundamentos/catalisadores) normais."""
    analise = _analise(fundamentos={"pl": 10.0, "alerta_qualidade": []}, catalisadores=[],
                       cobertura={"cobertura": None, "sem_cobertura": [], "divergencia": None})
    html_render, _ = _capturar_render(analise)
    assert "Cobertura de research indisponível agora" in html_render
    assert "Nenhuma casa monitorada publicou research recente" not in html_render


def test_fundamentos_reais_preenchem_metric_e_mostram_alerta():
    fundamentos = {"pl": 28.5, "pvp": 9.1, "roe": 32.0, "divida_liquida_ebitda": 0.3,
                   "alerta_qualidade": ["P/L negativo"]}
    analise = _analise(fundamentos=fundamentos)
    html_render, col_mock = _capturar_render(analise)
    assert col_mock.metric.call_count == 4
    assert "P/L negativo" in html_render


def test_catalisador_nao_confirmado_nunca_aparece_como_confirmado():
    catalisador = {"categoria": "Resultado corporativo", "data": date(2026, 11, 14), "confirmado": False}
    analise = _analise(catalisadores=[catalisador])
    html_render, _ = _capturar_render(analise)
    assert "estimado/prazo regulatório" in html_render
    assert "Resultado corporativo em 14/11/2026 (confirmado)" not in html_render


def test_mudanca_de_tese_cita_fonte_e_data_real():
    mudanca = {"data_evento": date(2026, 10, 20), "descricao": "Genial revisou WEGE3 para COMPRA",
               "fonte_label": "Genial Analisa", "fonte_url": "https://genial.com.br"}
    analise = _analise(mudancas=[mudanca])
    html_render, _ = _capturar_render(analise)
    assert "20/10/2026" in html_render and "Genial revisou WEGE3 para COMPRA" in html_render
    assert "genial.com.br" in html_render


def test_divergencia_de_recomendacao_aparece_como_aviso():
    cobertura = {"cobertura": [{"casa": "Genial Analisa", "data": "2026-10-20", "titulo": "t",
                                "link": "https://a", "recomendacao": "COMPRA"}],
                 "sem_cobertura": [], "divergencia": {"por_casa": {"Genial Analisa": "COMPRA", "XP Investimentos": "VENDA"}}}
    analise = _analise(cobertura=cobertura)
    html_render, _ = _capturar_render(analise)
    assert "Genial Analisa: COMPRA" in html_render and "XP Investimentos: VENDA" in html_render


def test_fontes_indisponiveis_sao_listadas_explicitamente():
    analise = _analise(fontes_indisponiveis=["fundamentos", "cobertura_research"])
    html_render, _ = _capturar_render(analise)
    assert "Indisponível nesta execução: fundamentos, cobertura_research" in html_render


def test_nunca_exibe_recomendacao_ou_preco_alvo_como_do_pregao():
    html_render, _ = _capturar_render(_analise())
    assert "ESTIMATIVA DE TERCEIRO" in html_render
    assert "nunca uma recomendação ou preço-alvo do Pregão" in html_render


def test_analise_ticker_cacheada_nao_recalcula_dentro_do_ttl():
    """Fase 2 (desempenho): abrir a mesma tela 2x pro mesmo ticker nunca
    deve rodar analise_ticker() (e os 3 módulos que ele agrega) de
    novo dentro do TTL - st.cache_data real (bare mode), não mockado."""
    chamadas = []

    def _fake(ticker, janela="7 DIAS"):
        chamadas.append(ticker)
        return _analise()

    with patch.object(analises_mod, "analise_ticker", side_effect=_fake):
        analises_mod._analise_ticker_cacheada.clear()
        analises_mod._analise_ticker_cacheada("WEGE3_CACHE_TESTE")
        analises_mod._analise_ticker_cacheada("WEGE3_CACHE_TESTE")
    assert chamadas == ["WEGE3_CACHE_TESTE"]  # só 1 chamada real pros 2 acessos


# ============================================================
# COMPARATIVO SETORIAL DE MÚLTIPLOS (2026-10-27) - botão em "Momento
# da empresa" que abre _dialog_comparativo_setor_empresa, reaproveitando
# data/radar.py:comparaveis_setor (mesma função usada em RADAR › Valuation).
# ============================================================

def test_botao_comparativo_setor_nao_aparece_sem_fundamentos():
    """Sem fundamentos, a seção inteira já diz 'indisponível agora' - não
    faz sentido oferecer comparação setorial do que não existe."""
    analise = _analise()
    with patch.object(analises_mod, "_analise_ticker_cacheada", return_value=analise), \
         patch.object(analises_mod.st, "markdown"), patch.object(analises_mod.st, "caption"), \
         patch.object(analises_mod.st, "button") as mock_button, \
         patch.object(analises_mod.st, "columns", return_value=[MagicMock()] * 4), \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_equity_research_executivo("WEGE3", _PREFS)
    mock_button.assert_not_called()


def test_botao_comparativo_setor_abre_dialogo_quando_clicado():
    fundamentos = {"pl": 10.0, "pvp": 1.5, "roe": 12.0, "divida_liquida_ebitda": 1.0, "alerta_qualidade": []}
    analise = _analise(fundamentos=fundamentos)
    with patch.object(analises_mod, "_analise_ticker_cacheada", return_value=analise), \
         patch.object(analises_mod.st, "markdown"), patch.object(analises_mod.st, "caption"), \
         patch.object(analises_mod.st, "button", return_value=True), \
         patch.object(analises_mod.st, "columns", return_value=[MagicMock()] * 4), \
         patch.object(analises_mod, "_dialog_comparativo_setor_empresa") as mock_dialog, \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_equity_research_executivo("WEGE3", _PREFS)
    mock_dialog.assert_called_once_with("WEGE3", _PREFS)


def test_botao_comparativo_setor_nao_abre_dialogo_sem_clique():
    fundamentos = {"pl": 10.0, "pvp": 1.5, "roe": 12.0, "divida_liquida_ebitda": 1.0, "alerta_qualidade": []}
    analise = _analise(fundamentos=fundamentos)
    with patch.object(analises_mod, "_analise_ticker_cacheada", return_value=analise), \
         patch.object(analises_mod.st, "markdown"), patch.object(analises_mod.st, "caption"), \
         patch.object(analises_mod.st, "button", return_value=False), \
         patch.object(analises_mod.st, "columns", return_value=[MagicMock()] * 4), \
         patch.object(analises_mod, "_dialog_comparativo_setor_empresa") as mock_dialog, \
         patch.object(analises_mod.st, "container") as container_mock:
        container_mock.return_value.__enter__ = lambda self: self
        container_mock.return_value.__exit__ = lambda *a: False
        analises_mod.render_equity_research_executivo("WEGE3", _PREFS)
    mock_dialog.assert_not_called()


def _capturar_dialog_setor(comp=None, levanta=None):
    """st.dialog preserva __wrapped__ (mesmo padrão de tests/test_cvm_ui.py:
    _abrir_card) - testa o corpo da função sem precisar de sessão real."""
    blocos = []
    with patch.object(analises_mod, "comparaveis_setor",
                       side_effect=levanta if levanta else lambda t: comp), \
         patch.object(analises_mod.st, "markdown", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(analises_mod.st, "caption", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(analises_mod.st, "warning", side_effect=lambda t, **k: blocos.append(str(t))), \
         patch.object(analises_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        analises_mod._dialog_comparativo_setor_empresa.__wrapped__("WEGE3", _PREFS)
    return "\n".join(blocos)


def test_dialog_setor_insuficiente_mostra_aviso_honesto():
    comp = {"insuficiente": True, "motivo": "menos de 3 pares do setor com dado válido",
            "setor": "Bens industriais", "pares_considerados": 1}
    html_render = _capturar_dialog_setor(comp=comp)
    assert "Dado insuficiente" in html_render
    assert "menos de 3 pares" in html_render


def test_dialog_setor_sem_setor_cadastrado_mostra_aviso_honesto():
    comp = {"setor": None, "pares_considerados": 0, "insuficiente": True, "motivo": "ticker sem setor cadastrado"}
    html_render = _capturar_dialog_setor(comp=comp)
    assert "ticker sem setor cadastrado" in html_render


def test_dialog_setor_sucesso_mostra_medianas_e_limitacao():
    comp = {"insuficiente": False, "setor": "Bens industriais", "pares_considerados": 10,
            "pl_mediana": 15.2, "pl_mediana_n": 8, "pvp_mediana": 2.1, "pvp_mediana_n": 7,
            "dy_mediana": 4.5, "dy_mediana_n": 6}
    html_render = _capturar_dialog_setor(comp=comp)
    assert "P/L mediano do setor" in html_render
    assert "P/VP mediano do setor" in html_render
    assert "Dividend yield mediano do setor" in html_render
    assert "8 pares considerados" in html_render
    assert "não é um índice oficial" in html_render
    assert "não é um preço justo nem uma recomendação" in html_render


def test_dialog_setor_metrica_isolada_insuficiente_nao_contamina_as_demais():
    """Mesmo princípio de isolamento por bloco já usado no resto do
    arquivo: 1 métrica sem pares válidos nunca escondo as outras 2 que
    têm dado suficiente."""
    comp = {"insuficiente": False, "setor": "Bens industriais", "pares_considerados": 5,
            "pl_mediana": None, "pl_mediana_n": 1, "pvp_mediana": 2.1, "pvp_mediana_n": 4,
            "dy_mediana": 4.5, "dy_mediana_n": 5}
    html_render = _capturar_dialog_setor(comp=comp)
    assert "P/L" in html_render and "dado insuficiente" in html_render
    assert "P/VP mediano do setor" in html_render
    assert "Dividend yield mediano do setor" in html_render


def test_dialog_setor_fonte_indisponivel_nunca_lanca_excecao():
    html_render = _capturar_dialog_setor(levanta=lambda t: (_ for _ in ()).throw(RuntimeError("yfinance fora do ar")))
    assert "indisponível agora" in html_render
