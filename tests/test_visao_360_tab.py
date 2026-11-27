# -*- coding: utf-8 -*-
"""ANÁLISES > Visão 360 (ui/visao_360_tab.py:render_visao_360).

Criado na missão visao-360-empresa-20261124 e reescrito na missão
visao-360-redesign-20261126 (redesign completo da tela de análise de 1
ativo). A tela continua sendo COMPOSIÇÃO de peças testadas isoladamente em
outros arquivos (render_perfil_* e render_parecer_especialista em
tests/test_coordenador_tab_perfil_empresa.py e
tests/test_coordenador_tab_cards_especialistas.py, controle_dcf_inline em
tests/test_analises_conclusao_investimento_ui.py, render_sintese_final em
tests/test_coordenador_tab_divergencia_comite.py) - este arquivo cobre a
ORQUESTRAÇÃO e as regras de APRESENTAÇÃO que o redesign introduziu, via
streamlit.testing.v1.AppTest real (mesmo padrão de
tests/test_smoke_todas_abas.py: script mínimo que chama DIRETO
render_visao_360, nunca app.py, que exige login Google real).

Mocks ficam no atributo do MÓDULO que de fato chama a fonte:
ui.visao_360_tab para obter_cotacao/obter_indicadores/linha_valuation/
listar_analises_por_ticker/obter_analise/_contexto_cacheado, e
ui.coordenador_tab para obter_perfil_empresa (importado direto lá, nunca
em ui/visao_360_tab.py).

Achados de desenho que esta suíte prova (pedidos explícitos do Rodrigo):
1. listar_analises_por_ticker devolvendo [] ("nunca analisado") e None
   ("Supabase indisponível, não dá pra saber") são avisos DIFERENTES - a
   UI nunca pode tratar os dois como a mesma coisa.
2. Recomendação e CONFIANÇA são coisas distintas: "COMPRA" com confiança
   BAIXA tem que carregar um aviso próprio de evidência fraca, nunca
   passar a mesma sensação de segurança de uma recomendação robusta.
3. Detalhe técnico de falha (repr de exceção, nome de coluna, SQL) nunca
   chega à tela - só o fato de a fonte não ter respondido.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit.testing.v1 import AppTest

import ui.visao_360_tab as v360

_RAIZ = str(Path(__file__).parent.parent)


@pytest.fixture(autouse=True)
def _limpa_cache_comite():
    """_carregar_comite ganhou @st.cache_data (correção de performance -
    ver test_carregar_comite_e_cacheado_nao_bate_supabase_em_toda_rerun).
    O cache é por processo, não por AppTest.run(), então sem limpar aqui
    um teste que roda PETR4 primeiro "vence" e deixa os testes seguintes
    lendo o resultado cacheado do teste anterior em vez do mock dele
    próprio - cada teste deste arquivo usa o mesmo ticker PETR4 de
    propósito (ver _script())."""
    v360._carregar_comite.clear()
    yield
    v360._carregar_comite.clear()


def _roda(script: str):
    at = AppTest.from_string(script, default_timeout=60).run()
    assert not at.exception, f"AppTest lançou exceção: {at.exception}"
    return at


def _textos(at) -> str:
    partes = [m.value for m in at.markdown] + [c.value for c in at.caption]
    for bloco in (at.info, at.warning, at.error, at.success):
        partes += [b.value for b in bloco]
    return " ".join(partes)


def _tem_rotulo(at, trecho: str) -> bool:
    """Um botão de navegação (ui/navegacao.py:link) vira st.button() de
    verdade OU, se o Streamlit recusar por engano um contexto de form que
    não existe de fato aqui, um link HTML puro (ver docstring de link) -
    os dois são formas válidas do CTA aparecer pro usuário; checa as duas,
    nunca assume qual delas o Streamlit escolheu neste processo."""
    if any(trecho in b.label for b in at.button):
        return True
    return trecho in _textos(at)


_COT_OK = {
    "ticker": "PETR4", "preco": 38.5, "fechamento_anterior": 37.9,
    "cotacao_em": "2026-11-24T18:00:00+00:00",
    "tipo_cotacao": "ATRASADA (Yahoo Finance; atraso pode variar)",
    "variacao": 0.6, "variacao_pct": 1.58, "maxima_dia": 38.9, "minima_dia": 37.8,
    "volume": 1_000_000, "maxima_52s": 42.0, "minima_52s": 30.0, "erro": None,
}

_LINHA_OK = {
    "ticker": "PETR4", "setor": "Energy", "moeda": "R$", "moeda_fonte": "yfinance",
    "preco": 38.5, "preco_erro": None, "consultado_em": "2026-11-24T18:00:00+00:00",
    "pl": 6.2, "pvp": 1.1, "dividend_yield": 12.4, "roe": 24.3, "margem_liquida": 18.0,
    "divida_liquida_ebitda": 1.2, "valor_mercado": 500_000_000_000.0, "ebitda": 150_000_000_000.0,
    "ev_ebitda": 4.5, "divida_liquida": 180_000_000_000.0, "fluxo_caixa_livre": 70_000_000_000.0,
    "desatualizado": False, "alerta_qualidade": [],
}

_INDICADORES_OK = {
    "valor_mercado": 500_000_000_000.0, "moeda_fonte": "BRL", "pl": 6.2, "pvp": 1.1,
    "dividend_yield": 12.4, "beta": 1.1, "roe": 24.3, "margem_liquida": 18.0,
    "margem_operacional": 27.5, "margem_ebitda": 41.2,
    "divida_liquida": 180_000_000_000.0, "divida_liquida_ebitda": 1.2,
    "ebitda": 150_000_000_000.0, "fluxo_caixa_livre": 70_000_000_000.0,
}

_CONTEXTO_VAZIO = {
    "ticker": "PETR4", "gerado_em": None, "catalisadores": [], "mudancas": [],
    "riscos": [], "interpretacao": None,
}

_PERFIL_OK = {
    "identificacao": {
        "setor": "Energy", "industria": "Oil & Gas", "pais": "Brazil",
        "resumo_negocio": "A Petrobras produz e refina petróleo e gás no Brasil.",
        "disponivel": True,
    },
    "noticias_recentes": [], "noticias_disponivel": False,
    "perguntas": {
        "o_que_a_empresa_faz": {
            "dado": "A Petrobras produz e refina petróleo e gás no Brasil.",
            "disponivel": True, "motivo_indisponivel": None,
        },
        "perspectivas": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "pressoes_de_margem": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "riscos": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "o_que_quebraria_a_tese": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "posicao_competitiva": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "vantagens_competitivas": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
        "concorrentes": {"disponivel": False, "motivo_indisponivel": "indisponivel"},
    },
}


def _consolidado(*, sinal="COMPRA", confianca="ALTA", analistas=None) -> dict:
    """Consolidado do Comitê no MESMO shape que
    data/coordenador_central/consolidacao.py:consolidar devolve - só os
    campos que esta tela lê."""
    return {
        "ticker": "PETR4",
        "sinal_comite": {
            "sinal": sinal, "justificativa": "ROE e margem fortes, dívida controlada.",
            "score": 7, "preco_atual": 38.5, "preco_alvo_modelo": 52.0,
            "upside_modelo_pct": 35.1, "preco_alvo_pl_setorial": 44.0,
            "preco_alvo_consenso": 46.5, "moeda_preco_alvo_modelo": "R$",
            "preco_atual_consultado_em": "2026-11-24T18:00:00+00:00",
        },
        "confianca": {"categoria": confianca, "justificativa": "Convergência entre especialistas."},
        "resumo_executivo": f"Comitê recomenda {sinal} para PETR4.",
        "pareceres_analistas": {
            "analistas": analistas if analistas is not None else [],
            "casas_research": [], "preco_alvo_consenso": {},
        },
        "divergencias": {"cross_comparador_memoria": None},
        "pontos_atencao": [], "conclusao": [], "evidencias": [], "visao_especialistas": {},
    }


_CONSOLIDADO_OK = _consolidado()


def _script(*, cot=None, linha=None, perfil=None, analises="_SENTINEL_", analise=None,
            perfil_erro=None, secao=None) -> str:
    """Monta o script do AppTest - cada mock vira repr() literal injetado
    no corpo (mesmo mecanismo de tests/test_coordenador_tab_sensibilidade_dcf.py).
    `analises="_SENTINEL_"` (string, nunca um valor real de teste) é só
    pra distinguir "não testar este mock" de "testar com None" (None é
    justamente um dos 2 cenários de degradação do Comitê, não pode virar
    o default silenciosamente). `secao`: pré-seleciona uma seção do
    andar de aprofundamento (default = Pareceres, como na tela real)."""
    cot = _COT_OK if cot is None else cot
    linha = _LINHA_OK if linha is None else linha
    perfil = _PERFIL_OK if perfil is None else perfil
    analises_repr = repr([{"id": "analise-abc123", "status": "CONCLUIDA", "iniciado_em": "2026-11-24T12:00:00+00:00"}]) \
        if analises == "_SENTINEL_" else repr(analises)
    analise = _CONSOLIDADO_OK if analise is None else analise
    analise_repr = repr({
        "id": "analise-abc123", "status": "CONCLUIDA",
        "iniciado_em": "2026-11-24T12:00:00+00:00", "resultado": analise,
    })
    perfil_mock = (
        f"side_effect=Exception({perfil_erro!r})" if perfil_erro else f"return_value={perfil!r}"
    )
    pre_selecao = (
        f"st.session_state['v360_aprofundar_PETR4'] = {secao!r}\n" if secao else ""
    )
    return f'''
import sys
sys.path.insert(0, r"{_RAIZ}")
from unittest.mock import patch
import streamlit as st
import ui.visao_360_tab as v360
import ui.coordenador_tab as coord

{pre_selecao}
with patch.object(v360, "obter_cotacao", return_value={cot!r}), \\
     patch.object(v360, "obter_indicadores", return_value={_INDICADORES_OK!r}), \\
     patch.object(v360, "linha_valuation", return_value={linha!r}), \\
     patch.object(v360, "_contexto_cacheado", return_value={_CONTEXTO_VAZIO!r}), \\
     patch.object(v360, "listar_analises_por_ticker", return_value={analises_repr}), \\
     patch.object(v360, "obter_analise", return_value={analise_repr}), \\
     patch.object(coord, "obter_perfil_empresa", {perfil_mock}):
    v360.render_visao_360("PETR4", {{"formato_numerico": "BR"}})
'''


# ============================================================
# 1. Dado completo: os 3 andares da tela aparecem (decisão, análise,
#    aprofundamento), com o veredito do Comitê no topo.
# ============================================================

def test_dado_completo_mostra_os_tres_andares_da_tela():
    at = _roda(_script())
    textos = _textos(at)
    assert "PETR4" in textos
    assert "R$" in textos and "38,50" in textos  # preço presente, formatado BR
    assert "VEREDITO DO COMITÊ" in textos
    assert "COMPRA" in textos
    assert "CONFIANÇA ALTA" in textos
    assert "PERFIL DA EMPRESA" in textos
    assert "A Petrobras produz e refina petróleo e gás" in textos
    assert "INDICADORES FUNDAMENTALISTAS" in textos
    assert "VALUATION" in textos
    assert "APROFUNDAMENTO" in textos
    assert "Executar Comitê" not in textos  # análise já existe - CTA de executar não aparece


def test_cabecalho_mostra_status_da_cotacao_e_complementares():
    at = _roda(_script())
    textos = _textos(at)
    assert "ATRASADA" in textos                  # status da cotação como selo próprio
    assert "VARIAÇÃO DO DIA" in textos
    assert "52 SEMANAS" in textos
    assert "horário de Brasília" in textos
    assert "não o do último negócio" in textos   # honestidade sobre o que a hora significa


def test_indicadores_saem_agrupados_por_categoria():
    at = _roda(_script())
    textos = _textos(at)
    for categoria in ("Valuation", "Rentabilidade", "Crescimento", "Saúde financeira"):
        assert categoria in textos, f"categoria ausente: {categoria}"
    assert "EV/EBITDA" in textos
    assert "MARGEM EBITDA" in textos             # vem de obter_indicadores (mesma coleta cacheada)
    # Crescimento sem análise do Comitê pra este mock: tem que dizer o motivo real
    assert "Nenhum indicador desta categoria" in textos or "Crescimento de receita" in textos


def test_valuation_mostra_resumo_e_cenarios_com_motivo_quando_nao_ha_dcf():
    at = _roda(_script())
    textos = _textos(at)
    assert "PREÇO JUSTO · DCF" in textos
    assert "52,00" in textos                     # preco_alvo_modelo do consolidado
    assert "CONSENSO DAS CASAS" in textos
    assert "DCF interativo" in textos
    # sem parecer do Model Builder neste mock -> cenários dizem por que não existem
    assert "Cenários" in textos
    assert "não calculados" in textos or "não existem para este ticker" in textos


# ============================================================
# 2. Sem análise do Comitê (lista vazia) - CTA de executar, nunca inventa
#    recomendação.
# ============================================================

def test_sem_analise_do_comite_mostra_cta_e_nunca_inventa_recomendacao():
    at = _roda(_script(analises=[]))
    textos = _textos(at)
    assert "ainda não analisou" in textos
    assert "COMPRA" not in textos
    assert "VENDA" not in textos
    assert _tem_rotulo(at, "Executar Comitê")
    # a tela não fica vazia: as seções que não dependem do Comitê continuam
    assert "INDICADORES FUNDAMENTALISTAS" in textos
    assert "VALUATION" in textos


# ============================================================
# 3. listar_analises_por_ticker devolve None (Supabase indisponível) -
#    mensagem DISTINTA do caso "nunca analisado".
# ============================================================

def test_comite_indisponivel_mostra_mensagem_distinta_de_nunca_analisado():
    at = _roda(_script(analises=None))
    textos = _textos(at)
    assert "Não foi possível verificar" in textos
    assert "Supabase indisponível" in textos
    assert "diferente de" in textos
    assert "ainda não analisou" not in textos
    assert "COMPRA" not in textos
    assert _tem_rotulo(at, "Executar Comitê")


# ============================================================
# 4. Recomendação × confiança: COMPRA com confiança BAIXA tem aviso
#    próprio de evidência fraca (pedido explícito da missão).
# ============================================================

def test_compra_com_confianca_baixa_recebe_aviso_de_evidencia_fraca():
    at = _roda(_script(analise=_consolidado(sinal="COMPRA", confianca="BAIXA")))
    textos = _textos(at)
    assert "COMPRA" in textos
    assert "CONFIANÇA BAIXA" in textos
    assert "evidência" in textos.lower()
    assert "hipótese a confirmar" in textos


def test_compra_com_confianca_alta_nao_recebe_aviso_de_evidencia_fraca():
    at = _roda(_script(analise=_consolidado(sinal="COMPRA", confianca="ALTA")))
    textos = _textos(at)
    assert "CONFIANÇA ALTA" in textos
    assert "hipótese a confirmar" not in textos


def test_cobertura_conta_so_especialistas_que_produziram_parecer():
    analistas = [
        {"id": "market_researcher", "nome": "Market Researcher", "recomendacao": "COMPRA",
         "especialidade": "Fundamentos", "tese": "Múltiplos descontados.", "pros": [], "contras": []},
        {"id": "earnings_reviewer", "nome": "Earnings Reviewer", "recomendacao": "INSUFICIENTE",
         "especialidade": "Resultados", "tese": "Nota de resultados indisponível.",
         "pros": [], "contras": []},
    ]
    at = _roda(_script(analise=_consolidado(analistas=analistas)))
    textos = _textos(at)
    assert "COBERTURA" in textos
    assert "1/2" in textos
    assert "Earnings Reviewer" in textos  # quem ficou sem base aparece, nunca é escondido


# ============================================================
# 5. Perfil indisponível - motivo voltado ao usuário, SEM detalhe técnico,
#    e sem derrubar as outras seções.
# ============================================================

def test_perfil_indisponivel_mostra_motivo_sem_detalhe_tecnico():
    at = _roda(_script(perfil_erro="KeyError('currentPrice') ao consultar yfinance"))
    textos = _textos(at)
    assert "Perfil da empresa indisponível no momento" in textos
    assert "não responderam nesta consulta" in textos
    # detalhe técnico fica no log do servidor, nunca na tela
    assert "KeyError" not in textos
    assert "currentPrice" not in textos
    # as outras seções continuam presentes
    assert "VALUATION" in textos
    assert "VEREDITO DO COMITÊ" in textos
    assert "COMPRA" in textos


# ============================================================
# 6. Cotação indisponível - preço "—" e motivo honesto, sem repr de
#    exceção, resto da página renderiza normal.
# ============================================================

def test_cotacao_indisponivel_mostra_traco_sem_detalhe_tecnico():
    cot_erro = {"ticker": "PETR4", "erro": "timeout ao consultar fast_info"}
    at = _roda(_script(cot=cot_erro))
    textos = _textos(at)
    assert "—" in textos
    assert "Preço atual indisponível agora" in textos
    assert "COTAÇÃO INDISPONÍVEL" in textos
    assert "fast_info" not in textos  # nome de função interna nunca vai pra tela
    # resto da página não quebra nem fica em branco
    assert "PERFIL DA EMPRESA" in textos
    assert "VALUATION" in textos
    assert "VEREDITO DO COMITÊ" in textos
    assert "COMPRA" in textos


# ============================================================
# 7. Andar de aprofundamento: cada seção abre e degrada com motivo.
# ============================================================

def test_aprofundamento_tem_as_cinco_secoes_e_abre_pareceres_por_padrao():
    at = _roda(_script())
    textos = _textos(at)
    # "button_group" é o nome do elemento de st.segmented_control no
    # registro do AppTest desta versão do Streamlit (1.64) - confirmado na
    # prática; "segmented_control" devolve lista vazia.
    rotulos_segmentado = [
        opcao for controle in at.get("button_group") for opcao in (controle.options or [])
    ]
    for secao in ("PARECERES DOS ESPECIALISTAS", "RESEARCH E CONSENSO", "EVIDÊNCIAS E DIVERGÊNCIAS",
                  "NOTÍCIAS", "HISTÓRICO DE ANÁLISES"):
        assert secao in rotulos_segmentado, f"seção ausente no seletor: {secao}"
    # sem parecer nenhum neste mock: diz isso, não fica em branco
    assert "nenhum parecer de especialista" in textos


def test_aprofundamento_pareceres_renderiza_o_parecer_escolhido():
    analistas = [
        {"id": "market_researcher", "nome": "Market Researcher", "recomendacao": "COMPRA",
         "especialidade": "Fundamentos, qualidade do negócio", "metodo": "Síntese heurística",
         "tese": "Múltiplos descontados contra o próprio histórico.",
         "pros": ["ROE alto"], "contras": ["Dívida elevada"], "fontes": ["Valuation Radar"]},
    ]
    at = _roda(_script(analise=_consolidado(analistas=analistas)))
    textos = _textos(at)
    assert "Especialistas" in textos
    assert "Múltiplos descontados contra o próprio histórico." in textos
    assert "Fundamentos, qualidade do negócio" in textos


def test_aprofundamento_evidencias_sem_analise_do_comite_diz_o_motivo():
    at = _roda(_script(analises=[], secao="EVIDÊNCIAS E DIVERGÊNCIAS"))
    textos = _textos(at)
    assert "dependem de uma análise do Comitê" in textos


def test_divergencia_cross_comparador_memoria_nunca_mostra_none_literal():
    """Regressão: data/coordenador_central/consolidacao.py devolve
    `comparador`/`memoria_research` como None quando uma das 2 fontes não
    tem preço-alvo/recomendação para aquela casa (caso legítimo, não é
    falta de dado por bug). A tabela de divergência tem que tratar isso
    com o mesmo fallback "—" das colunas vizinhas (casa/tipo/campo),
    nunca vazar a string literal "None" pro usuário."""
    consolidado = _consolidado()
    consolidado["divergencias"] = {
        "cross_comparador_memoria": {
            "n_casas_comparadas": 1,
            "divergencias": [
                {"casa": "XP", "tipo": "qualitativa", "campo": "recomendacao",
                 "comparador": None, "memoria_research": None},
            ],
        },
    }
    at = _roda(_script(analise=consolidado, secao="EVIDÊNCIAS E DIVERGÊNCIAS"))
    textos = _textos(at)
    assert "COMPARADOR × MEMÓRIA DE RESEARCH" in textos
    assert "None" not in textos
    assert "—" in textos


def test_aprofundamento_historico_lista_execucoes_do_ticker():
    at = _roda(_script(secao="HISTÓRICO DE ANÁLISES"))
    textos = _textos(at)
    assert "Análises do Comitê" in textos
    assert "CONCLUIDA" in textos
    assert _tem_rotulo(at, "Abrir registro completo no Comitê")


def test_aprofundamento_historico_distingue_fonte_fora_do_ar_de_nunca_analisado():
    at = _roda(_script(analises=None, secao="HISTÓRICO DE ANÁLISES"))
    textos = _textos(at)
    assert "Histórico de análises indisponível agora" in textos
    assert "diferente de 'nunca analisado'" in textos


# ============================================================
# Regressão de performance: _carregar_comite tem que ser cacheado.
# ============================================================

def test_carregar_comite_e_cacheado_nao_bate_supabase_em_toda_rerun():
    """Antes desta correção, _carregar_comite não tinha @st.cache_data e
    a PR subiu limite=1 -> limite=12 em listar_analises_por_ticker.
    Streamlit reexecuta o script inteiro em toda interação de widget
    (clique no segmented-control, edição de premissa do DCF) - sem
    cache, toda interação disparava uma leitura 12x maior no Supabase.
    Chamadas repetidas com o mesmo ticker dentro do TTL não podem
    disparar nova leitura (spy na função de persistência)."""
    v360._carregar_comite.clear()
    chamadas = []

    def _fake_listar(ticker, limite=1):
        chamadas.append((ticker, limite))
        return [{"id": "analise-abc123", "status": "CONCLUIDA",
                 "iniciado_em": "2026-11-24T12:00:00+00:00"}]

    with patch.object(v360, "listar_analises_por_ticker", side_effect=_fake_listar), \
         patch.object(v360, "obter_analise", return_value={
             "id": "analise-abc123", "status": "CONCLUIDA",
             "iniciado_em": "2026-11-24T12:00:00+00:00", "resultado": _CONSOLIDADO_OK,
         }):
        v360._carregar_comite("PETR4")
        v360._carregar_comite("PETR4")
        v360._carregar_comite("PETR4")
    assert len(chamadas) == 1, f"esperava 1 leitura cacheada, teve {len(chamadas)}"


# ============================================================
# Sem ticker - aviso explícito, nunca uma página em branco.
# ============================================================

def test_sem_ticker_mostra_aviso():
    script = f'''
import sys
sys.path.insert(0, r"{_RAIZ}")
import ui.visao_360_tab as v360

v360.render_visao_360("", {{"formato_numerico": "BR"}})
'''
    at = _roda(script)
    textos = _textos(at)
    assert "Selecione um ticker" in textos
