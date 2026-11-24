# -*- coding: utf-8 -*-
"""Perfil da Empresa (ui/coordenador_tab.py:render_perfil_empresa_tab) -
pedido literal do Rodrigo: "eu queria que tivesse a opinião do analistas,
quando eu fosse ver o preço atual da empresa, gostaria de um resumo da
história e do momento que ela está passando". data/empresa_perfil.py:
obter_perfil_empresa já existia pronto e testado (tests/
test_empresa_perfil.py) mas nunca era referenciado em nenhuma tela até a
missão perfil-empresa-ui-20261118 - esta mudança só liga a UI nova nesse
dado já existente, sem tocar a camada de dados.

Missão "aba própria" (pedido explícito do Rodrigo, 2026-11-23): o painel
viveu dentro de um st.expander em COMITÊ > Histórico (via
_render_consolidado) entre 2026-11-18 e 2026-11-23; foi extraído pra aba
própria/independente - ANÁLISES > Perfil da Empresa (ver ui/navegacao.py
e app.py rota ("analises", "perfil")). A função foi renomeada de
_render_perfil_empresa (privada) pra render_perfil_empresa_tab (pública);
o conteúdo renderizado (identificação/momento atual/posicionamento/
notícias) não mudou - só deixou de ficar dentro de um expander (agora é
a própria página, dentro de um st.container(border=True) com
painel-titulo, mesmo padrão visual de ANÁLISES > Fundamentos).

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
         patch.object(tab.st, "info", side_effect=_guardar), \
         patch.object(tab.st, "container") as mock_container:
        mock_container.return_value.__enter__ = lambda self: self
        mock_container.return_value.__exit__ = lambda self, *a: False
        fn(*args, **kwargs)
    return " ".join(textos)


# ============================================================
# Fixture realista - shape real que data/empresa_perfil.py:
# obter_perfil_empresa devolve (ver docstring do módulo pro shape
# completo); só as chaves que render_perfil_empresa_tab de fato lê.
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
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "PERFIL DA EMPRESA" in textos
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
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "Posicionamento competitivo" in textos
    assert "Posição competitiva" in textos
    assert "líder de mercado em refino" in textos
    assert "Vantagens competitivas" in textos
    assert "custo de extração no pré-sal" in textos


def test_perfil_disponivel_mostra_ate_5_noticias_recentes():
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "Notícias recentes" in textos
    assert "Petrobras anuncia novo plano de investimentos" in textos
    assert "Petrobras eleva produção de óleo no 4T26" in textos
    assert "CONFIRMADA" in textos


# ============================================================
# Consenso entre casas de research - achado real (auditoria de
# continuação, 2026-11-23): data/empresa_perfil.py já calculava
# dispersão/divergência/evolução histórica dentro da chave 'research',
# mas esta tela nunca lia isso. _render_perfil_research_consenso é o
# fechamento desse gap - mostra só o que já existe, nunca recalcula.
# ============================================================

def test_research_disponivel_mostra_dispersao_divergencia_e_mudanca_hoje():
    perfil = _perfil_disponivel()
    perfil["research"] = {
        "disponivel": True, "motivo": None, "casas": ["BTG", "XP"],
        "indicadores_adicionais": None,
        "dispersao_precos_alvo": {
            "moeda": "BRL", "amostra_insuficiente": False,
            "minimo": 30.0, "mediana": 34.0, "maximo": 40.0,
            "resumo": "calculado com 2 de 2 casa(s) cobrindo o ticker.",
        },
        "divergencia_recomendacao": {
            "numerica": True, "n_casas_com_preco_alvo": 2, "qualitativa": True,
            "amostra_insuficiente_qualitativa": False,
            "casa_mais_otimista": "BTG", "casa_mais_cautelosa": "XP",
            "criterio_otimismo": "preco_alvo (maior/menor preco-alvo numerico entre as casas com esse dado - BRL)",
        },
        "divergencia_premissas": None,
        "evolucao_historica": {
            "BTG": {"mudou_recomendacao_ou_alvo_hoje": True},
            "XP": {"mudou_recomendacao_ou_alvo_hoje": False},
        },
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "Consenso entre casas de research" in textos
    assert "mediano" in textos.lower() or "mediana" in textos.lower()
    assert "calculado com 2 de 2 casa(s)" in textos
    assert "Mais otimista: BTG" in textos
    assert "Mais cautelosa: XP" in textos
    assert "Mudou recomendação ou preço-alvo hoje: BTG." in textos


def test_research_amostra_insuficiente_mostra_apenas_resumo_sem_tabela():
    perfil = _perfil_disponivel()
    perfil["research"] = {
        "disponivel": True, "motivo": None, "casas": ["BTG"],
        "indicadores_adicionais": None,
        "dispersao_precos_alvo": {
            "moeda": "BRL", "amostra_insuficiente": True,
            "minimo": 30.0, "mediana": 30.0, "maximo": 30.0,
            "resumo": "apenas 1 de 1 casa(s) com preco-alvo numerico - dispersao nao e significativa com 1 dado so'.",
        },
        "divergencia_recomendacao": {
            "numerica": False, "n_casas_com_preco_alvo": 1, "qualitativa": False,
            "amostra_insuficiente_qualitativa": True,
            "casa_mais_otimista": None, "casa_mais_cautelosa": None, "criterio_otimismo": None,
        },
        "divergencia_premissas": None, "evolucao_historica": {},
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "dispersao nao e significativa com 1 dado so" in textos
    assert "Mais otimista:" not in textos
    assert "Mudou recomendação" not in textos


def test_research_disponivel_sem_nenhuma_casa_mostra_motivo_em_vez_de_secao_vazia():
    """disponivel=True com 0 casas (ver data/research/comparador.py:
    comparar_ticker - banco respondeu, zero publicação estruturada pra
    esse ticker) - dispersão/divergência/evolução nem existem nesse
    caso real; a seção precisa mostrar o motivo, nunca ficar vazia em
    silêncio (pareceria sucesso sem dado)."""
    perfil = _perfil_disponivel()
    perfil["research"] = {
        "disponivel": True, "ticker": "PETR4", "casas": [],
        "motivo": "sem publicacoes estruturadas para este ticker na biblioteca permanente de research",
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "sem publicacoes estruturadas para este ticker" in textos


def test_research_indisponivel_mostra_motivo_literal():
    perfil = _perfil_disponivel()
    perfil["research"] = {
        "disponivel": False, "motivo": "banco de research indisponivel no momento",
        "casas": [], "indicadores_adicionais": None, "dispersao_precos_alvo": None,
        "divergencia_recomendacao": None, "divergencia_premissas": None, "evolucao_historica": None,
    }
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "Consenso entre casas de research" in textos
    assert "banco de research indisponivel no momento" in textos


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
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "yfinance não retornou resumo institucional para este ticker." in textos
    assert "A Petrobras é uma das maiores produtoras" not in textos
    # Sem setor/indústria/país, nenhum metadado vazio ("Setor: None") deve aparecer.
    assert "Setor:" not in textos and "Indústria:" not in textos and "País:" not in textos


def test_noticias_indisponiveis_mostra_mensagem_honesta_sem_lista_vazia():
    perfil = _perfil_disponivel()
    perfil["noticias_disponivel"] = False
    perfil["noticias_recentes"] = []
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
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
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "O que quebraria a tese" in textos
    assert "Disponível, mas sem trecho de risco estruturado associado." in textos


def test_conteudo_malicioso_em_evidencia_e_noticia_e_escapado():
    perfil = _perfil_disponivel()
    payload = "<script>alert(1)</script>"
    perfil["perguntas"]["riscos"]["evidencias"][0]["texto"] = payload
    perfil["noticias_recentes"][0]["titulo"] = payload
    with patch.object(tab, "obter_perfil_empresa", return_value=perfil):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "<script>alert(1)</script>" not in textos
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in textos


def test_pergunta_indisponivel_mostra_motivo_literal_da_camada_de_dados():
    with patch.object(tab, "obter_perfil_empresa", return_value=_perfil_disponivel()):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
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
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "Pressões sobre a margem" in textos
    assert "sem trecho de research estruturado associado" in textos


# ============================================================
# Degradação: exceção na chamada e ausência de ticker.
# ============================================================

def test_excecao_ao_obter_perfil_nao_quebra_e_mostra_mensagem_honesta():
    with patch.object(tab, "obter_perfil_empresa", side_effect=Exception("timeout ao consultar yfinance")):
        textos = _capturar(tab.render_perfil_empresa_tab, "PETR4")
    assert "PERFIL DA EMPRESA" in textos
    assert "indisponível" in textos.lower()
    assert "timeout ao consultar yfinance" in textos


def test_sem_ticker_mostra_aviso_e_nao_chama_obter_perfil():
    """Como aba própria (ANÁLISES > Perfil da Empresa), ausência de
    ticker precisa de um aviso explícito - não pode mais ficar
    silenciosa como ficava dentro do expander em COMITÊ (lá, a seção
    inteira era condicionada a 'if ticker:' no chamador, nunca chegava
    a esta função sem ticker; aqui ela é chamada direto pelo app.py e
    precisa se defender)."""
    with patch.object(tab, "obter_perfil_empresa") as mock_obter:
        textos_none = _capturar(tab.render_perfil_empresa_tab, None)
        textos_vazio = _capturar(tab.render_perfil_empresa_tab, "")
    assert not mock_obter.called
    assert "Selecione um ticker para ver o perfil da empresa." in textos_none
    assert "Selecione um ticker para ver o perfil da empresa." in textos_vazio


# ============================================================
# _render_consolidado não mexe mais com perfil da empresa - extraído
# pra aba própria (ver topo do arquivo).
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


def test_render_consolidado_nao_renderiza_mais_perfil_da_empresa_extraido_para_aba_propria():
    """Perfil da Empresa saiu do expander dentro de COMITÊ e virou aba
    própria (ANÁLISES > Perfil da Empresa, ver app.py rota
    ("analises", "perfil") e tab.render_perfil_empresa_tab) - pedido
    explícito do Rodrigo, 2026-11-23. _render_consolidado (usado por
    COMITÊ > Histórico e VALUATION > Simulador DCF) não deve mais tocar
    nenhuma função de perfil, nem a camada de dados."""
    with patch.object(tab, "_render_cabecalho_decisao"), \
         patch.object(tab, "_render_sintese_final"), \
         patch.object(tab, "obter_perfil_empresa") as mock_obter, \
         patch.object(tab.st, "markdown"):
        tab.render_consolidado(_consolidado_minimo(ticker="PETR4", ticker_pareceres="VALE3"))
    assert not mock_obter.called


def test_render_perfil_empresa_privada_nao_existe_mais():
    """Prova de remoção real (não só código morto): o nome antigo,
    privado, não deve mais existir no módulo - só render_perfil_empresa_tab
    (público), chamado por app.py."""
    assert not hasattr(tab, "_render_perfil_empresa")
    assert hasattr(tab, "render_perfil_empresa_tab")
