# -*- coding: utf-8 -*-
"""Navegacao do PREGAO 2.0 (ui/navegacao.py + despacho em app.py).

Parte pura (disponiveis/resolver/rota_da_url) testada direto; widgets
(segmented_control, URL, callbacks de vinculo) testados com
streamlit.testing.v1.AppTest num script minimo que usa o MESMO modulo -
app.py inteiro exige login Google real, por isso o despacho dele e'
conferido estaticamente (toda rota tem um bloco `if rota == (...)`).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from ui import navegacao
from ui.navegacao import AREAS, ROTA_LEGADO

RAIZ = Path(__file__).parent.parent

ORDEM_ESPERADA = ["mercado", "noticias", "radar", "analises", "macro", "setores", "morning-call", "mais"]


def _todas_rotas():
    return [(a.id, s.id) for a in AREAS for s in a.subabas]


def test_ordem_das_areas_principais():
    assert [a.id for a in AREAS] == ORDEM_ESPERADA
    assert [a.rotulo for a in AREAS][:7] == [
        "MERCADO", "NOTÍCIAS", "RADAR", "ANÁLISES", "MACRO", "SETORES", "MORNING CALL",
    ]


def test_subabas_exigidas_pela_arquitetura():
    subs = {a.id: [s.rotulo for s in a.subabas] for a in AREAS}
    assert subs["mercado"] == ["Visão Geral", "Painel", "Agenda", "Mercados Globais"]
    assert subs["noticias"][:4] == ["Destaques", "Brasil", "Internacional", "Empresas"]
    assert subs["radar"] == ["Alertas", "Carteiras Recomendadas", "Oportunidades", "Acompanhamento"]
    assert subs["analises"] == ["Empresas", "Fundamentos", "Valuation", "Teses"]
    assert subs["macro"] == ["Indicadores", "Juros", "Câmbio e Commodities", "Calendário Econômico"]
    assert subs["setores"] == ["Mapa Setorial", "Visão por Setor", "Catalisadores"]
    assert subs["morning-call"] == ["Edição Atual", "Relatório Completo", "Histórico", "Preferências"]


def test_ids_unicos_e_seguros_pra_url():
    rotas = _todas_rotas()
    assert len(rotas) == len(set(rotas))
    for area, sub in rotas:
        assert re.fullmatch(r"[a-z-]+", area) and re.fullmatch(r"[a-z-]+", sub)


def test_toda_aba_antiga_tem_destino():
    """Nenhuma funcionalidade antiga fica sem lugar na navegacao nova."""
    antigas = set(config.ABAS_DISPONIVEIS) | {"CONFIG", "SISTEMA", "SAÚDE DOS DADOS"}
    assert antigas <= set(ROTA_LEGADO)
    rotas = set(_todas_rotas())
    for destino in ROTA_LEGADO.values():
        assert destino in rotas
    legados_usados = {leg for a in AREAS for s in a.subabas for leg in s.legado}
    assert legados_usados <= set(config.ABAS_DISPONIVEIS)


def test_admin_some_para_usuario_comum():
    comum = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=False)
    admin = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=True)
    subs_mais = lambda areas: [s.id for a in areas if a.id == "mais" for s in a.subabas]  # noqa: E731
    assert "sistema" not in subs_mais(comum) and "saude" not in subs_mais(comum)
    assert {"sistema", "saude"} <= set(subs_mais(admin))
    # URL apontando pra subaba admin, usuario comum: cai na padrao do MAIS, invalida
    assert navegacao.resolver(comum, "mais", "sistema") == ("mais", "watchlist", False)


def test_preferencia_antiga_de_abas_esconde_subabas():
    areas = navegacao.disponiveis([a for a in config.ABAS_DISPONIVEIS if a != "CVM"], eh_admin=False)
    noticias = next(a for a in areas if a.id == "noticias")
    assert "documentos" not in [s.id for s in noticias.subabas]
    # tudo escondido: so' sobra o que nao depende de aba antiga (CONFIG sempre acessivel)
    minimas = navegacao.disponiveis([], eh_admin=False)
    assert [a.id for a in minimas] == ["setores", "morning-call", "mais"]
    assert "config" in [s.id for s in minimas[-1].subabas]


def test_resolver_rotas_invalidas():
    areas = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=False)
    assert navegacao.resolver(areas, "radar", "alertas") == ("radar", "alertas", True)
    assert navegacao.resolver(areas, "radar", None) == ("radar", "alertas", True)
    assert navegacao.resolver(areas, "radar", "nao-existe") == ("radar", "alertas", False)
    assert navegacao.resolver(areas, "xpto", "y") == ("mercado", "visao-geral", False)


def test_rota_da_url():
    assert navegacao.rota_da_url({}) is None
    assert navegacao.rota_da_url({"aba": "RADAR", "sub": "Alertas"}) == ("radar", "alertas")
    assert navegacao.rota_da_url({"aba": "macro"}) == ("macro", None)


def test_ticker_da_url():
    assert navegacao.ticker_da_url({}) is None
    assert navegacao.ticker_da_url({"ticker": ""}) is None
    assert navegacao.ticker_da_url({"ticker": "  "}) is None
    assert navegacao.ticker_da_url({"ticker": "petr4"}) == "PETR4"
    assert navegacao.ticker_da_url({"aba": "radar", "ticker": "VALE3"}) == "VALE3"


def test_app_despacha_todas_as_rotas():
    """Nenhuma subaba aponta pra pagina vazia: cada rota tem bloco no app.py."""
    fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
    despachadas = set(re.findall(r'if rota == \("([a-z-]+)", "([a-z-]+)"\)', fonte))
    assert set(_todas_rotas()) == despachadas


def test_app_reconfirma_admin_no_despacho():
    """Toda subaba admin=True (hoje Sistema/Saude; USUARIOS do PR #72 ao
    integrar) reconfirma _eh_admin no despacho - esconder da nav nunca e'
    a unica barreira."""
    fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
    admins = [(a.id, s.id) for a in AREAS for s in a.subabas if s.admin]
    assert ("mais", "sistema") in admins and ("mais", "saude") in admins
    for area, sub in admins:
        bloco = fonte.split(f'if rota == ("{area}", "{sub}"):', 1)[1][:300]
        assert "if _eh_admin:" in bloco, sub


def test_nenhum_resquicio_da_navegacao_antiga():
    for arquivo in list((RAIZ / "ui").glob("*.py")) + [RAIZ / "app.py"]:
        texto = arquivo.read_text(encoding="utf-8")
        assert 'session_state["secao_ativa"]' not in texto, arquivo.name
        assert "secao_atual ==" not in texto, arquivo.name


# --- widgets de verdade (AppTest) ------------------------------------------

_SCRIPT_NAV = '''
import streamlit as st
import config
from ui import navegacao
areas = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=False)
navegacao.aplicar_url_de_entrada(areas)
area = navegacao.render_nav_principal(areas)
area_obj = next(a for a in areas if a.id == area)
sub = navegacao.render_subnav(area_obj)
navegacao.publicar_url(area, sub)
aviso = navegacao.consumir_aviso()
if aviso:
    st.info(aviso)
st.markdown(f"ROTA={area}/{sub}")
navegacao.link("Ir pro setor", "setores", "setor", chave="vinculo_teste")
'''


def _app(query=None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT_NAV, default_timeout=30)
    for k, v in (query or {}).items():
        at.query_params[k] = v
    return at.run()


def _rota(at):
    return next(m.value for m in at.markdown if m.value.startswith("ROTA="))[5:]


def test_appteste_rota_padrao_e_url_publicada():
    at = _app()
    assert not at.exception
    assert _rota(at) == "mercado/visao-geral"
    assert at.query_params["aba"] == ["mercado"] and at.query_params["sub"] == ["visao-geral"]


def test_appteste_link_direto_pela_url():
    at = _app({"aba": "macro", "sub": "juros"})
    assert _rota(at) == "macro/juros"
    assert not at.info


def test_appteste_url_invalida_cai_na_padrao_com_aviso():
    at = _app({"aba": "radar", "sub": "inexistente"})
    assert _rota(at) == "radar/alertas"
    assert "inválido" in at.info[0].value


def test_appteste_troca_de_area_e_memoria_da_subaba():
    at = _app()
    at.button_group(key=navegacao.KEY_AREA).set_value("noticias").run()
    assert _rota(at) == "noticias/destaques"
    at.button_group(key=navegacao.key_sub("noticias")).set_value("empresas").run()
    assert _rota(at) == "noticias/empresas"
    assert at.query_params["sub"] == ["empresas"]
    at.button_group(key=navegacao.KEY_AREA).set_value("radar").run()
    assert _rota(at) == "radar/alertas"
    # voltar pra NOTICIAS reabre a ultima subaba usada la'
    at.button_group(key=navegacao.KEY_AREA).set_value("noticias").run()
    assert _rota(at) == "noticias/empresas"


def test_appteste_vinculo_contextual():
    at = _app()
    at.button(key="vinculo_teste").click().run()
    assert _rota(at) == "setores/setor"
    assert at.query_params["aba"] == ["setores"]
