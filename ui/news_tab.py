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
import re
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from data.news import (
    SELO_CONFIRMADA, SELO_MENCAO, eh_fonte_confiavel, extrair_por_que_importa, imagem_pronta_do_grupo,
    obter_noticias, obter_noticias_watchlist, obter_resumo_grupo, obter_resumos_prontos,
    ordenar_fontes_para_resumo, separar_secoes_resumo,
)
from data.research import store as research_store
from data.research.genial import obter_recomendacoes
from ui import navegacao
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
_PESO_COL_THUMB = 36  # miniatura opcional (TOP MERCADO / VISÃO GERAL), antes das demais

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

.w-divider { border-bottom:1px solid var(--borda); margin:0.1rem 0 0.25rem 0; }

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
.news-divider { border-bottom: 1px solid var(--borda); margin: 0.35rem 0 0.7rem 0; }
/* miniatura da lista wire (TOP MERCADO / VISÃO GERAL) - pequena de
   propósito: identifica a matéria sem virar portal de notícias */
.w-thumb {
    position: relative; width: 30px; height: 30px; overflow: hidden; margin: 1px 0;
    border: 1px solid var(--borda); background: var(--painel-bg);
}
.w-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.w-thumb-fallback { position: absolute; inset: 0; }
/* celular: as colunas da lista wire empilham (uma por linha) - a
   miniatura viraria mais uma linha por item; some só aqui (o feed
   NOTÍCIAS mantém a miniatura lado a lado com o título) */
@media (max-width: 640px) {
    div[data-testid="stColumn"]:has(.w-thumb) { display: none !important; }
}
.news-item-thumb-wrap {
    /* redesign 2026-10-19 (pedido explícito: capa pequena demais, "mesma
       formatação de antes") - de 60x60 (quadrado, quase ícone) pra 4:3
       de verdade, área visualmente relevante sem empilhar acima do texto
       (mantém lado a lado, card continua compacto em altura). */
    position: relative; width: 72px; height: 54px; flex: 0 0 72px;
    border: 1px solid var(--borda); background: var(--painel-bg); overflow: hidden;
}
.news-item-thumb-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.news-item-thumb-fallback {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    color: var(--cinza); font-size: 1.1rem; font-weight: 700; letter-spacing: 0.02em;
    font-family: 'IBM Plex Mono', monospace;
}
.news-item-meta {
    font-size: 0.72rem; color: var(--cinza); font-family: 'IBM Plex Mono', monospace;
    margin-top: 0.18rem; line-height: 1.5;
}
.news-item-resumo {
    /* separação visual real do bloco de manchete/meta acima (pedido:
       "resumo editorial visualmente separado da manchete") - antes era
       só um margin-top com opacidade, sem nenhuma fronteira visual. */
    font-size: 0.78rem; color: var(--neutro); opacity: 0.86; line-height: 1.45;
    margin-top: 0.4rem; padding-top: 0.4rem; border-top: 1px solid var(--borda);
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.news-ia-chip {
    display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 0.6rem;
    font-weight: 700; letter-spacing: 0.05em; color: var(--cinza); opacity: 0.8;
    border: 1px solid var(--borda); padding: 0.02rem 0.3rem; margin-right: 0.4rem;
    vertical-align: 1px; -webkit-box-orient: horizontal; /* nunca corta dentro do clamp acima */
}
.news-ia-chip-fraco { opacity: 0.55; }
/* FIX (2026-10-08, causa raiz real - achado novo, nao e' repeticao das 2
   tentativas descartadas em sessoes anteriores, documentadas no
   BACKLOG.md): o bug de sobreposicao do card de noticia (meta/resumo
   cobertos pelo divisor do item seguinte quando o texto quebra p/ 2+
   linhas) NAO e' causa do texto quebrar em si - e' um wrapper interno do
   proprio Streamlit (`stElementContainer > .stMarkdown > div[flex] >
   [data-testid="stMarkdownContainer"]`) que mede a altura errada por 2
   motivos, confirmados com Playwright medindo bounding box real de cada
   nivel da arvore contra o CSS computado (nao suspeita, reproduzido e
   corrigido num harness isolado, mesma tecnica ja usada p/ MERCADO/CVM):
   1) o `div` entre `.stMarkdown` e `stMarkdownContainer` e'
      `display:flex; flex-direction:row; flex-wrap:nowrap` com 1 filho
      so' - nesse caso o Chromium as vezes calcula a altura "auto" do
      flex container usando a largura ANTES do texto quebrar (altura de
      1 linha so'), nao a altura real pos-wrap; forcar esse wrapper pra
      `display:block` (o unico filho preenche 100% da largura de
      qualquer jeito, visualmente identico) elimina o calculo de flex
      errado.
   2) `[data-testid="stMarkdownContainer"]` do proprio Streamlit vem com
      `margin-bottom:-16px` embutido (serve pra' compensar a margem
      inferior padrao de paragrafo <p> quando o markdown é texto comum) -
      nosso HTML aqui e' um <div> cru sem <p>, entao não há margem de
      paragrafo nenhuma pra compensar; essa margem negativa so' colapsa
      pra' dentro do container pai (`stElementContainer`, que mede a
      altura real do card), encurtando-o ~16px a menos que o conteudo
      real renderizado - exatamente o "container menor que o conteudo"
      medido nas 2 tentativas anteriores (13-16px de diferença, mesma
      ordem de grandeza). Zerar essa margem SO' dentro do escopo do
      card de noticia (via :has(), não global - não mexe no resto do
      markdown do app) resolve o encurtamento.
   Validado com harness Playwright isolado (dados sinteticos, mesmo
   style.css real), 390/768/1280px, screenshot antes/depois: a linha de
   metadados/resumo aparece completa (tickers + nº de fontes + "↗ abrir")
   sem nenhuma sobreposição pelo divisor, com texto de 1 OU 2 linhas. */
div[data-testid="stMarkdown"]:has(.news-item-meta, .news-item-resumo) > div {
    display: block !important;
}
div[data-testid="stMarkdown"]:has(.news-item-meta, .news-item-resumo) [data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
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

/* ---- modal editorial da noticia (FASE C, 2026-10-09) -----------------
   Capa (imagem OU fallback elegante) no topo, manchete, 1 linha de
   metadados essenciais, corpo em paragrafos com respiro, LEITURA DE
   MERCADO destacada so' por borda lateral (nunca uma caixa colorida
   competindo com o conteudo) e o resto (veiculos/tickers/score) em
   fonte pequena/cinza no rodape - nada de lista de campos internos ou
   divisores em excesso (era a critica real do Rodrigo sobre o modal
   antigo parecer "log de depuracao"). */
/* Causa raiz do corte de imagem (auditoria 2026-10-22): a capa sempre
   forçava object-fit:cover numa caixa de altura fixa, qualquer que fosse
   a proporção real da foto - uma foto vertical (retrato) ou muito
   panorâmica perdia boa parte do enquadramento original (laterais ou
   topo/base cortados). As 5 regras de altura que existiram aqui ao longo
   do tempo (base + 2 breakpoints + 1 específica do fallback + 2 dentro de
   "div[data-testid=stDialog] .news-capa") também tinham especificidade
   CSS diferente entre si - a mais específica (escopada ao dialog) sempre
   vencia, deixando pelo menos 3 delas como código morto (nunca realmente
   aplicadas), incluindo a redução de altura no celular. Consolidado aqui:
   uma única altura responsiva + a escolha cobrir/conter decidida no
   PYTHON a partir da proporção REAL da imagem (_capa_data_uri já abre a
   foto com PIL pra redimensionar - o aspect ratio sai de graça dali, ver
   _renderizar_capa) - nunca um palpite de CSS. "conter" nunca deixa
   espaço vazio liso: o fundo desfocado usa a MESMA foto. */
.news-capa {
    position: relative; width: 100%; height: clamp(170px, 30vh, 300px);
    overflow: hidden; border: 1px solid var(--borda); background: var(--painel-bg);
    margin-bottom: 0.7rem; border-radius: 4px;
}
.news-capa-fundo {
    position: absolute; inset: -12px; background-size: cover; background-position: center;
    filter: blur(22px) brightness(0.45) saturate(1.1); transform: scale(1.12); display: none;
}
.news-capa--conter .news-capa-fundo { display: block; }
.news-capa img {
    position: relative; width: 100%; height: 100%; display: block; z-index: 1;
}
.news-capa--cobrir img { object-fit: cover; object-position: center 38%; }
.news-capa--conter img { object-fit: contain; }
/* sem foto: caixa baixa (nunca reserva o mesmo espaço de uma foto real) */
.news-capa:not(:has(img)) { height: 72px; }
/* celular: altura menor que no desktop (tela mais estreita, a imagem não
   pode empurrar manchete/resumo pra fora da área visível) - ÚNICA regra
   de altura pra mobile agora (as 3 versões antigas conflitantes sumiram,
   ver comentário acima). */
@media (max-width: 640px) {
    .news-capa { height: 140px; }
    .news-capa:not(:has(img)) { height: 56px; }
}
.news-capa-fallback {
    display: flex; align-items: center; justify-content: center; height: 100%;
    flex-direction: column; gap: 0.3rem;
}
.news-capa-fallback span {
    font-family: 'IBM Plex Mono', monospace; font-size: 1.1rem; letter-spacing: 0.1em;
    color: var(--cinza); opacity: 0.55; text-transform: uppercase;
}
.news-headline {
    font-family: Georgia,'Source Serif 4','Times New Roman',Times,serif;
    font-size: 1.22rem; font-weight: 700; line-height: 1.3; color: var(--neutro);
    margin-bottom: 0.35rem; letter-spacing: -0.01em;
}
.news-meta-line {
    font-size: 0.74rem; color: var(--cinza); font-family: 'IBM Plex Mono', monospace;
    line-height: 1.6; margin-bottom: 0.6rem;
}
.news-meta-line a { color: var(--destaque); text-decoration: none; }
.news-meta-line a:hover { text-decoration: underline; }
.news-resumo-rotulo {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; color: var(--cinza);
    text-transform: uppercase; margin-bottom: 0.4rem; opacity: 0.85;
}
.news-resumo-rotulo span { font-weight: 400; text-transform: none; }
/* Prosa editorial (resumo/interpretação/rodapé) na mesma tipografia humana
   usada no Morning Call (mesmo espírito do PR #62/reconstrução da aba
   Morning Call, 22/10/2026) - antes herdava a fonte monoespaçada global
   do app inteiro (style.css: html/body/[class*=css] em IBM Plex Mono
   !important), deixando o resumo com cara de log técnico em vez de texto
   de leitura. Mono reservado a selo/hora/score/tickers (.news-meta-line,
   .selo-tag, .w-ticker-tag), que continuam monoespaçados de propósito. */
.news-corpo-p {
    font-family: 'Libre Franklin','Segoe UI',Arial,Helvetica,sans-serif;
    font-size: 0.92rem; line-height: 1.68; color: var(--neutro); margin-bottom: 0.85rem;
    max-width: 68ch;
}
.news-parcial-nota {
    font-family: 'Libre Franklin','Segoe UI',Arial,Helvetica,sans-serif;
    font-size: 0.7rem; color: var(--cinza); opacity: 0.8; margin: -0.3rem 0 0.9rem 0;
    font-style: italic;
}
/* "Por que importa": relevância econômica/financeira do fato (quando a
   fonte sustentar) - mesma densidade/borda lateral do bloco de impacto
   potencial abaixo, mas em --cinza (não --destaque): é uma seção à
   parte do RESUMO, mas tipicamente mais próxima de fato apoiado em algo
   que a própria fonte já deu (ex: participação no índice/na receita) do
   que uma leitura especulativa - a cor mais neutra reflete isso, sem
   competir visualmente com o destaque reservado pra "Impacto potencial"
   (único bloco sempre e exclusivamente interpretação analítica). */
.news-importa-wrap {
    border-left: 2px solid var(--cinza); padding: 0.1rem 0 0.1rem 0.7rem; margin: 0.3rem 0 0.7rem 0;
}
.news-importa-titulo {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; color: var(--cinza);
    text-transform: uppercase; margin-bottom: 0.25rem;
}
.news-importa-corpo {
    font-family: 'Libre Franklin','Segoe UI',Arial,Helvetica,sans-serif;
    font-size: 0.86rem; line-height: 1.6; color: var(--neutro); opacity: 0.92;
}
.news-leitura-wrap {
    border-left: 2px solid var(--destaque); padding: 0.1rem 0 0.1rem 0.7rem; margin: 0.3rem 0 1rem 0;
}
.news-leitura-titulo {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; color: var(--destaque);
    text-transform: uppercase; margin-bottom: 0.25rem;
}
.news-leitura-corpo {
    font-family: 'Libre Franklin','Segoe UI',Arial,Helvetica,sans-serif;
    font-size: 0.86rem; line-height: 1.6; color: var(--neutro); opacity: 0.92;
}
.news-leitura-nota { font-size: 0.68rem; color: var(--cinza); opacity: 0.75; margin-top: 0.3rem; }
.news-secundario {
    border-top: 1px solid var(--borda); margin-top: 0.8rem; padding-top: 0.6rem;
    font-size: 0.74rem; color: var(--cinza); line-height: 1.7; overflow-wrap: anywhere;
}
.news-secundario b { color: var(--neutro); font-weight: 600; }

/* ---- feed NEWS: hierarquia editorial e leitura mobile ----------------
   A grade global do Streamlit empilha colunas no celular. Para os cards
   editoriais, isso separava a miniatura do título e desperdiçava altura;
   aqui preservamos thumb + conteúdo lado a lado, com o texto usando todo
   o espaço restante. */
div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) {
    display: flex !important;
    flex-wrap: nowrap !important;
    align-items: flex-start !important;
    gap: 0.7rem !important;
    overflow: visible !important;
}
div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) > div[data-testid="stColumn"]:first-child {
    flex: 0 0 72px !important;
    width: 72px !important;
    min-width: 72px !important;
}
div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) > div[data-testid="stColumn"]:last-child {
    flex: 1 1 0% !important;
    width: auto !important;
    min-width: 0 !important;
}
.news-item-thumb-wrap {
    width: 72px;
    height: 54px;
}
.news-item-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.45rem;
    font-size: 0.68rem;
    line-height: 1.55;
    overflow-wrap: anywhere;
}
.news-item-meta .selo-tag {
    flex: 0 0 auto;
    margin-right: 0.15rem;
}
.news-item-meta .w-ticker-tag {
    margin: 0;
    padding: 0.02rem 0.28rem;
    font-size: 0.66rem;
}
.news-item-meta .w-abrir-link {
    white-space: nowrap;
    font-weight: 600;
}
.news-item-resumo {
    margin-top: 0.42rem;
    font-size: 0.78rem;
    line-height: 1.55;
    opacity: 0.9;
}
.news-divider {
    border-bottom: 1px solid var(--borda);
    margin: 0.65rem 0 0.8rem;
    opacity: 0.75;
}
/* Headlines mais legíveis, sem transformar cada notícia em um card pesado. */
div[class*="st-key-news-card-titulo-"] button {
    font-size: 0.94rem !important;
    line-height: 1.42 !important;
    overflow-wrap: anywhere !important;
}
div[class*="st-key-news-live-card-"] {
    padding: 0.55rem 0 0.55rem 0.7rem;
    margin: 0.15rem 0;
}
.news-live-badge {
    display: inline-block;
    margin-bottom: 0.2rem;
}
/* Capa em fallback: nao reservar um retangulo gigante sem imagem real. */
.news-capa-fallback { min-height: 0; }
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) {
        gap: 0.6rem !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) > div[data-testid="stColumn"]:first-child {
        flex-basis: 64px !important;
        width: 64px !important;
        min-width: 64px !important;
    }
    .news-item-thumb-wrap {
        width: 64px;
        height: 48px;
    }
    div[class*="st-key-news-card-titulo-"] button {
        font-size: 0.88rem !important;
        line-height: 1.4 !important;
    }
    .news-item-meta {
        gap: 0.18rem 0.38rem;
        font-size: 0.65rem;
        line-height: 1.5;
    }
    .news-item-resumo {
        font-size: 0.75rem;
        line-height: 1.48;
        -webkit-line-clamp: 3;
    }
    .news-divider {
        margin: 0.55rem 0 0.7rem;
    }
    /* Filtros quebram em linhas sem ultrapassar a largura do viewport. */
    [data-testid="stButtonGroup"] {
        max-width: 100%;
        row-gap: 0.35rem !important;
    }
}
@media (max-width: 380px) {
    div[data-testid="stHorizontalBlock"]:has(.news-item-thumb-wrap) > div[data-testid="stColumn"]:first-child {
        flex-basis: 56px !important;
        width: 56px !important;
        min-width: 56px !important;
    }
    .news-item-thumb-wrap {
        width: 56px;
        height: 42px;
    }
    .news-item-meta { font-size: 0.62rem; }
}
/* Modal NOTÍCIA: reduzir altura e espaçamento em celular.
   O fallback de capa não deve ocupar meia tela quando a fonte não oferece foto. */
@media (max-width: 640px) {
    .news-headline {
        font-size: 0.98rem !important;
        line-height: 1.28 !important;
        margin-bottom: 0.2rem !important;
    }
    .news-meta-line {
        font-size: 0.66rem !important;
        line-height: 1.4 !important;
        margin-bottom: 0.4rem !important;
    }
    .news-corpo-p {
        font-size: 0.84rem !important;
        line-height: 1.48 !important;
        margin-bottom: 0.48rem !important;
        max-width: none !important;
    }
    .news-parcial-nota {
        font-size: 0.64rem !important;
        line-height: 1.4 !important;
        margin: 0.15rem 0 0.55rem !important;
    }
    .news-resumo-rotulo { font-size: 0.64rem !important; margin-bottom: 0.3rem !important; }
    .news-importa-wrap {
        padding-left: 0.5rem !important;
        margin: 0.25rem 0 0.5rem !important;
    }
    .news-importa-titulo { margin-bottom: 0.15rem !important; }
    .news-importa-corpo { font-size: 0.8rem !important; line-height: 1.45 !important; }
    .news-leitura-wrap {
        padding-left: 0.5rem !important;
        margin: 0.25rem 0 0.6rem !important;
    }
    .news-leitura-titulo { margin-bottom: 0.15rem !important; }
    .news-leitura-corpo { font-size: 0.8rem !important; line-height: 1.45 !important; }
    .news-secundario {
        margin-top: 0.55rem !important;
        padding-top: 0.4rem !important;
        font-size: 0.68rem !important;
        line-height: 1.5 !important;
    }
    div[data-testid="stDialog"] [data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }
}
@media (max-width: 380px) {
    .news-corpo-p { font-size: 0.81rem !important; line-height: 1.44 !important; }
}
@media (max-width: 480px) {
    .news-headline { font-size: 1rem; }
    .news-corpo-p { font-size: 0.88rem; max-width: none; }
}

/* Redesign editorial do modal NOTÍCIA — visual mais próximo de um terminal
   financeiro, sem alterar a lógica dos dados nem os links existentes.
   CORRIGIDO (auditoria 2026-10-22): toda cor aqui era hex fixo (#28313a,
   #090d11 etc - uma paleta azulada PRÓPRIA, nem o preto/cinza neutro de
   --bg/--borda nem o âmbar real --destaque/#FFA028) - o modal ficava
   com uma identidade visual DIFERENTE do resto do terminal no tema AMBAR
   e simplesmente ignorava os outros 3 temas (FOSFORO/AZUL/CLARO trocam
   essas variáveis em runtime, config.py:TEMAS - um hex fixo nunca
   acompanha). Mesmas variáveis do resto do app agora. A altura/object-fit
   da capa não é mais redefinida aqui - fica só na regra única (.news-capa
   acima), pra nao reabrir a guerra de especificidade que deixava 3
   versões antigas da mesma regra mortas (ver comentário lá). */
div[data-testid="stDialog"] > div {
    border: 1px solid var(--borda) !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, var(--bg) 0%, var(--painel-bg) 100%) !important;
    box-shadow: 0 18px 60px rgba(0,0,0,.48) !important;
}
div[data-testid="stDialog"] [data-testid="stDialogHeader"] {
    padding: 0.8rem 1.15rem 0.55rem !important;
    border-bottom: 1px solid var(--borda) !important;
}
div[data-testid="stDialog"] .news-headline {
    font-size: clamp(1.15rem, 2vw, 1.65rem) !important;
    line-height: 1.22 !important;
    letter-spacing: -0.025em !important;
    font-weight: 750 !important;
    margin: 0.15rem 0 0.55rem !important;
    max-width: 34ch !important;
}
div[data-testid="stDialog"] .news-meta-line {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    gap: 0.2rem 0.65rem !important;
    padding-bottom: 0.65rem !important;
    margin-bottom: 0.7rem !important;
    border-bottom: 1px solid var(--borda) !important;
    font-size: 0.72rem !important;
}
div[data-testid="stDialog"] .news-resumo-rotulo {
    color: var(--cinza) !important;
    font-size: 0.66rem !important;
    letter-spacing: .12em !important;
    margin-bottom: 0.5rem !important;
}
div[data-testid="stDialog"] .news-corpo-p {
    max-width: 78ch !important;
    font-size: 0.96rem !important;
    line-height: 1.72 !important;
    color: var(--neutro) !important;
    margin-bottom: 0.9rem !important;
}
div[data-testid="stDialog"] .news-parcial-nota {
    padding-left: 0.65rem !important;
    border-left: 2px solid var(--destaque) !important;
    font-size: 0.72rem !important;
    line-height: 1.5 !important;
}
div[data-testid="stDialog"] a[href][target="_blank"] {
    transition: color .15s ease, border-color .15s ease !important;
}
div[data-testid="stDialog"] a.w-abrir-link,
div[data-testid="stDialog"] a[href][target="_blank].news-open-link {
    color: var(--destaque) !important;
}
div[data-testid="stDialog"] [data-testid="stLinkButton"] a,
div[data-testid="stDialog"] a:has(span) {
    border-color: var(--destaque) !important;
}
div[data-testid="stDialog"] .news-secundario {
    border-top: 1px solid var(--borda) !important;
    margin-top: 1rem !important;
    padding-top: 0.75rem !important;
    color: var(--cinza) !important;
}
div[data-testid="stDialog"] .news-secundario a {
    color: var(--destaque) !important;
}
@media (max-width: 640px) {
    div[data-testid="stDialog"] > div {
        border-radius: 10px !important;
    }
    div[data-testid="stDialog"] .news-headline {
        font-size: 1.08rem !important;
        max-width: none !important;
    }
    div[data-testid="stDialog"] .news-corpo-p {
        font-size: 0.86rem !important;
        line-height: 1.55 !important;
    }
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
    """Explica o selo/score (ver data/news.py:_calcular_score): e' uma
    heuristica por REGRAS fixas (veiculo confiavel, nº de veiculos,
    linguagem sensacionalista/termo de rumor) - nunca uma probabilidade
    calibrada de o fato estar certo, nem uma nota de confianca da IA (ABA
    5, 2026-10-17: achado real - card em produção mostrou "PROV 100" e o
    numero foi lido como % de acerto, quando na verdade e' so' a soma das
    regras abaixo, capada em 100)."""
    prefixo = "confiabilidade editorial (regras, não é % de acerto): "
    if not n["regras"]:
        return prefixo + "score base, nenhuma regra especial se aplicou"
    return prefixo + "; ".join(n["regras"])


def _truncar(texto: str, limite: int = _TRUNCA_MANCHETE) -> str:
    """Corta em `limite` caracteres, mas nunca no meio de uma palavra
    (PR #79): "...aprovacao unanime..." virava "...aprovacao u…". Recua
    até o último espaço dentro do limite; corte duro só quando não há
    espaço (token único, ex: URL longa)."""
    if len(texto) <= limite:
        return texto
    cortado = texto[: limite - 1]
    ultimo_espaco = cortado.rfind(" ")
    if ultimo_espaco > 0:
        cortado = cortado[:ultimo_espaco]
    return cortado.rstrip() + "…"


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


# bug real encontrado nesta auditoria (2026-10-17): o UA usado aqui
# ("...PregaoNews/1.0)") se auto-identifica como bot pra qualquer CDN de
# imagem que faça fingerprint de User-Agent (comum em WAF de veiculo BR,
# ex: glbimg/imguol) - a mesma classe de bloqueio que já forçou o
# download do ARTIGO (ver data/news.py:_extrair_texto_artigo) a usar um
# UA de navegador real em vez do UA educado padrão do projeto. Troca
# pro mesmo UA de navegador real (replicado também em
# data/news.py:_HEADERS_IMAGEM, usado pela validação em lote) em vez de
# inventar um terceiro UA diferente pra cada chamada relacionada a
# imagem.
_HEADERS_IMAGEM_CAPA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


@st.cache_data(ttl=3600, max_entries=80, show_spinner=False)
def _baixar_imagem_capa(url: str) -> bytes | None:
    """Baixa a imagem no servidor do Pregão, evitando hotlink/CORS e URLs
    que o Safari/iOS ou o navegador não conseguem carregar diretamente.
    Limita tamanho, tempo e tipo de conteúdo; falha vira fallback, nunca
    derruba a abertura da notícia."""
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None
    try:
        with requests.get(
            url,
            headers=_HEADERS_IMAGEM_CAPA,
            timeout=(3.05, 7),
            stream=True,
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            tipo = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not tipo.startswith("image/"):
                return None
            tamanho = response.headers.get("Content-Length")
            if tamanho and int(tamanho) > 8 * 1024 * 1024:
                return None
            partes = []
            total = 0
            for parte in response.iter_content(chunk_size=64 * 1024):
                if not parte:
                    continue
                total += len(parte)
                if total > 8 * 1024 * 1024:
                    return None
                partes.append(parte)
            dados = b"".join(partes)
            if not dados:
                return None
            # Valida que o payload é realmente uma imagem decodificável.
            from PIL import Image
            with Image.open(BytesIO(dados)) as img:
                img.verify()
            return dados
    except Exception:
        return None


_LARGURA_MAX_CAPA = 960


# Proporção (largura/altura) fora desta faixa não fica bem em cobrir
# (object-fit:cover): abaixo de 1.15 é retrato/quadrada - cobrir cortaria
# as laterais; acima de 2.3 é panorâmica - cobrir cortaria topo/base. Faixa
# calibrada no formato típico de foto editorial (og:image 1200x630 = 1.9,
# 16:9 = 1.78) ficando dentro, ou seja, continua em "cobrir" (visualmente
# melhor pra foto quase do tamanho da caixa - sem letterbox desnecessário).
_RATIO_MIN_COBRIR = 1.15
_RATIO_MAX_COBRIR = 2.3


@st.cache_data(ttl=3600, max_entries=80, show_spinner=False)
def _capa_data_uri(url: str) -> tuple[str, float] | None:
    """Capa já baixada no servidor (_baixar_imagem_capa), reduzida pra no
    máximo _LARGURA_MAX_CAPA px e embutida como data URI - entra DENTRO do
    .news-capa, em vez do st.image solto de antes, que exibia a foto na
    proporção original (retrato de 1200px de altura ocupava a tela inteira
    do modal). Devolve (data_uri, largura/altura) - a proporção REAL da
    foto (o PIL já abriu a imagem aqui mesmo; nenhum custo extra) decide,
    em _renderizar_capa, se a capa usa object-fit:cover (a maioria das
    fotos editoriais, perto de 16:9) ou :contain (retrato/panorâmica, onde
    cover cortaria parte relevante da imagem - causa raiz do "imagem
    cortada" auditada em 2026-10-22). Qualquer falha -> None (quem chama
    cai pra segunda via/fallback)."""
    dados = _baixar_imagem_capa(url)
    if not dados:
        return None
    try:
        import base64
        from PIL import Image
        with Image.open(BytesIO(dados)) as img:
            img = img.convert("RGB")
            proporcao = img.width / img.height if img.height else 1.0
            if img.width > _LARGURA_MAX_CAPA:
                img = img.resize((_LARGURA_MAX_CAPA, max(1, round(img.height * _LARGURA_MAX_CAPA / img.width))))
            saida = BytesIO()
            img.save(saida, format="JPEG", quality=82, optimize=True)
        data_uri = "data:image/jpeg;base64," + base64.b64encode(saida.getvalue()).decode("ascii")
        return data_uri, proporcao
    except Exception:
        return None


def _renderizar_capa(imagem: str | None, veiculo_principal: str) -> None:
    """Renderiza a capa a partir de bytes baixados pelo backend (evita
    hotlink/CORS/Safari). Se o download no servidor falhar, a segunda via
    é o <img> direto com fallback automático (listener global de
    injetar_fallback_imagem) - nunca um st.image(url) solto, que mostrava
    o ícone de imagem quebrada quando o navegador também não conseguia.

    Modo cobrir/conter (ver _capa_html) só pode ser decidido quando a
    proporção real é conhecida - ou seja, quando o download no servidor
    funcionou. Na segunda via (download falhou, navegador busca a URL
    direto) a proporção não existe ainda nesse ponto; fica 'cobrir' por
    padrão, igual ao comportamento anterior - degradação honesta, não um
    retrocesso silencioso."""
    marca = veiculo_principal or "NOTÍCIA"
    if not (imagem and isinstance(imagem, str) and imagem.startswith(("https://", "http://"))):
        st.markdown(_capa_html(None, marca), unsafe_allow_html=True)
        return
    resultado = _capa_data_uri(imagem)
    if resultado:
        data_uri, proporcao = resultado
        modo = "cobrir" if _RATIO_MIN_COBRIR <= proporcao <= _RATIO_MAX_COBRIR else "conter"
        st.markdown(_capa_html(data_uri, marca, modo), unsafe_allow_html=True)
    else:
        st.markdown(_capa_html(imagem, marca, "cobrir"), unsafe_allow_html=True)


def _capa_html(imagem: str | None, veiculo_principal: str, modo: str = "cobrir") -> str:
    """Capa do modal editorial - imagem real da materia (og:image, ja'
    extraida junto do texto - ver data/news.py:_extrair_texto_artigo,
    nunca uma busca de rede extra so' pra foto) OU um fallback visual
    discreto (nome do veiculo, sem foto nenhuma) quando nao ha' imagem
    confiavel - NUNCA um placeholder generico enganoso (ex: foto de banco
    de imagens que pareça ser da matéria). Mesmo padrão de
    irmão-oculto de _thumb_html: a imagem some e o fallback (já no DOM,
    só oculto) aparece, se o link quebrar/expirar no navegador - quem
    faz a troca é o listener global de injetar_fallback_imagem().

    `modo` ("cobrir"/"conter", ver _renderizar_capa): "conter" preserva a
    foto INTEIRA (object-fit:contain, nunca corta o assunto principal de
    um retrato/panorâmica) com um fundo desfocado da MESMA foto atrás -
    nunca uma barra vazia lisa nem uma cor genérica no lugar do que
    sobra da caixa.

    So' usado como SEGUNDA via (_renderizar_capa ja' baixa a imagem no
    servidor antes - ver _baixar_imagem_capa); aqui o navegador busca a
    URL direto, por isso referrerpolicy='no-referrer': bloqueio de
    hotlink por Referer (comum em CDN de veiculo BR) costuma liberar
    requisicao SEM referer e so' bloquear quando o referer aponta pra
    um dominio estranho - sem custo nenhum quando o host nao valida
    referer."""
    marca = html.escape(veiculo_principal or "NOTÍCIA")
    if not imagem:
        return f"<div class='news-capa'><div class='news-capa-fallback'><span>{marca}</span></div></div>"
    classe = "news-capa--conter" if modo == "conter" else "news-capa--cobrir"
    imagem_escapada = html.escape(imagem, quote=True)
    fundo = f"<div class='news-capa-fundo' style=\"background-image:url('{imagem_escapada}')\"></div>" if modo == "conter" else ""
    return (
        f"<div class='news-capa {classe}'>" + fundo
        + f"<img src='{imagem_escapada}' loading='lazy' decoding='async' "
        "referrerpolicy='no-referrer' alt=''>"
        f"<div class='news-capa-fallback' style='display:none;'><span>{marca}</span></div>"
        "</div>"
    )


# bug real encontrado nesta auditoria (2026-10-09, evidencia real via
# Playwright): o atributo onerror="..." inline (abordagem antiga de
# _thumb_html/_capa_html) NUNCA disparava - confirmado lendo o DOM
# renderizado de verdade, o proprio Streamlit remove atributos de evento
# inline (onerror/onclick/etc) do HTML passado em st.markdown(...,
# unsafe_allow_html=True) como protecao contra XSS (sanitizacao da
# propria lib, nao e' bug deste projeto) - toda imagem quebrada ficava
# com o <img> vazio visivel (sem fallback nenhum), o oposto do que o
# pedido do Rodrigo exige ("nunca apresente imagem quebrada"). Scripts
# inline tambem nao bastam sozinhos (um <script> inserido via innerHTML
# nao executa, limitacao conhecida do DOM) - a saida real (mesmo padrao
# ja' usado em ui/workspace.py pro drag/resize) e' st.iframe(html,
# height=1), que roda o script de verdade (com acesso a
# window.parent.document) e sobrevive a reruns via um listener de
# 'error' em fase de CAPTURA (captura e' obrigatorio: o evento 'error'
# de <img> NAO faz bubble) anexado 1x no document pai, cobrindo
# qualquer imagem (thumb do feed OU capa do modal) que falhar, mesmo
# recriada em reruns futuros.
_SCRIPT_FALLBACK_IMAGEM = """
<script>
(function() {
    const doc = window.parent.document;
    if (doc.__pregaoImgFallbackInstalado) return;
    doc.__pregaoImgFallbackInstalado = true;
    const SELETOR = '.news-item-thumb-wrap img, .news-capa img, .w-thumb img';
    function aplicarFallback(img) {
        img.style.display = 'none';
        const fallback = img.nextElementSibling;
        if (fallback) fallback.style.display = 'flex';
    }
    doc.addEventListener('error', function(ev) {
        const img = ev.target;
        if (!img || img.tagName !== 'IMG' || !img.matches(SELETOR)) return;
        aplicarFallback(img);
    }, true);
    // corrida real (validação visual 2026-10-19, celular): a imagem pode
    // falhar ANTES deste iframe instalar o listener - o evento 'error' já
    // passou e o <img> quebrado ficava visível. Varre as imagens que já
    // terminaram de carregar sem pixel nenhum (agora e a cada 1,5s, pra
    // cobrir reruns do Streamlit) - custo desprezível.
    function varrer() {
        doc.querySelectorAll(SELETOR).forEach(function(img) {
            if (img.complete && img.naturalWidth === 0 && img.style.display !== 'none') aplicarFallback(img);
        });
    }
    varrer();
    setInterval(varrer, 1500);
})();
</script>
"""


def injetar_fallback_imagem():
    """Chamado 1x no app.py (toda pagina, nao so' dentro de NEWS) - o
    modal editorial (_capa_html) pode abrir a partir de outras abas
    tambem (RADAR reaproveita abrir_card_noticia, ver ui/radar_tab.py),
    entao o listener precisa estar instalado ANTES de qualquer imagem
    poder falhar, nao so' quando render_news roda."""
    st.iframe(_SCRIPT_FALLBACK_IMAGEM, height=1)


def _meta_line_dialog(n: dict) -> str:
    """1 linha compacta de metadados essenciais (selo+score no tooltip,
    hora, veiculo principal, nº de fontes) - substitui o antigo bloco com
    selo em linha própria + lista de "regras" soltas (lia como log de
    depuração, ver PROGRESSO.md FASE C)."""
    classe_selo = _CLASSE_SELO.get(n["selo"], "selo-naoconfirmada")
    tooltip = html.escape(_tooltip_regras(n))
    veiculo_principal = (n.get("veiculos") or [""])[0]
    partes = [f"<span class='selo-tag {classe_selo}' title='{tooltip}'>{_texto_tag(n)}</span>"]
    if veiculo_principal:
        partes.append(html.escape(veiculo_principal))
    partes.append(_fmt_hora(n["data"]))
    tooltip_fontes = html.escape(
        "veículos distintos que publicaram manchete semelhante sobre o mesmo fato — "
        "não garante apuração independente (pode incluir reprodução da mesma agência/wire)"
    )
    partes.append(f"<span title='{tooltip_fontes}' style='cursor:help;'>{n['fontes_count']} fonte(s)</span>")
    confirmacao = n.get("cvm_confirmacao")
    if confirmacao:
        data_doc = confirmacao["data"][:10]
        partes.append(
            f"<a href='{confirmacao['link']}' target='_blank'>↗ documento oficial CVM "
            f"({html.escape(confirmacao['tipo_label'])}, {data_doc})</a>"
        )
    return f"<div class='news-meta-line'>{' · '.join(partes)}</div>"


@st.dialog("NOTÍCIA", width="large")
def _abrir_card(n: dict, watchlist: list):
    """Card editorial completo do grupo - capa, manchete, metadados
    essenciais e o resumo (editorial, gerado aqui na hora do clique,
    nunca antes - cache de obter_resumo_grupo), em até 3 blocos
    rotulados, cada um só quando houver base real (nunca força seção sem
    evidência - ver data/news.py:_PROMPT_SISTEMA_RESUMO):
    1. RESUMO (GERADO POR IA) - síntese factual do que a fonte reportou.
    2. Por que importa - relevância econômica/financeira do fato,
       quando a fonte sustentar isso (ver extrair_por_que_importa).
    3. Impacto potencial - leitura analítica de que ativos/setores podem
       ser afetados e por quê, SEMPRE marcada como interpretação (não
       fato confirmado) - ver separar_secoes_resumo (bloco LEITURA DE
       MERCADO internamente, renomeado só na exibição).
    Veículos/tickers/contexto de research ficam em área secundária
    discreta no rodapé, sem listas/divisores internos competindo com o
    conteúdo (card reescrito na FASE C, 2026-10-09; blocos 2/3 e rótulo
    de IA adicionados no redesign editorial de 2026-10-19 - ver
    PROGRESSO.md)."""
    with st.spinner("Gerando resumo..."):
        fontes_ordenadas = ordenar_fontes_para_resumo(n["fontes"])
        titulos_grupo = tuple(n.get("titulos") or [n["titulo"]])
        resultado = obter_resumo_grupo(n["titulo"], fontes_ordenadas, titulos_grupo)

    veiculo_principal = (n.get("veiculos") or [""])[0]
    # foto da página que gerou o resumo ou, sem ela, a já validada pelo
    # coletor (registro próprio de imagem - existe mesmo sem resumo), com
    # os mesmos filtros de leitura do feed (genérica, URL reprovada)
    _renderizar_capa(imagem_pronta_do_grupo(n, resultado), veiculo_principal)
    st.markdown(f"<div class='news-headline'>{html.escape(n['titulo'])}</div>", unsafe_allow_html=True)
    st.markdown(_meta_line_dialog(n), unsafe_allow_html=True)

    if resultado["resumo"]:
        paragrafos, leitura_mercado = separar_secoes_resumo(resultado["resumo"])
        por_que_importa = extrair_por_que_importa(resultado["resumo"])

        # rotulo explicita "gerado por IA" (mesmo principio/convencao ja
        # aplicada no modal da CVM e no bloco de resumo do RESEARCH -
        # auditoria 360): sem isso, o texto sintetizado podia passar a
        # impressao de ser um trecho/citacao oficial da materia, nao uma
        # sintese de modelo de linguagem.
        st.markdown(
            "<div class='news-resumo-rotulo'>Resumo <span>(gerado por IA)</span></div>",
            unsafe_allow_html=True,
        )
        for p in paragrafos:
            st.markdown(f"<div class='news-corpo-p'>{html.escape(p)}</div>", unsafe_allow_html=True)
        qualidade_texto = resultado.get("qualidade_texto")
        if qualidade_texto == "full_text":
            # texto integral de verdade - nenhum aviso de "parcial" (bug real
            # corrigido 2026-10-19: a versao anterior mostrava uma nota aqui
            # tambem, na mesma div .news-parcial-nota das notas de ressalva,
            # dando a falsa impressao de que o full_text tambem era parcial).
            aviso_evidencia = None
        elif qualidade_texto == "partial_text":
            aviso_evidencia = (
                "Leitura parcial: resumo baseado em fragmentos de texto extraídos "
                "e manchetes; não representa necessariamente a matéria completa."
            )
        elif qualidade_texto == "snippet_only":
            aviso_evidencia = (
                "Atenção: não foi possível extrair o corpo da matéria. "
                "Esta síntese usa apenas manchetes; pode omitir fatos importantes."
            )
        elif qualidade_texto == "extraction_failed":
            aviso_evidencia = (
                "Não foi possível acessar texto suficiente da matéria. "
                "Abra a fonte original; não há base confiável para resumir o conteúdo."
            )
        elif resultado.get("parcial"):
            # Compatibilidade com entradas antigas do cache sem qualidade_texto.
            aviso_evidencia = (
                "Leitura parcial: síntese baseada em trechos/manchetes de várias fontes; "
                "o texto completo da matéria não foi acessado."
            )
        else:
            aviso_evidencia = None

        if aviso_evidencia:
            st.markdown(
                f"<div class='news-parcial-nota'>{html.escape(aviso_evidencia)}</div>",
                unsafe_allow_html=True,
            )
        if por_que_importa:
            st.markdown(
                "<div class='news-importa-wrap'>"
                "<div class='news-importa-titulo'>Por que importa</div>"
                f"<div class='news-importa-corpo'>{html.escape(por_que_importa)}</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        if leitura_mercado:
            st.markdown(
                "<div class='news-leitura-wrap'>"
                "<div class='news-leitura-titulo'>Impacto potencial</div>"
                f"<div class='news-leitura-corpo'>{html.escape(leitura_mercado)}</div>"
                "<div class='news-leitura-nota'>Interpretação analítica a partir do texto acima — não é "
                "um fato confirmado pela fonte; quando o efeito sobre um ativo/setor específico não é "
                "claro, o texto admite essa incerteza em vez de afirmar.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
    else:
        motivo = resultado.get("motivo_indisponivel") or "motivo desconhecido"
        st.caption(f"Resumo indisponível ({motivo}).")

    st.link_button("ABRIR MATÉRIA ↗", n["link"], use_container_width=True)

    secundario = [f"<b>Veículos</b> ({n['fontes_count']}): {_linha_veiculos(n['fontes'])}"]
    if n.get("tickers"):
        tags = "".join(
            f"<span class='w-ticker-tag{' w-ticker-tag-watch' if t in watchlist else ''}'>{t}</span>"
            for t in n["tickers"]
        )
        secundario.append(f"<b>Tickers citados</b>: {tags}")
    st.markdown(
        f"<div class='news-secundario'>{'<br>'.join(secundario)}</div>",
        unsafe_allow_html=True,
    )

    _bloco_contexto_research(_tickers_do_item(n), watchlist)
    _vinculos_noticia(n)


def _ir_para_empresa(ticker: str):
    navegacao.ir_para("analises", "empresas", ticker)


def _ir_para_setor(setor: str):
    # import tardio: ui.setores_tab importa ui.top_mercado_tab, que importa
    # este modulo
    from ui.setores_tab import ir_para_setor

    ir_para_setor(setor)


def _vinculos_noticia(n: dict):
    """Noticia -> empresa / setor (PREGAO 2.0, ui/navegacao.py). So' usa
    o que o coletor ja' identificou no grupo (n["tickers"]: ticker citado
    explicitamente; n["setores"]: data/news_setores.classificar_setores na
    coleta) - nenhuma associacao nova por semelhanca de nome. Mesma
    noticia, mesmo registro: o vinculo leva pra outra AREA, nao copia."""
    tickers = list(n.get("tickers") or [])[:4]
    setores = list(n.get("setores") or [])[:2]
    if not tickers and not setores:
        return
    alvos = [(f"{t} ↗", _ir_para_empresa, t, "Abrir a empresa em ANÁLISES › Empresas") for t in tickers]
    alvos += [(f"Setor: {s} ↗", _ir_para_setor, s, "Abrir em SETORES › Visão por Setor") for s in setores]
    chave_base = abs(hash(n["link"]))
    cols = st.columns(len(alvos))
    for i, (rotulo, fn, arg, ajuda) in enumerate(alvos):
        with cols[i]:
            st.button(rotulo, key=f"news_vinculo_{chave_base}_{i}", on_click=fn, args=(arg,), help=ajuda,
                      width="stretch")


def abrir_card_noticia(n: dict, watchlist: list):
    """Wrapper público de _abrir_card - pensado pra RADAR (ui/radar_tab.py)
    reaproveitar o MESMO dialog editorial da aba NEWS em vez de duplicar
    a lógica (zero implementação paralela, pedido explícito)."""
    _abrir_card(n, watchlist)


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


@st.cache_data(ttl=120, show_spinner=False, max_entries=64)
def _prontos_para_lista(grupos: list) -> dict:
    """obter_resumos_prontos com cache curto pras listas wire (TOP MERCADO,
    VISÃO GERAL, EQUITY): a VISÃO GERAL reroda a cada interação da página,
    e sem isto cada rerun era mais uma ida ao Supabase só pras miniaturas.
    2 min é bem menor que o ciclo do coletor (30 min) que grava as fotos.
    Falha -> {} (lista sem miniatura, nunca quebra)."""
    try:
        return obter_resumos_prontos(grupos)
    except Exception:
        return {}


def _thumb_wire_html(imagem: str | None) -> str:
    """Miniatura compacta da lista wire (TOP MERCADO / VISÃO GERAL): 40x40,
    recorte uniforme; sem foto confiável, um quadrado neutro vazio (mantém
    o alinhamento da coluna sem chamar atenção). Mesmo fallback automático
    da thumb do feed se a URL falhar no navegador."""
    if not imagem:
        return "<div class='w-thumb'><div class='w-thumb-fallback'></div></div>"
    return (
        "<div class='w-thumb'>"
        f"<img src='{html.escape(imagem)}' loading='lazy' decoding='async' referrerpolicy='no-referrer' alt=''>"
        "<div class='w-thumb-fallback' style='display:none;'></div>"
        "</div>"
    )


def _linha_noticia(n: dict, idx: int, mostrar_ticker: bool, prefixo: str, watchlist: list,
                   resumos_prontos: dict | None = None):
    eh_ranking = "importancia" in n
    cols_pesos = _COLS_RANK if eh_ranking else _COLS_PADRAO
    com_thumb = resumos_prontos is not None
    if com_thumb:
        cols_pesos = [_PESO_COL_THUMB] + cols_pesos
    colunas = st.columns(cols_pesos, gap="xsmall", vertical_alignment="center")
    i = 0

    if com_thumb:
        with colunas[i]:
            st.markdown(_thumb_wire_html((resumos_prontos.get(n["link"]) or {}).get("imagem")), unsafe_allow_html=True)
        i += 1

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
def _renderizar_lista(itens: list, mostrar_ticker: bool, prefixo: str, watchlist: list,
                      resumos_prontos: dict | None = None):
    """Reusado pela aba TOP MERCADO - lista + card, sem nenhum resumo
    automatico (so sob demanda, dentro do card). @st.fragment: clicar
    numa manchete (pra abrir o card) so' reroda ISSO aqui, nao a pagina
    inteira - antes, cada clique refazia render_news/render_top_mercado
    do zero (embora os DADOS ja viessem de cache, reconstruir todos os
    widgets da lista inteira a cada clique era a lentidao real)."""
    for idx, n in enumerate(itens):
        _linha_noticia(n, idx, mostrar_ticker, prefixo, watchlist, resumos_prontos)


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

_TRUNCA_TEASER = 320
_MIN_FRASES_TEASER = 2
_MAX_FRASES_TEASER = 4
# separador de fim de frase: pontuacao de frase seguida de espaco - nunca
# quebra em abreviacao/numero decimal (ex: "R$ 2,3" ou "12h30") porque
# esses nao terminam em ./!/? seguido de espaco
_RE_FIM_FRASE = re.compile(r"(?<=[.!?])\s+")


def _resumo_teaser(resumo: str, limite: int = _TRUNCA_TEASER) -> str:
    """Teaser de 2 a 4 frases úteis pro card do feed (pedido: resumo
    visível no próprio card, nunca um corte bruto no meio de uma frase),
    extraido do primeiro parágrafo do resumo EDITORIAL completo de NEWS
    (blocos RESUMO/LEITURA DE MERCADO, ver data/news.py:
    separar_secoes_resumo) - nunca o bloco inteiro (verboso demais pra
    uma linha de lista; o resumo completo continua disponível no dialog)
    e nunca o 2º parágrafo nem a LEITURA DE MERCADO (interpretação, não o
    fato em si - não cabe como teaser). Acumula frase a frase até
    _MAX_FRASES_TEASER ou até estourar `limite` (garantindo ao menos
    _MIN_FRASES_TEASER quando o texto tiver tantas) - só corta no meio de
    uma frase (via _truncar) se nem a 1ª frase sozinha couber."""
    paragrafos, _ = separar_secoes_resumo(resumo)
    texto = paragrafos[0] if paragrafos else resumo.strip()
    frases = [f.strip() for f in _RE_FIM_FRASE.split(texto) if f.strip()]
    if len(frases) <= 1:
        return _truncar(texto, limite)

    teaser = ""
    for i, frase in enumerate(frases[:_MAX_FRASES_TEASER]):
        candidato = f"{teaser} {frase}".strip() if teaser else frase
        if i >= _MIN_FRASES_TEASER and len(candidato) > limite:
            break
        teaser = candidato
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
    se a imagem faltar OU falhar ao carregar no navegador - quem troca
    pro fallback e' o listener global injetado por
    injetar_fallback_imagem() (ver mais abaixo), nunca deixa um icone de
    imagem quebrada no feed.

    Diferente da capa do modal (_renderizar_capa), o thumb do feed NUNCA
    baixa a imagem no servidor (proibido por design - zero requisicao de
    rede por card, ver docstring de data/news.py:obter_resumos_prontos,
    20-50 cards por pagina tornariam isso lento/serial); o navegador
    busca a URL direto, por isso referrerpolicy='no-referrer' (achado
    real desta auditoria 2026-10-17: alguns CDNs de veiculo BR bloqueiam
    por Referer estranho mas liberam sem referer nenhum - sem custo
    quando o host nao faz esse tipo de checagem)."""
    marca = html.escape((iniciais or "?")[:2].upper())
    if not imagem:
        return f"<div class='news-item-thumb-wrap'><div class='news-item-thumb-fallback'>{marca}</div></div>"
    return (
        "<div class='news-item-thumb-wrap'>"
        f"<img src='{html.escape(imagem)}' loading='lazy' referrerpolicy='no-referrer' alt=''>"
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


_TOOLTIP_QUALIDADE_IA = {
    "full_text": "Gerado por IA a partir do texto completo da matéria",
    "partial_text": "Gerado por IA — leitura parcial (fragmentos de texto)",
    "snippet_only": "Gerado por IA — só manchetes, sem o corpo da matéria",
    "extraction_failed": "Gerado por IA — sem texto suficiente da fonte",
}


def _rotulo_ia_chip_html(resultado: dict) -> str:
    """Selo discreto 'IA' no teaser do card do feed (pedido explícito:
    indicador de qualidade do resumo visível no CARD, não só dentro do
    modal ao clicar) - tooltip reaproveita a mesma distinção de
    qualidade_texto já usada no aviso do modal (_abrir_card), só que
    condensada num title em vez de um parágrafo. Opacidade reduzida
    (news-ia-chip-fraco) quando a evidência por trás é fraca (sem corpo
    de matéria nenhum) - "discreto mas claro" não pode virar "escondido"
    justo no caso em que mais importa avisar."""
    qualidade = resultado.get("qualidade_texto")
    fraco = qualidade in ("snippet_only", "extraction_failed")
    tooltip = _TOOLTIP_QUALIDADE_IA.get(qualidade, "Gerado por IA")
    classe = "news-ia-chip news-ia-chip-fraco" if fraco else "news-ia-chip"
    return f"<span class='{classe}' title='{html.escape(tooltip)}'>IA</span>"


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
            chip = _rotulo_ia_chip_html(resultado)
            teaser = html.escape(_resumo_teaser(resultado["resumo"]))
            st.markdown(f"<div class='news-item-resumo'>{chip}{teaser}</div>", unsafe_allow_html=True)
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

        noticias_mostradas = [it["dado"] for it in mostrar if it["tipo_feed"] == "NOTICIA"]
        resumos_prontos = obter_resumos_prontos(noticias_mostradas)

        # O feed antes so mostrava foto/resumo se outro uso ja tivesse
        # preenchido o cache (normalmente o usuario precisava clicar no
        # titulo primeiro). Preaquece poucos cards por rerun: aproveita o
        # mesmo extrator texto+og:image e o cache global existente, sem
        # disparar dezenas de chamadas de IA ao abrir a aba.
        limite_preparo = 3
        preparados = 0
        for noticia in noticias_mostradas:
            # só pula quem já tem RESUMO - card com foto mas sem resumo
            # (registro de imagem do coletor) ainda vale o preparo
            if (resumos_prontos.get(noticia["link"]) or {}).get("resumo"):
                continue
            if preparados >= limite_preparo:
                break
            try:
                fontes = ordenar_fontes_para_resumo(noticia["fontes"])
                titulos = tuple(noticia.get("titulos") or (noticia["titulo"],))
                resultado = obter_resumo_grupo(noticia["titulo"], fontes, titulos)
                if resultado and (resultado.get("resumo") or resultado.get("imagem")):
                    anterior = resumos_prontos.get(noticia["link"]) or {}
                    resumos_prontos[noticia["link"]] = {
                        **resultado, "imagem": resultado.get("imagem") or anterior.get("imagem"),
                    }
            except Exception:
                # Falha isolada de uma materia nao pode derrubar o feed.
                pass
            preparados += 1

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

    prontos = _prontos_para_lista(noticias[:8])
    _renderizar_lista(noticias[:8], mostrar_ticker=False, prefixo=f"eq-{ticker}", watchlist=prefs.get("watchlist") or [],
                      resumos_prontos=prontos)
