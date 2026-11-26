# -*- coding: utf-8 -*-
"""Design system compartilhado do PREGÃO - fundação visual "terminal
Bloomberg" (preto/âmbar, denso, monoespaçado) usada por TODAS as abas.

Nasceu (auditoria "missao master" 2026-10-31) porque varias abas escritas
por sessoes diferentes usavam st.markdown("**Texto**")/st.metric() pra
subtitulo de secao - unica forma de conteudo do app que renderizava no
tamanho de fonte PADRAO do Streamlit, bem maior que o resto (que usa HTML
com font-size explicito em quase toda parte). Criado como modulo proprio
(nao deixado dentro de ui/analises_tab.py, onde nasceu) porque o mesmo
padrao se repetiu em pelo menos 2 abas (ANALISES, COORDENADOR CENTRAL)
escritas por sessoes diferentes - fica aqui pra ser o lugar obvio de
importar em qualquer aba nova.

Estendido (2026-11-06, missao "fundacao do design system") como base pra
uma reformulacao visual completa, em ondas, de todas as abas (Home/Mercado,
Watchlist, Research Radar, Comite, Analise de Empresas, Valuation,
Carteiras, Noticias/Morning Call) - cada onda e' uma frente/agente
diferente, trabalhando em paralelo. Pra isso NAO conflitar:

COMO AS PROXIMAS FRENTES DEVEM USAR ISTO
-----------------------------------------
1. Cor NUNCA e' hex solto num arquivo de aba. As cores reais (tema AMBAR
   por padrao, ver config.TEMAS) ja' viram variaveis CSS em runtime
   (app.py, perto de "_css_vars") - use sempre `var(--destaque)`,
   `var(--alta)`, `var(--baixa)`, `var(--neutro)`, `var(--cinza)`,
   `var(--borda)`, `var(--bg)`, `var(--painel-bg)`, `var(--ciano)` dentro
   de HTML/CSS. So' precisa do HEX cru (ex: biblioteca de grafico que nao
   aceita CSS var, tipo Plotly) quando REALMENTE nao da' pra evitar - nesse
   caso leia de `config.TEMAS[prefs["tema"]]`, nunca copie o numero.
   Excecao deliberada: jobs/morning_call_pdf.py e o HTML do e-mail
   (jobs/morning_call.py) sao um produto editorial a parte ("jornal
   economico, papel branco/serifada", ver docstring de cada um) - NAO
   usam este design system de proposito, nao migrar.
2. Indicador positivo/negativo: use `classe_sinal()` + as classes CSS
   globais `.alta`/`.baixa` (ja existem em style.css, ha' anos) - nunca
   reinvente um `"verde" if x > 0 else "vermelho"` novo. Pra variacao
   percentual/numero com sinal pronto pra exibir, use `variacao_html()`
   em vez de montar `"+" if x >= 0 else ""` + cor na mao (esse exato
   padrao se repetia, duplicado, em pelo menos 10 lugares antes desta
   fundacao - app.py, ui/mercado_tab.py, ui/macro_tab.py, ui/visao_geral.py,
   ui/setores_tab.py).
3. Numero financeiro alinhado (coluna de tabela, lista de cotacoes): use
   `numero_financeiro_html()` - aplica `font-variant-numeric: tabular-nums`
   + alinhamento a direita, pra colunas de numero nunca "dancarem" entre
   linhas. Formatacao BR/US continua vindo de `config.formatar_numero` /
   `config.formatar_valor_mercado` / `config.formatar_multiplo` (nao
   duplicar essa logica aqui - este modulo so' cuida do VISUAL do numero
   ja formatado).
4. Divisor entre secoes dentro de um painel: `divisor()` / `divisor_html()`
   - linha fina (`var(--borda)`), nunca uma `<hr>` padrao do navegador nem
   uma borda pesada nova.
5. Bloco de linhas densas (lista de itens, feed, ranking): classe CSS
   `.ds-compacto` (aplicada ao container pai) - reduz padding/line-height
   entre filhos sem precisar redeclarar isso em cada aba. Ver estilo em
   style.css, secao "DESIGN SYSTEM COMPARTILHADO".
6. Subtitulo de secao / lista com marcador: `subtitulo()`/`subtitulo_html()`
   / `lista_compacta()` (ja existiam, documentados abaixo) continuam
   validos e devem ser reaproveitados, nao recriados.
7. NÃO: cards genericos de SaaS (caixa com sombra/gradiente/icone
   decorativo), espaco vazio grande, mini-grafico sem funcao analitica,
   nada que pareca "dashboard generico de IA". O terminal e' denso,
   quadrado (sem border-radius), com hierarquia por COR/TIPOGRAFIA, nao
   por caixas.

ONDA "VISÃO 360" (2026-11-26, missão visao-360-redesign): a reformulação
completa da tela de análise de 1 ativo (ui/visao_360_tab.py) precisava de
5 padrões visuais que JÁ se repetiam copiados em 3+ abas, cada um com
medidas ligeiramente diferentes - foram promovidos pra cá em vez de
nascerem uma 6a vez dentro da tela nova:

- `rotulo_html()` - micro-rótulo maiúsculo cinza acima de um número
  (`<div class='cinza' style='font-size:0.6rem; letter-spacing:0.04em'>`
  estava literal em ui/visao_360_tab.py, 3x em ui/analises_tab.py e, com
  outro tamanho, em `.coord-metrica-rotulo`).
- `faixa_metricas_html()` - a faixa de "rótulo em cima / número embaixo"
  lado a lado (era um `display:flex; flex-wrap:wrap; gap:1.2rem` montado
  à mão em ui/visao_360_tab.py:_render_valuation, ui/analises_tab.py:
  _render_multiplos_atuais_empresa/_render_research_e_fatores/
  render_equity_research_executivo e `.coord-metricas`). Aqui vira GRADE
  (`auto-fit`), não flex solto: com grade os números alinham em coluna
  entre linhas da faixa e nada estoura a largura do painel em telas
  estreitas.
- `badge_html()` - selo de status/categoria (`.coord-badge` + as 4
  variantes de cor de ui/coordenador_tab.py, que só existiam lá).
- `tabela_html()` - tabela densa de terminal com rolagem horizontal
  própria (o wrapper `overflow-x:auto` + thead cinza existia em
  `.coord-tabela-wrap` e, de novo, em ui/analises_tab.py:_tabela_html).
- `vazio()` - estado vazio elegante ("sem cobertura disponível"), que
  antes era `st.caption` solto e se perdia visualmente no meio do texto.

Regra que continua valendo: estes helpers só EMPACOTAM `var(--*)` já
existentes - nenhuma cor nova, nenhum border-radius, nenhuma sombra. O CSS
mora em style.css (seção "DESIGN SYSTEM COMPARTILHADO"), nunca duplicado
por aba.

O tema AMBAR (config.TEMAS["AMBAR"]) já É esta identidade (preto #000000 +
âmbar #FFA028 + verde/vermelho de sinal #00D26A/#FF3B3B) e já é o tema
PADRÃO do app (config.PREFS_PADRAO["tema"]) - confirmado antes desta
mudança, nenhum valor de cor precisou mudar. Os outros temas (FOSFORO,
AZUL, CLARO) continuam existindo como opção do usuário em CONFIGURAÇÕES;
nada aqui os remove ou depende de qual deles está ativo (tudo usa `var(--*)`,
que o app.py já recalcula pra qualquer tema escolhido)."""

import html

import streamlit as st

import config


def subtitulo_html(texto: str) -> str:
    """Mesmo visual de subtitulo() (ver abaixo), em string em vez de
    st.markdown direto - para código que monta um bloco HTML grande antes
    de exibir tudo de uma vez (ex: ui/morning_call_tab.py, cujas funções
    de montagem são propositalmente puras/testáveis fora de uma sessão
    Streamlit real - ver docstring do módulo). `texto` é sempre escapado
    (mesma regra de subtitulo)."""
    return (
        f"<div style='font-size:0.72rem; font-weight:700; letter-spacing:0.03em; "
        f"margin:0.7rem 0 0.3rem 0; color:var(--neutro);'>{html.escape(texto)}</div>"
    )


def subtitulo(texto: str):
    """Subtítulo de seção compacto - mesmo tamanho de fonte usado em
    quase todo o resto do app (~0.72rem), nunca o padrão do Streamlit.
    `texto` é sempre escapado (é um rótulo curto, nunca HTML pré-formatado -
    diferente de lista_compacta, que recebe HTML de quem chama)."""
    st.markdown(subtitulo_html(texto), unsafe_allow_html=True)


def lista_compacta(linhas_html):
    """Lista com marcador, mesmo tamanho de fonte do resto do app (ver
    subtitulo) - substitui `st.markdown(f"- {texto}")` solto, que também
    herdava o tamanho padrão do Streamlit. `linhas_html`: iterável de
    strings já em HTML (quem chama decide se escapa ou não, mesma
    responsabilidade que st.markdown sempre teve)."""
    st.markdown(
        "".join(
            f"<div style='font-size:0.78rem; padding:0.12rem 0 0.12rem 0.9rem; position:relative;'>"
            f"<span style='position:absolute; left:0;'>·</span>{linha}</div>"
            for linha in linhas_html
        ),
        unsafe_allow_html=True,
    )


# === Indicador positivo/negativo (sinal) ===================================
#
# Substitui o padrão `cls = "alta" if valor >= 0 else "baixa"` +
# `sinal = "+" if valor >= 0 else ""` que se repetia, literalmente
# duplicado, em pelo menos 10 lugares do app (app.py, ui/mercado_tab.py,
# ui/macro_tab.py, ui/visao_geral.py, ui/setores_tab.py...) antes desta
# fundação. As classes `.alta`/`.baixa` em si já existiam há muito tempo em
# style.css (cor de sinal do tema ativo) - o que faltava era UM lugar para
# decidir qual das duas aplicar e formatar o número, não a cor em si.

def classe_sinal(valor: float) -> str:
    """"alta" (classe CSS, cor var(--alta)) se valor >= 0, senão "baixa".
    Mesmo critério (>=0 é alta) usado em todo o app até aqui - zero também
    é "alta" de propósito (ex: variação 0,00% nunca foi tratada como
    queda)."""
    return "alta" if valor >= 0 else "baixa"


def numero_financeiro_html(
    valor: float,
    casas: int = 2,
    formato: str = "BR",
    prefixo: str = "",
    sufixo: str = "",
    com_sinal: bool = False,
    colorir: bool = False,
) -> str:
    """Número financeiro pronto pra exibir, alinhado: `font-variant-numeric:
    tabular-nums` (dígitos de largura fixa - colunas de números não
    "dançam" entre linhas, mesmo com dígitos diferentes) + alinhamento à
    direita, dentro de um <span>. A FORMATAÇÃO do número em si (separador
    BR "1.234,56" vs US "1,234.56") continua vindo de
    `config.formatar_numero` - este helper só cuida do visual de quem já
    tem o número formatado, não duplica aquela lógica.

    `com_sinal`: prefixa "+" quando valor >= 0 (nunca mexe no "-", que o
    próprio `:,.{casas}f` do Python já gera sozinho).
    `colorir`: aplica `classe_sinal(valor)` (var(--alta)/var(--baixa)) -
    por padrão desligado, porque nem todo número financeiro é uma
    variação (ex: preço em si costuma ficar neutro, só a variação % é
    colorida)."""
    sinal = "+" if (com_sinal and valor >= 0) else ""
    texto = f"{prefixo}{sinal}{config.formatar_numero(valor, casas, formato)}{sufixo}"
    classe = f" {classe_sinal(valor)}" if colorir else ""
    return f"<span class='ds-numero{classe}'>{html.escape(texto)}</span>"


def variacao_html(valor_pct: float, formato: str = "BR", casas: int = 2) -> str:
    """Caso mais comum de `numero_financeiro_html`: uma variação percentual
    colorida e com sinal, pronta pra colar ao lado de um preço - ex:
    `f"{config.formatar_numero(preco, 2, fmt)} ({variacao_html(var_pct, fmt)})"`.
    Equivalente a `cls = "alta" if valor_pct >= 0 else "baixa"` + `sinal =
    "+" if valor_pct >= 0 else ""` que se repetia pelo app (ver docstring
    do módulo) - centraliza os dois numa função só."""
    return numero_financeiro_html(valor_pct, casas=casas, formato=formato, sufixo="%", com_sinal=True, colorir=True)


# === Divisor discreto ========================================================

def divisor_html() -> str:
    """Linha divisória fina (`var(--borda)`, 1px) entre seções dentro de um
    mesmo painel - nunca uma `<hr>` padrão do navegador (grossa, com
    margem própria do user-agent) nem uma borda pesada nova. Versão string
    de `divisor()`, para montagem de blocos HTML grandes antes de um único
    `st.markdown` (mesmo motivo de `subtitulo_html`, ver acima)."""
    return "<hr style='border:none; border-top:1px solid var(--borda); margin:0.5rem 0;' />"


def divisor():
    """Renderiza `divisor_html()` diretamente (ver docstring acima)."""
    st.markdown(divisor_html(), unsafe_allow_html=True)


# === Valor monetário / percentual já formatado =============================
#
# Promovidos de ui/coordenador_tab.py (_moeda_html/_pct_html, 2026-11-06),
# onde eram usados 40+ vezes e eram a ÚNICA implementação de "número com
# fallback honesto quando a fonte não devolveu nada" do app. A tela nova
# (ui/visao_360_tab.py) precisava dos dois - duplicar seria a 2a cópia da
# mesma regra. coordenador_tab.py continua com `_moeda_html`/`_pct_html`
# como alias destas funções (mesma assinatura, mesmo retorno) pra não
# tocar nos 40+ pontos de chamada nem nos testes que os exercitam.

def moeda_html(valor, moeda: str, casas: int = 2, fallback: str = "—", formato: str = "BR") -> str:
    """Valor monetário alinhado/mono (`numero_financeiro_html`), com
    `fallback` ESCAPADO quando o valor não é um número real - nunca um
    "0,00" fabricado pra disfarçar dado ausente. `bool` é recusado de
    propósito (True é `int` em Python; um booleano chegando aqui é sempre
    bug de quem chama, não um preço). Já devolve HTML seguro - nunca
    re-escapar o retorno.

    `formato` default "BR" preserva exatamente o comportamento do
    ex-`coordenador_tab._moeda_html` (que era sempre BR) nos 40+ pontos de
    chamada de lá; telas que têm `prefs["formato_numerico"]` em mão (ex.:
    ui/visao_360_tab.py) devem passar o formato do usuário."""
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return html.escape(fallback)
    return numero_financeiro_html(valor, casas=casas, formato=formato, prefixo=f"{moeda} ")


def pct_html(valor, casas: int = 1, fallback: str = "—", escala: float = 100.0) -> str:
    """Taxa/premissa/nível em %, alinhado/mono e SEM sinal/cor - para o
    que não é uma variação (WACC, crescimento perpétuo, ROE, margem).
    Variação de verdade (onde o sinal importa) usa `variacao_html()`; ver
    ponto 2 da docstring do módulo. `escala`: 100.0 quando o valor vem em
    fração (0,12 -> 12,0%), 1.0 quando já vem em pontos percentuais."""
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return html.escape(fallback)
    return numero_financeiro_html(valor * escala, casas=casas, formato="BR", sufixo="%")


# === Rótulo, faixa de métricas, selo, tabela, estado vazio =================

def rotulo_html(texto: str) -> str:
    """Micro-rótulo maiúsculo cinza que fica ACIMA de um número (padrão
    de terminal: o rótulo é discreto, o número é o protagonista). `texto`
    é sempre escapado (rótulo curto, nunca HTML)."""
    return f"<div class='ds-rotulo'>{html.escape(texto)}</div>"


def faixa_metricas_html(itens, *, grande: bool = False, minimo: int = 108) -> str:
    """Faixa de métricas em GRADE (rótulo em cima, número embaixo), que se
    reflui sozinha (`auto-fit`) sem nunca estourar a largura do painel.

    `itens`: iterável de `(rotulo, valor_html)` ou `(rotulo, valor_html,
    nota)`. `rotulo`/`nota` são texto plano (escapados aqui); `valor_html`
    é HTML pronto de quem chama - na prática sempre
    `numero_financeiro_html`/`variacao_html`/`moeda_html`/`pct_html` (ou
    um "—" literal), mesma divisão de responsabilidade de
    `lista_compacta`.

    `grande=True` sobe só o tamanho do NÚMERO (não do rótulo) - usado
    quando a faixa é a leitura principal do bloco (ex.: preço/preço-alvo/
    potencial), nunca pra "enfeitar" uma faixa secundária.
    `minimo`: largura mínima de cada coluna em px (um rótulo longo tipo
    "DÍV. LÍQ./EBITDA" precisa de mais que o padrão)."""
    classe_valor = "ds-metrica-valor ds-metrica-valor-g" if grande else "ds-metrica-valor"
    celulas = []
    for item in itens:
        rotulo, valor = item[0], item[1]
        nota = item[2] if len(item) > 2 else None
        nota_html = f"<div class='ds-metrica-nota'>{html.escape(str(nota))}</div>" if nota else ""
        celulas.append(
            f"<div class='ds-metrica'>{rotulo_html(str(rotulo))}"
            f"<div class='{classe_valor}'>{valor}</div>{nota_html}</div>"
        )
    if not celulas:
        return ""
    return (
        f"<div class='ds-metricas' style='grid-template-columns:repeat(auto-fit, minmax({int(minimo)}px, 1fr));'>"
        + "".join(celulas) + "</div>"
    )


# Níveis de selo = os MESMOS 4 estados semânticos que `.coord-badge` já
# usava em ui/coordenador_tab.py (ok/atenção/erro/sem base), agora
# nomeados num lugar só. Nenhuma cor nova: var(--alta)/var(--destaque)/
# var(--baixa)/var(--cinza).
NIVEL_OK = "ok"
NIVEL_ALERTA = "alerta"
NIVEL_ERRO = "erro"
NIVEL_NEUTRO = "neutro"


def badge_html(texto: str, nivel: str = NIVEL_NEUTRO) -> str:
    """Selo compacto de status/categoria (borda fina + texto na cor do
    nível, fundo transparente - nunca uma pílula preenchida/arredondada
    de SaaS). `nivel`: NIVEL_OK (var(--alta)), NIVEL_ALERTA
    (var(--destaque) - "requer atenção"), NIVEL_ERRO (var(--baixa)),
    NIVEL_NEUTRO (var(--cinza) - "sem base"/informativo)."""
    nivel = nivel if nivel in (NIVEL_OK, NIVEL_ALERTA, NIVEL_ERRO, NIVEL_NEUTRO) else NIVEL_NEUTRO
    return f"<span class='ds-badge ds-badge-{nivel}'>{html.escape(str(texto))}</span>"


def tabela_html(cabecalhos, linhas, *, min_largura: int | None = None) -> str:
    """Tabela densa de terminal com rolagem horizontal PRÓPRIA (o wrapper
    tem `overflow-x:auto`, então uma tabela larga rola dentro dela em vez
    de empurrar a página inteira - regra de responsividade do projeto:
    nenhuma tela pode ganhar scroll horizontal no body).

    `cabecalhos`: iterável de `(rotulo, alinhamento)` - alinhamento "d"
    (direita, coluna de número) ou "e" (esquerda, texto); mesma convenção
    que ui/analises_tab.py já usava. `linhas`: iterável de linhas, cada
    uma um iterável de `(html_da_celula, alinhamento)` - a célula é HTML
    pronto de quem chama (mesma regra de `faixa_metricas_html`).
    `min_largura`: px mínimos da tabela quando ela tem muitas colunas -
    força a rolagem do wrapper em vez de deixar o navegador comprimir
    coluna de texto até ficar ilegível."""
    ths = "".join(
        f"<th class='{'ds-num' if alinhamento == 'd' else ''}'>{html.escape(str(rotulo))}</th>"
        for rotulo, alinhamento in cabecalhos
    )
    trs = []
    for linha in linhas:
        tds = "".join(
            f"<td class='{'ds-num' if alinhamento == 'd' else ''}'>{celula}</td>"
            for celula, alinhamento in linha
        )
        trs.append(f"<tr>{tds}</tr>")
    estilo = f" style='min-width:{int(min_largura)}px;'" if min_largura else ""
    return (
        "<div class='ds-tabela-wrap'><table class='ds-tabela'" + estilo + ">"
        f"<thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>"
    )


def vazio_html(texto: str) -> str:
    """Estado vazio elegante: 1 linha cinza com um traço vertical fino à
    esquerda (fica claro que a seção RESPONDEU e não tem conteúdo, em vez
    de parecer um bloco que falhou em carregar). Texto sempre voltado ao
    usuário - nunca mensagem de migration/SQL/nome de coluna/exceção
    interna (regra explícita do pedido: detalhe técnico só em log)."""
    return f"<div class='ds-vazio'>{html.escape(texto)}</div>"


def vazio(texto: str):
    """Renderiza `vazio_html()` diretamente (ver docstring acima)."""
    st.markdown(vazio_html(texto), unsafe_allow_html=True)


def secao_html(titulo: str, nota: str | None = None) -> str:
    """Cabeçalho de SEÇÃO interna de um painel - um passo acima de
    `subtitulo()` na hierarquia (tem régua fina embaixo, ocupa a largura
    toda), pra separar visualmente blocos grandes dentro do mesmo painel
    sem precisar de um painel novo por bloco. `nota` é um complemento
    curto à direita do título (ex.: contagem, fonte, data-base)."""
    nota_html = f"<span class='ds-secao-nota'>{html.escape(str(nota))}</span>" if nota else ""
    return (
        f"<div class='ds-secao'><span class='ds-secao-titulo'>{html.escape(titulo)}</span>{nota_html}</div>"
    )


def secao(titulo: str, nota: str | None = None):
    """Renderiza `secao_html()` diretamente (ver docstring acima)."""
    st.markdown(secao_html(titulo, nota), unsafe_allow_html=True)


def painel_titulo_html(titulo: str, nota: str | None = None) -> str:
    """Barra de título de um painel (`.painel-titulo`, âmbar/maiúsculo,
    régua embaixo, sangrando até a borda do container) - o padrão de
    cabeçalho de painel do app desde sempre, aqui só centralizado em UM
    lugar (era `st.markdown('<div class="painel-titulo">...')` literal em
    ~40 pontos de ui/*.py). `nota`: complemento cinza à direita, no mesmo
    baseline (ex.: "atualizado às 18:02")."""
    nota_html = (
        f"<span style='float:right; font-weight:400; letter-spacing:0.02em; "
        f"text-transform:none; color:var(--cinza);'>{html.escape(str(nota))}</span>"
        if nota else ""
    )
    return f'<div class="painel-titulo">{html.escape(titulo)}{nota_html}</div>'


def painel_titulo(titulo: str, nota: str | None = None):
    """Renderiza `painel_titulo_html()` diretamente (ver docstring)."""
    st.markdown(painel_titulo_html(titulo, nota), unsafe_allow_html=True)
