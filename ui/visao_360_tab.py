# -*- coding: utf-8 -*-
"""ANÁLISES > Visão 360 - a tela de análise de UM ativo no PREGÃO.

HISTÓRICO
---------
Nasceu na missão visao-360-empresa-20261124 (pedido do Rodrigo) como
camada de COMPOSIÇÃO mínima sobre 4 peças já existentes (perfil da
empresa, múltiplos + DCF, veredito do Comitê, cotação), resolvendo o item
de BACKLOG.md "EQUITY não é 'Company 360'": até então a jornada "como a
empresa ganha dinheiro, quanto custa agora, quanto deveria custar e o que
o Comitê acha disso" estava espalhada em ANÁLISES > Empresas/Fundamentos/
Perfil da Empresa, VALUATION > Parecer do Comitê/Simulador DCF e COMITÊ,
cada uma com seu próprio seletor de ticker desconectado das outras.

REDESIGN COMPLETO (missão visao-360-redesign-20261126, pedido do Rodrigo:
"a interface está visualmente desorganizada, com excesso de informações
mal hierarquizadas... parece mais um relatório bruto de dados do que um
terminal profissional de investimentos"). O que mudou:

1. A tela deixou de ter 4 blocos empilhados em largura total e passou a
   ter uma HIERARQUIA explícita em 3 andares:
   - DECISÃO (sempre visível, topo): cabeçalho do ativo com o preço
     dominante + veredito do Comitê (recomendação, confiança, preço-alvo,
     potencial, score, cobertura).
   - ANÁLISE (sempre visível): visão executiva do negócio/momento/riscos/
     posicionamento, indicadores fundamentalistas por categoria e
     valuation (resumo + modelos + cenários).
   - APROFUNDAMENTO (uma seção por vez, via seletor): pareceres dos
     especialistas, research das casas, evidências/divergências, notícias
     e histórico de análises. Seletor em vez de st.tabs de propósito:
     st.tabs EXECUTA todas as abas em todo rerun (e aqui cada seção tem
     custo real de rede/Supabase), além de empilhar ~5 telas de conteúdo
     numa rolagem só - o oposto de "informação encontrável rapidamente".
2. Recomendação e CONFIANÇA ficaram visualmente separadas (pedido
   explícito): "COMPRA / CONFIANÇA BAIXA" mostra o sinal positivo mas com
   um aviso dedicado de evidência insuficiente - nunca a mesma sensação
   de segurança de uma recomendação com evidência robusta.
3. Blocos reaproveitados em vez de duplicados (ver "REUSO" abaixo).

ESTE MÓDULO NÃO CALCULA NADA NOVO
---------------------------------
Nenhum número desta tela é calculado aqui: cada valor vem pronto da camada
de dados ou do consolidado já persistido pelo Comitê. Em particular:
- Recomendação, confiança, score, preços-alvo e potencial do Comitê vêm
  inteiros de `consolidado["sinal_comite"]`/`["confianca"]`
  (data/coordenador_central/consolidacao.py) - esta tela NUNCA recalcula,
  reordena nem "melhora" esses campos (regra da missão: problema de lógica
  no Comitê se documenta, não se corrige junto de um redesign visual).
- Múltiplos/indicadores vêm de data/radar.py:linha_valuation; ROIC e
  receita YoY vêm do parecer do Market Researcher quando existir (nunca
  estimados quando não existir).
- Cenários de DCF vêm de `model_builder["cenarios"]` (motor único em
  data/coordenador_central/dcf.py); o DCF interativo é o MESMO
  ui/analises_tab.py:controle_dcf_inline de sempre.
- "Cobertura" do veredito é CONTAGEM de pareceres que produziram
  recomendação (ver `_cobertura_comite`) - leitura do que já existe, nunca
  um critério novo de qualidade.

REUSO (nada aqui é uma segunda implementação)
---------------------------------------------
- Perfil da empresa, parecer de especialista, casas de research,
  divergência entre especialistas, síntese final e síntese de IA: API
  pública de ui/coordenador_tab.py (render_perfil_*,
  render_parecer_especialista, render_casas_research,
  render_divergencia_comite, render_sintese_final, render_sintese_ia,
  obter_perfil_para_tela, badges) - ver o bloco "API PÚBLICA DE
  COMPOSIÇÃO" lá, criado nesta missão exatamente pra esta tela não
  duplicar aqueles blocos.
- DCF interativo e comparativo de casas: ui/analises_tab.py
  (controle_dcf_inline, comparativo_casas_cacheado, potencial_pct).
- Notícias do ticker: ui/news_tab.py:render_news_ticker (a mesma lista
  densa de manchete/hora/selo/fonte/link usada em TOP MERCADO).
- Visual: ui/design_system.py (faixa_metricas_html, tabela_html,
  badge_html, rotulo_html, secao, vazio, moeda_html, pct_html,
  variacao_html) - zero hex solto, zero card de SaaS, zero
  `"verde" if x > 0` reinventado.

PRINCÍPIO QUE A SUÍTE PROVA (tests/test_visao_360_tab.py)
---------------------------------------------------------
Dado ausente em QUALQUER seção degrada com motivo explícito - nunca
inventa número, nunca fica em silêncio vazio. Em especial, "nunca
analisado pelo Comitê" (listar_analises_por_ticker devolve []) e "não foi
possível checar se já foi analisado" (Supabase indisponível, devolve None)
são avisos DISTINTOS - confundir os dois diria a um usuário que um ticker
nunca visto pelo Comitê foi conferido e está limpo, quando na verdade a
conferência nem rodou. Mensagem de erro técnico (exceção, SQL, nome de
coluna) nunca vai pra tela do usuário nesta reformulação - só o fato de a
fonte não ter respondido."""

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from data.coordenador_central.persistencia import listar_analises_por_ticker, obter_analise
from data.market_makers import contexto_ticker
from data.prices import obter_cotacao, obter_indicadores
from data.radar import linha_valuation
from ui import coordenador_tab as comite_ui
from ui import design_system as ds
from ui import navegacao
from ui.analises_tab import comparativo_casas_cacheado, controle_dcf_inline, potencial_pct
from ui.news_tab import render_news_ticker

TZ_SP = ZoneInfo("America/Sao_Paulo")

# CSS próprio da tela (mesmo padrão de ui/coordenador_tab.py:_injetar_css e
# ui/news_tab.py: classe com prefixo do módulo, injetada uma vez por render).
# Só o que é ESPECÍFICO desta página mora aqui - tudo que se repete em mais
# de uma aba foi pro design system (ui/design_system.py + style.css).
#
# Responsividade (prioridade desktop, mas sem quebrar notebook/tablet): toda
# grade usa `auto-fit`/`flex-wrap`, nunca largura fixa, e o único breakpoint
# é >=1024px - o MESMO "tablet largo" já estabelecido em style.css (ver
# commit "sidebar touch empurra conteudo em tablets largos"), nunca um
# número novo.
_CSS_V360 = """
/* Compensação do -1rem do Streamlit nos blocos de HTML cru desta tela -
   mesma regra (e mesmo motivo medido com Playwright) documentada em
   style.css, seção "COMPENSAÇÃO DO -1rem DO STREAMLIT". Sem isto, o
   elemento seguinte a um destes blocos sobe 16px e fica por cima da
   última linha dele (visto: a faixa de ações rápidas cobrindo a linha de
   status da cotação). */
[data-testid="stMarkdownContainer"] > .v360-cabecalho:last-child,
[data-testid="stMarkdownContainer"] > .v360-veredito:last-child,
[data-testid="stMarkdownContainer"] > .v360-cenarios:last-child,
[data-testid="stMarkdownContainer"] > .v360-texto:last-child,
[data-testid="stMarkdownContainer"] > .v360-nota:last-child { margin-bottom: 1rem; }

/* --- cabeçalho do ativo --- */
.v360-cab { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.3rem 0.7rem; margin-bottom: 0.35rem; }
.v360-ticker { font-size: 1.5rem; font-weight: 700; color: var(--destaque); letter-spacing: 0.02em; line-height: 1.1; }
.v360-nome { font-size: 0.86rem; color: var(--neutro); min-width: 0; overflow-wrap: anywhere; }
.v360-cab-selos { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-left: auto; }
.v360-preco { font-size: 2rem; font-weight: 700; line-height: 1.05; color: var(--neutro); font-variant-numeric: tabular-nums; }
.v360-preco-var { font-size: 1rem; font-weight: 700; line-height: 1.3; }
.v360-cotacao {
    display: grid; grid-template-columns: minmax(140px, max-content) minmax(120px, max-content) 1fr;
    gap: 0.2rem 1.6rem; align-items: end; margin: 0.15rem 0 0.1rem 0;
}
.v360-cotacao-extra { min-width: 0; }
.v360-status { font-size: 0.64rem; color: var(--cinza); margin-top: 0.3rem; line-height: 1.5; }
@media (max-width: 1023px) {
    .v360-cotacao { grid-template-columns: 1fr; gap: 0.3rem; }
    .v360-cotacao-extra { grid-column: 1; }
    .v360-preco { font-size: 1.6rem; }
    .v360-ticker { font-size: 1.25rem; }
}

/* --- veredito do Comitê: recomendação e confiança nunca no mesmo peso --- */
.v360-veredito { display: grid; grid-template-columns: minmax(260px, 1.1fr) minmax(0, 2fr); gap: 0.4rem 1.5rem; align-items: start; }
.v360-rec { font-size: 1.5rem; font-weight: 700; line-height: 1.1; letter-spacing: 0.02em; }
.v360-conf { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.3rem; }
.v360-conf-barra { display: inline-flex; gap: 2px; }
.v360-conf-passo { width: 14px; height: 5px; background: var(--borda); }
.v360-conf-passo-on { background: currentColor; }
.v360-aviso-confianca {
    font-size: 0.68rem; color: var(--destaque); border-left: 2px solid var(--destaque);
    padding: 0.15rem 0 0.15rem 0.5rem; margin-top: 0.35rem; line-height: 1.45;
}
@media (max-width: 1023px) { .v360-veredito { grid-template-columns: 1fr; } }

/* --- texto analítico: nunca ocupa a largura toda de um terminal largo
   (linha longa demais destrói a legibilidade) --- */
.v360-texto { font-size: 0.78rem; line-height: 1.55; max-width: 78ch; }
.v360-nota { font-size: 0.66rem; color: var(--cinza); line-height: 1.5; margin-top: 0.2rem; }

/* --- cenários de valuation lado a lado --- */
.v360-cenarios { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.6rem; margin: 0.3rem 0 0.4rem 0; }
.v360-cenario { border-left: 2px solid var(--borda); padding-left: 0.55rem; min-width: 0; }
.v360-cenario-base { border-left-color: var(--destaque); }
.v360-cenario-valor { font-size: 1.05rem; font-weight: 700; font-variant-numeric: tabular-nums; }

/* --- lista de especialistas (coluna esquerda do aprofundamento) --- */
.st-key-v360_especialista [role="radiogroup"] { gap: 0.1rem; }
.st-key-v360_especialista label p { font-size: 0.72rem !important; }

/* --- seletores (fita de ticker e seções de aprofundamento): mesma
   linguagem da subnavegação do app (texto + sublinhado âmbar, sem caixa
   preenchida), escopada por chave de container pra não afetar os pills de
   filtro de outras abas. Ver .st-key-nav_sub em style.css. --- */
.st-key-v360_aprofundar [data-testid="stButtonGroup"] { gap: 0.1rem !important; border-bottom: 1px solid var(--borda); }
.st-key-v360_aprofundar [data-testid="stButtonGroup"] button {
    background-color: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important; box-shadow: none !important;
    border-radius: 0 !important; color: var(--cinza) !important; font-size: 0.7rem !important;
    letter-spacing: 0.04em; padding: 0.3rem 0.75rem !important; min-height: 32px !important;
    flex: 0 0 auto !important; white-space: nowrap;
}
.st-key-v360_aprofundar [data-testid="stButtonGroup"] button:hover { color: var(--destaque) !important; }
.st-key-v360_aprofundar [data-testid="stButtonGroup"] button[aria-checked="true"],
.st-key-v360_aprofundar [data-testid="stButtonGroup"] button[aria-pressed="true"] {
    background-color: transparent !important; border-bottom: 2px solid var(--destaque) !important;
    color: var(--destaque) !important; font-weight: 600;
}
/* ações rápidas: botões de vínculo discretos, não uma fileira de CTAs.
   Cada coluna encolhe pro tamanho do próprio botão (`flex: 0 0 auto`) e a
   fileira quebra linha quando não couber - com as colunas padrão do
   Streamlit (largura igual) o rótulo era cortado em telas de 1024px
   ("Fundamentos ↗" virava "Fundament…", medido no Playwright) e ficava
   esticado em telas largas. */
.st-key-v360_acoes [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.3rem !important;
}
.st-key-v360_acoes [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
}
.st-key-v360_acoes button {
    background-color: transparent !important; border: 1px solid var(--borda) !important;
    border-radius: 0 !important; color: var(--cinza) !important; font-size: 0.66rem !important;
    padding: 0.15rem 0.4rem !important; min-height: 26px !important;
}
.st-key-v360_acoes button:hover { color: var(--destaque) !important; border-color: var(--destaque) !important; }
"""


def _injetar_css():
    st.markdown(f"<style>{_CSS_V360}</style>", unsafe_allow_html=True)
    # blocos reaproveitados de COMITÊ emitem markup .coord-* - sem o CSS
    # daquele módulo eles renderizariam sem estilo nesta tela (bug real
    # corrigido nesta missão, ver coordenador_tab.injetar_css).
    comite_ui.injetar_css()


# ============================================================
# Carga de dados - cada fonte isolada, cada falha com motivo próprio.
# ============================================================

def _nome_empresa(ticker: str) -> str | None:
    """Nome de exibição da empresa - delega pra ui/coordenador_tab.py
    (cascata config.TICKER_NOME -> obter_nome_yf cacheado 24h). Esta tela
    tinha uma CÓPIA dessa cascata até 2026-11-26; agora é a função pública
    de lá, uma implementação só."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    try:
        return comite_ui.nome_empresa_exibicao(ticker)
    except Exception:
        return None


@st.cache_data(ttl=90, show_spinner=False)
def _contexto_cacheado(ticker: str) -> dict:
    """Catalisadores confirmados/estimados dos próximos 60 dias, mudanças
    de tese/CVM recentes e alertas de qualidade do indicador, pro bloco
    "Momento atual" - data/market_makers.py:contexto_ticker, a MESMA
    função que RADAR já usa por ticker (nenhum coletor novo).

    Cache na camada de UI (data/market_makers.py não importa Streamlit de
    propósito - é usado também fora de sessão, pelo Morning Call), mesmo
    TTL de ui/analises_tab.py:_analise_ticker_cacheada. NÃO usa
    `analise_ticker` (que embrulha este mesmo contexto) de propósito:
    aquela função também dispara comparaveis_setor (N consultas yfinance,
    1 por par do setor) e a série trimestral da CVM - custo que o projeto
    só paga sob demanda, nunca no primeiro render de uma página."""
    return contexto_ticker(ticker)


def _carregar_comite(ticker: str) -> dict:
    """Última análise do Comitê já persistida pra este ticker, como um
    estado explícito - nunca um `None` ambíguo:

    - "ok": `consolidado` disponível (+ metadados da execução).
    - "nunca": a fonte respondeu e não existe análise deste ticker.
    - "indisponivel": a fonte NÃO respondeu - não se sabe se existe.
    - "erro": a execução mais recente terminou em erro.
    - "sem_resultado": existe execução, ainda sem consolidado (em
      andamento).

    Zero execução nova é disparada daqui (só leitura do que o Comitê já
    persistiu), e os 5 estados têm mensagem própria na tela - "nunca" e
    "indisponivel" jamais compartilham texto (ver docstring do módulo)."""
    try:
        analises = listar_analises_por_ticker(ticker, limite=12)
    except Exception:
        analises = None
    if analises is None:
        return {"estado": "indisponivel", "analises": []}
    if not analises:
        return {"estado": "nunca", "analises": []}

    analise_id = (analises[0] or {}).get("id")
    analise = obter_analise(analise_id) if analise_id else None
    if analise is None:
        return {"estado": "indisponivel", "analises": analises}
    if analise.get("status") == "ERRO":
        return {
            "estado": "erro", "analises": analises, "analise": analise,
            "motivo": analise.get("erro") or "motivo não especificado",
        }
    consolidado = analise.get("resultado")
    if not consolidado:
        return {"estado": "sem_resultado", "analises": analises, "analise": analise}
    return {"estado": "ok", "analises": analises, "analise": analise, "consolidado": consolidado}


def _analista(consolidado: dict, analista_id: str) -> dict | None:
    """1 parecer específico dentro do consolidado (ex.: "model_builder",
    "market_researcher") - só leitura, nunca altera o dict."""
    analistas = ((consolidado or {}).get("pareceres_analistas") or {}).get("analistas") or []
    return next((a for a in analistas if a.get("id") == analista_id), None)


def _reais(valor, fmt: str, fallback: str = "—", moeda: str = "R$", casas: int = 2) -> str:
    """Valor monetário no formato de número que o USUÁRIO escolheu
    (prefs["formato_numerico"], BR ou US) - atalho local pra
    `design_system.moeda_html(..., formato=fmt)`, que esta tela chama
    dezenas de vezes. Nunca formata número aqui; só repassa."""
    return ds.moeda_html(valor, moeda, casas=casas, fallback=fallback, formato=fmt)


def _escolha_estavel(chave_widget: str, opcoes: list, padrao: str) -> tuple:
    """Mesma proteção que app.py:_escolha_estavel: `st.segmented_control`
    devolve None quando o usuário clica de novo na opção já selecionada -
    sem isto, reclicar a seção aberta jogaria o usuário de volta pra
    primeira. Devolve (ultima_escolha_valida, chave_de_memoria)."""
    chave_memoria = chave_widget + "_valido"
    ultimo = st.session_state.get(chave_memoria, padrao)
    return (ultimo if ultimo in opcoes else padrao), chave_memoria


# ============================================================
# BLOCO A - Cabeçalho do ativo: identidade + cotação dominante + status.
# ============================================================

_PREFIXO_STATUS_COTACAO = {
    "TEMPO REAL": ds.NIVEL_OK,
    "ATRASADA": ds.NIVEL_ALERTA,
    "CACHE": ds.NIVEL_ALERTA,
}


def _selo_status_cotacao(tipo_cotacao: str | None) -> str:
    """Selo do status da cotação a partir do PRÓPRIO rótulo que
    data/prices.py:obter_cotacao devolve (hoje "ATRASADA (Yahoo Finance;
    atraso pode variar)") - lê a primeira palavra-chave e escolhe o nível
    do selo; rótulo desconhecido cai em neutro em vez de afirmar tempo
    real. Nunca inventa "tempo real" quando a fonte não garante isso."""
    texto = str(tipo_cotacao or "").strip()
    if not texto:
        return ds.badge_html("ORIGEM NÃO INFORMADA", ds.NIVEL_NEUTRO)
    rotulo = texto.split("(")[0].strip().rstrip(";").upper() or texto.upper()
    nivel = next((n for p, n in _PREFIXO_STATUS_COTACAO.items() if rotulo.startswith(p)), ds.NIVEL_NEUTRO)
    return ds.badge_html(rotulo, nivel)


def _hora_consulta(cotacao_em: str | None) -> str | None:
    """Hora da consulta (horário de Brasília) a partir do ISO que
    obter_cotacao grava - `cotacao_em` é a hora da CONSULTA, não a do
    último negócio (fast_info não expõe isso), e o rótulo na tela diz
    exatamente isso."""
    if not cotacao_em:
        return None
    try:
        quando = datetime.fromisoformat(str(cotacao_em).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    try:
        return quando.astimezone(TZ_SP).strftime("%d/%m %H:%M")
    except (ValueError, OverflowError):
        return None


def _render_cabecalho(ticker: str, linha: dict | None, prefs: dict):
    """Identidade do ativo + cotação, com o PREÇO visualmente dominante
    (pedido explícito: ticker, nome e preço não podem ficar perdidos em
    elementos pequenos). Hierarquia: 1) ticker/nome, 2) preço, 3)
    variação, 4) status da cotação, 5) complementares (máx/mín, volume,
    52 semanas, setor/mercado).

    Emitido como UM bloco de HTML (sem widget do Streamlit no meio) de
    propósito: é a única forma de garantir o alinhamento exato entre preço
    e variação na mesma linha de base - st.columns introduz gaps próprios
    e quebra esse alinhamento em telas estreitas."""
    fmt = prefs["formato_numerico"]
    nome = _nome_empresa(ticker)
    try:
        cot = obter_cotacao(ticker)
    except Exception as exc:
        # motivo técnico fica no log, nunca na tela (regra da missão)
        print(f"[visao_360] cotação indisponível pra {ticker}: {exc!r}")
        cot = {"erro": "fonte de cotação não respondeu"}

    selos = []
    info = config.info_ativo(ticker) or {}
    mercado = info.get("mercado") or info.get("pais")
    if mercado:
        selos.append(ds.badge_html(str(mercado), ds.NIVEL_NEUTRO))
    setor = (linha or {}).get("setor") or config.IBOVESPA_SETORES.get(ticker)
    if setor:
        selos.append(ds.badge_html(str(setor), ds.NIVEL_NEUTRO))
    selos.append(_selo_status_cotacao(None if cot.get("erro") else cot.get("tipo_cotacao")))
    if cot.get("erro"):
        selos.append(ds.badge_html("COTAÇÃO INDISPONÍVEL", ds.NIVEL_ERRO))

    identidade = (
        "<div class='v360-cab'>"
        f"<span class='v360-ticker'>{html.escape(ticker)}</span>"
        + (f"<span class='v360-nome'>{html.escape(nome)}</span>" if nome else "")
        + f"<span class='v360-cab-selos'>{''.join(selos)}</span></div>"
    )

    if cot.get("erro"):
        st.markdown(
            "<div class='v360-cabecalho'>" + identidade
            + "<div class='v360-cotacao'><div>" + ds.rotulo_html("PREÇO")
            + "<div class='v360-preco'>—</div></div></div>"
            + "<div class='v360-status'>Preço atual indisponível agora: a fonte de cotação "
              "(Yahoo Finance) não respondeu nesta consulta. As demais seções desta tela "
              "continuam válidas - elas não dependem da cotação do momento.</div></div>",
            unsafe_allow_html=True,
        )
        return

    extras = []
    if cot.get("maxima_dia") is not None or cot.get("minima_dia") is not None:
        extras.append((
            "MÁX/MÍN DIA",
            _reais(cot.get("maxima_dia"), fmt) + " / " + _reais(cot.get("minima_dia"), fmt),
        ))
    if cot.get("volume") is not None:
        extras.append(("VOLUME", ds.numero_financeiro_html(cot["volume"], 0, fmt)))
    if cot.get("maxima_52s") is not None or cot.get("minima_52s") is not None:
        extras.append((
            "52 SEMANAS",
            _reais(cot.get("minima_52s"), fmt) + " / " + _reais(cot.get("maxima_52s"), fmt),
        ))
    if (linha or {}).get("valor_mercado") is not None:
        extras.append(("VALOR DE MERCADO", html.escape(config.formatar_valor_mercado(linha["valor_mercado"], fmt))))

    variacao_abs = cot.get("variacao")
    bloco_variacao = (
        f"<div class='v360-preco-var {ds.classe_sinal(cot['variacao_pct'])}'>"
        + (ds.numero_financeiro_html(variacao_abs, 2, fmt, com_sinal=True) + " "
           if isinstance(variacao_abs, (int, float)) else "")
        + ds.variacao_html(cot["variacao_pct"], fmt) + "</div>"
    )
    hora = _hora_consulta(cot.get("cotacao_em"))
    st.markdown(
        "<div class='v360-cabecalho'>" + identidade
        + "<div class='v360-cotacao'>"
        + "<div>" + ds.rotulo_html("PREÇO")
        + f"<div class='v360-preco'>{_reais(cot.get('preco'), fmt)}</div></div>"
        + "<div>" + ds.rotulo_html("VARIAÇÃO DO DIA") + bloco_variacao + "</div>"
        # minimo=168: "MÁX/MÍN DIA" e "52 SEMANAS" são valores COMPOSTOS
        # ("R$ 38,94 / R$ 37,80") e o número nunca quebra linha - medido a
        # 1024px, com uma coluna menor o segundo valor era cortado com
        # reticências e o usuário perdia a mínima do dia.
        + f"<div class='v360-cotacao-extra'>{ds.faixa_metricas_html(extras, minimo=168)}</div>"
        + "</div>"
        + "<div class='v360-status'>"
        + html.escape(str(cot.get("tipo_cotacao") or "Origem da cotação não informada"))
        + (f" · consultado em {html.escape(hora)} (horário de Brasília)" if hora else "")
        + ". O horário é o da CONSULTA, não o do último negócio.</div></div>",
        unsafe_allow_html=True,
    )


def _render_acoes_rapidas(ticker: str):
    """Ações rápidas = só vínculos pra funcionalidades que JÁ existem
    (nunca um botão decorativo): o detalhe de cada área continua na área
    dela, esta tela é o ponto de partida. Mesmo mecanismo de
    ui/navegacao.py:link usado pelo resto do app."""
    destinos = [
        ("Notícias ↗", "noticias", "empresas"),
        ("Research ↗", "research", "feed"),
        ("Fundamentos ↗", "analises", "fundamentos"),
        ("Valuation ↗", "valuation", "parecer"),
        ("Comitê ↗", "comite", "historico"),
    ]
    with st.container(key="v360_acoes"):
        # 1 coluna por destino; a LARGURA de cada uma é resolvida no CSS
        # (ver _CSS_V360, ".st-key-v360_acoes"): cada coluna encolhe pro
        # tamanho do botão e a fileira quebra linha quando precisa. Com as
        # colunas de largura igual do Streamlit, os botões ficavam gigantes
        # a 1920px e com o rótulo cortado a 1024px.
        colunas = st.columns(len(destinos))
        for coluna, (rotulo, area, sub) in zip(colunas, destinos):
            with coluna:
                # sem width="stretch": o botão fica do tamanho do próprio
                # rótulo (medido a 1024px, esticado ele cortava
                # "Fundamentos ↗" em "Fundament…"), e a coluna extra no fim
                # mantém todos agrupados à esquerda em telas largas.
                navegacao.link(
                    rotulo, area, sub, chave=f"v360_acao_{area}_{sub}_{ticker}", ticker=ticker,
                )


# ============================================================
# BLOCO B - Veredito do Comitê (resumo executivo da decisão).
# ============================================================

_NIVEL_CONFIANCA = {"ALTA": (3, ds.NIVEL_OK), "MEDIA": (2, ds.NIVEL_ALERTA),
                    "BAIXA": (1, ds.NIVEL_ERRO), "INSUFICIENTE": (0, ds.NIVEL_NEUTRO)}

_COR_NIVEL = {ds.NIVEL_OK: "var(--alta)", ds.NIVEL_ALERTA: "var(--destaque)",
              ds.NIVEL_ERRO: "var(--baixa)", ds.NIVEL_NEUTRO: "var(--cinza)"}


def _barra_confianca_html(categoria: str) -> str:
    """Confiança como MEDIDOR (3 passos preenchidos conforme a
    categoria), ao lado do selo textual - é o que separa visualmente
    "confiança" de "recomendação" em vez de duas palavras do mesmo
    tamanho lado a lado (pedido explícito: "COMPRA / CONFIANÇA BAIXA"
    nunca pode passar a mesma sensação de segurança de uma recomendação
    com evidência robusta). Nenhuma categoria nova é inventada: são as 4
    que data/coordenador_central/consolidacao.py:_confianca já devolve."""
    passos, nivel = _NIVEL_CONFIANCA.get(str(categoria or "").upper(), (0, ds.NIVEL_NEUTRO))
    blocos = "".join(
        f"<span class='v360-conf-passo{' v360-conf-passo-on' if i < passos else ''}'></span>"
        for i in range(3)
    )
    return (
        f"<div class='v360-conf' style='color:{_COR_NIVEL[nivel]};'>"
        f"{comite_ui.badge_confianca_html(categoria)}"
        f"<span class='v360-conf-barra'>{blocos}</span></div>"
    )


def _cobertura_comite(consolidado: dict) -> dict:
    """CONTAGEM de cobertura do veredito (campo pedido explicitamente):
    quantos especialistas acionados de fato produziram um parecer com
    recomendação, de quantos no total.

    "Produziu análise" = o parecer existe e a recomendação dele não é
    "INSUFICIENTE" (o rótulo que data/coordenador_central/pareceres.py já
    usa pra "sem base pra opinar"). É LEITURA do que o Comitê gravou -
    esta tela não cria um critério de qualidade novo nem reclassifica
    nenhum parecer; `especialistas_sem_parecer` existe pra o painel de
    evidências dizer QUEM ficou sem base, nunca pra esconder isso."""
    analistas = ((consolidado or {}).get("pareceres_analistas") or {}).get("analistas") or []
    com_parecer, sem_parecer = [], []
    for analista in analistas:
        nome = str(analista.get("nome") or analista.get("id") or "especialista")
        if str(analista.get("recomendacao") or "INSUFICIENTE").upper() == "INSUFICIENTE":
            sem_parecer.append(nome)
        else:
            com_parecer.append(nome)
    return {
        "n_com_parecer": len(com_parecer), "n_total": len(analistas),
        "especialistas_com_parecer": com_parecer, "especialistas_sem_parecer": sem_parecer,
    }


def _render_veredito(ticker: str, comite: dict, prefs: dict):
    """Resumo executivo do Comitê no topo da tela: RECOMENDAÇÃO,
    CONFIANÇA, PREÇO-ALVO, POTENCIAL, SCORE e COBERTURA - organizados em
    2 colunas (o "o quê" à esquerda, os números à direita) em vez de 6
    cards competindo entre si.

    Nenhum valor é recalculado: tudo vem de `consolidado["sinal_comite"]`
    e `["confianca"]`. Os 4 estados sem veredito (nunca analisado, fonte
    indisponível, execução com erro, execução sem consolidado) têm texto
    próprio e sempre oferecem o CTA de executar o Comitê."""
    estado = comite["estado"]
    if estado != "ok":
        if estado == "indisponivel":
            st.warning(
                f"Não foi possível verificar se {html.escape(ticker)} já foi analisado pelo Comitê agora "
                "(Supabase indisponível no momento) — isto é diferente de 'nunca analisado': a conferência "
                "não rodou, não se sabe ainda se existe uma análise ou não."
            )
        elif estado == "nunca":
            st.info(f"O Comitê ainda não analisou {html.escape(ticker)} nesta instalação.")
        elif estado == "erro":
            st.error(
                "A análise mais recente deste ticker terminou em erro: "
                f"{html.escape(str(comite.get('motivo')))}."
            )
        else:
            st.info("A análise mais recente deste ticker ainda não tem resultado consolidado "
                    "(pode estar em andamento).")
        navegacao.link(
            "Executar Comitê para este ticker ↗", "comite", "visao-geral",
            chave=f"v360_executar_comite_{ticker}", ticker=ticker,
        )
        return

    fmt = prefs["formato_numerico"]
    consolidado = comite["consolidado"]
    sinal = consolidado.get("sinal_comite") or {}
    confianca = consolidado.get("confianca") or {}
    recomendacao = str(sinal.get("sinal") or "INSUFICIENTE")
    categoria_confianca = str(confianca.get("categoria") or "INSUFICIENTE").upper()
    cobertura = _cobertura_comite(consolidado)
    moeda = sinal.get("moeda_preco_alvo_modelo") or "R$"
    upside = sinal.get("upside_modelo_pct")

    esquerda = (
        ds.rotulo_html("RECOMENDAÇÃO DO COMITÊ")
        + f"<div class='v360-rec' style='color:{comite_ui.cor_recomendacao(recomendacao)};'>"
        + html.escape(recomendacao) + "</div>"
        + _barra_confianca_html(categoria_confianca)
    )
    # Recomendação acionável + confiança fraca: o aviso é o PONTO desta
    # reformulação (pedido explícito) - um sinal positivo sustentado por
    # evidência insuficiente nunca pode parecer seguro.
    if recomendacao.upper() in ("COMPRA", "VENDA") and categoria_confianca in ("BAIXA", "INSUFICIENTE"):
        esquerda += (
            "<div class='v360-aviso-confianca'>Sinal direcional com evidência "
            f"{'insuficiente' if categoria_confianca == 'INSUFICIENTE' else 'fraca'}: a recomendação "
            f"é {html.escape(recomendacao)}, mas a confiança da consolidação é "
            f"{html.escape(categoria_confianca)} — trate como hipótese a confirmar, não como conclusão.</div>"
        )
    if confianca.get("justificativa"):
        esquerda += f"<div class='v360-nota'>{html.escape(str(confianca['justificativa']))}</div>"

    metricas = [
        ("PREÇO-ALVO · DCF", _reais(sinal.get("preco_alvo_modelo"), fmt, fallback="não calculado", moeda=moeda),
         "Model Builder"),
        ("POTENCIAL", ds.variacao_html(upside, fmt) if isinstance(upside, (int, float)) else "—",
         "sobre a cotação"),
        ("SCORE", html.escape(str(sinal.get("score"))) if sinal.get("score") is not None else "—",
         "sinal quantitativo"),
        ("COBERTURA", f"{cobertura['n_com_parecer']}/{cobertura['n_total']}", "especialistas com parecer"),
        ("ALVO · P/L SETORIAL", _reais(sinal.get("preco_alvo_pl_setorial"), fmt, fallback="não calculado", moeda=moeda),
         "múltiplo relativo"),
        ("ALVO · CONSENSO", _reais(sinal.get("preco_alvo_consenso"), fmt, fallback="não disponível", moeda=moeda),
         "casas de research"),
    ]
    st.markdown(
        "<div class='v360-veredito'>"
        f"<div>{esquerda}</div>"
        f"<div>{ds.faixa_metricas_html(metricas, grande=True, minimo=138)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if consolidado.get("resumo_executivo"):
        st.markdown(
            f"<div class='v360-texto' style='margin-top:0.3rem;'>"
            f"{html.escape(str(consolidado['resumo_executivo']))}</div>",
            unsafe_allow_html=True,
        )
    if sinal.get("justificativa"):
        st.markdown(f"<div class='v360-nota'>{html.escape(str(sinal['justificativa']))}</div>",
                    unsafe_allow_html=True)
    quando = comite_ui.fmt_data((comite.get("analise") or {}).get("iniciado_em"))
    st.markdown(
        f"<div class='v360-nota'>Análise do Comitê de {html.escape(quando)}. O score quantitativo "
        "(ROE, margem, dívida, FCF, crescimento e P/L relativo, sem DCF) é calculado de forma "
        "INDEPENDENTE do parecer de Valuation (que vem do upside do DCF) — os dois podem divergir "
        "para o mesmo ticker, e isso não é erro.</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# BLOCO C - Visão executiva: negócio, momento, riscos, posicionamento.
# ============================================================

def _render_momento_mercado(ticker: str):
    """Catalisadores dos próximos 60 dias e mudanças de tese/CVM recentes
    - o lado "acontecimentos" do momento atual (o lado "perspectivas" vem
    do perfil de research, ao lado). Só repassa o que
    data/market_makers.py:contexto_ticker devolve; lista vazia é um
    resultado REAL (nenhum evento na janela), com texto próprio."""
    try:
        contexto = _contexto_cacheado(ticker)
    except Exception as exc:
        print(f"[visao_360] contexto de mercado indisponível pra {ticker}: {exc!r}")
        ds.vazio("Catalisadores e mudanças recentes indisponíveis agora (a fonte não respondeu).")
        return

    catalisadores = contexto.get("catalisadores") or []
    mudancas = contexto.get("mudancas") or []
    ds.subtitulo("Catalisadores (próximos 60 dias)")
    if catalisadores:
        linhas = []
        for item in catalisadores:
            data_evento = item.get("data")
            quando = data_evento.strftime("%d/%m/%Y") if hasattr(data_evento, "strftime") else "—"
            status = item.get("status_label") or ("confirmado" if item.get("confirmado") else "estimado")
            linhas.append(
                f"{html.escape(str(item.get('categoria') or 'evento'))} em {html.escape(quando)} "
                f"<span class='cinza'>({html.escape(str(status))})</span>"
            )
        ds.lista_compacta(linhas)
    else:
        ds.vazio("Nenhum catalisador (resultado, proventos ou assembleia) nos próximos 60 dias.")

    if mudancas:
        linhas_mudanca = []
        for item in mudancas:
            data_evento = item.get("data_evento")
            quando = data_evento.strftime("%d/%m/%Y") if hasattr(data_evento, "strftime") else "—"
            fonte = ""
            if item.get("fonte_url"):
                fonte = (
                    f" — <a href='{html.escape(str(item['fonte_url']), quote=True)}' target='_blank' "
                    f"rel='noopener' class='cinza'>{html.escape(str(item.get('fonte_label') or 'fonte'))}</a>"
                )
            elif item.get("fonte_label"):
                fonte = f" — {html.escape(str(item['fonte_label']))}"
            linhas_mudanca.append(f"{html.escape(quando)}: {html.escape(str(item.get('descricao') or ''))}{fonte}")
        ds.subtitulo("Mudanças recentes (tese / CVM)")
        ds.lista_compacta(linhas_mudanca)


def _render_visao_executiva(ticker: str, perfil: dict | None, motivo_perfil: str | None):
    """Visão executiva do negócio em 4 blocos, 2 por linha (pedido
    explícito: "não exibir como parágrafos enormes... leitura inicial
    precisa ser rápida"): O NEGÓCIO | MOMENTO ATUAL na primeira linha,
    PRINCIPAIS RISCOS | POSICIONAMENTO COMPETITIVO na segunda.

    Os 4 blocos são os MESMOS renderizadores de ui/coordenador_tab.py
    (API pública render_perfil_*) - a diferença é só o arranjo: lá as 18
    perguntas do perfil saem numa coluna vertical única, e "riscos" fica
    enterrado no meio de "momento atual"; aqui risco é um bloco de
    primeira classe (é o que quebra a tese) e nada ocupa a largura toda
    de um terminal largo."""
    perguntas = (perfil or {}).get("perguntas") or {}
    if perfil is None:
        ds.vazio(str(motivo_perfil or "Perfil da empresa indisponível no momento."))
        return

    linha1_esq, linha1_dir = st.columns(2, gap="medium")
    with linha1_esq:
        ds.secao("O negócio", "o que faz e como ganha dinheiro")
        comite_ui.render_perfil_identificacao(perfil.get("identificacao") or {}, perguntas)
    with linha1_dir:
        ds.secao("Momento atual", "acontecimentos e perspectivas")
        comite_ui.render_perfil_pergunta(perguntas.get("perspectivas"), "Perspectivas")
        comite_ui.render_perfil_pergunta(perguntas.get("pressoes_de_margem"), "Pressões sobre a margem")
        _render_momento_mercado(ticker)

    linha2_esq, linha2_dir = st.columns(2, gap="medium")
    with linha2_esq:
        ds.secao("Principais riscos", "o que quebraria a tese")
        comite_ui.render_perfil_pergunta(perguntas.get("riscos"), "Riscos identificados")
        comite_ui.render_perfil_pergunta_quebra_tese(perguntas.get("o_que_quebraria_a_tese"))
    with linha2_dir:
        # As 3 perguntas, uma a uma, em vez de render_perfil_posicionamento
        # (que embute um subtítulo "Posicionamento competitivo" próprio) -
        # com o cabeçalho de seção acima, o subtítulo embutido repetia o
        # mesmo rótulo 2x seguidas na tela (visto no Playwright).
        ds.secao("Posicionamento competitivo", "concorrentes, vantagens, barreiras")
        comite_ui.render_perfil_pergunta(perguntas.get("posicao_competitiva"), "Posição competitiva")
        comite_ui.render_perfil_pergunta(perguntas.get("vantagens_competitivas"), "Vantagens competitivas")
        comite_ui.render_perfil_pergunta(perguntas.get("concorrentes"), "Concorrentes")


# ============================================================
# BLOCO D - Indicadores fundamentalistas por categoria.
# ============================================================

def _render_fundamentos(ticker: str, linha: dict | None, consolidado: dict | None, prefs: dict):
    """Indicadores por CATEGORIA (Valuation, Rentabilidade, Crescimento,
    Saúde financeira) em vez de uma fileira única de 7 números sem
    agrupamento - cada categoria só mostra o que a fonte de fato reportou
    pra ESTE ticker, e uma categoria sem nenhum indicador disponível diz o
    motivo real em vez de desaparecer em silêncio ou exibir "—" em tudo.

    Fontes: data/radar.py:linha_valuation (yfinance, ponto atual) para
    múltiplos/margens/dívida/FCF; ROIC trimestral, receita YoY e a mediana
    de P/L do setor vêm do parecer do Market Researcher (indicadores já
    calculados pelo Comitê) QUANDO existir análise - nunca estimados
    quando não existir. Nenhum indicador é calculado aqui."""
    fmt = prefs["formato_numerico"]
    linha = linha or {}
    indicadores_comite = (_analista(consolidado or {}, "market_researcher") or {}).get("indicadores") or {}
    # obter_indicadores: MESMA chamada (cache de 12h por ticker) que
    # linha_valuation já fez acima - zero requisição nova de rede. Usada só
    # pelas 2 margens que linha_valuation não repassa no dict dele
    # (margem EBITDA e margem operacional), pedidas explicitamente na lista
    # de indicadores da missão.
    try:
        indicadores_fonte = obter_indicadores(ticker) or {}
    except Exception as exc:
        print(f"[visao_360] margens adicionais indisponíveis pra {ticker}: {exc!r}")
        indicadores_fonte = {}

    def num(valor, casas=2, sufixo="", prefixo=""):
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            return None
        return ds.numero_financeiro_html(valor, casas, fmt, prefixo=prefixo, sufixo=sufixo)

    categorias = [
        ("Valuation", [
            ("P/L", num(linha.get("pl")), None),
            ("P/VP", num(linha.get("pvp")), None),
            ("EV/EBITDA", num(linha.get("ev_ebitda"), casas=1), None),
            ("P/L MEDIANA SETOR", num(indicadores_comite.get("pl_mediana_setor_x")), "Comitê"),
            ("DIV. YIELD 12M", num(linha.get("dividend_yield"), sufixo="%"), None),
        ], "Múltiplos do ponto atual (yfinance). Série histórica de múltiplos não é calculada "
           "nesta versão - só o valor de hoje existe, nunca estimado."),
        ("Rentabilidade", [
            ("ROE", num(linha.get("roe"), sufixo="%"), None),
            ("ROIC TRIMESTRAL", num(indicadores_comite.get("roic_trimestral_pct"), sufixo="%"), "não anualizado"),
            ("MARGEM LÍQUIDA", num(linha.get("margem_liquida"), sufixo="%"), None),
            ("MARGEM EBITDA", num(indicadores_fonte.get("margem_ebitda"), sufixo="%"), None),
            ("MARGEM OPERACIONAL", num(indicadores_fonte.get("margem_operacional"), sufixo="%"), None),
        ], "ROE e margens vêm do ponto atual (yfinance); ROIC só existe quando o Comitê já "
           "analisou o ticker (exige alíquota efetiva real e balanço no mesmo trimestre - nunca "
           "aproximado com alíquota-padrão)."),
        ("Crescimento", [
            ("RECEITA LÍQUIDA YoY", ds.variacao_html(indicadores_comite["receita_liquida_yoy_pct"], fmt)
             if isinstance(indicadores_comite.get("receita_liquida_yoy_pct"), (int, float)) else None, "Comitê"),
        ], "Crescimento de receita/EBITDA/lucro só existe nesta tela quando o Comitê já analisou o "
           "ticker (série trimestral da CVM, só Brasil). Não há fonte de crescimento no ponto atual "
           "do yfinance usado pelas demais categorias."),
        ("Saúde financeira", [
            ("DÍV. LÍQ./EBITDA", num(linha.get("divida_liquida_ebitda"), casas=1, sufixo="x"), None),
            ("DÍVIDA LÍQUIDA", html.escape(config.formatar_valor_mercado(linha["divida_liquida"], fmt))
             if isinstance(linha.get("divida_liquida"), (int, float)) else None, None),
            ("FLUXO DE CAIXA LIVRE", html.escape(config.formatar_valor_mercado(linha["fluxo_caixa_livre"], fmt))
             if isinstance(linha.get("fluxo_caixa_livre"), (int, float)) else None, "TTM"),
            ("EBITDA", html.escape(config.formatar_valor_mercado(linha["ebitda"], fmt))
             if isinstance(linha.get("ebitda"), (int, float)) else None, None),
        ], "Dívida líquida = dívida total − caixa (yfinance). Dívida líquida/EBITDA não é calculada "
           "quando o EBITDA é zero ou negativo - a razão pareceria baixa justamente no caso mais grave."),
    ]

    for titulo, itens, nota_fonte in categorias:
        disponiveis = [(rotulo, valor, nota) for rotulo, valor, nota in itens if valor]
        ds.secao(titulo, f"{len(disponiveis)} de {len(itens)} indicadores disponíveis")
        if disponiveis:
            st.markdown(ds.faixa_metricas_html(disponiveis, minimo=142), unsafe_allow_html=True)
        else:
            ds.vazio("Nenhum indicador desta categoria foi reportado para este ticker nesta consulta.")
        st.markdown(f"<div class='v360-nota'>{html.escape(nota_fonte)}</div>", unsafe_allow_html=True)

    if linha.get("preco_erro"):
        ds.vazio("A cotação usada nos múltiplos não foi obtida nesta consulta - múltiplos que dependem "
                 "do preço (P/L, P/VP, EV/EBITDA, dividend yield) podem estar defasados.")
    if linha.get("desatualizado"):
        ds.vazio("Os fundamentos exibidos vêm de uma coleta anterior (a fonte não respondeu agora) - "
                 "são dados reais, mas não do momento.")
    for alerta in (linha.get("alerta_qualidade") or []):
        st.warning(f"Alerta de qualidade no próprio dado: {alerta}.")


# ============================================================
# BLOCO E - Valuation: resumo, modelos e cenários.
# ============================================================

_ROTULO_CENARIO = {"pessimista": "BEAR · PESSIMISTA", "base": "BASE", "otimista": "BULL · OTIMISTA"}


def _render_cenarios_dcf(model_builder: dict, prefs: dict):
    """Os 3 cenários do DCF do Comitê lado a lado (bear/base/bull), com
    preço-alvo, potencial e as 2 premissas que mudam entre eles
    (crescimento do FCF e WACC) - comparáveis na horizontal, que é a
    leitura que a tabela vertical do parecer não dá.

    Zero cálculo: lê `model_builder["cenarios"]`, produzido pelo motor
    único (data/coordenador_central/dcf.py). O detalhamento completo
    (premissas, valor da firma, sensibilidade WACC × crescimento) NÃO é
    repetido aqui - fica só no parecer do Model Builder, no
    aprofundamento, pra mesma informação não aparecer 2x na tela."""
    cenarios = (model_builder or {}).get("cenarios") or {}
    disponiveis = [
        (chave, cenarios.get(chave) or {}) for chave in ("pessimista", "base", "otimista")
        if isinstance((cenarios.get(chave) or {}).get("preco_alvo"), (int, float))
    ]
    if not disponiveis:
        return False
    fmt = prefs["formato_numerico"]
    moeda = str(model_builder.get("moeda") or "R$")
    blocos = []
    for chave, cenario in disponiveis:
        upside = cenario.get("upside_pct")
        blocos.append(
            f"<div class='v360-cenario{' v360-cenario-base' if chave == 'base' else ''}'>"
            + ds.rotulo_html(_ROTULO_CENARIO[chave])
            + f"<div class='v360-cenario-valor'>{_reais(cenario.get('preco_alvo'), fmt, moeda=moeda)}</div>"
            + "<div style='font-size:0.72rem;'>"
            + (ds.variacao_html(upside, fmt) if isinstance(upside, (int, float)) else "—")
            + "</div>"
            + f"<div class='v360-nota'>cresc. FCF {ds.pct_html(cenario.get('crescimento_fcf'))} · "
              f"WACC {ds.pct_html(cenario.get('wacc'))}</div></div>"
        )
    st.markdown("<div class='v360-cenarios'>" + "".join(blocos) + "</div>", unsafe_allow_html=True)
    return True


def _render_valuation(ticker: str, linha: dict | None, comite: dict, prefs: dict):
    """Seção central do terminal, em 3 partes claramente separadas:

    1. RESUMO - preço atual, preço justo de cada modelo que existe,
       potencial, modelo utilizado, data-base e status do cálculo.
    2. MODELOS - DCF do Comitê (com os 3 cenários), múltiplo relativo
       (P/L setorial), consenso das casas e o DCF interativo com as
       premissas do usuário, cada um com sua origem explícita. Modelos
       diferentes apontando preços diferentes é esperado, não bug - fica
       dito na tela.
    3. CENÁRIOS - bear/base/bull quando o Model Builder tiver rodado.

    NENHUM modelo, premissa ou cálculo novo é introduzido aqui: os preços
    justos vêm do consolidado do Comitê e o DCF interativo é o mesmo
    controle_dcf_inline de ANÁLISES > Empresas. Lacunas estruturais (ex.:
    não existe modelo setorial específico - banco/seguradora/utility usam
    o mesmo DCF genérico) estão documentadas no relatório da missão, não
    improvisadas aqui."""
    fmt = prefs["formato_numerico"]
    linha = linha or {}
    consolidado = comite.get("consolidado") or {}
    sinal = consolidado.get("sinal_comite") or {}
    model_builder = _analista(consolidado, "model_builder") or {}
    moeda = sinal.get("moeda_preco_alvo_modelo") or model_builder.get("moeda") or "R$"
    preco_atual = linha.get("preco") if linha.get("preco") is not None else sinal.get("preco_atual")

    alvo_modelo = sinal.get("preco_alvo_modelo")
    alvo_pl = sinal.get("preco_alvo_pl_setorial")
    alvo_consenso = sinal.get("preco_alvo_consenso")
    upside_modelo = sinal.get("upside_modelo_pct")

    ds.secao("Resumo", "preço atual × preço justo estimado")
    resumo = [
        ("PREÇO ATUAL", _reais(preco_atual, fmt, fallback="indisponível"),
         comite_ui.fmt_data(sinal.get("preco_atual_consultado_em")) if sinal.get("preco_atual_consultado_em") else None),
        ("PREÇO JUSTO · DCF", _reais(alvo_modelo, fmt, fallback="não calculado", moeda=moeda), "Model Builder"),
        ("POTENCIAL", ds.variacao_html(upside_modelo, fmt) if isinstance(upside_modelo, (int, float)) else "—",
         "DCF vs. cotação"),
        ("REFERÊNCIA · P/L SETORIAL", _reais(alvo_pl, fmt, fallback="não calculado", moeda=moeda),
         "múltiplo relativo"),
        ("CONSENSO DAS CASAS", _reais(alvo_consenso, fmt, fallback="não disponível", moeda=moeda),
         "estimativa de terceiro"),
    ]
    st.markdown(ds.faixa_metricas_html(resumo, grande=True, minimo=150), unsafe_allow_html=True)
    _render_potencial_referencias(alvo_pl, alvo_consenso, preco_atual, fmt)

    if comite["estado"] != "ok":
        ds.vazio(
            "Preço justo proprietário (DCF do Comitê), referência por P/L setorial e consenso das casas "
            "só aparecem depois de uma análise do Comitê para este ticker. Abaixo, o DCF interativo "
            "calcula um preço-alvo com as premissas que você informar."
        )
    else:
        data_base = model_builder.get("data_base") or comite_ui.fmt_data((comite.get("analise") or {}).get("iniciado_em"))
        status_dcf = str(model_builder.get("recomendacao") or "INSUFICIENTE").upper()
        st.markdown(
            f"<div class='v360-nota'>Modelo: DCF de 5 anos + Gordon Growth, líquido de dívida "
            f"(motor único em data/coordenador_central/dcf.py) · data-base {html.escape(str(data_base))} · "
            f"status do cálculo: {'MODELADO' if status_dcf == 'MODELADO' else 'NÃO MODELADO'}. "
            "Modelos diferentes podem apontar preços justos diferentes para o mesmo papel — "
            "isso é esperado (premissas e fontes distintas), não um erro.</div>",
            unsafe_allow_html=True,
        )

    ds.secao("Cenários", "bear / base / bull do DCF do Comitê")
    if not _render_cenarios_dcf(model_builder, prefs):
        motivo = str(model_builder.get("tese") or "").strip()
        faltantes = [str(c) for c in (model_builder.get("campos_faltantes") or [])]
        if comite["estado"] != "ok":
            ds.vazio("Cenários de DCF não existem para este ticker ainda: nenhuma análise do Comitê "
                     "foi registrada nesta instalação.")
        elif faltantes:
            ds.vazio("Cenários de DCF não calculados nesta análise — premissas/dados ausentes: "
                     + ", ".join(faltantes) + ".")
        else:
            ds.vazio(motivo or "Cenários de DCF não calculados nesta análise (premissas explícitas "
                               "são necessárias).")

    ds.secao("DCF interativo", "premissas informadas por você")
    if linha.get("fluxo_caixa_livre") is None:
        ds.vazio(
            "DCF interativo indisponível para este ticker: não há fluxo de caixa livre ANUAL "
            "(ponto atual do yfinance) para descontar. O acumulado no ano da CVM nunca fecha 12 meses "
            "nesta integração e não serve de base anual sem fabricar uma anualização."
        )
        return
    st.markdown(
        "<div class='v360-nota'>O PREGÃO nunca assume taxa de crescimento nem taxa de desconto: "
        "informe as duas premissas e o preço-alvo é calculado na hora, com a dívida líquida "
        "subtraída e a sensibilidade WACC × crescimento disponível abaixo do resultado.</div>",
        unsafe_allow_html=True,
    )
    try:
        controle_dcf_inline(ticker, linha, None)
    except Exception as exc:
        print(f"[visao_360] DCF interativo falhou pra {ticker}: {exc!r}")
        ds.vazio("Não foi possível calcular o DCF interativo agora.")


def _render_potencial_referencias(alvo_pl, alvo_consenso, preco_atual, fmt: str):
    """Potencial indicativo das 2 referências que NÃO trazem upside
    próprio no consolidado (P/L setorial e consenso das casas) - usa
    ui/analises_tab.py:potencial_pct, o MESMO helper já usado em produção
    pro preço-alvo das casas (nunca uma fórmula nova), e
    design_system.variacao_html pro sinal/cor (nunca um "+" montado à
    mão). Nada aparece quando falta um dos dois lados - jamais um 0%
    fabricado."""
    partes = []
    for rotulo, alvo in (("P/L setorial", alvo_pl), ("consenso das casas", alvo_consenso)):
        potencial = potencial_pct(alvo, preco_atual)
        if potencial is not None:
            partes.append(f"{html.escape(rotulo)} {ds.variacao_html(potencial, fmt, casas=1)}")
    if partes:
        st.markdown(
            "<div class='v360-nota'>Potencial indicativo das referências: " + " · ".join(partes) + ".</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# APROFUNDAMENTO - uma seção por vez (ver docstring do módulo).
# ============================================================

def _render_pareceres(ticker: str, comite: dict):
    """Pareceres dos especialistas com navegação de LISTA LATERAL
    compacta (nome + recomendação) e o parecer completo ao lado - pedido
    explícito: "nunca seis nomes amontoados numa linha pouco legível".

    Também é a opção mais barata: só o parecer selecionado é renderizado
    (st.tabs monta os 6 em todo rerun, e cada parecer inclui tabelas de
    premissas/cenários/sensibilidade). O corpo é
    coordenador_tab.render_parecer_especialista - a MESMA função que
    COMITÊ > Histórico usa, nunca uma segunda versão."""
    if comite["estado"] != "ok":
        ds.vazio("Nenhum parecer de especialista para este ticker: depende de uma análise do Comitê.")
        return
    analistas = ((comite["consolidado"].get("pareceres_analistas") or {}).get("analistas")) or []
    if not analistas:
        ds.vazio("A análise mais recente deste ticker não registrou nenhum parecer de especialista.")
        return

    cobertura = _cobertura_comite(comite["consolidado"])
    rotulos = {}
    for indice, analista in enumerate(analistas):
        nome = str(analista.get("nome") or analista.get("id") or f"Especialista {indice + 1}")
        recomendacao = str(analista.get("recomendacao") or "INSUFICIENTE")
        rotulos[indice] = f"{nome} · {recomendacao}"

    coluna_lista, coluna_parecer = st.columns([0.27, 0.73], gap="medium")
    with coluna_lista:
        ds.secao("Especialistas", f"{cobertura['n_com_parecer']} de {cobertura['n_total']} com parecer")
        with st.container(key="v360_especialista"):
            escolhido = st.radio(
                "Especialista", list(rotulos), format_func=rotulos.get,
                key=f"v360_parecer_{ticker}", label_visibility="collapsed",
            )
        if cobertura["especialistas_sem_parecer"]:
            st.markdown(
                "<div class='v360-nota'>Sem base para opinar nesta análise: "
                + html.escape(", ".join(cobertura["especialistas_sem_parecer"]))
                + ". O motivo de cada um está no parecer dele.</div>",
                unsafe_allow_html=True,
            )
    with coluna_parecer:
        analista = analistas[escolhido if escolhido is not None else 0]
        ds.secao(
            str(analista.get("nome") or analista.get("id") or "Especialista"),
            str(analista.get("especialidade") or "") or None,
        )
        comite_ui.render_parecer_especialista(analista)


def _render_research(ticker: str, perfil: dict | None, comite: dict, prefs: dict):
    """Research das casas monitoradas: últimas publicações (recomendação,
    preço-alvo, data, tipo de documento), consenso e divergências.

    Fonte: data/research/comparador.py:montar_relatorio_comparativo (100%
    determinístico, zero IA) via o loader cacheado de ui/analises_tab.py;
    o consenso já calculado pelo perfil da empresa (dispersão de
    preço-alvo, casa mais otimista/cautelosa, quem mudou hoje) é
    reaproveitado de coordenador_tab.render_perfil_research_consenso.
    Quando o Comitê já rodou, as publicações que ELE usou aparecem pelo
    renderizador de casas de sempre.

    Estados vazios são curtos e voltados ao usuário ("sem cobertura
    disponível") - nenhuma mensagem de migration, SQL, nome de coluna ou
    exceção interna chega à tela (regra explícita da missão); o detalhe
    técnico vai pro log do servidor."""
    fmt = prefs["formato_numerico"]
    ds.secao("Casas monitoradas", "estado mais recente por casa")
    try:
        relatorio = comparativo_casas_cacheado(ticker)
    except Exception as exc:
        print(f"[visao_360] comparativo de casas indisponível pra {ticker}: {exc!r}")
        relatorio = None

    if relatorio is None or not relatorio.get("disponivel"):
        ds.vazio("Research das casas indisponível agora: a base monitorada não respondeu nesta consulta.")
    elif not relatorio.get("tabela_comparativa"):
        ds.vazio("Sem cobertura disponível para este ativo: nenhuma casa monitorada publicou "
                 "research estruturado sobre ele.")
    else:
        linhas = []
        for item in relatorio["tabela_comparativa"]:
            recomendacao = item.get("recomendacao_original") or item.get("recomendacao_categoria")
            linhas.append([
                (f"<b>{html.escape(str(item.get('casa') or '—'))}</b>", "e"),
                (comite_ui.badge_recomendacao_html(recomendacao) if recomendacao else "—", "e"),
                (_reais(item.get("preco_alvo"), fmt, fallback="não publicado"), "d"),
                (html.escape(str(item.get("data_publicacao") or "—")), "e"),
                (html.escape(str(item.get("tipo_documento") or "—")), "e"),
                (html.escape(str(item.get("projecao_receita") or "—")), "e"),
                (html.escape(str(item.get("projecao_ebitda_margem") or "—")), "e"),
            ])
        st.markdown(
            ds.tabela_html(
                [("Casa", "e"), ("Recomendação", "e"), ("Preço-alvo (BRL)", "d"), ("Publicação", "e"),
                 ("Documento", "e"), ("Projeção receita", "e"), ("Projeção margem EBITDA", "e")],
                linhas, min_largura=820,
            ),
            unsafe_allow_html=True,
        )
        consenso = relatorio.get("consenso") or {}
        dispersao = relatorio.get("dispersao_precos_alvo") or {}
        resumo_consenso = []
        if consenso.get("categoria_mais_comum"):
            contagem = (consenso.get("contagem_por_categoria") or {}).get(consenso["categoria_mais_comum"])
            resumo_consenso.append((
                "CONSENSO", html.escape(str(consenso["categoria_mais_comum"])),
                f"{contagem} de {consenso.get('n_casas_com_recomendacao_classificada')} casa(s)",
            ))
        if not dispersao.get("amostra_insuficiente"):
            resumo_consenso += [
                ("ALVO MÍNIMO", _reais(dispersao.get("minimo"), fmt), None),
                ("ALVO MEDIANO", _reais(dispersao.get("mediana"), fmt), None),
                ("ALVO MÁXIMO", _reais(dispersao.get("maximo"), fmt), None),
            ]
        if resumo_consenso:
            st.markdown(ds.faixa_metricas_html(resumo_consenso, minimo=140), unsafe_allow_html=True)
        elif consenso.get("amostra_insuficiente"):
            ds.vazio("Amostra insuficiente para apurar consenso: menos de 2 casas com recomendação "
                     "classificada para este ativo.")

        divergencia = (relatorio.get("divergencias_premissas") or {}).get("recomendacao") or {}
        if divergencia.get("numerica") or divergencia.get("qualitativa"):
            tipos = []
            if divergencia.get("numerica"):
                tipos.append("preços-alvo distantes entre si")
            if divergencia.get("qualitativa"):
                tipos.append("categorias de recomendação diferentes")
            extra = ""
            if divergencia.get("casa_mais_otimista") and divergencia.get("casa_mais_cautelosa"):
                extra = (f" Mais otimista: {divergencia['casa_mais_otimista']} · mais cautelosa: "
                         f"{divergencia['casa_mais_cautelosa']}.")
            st.warning(f"As casas divergem sobre este ativo ({' e '.join(tipos)}).{extra}")
        elif relatorio.get("tabela_comparativa"):
            st.markdown("<div class='v360-nota'>As casas com dado suficiente para comparar convergem "
                        "em recomendação e preço-alvo.</div>", unsafe_allow_html=True)

        if relatorio.get("fontes_evidencias"):
            with st.expander(f"Publicações e links ({len(relatorio['fontes_evidencias'])})"):
                ds.lista_compacta(
                    f"<b>{html.escape(str(f.get('casa') or '—'))}</b> "
                    f"({html.escape(str(f.get('data_publicacao') or '—'))}): "
                    + (f"<a href='{html.escape(str(f.get('link')), quote=True)}' target='_blank' "
                       f"rel='noopener'>{html.escape(str(f.get('titulo') or 'ver relatório'))}</a>"
                       if f.get("link") else html.escape(str(f.get("titulo") or "ver relatório")))
                    for f in relatorio["fontes_evidencias"]
                )

    ds.secao("Consenso e divergência consolidados", "cálculo do perfil da empresa")
    if perfil is None:
        ds.vazio("Consenso consolidado indisponível: o perfil da empresa não foi carregado nesta consulta.")
    else:
        comite_ui.render_perfil_research_consenso(perfil.get("research") or {})

    if comite["estado"] == "ok":
        casas_comite = (comite["consolidado"].get("pareceres_analistas") or {}).get("casas_research") or []
        if casas_comite:
            ds.secao("Publicações usadas pelo Comitê", f"{len(casas_comite)} casa(s)")
            comite_ui.render_casas_research(
                casas_comite,
                (comite["consolidado"].get("pareceres_analistas") or {}).get("preco_alvo_consenso") or {},
            )

    st.markdown(
        "<div class='v360-nota'>Recomendação e preço-alvo exibidos aqui são sempre ESTIMATIVA DE "
        "TERCEIRO (da casa que publicou), em BRL — nunca uma recomendação ou preço-alvo próprio do "
        "PREGÃO.</div>",
        unsafe_allow_html=True,
    )


def _render_evidencias(comite: dict):
    """Evidências, divergências e pontos que precisam de revisão numa
    estrutura visual própria - não como 4 accordions genéricos soltos
    (pedido explícito). Ordem: o que SUSTENTA a recomendação (evidências,
    com fonte e data), onde o Comitê DIVERGE de si mesmo (entre
    especialistas, e comparador × memória de research), o que ficou sem
    base, e por último a conclusão determinística completa + a leitura de
    IA quando existir.

    Divergência é tratada como informação de DECISÃO (fica visível, com
    selo), nunca como mensagem técnica escondida. Nada aqui é recalculado:
    os campos vêm prontos de data/coordenador_central/consolidacao.py."""
    if comite["estado"] != "ok":
        ds.vazio("Evidências e divergências dependem de uma análise do Comitê para este ticker.")
        return
    consolidado = comite["consolidado"]

    evidencias = consolidado.get("evidencias") or []
    ds.secao("Evidências utilizadas", f"{len(evidencias)} registro(s)")
    if evidencias:
        st.markdown(
            ds.tabela_html(
                [("Especialista", "e"), ("Fonte", "e"), ("Data", "e"), ("Evidência", "e")],
                [[
                    (html.escape(str(e.get("especialista") or "—")), "e"),
                    (html.escape(str(e.get("fonte") or "—")), "e"),
                    (html.escape(comite_ui.fmt_data(e.get("data"))), "e"),
                    (html.escape(str(e.get("titulo") or "—")), "e"),
                ] for e in evidencias],
                min_largura=620,
            ),
            unsafe_allow_html=True,
        )
    else:
        ds.vazio("Esta análise não registrou evidência estruturada — a recomendação se apoia apenas "
                 "nos indicadores quantitativos dos pareceres.")

    divergencias = consolidado.get("divergencias") or {}
    entre_especialistas = divergencias.get("entre_analistas_comite")
    cross = divergencias.get("cross_comparador_memoria") or {}
    itens_cross = cross.get("divergencias") or []
    ds.secao("Divergências", "informação de decisão, não aviso técnico")
    if entre_especialistas:
        comite_ui.render_divergencia_comite(entre_especialistas)
    if itens_cross:
        st.markdown(
            f"<div style='margin:0.3rem 0;'>{ds.badge_html('COMPARADOR × MEMÓRIA DE RESEARCH', ds.NIVEL_ALERTA)}"
            f"<span class='v360-nota' style='margin-left:0.4rem;'>{len(itens_cross)} campo(s) em que a "
            "leitura mais recente das casas não bate com o que está na memória permanente de research "
            "— mesmo tipo de dado, duas fontes.</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            ds.tabela_html(
                [("Casa", "e"), ("Tipo", "e"), ("Campo", "e"), ("Comparador", "e"), ("Memória", "e")],
                [[
                    (html.escape(str(d.get("casa") or "—")), "e"),
                    (html.escape(str(d.get("tipo") or "—")), "e"),
                    (html.escape(str(d.get("campo") or "—")), "e"),
                    (html.escape(str(d.get("comparador"))), "e"),
                    (html.escape(str(d.get("memoria_research"))), "e"),
                ] for d in itens_cross],
                min_largura=640,
            ),
            unsafe_allow_html=True,
        )
    if not entre_especialistas and not itens_cross:
        ds.vazio("Nenhuma divergência registrada nesta análise.")

    pontos = consolidado.get("pontos_atencao") or []
    cobertura = _cobertura_comite(consolidado)
    ds.secao("Pontos de revisão e dados insuficientes", f"{len(pontos)} ponto(s) de atenção")
    if pontos:
        ds.lista_compacta(html.escape(str(p)) for p in pontos)
    else:
        ds.vazio("A consolidação não marcou nenhum ponto para revisão humana nesta análise.")
    if cobertura["especialistas_sem_parecer"]:
        ds.vazio("Sem base para opinar nesta análise: "
                 + ", ".join(cobertura["especialistas_sem_parecer"])
                 + " — o motivo de cada um está no parecer dele (aba Pareceres).")

    with st.expander("Conclusão consolidada completa e material de apoio"):
        comite_ui.render_sintese_final(consolidado)
    if consolidado.get("sintese_divergencia_comite_ia") or consolidado.get("sintese_qualitativa_research_ia"):
        comite_ui.render_sintese_ia(consolidado)


def _render_historico_analises(ticker: str, comite: dict):
    """Histórico de análises do Comitê para este ticker - data, status,
    recomendação e confiança de cada execução já persistida, numa tabela
    compacta (a lista vem de `listar_analises_por_ticker`, já carregada
    pro veredito: zero consulta nova). Abrir o registro completo continua
    sendo em COMITÊ > Histórico, por link."""
    analises = comite.get("analises") or []
    if comite["estado"] == "indisponivel":
        ds.vazio("Histórico de análises indisponível agora: não foi possível consultar a base. "
                 "Isto é diferente de 'nunca analisado'.")
        return
    if not analises:
        ds.vazio(f"O Comitê nunca analisou {ticker} nesta instalação.")
        navegacao.link(
            "Executar Comitê para este ticker ↗", "comite", "visao-geral",
            chave=f"v360_executar_comite_hist_{ticker}", ticker=ticker,
        )
        return

    ds.secao("Análises do Comitê", f"{len(analises)} execução(ões) registrada(s)")
    linhas = []
    for item in analises:
        status = str(item.get("status") or "—")
        nivel = ds.NIVEL_OK if status == "CONCLUIDA" else (
            ds.NIVEL_ERRO if status == "ERRO" else ds.NIVEL_ALERTA)
        resultado = item.get("resultado") or {}
        recomendacao = ((resultado.get("sinal_comite") or {}).get("sinal")) if resultado else None
        confianca = ((resultado.get("confianca") or {}).get("categoria")) if resultado else None
        linhas.append([
            (html.escape(comite_ui.fmt_data(item.get("iniciado_em"))), "e"),
            (ds.badge_html(status, nivel), "e"),
            (comite_ui.badge_recomendacao_html(recomendacao) if recomendacao else "—", "e"),
            (comite_ui.badge_confianca_html(confianca) if confianca else "—", "e"),
        ])
    st.markdown(
        ds.tabela_html(
            [("Data", "e"), ("Status", "e"), ("Recomendação", "e"), ("Confiança", "e")],
            linhas, min_largura=520,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='v360-nota'>Recomendação e confiança por execução vêm do consolidado gravado na "
        "época — uma análise antiga nunca é reinterpretada com os dados de hoje.</div>",
        unsafe_allow_html=True,
    )
    navegacao.link(
        "Abrir registro completo no Comitê ↗", "comite", "historico",
        chave=f"v360_historico_comite_{ticker}", ticker=ticker,
    )


def _render_noticias(ticker: str, prefs: dict):
    """Notícias do ticker - reusa ui/news_tab.py:render_news_ticker (a
    mesma lista densa de hora/selo/manchete/fontes/link usada em TOP
    MERCADO, incluindo o status de verificação da manchete). Nenhuma
    segunda implementação de feed aqui; a fonte só é consultada quando
    esta seção é a selecionada."""
    try:
        render_news_ticker(ticker, prefs)
    except Exception as exc:
        print(f"[visao_360] notícias indisponíveis pra {ticker}: {exc!r}")
        ds.vazio("Notícias indisponíveis agora: a fonte não respondeu nesta consulta.")


# ============================================================
# Composição final.
# ============================================================

_SECAO_PARECERES = "PARECERES DOS ESPECIALISTAS"
_SECAO_RESEARCH = "RESEARCH E CONSENSO"
_SECAO_EVIDENCIAS = "EVIDÊNCIAS E DIVERGÊNCIAS"
_SECAO_NOTICIAS = "NOTÍCIAS"
_SECAO_HISTORICO = "HISTÓRICO DE ANÁLISES"


def render_visao_360(ticker: str, prefs: dict):
    """A tela inteira, nos 3 andares descritos na docstring do módulo.

    Ordem das chamadas de dados é deliberada: cotação, múltiplos e perfil
    (sempre necessários) primeiro; o consolidado do Comitê em seguida
    (uma leitura, reaproveitada pelo veredito, fundamentos, valuation,
    pareceres, evidências e histórico - nunca relida por seção); e as
    fontes caras (research das casas, notícias) só dentro da seção de
    aprofundamento que o usuário abriu."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        st.info("Selecione um ticker para ver a Visão 360.")
        return
    _injetar_css()

    try:
        linha = linha_valuation(ticker)
    except Exception as exc:
        print(f"[visao_360] múltiplos indisponíveis pra {ticker}: {exc!r}")
        linha = None
    perfil, motivo_perfil = comite_ui.obter_perfil_para_tela(ticker)
    comite = _carregar_comite(ticker)

    # --- ANDAR 1: DECISÃO ---
    with st.container(border=True):
        _render_cabecalho(ticker, linha, prefs)
        _render_acoes_rapidas(ticker)

    with st.container(border=True):
        ds.painel_titulo("VEREDITO DO COMITÊ")
        _render_veredito(ticker, comite, prefs)

    # --- ANDAR 2: ANÁLISE ---
    with st.container(border=True):
        ds.painel_titulo("PERFIL DA EMPRESA — VISÃO EXECUTIVA")
        _render_visao_executiva(ticker, perfil, motivo_perfil)

    coluna_fundamentos, coluna_valuation = st.columns([0.42, 0.58], gap="medium")
    with coluna_fundamentos:
        with st.container(border=True):
            ds.painel_titulo("INDICADORES FUNDAMENTALISTAS")
            if linha is None:
                ds.vazio("Indicadores indisponíveis agora: a fonte de fundamentos não respondeu "
                         "nesta consulta.")
            else:
                _render_fundamentos(ticker, linha, comite.get("consolidado"), prefs)
    with coluna_valuation:
        with st.container(border=True):
            ds.painel_titulo("VALUATION")
            _render_valuation(ticker, linha, comite, prefs)

    # --- ANDAR 3: APROFUNDAMENTO (uma seção por vez) ---
    with st.container(border=True):
        ds.painel_titulo("APROFUNDAMENTO")
        secoes = [_SECAO_PARECERES, _SECAO_RESEARCH, _SECAO_EVIDENCIAS, _SECAO_NOTICIAS, _SECAO_HISTORICO]
        chave = f"v360_aprofundar_{ticker}"
        padrao, chave_memoria = _escolha_estavel(chave, secoes, secoes[0])
        with st.container(key="v360_aprofundar"):
            escolha = st.segmented_control(
                "Seção de aprofundamento", secoes, default=padrao,
                key=chave, label_visibility="collapsed",
            ) or padrao
        st.session_state[chave_memoria] = escolha

        if escolha == _SECAO_PARECERES:
            _render_pareceres(ticker, comite)
        elif escolha == _SECAO_RESEARCH:
            _render_research(ticker, perfil, comite, prefs)
        elif escolha == _SECAO_EVIDENCIAS:
            _render_evidencias(comite)
        elif escolha == _SECAO_NOTICIAS:
            _render_noticias(ticker, prefs)
        else:
            _render_historico_analises(ticker, comite)
