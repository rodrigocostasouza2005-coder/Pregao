# -*- coding: utf-8 -*-
"""Interface da fase NOTICIAS.

Dois estilos de apresentacao, MESMOS dados/cache por baixo:
- "wire" denso (_linha_noticia/_renderizar_lista, original) - uma linha
  por noticia (HORA | SELO | MANCHETE | Nº FONTES | ↗), reusado por
  TOP MERCADO (ui/top_mercado_tab.py) e pelo bloco compacto da aba
  EQUITY (render_news_ticker) - **intocado** na fase 3, pra nao arriscar
  regressao em telas que nao pediram mudanca.
- "editorial" (fase 3, _cartao_noticia/_cartao_live/_renderizar_feed) -
  card com foto (quando cacheada, nunca busca de rede extra so' pra
  isso - ver data/news.py:obter_resumos_prontos), titulo, veiculo/hora/
  ticker e resumo curto SO' quando ja estiver cacheado por algum uso
  anterior (nunca gera IA pra lista inteira - so' sob demanda, dentro do
  card, igual antes). Usado so' por render_news (feed principal da
  watchlist), que tambem passa a intercalar cronologicamente os itens
  "LIVE" da Genial (Morning Call etc, ja coletados pelo RESEARCH - ver
  data/research/genial_lives.py) como cards proprios no mesmo feed.

Clique na manchete/titulo abre um card (st.dialog) com selo+score
explicado, veiculos com link, tickers citados, resumo sob demanda e
contexto compacto de RESEARCH quando existir (recomendacao/preco-alvo ja
coletados, nunca uma fonte nova); o icone ↗ abre a materia direto em
nova aba, sem passar pelo card.

As listas rodam dentro de um st.fragment - clicar num item so' reroda o
fragmento, nao a pagina inteira (era a causa real da lentidao: cada
clique reconstruia todos os widgets da lista do zero, mesmo com os dados
ja vindo de cache)."""

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.news import (
    SELO_CONFIRMADA, SELO_MENCAO, eh_fonte_confiavel, obter_noticias, obter_noticias_watchlist,
    obter_resumo_grupo, obter_resumos_prontos, ordenar_fontes_para_resumo,
)
from data.research import store as research_store
from data.research.genial import obter_recomendacoes
from ui.research_tab import _abrir_resumo_live, _casas_ativas, _EXTRATOR_POR_CASA

_TZ_SP = ZoneInfo("America/Sao_Paulo")

_ORDEM_SELOS = [SELO_CONFIRMADA, "PROVÁVEL", "NÃO CONFIRMADA", "SUSPEITA", SELO_MENCAO]

_CLASSE_SELO = {
    SELO_CONFIRMADA: "selo-confirmada",
    "PROVÁVEL": "selo-provavel",
    "NÃO CONFIRMADA": "selo-naoconfirmada",
    "SUSPEITA": "selo-suspeita",
    SELO_MENCAO: "selo-mencao",
}

_SELO_ABREV = {
    SELO_CONFIRMADA: "CONF",
    "PROVÁVEL": "PROV",
    "NÃO CONFIRMADA": "N.CONF",
    "SUSPEITA": "SUSP",
    SELO_MENCAO: "MENÇ",
}

_JANELA_PADRAO_HORAS = 48
_LIMITE_PADRAO = 50
_TRUNCA_MANCHETE = 92

# larguras relativas das colunas (nao sao px exatos, st.columns usa peso
# relativo). Ticker NAO tem mais coluna propria - entra como tag inline
# dentro do texto da manchete, so' quando existe (ver _texto_manchete) -
# tirar essa coluna elimina a coluna vazia "—" de quando nao ha ticker e
# devolve a largura pra manchete. "N fontes" virou "NF" compacto.
_COLS_PADRAO = [70, 60, 440, 45, 35]  # HORA, SELO, MANCHETE, FONTES, ABRIR(↗)
_COLS_RANK = [60, 70, 60, 380, 45, 35]  # RANK+BR/INT, HORA, SELO, MANCHETE, FONTES, ABRIR(↗)

# CSS proprio do layout wire, injetado via st.markdown (nao mexe em
# style.css, que e' de outra sessao) - reaproveita as variaveis de tema
# ja definidas la (--bg/--neutro/--cinza/--alta/--baixa/--destaque), entao
# acompanha tema/densidade escolhidos pelo usuario. Tag de selo usa
# var(--bg) como cor de texto sobre o tom de destaque: os tons de
# alta/baixa/cinza de cada tema ja sao escolhidos p/ contraste legivel
# contra --bg (uso normal do app), entao o inverso tende a manter
# contraste bom nos 4 temas sem precisar de logica por tema aqui.
#
# .st-key-news-manchete-* : Streamlit aplica automaticamente a classe
# "st-key-<key>" no wrapper de qualquer elemento com key= (mesmo
# mecanismo ja usado em style.css pra .st-key-nav_secao) - usamos isso
# pra transformar o st.button da manchete num link discreto sem tocar
# em style.css. Selector com [class*=] pega qualquer key que comece com
# esse prefixo, mesmo com o sufixo variando por linha/hash.
_CSS_WIRE = """
.w-hora, .w-fontes { color:var(--cinza); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.selo-tag {
    display:inline-block;
    padding:0.04rem 0.32rem;
    border-radius:2px;
    font-size:10px;
    font-weight:700;
    letter-spacing:0.02em;
    white-space:nowrap;
    cursor:help;
    text-align:center;
}
.selo-confirmada { background:var(--destaque); color:var(--bg); font-weight:700; }
.selo-provavel { background:var(--alta); color:var(--bg); }
.selo-naoconfirmada { background:var(--cinza); color:var(--bg); }
.selo-suspeita { background:var(--baixa); color:var(--bg); }
.selo-mencao { background:transparent; color:var(--cinza); border:1px solid var(--cinza); }

div[class*="st-key-news-manchete-"] button,
div[class*="st-key-top-manchete-"] button {
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
    color:var(--neutro) !important;
    text-decoration:none !important;
    text-align:left !important;
    justify-content:flex-start !important;
    padding:0 !important;
    margin:0 !important;
    min-height:auto !important;
    height:auto !important;
    font-family:'IBM Plex Mono', monospace !important;
    font-size:12.5px !important;
    font-weight:400 !important;
    letter-spacing:0 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    width:100% !important;
    display:block !important;
}
div[class*="st-key-news-manchete-"] button:hover,
div[class*="st-key-top-manchete-"] button:hover {
    color:var(--destaque) !important;
    background:transparent !important;
}
div[class*="st-key-news-manchete-"] button p,
div[class*="st-key-top-manchete-"] button p {
    color:inherit !important;
    font-size:inherit !important;
    text-align:left !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
}

.w-divider { border-bottom:1px solid #1A1A1A; margin:0.1rem 0 0.25rem 0; }

.w-veic-link { color:var(--destaque) !important; text-decoration:none !important; font-size:0.82rem; opacity:0.85; }
.w-veic-link:hover { opacity:1; text-decoration:underline !important; }

.w-ticker-tag {
    display:inline-block; margin:0.15rem 0.3rem 0 0; padding:0.05rem 0.4rem;
    border:1px solid var(--borda); border-radius:2px; font-size:0.72rem;
    color:var(--cinza);
}
.w-ticker-tag-watch { border-color:var(--destaque); color:var(--destaque); font-weight:600; }
.w-regiao-tag {
    font-size:0.55rem; color:var(--cinza); border:1px solid var(--borda);
    border-radius:2px; padding:0 0.18rem; margin-left:0.25rem; vertical-align:middle;
}

.w-abrir-link {
    color:var(--cinza) !important; text-decoration:none !important;
    font-size:0.85rem; display:block; text-align:center;
}
.w-abrir-link:hover { color:var(--destaque) !important; }

.w-resumo-dialogo { color:var(--neutro); font-size:0.85rem; line-height:1.5; margin-bottom:1.1rem; white-space:pre-line; }
.w-card-divisor { border-top:1px solid var(--borda); margin:0.55rem 0; }

/* pills de filtro: retas e compactas, no padrao dos botoes do terminal.
   Nesta versao do Streamlit, st.pills E st.segmented_control renderizam
   os dois sob data-testid="stButtonGroup" (conferido no bundle JS: nao
   existe "stPills" nem "stSegmentedControl" ali) - as regras de
   style.css pra esses dois seletores nunca bateram por isso. Esta regra
   e' a que efetivamente aplica. */
[data-testid="stButtonGroup"] button {
    background-color: var(--painel-bg) !important;
    border: 1px solid var(--borda) !important;
    color: var(--cinza) !important;
    border-radius: 0 !important;
    font-size: 0.75rem !important;
    padding: 0.05rem 0.6rem !important;
    min-height: 24px !important;
    box-shadow: none !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"] {
    background-color: var(--destaque) !important;
    border-color: var(--destaque) !important;
    color: #000000 !important;
    font-weight: 600;
}
/* a correcao de flex-wrap das pills (duplicada em 4 arquivos, deixava
   MACRO/MERCADO/TOP MERCADO/VISAO GERAL de fora do mesmo bug) foi
   centralizada em style.css (2026-10-08, auditoria de responsividade). */

/* linha wire (colunas de HORA/SELO/MANCHETE/FONTES etc): sem min-width:0
   nos filhos flex, o texto com white-space:nowrap dentro de uma coluna
   recusa a encolher e forca rolagem horizontal na pagina inteira (voltou
   a cortar "ranking"/"top 20" pela esquerda - ver PROGRESSO.md) */
[data-testid="stHorizontalBlock"] { overflow-x: hidden; }
[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }

/* ---- feed editorial (fase 3) ----------------------------------------
   Card denso, sem aparencia de SaaS: sem sombra, sem gradiente, sem
   border-radius exagerado - so' uma borda fina separando itens (mesma
   logica do .w-divider acima), foto pequena (ajuda a identificar a
   materia, nunca domina o conteudo) e hierarquia por tamanho/peso de
   fonte, nao por caixa colorida. */
.news-divider { border-bottom: 1px solid #1A1A1A; margin: 0.35rem 0 0.7rem 0; }
.news-item-thumb-wrap {
    position: relative; width: 60px; height: 60px; flex: 0 0 60px;
    border: 1px solid var(--borda); background: var(--painel-bg); overflow: hidden;
}
.news-item-thumb-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.news-item-thumb-fallback {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    color: var(--cinza); font-size: 0.85rem; font-weight: 700; letter-spacing: 0.02em;
    font-family: 'IBM Plex Mono', monospace;
}
.news-item-meta {
    font-size: 0.72rem; color: var(--cinza); font-family: 'IBM Plex Mono', monospace;
    margin-top: 0.18rem; line-height: 1.5;
}
.news-item-resumo {
    font-size: 0.78rem; color: var(--neutro); opacity: 0.86; line-height: 1.45; margin-top: 0.3rem;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
div[class*="st-key-news-card-titulo-"] button {
    background: transparent !important; border: none !important; box-shadow: none !important;
    color: var(--neutro) !important; text-decoration: none !important; text-align: left !important;
    justify-content: flex-start !important; padding: 0 !important; margin: 0 !important;
    min-height: auto !important; height: auto !important; font-size: 0.92rem !important;
    font-weight: 600 !important; line-height: 1.32 !important; white-space: normal !important;
    width: 100% !important; display: block !important;
}
div[class*="st-key-news-card-titulo-"] button:hover { color: var(--destaque) !important; background: transparent !important; }
div[class*="st-key-news-card-titulo-"] button p { color: inherit !important; font-size: inherit !important; text-align: left !important; white-space: normal !important; }

/* card do MORNING CALL/lives - mesma densidade, destacado so' por uma
   borda lateral (sem preencher o fundo todo, sem sombra). Selector por
   st-key (nao classe propria) porque o conteudo vem de varios
   st.markdown/st.button dentro de um st.container(key=...) - ver
   _cartao_live e o comentario sobre nao-aninhamento de <div> cru. */
div[class*="st-key-news-live-card-"] {
    border-left: 3px solid var(--destaque); padding: 0.35rem 0 0.35rem 0.6rem; margin: 0.1rem 0;
}
.news-live-badge {
    color: var(--destaque); font-weight: 700; letter-spacing: 0.04em; font-size: 0.68rem;
    font-family: 'IBM Plex Mono', monospace;
}
.news-research-ctx {
    font-size: 0.74rem; color: var(--neutro); padding: 0.25rem 0.5rem; margin-top: 0.3rem;
    border-left: 2px solid var(--borda);
}
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_WIRE}</style>", unsafe_allow_html=True)


def _fmt_hora(data_iso: str) -> str:
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m %H:%M")
    except Exception:
        return data_iso


def _dentro_de_horas(data_iso: str, horas: int) -> bool:
    try:
        dt = datetime.fromisoformat(data_iso)
    except Exception:
        return False
    return (datetime.now(_TZ_SP) - dt) <= timedelta(hours=horas)


def _texto_tag(n: dict) -> str:
    abrev = _SELO_ABREV.get(n["selo"], n["selo"])
    if n["selo"] in (SELO_MENCAO, SELO_CONFIRMADA):
        return abrev
    return f"{abrev} {n['score']}"


def _tooltip_regras(n: dict) -> str:
    if not n["regras"]:
        return "score base, nenhuma regra especial se aplicou"
    return "; ".join(n["regras"])


def _truncar(texto: str, limite: int = _TRUNCA_MANCHETE) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _plural_fontes(qtd: int) -> str:
    """Compacto de proposito ("14F") - a versao "14 fontes" nao cabia na
    coluna estreita sem cortar (ver BACKLOG.md/PROGRESSO.md)."""
    return f"{qtd}F"


def _bloco_hora_coluna(n: dict) -> str:
    return f"<div class='w-hora'>{_fmt_hora(n['data'])}</div>"


def _bloco_rank_coluna(n: dict, idx: int) -> str:
    """So pras linhas do TOP MERCADO (identificadas por ter 'importancia'
    - ver data/news.py:obter_top_mercado): posicao no ranking, com o
    criterio do calculo (nº de fontes, recencia, veiculos confiaveis,
    temas de mercado) no tooltip - deixa explicito que e' estimativa,
    nao medicao real de audiencia. Mostra tambem a tag BR/INT (campo
    'regiao' - Parte D), pra distinguir a origem quando BRASIL e
    INTERNACIONAL aparecem juntos (view TUDO)."""
    tooltip = html.escape("estimativa de relevância — " + "; ".join(n["criterio_ranking"]))
    regiao = n.get("regiao")
    badge = f"<span class='w-regiao-tag'>{regiao}</span>" if regiao else ""
    if n.get("ao_vivo"):
        badge += "<span class='w-regiao-tag' style='color:var(--destaque); border-color:var(--destaque);' title='cobertura contínua, não é uma matéria específica'>AO VIVO</span>"
    return f"<div class='w-hora' style='cursor:help;' title='{tooltip}'>#{idx + 1}{badge}</div>"


def _tickers_do_item(n: dict) -> list:
    """Itens fundidos entre tickers (data/news.py:_mesclar_entre_tickers)
    perdem 'ticker' (singular) e ganham 'tickers' (lista, quando o fato
    envolve mais de uma empresa da watchlist) - usado onde precisamos do
    conjunto de tickers de UM item (filtro por ticker; ver tambem
    _prefixo_tickers, que usa isso pro texto inline da manchete)."""
    if n.get("ticker"):
        return [n["ticker"]]
    return n.get("tickers") or []


def _prefixo_tickers(n: dict) -> str:
    """Tickers como prefixo de TEXTO PURO pra colar na frente da manchete
    (o label de st.button nao aceita HTML/markdown, entao nao da pra
    colorir so' o ticker) - string vazia se nao houver ticker nenhum, pra
    nao sobrar coluna/espaco vazio (era a coluna TICKER com "—" antes).

    Pula ticker que ja aparece logo no comeco do proprio titulo (pratica
    comum do noticiario BR: "PETR4 sobe..." ou "Petrobras (PETR4)...") -
    sem isso o prefixo duplicava o ticker de forma redundante e feia
    ("PETR4 · PETR4 vê...")."""
    tickers = _tickers_do_item(n)
    if not tickers:
        return ""
    inicio_titulo = (n.get("titulo") or "")[:40].upper()
    tickers = [t for t in tickers if t.upper() not in inicio_titulo]
    if not tickers:
        return ""
    texto = " ".join(tickers[:2])
    if len(tickers) > 2:
        texto += f" +{len(tickers) - 2}"
    return texto + "  ·  "


_MAX_VEICULOS_VISIVEIS = 6


def _linha_veiculos(fontes: list) -> str:
    """Veiculos do grupo numa linha corrida (' · '), confiaveis primeiro
    - se passar de _MAX_VEICULOS_VISIVEIS, o resto some atras de um
    "e mais N" expansivel (<details>), pra nao esticar o card."""
    vistos = set()
    unicos = []
    for f in fontes:
        if f["veiculo"] not in vistos:
            vistos.add(f["veiculo"])
            unicos.append(f)
    unicos.sort(key=lambda f: not eh_fonte_confiavel(f["veiculo"]))

    def _link(f):
        return f"<a class='w-veic-link' href='{f['link']}' target='_blank'>{html.escape(f['veiculo'])} ↗</a>"

    visiveis, resto = unicos[:_MAX_VEICULOS_VISIVEIS], unicos[_MAX_VEICULOS_VISIVEIS:]
    linha = " · ".join(_link(f) for f in visiveis)

    if resto:
        itens_resto = " · ".join(_link(f) for f in resto)
        linha += (
            " · <details style='display:inline;'>"
            f"<summary style='display:inline; cursor:pointer; color:var(--cinza);'>e mais {len(resto)}</summary>"
            f" {itens_resto}</details>"
        )
    return linha


@st.dialog("NOTÍCIA", width="large")
def _abrir_card(n: dict, watchlist: list):
    """Card com os detalhes completos do grupo - resumo e' gerado aqui,
    na hora do clique (nunca antes), com cache de obter_resumo_grupo."""
    st.markdown(f"**{html.escape(n['titulo'])}**")
    st.caption(_fmt_hora(n["data"]))

    st.link_button("ABRIR MATÉRIA ↗", n["link"], use_container_width=True)

    classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
    sufixo_score = "" if n["selo"] in (SELO_MENCAO, SELO_CONFIRMADA) else f" · {n['score']}"
    st.markdown(
        f"<span class='selo-tag {classe_selo}'>{n['selo']}{sufixo_score}</span>",
        unsafe_allow_html=True,
    )
    for regra in n["regras"]:
        st.markdown(f"<div class='cinza' style='font-size:0.76rem; margin-top:0.15rem;'>• {html.escape(regra)}</div>", unsafe_allow_html=True)

    confirmacao = n.get("cvm_confirmacao")
    if confirmacao:
        data_doc = confirmacao["data"][:10]  # so' a data (Data_Entrega da CVM nao tem hora de verdade)
        st.markdown(
            f"<div style='margin-top:0.3rem;'><a href='{confirmacao['link']}' target='_blank' "
            f"style='color:var(--alta); font-size:0.76rem;'>↗ ver documento oficial na CVM "
            f"({html.escape(confirmacao['tipo_label'])}, {data_doc})</a></div>",
            unsafe_allow_html=True,
        )

    if n.get("tickers"):
        tags = "".join(
            f"<span class='w-ticker-tag{' w-ticker-tag-watch' if t in watchlist else ''}'>{t}</span>"
            for t in n["tickers"]
        )
        st.markdown(f"<div style='margin-top:0.4rem;'>{tags}</div>", unsafe_allow_html=True)

    st.markdown("<div class='w-card-divisor'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Veículos ({n['fontes_count']})</div>"
        f"<div style='font-size:0.82rem;'>{_linha_veiculos(n['fontes'])}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='w-card-divisor'></div>", unsafe_allow_html=True)
    st.markdown("<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Resumo</div>", unsafe_allow_html=True)
    with st.spinner("Gerando resumo..."):
        fontes_ordenadas = ordenar_fontes_para_resumo(n["fontes"])
        titulos_grupo = tuple(n.get("titulos") or [n["titulo"]])
        resultado = obter_resumo_grupo(n["titulo"], fontes_ordenadas, titulos_grupo)

    if resultado["resumo"]:
        imagem = resultado.get("imagem")
        if imagem:
            st.markdown(
                f"<img src='{html.escape(imagem)}' loading='lazy' style='width:100%; max-height:260px; "
                f"object-fit:cover; border:1px solid var(--borda); margin-bottom:0.6rem;' "
                f"onerror=\"this.style.display='none';\">",
                unsafe_allow_html=True,
            )
        st.markdown(f"<div class='w-resumo-dialogo'>{html.escape(resultado['resumo'])}</div>", unsafe_allow_html=True)
    else:
        motivo = resultado.get("motivo_indisponivel") or "motivo desconhecido"
        st.caption(f"resumo indisponível ({motivo})")

    _bloco_contexto_research(_tickers_do_item(n), watchlist)


_LIMITE_CONTEXTO_RESEARCH = 3


def _bloco_contexto_research(tickers: list, watchlist: list):
    """Contexto compacto de RESEARCH (fase 3, integracao NEWS<->RESEARCH):
    so' aparece quando ja existe recomendacao/preco-alvo REAL coletado
    pela Genial (mesma funcao cacheada - obter_recomendacoes - que a aba
    RESEARCH ja usa, ver ui/research_tab.py:_painel_watchlist) pra algum
    ticker do item. Zero fonte nova, zero chamada de IA, nunca N+1 (so'
    chamado aqui, dentro do dialog ja aberto - nunca na lista inteira)."""
    tickers_watch = [t for t in tickers if t in watchlist] or tickers
    if not tickers_watch:
        return
    recomendacoes = obter_recomendacoes() or []
    relevantes = [r for r in recomendacoes if r["ticker"] in tickers_watch][:_LIMITE_CONTEXTO_RESEARCH]
    if not relevantes:
        return

    st.markdown("<div class='w-card-divisor'></div>", unsafe_allow_html=True)
    st.markdown("<div class='cinza' style='font-size:0.72rem; text-transform:uppercase; margin-bottom:0.2rem;'>Research</div>", unsafe_allow_html=True)
    for r in relevantes:
        potencial = r.get("potencial_pct")
        potencial_txt = f" · potencial {potencial:.1f}%" if potencial is not None else ""
        preco_alvo = r.get("preco_alvo")
        preco_txt = f" · preço-alvo R$ {preco_alvo:.2f}" if preco_alvo is not None else ""
        st.markdown(
            f"<div class='news-research-ctx'><span style='color:var(--destaque); font-weight:600;'>{r['ticker']}</span>"
            f" · Genial: <b>{html.escape(str(r['recomendacao']))}</b>{potencial_txt}{preco_txt}</div>",
            unsafe_allow_html=True,
        )


def _linha_noticia(n: dict, idx: int, mostrar_ticker: bool, prefixo: str, watchlist: list):
    eh_ranking = "importancia" in n
    cols_pesos = _COLS_RANK if eh_ranking else _COLS_PADRAO
    colunas = st.columns(cols_pesos, gap="xsmall", vertical_alignment="center")
    i = 0

    if eh_ranking:
        with colunas[i]:
            st.markdown(_bloco_rank_coluna(n, idx), unsafe_allow_html=True)
        i += 1

    with colunas[i]:
        st.markdown(_bloco_hora_coluna(n), unsafe_allow_html=True)
    i += 1

    with colunas[i]:
        # tooltip so' aqui (no selo) - o help= da manchete foi removido de
        # proposito: um tooltip nativo (title=) sobre a lista renderiza
        # POR CIMA de qualquer coisa, inclusive um st.dialog aberto, se o
        # mouse ainda estiver sobre a linha quando o card abre
        classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
        tooltip = html.escape(_tooltip_regras(n))
        st.markdown(f"<span class='selo-tag {classe_selo}' title='{tooltip}'>{_texto_tag(n)}</span>", unsafe_allow_html=True)
    i += 1

    with colunas[i]:
        prefixo_ticker = _prefixo_tickers(n) if mostrar_ticker else ""
        texto_manchete = _truncar(prefixo_ticker + n["titulo"])
        chave_botao = f"news-manchete-{prefixo}-{idx}-{abs(hash(n['link']))}"
        if st.button(texto_manchete, key=chave_botao):
            _abrir_card(n, watchlist)
    i += 1

    with colunas[i]:
        st.markdown(f"<div class='w-fontes'>{_plural_fontes(n['fontes_count'])}</div>", unsafe_allow_html=True)
    i += 1

    with colunas[i]:
        # link direto pra materia, sem passar pelo card - <a> puro (nao e'
        # widget do Streamlit), abre em nova aba sem disparar rerun nenhum
        st.markdown(f"<a class='w-abrir-link' href='{n['link']}' target='_blank' title='Abrir matéria'>↗</a>", unsafe_allow_html=True)

    st.markdown("<div class='w-divider'></div>", unsafe_allow_html=True)


@st.fragment
def _renderizar_lista(itens: list, mostrar_ticker: bool, prefixo: str, watchlist: list):
    """Reusado pela aba TOP MERCADO - lista + card, sem nenhum resumo
    automatico (so sob demanda, dentro do card). @st.fragment: clicar
    numa manchete (pra abrir o card) so' reroda ISSO aqui, nao a pagina
    inteira - antes, cada clique refazia render_news/render_top_mercado
    do zero (embora os DADOS ja viessem de cache, reconstruir todos os
    widgets da lista inteira a cada clique era a lentidao real)."""
    for idx, n in enumerate(itens):
        _linha_noticia(n, idx, mostrar_ticker, prefixo, watchlist)


# ===================== feed editorial (fase 3) =====================
#
# NOTICIAS vira um feed editorial de terminal: card com foto (so' quando
# ja cacheada - nunca 1 chamada de rede por card), titulo, veiculo/hora/
# ticker e um teaser do resumo (idem, so' se ja cacheado); e os itens
# "LIVE" da Genial (Morning Call, Resumo da Manha, Fechamento de Mercado
# etc - ja coletados pelo RESEARCH, ver data/research/genial_lives.py)
# passam a aparecer intercalados CRONOLOGICAMENTE no mesmo feed, com um
# card proprio (_cartao_live) claramente identificado pelo programa+casa,
# em vez de ficarem numa secao isolada. _linha_noticia/_renderizar_lista
# acima (wire denso) continuam intocados - usados so' por TOP MERCADO e
# pelo bloco compacto da aba EQUITY (render_news_ticker).

_TRUNCA_TEASER = 220
_CAMPOS_TEASER = ("O QUE ACONTECEU", "IMPACTO")


def _resumo_teaser(resumo: str, limite: int = _TRUNCA_TEASER) -> str:
    """Teaser de 2-4 linhas pro card do feed, extraido do resumo
    estruturado completo de NEWS (O QUE ACONTECEU/NUMEROS/IMPACTO/
    PROXIMOS PASSOS, ver data/news.py) - nunca o bloco inteiro (verboso
    demais pra uma linha de lista, o bloco completo continua disponivel
    no dialog). Cai pro texto cru truncado se o formato nao bater (ex:
    resumo baseado so' em manchetes, que tem o mesmo formato + sufixo)."""
    campos = {}
    for linha in resumo.splitlines():
        campo, _, valor = linha.partition(":")
        if valor:
            campos[campo.strip().upper()] = valor.strip()
    partes = [
        campos[c] for c in _CAMPOS_TEASER
        if campos.get(c) and "informado" not in campos[c].lower()
    ]
    teaser = " ".join(partes).strip() or resumo.strip()
    return _truncar(teaser, limite)


def _teaser_live(resumo: str, limite: int = _TRUNCA_TEASER) -> str:
    """Teaser pro card do feed a partir do resumo narrativo do RESEARCH
    (blocos tipo 'O QUE IMPORTA HOJE' em MAIUSCULAS numa linha propria -
    ver data/research/resumir.py) - pula a(s) linha(s) que sao so' o
    titulo do bloco e tira a tag <b> (so' faz sentido dentro do dialog
    completo; aqui e' so' um preview em texto puro)."""
    sem_tags = resumo.replace("<b>", "").replace("</b>", "")
    linhas = [l.strip() for l in sem_tags.splitlines() if l.strip()]
    corpo = [l for l in linhas if not (l.isupper() and len(l) < 40)]
    texto = " ".join(corpo) if corpo else " ".join(linhas)
    return _truncar(texto, limite)


def _thumb_html(imagem: str | None, iniciais: str) -> str:
    """Thumbnail do card: foto (quando ja cacheada - ver
    data/news.py:obter_resumos_prontos, nunca uma busca de rede aqui)
    com fallback visual discreto (iniciais do veiculo, sem foto nenhuma)
    se a imagem faltar OU falhar ao carregar no navegador - onerror troca
    pro fallback, nunca deixa um icone de imagem quebrada no feed."""
    marca = html.escape((iniciais or "?")[:2].upper())
    if not imagem:
        return f"<div class='news-item-thumb-wrap'><div class='news-item-thumb-fallback'>{marca}</div></div>"
    return (
        "<div class='news-item-thumb-wrap'>"
        f"<img src='{html.escape(imagem)}' loading='lazy' alt='' "
        "onerror=\"this.style.display='none'; this.nextElementSibling.style.display='flex';\">"
        f"<div class='news-item-thumb-fallback' style='display:none;'>{marca}</div>"
        "</div>"
    )


def _meta_noticia_html(n: dict, mostrar_ticker: bool, watchlist: list) -> str:
    classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
    tooltip = html.escape(_tooltip_regras(n))
    partes = [
        f"<span class='selo-tag {classe_selo}' title='{tooltip}'>{_texto_tag(n)}</span>",
        html.escape((n.get("veiculos") or [""])[0]),
        _fmt_hora(n["data"]),
    ]
    if mostrar_ticker:
        for t in _tickers_do_item(n)[:3]:
            classe = "w-ticker-tag w-ticker-tag-watch" if t in watchlist else "w-ticker-tag"
            partes.append(f"<span class='{classe}'>{t}</span>")
    partes.append(_plural_fontes(n["fontes_count"]))
    partes.append(f"<a class='w-abrir-link' style='display:inline;' href='{n['link']}' target='_blank' title='Abrir matéria'>↗ abrir</a>")
    return f"<div class='news-item-meta'>{' · '.join(p for p in partes if p)}</div>"


def _cartao_noticia(n: dict, idx: int, mostrar_ticker: bool, prefixo: str, watchlist: list, resultado: dict | None):
    """Card editorial de UMA noticia/grupo - foto+resumo so' quando
    `resultado` ja vier preenchido (leitura em lote feita 1x pro feed
    inteiro ANTES deste loop, ver obter_resumos_prontos/render_news) -
    nunca gera nada aqui. Clique no titulo abre o dialog completo
    (_abrir_card, inalterado), que ai' sim gera o resumo sob demanda se
    ainda nao existir."""
    cols = st.columns([1, 9], gap="small", vertical_alignment="top")
    with cols[0]:
        imagem = (resultado or {}).get("imagem")
        iniciais = (n.get("veiculos") or [n["titulo"]])[0]
        st.markdown(_thumb_html(imagem, iniciais), unsafe_allow_html=True)
    with cols[1]:
        prefixo_ticker = _prefixo_tickers(n) if mostrar_ticker else ""
        chave_botao = f"news-card-titulo-{prefixo}-{idx}-{abs(hash(n['link']))}"
        if st.button(prefixo_ticker + n["titulo"], key=chave_botao):
            _abrir_card(n, watchlist)
        st.markdown(_meta_noticia_html(n, mostrar_ticker, watchlist), unsafe_allow_html=True)
        if resultado and resultado.get("resumo"):
            st.markdown(
                f"<div class='news-item-resumo'>{html.escape(_resumo_teaser(resultado['resumo']))}</div>",
                unsafe_allow_html=True,
            )
    st.markdown("<div class='news-divider'></div>", unsafe_allow_html=True)


def _chave_ordenacao_live(rel: dict) -> str:
    """Timestamp usado SO' PRA ORDENAR o item LIVE dentro do feed
    unificado - usa publicado_em (hora REAL, quando a fonte preencheu -
    hoje so' Genial Lives, ver data/research/genial_lives.py) ou cai pro
    meio-dia da DATA de publicacao quando so' isso existir (so' posiciona
    o item no dia certo; NUNCA exibido - ver _hora_exibicao_live, que so'
    mostra HH:MM quando publicado_em de fato existe, nunca inventa hora)."""
    publicado = rel.get("publicado_em")
    if publicado:
        return publicado
    data = rel.get("data") or ""
    return f"{data}T12:00:00-03:00" if data else "1970-01-01T00:00:00+00:00"


def _hora_exibicao_live(rel: dict) -> str:
    publicado = rel.get("publicado_em")
    if not publicado:
        return ""
    try:
        return datetime.fromisoformat(publicado).astimezone(_TZ_SP).strftime("%H:%M")
    except Exception:
        return ""


def _cartao_live(rel: dict, idx: int, prefixo: str):
    """Card editorial de um item LIVE (Morning Call/Resumo da Manha/
    Fechamento etc) - mesma densidade dos cards de noticia, diferenciado
    so' por uma borda lateral + selo CASA/PROGRAMA (sem preencher o fundo
    todo, sem sombra). st.container(key=...) (nao HTML cru) pra' borda
    envolver de verdade titulo+meta+teaser - um <div> aberto num
    st.markdown e fechado em outro NAO aninha no DOM real do Streamlit
    (cada st.markdown/st.button e' seu proprio elemento isolado)."""
    chave_container = f"news-live-card-{prefixo}-{idx}-{abs(hash(rel['link']))}"
    with st.container(key=chave_container):
        hora = _hora_exibicao_live(rel)
        programa = html.escape((rel.get("autor") or "LIVE").upper())
        casa = html.escape((rel.get("casa") or "").upper())
        cabecalho = f"<span class='news-live-badge'>{programa} · {casa}</span>"
        if hora:
            cabecalho += f" <span class='w-hora'>{hora}</span>"
        st.markdown(cabecalho, unsafe_allow_html=True)

        chave_botao = f"news-card-titulo-live-{prefixo}-{idx}-{abs(hash(rel['link']))}"
        if st.button(rel["titulo"], key=chave_botao):
            _abrir_resumo_live(rel, _EXTRATOR_POR_CASA.get(rel["casa"]))

        if rel.get("resumo"):
            st.markdown(
                f"<div class='news-item-resumo'>{html.escape(_teaser_live(rel['resumo']))}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("Resumo ainda não gerado — clique no título para gerar.")
    st.markdown("<div class='news-divider'></div>", unsafe_allow_html=True)


def _lives_para_feed(prefs: dict) -> list:
    """Itens LIVE (Morning Call etc da Genial) pra intercalar no feed do
    NEWS - SO' LEITURA do que o RESEARCH ja coletou (mesma tabela/cache
    de sempre, data.research.store.listar_itens) - nunca dispara coleta
    nova daqui: quem e' responsavel por coletar e' a aba RESEARCH (ver
    data/research/__init__.py:coletar_pendentes); ler de novo aqui so'
    duplicaria a responsabilidade sem ganhar nada, e coletar a cada
    abertura do NEWS violaria "nao coletar a cada rerun". Respeita a
    mesma preferencia de casas ativas da aba RESEARCH (CONFIG > CASAS DE
    RESEARCH) - se o usuario desligou "Genial (Lives)" la, tambem nao
    aparece aqui. [] (nunca None) se desligado ou se o Supabase falhar -
    o feed principal de noticias nunca e' derrubado por isso."""
    if "genial_lives" not in _casas_ativas(prefs):
        return []
    return research_store.listar_itens(["Genial (Lives)"]) or []


def _dt_ordenacao(chave_data: str) -> datetime:
    """Parseia 'chave_data' (ISO, offsets podem variar: noticias vem em
    -03:00 jah convertido, lives podem vir em +00:00 - ver
    _chave_ordenacao_live) pra um datetime tz-aware COMPARAVEL de
    verdade. Comparar as STRINGS direto (como _dentro_de_horas faz,
    seguro so' porque so' testa distancia pra 'agora') ordenaria errado
    aqui: '09:42-03:00' (meio-dia UTC) viria ANTES de '11:30+00:00' na
    ordenacao lexicografica, mesmo sendo horario UTC mais tarde - bug
    real pego pelo teste de ordenacao cronologica (tests/test_news_fase3.py)."""
    try:
        return datetime.fromisoformat(chave_data)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _montar_feed(noticias: list, lives: list) -> list:
    """Combina noticias + lives num feed CRONOLOGICO unico - funcao pura
    (sem Streamlit, testavel isoladamente). Cada item fica envelopado com
    'tipo_feed' (NOTICIA/LIVE) + 'chave_data' (string ISO, usada pelos
    filtros de janela/VER MAIS existentes, que ja operam so' com uma
    string de data - ver _dentro_de_horas) - a ORDENACAO em si usa
    _dt_ordenacao (datetime real, nunca a string crua - ver acima)."""
    itens = [{"tipo_feed": "NOTICIA", "chave_data": n["data"], "dado": n} for n in noticias]
    itens += [{"tipo_feed": "LIVE", "chave_data": _chave_ordenacao_live(r), "dado": r} for r in lives]
    itens.sort(key=lambda it: _dt_ordenacao(it["chave_data"]), reverse=True)
    return itens


@st.fragment
def _renderizar_feed_editorial(itens_feed: list, watchlist: list, resumos_prontos: dict, prefixo: str):
    """Feed editorial (fase 3): cards de noticia + lives intercalados
    cronologicamente. @st.fragment, mesmo motivo de _renderizar_lista:
    clicar num item so' reroda isso aqui, nao a pagina inteira."""
    for idx, item in enumerate(itens_feed):
        if item["tipo_feed"] == "LIVE":
            _cartao_live(item["dado"], idx, prefixo)
        else:
            n = item["dado"]
            _cartao_noticia(n, idx, True, prefixo, watchlist, resumos_prontos.get(n["link"]))


@st.fragment
def render_news(prefs: dict):
    """Ponto de entrada da aba NEWS, chamado pelo app.py. Feed editorial
    (fase 3) da watchlist: noticias + Morning Call/lives da Genial
    intercalados cronologicamente (ver _montar_feed), com filtro
    compacto (pills) por ticker e selo. Padrão: últimas 48h, até 50
    itens, com VER MAIS pra expandir. O teaser que aparece direto no
    card (foto+resumo curto) so' usa o que JA estiver cacheado por algum
    uso anterior (obter_resumos_prontos - 1 leitura em lote pra tela
    inteira, nunca 1 chamada de IA/rede por card); resumo completo
    continua so' sob demanda, dentro do dialog (clique no título) -
    comportamento inalterado.

    @st.fragment (perf, bug real corrigido 2026-10-08): so' o feed
    (_renderizar_feed_editorial) era fragment - os pills de ticker/selo
    e o botão VER MAIS, que ficam AQUI fora, continuavam disparando
    rerun da PÁGINA INTEIRA a cada clique (o fragment interno não
    blinda widgets fora dele). Isso incluía reconsultar o Supabase via
    obter_noticias_watchlist/_lives_para_feed/obter_resumos_prontos de
    novo a cada clique de filtro. Mesmo padrão já usado em RESEARCH
    (ponto de entrada inteiro é o fragment, não só o feed interno)."""
    _injetar_css()

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">NOTÍCIAS</div>', unsafe_allow_html=True)

        watchlist = prefs.get("watchlist") or []
        if not watchlist:
            st.info("Adicione tickers na barra lateral para ver notícias.")
            return

        noticias, falhas = obter_noticias_watchlist(watchlist)
        lives = _lives_para_feed(prefs)

        if falhas:
            st.warning("Indisponível no momento: " + ", ".join(falhas) + ".")

        if not noticias and not lives:
            st.info("Nenhuma notícia encontrada para os tickers da sua watchlist no momento.")
            return

        st.caption(
            f"Mostrando itens das últimas {_JANELA_PADRAO_HORAS}h por padrão (clique em VER MAIS pra ver até "
            f"5 dias) — selo de confiabilidade calculado por regras simples (fonte, nº de veículos, linguagem), "
            f"não é uma verificação factual definitiva. Clique num item para ver os detalhes."
        )

        # so' tickers da watchlist do usuario - _tickers_do_item(n) ja deveria
        # trazer so' isso na pratica (obter_noticias_watchlist so' busca por
        # tickers da watchlist), mas o filtro exige a intersecao explicita
        # como garantia (achado real: o filtro chegou a mostrar codigo de
        # contrato futuro tipo WDOV26/WINV26, que nao e' um ticker de acao
        # nem o que o usuario espera ver aqui)
        watchlist_set = set(watchlist)
        tickers_no_feed = ["TODOS"] + sorted({t for n in noticias for t in _tickers_do_item(n) if t in watchlist_set})
        selos_no_feed = ["TODOS"] + [s for s in _ORDEM_SELOS if s in {n["selo"] for n in noticias}]

        filtro_ticker = st.pills(
            "Ticker", tickers_no_feed, default="TODOS", selection_mode="single", key="news_pill_ticker",
        ) or "TODOS"
        filtro_selo = st.pills(
            "Selo", selos_no_feed, default="TODOS", selection_mode="single", key="news_pill_selo",
        ) or "TODOS"

        # filtro de ticker/selo so' se aplica a NOTICIA (LIVE nao tem selo
        # nem ticker unico) - com algum filtro ativo, os lives somem do
        # feed (filtrar por ticker/selo e' sobre uma noticia de mercado
        # especifica, nao sobre o programa do dia)
        noticias_filtradas = [
            n for n in noticias
            if (filtro_ticker == "TODOS" or filtro_ticker in _tickers_do_item(n))
            and (filtro_selo == "TODOS" or n["selo"] == filtro_selo)
        ]
        lives_filtradas = lives if (filtro_ticker == "TODOS" and filtro_selo == "TODOS") else []

        feed = _montar_feed(noticias_filtradas, lives_filtradas)

        if not feed:
            st.info("Nenhuma notícia com esses filtros.")
            return

        if "news_ver_mais" not in st.session_state:
            st.session_state.news_ver_mais = False
        if "news_limite" not in st.session_state:
            st.session_state.news_limite = _LIMITE_PADRAO

        if st.session_state.news_ver_mais:
            candidatos = feed
        else:
            candidatos = [it for it in feed if _dentro_de_horas(it["chave_data"], _JANELA_PADRAO_HORAS)] or feed

        mostrar = candidatos[: st.session_state.news_limite]

        st.markdown(
            f"<div class='cinza' style='font-size:0.68rem; margin:0.3rem 0 0.4rem 0;'>{len(mostrar)} de {len(candidatos)} item(ns)</div>",
            unsafe_allow_html=True,
        )

        resumos_prontos = obter_resumos_prontos([it["dado"] for it in mostrar if it["tipo_feed"] == "NOTICIA"])
        _renderizar_feed_editorial(mostrar, watchlist, resumos_prontos, prefixo="feed")

        falta_mostrar = len(candidatos) - len(mostrar)
        falta_janela = not st.session_state.news_ver_mais and len(feed) > len(candidatos)
        if falta_mostrar > 0 or falta_janela:
            if st.button("VER MAIS", key="news_ver_mais_btn"):
                st.session_state.news_ver_mais = True
                st.session_state.news_limite += _LIMITE_PADRAO
                st.rerun()


def render_news_ticker(ticker: str, prefs: dict):
    """Bloco compacto com as noticias mais recentes de UM ticker, pra
    encaixar na aba EQUITY (ex: dentro de um st.container(border=True))."""
    _injetar_css()
    st.markdown('<div class="painel-titulo">NOTÍCIAS</div>', unsafe_allow_html=True)

    noticias = obter_noticias(ticker)
    if noticias is None:
        st.warning("Fonte de notícias indisponível no momento.")
        return
    if not noticias:
        st.info("Nenhuma notícia recente encontrada.")
        return

    _renderizar_lista(noticias[:8], mostrar_ticker=False, prefixo=f"eq-{ticker}", watchlist=prefs.get("watchlist") or [])
