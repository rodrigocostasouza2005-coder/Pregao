# -*- coding: utf-8 -*-
"""Perfil da Empresa dentro do COMITÊ (ui/coordenador_tab.py:
_render_perfil_empresa, missão perfil-empresa-ui-20261118) - pedido
literal do Rodrigo: "eu queria que tivesse a opinião do analistas,
quando eu fosse ver o preço atual da empresa, gostaria de um resumo da
história e do momento que ela está passando". data/empresa_perfil.py:
obter_perfil_empresa já existia pronto e testado (tests/
test_empresa_perfil.py) mas nunca era referenciado em nenhuma tela
(código morto confirmado por grep) - esta mudança só liga a UI nova
nesse dado já existente, sem tocar a camada de dados.

Mesmo padrão de captura de tests/test_coordenador_tab_divergencia_comite.py
e tests/test_coordenador_tab_cards_especialistas.py (patch.object(tab.st,
...) pra inspecionar o HTML/texto gerado sem precisar de uma sessão
Streamlit de verdade) - obter_perfil_empresa é mockada via
patch.object(tab, "obter_perfil_empresa", ...) porque é importada direto
(from data.empresa_perfil import obter_perfil_empresa) dentro de
ui/coordenador_tab.py."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.coordenador_tab as tab


def _capturar(fn, *args, **kwargs):
    textos = []

    def _guardar(*a, **k):
        if a:
            textos.append(str(a[0]))

    with patch.object(tab.st, "markdown", side_effect=_guardar), \
         patch.object(tab.st, "caption", side_effect=_guardar), \
         patch.object(tab.st, "expander") as mock_expander:
        mock_expander.return_value.__enter__ = lambda self: self
        mock_expander.return_value.__exit__ = lambda self, *a: False
        fn(*args, **kwargs)
        rotulos_expander = [c.args[0] if c.args else None for c in mock_expander.call_args_list]
    return " ".join(textos), rotulos_expander


# ============================================================
# Fixture realista - shape real que data/empresa_perfil.py:
# obter_perfil_empresa devolve (ver docstring do módulo pro shape
# completo); só as chaves que _render_perfil_empresa de fato lê.
# ============================================================

def _perfil_disponivel(ticker="PETR4"):
    return {
        "ticker": ticker,
        "gerado_em": "2026-11-18T10:00:00+00:00",
        "identificacao": {
            "setor": "Energy", "industria": "Oil & Gas Integrated", "pais": "Brazil",
            "website": "https://petrobras.com.br", "funcionarios": 45000,
            "resumo_negocio": ("A Petrobras é uma das maiores produtoras de petróleo e gás do Brasil, "
                                "atuando em exploração, produção, refino, distribuição e comercialização "
                                "de derivados em todo o território nacional e no exterior."),
            "fonte": "yfinance (tk.info)", "consultado_em": "2026-11-18T09:00:00+00:00", "disponivel": True,
        },
        "indicadores_fundamentalistas": {"moeda": "R$", "roe": 18.4, "margem_liquida": 21.0},
        "research": {
            "disponivel": True, "motivo": None, "casas": ["BTG", "XP"],
            "indicadores_adicionais": None, "dispersao_precos_alvo": None,
            "divergencia_recomendacao": None, "divergencia_premissas": None, "evolucao_historica": None,
        },
        "noticias_recentes": [
            {"titulo": "Petrobras anuncia novo plano de investimentos para o pré-sal", "data": "2026-11-15",
             "link": "https://noticia.com/1", "selo": "CONFIRMADA", "veiculos": ["Valor"]},
            {"titulo": "Petrobras eleva produção de óleo no 4T26", "data": "2026-11-10",
             "link": "https://noticia.com/2", "selo": "PROVÁVEL", "veiculos": ["InfoMoney"]},
        ],
        "noticias_disponivel": True,
        "perguntas": {
            "o_que_a_empresa_faz": {
                "pergunta": "O que a empresa faz?", "fonte_primaria": "yfinance (resumo institucional)",
                "dado": ("A Petrobras é uma das maiores produtoras de petróleo e gás do Brasil, "
                          "atuando em exploração, produção, refino, distribuição e comercialização "
                          "de derivados em todo o território nacional e no exterior."),
                "evidencias": [], "disponivel": True, "motivo_indisponivel": None,
            },
            "como_ganha_dinheiro": {
                "pergunta": "Como a empresa ganha dinheiro?", "fonte_primaria": "yfinance (resumo institucional)",
                "dado": "mesmo resumo institucional", "evidencias": [], "disponivel": True,
                "motivo_indisponivel": None,
            },
            "perspectivas": {
                "pergunta": "Quais são as perspectivas para a empresa?",
                "fonte_primaria": "research (projeções de receita/margem/lucro por casa)",
                "dado": ["Projeção de crescimento de receita de 8% em 2027, puxado pelo pré-sal."],
                "evidencias": [
                    {"casa": "BTG", "texto": "Projeção de crescimento de receita de 8% em 2027, puxado pelo pré-sal.",
                     "data_publicacao": "2026-11-05", "link": "https://btg.com/r1"},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "pressoes_de_margem": {
                "pergunta": "Quais são as pressões sobre a margem da empresa?",
                "fonte_primaria": "yfinance (margens atuais) + research",
                "dado": {"margens_atuais": {"margem_liquida_pct": 21.0}, "evidencias_research": [
                    "Pressão de custo de insumos no refino afeta margem bruta no curto prazo.",
                ]},
                "evidencias": [
                    {"casa": "XP", "texto": "Pressão de custo de insumos no refino afeta margem bruta no curto prazo.",
                     "data_publicacao": "2026-11-01", "link": None},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "riscos": {
                "pergunta": "Quais são os principais riscos identificados para a empresa?",
                "fonte_primaria": "research (campo dedicado 'riscos' por casa)",
                "dado": ["Risco regulatório sobre política de preços de combustíveis."],
                "evidencias": [
                    {"casa": "BTG", "texto": "Risco regulatório sobre política de preços de combustíveis.",
                     "data_publicacao": "2026-11-05", "link": "https://btg.com/r1"},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "o_que_quebraria_a_tese": {
                "pergunta": "O que poderia invalidar/quebrar a tese de investimento?",
                "fonte_primaria": "research (riscos por casa + divergência entre casas)",
                "dado": {
                    "riscos": ["Risco regulatório sobre política de preços de combustíveis."],
                    "divergencia_entre_casas": [
                        {"premissa": "Manutenção da política de preços internacionais de combustíveis",
                         "casas_que_mencionam": ["BTG"], "casas_que_nao_mencionam": ["XP"]},
                    ],
                },
                "evidencias": [
                    {"casa": "BTG", "texto": "Risco regulatório sobre política de preços de combustíveis.",
                     "data_publicacao": "2026-11-05", "link": "https://btg.com/r1"},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "posicao_competitiva": {
                "pergunta": "Qual é a posição competitiva da empresa no setor?",
                "fonte_primaria": "research (premissas/riscos por casa)",
                "dado": ["Petrobras é líder de mercado em refino no Brasil."],
                "evidencias": [
                    {"casa": "XP", "texto": "Petrobras é líder de mercado em refino no Brasil.",
                     "data_publicacao": "2026-11-01", "link": None},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "vantagens_competitivas": {
                "pergunta": "Quais são as vantagens competitivas da empresa?",
                "fonte_primaria": "research (premissas/riscos por casa)",
                "dado": ["Vantagem competitiva em custo de extração no pré-sal."],
                "evidencias": [
                    {"casa": "BTG", "texto": "Vantagem competitiva em custo de extração no pré-sal.",
                     "data_publicacao": "2026-11-05", "link": "https://btg.com/r1"},
                ],
                "disponivel": True, "motivo_indisponivel": None,
            },
            "concorrentes": {
                "pergunta": "Quem são os concorrentes da empresa?",
                "fonte_primaria": "research (premissas/riscos por casa)",
                "dado": [], "evidencias": [], "disponivel": False,
                "motivo_indisponivel": (
                    "nenhuma casa de research monitorada tem publicação com trecho explícito sobre este "
                    "assunto na biblioteca permanente - pode ser que nenhum relatório aborde isso, ou que "
                    "ainda não haja relatório coletado para este ticker"
                ),
            },
        },
    }


# ============================================================
# Caso disponível - texto normal, evidências com atribuição e link.
# ============================================================

def test_perfil_disponivel_mostra_identificacao_metadados_e_momento_atual():
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos, rotulos_expander = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Perfil da empresa — resumo do negócio e momento atual" in rotulos_expander
    assert "O que a empresa faz / como ganha dinheiro" in textos
    assert "A Petrobras é uma das maiores produtoras de petróleo e gás do Brasil" in textos
    assert "Setor: Energy" in textos
    assert "Indústria: Oil &amp; Gas Integrated" in textos or "Oil & Gas Integrated" in textos
    assert "País: Brazil" in textos
    assert "Momento atual" in textos
    assert "Perspectivas" in textos
    assert "Projeção de crescimento de receita de 8% em 2027" in textos
    assert "BTG" in textos
    assert "2026-11-05" in textos
    assert "Pressões sobre a margem" in textos
    assert "Pressão de custo de insumos no refino" in textos
    assert "Principais riscos" in textos
    assert "Risco regulatório sobre política de preços" in textos
    assert "O que quebraria a tese" in textos
    assert "Divergência entre casas sobre a premissa" in textos
    assert "Manutenção da política de preços internacionais" in textos


def test_perfil_disponivel_mostra_posicionamento_competitivo():
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Posicionamento competitivo" in textos
    assert "Posição competitiva" in textos
    assert "líder de mercado em refino" in textos
    assert "Vantagens competitivas" in textos
    assert "custo de extração no pré-sal" in textos


def test_perfil_disponivel_mostra_ate_5_noticias_recentes():
    textos_fixture, _ = _capturar(tab._render_perfil_empresa, None)  # smoke: sem ticker não quebra
    assert textos_fixture == ""
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Notícias recentes" in textos
    assert "Petrobras anuncia novo plano de investimentos" in textos
    assert "Petrobras eleva produção de óleo no 4T26" in textos
    assert "CONFIRMADA" in textos


# ============================================================
# Pergunta indisponível - motivo literal, nunca texto genérico.
# ============================================================

def test_identificacao_indisponivel_mostra_motivo_em_vez_do_resumo():
    perfil = _perfil_disponivel()
    perfil["identificacao"] = {"setor": None, "industria": None, "pais": None,
                                 "website": None, "funcionarios": None, "resumo_negocio": None,
                                 "fonte": None, "consultado_em": None, "disponivel": False}
    perfil["perguntas"]["o_que_a_empresa_faz"] = {
        "pergunta": "O que a empresa faz?", "fonte_primaria": "yfinance (resumo institucional)",
        "dado": None, "evidencias": [], "disponivel": False,
        "motivo_indisponivel": "yfinance não retornou resumo institucional para este ticker.",
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "yfinance não retornou resumo institucional para este ticker." in textos
    assert "A Petrobras é uma das maiores produtoras" not in textos
    # Sem setor/indústria/país, nenhum metadado vazio ("Setor: None") deve aparecer.
    assert "Setor:" not in textos and "Indústria:" not in textos and "País:" not in textos


def test_noticias_indisponiveis_mostra_mensagem_honesta_sem_lista_vazia():
    perfil = _perfil_disponivel()
    perfil["noticias_disponivel"] = False
    perfil["noticias_recentes"] = []
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Não há notícia recente disponível para este ticker no momento." in textos


def test_quebra_tese_disponivel_sem_riscos_nem_divergencia_mostra_nota_honesta():
    perfil = _perfil_disponivel()
    perfil["perguntas"]["o_que_quebraria_a_tese"] = {
        "pergunta": "O que poderia invalidar/quebrar a tese de investimento?",
        "fonte_primaria": "research (riscos por casa + divergência entre casas)",
        "dado": {"riscos": [], "divergencia_entre_casas": []},
        "evidencias": [], "disponivel": True, "motivo_indisponivel": None,
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "O que quebraria a tese" in textos
    assert "Disponível, mas sem trecho de risco estruturado associado." in textos


def test_conteudo_malicioso_em_evidencia_e_noticia_e_escapado():
    perfil = _perfil_disponivel()
    payload = "<script>alert(1)</script>"
    perfil["perguntas"]["riscos"]["evidencias"][0]["texto"] = payload
    perfil["noticias_recentes"][0]["titulo"] = payload
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "<script>alert(1)</script>" not in textos
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in textos


def test_pergunta_indisponivel_mostra_motivo_literal_da_camada_de_dados():
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Concorrentes" in textos
    assert ("nenhuma casa de research monitorada tem publicação com trecho explícito sobre este "
            "assunto na biblioteca permanente") in textos
    # Nunca um texto genérico inventado substituindo o motivo real.
    assert "Dado indisponível para este ticker." not in textos


def test_pergunta_disponivel_sem_evidencias_mostra_nota_honesta_sem_inventar():
    """pressoes_de_margem pode ficar disponivel=True só pelo número
    (margens_atuais), sem nenhum trecho de research - a UI não pode
    inventar um trecho que não existe nem omitir a seção."""
    perfil = _perfil_disponivel()
    perfil["perguntas"]["pressoes_de_margem"] = {
        "pergunta": "Quais são as pressões sobre a margem da empresa?",
        "fonte_primaria": "yfinance (margens atuais)",
        "dado": {"margens_atuais": {"margem_liquida_pct": 21.0}, "evidencias_research": []},
        "evidencias": [], "disponivel": True, "motivo_indisponivel": None,
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos, _ = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Pressões sobre a margem" in textos
    assert "sem trecho de research estruturado associado" in textos


# ============================================================
# Degradação: exceção na chamada e ausência de ticker.
# ============================================================

def test_excecao_ao_obter_perfil_nao_quebra_e_mostra_mensagem_honesta():
    with patch.object(tab, "obter_perfil_empresa", side_effect=Exception("timeout ao consultar yfinance")):
        textos, rotulos_expander = _capturar(tab._render_perfil_empresa, "PETR4")
    assert "Perfil da empresa — resumo do negócio e momento atual" in rotulos_expander
    assert "indisponível" in textos.lower()
    assert "timeout ao consultar yfinance" in textos


def test_sem_ticker_nao_chama_obter_perfil_nem_renderiza_nada():
    with patch.object(tab, "obter_perfil_empresa") as mock_obter:
        textos_none, rotulos_none = _capturar(tab._render_perfil_empresa, None)
        textos_vazio, rotulos_vazio = _capturar(tab._render_perfil_empresa, "")
    assert not mock_obter.called
    assert textos_none == "" and rotulos_none == []
    assert textos_vazio == "" and rotulos_vazio == []


# ============================================================
# Wiring em _render_consolidado - ticker resolvido 1x, mesma lógica de
# fallback de _render_cabecalho_decisao, chamado logo após o cabeçalho.
# ============================================================

def _consolidado_minimo(ticker=None, ticker_pareceres=None):
    consolidado = {
        "sinal_comite": {}, "confianca": {}, "resumo_executivo": "",
        "pareceres_analistas": {"analistas": [], "casas_research": [], "preco_alvo_consenso": {}},
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [], "evidencias": [], "visao_especialistas": {},
    }
    if ticker is not None:
        consolidado["ticker"] = ticker
    if ticker_pareceres is not None:
        consolidado["pareceres_analistas"]["ticker"] = ticker_pareceres
    return consolidado


def test_render_consolidado_chama_perfil_empresa_com_ticker_top_level():
    with patch.object(tab, "_render_cabecalho_decisao"), \
         patch.object(tab, "_render_perfil_empresa") as mock_perfil, \
         patch.object(tab, "_render_sintese_final"), \
         patch.object(tab.st, "markdown"):
        tab._render_consolidado(_consolidado_minimo(ticker="PETR4", ticker_pareceres="VALE3"))
    mock_perfil.assert_called_once_with("PETR4")


def test_render_consolidado_usa_fallback_ticker_de_pareceres_quando_falta_no_topo():
    with patch.object(tab, "_render_cabecalho_decisao"), \
         patch.object(tab, "_render_perfil_empresa") as mock_perfil, \
         patch.object(tab, "_render_sintese_final"), \
         patch.object(tab.st, "markdown"):
        tab._render_consolidado(_consolidado_minimo(ticker_pareceres="VALE3"))
    mock_perfil.assert_called_once_with("VALE3")


def test_render_consolidado_sem_ticker_nenhum_nao_chama_perfil_empresa():
    with patch.object(tab, "_render_cabecalho_decisao"), \
         patch.object(tab, "_render_perfil_empresa") as mock_perfil, \
         patch.object(tab, "_render_sintese_final"), \
         patch.object(tab.st, "markdown"):
        tab._render_consolidado(_consolidado_minimo())
    assert not mock_perfil.called
