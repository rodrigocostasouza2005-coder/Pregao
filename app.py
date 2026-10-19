# -*- coding: utf-8 -*-
"""PREGÃO - terminal de mercado pessoal. Interface principal (Streamlit)."""

import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import auth
import config
from data import diagnostico
from data.mercado import obter_cotacoes_lote
from data.prices import (
    calcular_retornos,
    dias_sem_pregao,
    obter_cotacao,
    obter_cotacao_indice,
    obter_historico,
    obter_historico_intraday,
    obter_indicadores,
    obter_nome_yf,
    validar_ticker,
)
from data.research import CASAS as CASAS_RESEARCH
from data.user_prefs import (
    deve_oferecer_morning_call, email_valido, obter_prefs, registrar_acesso, salvar_prefs,
)
from ui import (
    analises_tab, busca, graficos, macro_tab, morning_call_tab, navegacao, paineis, radar_tab, secoes,
    setores_tab,
)
from ui.cvm_tab import render_cvm, render_cvm_ticker
from ui.macro_tab import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_MACRO
from ui.macro_tab import render_macro
from ui.mercado_tab import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_MERCADO
from ui.mercado_tab import render_mercado
from ui.news_tab import injetar_fallback_imagem, render_news, render_news_ticker
from ui.research_tab import render_research
from ui.saude_dados_tab import render_saude_dados
from ui.sistema_tab import render_sistema
from ui.top_mercado_tab import render_top_mercado
from ui.usuarios_tab import render_usuarios
from ui.visao_geral import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_VISAO_GERAL
from ui.visao_geral import render_visao_geral


# initial_sidebar_state="auto" (nao mais "expanded" fixo): bug real
# confirmado por screenshot (Playwright contra o app rodando de verdade,
# 2026-10-09) - "expanded" forcava a sidebar (WATCHLIST) aberta em
# QUALQUER largura, inclusive celular; numa tela de ~390px isso deixava
# so' ~90px pro conteudo principal (app ilegivel ate' o usuario fechar
# a sidebar manualmente). "auto" e' o modo que a propria documentacao do
# Streamlit recomenda pra isso: comeca aberta em telas largas (mesmo
# comportamento desktop de sempre) e fechada em telas estreitas.
st.set_page_config(page_title="PREGÃO", layout="wide", initial_sidebar_state="auto")

with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# horario regular de negociacao da B3 (nao inclui leilao de abertura antes
# das 10h nem after-market apos as 18h - simplificado de proposito, e' so'
# um indicador visual, nao uma fonte oficial de horario de pregao)
_PREGAO_ABRE_HM = (10, 0)
_PREGAO_FECHA_HM = (17, 0)


def _pregao_esta_aberto(agora: datetime) -> bool:
    if agora.weekday() >= 5:  # 5=sabado, 6=domingo
        return False
    hm_atual = (agora.hour, agora.minute)
    return _PREGAO_ABRE_HM <= hm_atual <= _PREGAO_FECHA_HM


# --- login obrigatorio: sem login, so a tela de apresentacao -------------
if not auth.logado():
    auth.tela_apresentacao()
    st.stop()

usuario = auth.dados_usuario()

# instalado 1x por pagina (nao so' dentro de NEWS): o modal editorial de
# noticia pode abrir a partir de QUALQUER aba que reaproveite
# abrir_card_noticia (RADAR, por exemplo) - ver ui/news_tab.py:
# injetar_fallback_imagem pro bug real que isso corrige (onerror inline
# nunca disparava, imagem quebrada ficava visivel sem fallback nenhum).
injetar_fallback_imagem()


def nome_empresa(ticker: str) -> str:
    """Nome da empresa: mapa local primeiro, senao busca no yfinance."""
    return config.TICKER_NOME.get(ticker) or obter_nome_yf(ticker)


# --- carregar preferencias (uma vez por sessao, ou se o usuario mudou) --
if st.session_state.get("prefs_sub") != usuario["sub"]:
    prefs, banco_ok = obter_prefs(usuario["sub"])
    st.session_state.prefs = prefs
    st.session_state.prefs_sub = usuario["sub"]
    st.session_state.banco_ok = banco_ok

prefs = st.session_state.prefs

# --- registra o acesso pro painel admin USUARIOS (ver ui/usuarios_tab.py)
# so' 1x por sessao de proposito (guarda abaixo) - data/user_prefs.py:
# registrar_acesso tambem e' rate-limitada do lado do banco (last_seen_at
# so' atualiza se ja fez mais de 30min), entao multiplas abas/sessoes do
# mesmo dia nao geram escrita excessiva. Nunca bloqueia nem avisa o
# usuario se falhar - e' so' telemetria de uso, nao preferencia dele.
if not st.session_state.get("_acesso_registrado"):
    registrar_acesso(usuario["sub"], usuario["email"])
    st.session_state["_acesso_registrado"] = True


def _persistir_prefs():
    """Tenta salvar no Supabase; se falhar, alteracoes valem so nesta sessao."""
    ok = salvar_prefs(usuario["sub"], usuario["email"], st.session_state.prefs)
    st.session_state.banco_ok = ok
    return ok


# --- migra abas novas (ex: TOP MERCADO) pras prefs de usuarios existentes -
# so adiciona em abas_visiveis o que o usuario AINDA NAO CONHECIA (nao
# reaparece uma aba que ele escondeu de proposito) - abas_conhecidas
# registra o que ja foi oferecido a ele, pra diferenciar "nunca vi essa
# aba" de "vi e escondi de proposito". So persiste quando ha algo novo
# (evita escrita no Supabase a toa em toda rerun).
_abas_novas = [a for a in config.ABAS_DISPONIVEIS if a not in prefs.get("abas_conhecidas", [])]
if _abas_novas:
    prefs["abas_visiveis"] = list(prefs.get("abas_visiveis", [])) + [
        a for a in _abas_novas if a not in prefs.get("abas_visiveis", [])
    ]
    prefs["abas_conhecidas"] = list(prefs.get("abas_conhecidas", [])) + _abas_novas
    _persistir_prefs()


def _escolha_estavel(chave_widget: str, opcoes: list, padrao):
    """Guarda a ultima escolha valida de um segmented_control (que pode voltar None ao desmarcar)."""
    chave_memoria = chave_widget + "_valido"
    ultimo_valido = st.session_state.get(chave_memoria, padrao)
    if ultimo_valido not in opcoes:
        ultimo_valido = padrao
    return ultimo_valido, chave_memoria


# --- aplicar tema escolhido como variaveis CSS ---------------------------
tema = config.TEMAS.get(prefs["tema"], config.TEMAS["AMBAR"])
_css_vars = (
    f":root {{"
    f"--bg:{tema['fundo']}; --painel-bg:{tema['painel']}; --borda:{tema['borda']}; "
    f"--destaque:{tema['destaque']}; --alta:{tema['alta']}; --baixa:{tema['baixa']}; "
    f"--neutro:{tema['neutro']}; --cinza:{tema['cinza']}; --ciano:{tema['ciano']}; "
    f"--padding-painel:{config.DENSIDADES.get(prefs['densidade'], '0.4rem')}; "
    f"--fonte-base:{config.FONTES.get(prefs['fonte'], '0.9rem')};"
    f"}}"
)
st.markdown(f"<style>{_css_vars}</style>", unsafe_allow_html=True)


# --- ticker tape unico (camada 2): indices de mercado
# (config.INDICES_TICKER_TAPE) + tickers da watchlist pessoal, na MESMA
# fita. Ate 2026-10-01 a watchlist vivia numa "camada 4" separada
# (_watchlist_chips, removida) em fluxo normal apos a NAV - sem animacao,
# so' scroll horizontal manual (overflow-x:auto), cortava visualmente.
# Unificado numa fita so' (pedido explicito do Rodrigo): reaproveita o
# MESMO mecanismo de loop continuo em CSS puro (ver pregao-marquee em
# style.css) que ja existia aqui so' pros indices.
#
# Renderizada ANTES do cabecalho (camada 1) de proposito: fica dentro de
# uma faixa position:fixed no topo (ver .pregao-topo-fixo no style.css),
# empilhada logo abaixo da faixa fixa da camada 1 (.st-key-camada1_header)
# - a ordem de EXIBICAO das duas (header por cima, ticker embaixo) vem so'
# do `top` de cada uma no CSS, nao da ordem de chamada aqui no Python; a
# camada 1 continua tendo que ficar FORA deste fragment (ver comentario em
# camada1_header mais abaixo, sobre por que os botoes de busca não podem
# viver dentro de um fragment). O resto do conteudo (abas etc.) vem
# depois, em fluxo normal, com espaco reservado no padding-top do
# block-container.
@st.fragment(run_every=prefs["atualizacao_intervalo"])
def _ticker_tape():
    fmt = prefs["formato_numerico"]
    itens = []

    for nome_idx, symbol_idx in config.INDICES_TICKER_TAPE.items():
        cot = obter_cotacao_indice(nome_idx, symbol_idx)
        if cot.get("erro"):
            itens.append(f"<span class='cinza'>{nome_idx} --</span>")
        else:
            cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
            sinal = "+" if cot["variacao_pct"] >= 0 else ""
            itens.append(
                f"<span class='cinza'>{nome_idx}</span> "
                f"<span class='{cls}'>{config.formatar_numero(cot['preco'], 2, fmt)} "
                f"({sinal}{config.formatar_numero(cot['variacao_pct'], 2, fmt)}%)</span>"
            )

    # tickers da watchlist pessoal entram na MESMA fita (redesign
    # 2026-10-01: antes viviam numa segunda faixa separada - _watchlist_chips,
    # removida - sem animacao, cortava com overflow-x:auto manual em vez de
    # rodar feito a de indices acima). Mesmo formato dos indices acima
    # (ticker + preco + variacao), fonte de dados identica a' que a faixa
    # antiga ja usava (obter_cotacao, mesmo cache).
    # obter_cotacoes_lote (N+1 real corrigido, 2026-10-08): 1 UNICA
    # requisicao em lote pra watchlist inteira - essa fita roda no header,
    # em TODA pagina, no mesmo run_every do fragment; antes disparava 1
    # yf.Ticker().fast_info POR TICKER da watchlist (obter_cotacao)
    # sequencialmente a cada atualizacao.
    cotacoes_watchlist = obter_cotacoes_lote(tuple(prefs["watchlist"]))
    for t in prefs["watchlist"]:
        cot = cotacoes_watchlist.get(t, {"erro": "sem dado"})
        if cot.get("erro"):
            itens.append(f"<span class='cinza'>{t} --</span>")
        else:
            cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
            sinal = "+" if cot["variacao_pct"] >= 0 else ""
            itens.append(
                f"<span class='cinza'>{t}</span> "
                f"<span class='{cls}'>{config.formatar_numero(cot['preco'], 2, fmt)} "
                f"({sinal}{config.formatar_numero(cot['variacao_pct'], 2, fmt)}%)</span>"
            )

    conteudo = " &nbsp;·&nbsp; ".join(itens)
    animado = prefs["ticker_tape_modo"] == "ANIMADO"

    # barra de status: relogio de Brasilia + indicador aberto/fechado do
    # pregao + nota de atraso da cotacao - faz parte do mesmo fragment do
    # letreiro (mesmo run_every) de proposito: um fragment separado so pro
    # relogio ficaria "tique-taqueando" a 1x/segundo, gerando muito mais
    # rerun do que o necessario so pra atualizar um relogio (contraria o
    # trabalho de performance da auditoria da FILA1) - atualizar no mesmo
    # ritmo das cotacoes (prefs["atualizacao_intervalo"]) e' suficiente.
    agora = datetime.now(FUSO_BR)
    aberto = _pregao_esta_aberto(agora)
    classe_status = "alta" if aberto else "baixa"
    rotulo_status = "PREGÃO ABERTO" if aberto else "PREGÃO FECHADO"
    status_html = (
        f"<div style='display:flex; justify-content:space-between; align-items:center; "
        f"flex-wrap:wrap; gap:0.5rem; font-size:0.68rem; padding:0.15rem 1rem 0.3rem 1rem;' class='cinza'>"
        f"<span>{agora.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)</span>"
        f"<span class='{classe_status}' style='font-weight:600;'>● {rotulo_status}</span>"
        f"<span>cotações com atraso de ~15 min (fonte: Yahoo Finance)</span>"
        f"</div>"
    )

    if not animado:
        st.markdown(
            f"<div class='pregao-topo-fixo'><div class='ticker-tape-wrap fixo'><div class='ticker-tape-track'>"
            f"<span class='ticker-tape-set'>{conteudo}</span></div></div>{status_html}</div>",
            unsafe_allow_html=True,
        )
        return

    # velocidade constante: duracao da animacao escala com o tamanho do
    # conteudo (estimado pelo numero de caracteres visiveis, fonte mono) -
    # so' os indices de config.INDICES_TICKER_TAPE entram aqui agora, mas o
    # calculo continua generico pra nao quebrar se a lista de indices crescer
    velocidade_px_s = config.VELOCIDADES_TICKER_TAPE[prefs["ticker_tape_velocidade"]]
    texto_visivel = re.sub(r"<[^>]+>", "", conteudo)
    largura_estimada_px = len(texto_visivel) * 8.75  # px/char pra fonte 0.875rem (ver ticker-tape-set no style.css)
    duracao_s = max(largura_estimada_px / velocidade_px_s, 8)

    # animation-delay negativo: a animacao parece ter comecado no epoch e
    # estar rodando continuamente, entao o refresh do fragment (que troca o
    # elemento HTML inteiro) nao gera um "pulo" visivel de volta ao inicio
    atraso_s = -(time.time() % duracao_s)

    st.markdown(
        f"<div class='pregao-topo-fixo'><div class='ticker-tape-wrap'>"
        f"<div class='ticker-tape-track' style='animation-duration:{duracao_s:.1f}s; animation-delay:{atraso_s:.1f}s;'>"
        f"<span class='ticker-tape-set'>{conteudo}</span>"
        f"<span class='ticker-tape-set'>{conteudo}</span>"
        f"</div></div>{status_html}</div>",
        unsafe_allow_html=True,
    )


if not st.session_state.banco_ok:
    st.warning("Sem conexão com o Supabase — preferências e watchlist valem só para esta sessão.")

# --- oferta de inscricao no Morning Call por e-mail: aparece 1x por
# usuario, so' ate ele responder (aceitar OU recusar) - ver
# data/user_prefs.py:deve_oferecer_morning_call. So' mostra com banco_ok
# (sem conexao com o Supabase, qualquer resposta valeria so' nesta
# sessao e a pergunta voltaria a aparecer na visita seguinte - melhor
# nao perguntar do que perguntar e nao conseguir lembrar a resposta).
# Nao bloqueia nada: e' um painel normal, igual qualquer outro, com 2
# acoes explicitas - nunca marca inscricao so' por ter sido exibido.
if st.session_state.banco_ok and deve_oferecer_morning_call(prefs):
    with st.container(border=True):
        st.markdown(
            '<div class="painel-titulo">RECEBER O MORNING CALL POR E-MAIL?</div>',
            unsafe_allow_html=True,
        )
        email_usuario_ok = email_valido(usuario["email"])
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem; margin-bottom:0.5rem;'>"
            "Todo dia útil, por volta das 08h (Brasília): um resumo com mercados, "
            "macro, agenda do dia e notícias — só isso, nada além do que já existe "
            f"aqui no terminal. Enviado para <b>{usuario['email'] or '(sem e-mail)'}</b>. "
            "Pode desligar quando quiser, em MORNING CALL › Preferências."
            "</div>",
            unsafe_allow_html=True,
        )
        email_destino = usuario["email"]
        if not email_usuario_ok:
            email_destino = st.text_input(
                "Sua conta não tem um e-mail válido associado — informe um e-mail pra receber:",
                key="onboarding_mc_email_manual",
                placeholder="voce@exemplo.com",
            )
            email_usuario_ok = email_valido(email_destino)

        colb1, colb2, _colb3 = st.columns([1, 1, 3])
        with colb1:
            aceitou = st.button(
                "QUERO RECEBER", key="onboarding_mc_aceitar", type="primary", disabled=not email_usuario_ok,
            )
        with colb2:
            recusou = st.button("AGORA NÃO", key="onboarding_mc_recusar")

        if aceitou or recusou:
            prefs["morning_call_email_perguntado"] = True
            if aceitou:
                prefs["morning_call_email_ativo"] = True
            ok = salvar_prefs(usuario["sub"], email_destino or usuario["email"], prefs)
            st.session_state.banco_ok = ok
            if ok:
                st.toast(
                    "Você vai receber o Morning Call por e-mail."
                    if aceitou else "Combinado — você pode ativar isso depois em MORNING CALL › Preferências.",
                )
            else:
                st.warning("Não foi possível salvar agora (banco indisponível) — a pergunta pode voltar a aparecer.")
            st.rerun()

# --- navegacao PREGAO 2.0 (ver ui/navegacao.py e docs/arquitetura-pregao-2.md):
# 7 areas + MAIS, cada uma com subabas. So a subaba ativa executa
# (diferente de st.tabs(), que roda o conteudo de TODAS as abas em toda
# rerun e so esconde por CSS) - alem de mais rapido, uma excecao numa
# secao nao derruba as outras (era o caso do bug que deixava RESEARCH e
# CONFIG em branco juntos). abas_visiveis (preferencia antiga) continua
# valendo: esconde as subabas cujo conteudo vem de uma aba escondida.
abas_visiveis = [a for a in prefs["abas_visiveis"] if a in config.ABAS_DISPONIVEIS]
if not abas_visiveis:
    abas_visiveis = list(config.ABAS_DISPONIVEIS)
# SISTEMA/SAÚDE DOS DADOS: so pros e-mails admin - de proposito NAO entram
# em config.ABAS_DISPONIVEIS (isso faria abas_conhecidas oferecer a aba
# pra todo mundo, ver migracao de abas novas la em cima); em
# ui/navegacao.py sao subabas admin=True do MAIS, e o despacho mais
# abaixo reconfirma _eh_admin (esconder da nav nunca e' a unica barreira).
_eh_admin = usuario["email"] in config.obter_emails_admin()
# USUÁRIOS: painel administrativo de usuarios/metricas/inscricao no
# Morning Call (ver ui/usuarios_tab.py) - mesmo tratamento de SISTEMA/
# SAÚDE DOS DADOS (subaba admin=True de MAIS, fora de ABAS_DISPONIVEIS,
# ver ui/navegacao.py). A autorizacao e' reconfirmada no dispatch abaixo
# E dentro de render_usuarios/data/admin_usuarios.py - esconder da nav
# nunca e' a UNICA barreira.
areas_nav = navegacao.disponiveis(abas_visiveis, _eh_admin)
navegacao.aplicar_url_de_entrada(areas_nav)


# --- busca global (ETAPA 8): ativo qualquer, atalhos pra abrir em ANÁLISES›
# Empresas / NOTÍCIAS›Empresas ja com o ticker escolhido, ou so adicionar
# na watchlist sem sair da aba atual. Renderizada ANTES do nav (ver
# comentario em _ir_com_ticker sobre por que essa ordem importa) -
# funciona em qualquer aba (nao so nas que mostram ticker). Empresas
# (seletor de ticker) e NOTÍCIAS›Empresas (obter_noticias_watchlist) so
# mostram dado de tickers da watchlist - por isso "abrir em X" adiciona o
# ticker na watchlist primeiro se ele ainda nao estiver la (mesma
# validacao ja usada no fluxo da sidebar).
def _ir_com_ticker(secao_legado: str, ticker: str, chave_pill_ticker: str | None):
    """Muda de secao + preseleciona o ticker, com efeito no MESMO rerun
    (sem chamar st.rerun()) - escrever nas chaves dos widgets da nav
    (ui/navegacao.py:ir_para) só é permitido ANTES desses widgets serem
    instanciados nesse rerun; por isso esta funcao roda (e e' chamada)
    ANTES de navegacao.render_nav_principal mais abaixo. Descoberto na
    pratica: tentar escrever DEPOIS derruba com
    StreamlitWidgetAlreadyInstantiatedError."""
    area_id, sub_id = navegacao.ROTA_LEGADO[secao_legado]
    _, _, rota_ok = navegacao.resolver(areas_nav, area_id, sub_id)
    if not rota_ok:
        st.warning(f"{navegacao.rotulo_rota(area_id, sub_id)} está oculta nas suas preferências (MAIS › Configurações).")
        return
    if ticker not in prefs["watchlist"]:
        if not validar_ticker(ticker):
            st.error(f"Ticker '{ticker}' não encontrado no yfinance.")
            return
        prefs["watchlist"].append(ticker)
        _persistir_prefs()
    navegacao.ir_para(area_id, sub_id, ticker)
    if chave_pill_ticker:
        st.session_state[chave_pill_ticker] = ticker


# --- header fixo: camada 1 (identidade+busca+acoes+usuario) seguida da
# camada 2 (ticker de mercado), NUM UNICO wrapper fixed (.st-key-header_fixo,
# ver style.css) - as duas camadas sao filhos NORMAIS desse wrapper, entao a
# ordem visual (header sempre acima do ticker) vem do fluxo normal do HTML,
# nao de dois `top` fixos calculados separadamente (isso e' o que causava
# risco de ordem errada/sobreposicao se a altura real de uma camada
# divergisse da estimativa em CSS). O fragment do ticker (_ticker_tape, com
# seu run_every) pode morar dentro deste container normal sem problema - so'
# os BOTOES da camada 1 e' que precisam ficar FORA de qualquer fragment:
# "↗"/"▣" escrevem nas chaves da nav (ui/navegacao.py:ir_para)
# esperando um rerun DA PAGINA INTEIRA (pra rota, mais abaixo, pegar
# o valor novo) - dentro de um fragment, um clique so' dispara rerun do
# fragment, e a pagina nunca trocaria de aba.
with st.container(key="header_fixo"):
    with st.container(key="camada1_header"):
        # col_user ganhou mais espaco (1.35->1.7) e col_busca cedeu um pouco
        # (3.9->3.55) - achado real (BACKLOG.md): o e-mail do usuario
        # "sumia" do header em telas mais estreitas porque o botao SAIR
        # (width="stretch" + texto que nao quebra linha) brigava por
        # espaco com o chip de e-mail dentro da mesma coluna apertada;
        # ver tambem sub_email/sub_sair logo abaixo.
        col_logo, col_busca, col_ctrlk, col_eq, col_news, col_add, col_user = st.columns(
            [1.1, 3.55, 0.55, 0.5, 0.5, 0.5, 1.7], gap="small", vertical_alignment="center",
        )
        with col_logo:
            st.markdown('<div class="pregao-logo-compacto">PREGÃO</div>', unsafe_allow_html=True)
        with col_busca:
            ticker_busca_global = busca.buscar_ativo(
                "Busca global", chave="busca_global_ticker", extras=prefs["watchlist"],
                ajuda="Busca por ticker ou nome — abre direto em ANÁLISES › Empresas ou NOTÍCIAS desse ativo",
            )
        with col_ctrlk:
            st.markdown('<div class="pregao-ctrlk">CTRL K</div>', unsafe_allow_html=True)
        ja_na_watchlist = bool(ticker_busca_global) and ticker_busca_global in prefs["watchlist"]
        with col_eq:
            if st.button("↗", key="busca_global_eq", width="stretch", disabled=not ticker_busca_global, help="Abrir em ANÁLISES › Empresas"):
                _ir_com_ticker("EQUITY", ticker_busca_global, None)
        with col_news:
            if st.button("▣", key="busca_global_news", width="stretch", disabled=not ticker_busca_global, help="Abrir em NOTÍCIAS › Empresas"):
                _ir_com_ticker("NEWS", ticker_busca_global, "news_pill_ticker")
        with col_add:
            if st.button(
                "✓" if ja_na_watchlist else "+",
                key="busca_global_add", width="stretch",
                disabled=not ticker_busca_global or ja_na_watchlist,
                help="Na watchlist" if ja_na_watchlist else "Adicionar à watchlist",
            ):
                if validar_ticker(ticker_busca_global):
                    prefs["watchlist"].append(ticker_busca_global)
                    _persistir_prefs()
                    st.rerun()
                else:
                    st.error(f"Ticker '{ticker_busca_global}' não encontrado no yfinance.")
        with col_user:
            # sub_sair SEM width="stretch" (fica do tamanho do proprio
            # texto/padding, nao estica) - antes, os dois esticando dentro
            # de colunas estreitas faziam o SAIR "ganhar" a disputa por
            # espaco (texto nao quebra linha) e sobrava quase nada pro
            # chip de e-mail, que entao cortava quase tudo via ellipsis
            sub_email, sub_sair = st.columns([4, 1], gap="small")
            with sub_email:
                st.markdown(
                    f"<div class='cinza pregao-user-chip' title='{usuario['email']}'>{usuario['email']}</div>",
                    unsafe_allow_html=True,
                )
            with sub_sair:
                if st.button("SAIR", key="sair_btn"):
                    st.logout()

    # link direto por ticker (tabelas HTML densas sem widget real por
    # linha, achado P1 da auditoria 360 - docs/auditoria-redesign-360.md
    # secao 4, ex: ui/radar_tab.py): ?ticker=X na URL abre ANALISES >
    # Empresas com esse papel, mesma validacao/efeito de _ir_com_ticker
    # ja usado pela busca global acima. Consumido e removido da URL no
    # MESMO run - sem isso, qualquer rerun seguinte (clicar em outra
    # coisa) reabriria o mesmo ticker de novo.
    _ticker_url = navegacao.ticker_da_url(st.query_params)
    if _ticker_url:
        del st.query_params["ticker"]
        _ir_com_ticker("EQUITY", _ticker_url, None)

    _ticker_tape()

    # navegacao (camada 3) tambem dentro do wrapper sticky (pedido do
    # Rodrigo, 2026-09-28: "cabecalho ate as abas" fixo ao rolar a pagina,
    # nao so' o header+ticker) - subabas e conteudo continuam FORA, em
    # fluxo normal (rolam com a pagina; no celular o header fixo ja ocupa
    # bastante altura, uma 4a faixa fixa sobraria pouco pro conteudo).
    area_atual = navegacao.render_nav_principal(areas_nav)

_area_obj = next(a for a in areas_nav if a.id == area_atual)
sub_atual = navegacao.render_subnav(_area_obj)
navegacao.publicar_url(area_atual, sub_atual)
rota = (area_atual, sub_atual)
_aviso_nav = navegacao.consumir_aviso()
if _aviso_nav:
    st.info(_aviso_nav)


# --- sidebar: gestao da watchlist ------------------------------------------
with st.sidebar:
    st.markdown('<div class="painel-titulo">WATCHLIST</div>', unsafe_allow_html=True)

    if "contador_input_ticker" not in st.session_state:
        st.session_state.contador_input_ticker = 0

    def _adicionar_ticker(ticker: str):
        if not ticker:
            st.warning("Digite ou escolha um ticker.")
        elif ticker in prefs["watchlist"]:
            st.warning(f"{ticker} já está na lista.")
        elif validar_ticker(ticker):
            prefs["watchlist"].append(ticker)
            _persistir_prefs()
            st.session_state.contador_input_ticker += 1  # forca campo/busca vazios no rerun
            st.rerun()
        else:
            st.error(f"Ticker '{ticker}' não encontrado no yfinance.")

    ticker_buscado = busca.buscar_ativo(
        "Buscar ativo", chave=f"busca_ativo_{st.session_state.contador_input_ticker}",
        extras=prefs["watchlist"],
    )
    if st.button("ADICIONAR", width="stretch"):
        _adicionar_ticker((ticker_buscado or "").strip().upper())

    with st.expander("Ticker não está na lista? digite manualmente"):
        novo_ticker = st.text_input(
            "Adicionar ticker (ex: PETR4)",
            key=f"input_novo_ticker_{st.session_state.contador_input_ticker}",
            label_visibility="collapsed", placeholder="TICKER EXATO (EX: PETR4)",
        ).strip().upper()
        if st.button("ADICIONAR MANUALMENTE", width="stretch"):
            _adicionar_ticker(novo_ticker)

    @st.fragment(run_every=prefs["atualizacao_intervalo"])
    def _fragmento_watchlist():
        # obter_cotacoes_lote (N+1 restante corrigido, FASE 8): 1 UNICA
        # requisicao em lote pra watchlist inteira, mesmo mecanismo ja
        # usado no ticker tape/VISAO GERAL (data/mercado.py) - antes
        # disparava 1 yf.Ticker().fast_info POR TICKER aqui tambem.
        cotacoes = obter_cotacoes_lote(tuple(prefs["watchlist"]))
        for t in list(prefs["watchlist"]):
            cot = cotacoes.get(t, {"erro": "sem dado"})
            nome = nome_empresa(t)
            if cot.get("erro"):
                var_html = "<span class='cinza'>--</span>"
            else:
                cls = "alta" if cot["variacao_pct"] >= 0 else "baixa"
                sinal = "+" if cot["variacao_pct"] >= 0 else ""
                var_html = f"<span class='{cls}'>{sinal}{config.formatar_numero(cot['variacao_pct'], 2, prefs['formato_numerico'])}%</span>"

            col_info, col_remover = st.columns([4, 1])
            col_info.markdown(
                f"<div style='padding-bottom:0.35rem; margin-bottom:0.35rem; border-bottom:1px solid var(--borda);'>"
                f"<div style='display:flex; justify-content:space-between; align-items:baseline;'>"
                f"<span style='color:var(--destaque); font-weight:600;'>{t}</span>{var_html}</div>"
                f"<div class='cinza' style='font-size:0.66rem; margin-top:0.1rem;'>{nome}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if col_remover.button("x", key=f"remover_{t}"):
                prefs["watchlist"].remove(t)
                if st.session_state.get(navegacao.KEY_TICKER_EXTERNO) == t:
                    st.session_state.pop(navegacao.KEY_TICKER_EXTERNO)
                _persistir_prefs()
                st.rerun()

    _fragmento_watchlist()


# =============================================================================
# DESPACHO PELA ROTA (ui/navegacao.py). Cada bloco reaproveita o render da
# aba antiga correspondente (matriz completa em docs/arquitetura-pregao-2.md).
# =============================================================================

# --- MERCADO › Visão Geral (home - resumo do mercado, ver ui/visao_geral.py) --
if rota == ("mercado", "visao-geral"):
    with st.container():
        render_visao_geral(prefs, persistir_fn=_persistir_prefs)
        secoes.render_atalhos_visao_geral()

# --- MERCADO › Painel (antiga aba MERCADO: workspace personalizavel) ---------
if rota == ("mercado", "painel"):
    with st.container():
        render_mercado(prefs, persistir_fn=_persistir_prefs)

if rota == ("mercado", "agenda"):
    secoes.render_agenda(prefs)

if rota == ("mercado", "globais"):
    secoes.render_mercados_globais(prefs)

# --- NOTÍCIAS -----------------------------------------------------------------
if rota == ("noticias", "destaques"):
    render_top_mercado(prefs, regiao_fixa="TUDO", titulo="DESTAQUES")
if rota == ("noticias", "brasil"):
    render_top_mercado(prefs, regiao_fixa="BRASIL", titulo="BRASIL")
if rota == ("noticias", "internacional"):
    render_top_mercado(prefs, regiao_fixa="INTERNACIONAL", titulo="INTERNACIONAL")
if rota == ("noticias", "empresas"):
    with st.container():
        render_news(prefs)
# --- antiga aba CVM (documentos oficiais: fato relevante, comunicado,
# resultados, proventos, calendario - watchlist inteira, ver ui/cvm_tab.py)
if rota == ("noticias", "documentos"):
    with st.container():
        render_cvm(prefs)

# --- RADAR (ver ui/radar_tab.py) ---------------------------------------------
if rota == ("radar", "alertas"):
    radar_tab.render_radar_alertas(prefs)
if rota == ("radar", "carteiras"):
    radar_tab.render_radar_carteiras(prefs)
    # antiga aba RESEARCH: recomendacoes/relatorios das casas de analise
    with st.container():
        render_research(prefs)
if rota == ("radar", "oportunidades"):
    radar_tab.render_radar_oportunidades(prefs)
if rota == ("radar", "acompanhamento"):
    radar_tab.render_radar_acompanhamento(prefs)

# --- ANÁLISES › Fundamentos/Valuation/Teses -------------------------------------
if rota == ("analises", "fundamentos"):
    analises_tab.render_fundamentos(prefs)
if rota == ("analises", "valuation"):
    radar_tab.render_valuation(prefs)
if rota == ("analises", "teses"):
    radar_tab.render_teses(prefs)

# --- MACRO (Indicadores = workspace completo da antiga aba MACRO) -------------
if rota == ("macro", "indicadores"):
    with st.container():
        render_macro(prefs, persistir_fn=_persistir_prefs)
if rota == ("macro", "juros"):
    macro_tab.render_macro_juros(prefs)
if rota == ("macro", "cambio"):
    macro_tab.render_macro_cambio_commodities(prefs)
if rota == ("macro", "calendario"):
    macro_tab.render_macro_calendario(prefs)

# --- SETORES (ver ui/setores_tab.py) -------------------------------------------
if rota == ("setores", "mapa"):
    setores_tab.render_mapa_setorial(prefs)
if rota == ("setores", "setor"):
    setores_tab.render_visao_setor(prefs)
if rota == ("setores", "catalisadores"):
    setores_tab.render_catalisadores_setor(prefs)

# --- MORNING CALL (ver ui/morning_call_tab.py - nunca envia e-mail) -------------
if rota == ("morning-call", "edicao"):
    morning_call_tab.render_edicao_atual(prefs)
if rota == ("morning-call", "relatorio"):
    morning_call_tab.render_relatorio_completo(prefs)
if rota == ("morning-call", "historico"):
    morning_call_tab.render_historico(prefs)
if rota == ("morning-call", "preferencias"):
    morning_call_tab.render_preferencias(prefs, usuario, _persistir_prefs)

# --- MAIS › Watchlist -------------------------------------------------------------
if rota == ("mais", "watchlist"):
    secoes.render_watchlist(prefs)


# --- ANÁLISES › Empresas (antiga aba EQUITY) ----------------------------------
if rota == ("analises", "empresas"):
    with st.container():
        # ticker aberto por um vinculo (setor/ranking/busca) que ainda nao
        # esta na watchlist: entra como opcao TEMPORARIA do seletor (com
        # botao pra adicionar), em vez de mexer na watchlist sem pedir
        ticker_externo = st.session_state.get(navegacao.KEY_TICKER_EXTERNO)
        opcoes_ticker = list(prefs["watchlist"])
        if ticker_externo and ticker_externo not in opcoes_ticker:
            opcoes_ticker.append(ticker_externo)
        if not opcoes_ticker:
            st.info("Adicione um ticker na barra lateral para começar.")
        else:
            padrao_ticker, mem_ticker = _escolha_estavel("ticker_selecionado", opcoes_ticker, opcoes_ticker[0])
            sel = st.segmented_control(
                "Ticker", opcoes_ticker, default=padrao_ticker,
                label_visibility="collapsed", key="ticker_selecionado",
            )
            ticker_selecionado = sel or padrao_ticker
            st.session_state[mem_ticker] = ticker_selecionado
            if ticker_selecionado not in prefs["watchlist"]:
                if st.button(f"+ ADICIONAR {ticker_selecionado} À WATCHLIST", key="empresa_add_watchlist"):
                    prefs["watchlist"].append(ticker_selecionado)
                    st.session_state.pop(navegacao.KEY_TICKER_EXTERNO, None)
                    _persistir_prefs()
                    st.rerun()
            analises_tab.barra_contexto_empresa(ticker_selecionado, prefs)

            if len(prefs["watchlist"]) > 1:
                @st.fragment(run_every=prefs["atualizacao_intervalo"])
                def _painel_comparativo_watchlist():
                    fmt = prefs["formato_numerico"]
                    linhas_dados = []
                    # obter_cotacoes_lote (N+1 corrigido, FASE 8): 1 UNICA
                    # requisicao em lote pra cotacao da watchlist inteira.
                    # obter_indicadores CONTINUA por ticker de proposito:
                    # vem de yf.Ticker().info (P/L, P/VP, DY...), que o
                    # yfinance nao oferece em lote (so' fast_info/download
                    # de OHLCV sao batcheaveis) - e' cacheado 12h por
                    # ticker (data/prices.py:_TTL_INDICADORES), bem acima
                    # do run_every deste fragment, entao o custo real de
                    # rede aqui ja' e' raro (so' no 1o load/expiracao).
                    cotacoes = obter_cotacoes_lote(tuple(prefs["watchlist"]))
                    for t in prefs["watchlist"]:
                        cot = cotacoes.get(t, {"erro": "sem dado"})
                        if cot.get("erro"):
                            continue
                        ind = obter_indicadores(t)
                        linhas_dados.append({"ticker": t, "cot": cot, "ind": ind})

                    with st.container(border=True):
                        st.markdown('<div class="painel-titulo">COMPARATIVO DA WATCHLIST</div>', unsafe_allow_html=True)
                        if not linhas_dados:
                            st.markdown("<div class='cinza' style='font-size:0.78rem;'>Sem cotações disponíveis agora.</div>", unsafe_allow_html=True)
                        else:
                            melhor = max(linhas_dados, key=lambda d: d["cot"]["variacao_pct"])
                            pior = min(linhas_dados, key=lambda d: d["cot"]["variacao_pct"])
                            # "melhor/pior desempenho" em vez de "maior alta/baixa": se a
                            # watchlist inteira estiver no vermelho hoje, o "melhor" ainda
                            # e' negativo - chamar isso de "alta" seria enganoso
                            cls_melhor = "alta" if melhor["cot"]["variacao_pct"] >= 0 else "baixa"
                            cls_pior = "alta" if pior["cot"]["variacao_pct"] >= 0 else "baixa"
                            st.markdown(
                                f"<div class='cinza' style='font-size:0.7rem; margin-bottom:0.3rem;'>"
                                f"melhor desempenho do dia: <span class='{cls_melhor}' style='font-weight:600;'>{melhor['ticker']} "
                                f"{'+' if melhor['cot']['variacao_pct'] >= 0 else ''}{config.formatar_numero(melhor['cot']['variacao_pct'], 2, fmt)}%</span>"
                                f" · pior desempenho do dia: <span class='{cls_pior}' style='font-weight:600;'>{pior['ticker']} "
                                f"{'+' if pior['cot']['variacao_pct'] >= 0 else ''}{config.formatar_numero(pior['cot']['variacao_pct'], 2, fmt)}%</span></div>",
                                unsafe_allow_html=True,
                            )
                            linhas_html = "".join(
                                f"<tr>"
                                f"<td style='padding:0.2rem 0.4rem 0.2rem 0;'><span style='color:var(--destaque); font-weight:600;'>{d['ticker']}</span></td>"
                                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>R$ {config.formatar_numero(d['cot']['preco'], 2, fmt)}</td>"
                                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='{'alta' if d['cot']['variacao_pct'] >= 0 else 'baixa'}'>"
                                f"{'+' if d['cot']['variacao_pct'] >= 0 else ''}{config.formatar_numero(d['cot']['variacao_pct'], 2, fmt)}%</td>"
                                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>{config.formatar_multiplo(d['ind']['pl'], 2, fmt)}</td>"
                                f"<td style='padding:0.2rem 0.4rem; text-align:right;' class='neutro'>{config.formatar_multiplo(d['ind']['pvp'], 2, fmt)}</td>"
                                f"<td style='padding:0.2rem 0 0.2rem 0.4rem; text-align:right;' class='neutro'>{config.formatar_numero(d['ind']['dividend_yield'], 2, fmt) + '%' if d['ind']['dividend_yield'] is not None else '—'}</td>"
                                f"</tr>"
                                for d in linhas_dados
                            )
                            st.markdown(
                                f"<div style='overflow-x:auto; overflow-y:hidden;'>"
                                f"<table style='width:100%; font-size:0.8rem; border-collapse:collapse;'>"
                                f"<thead><tr class='cinza' style='font-size:0.68rem;'>"
                                f"<th style='text-align:left; font-weight:400; padding:0 0.4rem 0.2rem 0;'>TICKER</th>"
                                f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>PREÇO</th>"
                                f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>VAR. DIA</th>"
                                f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>P/L</th>"
                                f"<th style='text-align:right; font-weight:400; padding:0 0.4rem 0.2rem;'>P/VP</th>"
                                f"<th style='text-align:right; font-weight:400; padding:0 0 0.2rem 0.4rem;'>DY</th>"
                                f"</tr></thead><tbody>{linhas_html}</tbody></table></div>",
                                unsafe_allow_html=True,
                            )

                _painel_comparativo_watchlist()

            @st.fragment(run_every=prefs["atualizacao_intervalo"])
            def _painel_precos(ticker_sel):
                cotacao = obter_cotacao(ticker_sel)
                st.markdown('<div class="painel-titulo">PREÇOS</div>', unsafe_allow_html=True)

                if cotacao.get("erro"):
                    # motivo tecnico (cotacao['erro'], ex: KeyError do yfinance) nao vai
                    # pra tela - so' o fato de a fonte nao ter respondido
                    st.warning(f"Cotação de {ticker_sel} indisponível no momento (fonte: Yahoo Finance).")
                else:
                    fmt = prefs["formato_numerico"]
                    sinal_classe = "alta" if cotacao["variacao"] >= 0 else "baixa"
                    sinal_sim = "+" if cotacao["variacao"] >= 0 else ""
                    nome_empresa_sel = nome_empresa(ticker_sel)

                    def _num_ou_traco(valor, casas=2):
                        return config.formatar_numero(valor, casas, fmt) if valor is not None else "—"

                    max_min_dia = (
                        f"{_num_ou_traco(cotacao['maxima_dia'])} / {_num_ou_traco(cotacao['minima_dia'])}"
                        if cotacao["maxima_dia"] is not None or cotacao["minima_dia"] is not None else "—"
                    )

                    st.markdown(
                        f"""
                        <div style="overflow-x:auto; overflow-y:hidden;">
                        <table style="width:100%; border-collapse:collapse;">
                        <thead><tr>
                            <th style="text-align:left; font-weight:400; white-space:normal;" class="cinza">{ticker_sel} {nome_empresa_sel}</th>
                            <th class="cinza">VARIAÇÃO DIA</th>
                            <th class="cinza">MÁX/MÍN DIA</th>
                            <th class="cinza">VOLUME</th>
                            <th class="cinza">MÁX 52 SEM</th>
                            <th class="cinza">MÍN 52 SEM</th>
                        </tr></thead>
                        <tbody><tr>
                            <td style="text-align:left; font-size:1.15rem; font-weight:600;" class="{sinal_classe}">
                                R$ {_num_ou_traco(cotacao['preco'])}</td>
                            <td class="{sinal_classe}">{sinal_sim}{_num_ou_traco(cotacao['variacao'])}
                                ({sinal_sim}{_num_ou_traco(cotacao['variacao_pct'])}%)</td>
                            <td class="neutro">{max_min_dia}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['volume'], 0)}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['maxima_52s'])}</td>
                            <td class="neutro">{_num_ou_traco(cotacao['minima_52s'])}</td>
                        </tr></tbody>
                        </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    # todas as janelas partem do mesmo preco atual do painel
                    # PRECOS (fast_info), nao do fechamento historico de
                    # ontem - senao cada janela podia comparar contra uma
                    # "foto" diferente do preco
                    preco_para_retornos = cotacao["preco"] if not cotacao.get("erro") else None
                    retornos = calcular_retornos(ticker_sel, preco_para_retornos) if preco_para_retornos else {}
                    # garante 1D identico a VARIACAO DIA por construcao,
                    # mesmo que o "fechamento de 1 dia atras" do historico
                    # caia numa data ligeiramente diferente do previousClose
                    # do fast_info
                    if retornos and not cotacao.get("erro"):
                        retornos["1D"] = cotacao["variacao_pct"]
                    if retornos:
                        partes = []
                        for rotulo in config.JANELAS_RETORNO:
                            valor = retornos.get(rotulo)
                            if valor is None:
                                partes.append(f"<span class='cinza'>{rotulo} —</span>")
                            else:
                                cls = "alta" if valor >= 0 else "baixa"
                                sinal = "+" if valor >= 0 else ""
                                partes.append(
                                    f"<span class='cinza'>{rotulo}</span> "
                                    f"<span class='{cls}'>{sinal}{config.formatar_numero(valor, 1, fmt)}%</span>"
                                )
                        st.markdown(
                            "<div style='display:flex; gap:0.9rem; flex-wrap:wrap; font-size:0.72rem; "
                            "margin-top:0.4rem; overflow-x:auto; overflow-y:hidden;'>" + "".join(partes) + "</div>",
                            unsafe_allow_html=True,
                        )

                    agora_preco = datetime.now(FUSO_BR)
                    if _pregao_esta_aberto(agora_preco):
                        legenda_atraso = "cotação com atraso de ~15 min (fonte: Yahoo Finance)"
                    else:
                        # achado real (2026-10-08): fora do horario de pregao
                        # (fim de semana/feriado/apos as 17h) o texto antigo
                        # misturava "hora em que a pagina renderizou" com
                        # "hora real da cotacao" - um domingo mostrava
                        # "atraso de ~15 min" quando o ultimo preco real e'
                        # de sexta-feira.
                        legenda_atraso = "cotação de fechamento (mercado fechado, fonte: Yahoo Finance)"
                    st.markdown(
                        f"<div class='cinza' style='font-size:0.65rem; margin-top:0.3rem;'>"
                        f"Última atualização {agora_preco.strftime('%H:%M:%S')} — {legenda_atraso}</div>",
                        unsafe_allow_html=True,
                    )

            with st.container(border=True):
                _painel_precos(ticker_selecionado)

            with st.container(border=True):
                st.markdown('<div class="painel-titulo">INDICADORES</div>', unsafe_allow_html=True)
                fmt = prefs["formato_numerico"]
                ind = obter_indicadores(ticker_selecionado)
                dy = ind["dividend_yield"]

                # dados stale (2026-10-06): "_coletado_em" so' existe se
                # pelo menos 1 campo veio de uma coleta bem-sucedida
                # (ver data/prices.py:obter_indicadores) - se essa coleta
                # for mais velha que o TTL normal (12h), os indicadores
                # exibidos sao reaproveitados de um bloqueio anterior do
                # Yahoo, nao da tentativa de agora - aviso discreto,
                # mesma linguagem visual do "atualizado ha Xh" do
                # CALENDARIO (ui/calendario_tab.py)
                aviso_indicadores_antigos = ""
                coletado_em = ind.get("_coletado_em")
                if coletado_em:
                    try:
                        idade_h = (datetime.now(timezone.utc) - datetime.fromisoformat(coletado_em)).total_seconds() / 3600
                        if idade_h > 12:
                            aviso_indicadores_antigos = (
                                f"<div class='cinza' style='font-size:0.65rem; margin-top:0.5rem;'>"
                                f"⚠ indicadores reaproveitados de uma coleta de há {int(idade_h)}h "
                                f"(Yahoo Finance bloqueou a tentativa mais recente)</div>"
                            )
                    except ValueError:
                        pass

                st.markdown(
                    f"""
                    <div style="overflow-x:auto; overflow-y:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                    <thead><tr>
                        <th class="cinza" title="Preço da ação x número total de ações em circulação - o que o mercado paga pela empresa inteira hoje">VALOR DE MERCADO</th>
                        <th class="cinza" title="Preço/Lucro: preço da ação dividido pelo lucro por ação nos últimos 12 meses - quantos anos de lucro atual pagariam o preço de hoje (menor = mais barato, na média do setor). N.M. = lucro negativo (prejuízo), o múltiplo perde sentido">P/L</th>
                        <th class="cinza" title="Preço/Valor Patrimonial: preço da ação dividido pelo patrimônio líquido por ação - acima de 1 significa que o mercado paga mais que o valor contábil da empresa. N.M. = patrimônio líquido negativo, o múltiplo perde sentido">P/VP</th>
                        <th class="cinza" title="Dividend Yield: total pago em dividendos/JCP nos últimos 12 meses dividido pelo preço da ação - retorno percentual só de proventos, sem contar valorização">DIV. YIELD (12M)</th>
                        <th class="cinza" title="cov(retornos semanais do papel, retornos semanais do Ibovespa) / var(retornos semanais do Ibovespa), 2 anos - calculado localmente, nao vem do yfinance">BETA (2A)</th>
                    </tr></thead>
                    <tbody><tr>
                        <td class="neutro">{config.formatar_valor_mercado(ind['valor_mercado'], fmt)}</td>
                        <td class="neutro">{config.formatar_multiplo(ind['pl'], 2, fmt)}</td>
                        <td class="neutro">{config.formatar_multiplo(ind['pvp'], 2, fmt)}</td>
                        <td class="neutro">{config.formatar_numero(dy, 2, fmt) + '%' if dy is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['beta'], 2, fmt) if ind['beta'] is not None else '—'}</td>
                    </tr></tbody>
                    </table>
                    </div>
                    <div style="overflow-x:auto; overflow-y:hidden; margin-top:0.5rem;">
                    <table style="width:100%; border-collapse:collapse;">
                    <thead><tr>
                        <th class="cinza" title="Lucro liquido dividido pelo patrimonio liquido dos ultimos 12 meses - quanto a empresa gera de retorno sobre o capital dos acionistas">ROE</th>
                        <th class="cinza" title="Lucro liquido dividido pela receita liquida - quanto sobra de cada R$ 1 vendido, ja descontado tudo">MARGEM LÍQUIDA</th>
                        <th class="cinza" title="Lucro operacional dividido pela receita liquida - rentabilidade da operacao, antes de juros e impostos">MARGEM OPERACIONAL</th>
                        <th class="cinza" title="EBITDA dividido pela receita liquida - geracao de caixa operacional antes de juros, impostos, depreciacao e amortizacao. Nao se aplica a bancos/seguradoras (sem EBITDA tradicional)">MARGEM EBITDA</th>
                        <th class="cinza" title="Divida total menos caixa disponivel. Entre parenteses: quantos anos de EBITDA seriam necessarios pra quitar a divida liquida (quanto menor, melhor)">DÍVIDA LÍQUIDA</th>
                    </tr></thead>
                    <tbody><tr>
                        <td class="neutro">{config.formatar_numero(ind['roe'], 2, fmt) + '%' if ind['roe'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['margem_liquida'], 2, fmt) + '%' if ind['margem_liquida'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['margem_operacional'], 2, fmt) + '%' if ind['margem_operacional'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_numero(ind['margem_ebitda'], 2, fmt) + '%' if ind['margem_ebitda'] is not None else '—'}</td>
                        <td class="neutro">{config.formatar_valor_mercado(ind['divida_liquida'], fmt)}{f" ({config.formatar_numero(ind['divida_liquida_ebitda'], 1, fmt)}x EBITDA)" if ind['divida_liquida_ebitda'] is not None else ""}</td>
                    </tr></tbody>
                    </table>
                    </div>
                    {aviso_indicadores_antigos}
                    """,
                    unsafe_allow_html=True,
                )

            with st.container(border=True):
                titulo_grafico = st.empty()
                titulo_grafico.markdown('<div class="painel-titulo">GRÁFICO</div>', unsafe_allow_html=True)

                periodos = config.PERIODOS_INTRADIARIOS + list(config.PERIODOS_GRAFICO.keys())
                padrao_periodo = prefs["grafico_periodo_padrao"] if prefs["grafico_periodo_padrao"] in periodos else "6M"
                padrao_periodo, mem_periodo = _escolha_estavel("periodo_grafico", periodos, padrao_periodo)
                sel_periodo = st.segmented_control(
                    "Período", periodos, default=padrao_periodo,
                    label_visibility="collapsed", key="periodo_grafico",
                )
                periodo = sel_periodo or padrao_periodo
                st.session_state[mem_periodo] = periodo
                eh_intraday = periodo in config.PERIODOS_INTRADIARIOS

                comparar_ibov = st.checkbox("Comparar com Ibovespa (base 100)", value=False, key="comparar_ibov")

                if eh_intraday:
                    df = obter_historico_intraday(ticker_selecionado, periodo)
                else:
                    df = obter_historico(ticker_selecionado, periodo)

                if eh_intraday and periodo == "1D" and df is not None and not df.empty:
                    data_pregao = df["Data"].iloc[-1].strftime("%d/%m")
                    titulo_grafico.markdown(
                        f'<div class="painel-titulo">GRÁFICO — PREGÃO DE {data_pregao}</div>',
                        unsafe_allow_html=True,
                    )

                def _layout_grafico_escuro(fig, altura=480):
                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor=tema["fundo"],
                        plot_bgcolor=tema["fundo"],
                        font=dict(color=tema["cinza"], family="IBM Plex Mono", size=11),
                        xaxis_rangeslider_visible=False,
                        height=altura,
                        margin=dict(l=10, r=10, t=10, b=10),
                        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10)),
                    )
                    # tema["borda"] (nao "#1A1A1A" fixo, achado da
                    # auditoria visual 2026-10-16): no tema CLARO (fundo
                    # claro), um grid quase-preto fixo ficava bem mais
                    # proeminente do que a grade sutil pretendida - cada
                    # tema ja' calibra sua propria cor de borda sutil.
                    fig.update_xaxes(gridcolor=tema["borda"])
                    fig.update_yaxes(gridcolor=tema["borda"])

                if df is None:
                    if eh_intraday:
                        st.warning(f"Não foi possível obter o histórico intradiário de {ticker_selecionado}.")
                    else:
                        st.warning(f"Não foi possível obter o histórico de {ticker_selecionado} para o período {periodo}.")
                elif comparar_ibov and not eh_intraday:
                    fig = go.Figure()
                    serie_acao = (df["Close"] / df["Close"].iloc[0]) * 100
                    fig.add_trace(go.Scatter(x=df["Data"], y=serie_acao, name=ticker_selecionado,
                                              line=dict(color=tema["destaque"], width=1.5)))

                    df_ibov = obter_historico(config.SIMBOLO_IBOVESPA, periodo)
                    if df_ibov is None:
                        st.warning("Não foi possível obter o histórico do Ibovespa para comparação.")
                    else:
                        serie_ibov = (df_ibov["Close"] / df_ibov["Close"].iloc[0]) * 100
                        fig.add_trace(go.Scatter(x=df_ibov["Data"], y=serie_ibov, name="IBOVESPA",
                                                  line=dict(color=tema["ciano"], width=1.5)))

                    _layout_grafico_escuro(fig)
                    fig.update_yaxes(title="Base 100")

                    _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
                    if intervalo_periodo == "1d":
                        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=dias_sem_pregao(df))])

                    chave_zoom = graficos.zoom_key("equity_comparativo_ibov", ticker_selecionado, periodo)
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave_zoom)
                else:
                    if comparar_ibov and eh_intraday:
                        st.info("Comparação com Ibovespa não disponível para períodos intradiários (1D/1S).")

                    fig = make_subplots(
                        rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.75, 0.25], vertical_spacing=0.03,
                    )

                    tipo_grafico = prefs["grafico_tipo"]
                    if tipo_grafico == "CANDLE":
                        fig.add_trace(
                            go.Candlestick(
                                x=df["Data"], open=df["Open"], high=df["High"],
                                low=df["Low"], close=df["Close"], name=ticker_selecionado,
                                increasing_line_color=tema["alta"], decreasing_line_color=tema["baixa"],
                            ),
                            row=1, col=1,
                        )
                    elif tipo_grafico == "AREA":
                        fig.add_trace(
                            go.Scatter(
                                x=df["Data"], y=df["Close"], name=ticker_selecionado, fill="tozeroy",
                                line=dict(color=tema["destaque"], width=1.5),
                            ),
                            row=1, col=1,
                        )
                    else:  # LINHA
                        fig.add_trace(
                            go.Scatter(
                                x=df["Data"], y=df["Close"], name=ticker_selecionado,
                                line=dict(color=tema["destaque"], width=1.5),
                            ),
                            row=1, col=1,
                        )

                    sufixo_mm = ""
                    if eh_intraday:
                        sufixo_mm = " (5 min)" if periodo == "1D" else " (30 min)"

                    # em CANDLE o preco vira barras alta/baixa (sem cor propria) - MM20
                    # pode usar --destaque sem colidir. Em LINHA/AREA o preco JA usa
                    # --destaque, entao MM20 precisa de outra cor pra nao ficar
                    # indistinguivel da linha de preco (ver BACKLOG.md)
                    cor_mm20 = tema["neutro"] if tipo_grafico in ("LINHA", "AREA") else tema["destaque"]
                    if prefs["mm20"] and df["MM20"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM20"], name=f"MM20{sufixo_mm}",
                                       line=dict(color=cor_mm20, width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm50"] and df["MM50"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM50"], name=f"MM50{sufixo_mm}",
                                       line=dict(color=tema["ciano"], width=1)),
                            row=1, col=1,
                        )
                    if prefs["mm200"] and df["MM200"].notna().any():
                        fig.add_trace(
                            go.Scatter(x=df["Data"], y=df["MM200"], name=f"MM200{sufixo_mm}",
                                       line=dict(color=tema["cinza"], width=1)),
                            row=1, col=1,
                        )

                    cores_volume = [
                        tema["alta"] if c >= o else tema["baixa"]
                        for o, c in zip(df["Open"], df["Close"])
                    ]
                    fig.add_trace(
                        go.Bar(x=df["Data"], y=df["Volume"], name="Volume",
                               marker_color=cores_volume, opacity=0.6),
                        row=2, col=1,
                    )

                    _layout_grafico_escuro(fig)

                    if eh_intraday:
                        # esconde fim de semana e fora do horario de pregao da B3
                        # (10h-17h, conferido nos dados intradiarios reais)
                        fig.update_xaxes(rangebreaks=[
                            dict(bounds=["sat", "mon"]),
                            dict(bounds=[17, 10], pattern="hour"),
                        ])
                    else:
                        # remove buracos de fim de semana/feriado no eixo X (so faz sentido em barras diarias)
                        _, intervalo_periodo = config.PERIODOS_GRAFICO[periodo]
                        if intervalo_periodo == "1d":
                            feriados = dias_sem_pregao(df)
                            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(values=feriados)])

                    chave_zoom = graficos.zoom_key(
                        "equity_grafico", ticker_selecionado, periodo, tipo_grafico,
                        prefs["mm20"], prefs["mm50"], prefs["mm200"],
                    )
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=chave_zoom)

            with st.container(border=True):
                render_news_ticker(ticker_selecionado, prefs)

            with st.container(border=True):
                render_cvm_ticker(ticker_selecionado, prefs)


# --- MAIS › Sistema / Saúde dos Dados (so admin): _eh_admin reconfirmado
# aqui (nao so' na nav) - mesmo que a rota chegasse a uma subaba admin por
# URL ou estado de sessao reaproveitado, quem nao e' admin nunca ve o
# conteudo (navegacao.disponiveis ja' nem oferece a rota pra ele).
if rota == ("mais", "sistema"):
    with st.container():
        if _eh_admin:
            render_sistema(prefs)
        else:
            st.error("Acesso restrito a administradores.")

if rota == ("mais", "saude"):
    with st.container():
        if _eh_admin:
            render_saude_dados()
        else:
            st.error("Acesso restrito a administradores.")


# --- MAIS › Usuários (so admin, ver ui/usuarios_tab.py) - reconfirma
# _eh_admin aqui tambem (nao so' na nav): mesmo que a rota chegasse a
# ("mais", "usuarios") por algum jeito que nao passasse pela nav (ex:
# estado de sessao reaproveitado de uma troca de usuario na mesma aba
# do navegador), quem nao e' admin nunca ve' o conteudo real - e
# render_usuarios/data/admin_usuarios.py reconfirmam de novo, inclusive
# na consulta ------
if rota == ("mais", "usuarios"):
    with st.container():
        if _eh_admin:
            render_usuarios(usuario)
        else:
            st.error("Acesso restrito a administradores.")


# --- MAIS › Configurações (antiga aba CONFIG) ---------------------------------
if rota == ("mais", "config"):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">CONFIG</div>', unsafe_allow_html=True)

        # Notificação por e-mail do Morning Call: o toggle de efeito
        # imediato (opt-in explícito, default DESLIGADO) mudou pra
        # MORNING CALL › Preferências (ui/morning_call_tab.py:
        # render_preferencias) - mesmo comportamento, mesma chave de prefs.
        st.markdown(
            "<div class='cinza' style='font-size:0.68rem; margin-bottom:0.3rem;'>NOTIFICAÇÕES</div>",
            unsafe_allow_html=True,
        )
        navegacao.link(
            "MORNING CALL POR E-MAIL: "
            + ("ATIVADO" if prefs.get("morning_call_email_ativo", False) else "DESATIVADO") + " — ALTERAR ↗",
            "morning-call", "preferencias", chave="config_ir_mc_prefs",
        )

        with st.form("form_config"):
            c1, c2 = st.columns(2)
            with c1:
                novo_tema = st.selectbox("TEMA", list(config.TEMAS.keys()),
                                          index=list(config.TEMAS.keys()).index(prefs["tema"]))
                nova_densidade = st.selectbox("DENSIDADE", list(config.DENSIDADES.keys()),
                                               index=list(config.DENSIDADES.keys()).index(prefs["densidade"]))
                nova_fonte = st.selectbox("TAMANHO DA FONTE", list(config.FONTES.keys()),
                                           index=list(config.FONTES.keys()).index(prefs["fonte"]))
                novo_formato = st.selectbox("FORMATO NUMÉRICO", ["BR", "US"],
                                             index=["BR", "US"].index(prefs["formato_numerico"]))
                rotulos_intervalo = list(config.INTERVALOS_ATUALIZACAO.keys())
                valores_intervalo = list(config.INTERVALOS_ATUALIZACAO.values())
                idx_intervalo = valores_intervalo.index(prefs["atualizacao_intervalo"]) if prefs["atualizacao_intervalo"] in valores_intervalo else 1
                novo_rotulo_intervalo = st.selectbox("ATUALIZAÇÃO AUTOMÁTICA", rotulos_intervalo, index=idx_intervalo)
            with c2:
                novo_tipo_grafico = st.selectbox("TIPO DE GRÁFICO", ["CANDLE", "LINHA", "AREA"],
                                                  index=["CANDLE", "LINHA", "AREA"].index(prefs["grafico_tipo"]))
                novo_periodo_padrao = st.selectbox("PERÍODO PADRÃO", list(config.PERIODOS_GRAFICO.keys()),
                                                    index=list(config.PERIODOS_GRAFICO.keys()).index(prefs["grafico_periodo_padrao"]))
                novo_mm20 = st.checkbox(
                    "MÉDIA MÓVEL 20", value=prefs["mm20"],
                    help="Média dos últimos 20 preços de fechamento - referência de curto prazo; cruzamento com o preço costuma ser lido como sinal de tendência recente",
                )
                novo_mm50 = st.checkbox(
                    "MÉDIA MÓVEL 50", value=prefs["mm50"],
                    help="Média dos últimos 50 preços de fechamento - referência de médio prazo",
                )
                novo_mm200 = st.checkbox(
                    "MÉDIA MÓVEL 200", value=prefs["mm200"],
                    help="Média dos últimos 200 preços de fechamento - referência de longo prazo; muito usada como linha de tendência de fundo (acima = tendência de alta no longo prazo)",
                )
                novo_tape_modo = st.selectbox("LETREIRO", ["ANIMADO", "FIXO"],
                                               index=["ANIMADO", "FIXO"].index(prefs["ticker_tape_modo"]))
                novo_tape_velocidade = st.selectbox("VELOCIDADE DO LETREIRO", list(config.VELOCIDADES_TICKER_TAPE.keys()),
                                                     index=list(config.VELOCIDADES_TICKER_TAPE.keys()).index(prefs["ticker_tape_velocidade"]))

            novas_abas = st.multiselect(
                "MÓDULOS VISÍVEIS (esconde as subabas que exibem o conteúdo de cada módulo)",
                config.ABAS_DISPONIVEIS, default=abas_visiveis,
            )

            # ordem/visibilidade dos paineis dentro de cada aba que ja adota
            # o sistema de paineis registrados (ver ui/paineis.py) - por
            # enquanto MERCADO e MACRO; outras abas podem adotar o mesmo
            # padrao depois. TAMANHO nao entra aqui de proposito: e' um
            # popover "⚙" direto em cada painel, na propria aba, com efeito
            # imediato (pedido do Rodrigo, 2026-09-26) - CONFIG so' cuida de
            # reexibir um painel escondido, unico ajuste que exige vir de
            # fora (um painel escondido nao tem cabecalho pra clicar).
            nova_ordem_mercado = paineis.controle_ordem_config(
                "MERCADO", "MERCADO", _REGISTRO_PAINEIS_MERCADO, prefs,
            )
            novos_visiveis_mercado = paineis.controle_visibilidade_config(
                "MERCADO", "MERCADO", _REGISTRO_PAINEIS_MERCADO, prefs,
            )
            nova_ordem_macro = paineis.controle_ordem_config(
                "MACRO", "MACRO", _REGISTRO_PAINEIS_MACRO, prefs,
            )
            novos_visiveis_macro = paineis.controle_visibilidade_config(
                "MACRO", "MACRO", _REGISTRO_PAINEIS_MACRO, prefs,
            )
            nova_ordem_visao_geral = paineis.controle_ordem_config(
                "VISÃO GERAL", "VISÃO GERAL", _REGISTRO_PAINEIS_VISAO_GERAL, prefs,
            )
            novos_visiveis_visao_geral = paineis.controle_visibilidade_config(
                "VISÃO GERAL", "VISÃO GERAL", _REGISTRO_PAINEIS_VISAO_GERAL, prefs,
            )

            ids_casas_research = [c["id"] for c in CASAS_RESEARCH]
            nomes_casas_research = {c["id"]: c["nome"] for c in CASAS_RESEARCH}
            padrao_casas_research = [c for c in prefs.get("research_casas_ativas", []) if c in ids_casas_research]
            novas_casas_research = st.multiselect(
                "CASAS DE RESEARCH",
                ids_casas_research, default=padrao_casas_research,
                format_func=lambda cid: nomes_casas_research.get(cid, cid),
            )

            salvar = st.form_submit_button("SALVAR")
            if salvar:
                st.session_state.prefs.update({
                    "tema": novo_tema,
                    "densidade": nova_densidade,
                    "fonte": nova_fonte,
                    "formato_numerico": novo_formato,
                    "grafico_tipo": novo_tipo_grafico,
                    "grafico_periodo_padrao": novo_periodo_padrao,
                    "mm20": novo_mm20,
                    "mm50": novo_mm50,
                    "mm200": novo_mm200,
                    "abas_visiveis": novas_abas or list(config.ABAS_DISPONIVEIS),
                    "research_casas_ativas": novas_casas_research or list(config.PREFS_PADRAO["research_casas_ativas"]),
                    "atualizacao_intervalo": config.INTERVALOS_ATUALIZACAO[novo_rotulo_intervalo],
                    "ticker_tape_modo": novo_tape_modo,
                    "ticker_tape_velocidade": novo_tape_velocidade,
                    "ordem_paineis": {
                        **(prefs.get("ordem_paineis") or {}),
                        "MERCADO": nova_ordem_mercado,
                        "MACRO": nova_ordem_macro,
                        "VISÃO GERAL": nova_ordem_visao_geral,
                    },
                    "paineis_visiveis": {
                        **(prefs.get("paineis_visiveis") or {}),
                        "MERCADO": novos_visiveis_mercado,
                        "MACRO": novos_visiveis_macro,
                        "VISÃO GERAL": novos_visiveis_visao_geral,
                    },
                    # tamanho_paineis NAO entra aqui: e' salvo direto pelo
                    # popover "⚙" de cada painel (ver ui/paineis.py), com
                    # persistir_fn=_persistir_prefs - omitir a chave aqui
                    # deixa o valor atual intocado (st.session_state.prefs.update
                    # so' sobrescreve o que estiver no dict passado).
                })
                if _persistir_prefs():
                    st.success("Preferências salvas.")
                else:
                    st.warning("Preferências aplicadas nesta sessão (banco indisponível, não foram salvas).")
                st.rerun()

        if st.button("RESTAURAR PADRÃO"):
            watchlist_atual = st.session_state.prefs["watchlist"]
            st.session_state.prefs = dict(config.PREFS_PADRAO)
            st.session_state.prefs["watchlist"] = watchlist_atual
            if _persistir_prefs():
                st.success("Preferências restauradas ao padrão.")
            else:
                st.warning("Preferências restauradas nesta sessão (banco indisponível, não foram salvas).")
            st.rerun()

    # --- painel DIAGNOSTICO DE FONTES: so pro(s) e-mail(s) admin (config.obter_emails_admin) -
    # testa cada fonte de verdade, rodando neste servidor (local ou Streamlit Cloud),
    # pra saber o que funciona em producao sem depender do sandbox de desenvolvimento
    # (varios dominios ficam bloqueados por WAF/CDN so la - ver BACKLOG.md)
    if usuario["email"] in config.obter_emails_admin():
        with st.container(border=True):
            st.markdown('<div class="painel-titulo">DIAGNÓSTICO DE FONTES</div>', unsafe_allow_html=True)
            st.markdown(
                "<div class='cinza' style='font-size:0.7rem; margin-bottom:0.4rem;'>"
                "Testa cada fonte externa rodando aqui no servidor — mostra o que "
                "funciona de verdade em produção.</div>",
                unsafe_allow_html=True,
            )
            if st.button("TESTAR TODAS AS FONTES"):
                resultados = []
                with st.status("Testando fontes...", expanded=True) as status_box:
                    for fonte in diagnostico.FONTES:
                        st.write(f"Testando {fonte['nome']}...")
                        resultado = diagnostico.testar_fonte(fonte)
                        resultados.append(resultado)
                        sinal = "OK" if resultado["ok"] else "FALHOU"
                        st.write(f"→ {fonte['nome']}: {sinal} ({resultado['status']}, {resultado['tempo_ms']}ms)")
                    status_box.update(label="Diagnóstico concluído.", state="complete")

                linhas_html = "".join(
                    f"<tr><td style='text-align:left;' class='neutro'>{r['nome']}</td>"
                    f"<td class='{'alta' if r['ok'] else 'baixa'}'>{r['status']}</td>"
                    f"<td class='neutro'>{r['tempo_ms']}ms</td>"
                    f"<td class='neutro'>{r['tamanho_bytes']:,} bytes</td></tr>"
                    for r in resultados
                )
                st.markdown(
                    f"""
                    <div style="overflow-x:auto; overflow-y:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                    <thead><tr>
                        <th style="text-align:left; font-weight:400;" class="cinza">FONTE</th>
                        <th class="cinza">STATUS</th>
                        <th class="cinza">TEMPO</th>
                        <th class="cinza">TAMANHO</th>
                    </tr></thead>
                    <tbody>{linhas_html}</tbody>
                    </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
