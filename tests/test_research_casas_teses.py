# -*- coding: utf-8 -*-
"""Núcleo puro da reformulação de RESEARCH › Casas de Análise em painel de
teses (ui/research_tab.py, 2026-10-24): dedup, filtros, período, ordenação
e as regras de "não misture falha de coleta com ausência de publicação" e
"recomendação/preço-alvo só depois do resumo existir". Tudo testado sem
nenhuma dependência de Streamlit - dicts puros, mesmo formato que
data/research/store.py:_linha_para_item devolve pra UI."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as rt


def _item(**over):
    base = {
        "casa": "Genial Analisa", "titulo": "Petrobras: revisão de preço-alvo",
        "data": "2026-10-20", "autor": "Equipe Genial", "tipo": "ACOES",
        "tickers": ["PETR4"], "link": "https://genial.com.br/petr4",
        "resumo": None, "modelo_resumo": None, "preco_alvo": None,
        "recomendacao": None, "coletado_em": "2026-10-20T10:00:00+00:00",
        "publicado_em": None,
    }
    base.update(over)
    return base


# --- dedup -------------------------------------------------------------

def test_dedupe_remove_mesmo_link_mantem_1_ocorrencia():
    itens = [_item(link="https://a"), _item(link="https://a", titulo="duplicata"), _item(link="https://b")]
    out = rt._dedupe_teses(itens)
    assert len(out) == 2
    assert {i["link"] for i in out} == {"https://a", "https://b"}


def test_dedupe_preserva_ordem_da_primeira_ocorrencia():
    itens = [_item(link="https://a", titulo="primeira"), _item(link="https://a", titulo="segunda")]
    assert rt._dedupe_teses(itens)[0]["titulo"] == "primeira"


# --- filtros -------------------------------------------------------------

def test_filtro_por_casa():
    itens = [_item(casa="Genial Analisa"), _item(casa="XP Investimentos", link="https://b")]
    out = rt._filtrar_teses(itens, casas={"XP Investimentos"})
    assert len(out) == 1 and out[0]["casa"] == "XP Investimentos"


def test_filtro_por_tipo():
    itens = [_item(tipo="ACOES"), _item(tipo="MACRO", link="https://b")]
    out = rt._filtrar_teses(itens, tipos={"MACRO"})
    assert len(out) == 1 and out[0]["tipo"] == "MACRO"


def test_filtro_por_ticker_todos_nao_exclui_nada():
    itens = [_item(tickers=["PETR4"]), _item(tickers=[], link="https://b")]
    assert len(rt._filtrar_teses(itens, ticker="Todos")) == 2


def test_filtro_por_ticker_especifico_exclui_item_sem_esse_ticker():
    itens = [_item(tickers=["PETR4"]), _item(tickers=["VALE3"], link="https://b")]
    out = rt._filtrar_teses(itens, ticker="VALE3")
    assert len(out) == 1 and out[0]["tickers"] == ["VALE3"]


def test_filtro_por_ticker_nunca_exclui_conteudo_macro_sem_ticker_quando_todos():
    """Painel não se limita a publicações com ticker (pedido explícito da
    missão) - conteúdo macro/setorial sem nenhum ticker continua visível
    com o filtro padrão "Todos"."""
    itens = [_item(tickers=[], tipo="MACRO", titulo="Comentário sobre Selic")]
    assert len(rt._filtrar_teses(itens, ticker="Todos")) == 1


def test_filtro_por_recomendacao():
    itens = [_item(recomendacao="COMPRA"), _item(recomendacao="VENDA", link="https://b"),
             _item(recomendacao=None, link="https://c")]
    out = rt._filtrar_teses(itens, recomendacoes={"COMPRA"})
    assert len(out) == 1 and out[0]["recomendacao"] == "COMPRA"


def test_chave_recomendacao_mapeia_ausencia_pro_rotulo_sem_recomendacao():
    assert rt._chave_recomendacao(_item(recomendacao="COMPRA")) == "COMPRA"
    assert rt._chave_recomendacao(_item(recomendacao=None)) == rt._SEM_RECOMENDACAO


def test_filtro_recomendacao_com_todas_as_opcoes_marcadas_nao_esconde_quem_nao_tem_recomendacao():
    """Achado real (validação com Playwright, 24/10/2026): o filtro de
    Recomendação, com TODAS as opções reais marcadas por padrão (estado
    inicial, sem o usuário tocar em nada), escondia todo item sem
    recomendação identificada - a maioria do painel (macro, ainda não
    resumido). O conjunto de opções precisa incluir o rótulo
    _SEM_RECOMENDACAO pra "tudo marcado" mostrar tudo de verdade."""
    itens = [
        _item(link="https://a", recomendacao="COMPRA"),
        _item(link="https://b", recomendacao=None, tipo="MACRO", tickers=[]),
        _item(link="https://c", recomendacao=None, resumo=None),
    ]
    opcoes_com_placeholder = {"COMPRA", rt._SEM_RECOMENDACAO}
    out = rt._filtrar_teses(itens, recomendacoes=opcoes_com_placeholder)
    assert len(out) == 3  # nada escondido quando toda opção (inclusive a de "sem recomendação") está marcada

    so_compra = rt._filtrar_teses(itens, recomendacoes={"COMPRA"})
    assert [i["link"] for i in so_compra] == ["https://a"]  # desmarcar o placeholder de fato filtra


def test_busca_textual_por_titulo_ticker_casa_e_resumo():
    itens = [
        _item(titulo="Vale anuncia dividendos", tickers=["VALE3"], link="https://a"),
        _item(titulo="Panorama macro semanal", casa="XP Investimentos", tickers=[], link="https://b"),
        _item(titulo="Sem relação", tickers=[], link="https://c", resumo="menciona Itaú no corpo"),
    ]
    assert [i["link"] for i in rt._filtrar_teses(itens, busca="vale")] == ["https://a"]
    assert [i["link"] for i in rt._filtrar_teses(itens, busca="XP")] == ["https://b"]
    assert [i["link"] for i in rt._filtrar_teses(itens, busca="itaú")] == ["https://c"]


def test_busca_textual_case_insensitive_e_ignora_espacos_nas_pontas():
    itens = [_item(titulo="Resultado do 3T26")]
    assert len(rt._filtrar_teses(itens, busca="  RESULTADO  ")) == 1


# --- período / ausência de data -----------------------------------------

def test_periodo_tudo_nunca_exclui_item_sem_data():
    itens = [_item(data="")]
    dentro, sem_data = rt._aplicar_periodo(itens, dias=None)
    assert len(dentro) == 1 and sem_data == 0


def test_periodo_especifico_tira_item_sem_data_mas_conta_quantos():
    itens = [_item(data="2026-10-20"), _item(data="", link="https://b"), _item(data=None, link="https://c")]
    dentro, sem_data = rt._aplicar_periodo(itens, dias=30, hoje=date(2026, 10, 24))
    assert len(dentro) == 1 and sem_data == 2


def test_periodo_respeita_janela_de_dias():
    itens = [_item(data="2026-10-20"), _item(data="2026-08-01", link="https://b")]
    dentro, _ = rt._aplicar_periodo(itens, dias=7, hoje=date(2026, 10, 24))
    assert len(dentro) == 1 and dentro[0]["link"] == "https://genial.com.br/petr4"


def test_periodo_nunca_inventa_data_pra_item_com_data_malformada():
    itens = [_item(data="data-invalida")]
    dentro, sem_data = rt._aplicar_periodo(itens, dias=7, hoje=date(2026, 10, 24))
    assert dentro == [] and sem_data == 1


# --- ordenação -------------------------------------------------------------

def test_ordenacao_mais_recente_primeiro_pela_data_real():
    itens = [_item(data="2026-10-01", link="https://a"), _item(data="2026-10-20", link="https://b")]
    out = rt._ordenar_teses(itens)
    assert [i["link"] for i in out] == ["https://b", "https://a"]


def test_ordenacao_item_sem_data_vai_pro_final_nunca_pro_topo():
    itens = [_item(data="", link="https://sem-data"), _item(data="2026-01-01", link="https://antigo")]
    out = rt._ordenar_teses(itens)
    assert [i["link"] for i in out] == ["https://antigo", "https://sem-data"]


# --- recomendação/preço-alvo: só depois do resumo -------------------------

def test_linha_recomendacao_none_antes_do_resumo_existir():
    """Item ainda não resumido: recomendacao/preco_alvo no banco são
    irrelevantes (ainda não foram verificados) - a linha não aparece,
    nunca mostra 'não informado' nesse estágio."""
    item = _item(resumo=None, recomendacao="COMPRA", preco_alvo=45.0)
    assert rt._linha_recomendacao(item, "BR") is None


def test_linha_recomendacao_nao_identificados_quando_resumo_existe_mas_vazio():
    item = _item(resumo="texto do resumo", recomendacao=None, preco_alvo=None)
    out = rt._linha_recomendacao(item, "BR")
    assert out is not None and "não identificados" in out


def test_linha_recomendacao_mostra_recomendacao_e_preco_quando_extraidos():
    item = _item(resumo="texto do resumo", recomendacao="COMPRA", preco_alvo=45.5)
    out = rt._linha_recomendacao(item, "BR")
    assert "COMPRA" in out and "45,50" in out


def test_linha_recomendacao_preco_alvo_nao_informado_quando_so_recomendacao_existe():
    item = _item(resumo="texto do resumo", recomendacao="MANTER", preco_alvo=None)
    out = rt._linha_recomendacao(item, "BR")
    assert "MANTER" in out and "não informado" in out


def test_badge_disponibilidade_distingue_resumo_de_so_metadados():
    assert "RESUMO (IA) DISPONÍVEL" in rt._badge_disponibilidade(_item(resumo="x"))
    assert "SOMENTE METADADOS" in rt._badge_disponibilidade(_item(resumo=None))


# --- contagem por casa (área B, sem consulta nova) -------------------------

def test_quantidade_por_casa_conta_itens_ja_carregados():
    itens = [_item(casa="Genial Analisa", link="https://a"), _item(casa="Genial Analisa", link="https://b"),
             _item(casa="XP Investimentos", link="https://c")]
    assert rt._quantidade_por_casa(itens) == {"Genial Analisa": 2, "XP Investimentos": 1}
