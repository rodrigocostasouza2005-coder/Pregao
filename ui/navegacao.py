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
aparece sempre.

Auditoria de uso do design system (ui/design_system.py, missao rollout A,
2026-11-14): este arquivo nao importa o modulo de proposito - e' roteamento
puro (dataclasses, resolucao de URL, link de navegacao), nunca lida com
numero financeiro, sinal de alta/baixa ou divisor visual."""

import html
from dataclasses import dataclass, field
from urllib.parse import quote

import streamlit as st
from streamlit.errors import (
    StreamlitInvalidFormCallbackError,
    StreamlitInvalidLayoutContextError,
)

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
        # Lente setorial (Fase 2b, 2026-11-17): movida da area SETORES
        # (dissolvida - "Mapa Setorial" era duplicata literal de MERCADO >
        # Painel, removido sem perda; estas 2 subabas usam a MESMA
        # taxonomia que classifica noticia por setor, por isso moram aqui
        # agora, nao mais numa area propria). Mesmas funcoes de sempre
        # (ui/setores_tab.py), zero logica nova.
        Subaba("setor", "Visão por Setor"),
        Subaba("catalisadores-setor", "Catalisadores Setoriais"),
    )),
    Area("radar", "RADAR", ":material/radar:", (
        Subaba("alertas", "Alertas", ("RADAR",)),
        Subaba("carteiras", "Carteiras Recomendadas", ("RADAR",)),
        Subaba("oportunidades", "Oportunidades", ("RADAR",)),
        Subaba("acompanhamento", "Acompanhamento", ("RADAR",)),
        Subaba("preferencias", "Preferências"),
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
        # RADAR X - INTELIGENCIA SOCIAL (2026-10-30): conteudo novo, sem
        # aba antiga - sempre visivel (mesmo padrao de "casas" acima).
        # Conector fica desligado sem X_BEARER_TOKEN, mas a secao sempre
        # mostra a saude real disso - nunca esconde a subaba por causa
        # de credencial ausente.
        Subaba("radar-x", "Radar X"),
        # mesmo legado duplo de antes ("Teses" dependia de RADAR OU
        # RESEARCH ja' visivel) - o conteudo (evidencias/copiloto vem de
        # data/radar.py, tese propria vem de data/research/tese.py) nao
        # mudou, so' a area que a hospeda.
        Subaba("teses", "Minha Tese", ("RADAR", "RESEARCH")),
        # Memoria de Research (Equity Research Library, Fase C - RAG,
        # 2026-10-30): busca em linguagem natural + filtros sobre a
        # biblioteca PERMANENTE de premissas/projecoes (research_premissas,
        # ver sql/research_premissas.sql e data/research/embeddings.py) -
        # conteudo novo, sem aba antiga, sempre visivel (mesmo padrao de
        # "casas" acima).
        Subaba("memoria", "Memória de Research"),
        # MORNING CALL (Fase 2b, 2026-11-18): antes area propria de 1o
        # nivel - so' a camada de LEITURA de um job de e-mail/PDF (zero
        # coleta propria, ver docstring de ui/morning_call_tab.py),
        # compartilha catalogo com a lente setorial (ver "Catalisadores
        # Setoriais" em NOTICIAS) e tem sobreposicao tematica direta com
        # RESEARCH (recomendacoes das casas) - nao justificava ser 1 das
        # 10 areas de 1o nivel sozinha. Mesmas 4 subabas de sempre,
        # mesmas funcoes (ui/morning_call_tab.py), so' a area que
        # hospeda mudou.
        Subaba("mc-edicao", "Morning Call: Edição Atual"),
        Subaba("mc-relatorio", "Morning Call: Relatório Completo"),
        Subaba("mc-historico", "Morning Call: Histórico"),
        Subaba("mc-preferencias", "Morning Call: Preferências"),
    )),
    Area("analises", "ANÁLISES", ":material/query_stats:", (
        # VISÃO 360 (missão visao-360-empresa-20261124, resolve o backlog
        # "EQUITY não é 'Company 360'"): 1 tela só por ticker - contexto do
        # negócio + preço atual + valuation/preço-alvo + o que o Comitê acha,
        # hoje espalhado em Empresas/Fundamentos/Perfil da Empresa/Valuation/
        # Comitê com seletores de ticker desconectados entre si. Posição
        # INICIAL de propósito (antes de "empresas") - é o ponto de entrada
        # natural pra quem abre um ticker querendo o panorama completo antes
        # de ir pro detalhe de cada aba. Conteúdo novo nesta posição da
        # navegação (orquestra funções já existentes, zero cálculo novo - ver
        # ui/visao_360_tab.py), sem aba antiga - sempre visível (mesmo padrão
        # de "casas"/"radar-x" em RESEARCH, "perfil" acima). id="panorama"
        # (não "visao-360"/"empresa360") de propósito - tests/test_navegacao.py
        # exige id de subaba em `[a-z-]+` (nunca dígito), mesma regra que
        # mantém toda rota segura pra URL; rótulo visível continua "Visão 360".
        Subaba("panorama", "Visão 360"),
        Subaba("empresas", "Empresas", ("EQUITY",)),
        Subaba("fundamentos", "Fundamentos", ("EQUITY",)),
        # PERFIL DA EMPRESA (missão "aba própria", pedido explícito do
        # Rodrigo, 2026-11-23): até aqui vivia dentro de um st.expander
        # em COMITÊ > Histórico (e, por reuso da mesma função, também em
        # VALUATION > Simulador DCF) - ver ui/coordenador_tab.py:
        # render_perfil_empresa_tab (ex-_render_perfil_empresa). Mora em
        # ANÁLISES, ao lado de Empresas/Fundamentos (mesma unidade de
        # navegação "por ticker da watchlist", mesmo seletor de ticker -
        # ver app.py rota ("analises", "perfil")) em vez de virar área
        # própria de 1o nível só pra 1 painel. Conteúdo novo nesta posição
        # da navegação, sem aba antiga - sempre visível (mesmo padrão de
        # "casas"/"radar-x" em RESEARCH acima).
        Subaba("perfil", "Perfil da Empresa"),
    )),
    # VALUATION (missão "reformulação Pregão Terminal Experience", Fase 2a,
    # 2026-11-17): antes fragmentado em 2 areas sem relacao visual entre si
    # - ANALISES > Valuation (parecer automatizado do Comite, calculado a
    # partir dos fundamentos coletados - ui/radar_tab.render_valuation) e
    # COORDENADOR > Analisar (simulador manual de DCF operacional - ui/
    # dcf_operacional.py, via coordenador_tab.render_analisar). Os dois
    # continuam sendo motores DISTINTOS por desenho (podem apontar
    # precos-alvo diferentes pro mesmo papel - nao e' bug, ver docstring de
    # ui/dcf_operacional.py) - esta area so' os aproxima fisicamente na
    # navegacao, nao funde a logica.
    Area("valuation", "VALUATION", ":material/calculate:", (
        Subaba("parecer", "Parecer do Comitê", ("RADAR",)),
        Subaba("simulador", "Simulador DCF"),
    )),
    # COMITÊ (ex-"COORDENADOR CENTRAL", renomeado na Fase 2a - o proprio
    # codigo ja chamava isso de "comite" em comentarios internos, ex.
    # "parecer de Valuation do comite"; Fase E, pedido do Rodrigo,
    # 2026-10-31): orquestra especialistas (inteligências Python já
    # existentes, ver data/coordenador_central/registro.py) com execução
    # paralela/isolada, consolidação e persistência - conteúdo novo, sem
    # aba antiga, sempre visível (mesmo padrão de "casas"/"radar-x" em
    # RESEARCH acima). "Analisar" (simulador DCF) mudou de lugar pra
    # VALUATION acima - mesma funcao, so' outra area.
    Area("comite", "COMITÊ", ":material/hub:", (
        Subaba("visao-geral", "Visão Geral"),
        Subaba("especialistas", "Especialistas"),
        Subaba("execucoes", "Execuções"),
        Subaba("historico", "Histórico"),
        # CENTRAL DE INTELIGÊNCIAS (missão noturna 2026-11-12, Agente A):
        # console READ-ONLY que cruza o cadastro de especialistas (ver
        # "Especialistas" acima) com métricas/histórico já persistidos -
        # conteúdo novo, sem aba antiga, sempre visível (mesmo padrão de
        # "casas"/"radar-x" em RESEARCH). Não substitui nenhuma subaba
        # existente: Especialistas/Execuções/Histórico continuam servindo
        # consulta pontual; esta é a visão consolidada de observabilidade.
        Subaba("central", "Central de Inteligências"),
    )),
    Area("macro", "MACRO", ":material/public:", (
        Subaba("indicadores", "Indicadores", ("MACRO",)),
        Subaba("juros", "Juros", ("MACRO",)),
        Subaba("cambio", "Câmbio e Commodities", ("MACRO",)),
    )),
    # CALENDÁRIO (missão "reformulação Pregão Terminal Experience", Fase
    # 2a, 2026-11-17): consolida os 2 calendarios que antes viviam
    # escondidos em areas de negocio diferentes - MERCADO > Agenda (eventos
    # corporativos: resultados/proventos/assembleias da watchlist, ver
    # ui/secoes.render_agenda) e MACRO > Calendario Economico (indicadores
    # macro, ver ui/macro_tab.render_macro_calendario). Conteudo/logica
    # identicos, so' a area que hospeda cada subaba mudou.
    Area("calendario", "CALENDÁRIO", ":material/calendar_month:", (
        Subaba("corporativo", "Eventos Corporativos", ("CALENDÁRIO",)),
        Subaba("economico", "Calendário Econômico", ("MACRO",)),
    )),
    # CARTEIRA RECOMENDADA (módulo novo, missão "Frente 4" 2026-11-12/13):
    # adicionada isolada no final da lista de áreas DE CONTEÚDO, antes de
    # "mais" (que é de propósito o menu de overflow/admin e precisa
    # continuar sendo a última - minimiza risco de conflito com outro
    # trabalho em ui/navegacao.py, ex. PR #297). Conteúdo novo, sem aba
    # antiga, sempre visível (mesmo padrão de "casas"/"radar-x" em
    # RESEARCH). Camada de dados em data/carteira_recomendada.py; esta
    # área é SEPARADA de RADAR > "Carteiras Recomendadas" (que monitora
    # carteiras PÚBLICAS de terceiros - Genial/Itaú/Safra - data/
    # radar_quedas.py) e de posições reais do Rodrigo (data/posicoes.py) -
    # nunca misturar as três.
    Area("carteira-recomendada", "CARTEIRA RECOMENDADA", ":material/pie_chart:", (
        Subaba("visao-geral", "Visão Geral"),
        Subaba("historico", "Histórico"),
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
    "CALENDÁRIO": ("calendario", "corporativo"),
    "TOP MERCADO": ("noticias", "destaques"),
    "NEWS": ("noticias", "empresas"),
    "CVM": ("noticias", "documentos"),
    "RADAR": ("radar", "alertas"),
    "RESEARCH": ("research", "feed"),
    "EQUITY": ("analises", "empresas"),
    "EMPRESA360": ("analises", "panorama"),
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
    Quem consome isto (app.py) sempre abre em ANALISES > Visão 360
    (EMPRESA360, migrado de Empresas/EQUITY na missao
    visao-360-empresa-20261124), independente da aba/sub que a mesma
    URL também carregar."""
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


def _href_rota(area_id: str, sub_id: str | None, ticker: str | None) -> str:
    """URL de navegacao direta pra esta rota (?aba=X&sub=Y[&ticker=Z]) -
    mesmo mecanismo que rota_da_url/ticker_da_url + aplicar_url_de_entrada
    ja consomem em producao, e mesmo padrao de link puro em HTML que
    ui/secoes.py:_tabela_watchlist_comparativa ja usa pra ticker
    (`<a href='?ticker=X'>`). Usado como saida de emergencia por link()
    (ver docstring dela) quando um st.button real nao e' permitido."""
    partes = [f"aba={quote(area_id)}"]
    if sub_id:
        partes.append(f"sub={quote(sub_id)}")
    if ticker:
        partes.append(f"ticker={quote(ticker)}")
    return "?" + "&".join(partes)


def link(rotulo: str, area_id: str, sub_id: str | None = None, *, chave: str, ticker: str | None = None,
         ajuda: str | None = None, **kwargs):
    """Botao de vinculo contextual (noticia -> empresa, empresa -> setor,
    ...). on_click (nunca escrita direta) pelo motivo de ir_para.

    Dentro de um st.form, o Streamlit instalado (1.64, ver
    streamlit/elements/widgets/button.py:_button) proibe QUALQUER botao
    que nao seja st.form_submit_button - com on_click (
    StreamlitInvalidFormCallbackError) ou mesmo sem (
    StreamlitInvalidLayoutContextError, "st.button() nao pode ser usado
    num st.form()"). Nao existe widget de clique independente do submit
    que o Streamlit deixe renderizar literalmente dentro de um form nesta
    versao - entao nao da pra "corrigir" so' tirando o on_click (confirmado
    na pratica; ver PR desta correcao). A saida e' nunca derrubar a tela:
    tenta o botao real (comportamento IDENTICO de sempre fora de form) e,
    se Streamlit recusar por estarmos dentro de um form, cai pra um link
    HTML puro (?aba=X&sub=Y, mesmo mecanismo de navegacao por URL que
    aplicar_url_de_entrada/ticker_da_url ja atendem) - continua clicavel
    e navega sem precisar enviar o formulario, sem duplo-submit (e' so'
    markdown, nao escreve em nenhuma chave de widget) e sem apagar os
    outros campos do form (eles so' vao pra st.session_state quando o
    form e' de fato enviado - igual qualquer st.form, com ou sem este
    link dentro)."""
    ajuda_final = ajuda or f"Abrir em {rotulo_rota(area_id, sub_id)}"
    try:
        return st.button(
            rotulo, key=chave, on_click=ir_para, args=(area_id, sub_id, ticker),
            help=ajuda_final, **kwargs,
        )
    except (StreamlitInvalidFormCallbackError, StreamlitInvalidLayoutContextError):
        st.markdown(
            f"<a href='{html.escape(_href_rota(area_id, sub_id, ticker))}' "
            f"class='vg-ticker-link' title='{html.escape(ajuda_final)}'>{html.escape(rotulo)}</a>",
            unsafe_allow_html=True,
        )
        return False
