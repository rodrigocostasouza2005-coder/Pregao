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
