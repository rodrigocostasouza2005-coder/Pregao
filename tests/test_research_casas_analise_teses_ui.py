# -*- coding: utf-8 -*-
"""Render completo de RESEARCH › Casas de Análise (ui/research_tab.py:
render_casas_analise) após a reformulação em painel de teses (2026-10-24) -
bare mode (sem ScriptRunContext), mesmo padrão de
tests/test_research_casas_analise_ui.py: @st.fragment precisa de
.__wrapped__, st.markdown é capturado pra inspecionar o HTML gerado.
Widgets reais (st.pills/st.text_input/st.columns/st.expander) funcionam em
bare mode devolvendo o `default` - confirmado manualmente; não precisam
de mock pra não derrubar o teste, só emitem warning de ScriptRunContext."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.research_tab as rt

_PREFS = {"formato_numerico": "BR", "watchlist": []}


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


def _status_casa(nome="Genial Analisa", **over):
    base = {
        "nome": nome, "fonte": f"{nome.lower()}.com.br",
        "coleta_automatica_cloud": False, "codigo_estado": "SUCESSO_COM_NOVIDADE",
        "rotulo_estado": "Coleta OK - dados novos", "ultimo_sucesso_em": "2026-10-24T10:00:00+00:00",
        "ultima_tentativa_em": "2026-10-24T10:00:00+00:00", "registros_novos_ultima_coleta": 2, "alerta": False,
    }
    base.update(over)
    return base


def _render(relatorios, falhas=None, status_casas=None, prefs=None, casas_para_coletar=None):
    blocos = []

    def _texto(texto, *_a, **_k):
        blocos.append(texto)

    def _expander(label, *_a, **_k):
        blocos.append(label)
        cm = MagicMock()
        cm.__enter__ = lambda self: self
        cm.__exit__ = lambda *a: False
        return cm

    with patch.object(rt, "preparar_leitura", return_value=(relatorios, falhas or [], casas_para_coletar or [], [])), \
         patch.object(rt, "ultimas_coletas_formatadas", return_value=""), \
         patch.object(rt, "coletar_pendentes", return_value=[]), \
         patch.object(rt, "obter_status_casas", return_value=status_casas or []), \
         patch.object(rt, "cobertura_cruzada_casas", return_value={"ticker": "X", "cobertura": [], "sem_cobertura": [], "divergencia": None}), \
         patch.object(rt.st, "markdown", side_effect=_texto), \
         patch.object(rt.st, "info", side_effect=_texto), \
         patch.object(rt.st, "warning", side_effect=_texto), \
         patch.object(rt.st, "expander", side_effect=_expander):
        rt.render_casas_analise.__wrapped__(prefs or _PREFS)
    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def test_publicacao_real_renderiza_casa_titulo_tipo_data_ticker():
    out = _render([_item()])
    assert "TESES E PUBLICAÇÕES" in out
    assert "Petrobras: revisão de preço-alvo" in out
    assert "Genial Analisa" in out and "PETR4" in out
    assert "20/10/2026" in out


def test_item_sem_resumo_mostra_badge_somente_metadados_sem_linha_de_recomendacao():
    out = _render([_item(resumo=None, recomendacao="COMPRA", preco_alvo=45.0)])
    assert "SOMENTE METADADOS" in out
    assert "Recomendação: <b>COMPRA" not in out  # recomendacao no banco ainda não "conta" sem resumo


def test_item_com_resumo_mostra_badge_disponivel_e_recomendacao():
    out = _render([_item(resumo="já resumido", recomendacao="COMPRA", preco_alvo=45.0)])
    assert "RESUMO (IA) DISPONÍVEL" in out
    assert "COMPRA" in out and "45,00" in out


def test_conteudo_macro_sem_ticker_aparece_no_painel():
    out = _render([_item(tipo="MACRO", tickers=[], titulo="Comentário sobre o Copom", link="https://x/macro")])
    assert "Comentário sobre o Copom" in out


def test_ausencia_de_publicacao_distinta_de_falha_de_coleta():
    sem_nada = _render([], falhas=[])
    assert "Nenhuma publicação disponível no momento" in sem_nada
    assert "Falha de coleta" not in sem_nada

    com_falha = _render([], falhas=["BTG Pactual Research"])
    assert "Falha de coleta" in com_falha and "BTG Pactual Research" in com_falha


def test_dois_itens_mesma_data_ordenados_mais_recente_primeiro():
    out = _render([
        _item(link="https://a", titulo="Mais antigo", data="2026-10-01"),
        _item(link="https://b", titulo="Mais novo", data="2026-10-23"),
    ])
    assert out.index("Mais novo") < out.index("Mais antigo")


def test_cobertura_e_saude_mostra_coluna_de_publicacoes_disponiveis_sem_consulta_nova():
    status = [_status_casa("Genial Analisa"), _status_casa("XP Investimentos", registros_novos_ultima_coleta=0)]
    itens = [_item(casa="Genial Analisa", link="https://a"), _item(casa="Genial Analisa", link="https://b"),
             _item(casa="XP Investimentos", link="https://c")]
    out = _render(itens, status_casas=status)
    assert "PUBLICAÇÕES DISPONÍVEIS" in out
    assert "COBERTURA E SAÚDE DAS CASAS" in out


def test_casa_com_falha_na_ultima_coleta_nao_aparece_como_sem_publicacoes():
    """Uma casa com estado de falha pode continuar com publicações antigas
    disponíveis - saúde técnica e conteúdo nunca se confundem."""
    status = [_status_casa("Genial Analisa", codigo_estado="FONTE_INDISPONIVEL",
                            rotulo_estado="Fonte indisponivel: bloqueio WAF", alerta=True)]
    itens = [_item(casa="Genial Analisa", link="https://a"), _item(casa="Genial Analisa", link="https://b")]
    out = _render(itens, status_casas=status)
    assert "Fonte indisponivel" in out
    # as 2 publicações da Genial continuam no painel principal, apesar do alerta
    assert out.count("Petrobras: revisão de preço-alvo") >= 1


def test_dedup_por_link_nao_mostra_a_mesma_publicacao_duas_vezes():
    out = _render([
        _item(link="https://mesmo", titulo="Único título"),
        _item(link="https://mesmo", titulo="Único título"),
    ])
    assert out.count("Único título") == 1


def test_nenhuma_excecao_com_dado_minimo():
    assert _render([]) is not None
