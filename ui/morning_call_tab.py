# -*- coding: utf-8 -*-
"""Area MORNING CALL do PREGAO 2.0 (ui/navegacao.py). Ate aqui o Morning
Call so' existia como e-mail/PDF do job agendado (jobs/morning_call.py) +
o toggle de inscricao em CONFIG - esta area da' acesso a ele no app.

NUNCA envia e-mail e nunca grava em morning_call_execucoes: le o
historico do proprio job (data/morning_call_historico.py) e, so' quando
o usuario pede (botao), monta uma previa/PDF com as MESMAS funcoes do
job (montar_edicao/gerar_pdf), sem enviar_email.

Reconstrucao de UX (22/10/2026): a aba virava uma sequencia de caixas
pretas com borda (cada secao E cada item numa div com border+background
proprios, aninhadas dentro do container com borda do proprio painel) e
usava a fonte monoespacada do app inteiro (style.css: html/body/[class*=
css] em IBM Plex Mono !important) ate' em paragrafo de prosa - visual de
log tecnico, nao de jornal. Duas mudancas:

1. _bloco_editorial_html (texto persistido, unica fonte do que foi
   REALMENTE enviado) ganhou tipografia editorial propria (serifada pra
   manchete/prosa, mono so' pra numero/ticker/metadado - ver _estilo_mc)
   e perdeu a caixa dupla (secao com borda + item com borda dentro dela):
   agora e' lista plana com regua fina entre itens, e linhas de cotacao
   ("Ibovespa: 148.320,50; variacao...; referencia...", unico formato
   gerado por jobs/morning_call.py:_obter_cotacao_fmt/_macro_rows) viram
   cards de indicador em vez de mais um bullet de texto.
2. A previa "com os dados de agora" passou a consumir o MESMO dict
   estruturado que jobs/morning_call_pdf.py usa pra gerar o PDF
   (data/morning_call_editorial.montar_edicao) em vez do texto plano do
   e-mail (jobs/morning_call.py:montar_morning_call) - ganha card de
   mercado, card de noticia com imagem/categoria e agenda tabular de
   verdade, sem precisar reimplementar a coleta/selecao editorial (so'
   uma camada de apresentacao nova, como jobs/morning_call_pdf.py e' pro
   ReportLab). A edicao JA PUBLICADA (persistida em
   morning_call_execucoes) so' guarda o texto simples do e-mail - sem
   dict estruturado no banco, ela continua pelo caminho 1."""

import html
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

import streamlit as st

from data.morning_call_briefing import alertas_confiabilidade, tickers_novos
from data.morning_call_historico import listar_edicoes
from data.sintese_mercado import obter_sintese_mercado

TZ_SP = ZoneInfo("America/Sao_Paulo")
_URL = re.compile(r"https?://[^\s<>\"')]+")

# Mesma identidade tipografica do PDF/e-mail editorial (PR #62: serifada
# pra manchete/prosa, sans humanista pro corpo curto, mono - ja' herdada
# do resto do app - reservada a numero/ticker/metadado). Pilha web-safe
# (nao a fonte embutida do PDF, que nao existe fora dele - mesmo
# raciocinio de jobs/morning_call.py:_SERIF/_SANS, duplicada aqui de
# proposito: aquele modulo monta e-mail/texto, nao deve importar nada de
# Streamlit, e este nao deve importar o job inteiro (pesado, toca rede)
# so' por 2 constantes de string).
_SERIF = "Georgia,'Source Serif 4','Times New Roman',Times,serif"
_SANS = "'Libre Franklin','Segoe UI',Arial,Helvetica,sans-serif"


def texto_para_html(texto: str) -> str:
    """Texto do Morning Call -> HTML seguro: escapa tudo e so' depois
    transforma URL em link (links verificaveis, abrem em nova aba)."""
    escapado = html.escape(texto or "")
    return _URL.sub(lambda m: f"<a href='{m.group(0)}' target='_blank' rel='noopener'>{m.group(0)}</a>", escapado)


def _estilo_mc() -> str:
    """<style> compartilhado pelas duas camadas de renderizacao (texto
    persistido e dict estruturado) - um unico lugar pra tipografia/cores,
    nunca duplicado em inline style por elemento. Repetido a cada chamada
    de proposito (CSS identico redeclarado e' inofensivo pro navegador) -
    mantem _bloco_editorial_html/render_edicao_estruturada_html PURAS
    (sem estado de "ja' injetei o estilo", testaveis fora de uma sessao
    Streamlit de verdade - ver tests/test_morning_call_tab_ui.py)."""
    return (
        "<style>"
        ".mc-wrap{font-size:.86rem;max-width:100%;overflow-wrap:anywhere;}"
        ".mc-cabecalho{font-family:" + _SANS + ";color:var(--cinza);font-size:.72rem;line-height:1.5;margin:0 0 6px;}"
        ".mc-aviso{color:var(--destaque);font-family:" + _SANS + ";font-size:.74rem;"
        "line-height:1.5;padding:4px 0;}"
        # status da edição (cabeçalho): pílula, não mais uma palavra solta -
        # cor vem das MESMAS classes alta/baixa do resto do app (nunca uma
        # cor nova so' pra isto)
        ".mc-status-pill{display:inline-block;padding:1px 7px;border-radius:3px;"
        "font-family:'IBM Plex Mono',monospace;font-size:.62rem;font-weight:700;letter-spacing:.05em;}"
        ".mc-status-pill.alta{background:color-mix(in srgb, var(--alta) 18%, transparent);}"
        ".mc-status-pill.baixa{background:color-mix(in srgb, var(--baixa) 18%, transparent);}"
        ".mc-secao{margin:16px 0 0;min-width:0;}"
        ".mc-secao:first-child{margin-top:0;}"
        ".mc-secao-titulo{color:var(--destaque);font-family:'IBM Plex Mono',monospace;font-weight:700;"
        "font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;padding-bottom:4px;"
        "margin-bottom:8px;border-bottom:1px solid var(--borda);}"
        ".mc-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));"
        "gap:14px;align-items:start;}"
        # indicadores de mercado: pilula compacta, nunca mais um bullet de texto
        ".mc-indicadores{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;}"
        ".mc-indicador{flex:1 1 150px;min-width:132px;border-left:2px solid var(--borda);"
        "padding:4px 9px;background:color-mix(in srgb, var(--painel-bg) 80%, transparent);}"
        ".mc-indicador-nome{color:var(--cinza);font-size:.6rem;letter-spacing:.04em;"
        "text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
        ".mc-indicador-valor{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:.86rem;"
        "font-variant-numeric:tabular-nums;white-space:nowrap;}"
        ".mc-indicador-ref{color:var(--cinza);font-size:.6rem;margin-top:1px;overflow-wrap:anywhere;}"
        # manchete/chamadas da capa
        ".mc-manchete .mc-noticia-titulo{font-size:1.15rem;}"
        ".mc-chamadas{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 0;}"
        ".mc-chamada{font-family:" + _SERIF + ";font-weight:700;font-size:.86rem;line-height:1.3;"
        "color:var(--neutro);text-decoration:none;flex:1 1 220px;min-width:0;}"
        ".mc-chamada:hover{color:var(--destaque);}"
        # notícia: linha plana com regua fina, SEM caixa/fundo proprio
        ".mc-lista-noticias{display:flex;flex-direction:column;}"
        # .mc-noticia (texto persistido: chip+título+meta num fluxo só, SEM
        # imagem) fica em bloco normal - BUG real corrigido (22/10/2026,
        # Playwright 390px): como filho DIRETO de um flex container, o chip
        # (sem flex-shrink:0 nem white-space:nowrap) encolhia abaixo do seu
        # conteúdo e a palavra "TRADUZIDO" quebrava letra por letra na
        # coluna estreita do celular. .mc-card-noticia (renderer estruturado,
        # PODE ter imagem) continua flex (imagem ao lado do corpo).
        ".mc-noticia{padding:8px 0;min-width:0;"
        "border-bottom:1px solid color-mix(in srgb, var(--borda) 55%, transparent);}"
        ".mc-card-noticia{display:flex;gap:10px;padding:8px 0;min-width:0;"
        "border-bottom:1px solid color-mix(in srgb, var(--borda) 55%, transparent);}"
        ".mc-lista-noticias .mc-card-noticia:last-child,.mc-noticia:last-child{border-bottom:none;}"
        ".mc-card-noticia-corpo{min-width:0;flex:1 1 auto;}"
        ".mc-noticia-img{width:84px;height:84px;object-fit:cover;flex:0 0 auto;"
        "border:1px solid var(--borda);}"
        ".mc-noticia-titulo{font-family:" + _SERIF + ";font-weight:700;font-size:.95rem;line-height:1.35;"
        "text-decoration:none;color:var(--neutro);display:inline;}"
        ".mc-noticia-titulo:hover{color:var(--destaque);}"
        ".mc-noticia-meta{color:var(--cinza);font-size:.66rem;margin-top:2px;letter-spacing:.02em;}"
        ".mc-noticia-original{color:var(--cinza);font-size:.7rem;margin-top:2px;font-style:italic;}"
        ".mc-chip{display:inline-block;border:1px solid var(--borda);border-radius:3px;padding:0 5px;"
        "margin-right:6px;font-size:.6rem;letter-spacing:.04em;color:var(--neutro);white-space:nowrap;"
        "font-family:'IBM Plex Mono',monospace;vertical-align:middle;flex-shrink:0;}"
        ".mc-chip-interp{border-color:var(--destaque);color:var(--destaque);}"
        # linha plana generica (interpretacao/limitacoes/fontes/texto sem link)
        ".mc-linha{display:flex;gap:8px;align-items:baseline;padding:5px 0;min-width:0;"
        "border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-linha:last-child{border-bottom:none;}"
        ".mc-marca{color:var(--destaque);font-weight:700;flex:0 0 auto;}"
        ".mc-prosa-inline{min-width:0;overflow-wrap:anywhere;}"
        ".mc-prosa,.mc-prosa-inline{font-family:" + _SANS + ";line-height:1.6;color:var(--neutro);}"
        ".mc-prosa{margin:0 0 .6rem;}"
        # agenda
        ".mc-agenda-grupo-titulo{color:var(--cinza);font-size:.66rem;text-transform:uppercase;"
        "letter-spacing:.06em;margin:10px 0 4px;}"
        ".mc-agenda-grupo-titulo:first-child{margin-top:0;}"
        ".mc-agenda-linha{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;padding:5px 0;"
        "font-family:'IBM Plex Mono',monospace;font-size:.72rem;"
        "border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-agenda-linha:last-child{border-bottom:none;}"
        ".mc-agenda-data{color:var(--destaque);flex:0 0 auto;}"
        ".mc-agenda-empresa{color:var(--neutro);flex:1 1 160px;min-width:0;overflow-wrap:anywhere;}"
        ".mc-agenda-tipo{color:var(--cinza);flex:1 1 120px;min-width:0;overflow-wrap:anywhere;}"
        ".mc-agenda-horario{color:var(--cinza);flex:0 0 auto;}"
        # teses de research (casa/ativo/tese/data/fonte - secao propria,
        # separada de noticia geral e de catalisador/risco)
        ".mc-tese{padding:8px 0;border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-tese:last-child{border-bottom:none;}"
        ".mc-tese-topo{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:3px;}"
        ".mc-tese-ticker{font-family:'IBM Plex Mono',monospace;font-weight:700;color:var(--destaque);"
        "font-size:.76rem;}"
        ".mc-tese-data{color:var(--cinza);font-size:.66rem;margin-left:auto;white-space:nowrap;}"
        ".mc-tese-categoria{color:var(--cinza);font-size:.66rem;letter-spacing:.02em;margin-bottom:3px;}"
        ".mc-tese-corpo{font-family:" + _SANS + ";line-height:1.5;color:var(--neutro);font-size:.82rem;}"
        ".mc-tese-fonte{font-size:.68rem;margin-top:3px;}"
        ".mc-tese-fonte a{color:var(--cinza);text-decoration:none;}"
        ".mc-tese-fonte a:hover{color:var(--destaque);}"
        # radar setorial
        ".mc-radar-bloco{padding:8px 0;border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-radar-bloco:last-child{border-bottom:none;}"
        ".mc-radar-nome{color:var(--destaque);font-family:'IBM Plex Mono',monospace;font-weight:700;"
        "font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px;}"
        # resumo executivo (ANALISTA DE MERCADO, data/sintese_mercado.py) -
        # bloco A do briefing, topo da edição
        ".mc-resumo{margin-bottom:4px;}"
        ".mc-resumo-meta{color:var(--cinza);font-size:.66rem;margin-bottom:6px;}"
        ".mc-resumo-anterior{color:var(--destaque);font-size:.7rem;font-weight:600;margin-bottom:6px;}"
        # faixa compacta de alertas (bloco G) - nunca uma caixa grande,
        # só uma linha de atenção acima do conteúdo detalhado
        ".mc-alertas-faixa{display:flex;flex-direction:column;gap:3px;margin-bottom:10px;"
        "padding:6px 9px;border-left:2px solid var(--destaque);"
        "background:color-mix(in srgb, var(--painel-bg) 80%, transparent);font-size:.72rem;}"
        ".mc-alertas-faixa-item{color:var(--neutro);}"
        ".mc-alertas-faixa-item .mc-marca{color:var(--destaque);margin-right:4px;}"
        # radar de ações (oportunidades/riscos + movimentos, data/
        # sintese_mercado.py) - bloco C do briefing; mesma "forma" de
        # .mc-tese (topo com chips + corpo + fonte) pra consistência
        # visual com teses de research, mas classe própria (semântica
        # diferente: leitura do sistema, não recomendação de casa)
        ".mc-oportunidade{padding:8px 0;border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-oportunidade:last-child{border-bottom:none;}"
        ".mc-oportunidade-topo{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:3px;}"
        ".mc-oportunidade-ativo{font-family:'IBM Plex Mono',monospace;font-weight:700;color:var(--destaque);"
        "font-size:.78rem;}"
        ".mc-oportunidade-corpo{font-family:" + _SANS + ";line-height:1.5;color:var(--neutro);font-size:.82rem;}"
        ".mc-oportunidade-linha{font-size:.76rem;margin-top:2px;}"
        ".mc-oportunidade-fonte{color:var(--cinza);font-size:.66rem;margin-top:3px;}"
        # cenários (bull/base/bear qualitativo, data/sintese_mercado.py) -
        # bloco F
        ".mc-cenario{padding:8px 0;border-bottom:1px solid color-mix(in srgb, var(--borda) 40%, transparent);}"
        ".mc-cenario:last-child{border-bottom:none;}"
        ".mc-cenario-rotulo{font-size:.64rem;font-weight:700;letter-spacing:.03em;margin-bottom:2px;}"
        ".mc-cenario-texto{font-family:" + _SANS + ";font-weight:600;font-size:.84rem;color:var(--neutro);}"
        ".mc-cenario-linha{font-size:.76rem;margin-top:2px;color:var(--neutro);}"
        "</style>"
    )


_LINHA_NOTICIA = re.compile(r"^(?P<titulo>.+?) — (?P<link>https?://\S+)$")
_MARCA_EN = " [em inglês - tradução indisponível nesta edição]"
_ORIGINAL = re.compile(r"^(?P<pt>.+) \(original: (?P<en>.+)\)$")

# Linhas de cotacao geradas por jobs/morning_call.py:_obter_cotacao_fmt -
# unico lugar que produz esse formato (Ibovespa/Dolar/S&P/Nasdaq/Ouro/
# Petroleo), por isso seguro detectar por regex sem recalcular nada.
_RE_INDICADOR = re.compile(
    r"^(?P<nome>.+?): (?P<valor>[\d.,]+); variação sobre o fechamento anterior: "
    r"(?P<var>-?[\d.,]+)%; referência: (?P<ref>[^\[]+?)"
    r"(?:\s*\[último valor válido - (?P<cache>[^\]]+)\])?$"
)
_RE_INDICADOR_ERRO = re.compile(r"^(?P<nome>.+?): indisponível nesta edição \(a fonte não respondeu\)$")
# Linhas macro geradas por jobs/morning_call.py:_macro_rows (Selic/CDI/Focus)
_RE_MACRO = re.compile(
    r"^(?P<nome>.+?) \((?P<ref>[^()]+)\): (?P<valor>[\d.,]+)(?P<unidade>% a\.a\.|%)"
    r"(?: — (?P<detalhe>.+))?$"
)
_RE_MACRO_ERRO = re.compile(r"^(?P<nome>.+?): indisponível \((?P<motivo>.+)\)$")


def _indicador_da_linha(item: str) -> str | None:
    """Card de indicador (pilula) se `item` for uma linha de cotacao/macro
    reconhecida; None caso contrario (segue pro tratamento generico)."""
    m = _RE_INDICADOR.match(item)
    if m:
        var_num = m.group("var").replace(".", "").replace(",", ".")
        try:
            variacao = float(var_num)
        except ValueError:
            variacao = 0.0
        classe = "alta" if variacao > 0 else "baixa" if variacao < 0 else "cinza"
        cache = f" <span class='cinza'>({html.escape(m.group('cache'))})</span>" if m.group("cache") else ""
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(m.group('nome'))}</div>"
            f"<div class='mc-indicador-valor'>{html.escape(m.group('valor'))} "
            f"<span class='{classe}'>{html.escape(m.group('var'))}%</span></div>"
            f"<div class='mc-indicador-ref'>{html.escape(m.group('ref').strip())}{cache}</div>"
            "</div>"
        )
    m = _RE_INDICADOR_ERRO.match(item)
    if m:
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(m.group('nome'))}</div>"
            "<div class='mc-indicador-valor cinza'>indisponível</div>"
            "<div class='mc-indicador-ref'>a fonte não respondeu nesta execução</div></div>"
        )
    m = _RE_MACRO.match(item)
    if m:
        detalhe = f" · {html.escape(m.group('detalhe'))}" if m.group("detalhe") else ""
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(m.group('nome'))}</div>"
            f"<div class='mc-indicador-valor'>{html.escape(m.group('valor'))}{html.escape(m.group('unidade'))}</div>"
            f"<div class='mc-indicador-ref'>{html.escape(m.group('ref'))}{detalhe}</div></div>"
        )
    m = _RE_MACRO_ERRO.match(item)
    if m:
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(m.group('nome'))}</div>"
            "<div class='mc-indicador-valor cinza'>indisponível</div>"
            f"<div class='mc-indicador-ref'>{html.escape(m.group('motivo'))}</div></div>"
        )
    return None


def _item_noticia_html(item: str) -> str | None:
    """Linha de notícia do e-mail ("Manchete — https://...") como manchete
    clicável + domínio do veículo, em vez da URL crua. Manchete traduzida
    leva o original logo abaixo; manchete em inglês sem tradução leva a
    marca EN. None se a linha não for de notícia (fica como texto)."""
    from urllib.parse import urlparse

    m = _LINHA_NOTICIA.match(item)
    if not m:
        return None
    titulo, link = m.group("titulo"), m.group("link")
    chip, original = "", ""
    if titulo.endswith(_MARCA_EN):
        titulo = titulo[: -len(_MARCA_EN)]
        chip = "<span class='mc-chip'>EN · SEM TRADUÇÃO</span>"
    else:
        mo = _ORIGINAL.match(titulo)
        if mo:
            titulo = mo.group("pt")
            chip = "<span class='mc-chip'>TRADUZIDO</span>"
            original = f"<div class='mc-noticia-original'>original: {html.escape(mo.group('en'))}</div>"
    dominio = urlparse(link).netloc.replace("www.", "")
    return (
        f"{chip}<a href='{html.escape(link, quote=True)}' target='_blank' rel='noopener' "
        f"class='mc-noticia-titulo'>{html.escape(titulo)}</a>"
        f" <span class='mc-noticia-meta' style='display:inline'>{html.escape(dominio)} ↗</span>"
        + original
    )


def _bloco_editorial_html(texto: str) -> str:
    """Formata o briefing de texto em secoes legiveis sem alterar seu
    conteudo: indicadores de mercado viram cards compactos, noticias viram
    manchete clicavel + veiculo, e tudo o mais vira uma lista plana (regua
    fina entre linhas) - nunca mais uma caixa com borda dentro de outra
    caixa com borda. Secoes em grade de 2 colunas no desktop (1 no
    celular)."""
    secoes = []
    titulo_secao = None  # linhas antes da 1ª seção = cabeçalho da edição
    linhas_secao = []
    cabecalho = []

    def fechar_secao():
        nonlocal titulo_secao, linhas_secao
        if titulo_secao is None:
            cabecalho.extend(l.strip() for l in linhas_secao if l.strip())
            linhas_secao = []
            return
        itens = []
        indicadores = []
        paragrafo = []

        def fechar_paragrafo():
            if paragrafo:
                conteudo = " ".join(paragrafo)
                itens.append(f"<p class='mc-prosa'>{texto_para_html(conteudo)}</p>")
                paragrafo.clear()

        for linha in linhas_secao:
            limpa = linha.strip()
            if not limpa:
                fechar_paragrafo()
                continue
            if limpa.startswith("- "):
                fechar_paragrafo()
                item = limpa[2:].strip()
                tag = ""
                m = re.match(r"^\[(INTERPRETAÇÃO|INTERPRETACAO)\]\s*", item, re.I)
                if m:
                    tag = "<span class='mc-chip mc-chip-interp'>INTERPRETAÇÃO</span>"
                    item = item[m.end():]
                indicador = _indicador_da_linha(item) if not tag else None
                if indicador:
                    indicadores.append(indicador)
                    continue
                corpo = _item_noticia_html(item)
                if corpo:
                    itens.append(f"<div class='mc-noticia'>{tag}{corpo}</div>")
                else:
                    itens.append(
                        "<div class='mc-linha'><span class='mc-marca'>›</span>"
                        f"<span class='mc-prosa-inline'>{tag}{texto_para_html(item)}</span></div>"
                    )
            else:
                paragrafo.append(limpa)
        fechar_paragrafo()
        if itens or indicadores:
            secoes.append(
                "<div class='mc-secao'>"
                f"<div class='mc-secao-titulo'>{html.escape(titulo_secao)}</div>"
                + (f"<div class='mc-indicadores'>{''.join(indicadores)}</div>" if indicadores else "")
                + "".join(itens) + "</div>"
            )
        linhas_secao = []

    for linha in (texto or "").splitlines():
        limpa = linha.strip()
        eh_titulo = bool(
            re.match(r"^\d+\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9 &/—–():,-]{3,}$", limpa)
            or limpa in {"FONTES", "LIMITAÇÕES", "LIMITACOES"}
        )
        if eh_titulo:
            fechar_secao()
            titulo_secao = limpa
        else:
            linhas_secao.append(linha)
    fechar_secao()
    topo = ""
    if cabecalho:
        # 1ª linha é "MORNING CALL — dd/mm/aaaa", já dita no cabeçalho da aba
        resto = cabecalho[1:] if cabecalho[0].upper().startswith("MORNING CALL") else cabecalho
        topo = "".join(f"<div class='mc-cabecalho'>{texto_para_html(l)}</div>" for l in resto)
    return (
        _estilo_mc() + "<div class='mc-wrap'>" + topo
        + "<div class='mc-grade'>" + "".join(secoes) + "</div></div>"
    )


def _exibir_texto(texto: str):
    st.markdown(_bloco_editorial_html(texto), unsafe_allow_html=True)


# --- Previa estruturada: mesmo dict que jobs/morning_call_pdf.py usa -----

def _fmt_num_br(valor, casas=2) -> str:
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def _classe_variacao(valor) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "cinza"
    return "alta" if v > 0 else "baixa" if v < 0 else "cinza"


def _url_http_segura(url) -> str | None:
    """So' aceita URL absoluta http(s) pra virar href/src - mesmo critério
    de data/news.py:_url_imagem_valida (reaproveitado em espírito, não em
    código: aquele é só pra imagem e já roda na coleta). Defesa em
    profundidade na CAMADA DE APRESENTAÇÃO: o `link`/`imagem` do dict
    estruturado (data/morning_call_editorial.py:_item_fato) não passa por
    nenhum gate de esquema até chegar aqui - diferente do caminho em texto
    (_item_noticia_html), que só casa link por já exigir "https?://" no
    próprio regex. Sem este filtro, um link não-http(s) (ex: "javascript:
    ...") numa fonte comprometida viraria um href clicável de verdade -
    html.escape() escapa aspas/caracteres especiais, mas não o ESQUEMA da
    URL."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    return url if url.startswith("http://") or url.startswith("https://") else None


def _card_indicador_estruturado(ind: dict) -> str:
    """Mesmo card de _indicador_da_linha, a partir do dict estruturado
    (data/morning_call_editorial.py: _indicador ou _linha_macro) - sem
    regex, os campos já vêm nomeados."""
    nome = ind.get("nome") or ind.get("indicador") or "—"
    if "preco" in ind:  # cotação (índice/câmbio/commodity)
        if ind.get("erro"):
            return (
                "<div class='mc-indicador'>"
                f"<div class='mc-indicador-nome'>{html.escape(str(nome))}</div>"
                "<div class='mc-indicador-valor cinza'>indisponível</div>"
                f"<div class='mc-indicador-ref'>{html.escape(str(ind['erro']))}</div></div>"
            )
        var = ind.get("variacao_pct")
        classe = _classe_variacao(var)
        var_fmt = _fmt_num_br(var) if var is not None else None
        var_html = f"<span class='{classe}'>{'+' if (var or 0) > 0 else ''}{var_fmt}%</span>" if var_fmt else ""
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(str(nome))}</div>"
            f"<div class='mc-indicador-valor'>{_fmt_num_br(ind.get('preco'))} {var_html}</div>"
            f"<div class='mc-indicador-ref'>{html.escape(ind.get('barra_fmt') or '—')}</div></div>"
        )
    if ind.get("erro"):
        return (
            "<div class='mc-indicador'>"
            f"<div class='mc-indicador-nome'>{html.escape(str(nome))}</div>"
            "<div class='mc-indicador-valor cinza'>indisponível</div>"
            f"<div class='mc-indicador-ref'>{html.escape(str(ind['erro']))}</div></div>"
        )
    detalhe = f" · {html.escape(str(ind['detalhe']))}" if ind.get("detalhe") else ""
    return (
        "<div class='mc-indicador'>"
        f"<div class='mc-indicador-nome'>{html.escape(str(nome))}</div>"
        f"<div class='mc-indicador-valor'>{_fmt_num_br(ind.get('valor'))}{html.escape(str(ind.get('unidade') or ''))}</div>"
        f"<div class='mc-indicador-ref'>{html.escape(ind.get('referencia') or '—')}{detalhe}</div></div>"
    )


def _card_noticia_estruturada(fato: dict) -> str:
    """Card de notícia a partir do fato (data/morning_call_editorial.py:
    _item_fato) - título clicável, veículo, chip de tradução, imagem
    quando disponível (nunca uma imagem genérica no lugar) e até 2
    parágrafos do resumo já cacheado."""
    titulo = str(fato.get("titulo") or "(sem título)").strip()
    link = _url_http_segura(fato.get("link"))
    veiculo = fato.get("veiculo")
    corpo = fato.get("corpo") or []
    imagem = _url_http_segura(fato.get("imagem"))
    chip, original = "", ""
    if fato.get("titulo_original"):
        chip = "<span class='mc-chip'>TRADUZIDO</span>"
        original = f"<div class='mc-noticia-original'>original: {html.escape(str(fato['titulo_original']))}</div>"
    elif fato.get("sem_traducao"):
        chip = "<span class='mc-chip'>EN · SEM TRADUÇÃO</span>"
    titulo_html = (
        f"<a href='{html.escape(link, quote=True)}' target='_blank' rel='noopener' "
        f"class='mc-noticia-titulo'>{html.escape(titulo)}</a>"
        if link else f"<span class='mc-noticia-titulo'>{html.escape(titulo)}</span>"
    )
    meta = html.escape(str(veiculo)) if veiculo else ""
    img_html = f"<img src='{html.escape(imagem, quote=True)}' class='mc-noticia-img' alt=''>" if imagem else ""
    corpo_html = "".join(f"<p class='mc-prosa'>{texto_para_html(p)}</p>" for p in corpo[:2])
    return (
        "<div class='mc-card-noticia'>" + img_html
        + "<div class='mc-card-noticia-corpo'>" + chip + titulo_html
        + (f"<div class='mc-noticia-meta'>{meta}</div>" if meta else "")
        + original + corpo_html + "</div></div>"
    )


def _card_tese_research(m: dict) -> str:
    """Tese/recomendação de research (data/market_makers.py:mudancas_tese,
    fachada sobre data/radar.py:_mudancas_research/_mudancas_cvm) - casa,
    ativo, tese resumida, data e fonte, sempre explícitos. Nunca fabrica
    casa/preço-alvo/conclusão que a fonte não deu: sem fonte_label, o chip
    diz isso em vez de inventar um nome."""
    casa = m.get("fonte_label")
    fonte_url = _url_http_segura(m.get("fonte_url"))
    if fonte_url:
        fonte_html = (f"<a href='{html.escape(fonte_url, quote=True)}' target='_blank' rel='noopener'>"
                      f"{html.escape(casa or 'fonte')} ↗</a>")
    elif casa:
        fonte_html = html.escape(casa)
    else:
        fonte_html = "fonte não identificada nesta execução"
    return (
        "<div class='mc-tese'>"
        "<div class='mc-tese-topo'>"
        f"<span class='mc-chip mc-chip-interp'>{html.escape(casa) if casa else 'CASA NÃO IDENTIFICADA'}</span>"
        f"<span class='mc-tese-ticker'>{html.escape(m['ticker'])}</span>"
        f"<span class='mc-tese-data'>{m['data_evento'].strftime('%d/%m/%Y')}</span>"
        "</div>"
        f"<div class='mc-tese-categoria'>{html.escape(m.get('categoria') or '')}</div>"
        f"<div class='mc-tese-corpo'>{texto_para_html(m['descricao'])}</div>"
        f"<div class='mc-tese-fonte'>{fonte_html}</div>"
        "</div>"
    )


def _linha_agenda_estruturada(evento: dict) -> str:
    """Linha de agenda a partir do dict (data/morning_call_editorial.py:
    _linha_evento) - data/status/horário já vêm prontos, sem inferir nada
    que a fonte não confirmou."""
    status = evento.get("status_rotulo") or "status desconhecido"
    data_fmt = evento["data"].strftime("%d/%m") if evento.get("data") else "—"
    periodo = f" · {html.escape(str(evento['periodo']))}" if evento.get("periodo") else ""
    nota = html.escape(str(evento.get("status_nota") or ""))
    return (
        "<div class='mc-agenda-linha'>"
        f"<span class='mc-agenda-data'>{data_fmt}</span>"
        f"<span class='mc-agenda-empresa'>{html.escape(str(evento.get('empresa') or '—'))} "
        f"<span class='cinza'>({html.escape(str(evento.get('ticker') or '?'))})</span></span>"
        f"<span class='mc-agenda-tipo'>{html.escape(str(evento.get('tipo_evento') or 'EVENTO'))}{periodo}</span>"
        f"<span class='mc-agenda-horario'>{html.escape(str(evento.get('horario') or 'sem horário divulgado'))}</span>"
        f"<span class='mc-chip' title='{nota}'>{html.escape(str(status))}</span>"
        "</div>"
    )


def _bloco_resumo_executivo_html(sintese: dict) -> str:
    """Bloco A do briefing (RESUMO EXECUTIVO) - data/sintese_mercado.py,
    mesmo motor de IA já usado pela VISÃO GERAL, nenhuma chamada nova.
    Distingue FATO coletado de LEITURA (ressalvas/o_que_nao_sabemos é a
    lacuna, nunca preenchida com algo genérico)."""
    if not sintese.get("ok"):
        return (
            "<div class='mc-secao'><div class='mc-secao-titulo'>RESUMO EXECUTIVO</div>"
            "<div class='mc-aviso'>Análise indisponível nesta execução.</div></div>"
        )
    dados = sintese["dados"]
    resumo = dados["resumo_executivo"]
    partes = ["<div class='mc-secao'><div class='mc-secao-titulo'>RESUMO EXECUTIVO</div><div class='mc-resumo'>"]
    if not sintese.get("atual"):
        partes.append(
            "<div class='mc-resumo-anterior'>ANÁLISE ANTERIOR - a rodada atual não pôde ser gerada"
            + (f" ({html.escape(str(sintese['motivo_atual_indisponivel']))})" if sintese.get("motivo_atual_indisponivel") else "")
            + "</div>"
        )
    partes.append(f"<div class='mc-prosa-inline'>{texto_para_html(resumo['texto'])}</div>")
    if resumo.get("ressalvas"):
        partes.append(f"<div class='mc-noticia-meta' style='margin-top:4px;'>Ressalvas: {texto_para_html(resumo['ressalvas'])}</div>")
    nao_sabemos = dados.get("o_que_nao_sabemos") or []
    if nao_sabemos:
        partes.append(
            "<div class='mc-noticia-meta' style='margin-top:4px;'>O que ainda não sabemos: "
            + texto_para_html("; ".join(nao_sabemos)) + "</div>"
        )
    partes.append("</div></div>")
    return "".join(partes)


def _bloco_alertas_html(alertas_saude: list, novidades: list) -> str:
    """Bloco G do briefing (ALERTAS E ATUALIZAÇÕES) - faixa compacta,
    nunca uma caixa grande nem um 2º sistema de monitoramento: lê o
    painel SAÚDE DOS DADOS já existente (data/saude_dados.py) e compara
    texto simples com a última edição publicada (data/
    morning_call_briefing.py). [] nas duas listas -> sem seção (nada a
    avisar, não é omissão silenciosa de erro)."""
    if not alertas_saude and not novidades:
        return ""
    itens = []
    for a in alertas_saude:
        itens.append(
            f"<div class='mc-alertas-faixa-item'><span class='mc-marca'>›</span>"
            f"{html.escape(str(a.get('nome') or ''))} — {html.escape(str(a.get('rotulo_estado') or ''))}</div>"
        )
    if novidades:
        itens.append(
            "<div class='mc-alertas-faixa-item'><span class='mc-marca'>›</span>"
            "Novos no radar desde a última edição enviada: "
            + html.escape(", ".join(novidades)) + "</div>"
        )
    return "<div class='mc-alertas-faixa'>" + "".join(itens) + "</div>"


def _bloco_radar_acoes_html(sintese: dict) -> str:
    """Bloco C do briefing (RADAR DE AÇÕES E OPORTUNIDADES DE
    INVESTIGAÇÃO) - data/sintese_mercado.py: 'movimentos' (o que está
    movendo o mercado) + 'oportunidades_riscos' ('para investigar').
    Chip INTERPRETAÇÃO (já usado em outras partes da aba) marca que é
    LEITURA DO SISTEMA sobre os fatos coletados - nunca recomendação de
    compra/venda nem confundida com recomendação de casa (essa vive só
    na seção TESES E RECOMENDAÇÕES DE RESEARCH, abaixo)."""
    if not sintese.get("ok"):
        return ""
    dados = sintese["dados"]
    movimentos = dados.get("movimentos") or []
    oportunidades = dados.get("oportunidades_riscos") or []
    if not movimentos and not oportunidades:
        return ""
    partes = ["<div class='mc-secao'><div class='mc-secao-titulo'>RADAR DE AÇÕES E OPORTUNIDADES DE INVESTIGAÇÃO</div>"]
    partes.append(
        "<p class='mc-aviso' style='margin-bottom:8px;'>Leitura do sistema sobre os fatos já coletados nesta "
        "edição - nunca uma recomendação de compra/venda. Recomendações com atribuição de casa estão na seção "
        "TESES E RECOMENDAÇÕES DE RESEARCH.</p>"
    )
    for m in movimentos:
        fonte = m.get("fonte") or "fonte não informada"
        data_fonte = f" · {html.escape(str(m['data_fonte']))}" if m.get("data_fonte") else ""
        partes.append(
            "<div class='mc-oportunidade'><div class='mc-oportunidade-topo'>"
            "<span class='mc-chip mc-chip-interp'>INTERPRETAÇÃO</span>"
            f"<span class='mc-oportunidade-ativo'>{html.escape(str(m.get('evento') or ''))}</span>"
            f"<span class='mc-tese-data'>{html.escape(str(fonte))}{data_fonte} · confiança {html.escape(str(m.get('confianca') or '—'))}</span>"
            "</div>"
            f"<div class='mc-oportunidade-corpo'>{texto_para_html(m.get('por_que_importa') or '')}</div>"
            + (f"<div class='mc-oportunidade-linha'>Possível impacto: {texto_para_html(m['impacto_possivel'])}</div>"
               if m.get("impacto_possivel") else "")
            + "</div>"
        )
    for o in oportunidades:
        fonte = o.get("fonte") or "fonte não informada"
        data_fonte = f" · {html.escape(str(o['data_fonte']))}" if o.get("data_fonte") else ""
        partes.append(
            "<div class='mc-oportunidade'><div class='mc-oportunidade-topo'>"
            "<span class='mc-chip mc-chip-interp'>PARA INVESTIGAR</span>"
            f"<span class='mc-oportunidade-ativo'>{html.escape(str(o.get('ativo_ou_setor') or ''))}</span>"
            f"<span class='mc-tese-data'>{html.escape(str(fonte))}{data_fonte}</span>"
            "</div>"
            f"<div class='mc-oportunidade-linha'>Catalisador: {texto_para_html(o.get('catalisador') or '—')}</div>"
            f"<div class='mc-oportunidade-linha'><span class='alta'>A favor:</span> {texto_para_html(o.get('argumento_favoravel') or '—')}</div>"
            f"<div class='mc-oportunidade-linha'><span class='baixa'>Contra:</span> {texto_para_html(o.get('argumento_contrario') or '—')}</div>"
            + (f"<div class='mc-oportunidade-fonte'>Investigar: {texto_para_html(o['acompanhar'])}</div>"
               if o.get("acompanhar") else "")
            + "</div>"
        )
    partes.append("</div>")
    return "".join(partes)


def _bloco_cenarios_html(sintese: dict) -> str:
    """Bloco F do briefing (CENÁRIOS E RISCOS) - data/sintese_mercado.py
    ('cenarios'/'observar_proximas_sessoes'), mesma lógica de seleção
    do cenário principal já validada naquele módulo (nunca recalculada
    aqui) - preservada mesmo quando o 'principal' não vier primeiro na
    lista da IA (ver data/sintese_mercado.py:_validar_e_limpar)."""
    if not sintese.get("ok"):
        return ""
    dados = sintese["dados"]
    cenarios = dados.get("cenarios") or []
    observar = dados.get("observar_proximas_sessoes") or []
    if not cenarios and not observar:
        return ""
    # Garante "principal" primeiro na renderização mesmo se, por algum
    # motivo, não vier assim na lista (defesa em profundidade - a
    # mesma garantia já existe na geração/validação, ver
    # data/sintese_mercado.py:_validar_e_limpar, mas o renderer nunca
    # deve confiar ciegamente na ordem recebida).
    cenarios = sorted(cenarios, key=lambda c: c.get("tipo") != "principal")
    partes = ["<div class='mc-secao'><div class='mc-secao-titulo'>CENÁRIOS E RISCOS</div>"]
    for c in cenarios:
        principal = c.get("tipo") == "principal"
        rotulo = "CENÁRIO PRINCIPAL" if principal else "CENÁRIO ALTERNATIVO"
        cor = "alta" if principal else "cinza"
        partes.append(
            f"<div class='mc-cenario'><div class='mc-cenario-rotulo {cor}'>{rotulo}</div>"
            f"<div class='mc-cenario-texto'>{texto_para_html(c.get('cenario') or '')}</div>"
            + (f"<div class='mc-cenario-linha'>Condição: {texto_para_html(c['condicao'])}</div>" if c.get("condicao") else "")
            + (f"<div class='mc-oportunidade-fonte'>Sinalizadores: {texto_para_html(c['sinalizadores'])}</div>" if c.get("sinalizadores") else "")
            + "</div>"
        )
    if cenarios:
        partes.append(
            "<div class='mc-aviso'>Cenários não têm probabilidade numérica - são leituras qualitativas, "
            "nunca uma previsão de preço.</div>"
        )
    if observar:
        partes.append("<div class='mc-radar-nome' style='margin-top:8px;'>O que observar nas próximas sessões</div>")
        for item in observar:
            fonte = item.get("fonte") or "fonte não informada"
            data_fonte = f" · {html.escape(str(item['data_fonte']))}" if item.get("data_fonte") else ""
            partes.append(
                "<div class='mc-linha'><span class='mc-marca'>›</span>"
                f"<span class='mc-prosa-inline'>{texto_para_html(item.get('item') or '')} — "
                f"{texto_para_html(item.get('motivo') or '')} <span class='cinza'>({html.escape(str(fonte))}{data_fonte})</span></span></div>"
            )
    partes.append("</div>")
    return "".join(partes)


def _corpo_edicao_estruturada_html(edicao: dict) -> str:
    """Conteúdo do jornal (capa/Brasil/Exterior/Empresas/Agenda/Radar/
    Teses/Catalisadores/Fontes), SEM <style> nem o wrapper '.mc-wrap' -
    extraído de render_edicao_estruturada_html (2026-10-27, missão
    "Morning Call: briefing profissional") pra poder ser reaproveitado
    sem duplicar
    <style> nem reimplementar nada desta função - comportamento
    idêntico ao de antes da extração (ver
    tests/test_morning_call_tab_ui.py, que cobre render_edicao_
    estruturada_html com o conteúdo inalterado)."""
    partes = []
    nota = edicao.get("mercados_nota")
    if nota:
        partes.append(f"<div class='mc-aviso'>{texto_para_html(nota)}</div>")

    capa = edicao.get("capa") or {}
    manchete = capa.get("manchete")
    chamadas = capa.get("chamadas") or []
    if manchete:
        partes.append(f"<div class='mc-manchete'>{_card_noticia_estruturada(manchete)}</div>")
        if chamadas:
            partes.append(
                "<div class='mc-chamadas'>" + "".join(
                    f"<a class='mc-chamada' href='{html.escape(_url_http_segura(c.get('link')) or '#', quote=True)}' "
                    f"target='_blank' rel='noopener'>{html.escape(str(c.get('titulo') or ''))}</a>"
                    for c in chamadas if c.get("titulo")
                ) + "</div>"
            )

    def _secao_mercado(titulo, bloco):
        partes.append(f"<div class='mc-secao'><div class='mc-secao-titulo'>{html.escape(titulo)}</div>")
        indicadores = bloco.get("indicadores") or []
        if indicadores:
            partes.append(
                "<div class='mc-indicadores'>"
                + "".join(_card_indicador_estruturado(i) for i in indicadores) + "</div>"
            )
        erro = bloco.get("noticias_erro")
        noticias = bloco.get("noticias")
        if erro:
            partes.append(f"<div class='mc-aviso'>Notícias indisponíveis nesta execução ({html.escape(str(erro))}).</div>")
        elif noticias:
            partes.append(
                "<div class='mc-lista-noticias'>"
                + "".join(_card_noticia_estruturada(f) for f in noticias) + "</div>"
            )
        else:
            partes.append("<div class='mc-aviso'>Nenhuma manchete nesta coleta.</div>")
        partes.append("</div>")

    partes.append("<div class='mc-grade'>")
    _secao_mercado("BRASIL", edicao.get("brasil") or {})
    _secao_mercado("EXTERIOR", edicao.get("exterior") or {})
    partes.append("</div>")

    empresas = edicao.get("empresas") or {}
    partes.append("<div class='mc-secao'><div class='mc-secao-titulo'>EMPRESAS E SETORES</div>")
    if empresas.get("cards"):
        partes.append(
            "<div class='mc-lista-noticias'>"
            + "".join(_card_noticia_estruturada(f) for f in empresas["cards"]) + "</div>"
        )
    elif empresas.get("noticias_erro"):
        partes.append(f"<div class='mc-aviso'>Notícias indisponíveis nesta execução ({html.escape(str(empresas['noticias_erro']))}).</div>")
    else:
        partes.append("<div class='mc-aviso'>Sem fatos relevantes confirmados nesta sessão.</div>")
    partes.append("</div>")

    # agenda/agenda_proximos: None = calendário indisponível nesta execução,
    # [] = calendário respondeu e não há evento (data/morning_call_editorial.
    # py:_agenda_hoje/_agenda_proximos, docstring explícita sobre a
    # diferença) - "or" tratava as duas coisas como a mesma ausência e
    # OMITIA a seção inteira mesmo quando a agenda rodou normalmente e só
    # não achou evento, sem dizer isso ao leitor (o caminho em texto, jobs/
    # morning_call.py:_secao_agenda, sempre diz "Nenhum evento relevante
    # identificado para hoje" nesse caso - o renderer estruturado omitia
    # silenciosamente). Mostra a seção sempre que pelo menos uma das duas
    # rodou (not None), com a mensagem certa pra lista vazia; só some de
    # verdade quando as duas falharam.
    agenda_hoje = empresas.get("agenda")
    agenda_prox = empresas.get("agenda_proximos")
    if agenda_hoje is not None or agenda_prox is not None:
        partes.append("<div class='mc-secao'><div class='mc-secao-titulo'>AGENDA</div>")
        if agenda_hoje is not None:
            partes.append("<div class='mc-agenda-grupo-titulo'>Hoje</div>")
            if agenda_hoje:
                partes.append("".join(_linha_agenda_estruturada(e) for e in agenda_hoje))
            else:
                partes.append("<div class='mc-aviso'>Nenhum evento relevante identificado para hoje.</div>")
        if agenda_prox is not None:
            partes.append("<div class='mc-agenda-grupo-titulo'>Próximos dias</div>")
            if agenda_prox:
                partes.append("".join(_linha_agenda_estruturada(e) for e in agenda_prox))
            else:
                partes.append("<div class='mc-aviso'>Nenhum evento com data confirmada ou estimada nos próximos dias.</div>")
        partes.append("</div>")

    radar = edicao.get("radar")
    if radar and radar.get("setores"):
        partes.append("<div class='mc-secao'><div class='mc-secao-titulo'>RADAR SETORIAL</div>")
        for bloco in radar["setores"]:
            partes.append("<div class='mc-radar-bloco'>")
            partes.append(f"<div class='mc-radar-nome'>{html.escape(str(bloco.get('nome') or '—'))}</div>")
            for fato_txt in bloco.get("o_que_aconteceu") or []:
                partes.append(f"<p class='mc-prosa'>{texto_para_html(fato_txt)}</p>")
            if bloco.get("por_que_importa"):
                partes.append(f"<p class='mc-prosa'><b>Por que importa:</b> {texto_para_html(bloco['por_que_importa'])}</p>")
            if bloco.get("acompanhar"):
                partes.append(f"<p class='mc-prosa'><b>Acompanhar:</b> {texto_para_html(bloco['acompanhar'])}</p>")
            partes.append("</div>")
        partes.append("</div>")

    # data/market_makers.py:inteligencia_mercado - fachada compartilhada
    # (RADAR também consome). None = a própria consulta falhou (ver
    # data/morning_call_editorial.py:montar_edicao) - FALHA DE COLETA, bem
    # diferente de uma consulta que respondeu sem nenhuma mudança/catalisador/
    # risco pros tickers do dia (dict com listas vazias) - nunca tratadas
    # como a mesma coisa (ver docstring de aviso_edicao_de_hoje_ausente sobre
    # o mesmo princípio aplicado à edição inteira).
    mm = edicao.get("market_makers")
    partes.append("<div class='mc-secao'><div class='mc-secao-titulo'>TESES E RECOMENDAÇÕES DE RESEARCH</div>")
    if mm is None:
        partes.append("<div class='mc-aviso'>Indisponível nesta execução (fonte de research/CVM não respondeu).</div>")
    else:
        teses = mm.get("mudancas") or []
        if teses:
            partes.extend(_card_tese_research(m) for m in teses)
        else:
            partes.append(
                "<div class='mc-aviso'>Nenhuma mudança de tese ou recomendação de research verificada na "
                "janela recente para os ativos citados nesta edição.</div>"
            )
    partes.append("</div>")

    if mm is not None:
        catalisadores = mm.get("catalisadores") or []
        riscos = mm.get("riscos") or {}
        if catalisadores or riscos:
            partes.append(
                "<div class='mc-secao'><div class='mc-secao-titulo'>CATALISADORES E ALERTAS — ATIVOS EM COBERTURA</div>"
                "<p class='mc-aviso' style='margin-bottom:8px;'>Eventos de calendário e alertas de qualidade dos "
                "indicadores dos ativos já citados nesta edição — sem chamada de IA nova.</p>"
            )
            for c in catalisadores:
                selo = "CONFIRMADO" if c.get("confirmado") else c.get("status_label", "ESTIMADO")
                partes.append(
                    "<div class='mc-linha'><span class='mc-marca'>›</span>"
                    f"<span class='mc-prosa-inline'><b>{html.escape(c['ticker'])}</b> — {html.escape(c['categoria'])} em "
                    f"{c['data'].strftime('%d/%m/%Y')} <span class='cinza'>({html.escape(selo)})</span></span></div>"
                )
            for ticker, alertas in riscos.items():
                partes.append(
                    "<div class='mc-linha'><span class='mc-marca'>›</span>"
                    f"<span class='mc-prosa-inline'><b>{html.escape(ticker)}</b> — risco: "
                    f"{texto_para_html('; '.join(alertas))}</span></div>"
                )
            partes.append("</div>")

    limitacoes = edicao.get("limitacoes") or ()
    fontes = edicao.get("fontes") or ()
    if limitacoes or fontes:
        partes.append("<div class='mc-secao'>")
        if limitacoes:
            partes.append(
                "<div class='mc-secao-titulo'>LIMITAÇÕES</div>" + "".join(
                    f"<div class='mc-linha'><span class='mc-marca'>›</span>"
                    f"<span class='mc-prosa-inline'>{texto_para_html(l)}</span></div>"
                    for l in limitacoes
                )
            )
        if fontes:
            partes.append(
                "<div class='mc-secao-titulo' style='margin-top:10px;'>FONTES</div>" + "".join(
                    f"<div class='mc-linha'><span class='mc-marca'>›</span>"
                    f"<span class='mc-prosa-inline'>{texto_para_html(f)}</span></div>"
                    for f in fontes
                )
            )
        partes.append("</div>")

    return "".join(partes)


def render_edicao_estruturada_html(edicao: dict) -> str:
    """Jornal completo (capa/Brasil/Exterior/Empresas/Agenda/Radar/Fontes)
    a partir do MESMO dict que jobs/morning_call_pdf.py usa pro PDF -
    camada de apresentação nova (Streamlit/HTML), sem recalcular nenhum
    dado nem reimplementar a seleção editorial."""
    return _estilo_mc() + "<div class='mc-wrap'>" + _corpo_edicao_estruturada_html(edicao) + "</div>"


@st.cache_data(ttl=1800, show_spinner=False)
def _edicao_estruturada(hora_ref: str) -> dict:
    # hora_ref so' entra na chave do cache (no maximo 1 previa por hora)
    from data.morning_call_editorial import montar_edicao

    return montar_edicao(datetime.now(TZ_SP))


@st.cache_data(ttl=1800, show_spinner=False)
def _pdf_bytes(hora_ref: str) -> bytes:
    from jobs.morning_call_pdf import gerar_pdf

    return gerar_pdf(_edicao_estruturada(hora_ref))


def _hora_ref() -> str:
    return datetime.now(TZ_SP).strftime("%Y-%m-%d %H")


@st.cache_data(ttl=300, show_spinner=False)
def _alertas_confiabilidade_cacheados(hora_ref: str) -> list:
    # hora_ref so' entra na chave do cache; ttl curto (5min, bem menor
    # que o da edicao/PDF) porque e' so' 1 leitura do painel SAUDE DOS
    # DADOS (ja cacheado por si so' no Supabase/coletores_status) - nao
    # justifica os mesmos 30min do conteudo editorial.
    return alertas_confiabilidade()


# horário previsto do envio (radar-morning-call.yml: 08:03 BRT + reservas
# até 09:47). Depois disso a edição saiu atrasada - em 21/10/2026 o GitHub
# só entregou os disparos entre 12:55 e 14:06 BRT (ver MANUAL.md). A causa
# é externa ao Pregão (agendador do GitHub Actions atrasa/descarta
# `schedule`, não um bug deste código) - mitigada em jobs/morning_call.py
# (_CORTE_ENVIO_AGENDADO: disparo agendado depois das 17h não envia) e
# documentada no MANUAL.md ("Disparo externo dos agendamentos"), nunca
# "corrigida" aqui porque não há nada neste repositório pra corrigir.
_LIMITE_HORARIO_PREVISTO = time(9, 30)


def aviso_atraso(executado_em: datetime) -> str | None:
    """Frase para o leitor quando a edição foi gerada depois do horário
    previsto - as cotações e o noticiário refletem a hora da geração, não
    a abertura do dia. None quando saiu no horário."""
    if executado_em.astimezone(TZ_SP).time() <= _LIMITE_HORARIO_PREVISTO:
        return None
    return ("fora do horário previsto (08h): cotações e notícias refletem a hora em que foi gerada, "
            "não a abertura do dia")


def aviso_edicao_de_hoje_ausente(ultima_data, agora: datetime) -> str | None:
    """Frase quando a edição de HOJE ainda não existe depois do horário
    previsto (dia útil) - em 22/10/2026 nenhum disparo agendado chegou e a
    aba mostrava a edição da véspera só com um "NÃO é a edição de hoje"
    discreto. None no fim de semana, antes das 09:30 ou se já há edição."""
    agora = agora.astimezone(TZ_SP)
    if agora.weekday() >= 5 or agora.time() <= _LIMITE_HORARIO_PREVISTO:
        return None
    if ultima_data is not None and ultima_data >= agora.date():
        return None
    complemento = (f" Abaixo, a última edição publicada ({ultima_data.strftime('%d/%m')})."
                   if ultima_data is not None else "")
    return (f"A edição de hoje ({agora.strftime('%d/%m')}) ainda não foi gerada: o disparo agendado não "
            f"chegou até agora.{complemento} Use a prévia para ver os dados de agora.")


def _cabecalho_edicao(ed: dict):
    hoje = datetime.now(TZ_SP).date()
    rotulo_dia = "hoje" if ed["data"] == hoje else "NÃO é a edição de hoje"
    cls = "alta" if ed["status"] == "ENVIADA" else "baixa"
    atraso = aviso_atraso(ed["executado_em"])
    nota_status = (
        " <span class='cinza'>(conteúdo gerado normalmente; falhou só o envio por e-mail)</span>"
        if ed["status"] == "FALHA_ENVIO" else ""
    )
    st.markdown(
        f"<div class='cinza' style='font-size:0.7rem; margin-bottom:0.4rem;'>Edição de "
        f"<b>{ed['data'].strftime('%d/%m/%Y')}</b> ({rotulo_dia}) · gerada às "
        f"{ed['executado_em'].astimezone(TZ_SP).strftime('%H:%M')} (Brasília) · "
        f"<span class='mc-status-pill {cls}'>{ed['status']}</span>" + nota_status
        + (f"<br><span style='color:var(--destaque);'>⚠ {atraso}</span>" if atraso else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def render_edicao_atual(prefs: dict):
    """Briefing do Morning Call (missão "Morning Call: briefing
    profissional", 2026-10-27). Dois níveis de custo, de propósito
    separados (ver seção de desempenho da missão - "evitar chamadas
    externas durante a renderização de cada componente"):

    1. Resumo executivo/radar de ações/cenários/alertas (A/C/F/G) -
       data/sintese_mercado.py:obter_sintese_mercado() (mesma função
       que a VISÃO GERAL já chama sem gate nenhum - cache de 20min
       compartilhado via data/ia_cache.py, não é uma 2ª chamada de IA)
       + data/morning_call_briefing.py:alertas_confiabilidade() (leitura
       do painel SAÚDE DOS DADOS, cache de 5min aqui). Sem botão -
       barato, igual à VISÃO GERAL.
    2. Jornal completo (B/D/E - agenda/teses/notícias/radar setorial) -
       data/morning_call_editorial.py:montar_edicao(), live (news +
       tradução), continua atrás do botão GERAR/ATUALIZAR PRÉVIA que já
       existia (cache de 30min em _edicao_estruturada depois do 1º
       clique) - comportamento preservado, só o rótulo mudou.

    A edição OFICIAL enviada por e-mail continua disponível, só que num
    expander: o texto nunca muda, o conteúdo acima é que fica mais
    completo/rico (dados de agora, não só o que foi enviado hoje)."""
    edicoes = listar_edicoes()
    publicada = next((e for e in (edicoes or []) if e["conteudo"]), None)

    with st.container(border=True):
        st.markdown('<div class="painel-titulo">MORNING CALL — RESUMO EXECUTIVO</div>', unsafe_allow_html=True)
        if edicoes is not None:
            ausente = aviso_edicao_de_hoje_ausente(publicada["data"] if publicada else None, datetime.now(TZ_SP))
            if ausente:
                st.warning(ausente)
        sintese = obter_sintese_mercado()
        alertas_saude = _alertas_confiabilidade_cacheados(_hora_ref())
        st.markdown(
            _estilo_mc() + "<div class='mc-wrap'>"
            + _bloco_alertas_html(alertas_saude, [])
            + _bloco_resumo_executivo_html(sintese)
            + _bloco_radar_acoes_html(sintese)
            + _bloco_cenarios_html(sintese)
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Gerar jornal completo com os dados de agora (agenda, teses, notícias - não envia e-mail)"):
        st.caption("Monta o jornal completo com as mesmas funções/dados do PDF anexado ao e-mail "
                   "(data/morning_call_editorial.montar_edicao) — leva alguns segundos e consulta as "
                   "fontes ao vivo. Nada é enviado nem registrado.")
        tem_previa = bool(st.session_state.get("mc_previa"))
        if st.button("ATUALIZAR JORNAL" if tem_previa else "GERAR JORNAL COMPLETO", key="mc_previa_btn"):
            if tem_previa:
                # .clear() do st.cache_data limpa TODAS as chaves da função,
                # não só a hora atual (confirmado: streamlit.runtime.caching).
                # _pdf_bytes(hora_ref) chama _edicao_estruturada(hora_ref) por
                # dentro, mas tem o PRÓPRIO cache - sem limpar os dois juntos,
                # "ATUALIZAR" aqui invalidava o dict mas deixava o PDF e o
                # "ver conteúdo na tela" de RELATÓRIO COMPLETO com os bytes
                # antigos, pra mesma hora_ref - o PDF baixado passava a
                # divergir do que a tela mostra.
                _edicao_estruturada.clear()
                _pdf_bytes.clear()
            st.session_state.pop("mc_previa", None)
            with st.spinner("Montando o jornal com as fontes de agora..."):
                try:
                    st.session_state["mc_previa"] = _edicao_estruturada(_hora_ref())
                    st.session_state["mc_previa_em"] = datetime.now(TZ_SP)
                except Exception as exc:
                    print(f"[morning_call_tab] previa falhou: {exc!r}")
                    st.error("Não foi possível montar o jornal agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_previa"):
            previa = st.session_state["mc_previa"]
            gerada_em = st.session_state.get("mc_previa_em")
            if gerada_em:
                st.caption(f"Jornal montado em {gerada_em.strftime('%d/%m/%Y às %H:%M:%S')} (Brasília) — dados de agora, não da abertura do dia.")
            novidades = tickers_novos(previa, publicada)
            if novidades:
                st.markdown(
                    "<div class='cinza' style='font-size:0.7rem; margin-bottom:0.4rem;'>Novos no radar desde a "
                    f"última edição enviada: {html.escape(', '.join(novidades))}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(render_edicao_estruturada_html(previa), unsafe_allow_html=True)

    with st.expander("Edição oficial enviada por e-mail hoje"):
        if edicoes is None:
            st.warning("Histórico indisponível (banco fora do ar).")
        elif publicada is None:
            st.info("Nenhuma edição publicada registrada ainda.")
        else:
            _cabecalho_edicao(publicada)
            st.caption("Conteúdo original do e-mail. Seções e itens foram organizados visualmente para facilitar a leitura; o texto factual não é reescrito.")
            _exibir_texto(publicada["conteudo"])


def render_relatorio_completo(prefs: dict):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">RELATÓRIO COMPLETO (PDF EDITORIAL)</div>', unsafe_allow_html=True)
        st.markdown(
            "<div class='cinza' style='font-size:0.78rem;'>O mesmo jornal em PDF anexado ao e-mail (capa, Brasil, "
            "exterior, empresas, radar setorial, fontes e limitações). O PDF das edições anteriores não é "
            "armazenado — aqui ele é montado com os dados de agora, sob demanda, a partir do mesmo conteúdo "
            "mostrado abaixo (consistência entre a leitura na tela e o PDF).</div>",
            unsafe_allow_html=True,
        )
        tem_pdf = bool(st.session_state.get("mc_pdf_hora"))
        if st.button("ATUALIZAR PDF" if tem_pdf else "GERAR PDF DE HOJE", key="mc_pdf_btn"):
            if tem_pdf:
                _pdf_bytes.clear()
                _edicao_estruturada.clear()
            st.session_state.pop("mc_pdf_hora", None)
            with st.spinner("Montando o PDF (pode levar até 1 minuto)..."):
                try:
                    hora_ref = _hora_ref()
                    _pdf_bytes(hora_ref)  # aquece o cache; dispara a exceção aqui, não na leitura abaixo
                    st.session_state["mc_pdf_hora"] = hora_ref
                    st.session_state["mc_pdf_em"] = datetime.now(TZ_SP)
                except Exception as exc:
                    print(f"[morning_call_tab] PDF falhou: {exc!r}")
                    st.error("Não foi possível gerar o PDF agora (fontes indisponíveis). Tente novamente em alguns minutos.")
        if st.session_state.get("mc_pdf_hora"):
            hora_ref = st.session_state["mc_pdf_hora"]
            gerado_em = st.session_state.get("mc_pdf_em")
            if gerado_em:
                st.caption(f"PDF montado em {gerado_em.strftime('%d/%m/%Y às %H:%M:%S')} (Brasília).")
            st.download_button(
                "BAIXAR PDF", _pdf_bytes(hora_ref),
                file_name=f"pregao-morning-call-{datetime.now(TZ_SP).strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf", key="mc_baixar_pdf",
            )
            with st.expander("Ver o conteúdo na tela (mesmo texto do PDF)", expanded=False):
                st.markdown(render_edicao_estruturada_html(_edicao_estruturada(hora_ref)), unsafe_allow_html=True)


def render_historico(prefs: dict):
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">HISTÓRICO DE EDIÇÕES</div>', unsafe_allow_html=True)
        edicoes = listar_edicoes()
        if edicoes is None:
            st.warning("Histórico indisponível (banco fora do ar).")
            return
        if not edicoes:
            st.info("Nenhuma edição registrada ainda.")
            return
        total_enviadas = sum(1 for ed in edicoes if ed.get("status") == "ENVIADA")
        total_falhas = sum(1 for ed in edicoes if ed.get("status") == "FALHA_ENVIO")
        c1, c2, c3 = st.columns(3)
        c1.metric("EDIÇÕES", len(edicoes))
        c2.metric("ENVIADAS", total_enviadas)
        c3.metric("FALHAS DE ENVIO", total_falhas)
        st.caption(
            "Horários de Brasília. ENVIADA = ao menos um assinante recebeu o e-mail da edição naquele dia; "
            "FALHA_ENVIO = o conteúdo foi gerado normalmente, mas o envio por e-mail falhou para todos os "
            "destinatários dessa execução (problema de entrega — SMTP/provedor —, não de geração ou dado)."
        )
        busca = st.text_input(
            "Buscar no histórico",
            placeholder="Data, manchete, empresa ou palavra-chave…",
            key="mc_historico_busca",
        ).strip().casefold()
        filtro_status = st.selectbox(
            "Filtrar status",
            ["Todos os status", "ENVIADA", "FALHA_ENVIO"],
            key="mc_historico_status",
        )
        limite = st.selectbox(
            "Quantidade",
            [10, 20, 60],
            format_func=lambda n: f"Últimas {n} edições",
            key="mc_historico_limite",
        )
        filtradas = []
        for ed in edicoes:
            if filtro_status != "Todos os status" and ed.get("status") != filtro_status:
                continue
            texto_busca = f"{ed['data'].strftime('%d/%m/%Y')} {ed.get('status', '')} {ed.get('conteudo') or ''}".casefold()
            if busca and busca not in texto_busca:
                continue
            filtradas.append(ed)
        st.caption(f"{len(filtradas)} edição(ões) encontrada(s).")
        if not filtradas:
            st.info("Nenhuma edição corresponde aos filtros.")
            return
        for ed in filtradas[:limite]:
            rotulo = f"{ed['data'].strftime('%d/%m/%Y')} · {ed['status']}"
            with st.expander(rotulo):
                if ed["conteudo"]:
                    _cabecalho_edicao(ed)
                    _exibir_texto(ed["conteudo"])
                else:
                    st.caption("Texto não registrado nesta execução.")


def render_preferencias(prefs: dict, usuario: dict, persistir_fn):
    """Mesmo toggle de efeito imediato que vivia em CONFIG (default
    DESLIGADO, opt-in explicito - ver config.PREFS_PADRAO e
    jobs/morning_call.py:listar_assinantes_morning_call). So' muda a
    preferencia do proprio usuario; nao dispara envio."""
    with st.container(border=True):
        st.markdown('<div class="painel-titulo">PREFERÊNCIAS DE RECEBIMENTO</div>', unsafe_allow_html=True)
        ativo = st.toggle(
            "RECEBER MORNING CALL POR E-MAIL",
            value=prefs.get("morning_call_email_ativo", False),
            help=(
                "Envia o briefing diário (mercados, macro, agenda, notícias) por "
                f"e-mail às 08h BRT, em dias úteis, para {usuario['email']}. "
                "Pode ser desligado a qualquer momento - efeito imediato."
            ),
            key="toggle_morning_call_email",
        )
        if ativo != prefs.get("morning_call_email_ativo", False):
            prefs["morning_call_email_ativo"] = ativo
            # marca como "ja perguntado" tambem aqui: quem muda a
            # preferencia direto em MORNING CALL › Preferências (sem
            # passar pelo banner de onboarding) nao deve ver a oferta
            # reaparecer depois.
            prefs["morning_call_email_perguntado"] = True
            if persistir_fn():
                st.toast(
                    "Preferência de Morning Call por e-mail salva." if ativo
                    else "Você não vai mais receber o Morning Call por e-mail.",
                )
            else:
                st.warning("Preferência aplicada nesta sessão (banco indisponível, não foi salva).")
            st.rerun()
        st.caption(f"Destino: {usuario['email']} · dias úteis, por volta das 08h (Brasília).")
