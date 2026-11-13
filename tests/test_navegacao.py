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

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from ui import navegacao
from ui.navegacao import AREAS, ROTA_LEGADO

RAIZ = Path(__file__).parent.parent

ORDEM_ESPERADA = ["mercado", "noticias", "radar", "research", "analises", "coordenador", "macro", "setores",
                  "morning-call", "mais"]


def _todas_rotas():
    return [(a.id, s.id) for a in AREAS for s in a.subabas]


def test_ordem_das_areas_principais():
    assert [a.id for a in AREAS] == ORDEM_ESPERADA
    assert [a.rotulo for a in AREAS][:9] == [
        "MERCADO", "NOTÍCIAS", "RADAR", "RESEARCH", "ANÁLISES", "COORDENADOR", "MACRO", "SETORES",
        "MORNING CALL",
    ]


def test_subabas_exigidas_pela_arquitetura():
    subs = {a.id: [s.rotulo for s in a.subabas] for a in AREAS}
    assert subs["mercado"] == ["Visão Geral", "Painel", "Agenda", "Mercados Globais"]
    assert subs["noticias"][:4] == ["Destaques", "Brasil", "Internacional", "Empresas"]
    assert subs["radar"] == ["Alertas", "Carteiras Recomendadas", "Oportunidades", "Acompanhamento", "Preferências"]
    assert subs["research"] == ["Feed", "Casas de Análise", "Radar X", "Minha Tese", "Memória de Research"]
    assert subs["analises"] == ["Empresas", "Fundamentos", "Valuation"]
    assert subs["coordenador"] == ["Visão Geral", "Especialistas", "Execuções", "Histórico", "Analisar"]
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
    # tudo escondido: so' sobra o que nao depende de aba antiga (CONFIG,
    # Casas de Analise, Radar X, Memoria de Research e as duas
    # Preferencias - Morning Call e Radar - sempre acessiveis; "radar"
    # sobrevive so' com 1 subaba, "research" com 3 (casas/radar-x/
    # memoria), mesmo sem nenhuma aba antiga visivel)
    minimas = navegacao.disponiveis([], eh_admin=False)
    # "coordenador" sobrevive tambem (nenhuma subaba depende de aba antiga,
    # mesmo padrao de "casas"/"radar-x"/"memoria" em research acima).
    assert [a.id for a in minimas] == ["radar", "research", "coordenador", "setores", "morning-call", "mais"]
    radar_minimo = next(a for a in minimas if a.id == "radar")
    assert [s.id for s in radar_minimo.subabas] == ["preferencias"]
    pesquisa_minima = next(a for a in minimas if a.id == "research")
    assert [s.id for s in pesquisa_minima.subabas] == ["casas", "radar-x", "memoria"]
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


def test_link_direto_por_ticker_consome_antes_da_nav_instanciar():
    """O bloco que consome ?ticker=X em app.py (link direto do Radar e
    outras tabelas HTML densas) precisa rodar ANTES de
    navegacao.render_nav_principal no mesmo rerun - mesma restricao ja
    documentada em _ir_com_ticker (escrever depois derruba com
    StreamlitWidgetAlreadyInstantiatedError). Teste estatico (nao
    execucao) porque app.py inteiro exige login Google real - mesmo
    padrao de test_app_despacha_todas_as_rotas/
    test_ticker_externo_tem_chave_propria... em test_pregao2_modulos.py."""
    fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
    pos_ticker_url = fonte.index("navegacao.ticker_da_url(st.query_params)")
    pos_render_nav = fonte.index("navegacao.render_nav_principal(areas_nav)")
    assert pos_ticker_url < pos_render_nav
    bloco = fonte[pos_ticker_url:pos_render_nav]
    assert 'del st.query_params["ticker"]' in bloco
    assert '_ir_com_ticker("EQUITY"' in bloco


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


# --- link() dentro de um st.form ---------------------------------------------
#
# Streamlit 1.64 (ver requirements.txt / pip show streamlit) proibe QUALQUER
# st.button que nao seja st.form_submit_button dentro de um st.form - com
# on_click (StreamlitInvalidFormCallbackError, reproduzido isolado antes desta
# correcao) OU mesmo sem on_click (StreamlitInvalidLayoutContextError; "capturar
# so' o retorno do st.button sem on_click" NAO escapa da regra nesta versao).
# navegacao.link() cai pra um link HTML puro (?aba=X&sub=Y, mesmo mecanismo de
# rota_da_url/aplicar_url_de_entrada e do <a href='?ticker=X'> que
# ui/secoes.py:_tabela_watchlist_comparativa ja usa em producao) quando
# detecta que esta' dentro de um form - ver ui/navegacao.py:link().
_SCRIPT_NAV_FORM = '''
import streamlit as st
import config
from ui import navegacao
areas = navegacao.disponiveis(config.ABAS_DISPONIVEIS, eh_admin=False)
navegacao.aplicar_url_de_entrada(areas)
area = navegacao.render_nav_principal(areas)
area_obj = next(a for a in areas if a.id == area)
sub = navegacao.render_subnav(area_obj)
navegacao.publicar_url(area, sub)
st.markdown(f"ROTA={area}/{sub}")
with st.form("form_teste_vinculo"):
    st.text_input("Nome", key="form_nome")
    st.number_input("Idade", key="form_idade", value=0)
    clicou_link = navegacao.link(
        "Ir pro setor (form)", "setores", "setor", chave="vinculo_form_teste",
    )
    st.markdown(f"CLICOU_LINK={clicou_link}")
    enviado = st.form_submit_button("Enviar")
    if enviado:
        st.session_state["form_foi_enviado"] = True
        st.session_state["form_nome_recebido"] = st.session_state["form_nome"]
        st.session_state["form_idade_recebida"] = st.session_state["form_idade"]
'''


def _app_form(query=None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT_NAV_FORM, default_timeout=30)
    for k, v in (query or {}).items():
        at.query_params[k] = v
    return at.run()


def _href_do_link_form(at):
    md = next(m.value for m in at.markdown if m.value.startswith("<a href="))
    return re.search(r"href='([^']+)'", md).group(1).replace("&amp;", "&")


def test_link_dentro_de_formulario_nao_levanta_mais_excecao():
    """Bug original: StreamlitInvalidFormCallbackError derrubava a tela
    inteira. Reproduzido isolado (fora deste teste, com AppTest.from_string
    chamando navegacao.link() direto dentro de um st.form) ANTES da correção
    - traceback real:
        streamlit.errors.StreamlitInvalidFormCallbackError: Within a form,
        callbacks can only be defined on `st.form_submit_button`. ...
    Depois da correção: zero exceção, o form inteiro (inclusive os outros
    campos) renderiza normalmente."""
    at = _app_form()
    assert not at.exception, f"AppTest lançou exceção: {at.exception}"
    assert _rota(at) == "mercado/visao-geral"


def test_link_dentro_de_formulario_nao_e_mais_um_st_button_real():
    """Streamlit 1.64 proíbe qualquer st.button (com ou sem on_click) que
    não seja form_submit_button dentro de um form - não existe widget de
    clique "de verdade" aqui; o fallback é um link HTML puro (<a href=...>),
    não um widget com key= registrado.

    at.button(key=...) por uma key ausente levanta KeyError (comportamento
    de WidgetList.__call__ do próprio AppTest pra lookup por chave, não algo
    específico desta correção - confirmado isolado, fora deste teste). Mas a
    prova real não é o tipo da exceção (que uma troca de versão do Streamlit
    poderia mudar sem reintroduzir o bug) - é inspecionar at.button
    diretamente e confirmar que NENHUM widget com essa key existe: a única
    key presente tem que ser a do form_submit_button ("Enviar"), nunca a do
    link ("vinculo_form_teste")."""
    at = _app_form()
    with pytest.raises(KeyError):
        at.button(key="vinculo_form_teste")
    chaves_dos_botoes = [b.key for b in at.button]
    assert "vinculo_form_teste" not in chaves_dos_botoes
    assert chaves_dos_botoes == ["FormSubmitter:form_teste_vinculo-Enviar"]
    assert any(m.value.startswith("<a href=") for m in at.markdown)
    assert "CLICOU_LINK=False" in [m.value for m in at.markdown]


def test_link_dentro_de_formulario_gera_href_da_rota_certa():
    at = _app_form()
    href = _href_do_link_form(at)
    assert href == "?aba=setores&sub=setor"


def test_link_fora_de_formulario_continua_sendo_st_button_real_on_click():
    """Comportamento de quem chama link() FORA de um form (ex:
    ui/secoes.py:render_mercados_globais, ui/analises_tab.py linha ~2057/2059)
    tem que continuar IDÊNTICO: st.button real, clicável, navega via
    on_click/ir_para - nenhum fallback de markdown aparece."""
    at = _app()
    assert not any(m.value.startswith("<a href=") for m in at.markdown)
    at.button(key="vinculo_teste").click().run()
    assert _rota(at) == "setores/setor"


def test_formulario_com_multiplos_campos_nao_perde_dado_so_por_ter_link():
    """O link dentro do form não pode impedir os OUTROS campos do mesmo
    form de renderizar/funcionar - preenche nome e idade, confirma que os
    dois widgets continuam lá (nenhuma exceção interrompeu o form no meio)."""
    at = _app_form()
    at.text_input(key="form_nome").set_value("Rodrigo").run()
    at.number_input(key="form_idade").set_value(42).run()
    assert not at.exception
    assert at.text_input(key="form_nome").value == "Rodrigo"
    assert at.number_input(key="form_idade").value == 42
    # nada foi submetido ainda - draft de form so' vai pro session_state
    # "oficial" quando o form_submit_button e' pressionado (comportamento
    # padrao de st.form, nao alterado por esta correcao)
    assert "form_foi_enviado" not in at.session_state


def test_submissao_do_formulario_continua_funcionando_com_o_link_dentro():
    at = _app_form()
    at.text_input(key="form_nome").set_value("Rodrigo").run()
    at.number_input(key="form_idade").set_value(42).run()
    at.button(key="FormSubmitter:form_teste_vinculo-Enviar").click().run()
    assert not at.exception
    assert at.session_state["form_foi_enviado"] is True
    assert at.session_state["form_nome_recebido"] == "Rodrigo"
    assert at.session_state["form_idade_recebida"] == 42


def test_navegacao_apos_submissao_nao_e_afetada_pelo_link_do_form():
    """Enviar o form (form_submit_button) não navega pra lugar nenhum - o
    link dentro dele é um <a> independente, só o clique real (pelo
    navegador) nessa URL navegaria. A rota continua intocada após o
    submit."""
    at = _app_form()
    at.button(key="FormSubmitter:form_teste_vinculo-Enviar").click().run()
    assert not at.exception
    assert at.session_state["form_foi_enviado"] is True
    assert _rota(at) == "mercado/visao-geral"


def test_navegacao_sem_submissao_via_href_do_link_do_form():
    """'Clicar' o link de navegação dentro do form, sem enviar o form, é
    literalmente navegar pra URL do href (?aba=X&sub=Y) - como o fallback
    não é um widget Streamlit, a forma real de testar o clique é a mesma
    usada por test_appteste_link_direto_pela_url (mesmo mecanismo:
    aplicar_url_de_entrada): abrir uma sessão nova direto nessa URL,
    SEM qualquer submissão do form, e confirmar que a rota muda."""
    at_form = _app_form()
    href = _href_do_link_form(at_form)
    assert "aba=" in href and "form_foi_enviado" not in at_form.session_state

    aba, sub = href.lstrip("?").split("&")
    query = dict(p.split("=") for p in [aba, sub])
    at_destino = _app(query)
    assert not at_destino.exception
    assert _rota(at_destino) == "setores/setor"


def test_persistencia_de_session_state_apos_rerun_do_form():
    """Preencher campos, rerodar (clicar em outro widget sem ser o submit -
    aqui, o próprio nav) e confirmar que os valores digitados sobrevivem ao
    rerun (comportamento herdado do st.form, não quebrado por link() estar
    dentro)."""
    at = _app_form()
    at.text_input(key="form_nome").set_value("Rodrigo").run()
    at.number_input(key="form_idade").set_value(42).run()
    # rerun disparado por outro widget (troca de subaba), nao pelo submit
    at.button_group(key=navegacao.key_sub("mercado")).set_value("painel").run()
    assert not at.exception
    assert at.text_input(key="form_nome").value == "Rodrigo"
    assert at.number_input(key="form_idade").value == 42
    assert "form_foi_enviado" not in at.session_state


def test_idempotencia_rerun_multiplo_sem_clique_nao_duplica_efeito():
    """Rodar o mesmo script 2x sem interação nenhuma (nenhum clique, nenhum
    submit) tem que ficar estável: nenhuma navegação nova, nenhum
    form_foi_enviado criado do nada, nenhuma exceção na 2a rodada."""
    at = _app_form()
    rota_1 = _rota(at)
    href_1 = _href_do_link_form(at)
    at.run()
    assert not at.exception
    assert _rota(at) == rota_1
    assert _href_do_link_form(at) == href_1
    assert "form_foi_enviado" not in at.session_state


def test_href_rota_funcao_pura():
    """_href_rota isolada (sem Streamlit) - mesma função usada no fallback
    de link(); cobre os 3 formatos (area só, area+sub, area+sub+ticker)."""
    assert navegacao._href_rota("setores", None, None) == "?aba=setores"
    assert navegacao._href_rota("setores", "setor", None) == "?aba=setores&sub=setor"
    assert navegacao._href_rota("analises", "empresas", "PETR4") == "?aba=analises&sub=empresas&ticker=PETR4"


def test_compatibilidade_render_mercados_globais_e_render_research_e_fatores():
    """Os 2 call-sites reais apontados pela missão (ui/secoes.py:
    render_mercados_globais, ui/analises_tab.py:_render_research_e_fatores)
    não estão hoje dentro de nenhum st.form (confirmado lendo app.py: nenhum
    dos 2 dispatches - rota == ("mercado","globais") e rota ==
    ("analises","fundamentos") - está dentro de um `with st.form(...)`) - o
    smoke test real (tests/test_smoke_todas_abas.py) já cobre os dois sem
    exceção; este teste fixa essa garantia aqui também, direto pelo módulo,
    sem depender só do smoke."""
    from streamlit.testing.v1 import AppTest

    script_globais = '''
import sys
sys.path.insert(0, r"{raiz}")
from ui import secoes
prefs = {{"formato_numerico": "BR", "watchlist": ["PETR4"]}}
secoes.render_mercados_globais(prefs)
'''.format(raiz=str(RAIZ).replace("\\", "\\\\"))
    at_globais = AppTest.from_string(script_globais, default_timeout=30).run()
    assert not at_globais.exception, f"AppTest lançou exceção: {at_globais.exception}"

    script_fund = '''
import sys
sys.path.insert(0, r"{raiz}")
from ui import analises_tab
prefs = {{"formato_numerico": "BR", "watchlist": ["PETR4", "VALE3"]}}
analises_tab.render_fundamentos(prefs)
'''.format(raiz=str(RAIZ).replace("\\", "\\\\"))
    at_fund = AppTest.from_string(script_fund, default_timeout=30).run()
    assert not at_fund.exception, f"AppTest lançou exceção: {at_fund.exception}"
