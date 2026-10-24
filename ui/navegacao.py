# -*- coding: utf-8 -*-
"""Navegacao principal do PREGAO 2.0: 7 areas + menu MAIS, cada uma com
subabas proprias (ver docs/arquitetura-pregao-2.md pra matriz completa de
onde cada tela antiga foi parar).

Modelo puro (AREAS/disponiveis/resolver/rota_da_url) separado do
desenho dos widgets (render_nav_principal/render_subnav) de proposito:
a parte pura e' testavel sem sessao Streamlit (tests/test_navegacao.py)
e e' o unico lugar a mexer pra adicionar/mover uma subaba - app.py so'
despacha pela rota resolvida.

Mesmo principio da navegacao anterior (app.py, segmented_control
"secao_ativa"): SO' a subaba ativa executa (st.tabs() rodaria todas em
toda rerun). Rota fica espelhada na URL (?aba=<area>&sub=<subaba>), o
que permite link direto/recarregar a pagina sem perder o lugar.

`legado` de cada subaba = nome da aba antiga (config.ABAS_DISPONIVEIS)
que fornece o conteudo dela - continua respeitando a preferencia
"abas_visiveis" que o usuario ja tinha (subaba cuja aba antiga ele
escondeu nao aparece). Subaba sem `legado` (conteudo novo, ou CONFIG)
aparece sempre."""

from dataclasses import dataclass, field

import streamlit as st

KEY_AREA = "nav_area"
KEY_TICKER_EXTERNO = "empresa_ticker_externo"
_KEY_URL_SINCRONIZADA = "_nav_url_sincronizada"
_KEY_AVISO = "_nav_aviso"


@dataclass(frozen=True)
class Subaba:
    id: str
    rotulo: str
    legado: tuple = ()
    admin: bool = False


@dataclass(frozen=True)
class Area:
    id: str
    rotulo: str
    icone: str
    subabas: tuple = field(default_factory=tuple)


AREAS = (
    Area("mercado", "MERCADO", ":material/bar_chart:", (
        Subaba("visao-geral", "Visão Geral", ("VISÃO GERAL",)),
        Subaba("painel", "Painel", ("MERCADO",)),
        Subaba("agenda", "Agenda", ("CALENDÁRIO",)),
        Subaba("globais", "Mercados Globais", ("MERCADO",)),
    )),
    Area("noticias", "NOTÍCIAS", ":material/feed:", (
        Subaba("destaques", "Destaques", ("TOP MERCADO",)),
        Subaba("brasil", "Brasil", ("TOP MERCADO",)),
        Subaba("internacional", "Internacional", ("TOP MERCADO",)),
        Subaba("empresas", "Empresas", ("NEWS",)),
        # documentos oficiais da CVM (fato relevante/comunicado/resultado)
        # da watchlist: destino mais proximo de "cobertura sobre empresas"
        # sem misturar com o feed jornalistico - ver matriz no docs/
        Subaba("documentos", "Documentos CVM", ("CVM",)),
    )),
    Area("radar", "RADAR", ":material/radar:", (
        Subaba("alertas", "Alertas", ("RADAR",)),
        Subaba("carteiras", "Carteiras Recomendadas", ("RADAR",)),
        Subaba("oportunidades", "Oportunidades", ("RADAR",)),
        Subaba("acompanhamento", "Acompanhamento", ("RADAR",)),
    )),
    # Area propria (2026-10-23, missao "RESEARCH institucional"): antes
    # "Research" (feed/recomendacoes das casas) vivia em RADAR e "Teses"
    # vivia em ANALISES, sem nenhum lugar unico que organizasse research
    # de verdade (publicacoes de casas, cobertura/saude das fontes,
    # anotacao pessoal). Consolida os dois + 1 subaba nova (Casas de
    # Analise, ver data/research/casas_status.py) - zero coletor novo,
    # zero tabela nova, so reorganiza o que ja existia.
    Area("research", "RESEARCH", ":material/menu_book:", (
        Subaba("feed", "Feed", ("RESEARCH",)),
        Subaba("casas", "Casas de Análise"),  # conteudo novo, sem aba antiga - sempre visivel
        # mesmo legado duplo de antes ("Teses" dependia de RADAR OU
        # RESEARCH ja' visivel) - o conteudo (evidencias/copiloto vem de
        # data/radar.py, tese propria vem de data/research/tese.py) nao
        # mudou, so' a area que a hospeda.
        Subaba("teses", "Minha Tese", ("RADAR", "RESEARCH")),
    )),
    Area("analises", "ANÁLISES", ":material/query_stats:", (
        Subaba("empresas", "Empresas", ("EQUITY",)),
        Subaba("fundamentos", "Fundamentos", ("EQUITY",)),
        Subaba("valuation", "Valuation", ("RADAR",)),
    )),
    Area("macro", "MACRO", ":material/public:", (
        Subaba("indicadores", "Indicadores", ("MACRO",)),
        Subaba("juros", "Juros", ("MACRO",)),
        Subaba("cambio", "Câmbio e Commodities", ("MACRO",)),
        Subaba("calendario", "Calendário Econômico", ("MACRO",)),
    )),
    Area("setores", "SETORES", ":material/category:", (
        Subaba("mapa", "Mapa Setorial"),
        Subaba("setor", "Visão por Setor"),
        Subaba("catalisadores", "Catalisadores"),
    )),
    Area("morning-call", "MORNING CALL", ":material/wb_twilight:", (
        Subaba("edicao", "Edição Atual"),
        Subaba("relatorio", "Relatório Completo"),
        Subaba("historico", "Histórico"),
        Subaba("preferencias", "Preferências"),
    )),
    Area("mais", "MAIS", ":material/more_horiz:", (
        Subaba("watchlist", "Watchlist"),
        Subaba("config", "Configurações"),
        Subaba("sistema", "Sistema", admin=True),
        Subaba("saude", "Saúde dos Dados", admin=True),
        Subaba("usuarios", "Usuários", admin=True),
    )),
)

# aba antiga -> rota nova (atalhos que ja existiam: busca global
# "abrir na EQUITY/NOTICIAS", ranking do MERCADO -> EQUITY)
ROTA_LEGADO = {
    "VISÃO GERAL": ("mercado", "visao-geral"),
    "MERCADO": ("mercado", "painel"),
    "CALENDÁRIO": ("mercado", "agenda"),
    "TOP MERCADO": ("noticias", "destaques"),
    "NEWS": ("noticias", "empresas"),
    "CVM": ("noticias", "documentos"),
    "RADAR": ("radar", "alertas"),
    "RESEARCH": ("research", "feed"),
    "EQUITY": ("analises", "empresas"),
    "MACRO": ("macro", "indicadores"),
    "CONFIG": ("mais", "config"),
    "SISTEMA": ("mais", "sistema"),
    "SAÚDE DOS DADOS": ("mais", "saude"),
    "USUÁRIOS": ("mais", "usuarios"),
}


def key_sub(area_id: str) -> str:
    """Uma chave de widget POR area: cada area lembra a ultima subaba
    aberta nela (voltar pra NOTICIAS cai em Empresas se era la' que o
    usuario estava, nao sempre na primeira)."""
    return f"nav_sub_{area_id}"


def disponiveis(abas_visiveis, eh_admin: bool) -> list:
    """Areas/subabas que este usuario pode ver. Subaba admin some pra
    quem nao e' admin (o despacho em app.py reconfirma - esconder da nav
    nunca e' a unica barreira); area sem nenhuma subaba visivel some."""
    visiveis = set(abas_visiveis or [])
    resultado = []
    for area in AREAS:
        subs = tuple(
            s for s in area.subabas
            if (eh_admin or not s.admin) and (not s.legado or visiveis.intersection(s.legado))
        )
        if subs:
            resultado.append(Area(area.id, area.rotulo, area.icone, subs))
    return resultado


def _area(areas, area_id):
    return next((a for a in areas if a.id == area_id), None)


def resolver(areas, area_id, sub_id) -> tuple:
    """(area_id, sub_id, valida) - rota invalida (area/subaba que nao
    existe ou que o usuario nao ve) cai na primeira subaba da area, ou na
    primeira area. Nunca levanta: URL digitada errada vira so' um aviso."""
    area = _area(areas, area_id)
    if area is None:
        primeira = areas[0]
        return primeira.id, primeira.subabas[0].id, False
    ids = [s.id for s in area.subabas]
    if sub_id in ids:
        return area.id, sub_id, True
    return area.id, ids[0], sub_id is None


def rotulo_rota(area_id: str, sub_id: str) -> str:
    area = _area(AREAS, area_id)
    if area is None:
        return area_id
    sub = next((s for s in area.subabas if s.id == sub_id), None)
    return f"{area.rotulo} › {sub.rotulo}" if sub else area.rotulo


def rota_da_url(query_params) -> tuple | None:
    area = (query_params.get("aba") or "").strip().lower()
    if not area:
        return None
    sub = (query_params.get("sub") or "").strip().lower() or None
    return area, sub


def ticker_da_url(query_params) -> str | None:
    """Ticker vindo de um link direto (?ticker=X), usado por tabelas HTML
    densas sem widget real por linha (ex: ui/radar_tab.py - embutir
    st.button por linha reintroduziria o problema de largura que motivou
    essas tabelas serem HTML, ver docs/auditoria-redesign-360.md secao 4).
    Quem consome isto (app.py) sempre abre em ANALISES > Empresas,
    independente da aba/sub que a mesma URL também carregar."""
    return (query_params.get("ticker") or "").strip().upper() or None


def ir_para(area_id: str, sub_id: str | None = None, ticker: str | None = None):
    """Troca a rota (e opcionalmente preseleciona um ticker em ANALISES).
    Escreve nas chaves dos widgets da nav, entao so' pode rodar ANTES
    deles serem instanciados no run atual - na pratica: dentro de um
    callback on_click/on_change (roda antes do proximo rerun) ou no topo
    do app.py. Mesma restricao que _ir_com_ticker ja documentava."""
    st.session_state[KEY_AREA] = area_id
    if sub_id:
        st.session_state[key_sub(area_id)] = sub_id
    if ticker:
        st.session_state["ticker_selecionado"] = ticker
        st.session_state["ticker_selecionado_valido"] = ticker
        # chave PROPRIA do ticker aberto por vinculo (nao a memoria do
        # seletor, "ticker_selecionado_valido", que tambem guarda o ultimo
        # ticker escolhido - usar ela fazia um ticker removido da watchlist
        # reaparecer em ANALISES > Empresas como opcao temporaria)
        st.session_state[KEY_TICKER_EXTERNO] = ticker


def ir_para_legado(secao: str, ticker: str | None = None):
    area_id, sub_id = ROTA_LEGADO[secao]
    ir_para(area_id, sub_id, ticker)


def aplicar_url_de_entrada(areas):
    """Link direto/recarga/URL editada a mao: se a rota na URL nao e' a
    que este app escreveu por ultimo, ela veio de fora e manda. Senao a
    autoridade e' o widget (clique do usuario no run anterior). Rota
    invalida (ou oculta pra este usuario, ex: subaba admin) cai na
    padrao com um aviso - nunca uma pagina em branco."""
    rota = rota_da_url(st.query_params)
    if rota is None or rota == st.session_state.get(_KEY_URL_SINCRONIZADA):
        return
    area_id, sub_id, valida = resolver(areas, *rota)
    if not valida:
        avisar(f"Endereço de seção inválido ou indisponível ({'/'.join(r for r in rota if r)}) — abrindo {rotulo_rota(area_id, sub_id)}.")
    ir_para(area_id, sub_id)
    st.session_state[_KEY_URL_SINCRONIZADA] = rota


def _manter_selecao(chave: str):
    """on_change: segmented_control volta None quando o usuario clica de
    novo na opcao ja selecionada - restaura a ultima escolha valida pra
    nav nunca ficar sem nenhuma aba marcada."""
    if st.session_state.get(chave) is None:
        st.session_state[chave] = st.session_state.get(chave + "_valido")


def _segmentado(chave: str, opcoes: list, rotulos: dict, rotulo_widget: str) -> str:
    atual = st.session_state.get(chave)
    if atual not in opcoes:
        atual = st.session_state.get(chave + "_valido")
        if atual not in opcoes:
            atual = opcoes[0]
        st.session_state[chave] = atual
    valor = st.segmented_control(
        rotulo_widget, opcoes, format_func=rotulos.get, key=chave,
        label_visibility="collapsed", on_change=_manter_selecao, args=(chave,),
    ) or atual
    st.session_state[chave + "_valido"] = valor
    return valor


def render_nav_principal(areas) -> str:
    # container key="nav_secao": reaproveita o CSS da navegacao anterior
    # (style.css, .st-key-nav_secao - sublinhado ambar, scroll horizontal
    # no celular), sem duplicar regra
    with st.container(key="nav_secao"):
        return _segmentado(
            KEY_AREA, [a.id for a in areas],
            {a.id: f"{a.icone} {a.rotulo}" for a in areas}, "Área",
        )


# Voltar/avancar do navegador: cada troca de rota grava 1 entrada no
# historico (publicar_url), mas o Streamlit NAO reexecuta o script no
# popstate - so' a URL mudava e a tela ficava na rota antiga (visto no
# Playwright). Recarregar a pagina faz a rota da URL mandar de novo
# (aplicar_url_de_entrada). Mesma tecnica de JS via iframe com acesso a
# window.parent ja' usada em producao por ui/workspace.py; guarda no
# window.parent evita registrar o listener de novo a cada rerun.
_JS_HISTORICO = (
    "<script>(function(){var w=window.parent;if(w.__pregaoHistorico)return;"
    "w.__pregaoHistorico=true;w.addEventListener('popstate',function(){w.location.reload();});})();</script>"
)


def render_subnav(area) -> str:
    with st.container(key="nav_sub"):
        sub = _segmentado(
            key_sub(area.id), [s.id for s in area.subabas],
            {s.id: s.rotulo for s in area.subabas}, f"Subseção de {area.rotulo}",
        )
        # height=1: st.iframe nao aceita 0 (ver ui/workspace.py)
        st.iframe(_JS_HISTORICO, height=1)
        return sub


def publicar_url(area_id: str, sub_id: str):
    rota = (area_id, sub_id)
    st.session_state[_KEY_URL_SINCRONIZADA] = rota
    if st.query_params.get("aba") != area_id or st.query_params.get("sub") != sub_id:
        # from_dict = UMA atualizacao da URL (atribuir aba e sub em
        # separado gerava 2 entradas no historico do navegador, a 1a com
        # uma rota intermediaria invalida - visto no Playwright). Demais
        # parametros da URL sao preservados.
        st.query_params.from_dict({**st.query_params.to_dict(), "aba": area_id, "sub": sub_id})


def avisar(texto: str):
    """Aviso que sobrevive ao rerun disparado por um callback (st.toast
    dentro de on_click as vezes se perde no rerun seguinte)."""
    st.session_state[_KEY_AVISO] = texto


def consumir_aviso() -> str | None:
    return st.session_state.pop(_KEY_AVISO, None)


def link(rotulo: str, area_id: str, sub_id: str | None = None, *, chave: str, ticker: str | None = None,
         ajuda: str | None = None, **kwargs):
    """Botao de vinculo contextual (noticia -> empresa, empresa -> setor,
    ...). on_click (nunca escrita direta) pelo motivo de ir_para."""
    return st.button(
        rotulo, key=chave, on_click=ir_para, args=(area_id, sub_id, ticker),
        help=ajuda or f"Abrir em {rotulo_rota(area_id, sub_id)}", **kwargs,
    )
