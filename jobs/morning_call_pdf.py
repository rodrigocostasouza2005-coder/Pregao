# -*- coding: utf-8 -*-
"""Camada de apresentação (ReportLab) do Morning Call em PDF.

Consome SÓ o dict devolvido por data/morning_call_editorial.py:montar_edicao
- nunca chama provedor de dado nenhum diretamente (separação exigida pela
missão: dados != layout). A única chamada de rede feita aqui é o download
best-effort da foto de um card de notícia já validada como imagem real por
data/news.py (_baixar_imagem_card) - qualquer falha cai pro retângulo
tipográfico/vetorial (nunca um link de imagem quebrado nem um placeholder
genérico de banco de imagens).

Identidade visual (mockup "Mockup Editorial do Morning Call Financeiro.png",
Downloads, referência de linguagem visual - não de conteúdo): azul-marinho +
branco quente + cinza editorial + âmbar/laranja de destaque; serifada
(Times-Roman/Bold) pra manchetes/título, sans-serif (Helvetica) pro corpo e
tabelas - ambas fontes base-14 do PDF, sem embutir arquivo de fonte.
"""
import io
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

try:
    import requests
except Exception:  # pragma: no cover - requests já é dependência do projeto
    requests = None

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - Pillow já é dependência transitiva (streamlit)
    Image = None
    ImageDraw = None

PAGINA_LARGURA, PAGINA_ALTURA = A4
MARGEM = 16 * 2.834645669  # ~16mm em pontos (1mm = 2.834645669pt)

# Geometria do cabeçalho navy (usada por _cabecalho) e do título de página
# interna (BRASIL/EXTERIOR/EMPRESAS E SETORES) - constantes nomeadas (não
# literais espalhados) porque um bug real (2026-10-17, achado por inspeção
# visual real, não por teste automatizado) foi exatamente esses 2 números
# ficando próximos demais: o título (serifado 18pt) desenhado com y perto
# demais do rodapé do cabeçalho tinha o topo dos glifos sobreposto pelo
# retângulo navy (texto navy-sobre-navy = invisível). Ver
# test_titulo_pagina_interna_nao_sobrepoe_cabecalho em
# tests/test_morning_call_pdf.py - regressão geométrica, não visual.
ALTURA_CABECALHO = 22 * 2.834645669
ALTURA_FAIXA_AMBAR_CABECALHO = 2
Y_TITULO_PAGINA_INTERNA = PAGINA_ALTURA - 92

# Altura do card de indicador (_card_indicador) - 4 linhas SEMPRE
# empilhadas (nome/preço/variação/barra), nunca 2 lado a lado na mesma
# linha. Achado real (mesma inspeção de 2026-10-17): variação% e
# barra_fmt na mesma linha colidiam no layout de 4 colunas da página
# EXTERIOR (cards mais estreitos que os 2 de BRASIL/CAPA).
ALTURA_CARD_INDICADOR = 68

AZUL_MARINHO = HexColor("#0E1B2E")
BRANCO_QUENTE = HexColor("#F7F3ED")
CINZA_EDITORIAL = HexColor("#4A4F57")
AMBAR = HexColor("#E8762C")
VERDE_ALTA = HexColor("#2E8B57")
VERMELHO_QUEDA = HexColor("#C0392B")
BRANCO = HexColor("#FFFFFF")
CINZA_CLARO = HexColor("#D9D4CC")
ROXO_SINTESE = HexColor("#5B4B8A")

SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"

# Fonte/tamanho do título de página interna ("Brasil"/"Exterior"/"Empresas
# e Setores") - usada pela geometria em Y_TITULO_PAGINA_INTERNA acima.
FONTE_TITULO_PAGINA_INTERNA = (SERIF_BOLD, 18)

_TAG_COR = {
    "FATO": AZUL_MARINHO,
    "INTERPRETAÇÃO": AMBAR,
    "ACOMPANHAR": CINZA_EDITORIAL,
    "SÍNTESE": ROXO_SINTESE,
}

_HEADERS_IMAGEM = {"User-Agent": "Mozilla/5.0 (compatible; PregaoBot/1.0)"}

_DIAS_SEMANA_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
_MESES_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _data_extenso_pt_br(agora):
    """'Segunda-feira, 19 de outubro de 2026' sem depender de locale do
    SO (agora.strftime('%A')/'%B' lê o locale do processo - em runner do
    GitHub Actions, sem pt_BR instalado, isso saía em inglês: 'Monday, 19
    de october de 2026', achado real na inspeção visual da CAPA,
    2026-10-17). datetime.weekday(): 0=segunda...6=domingo - mesma ordem
    de _DIAS_SEMANA_PT."""
    dia_semana = _DIAS_SEMANA_PT[agora.weekday()]
    mes = _MESES_PT[agora.month - 1]
    return f"{dia_semana.capitalize()}, {agora.day:02d} de {mes} de {agora.year}"


def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def _cor_variacao(variacao_pct):
    if variacao_pct is None:
        return CINZA_EDITORIAL
    if variacao_pct > 0:
        return VERDE_ALTA
    if variacao_pct < 0:
        return VERMELHO_QUEDA
    return CINZA_EDITORIAL


def _texto_variacao(variacao_pct):
    if variacao_pct is None:
        return "indisponível"
    sinal = "+" if variacao_pct > 0 else ""
    return f"{sinal}{_fmt_num(variacao_pct)}%"


def _quebrar_linhas(texto, fonte, tamanho, largura_max):
    """Quebra `texto` em linhas que cabem em `largura_max` pontos, medindo
    com stringWidth (métrica real da fonte base-14) - nunca um corte por
    contagem de caracteres, que erraria em textos com acento/maiúsculas
    (larguras bem diferentes entre glifos em fonte não-monoespaçada)."""
    palavras = (texto or "").split()
    linhas, atual = [], ""
    for palavra in palavras:
        candidato = f"{atual} {palavra}".strip()
        if stringWidth(candidato, fonte, tamanho) <= largura_max or not atual:
            atual = candidato
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas or [""]


def _desenhar_paragrafo(c, texto, x, y, largura_max, fonte=SANS, tamanho=9, cor=AZUL_MARINHO,
                         interlinha=None, max_linhas=None, link=None):
    """Desenha texto quebrado em múltiplas linhas a partir de (x, y) descendo
    - devolve o y final (topo da próxima linha livre). `link` (opcional)
    torna a área ocupada por TODAS as linhas desenhadas clicável (usado nas
    manchetes, que sempre têm o link original da fonte, nunca um link
    inventado)."""
    interlinha = interlinha or (tamanho * 1.28)
    linhas = _quebrar_linhas(texto, fonte, tamanho, largura_max)
    if max_linhas:
        cortado = len(linhas) > max_linhas
        linhas = linhas[:max_linhas]
        if cortado and linhas:
            while linhas[-1] and stringWidth(linhas[-1] + "…", fonte, tamanho) > largura_max:
                linhas[-1] = linhas[-1][:-1]
            linhas[-1] = linhas[-1] + "…"
    c.setFont(fonte, tamanho)
    c.setFillColor(cor)
    y_inicio = y
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= interlinha
    if link:
        altura_total = y_inicio - y + (interlinha - tamanho)
        c.linkURL(link, (x, y, x + largura_max, y_inicio + tamanho), relative=0, thickness=0)
    return y


def _tag_chip(c, tag, x, y):
    if not tag:
        return x
    cor = _TAG_COR.get(tag, CINZA_EDITORIAL)
    largura = stringWidth(tag, SANS_BOLD, 6.5) + 10
    c.setFillColor(cor)
    c.roundRect(x, y - 2, largura, 11, 2, stroke=0, fill=1)
    c.setFillColor(BRANCO)
    c.setFont(SANS_BOLD, 6.5)
    c.drawString(x + 5, y + 1.3, tag)
    return x + largura + 6


def _grafico_linha_png(serie, largura_px=520, altura_px=200, cor_linha="#E8762C"):
    """Mini-gráfico de linha (PNG, via Pillow) a partir de uma série REAL
    [(datetime, valor), ...] - nunca inventa ponto; série vazia/curta demais
    devolve None (quem desenha a página cai pro aviso textual "gráfico
    indisponível nesta execução", nunca um gráfico vazio/quebrado)."""
    if Image is None or not serie or len(serie) < 2:
        return None
    valores = [v for _, v in serie]
    minimo, maximo = min(valores), max(valores)
    extensao = (maximo - minimo) or 1.0
    pad = 14
    img = Image.new("RGB", (largura_px, altura_px), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    pontos = []
    n = len(valores)
    for i, v in enumerate(valores):
        px = pad + (largura_px - 2 * pad) * (i / (n - 1))
        py = altura_px - pad - (altura_px - 2 * pad) * ((v - minimo) / extensao)
        pontos.append((px, py))
    draw.line(pontos, fill=cor_linha, width=3, joint="curve")
    draw.line([(pad, altura_px - pad), (largura_px - pad, altura_px - pad)], fill="#D9D4CC", width=1)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _baixar_imagem_card(url, timeout=(3, 6), tamanho_max=4_000_000):
    """Download best-effort da foto de um card - a URL já passou pela
    validação de conteúdo real de data/news.py (og:image, nunca ícone/pixel
    de rastreio) no momento em que foi cacheada; aqui só confirmamos de novo
    o Content-Type (defesa em profundidade, nunca confia em cache antigo
    sem reconferir) e limitamos o tamanho pra nunca travar a geração do PDF
    numa imagem gigante. Qualquer falha (timeout, HTTP de erro, tipo
    errado, imagem corrompida) -> None, nunca lança exceção."""
    if not url or requests is None or Image is None:
        return None
    try:
        r = requests.get(url, headers=_HEADERS_IMAGEM, timeout=timeout, stream=True)
        if r.status_code >= 400:
            return None
        tipo = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not tipo.startswith("image/"):
            return None
        bruto = r.raw.read(tamanho_max + 1, decode_content=True)
        if not bruto or len(bruto) > tamanho_max:
            return None
        Image.open(io.BytesIO(bruto)).verify()
        return bruto
    except Exception:
        return None


def _placeholder_foto(c, x, y, largura, altura, rotulo):
    """Fallback tipográfico/vetorial quando não há imagem legítima
    cacheada (ou o download falhou) - NUNCA um placeholder genérico de
    banco de imagens/ícone quebrado: um bloco sólido na identidade visual
    da publicação com a palavra-chave do assunto, mesma régua editorial de
    jornal quando não há foto disponível pra uma matéria."""
    c.setFillColor(AZUL_MARINHO)
    c.rect(x, y, largura, altura, stroke=0, fill=1)
    c.setFillColor(AMBAR)
    c.rect(x, y, largura, 4, stroke=0, fill=1)
    c.setFillColor(BRANCO_QUENTE)
    c.setFont(SERIF_BOLD, 10)
    palavra = (rotulo or "PREGÃO").strip().split()[0].upper()[:14]
    c.drawCentredString(x + largura / 2, y + altura / 2 - 4, palavra)
    c.setFont(SANS, 6)
    c.setFillColor(CINZA_CLARO)
    c.drawCentredString(x + largura / 2, y + altura / 2 - 16, "sem foto disponível")


def _cabecalho(c, agora, pagina_titulo):
    altura = ALTURA_CABECALHO
    c.setFillColor(AZUL_MARINHO)
    c.rect(0, PAGINA_ALTURA - altura, PAGINA_LARGURA, altura, stroke=0, fill=1)
    c.setFillColor(AMBAR)
    c.rect(0, PAGINA_ALTURA - altura - ALTURA_FAIXA_AMBAR_CABECALHO, PAGINA_LARGURA, ALTURA_FAIXA_AMBAR_CABECALHO, stroke=0, fill=1)
    c.setFillColor(BRANCO_QUENTE)
    c.setFont(SERIF_BOLD, 16)
    c.drawString(MARGEM, PAGINA_ALTURA - altura / 2 - 5, "PREGÃO")
    c.setFont(SANS, 8)
    c.drawString(MARGEM + stringWidth("PREGÃO", SERIF_BOLD, 16) + 8, PAGINA_ALTURA - altura / 2 - 4,
                 "MORNING CALL")
    c.setFont(SANS, 9)
    c.drawRightString(PAGINA_LARGURA - MARGEM, PAGINA_ALTURA - altura / 2 - 1,
                       agora.strftime("%d/%m/%Y"))
    c.setFont(SANS, 7)
    c.setFillColor(CINZA_CLARO)
    c.drawRightString(PAGINA_LARGURA - MARGEM, PAGINA_ALTURA - altura / 2 - 11, pagina_titulo)


def _rodape(c, agora, numero_pagina, total_paginas):
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.5)
    c.line(MARGEM, 28, PAGINA_LARGURA - MARGEM, 28)
    c.setFont(SANS, 6.5)
    c.setFillColor(CINZA_EDITORIAL)
    c.drawString(MARGEM, 18, "Conteúdo informativo, gerado a partir de fontes públicas - não constitui recomendação de investimento.")
    c.drawRightString(PAGINA_LARGURA - MARGEM, 18, f"Página {numero_pagina}/{total_paginas} · gerado {agora.strftime('%d/%m/%Y %H:%M')} (horário de Brasília)")


def _card_indicador(c, indicador, x, y, largura, altura):
    """4 linhas empilhadas (nome/preço/variação/barra), nunca lado a lado
    - achado real da inspeção visual (2026-10-17): variação e barra_fmt
    na MESMA linha (uma à esquerda, outra à direita) colidiam no layout
    de 4 colunas (página EXTERIOR, cards mais estreitos que BRASIL/CAPA,
    que só têm 2) porque barra_fmt ("DD/MM HH:MM (horário de Brasília)")
    é longo demais pra sobrar espaço ao lado da variação em card
    estreito. Empilhada, a barra também é truncada com reticência
    (_quebrar_linhas) pra nunca estourar a largura do card."""
    c.setFillColor(BRANCO)
    c.setStrokeColor(CINZA_CLARO)
    c.roundRect(x, y, largura, altura, 4, stroke=1, fill=1)
    c.setFillColor(CINZA_EDITORIAL)
    c.setFont(SANS_BOLD, 8)
    c.drawString(x + 8, y + altura - 14, indicador["nome"].upper())
    if indicador.get("erro"):
        c.setFont(SANS, 8)
        c.setFillColor(CINZA_EDITORIAL)
        c.drawString(x + 8, y + altura / 2 - 6, "indisponível")
        return
    c.setFont(SERIF_BOLD, 15)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(x + 8, y + altura - 34, _fmt_num(indicador.get("preco")))
    c.setFont(SANS_BOLD, 9)
    c.setFillColor(_cor_variacao(indicador.get("variacao_pct")))
    c.drawString(x + 8, y + altura - 48, _texto_variacao(indicador.get("variacao_pct")))
    if indicador.get("barra_fmt"):
        c.setFont(SANS, 6)
        c.setFillColor(CINZA_EDITORIAL)
        linha_barra = _quebrar_linhas(indicador["barra_fmt"], SANS, 6, largura - 16, )[0]
        if stringWidth(linha_barra, SANS, 6) > largura - 16:
            while linha_barra and stringWidth(linha_barra + "…", SANS, 6) > largura - 16:
                linha_barra = linha_barra[:-1]
            linha_barra += "…"
        c.drawString(x + 8, y + altura - 60, linha_barra)


def _tabela(c, linhas, colunas, x, y, largura, altura_linha=14):
    """Tabela simples (cabeçalho navy + linhas alternadas) - `colunas` é
    lista de (chave, rótulo, largura_relativa)."""
    total_relativo = sum(l for _, _, l in colunas)
    larguras = [largura * l / total_relativo for _, _, l in colunas]
    c.setFillColor(AZUL_MARINHO)
    c.rect(x, y - altura_linha, largura, altura_linha, stroke=0, fill=1)
    cx = x
    c.setFont(SANS_BOLD, 7.5)
    c.setFillColor(BRANCO_QUENTE)
    for (_, rotulo, _), w in zip(colunas, larguras):
        c.drawString(cx + 6, y - altura_linha + 4, rotulo.upper())
        cx += w
    linha_y = y - altura_linha
    for i, linha in enumerate(linhas):
        linha_y -= altura_linha
        if i % 2 == 1:
            c.setFillColor(HexColor("#EFEAE2"))
            c.rect(x, linha_y, largura, altura_linha, stroke=0, fill=1)
        cx = x
        c.setFont(SANS, 7.5)
        c.setFillColor(AZUL_MARINHO)
        for (chave, _, _), w in zip(colunas, larguras):
            valor = str(linha.get(chave, "") or "")
            linhas_txt = _quebrar_linhas(valor, SANS, 7.5, w - 10)
            c.drawString(cx + 6, linha_y + 4, linhas_txt[0])
            cx += w
    return linha_y


def _secao_noticias(c, titulo_secao, noticias, noticias_erro, x, y, largura, max_itens=6):
    c.setFont(SERIF_BOLD, 11)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(x, y, titulo_secao)
    y -= 16
    if noticias_erro:
        y = _desenhar_paragrafo(c, f"Notícias indisponíveis nesta execução ({noticias_erro}).",
                                 x, y, largura, fonte=SANS, tamanho=8, cor=CINZA_EDITORIAL)
        return y - 6
    if not noticias:
        y = _desenhar_paragrafo(c, "Nenhuma manchete relevante nesta coleta.",
                                 x, y, largura, fonte=SANS, tamanho=8, cor=CINZA_EDITORIAL)
        return y - 6
    for item in noticias[:max_itens]:
        x_tag = _tag_chip(c, item.get("tag"), x, y - 2)
        titulo = item.get("titulo") or ""
        veiculo = item.get("veiculo")
        rotulo = f"{titulo} — {veiculo}" if veiculo else titulo
        y = _desenhar_paragrafo(c, rotulo, x_tag, y, largura - (x_tag - x), fonte=SANS, tamanho=8.5,
                                 cor=AZUL_MARINHO, max_linhas=2, link=item.get("link"))
        y -= 6
    return y


def _pagina_capa(c, edicao):
    agora = edicao["agora"]
    _cabecalho(c, agora, "CAPA")
    y = PAGINA_ALTURA - 100
    c.setFillColor(AZUL_MARINHO)
    c.setFont(SERIF_BOLD, 26)
    c.drawString(MARGEM, y, "MORNING CALL")
    c.setFillColor(AMBAR)
    c.setFont(SERIF, 13)
    c.drawString(MARGEM, y - 22, _data_extenso_pt_br(agora))

    capa = edicao.get("capa") or {}
    indicadores = capa.get("indicadores") or []
    largura_util = PAGINA_LARGURA - 2 * MARGEM
    largura_card = (largura_util - 12) / max(len(indicadores), 1)
    cx = MARGEM
    y_cards = y - 60
    for ind in indicadores:
        _card_indicador(c, ind, cx, y_cards - ALTURA_CARD_INDICADOR, largura_card - 12, ALTURA_CARD_INDICADOR)
        cx += largura_card

    y_destaques = y_cards - 98
    c.setFont(SERIF_BOLD, 12)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y_destaques, "NESTA EDIÇÃO")
    y_destaques -= 20
    destaques = capa.get("destaques") or []
    if not destaques:
        _desenhar_paragrafo(c, "Sem manchetes de destaque confirmadas nesta coleta — ver BRASIL/EXTERIOR.",
                             MARGEM, y_destaques, largura_util, fonte=SANS, tamanho=9, cor=CINZA_EDITORIAL)
    for item in destaques:
        x_tag = _tag_chip(c, item.get("tag"), MARGEM, y_destaques - 2)
        titulo = item.get("titulo") or ""
        veiculo = item.get("veiculo")
        rotulo = f"{titulo} — {veiculo}" if veiculo else titulo
        y_destaques = _desenhar_paragrafo(c, rotulo, x_tag, y_destaques, largura_util - (x_tag - MARGEM),
                                           fonte=SERIF, tamanho=11, cor=AZUL_MARINHO, max_linhas=2,
                                           link=item.get("link"))
        y_destaques -= 14

    _desenhar_paragrafo(
        c,
        "Edição gerada automaticamente a partir de dados públicos (Yahoo Finance, Banco Central/Focus, "
        "CVM, Google News) - ver página 4 para fontes e limitações completas.",
        MARGEM, 70, largura_util, fonte=SANS, tamanho=7.5, cor=CINZA_EDITORIAL,
    )
    _rodape(c, agora, 1, 4)


def _pagina_brasil(c, edicao):
    agora = edicao["agora"]
    _cabecalho(c, agora, "BRASIL · JUROS E MERCADO")
    largura_util = PAGINA_LARGURA - 2 * MARGEM
    y = Y_TITULO_PAGINA_INTERNA
    c.setFont(*FONTE_TITULO_PAGINA_INTERNA)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y, "Brasil")

    brasil = edicao.get("brasil") or {}
    indicadores = (brasil.get("indicadores") or [])[:2]
    largura_card = (largura_util - 12) / max(len(indicadores), 1)
    cx = MARGEM
    y_cards = y - 36
    for ind in indicadores:
        _card_indicador(c, ind, cx, y_cards - ALTURA_CARD_INDICADOR, largura_card - 12, ALTURA_CARD_INDICADOR)
        cx += largura_card

    grafico = _grafico_linha_png(brasil.get("historico_ibov"), cor_linha="#E8762C")
    y_grafico_topo = y_cards - 78
    altura_grafico = 90
    if grafico:
        c.drawImage(ImageReader(grafico), MARGEM, y_grafico_topo - altura_grafico, width=largura_util,
                     height=altura_grafico, preserveAspectRatio=False, mask="auto")
    else:
        c.setFillColor(HexColor("#EFEAE2"))
        c.rect(MARGEM, y_grafico_topo - altura_grafico, largura_util, altura_grafico, stroke=0, fill=1)
        c.setFont(SANS, 8)
        c.setFillColor(CINZA_EDITORIAL)
        c.drawCentredString(PAGINA_LARGURA / 2, y_grafico_topo - altura_grafico / 2, "Ibovespa (1 mês): gráfico indisponível nesta execução")
    c.setFont(SANS, 7)
    c.setFillColor(CINZA_EDITORIAL)
    c.drawString(MARGEM, y_grafico_topo - altura_grafico - 10, "Ibovespa — fechamento diário, últimos 30 dias (Yahoo Finance)")

    y_tabela = y_grafico_topo - altura_grafico - 26
    linhas_tabela = [
        {"indicador": l.get("indicador", l.get("nome")), "referencia": l.get("referencia", ""), "detalhe": l.get("detalhe", "")}
        for l in (brasil.get("indicadores") or [])[2:]
    ]
    if linhas_tabela:
        c.setFont(SERIF_BOLD, 11)
        c.setFillColor(AZUL_MARINHO)
        c.drawString(MARGEM, y_tabela, "Indicadores macro")
        y_tabela = _tabela(
            c, linhas_tabela,
            [("indicador", "Indicador", 1.0), ("referencia", "Referência", 0.7), ("detalhe", "Detalhe", 2.3)],
            MARGEM, y_tabela - 6, largura_util,
        )
        y_tabela -= 14

    destaque = brasil.get("destaque")
    if destaque:
        c.setFillColor(HexColor("#EFEAE2"))
        c.rect(MARGEM, y_tabela - 48, largura_util, 48, stroke=0, fill=1)
        c.setFillColor(AMBAR)
        c.rect(MARGEM, y_tabela - 48, 3, 48, stroke=0, fill=1)
        c.setFont(SERIF, 12)
        c.setFillColor(AZUL_MARINHO)
        y_cit = _desenhar_paragrafo(c, f"“{destaque['titulo']}”", MARGEM + 14, y_tabela - 16, largura_util - 28,
                                     fonte=SERIF, tamanho=12, cor=AZUL_MARINHO, max_linhas=2, link=destaque.get("link"))
        if destaque.get("veiculo"):
            c.setFont(SANS, 7.5)
            c.setFillColor(CINZA_EDITORIAL)
            c.drawString(MARGEM + 14, y_tabela - 42, f"— {destaque['veiculo']}")
        y_tabela -= 58

    _secao_noticias(c, "Notícias — Brasil", brasil.get("noticias"), brasil.get("noticias_erro"),
                     MARGEM, y_tabela - 6, largura_util, max_itens=5)
    _rodape(c, agora, 2, 4)


def _pagina_exterior(c, edicao):
    agora = edicao["agora"]
    _cabecalho(c, agora, "EXTERIOR · COMMODITIES")
    largura_util = PAGINA_LARGURA - 2 * MARGEM
    y = Y_TITULO_PAGINA_INTERNA
    c.setFont(*FONTE_TITULO_PAGINA_INTERNA)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y, "Exterior")

    exterior = edicao.get("exterior") or {}
    indicadores = exterior.get("indicadores") or []
    largura_card = (largura_util - 3 * 8) / max(len(indicadores), 1)
    cx = MARGEM
    y_cards = y - 36
    for ind in indicadores:
        _card_indicador(c, ind, cx, y_cards - ALTURA_CARD_INDICADOR, largura_card - 8, ALTURA_CARD_INDICADOR)
        cx += largura_card + 8

    grafico = _grafico_linha_png(exterior.get("historico_petroleo"), cor_linha="#0E1B2E")
    y_grafico_topo = y_cards - 78
    altura_grafico = 90
    if grafico:
        c.drawImage(ImageReader(grafico), MARGEM, y_grafico_topo - altura_grafico, width=largura_util,
                     height=altura_grafico, preserveAspectRatio=False, mask="auto")
    else:
        c.setFillColor(HexColor("#EFEAE2"))
        c.rect(MARGEM, y_grafico_topo - altura_grafico, largura_util, altura_grafico, stroke=0, fill=1)
        c.setFont(SANS, 8)
        c.setFillColor(CINZA_EDITORIAL)
        c.drawCentredString(PAGINA_LARGURA / 2, y_grafico_topo - altura_grafico / 2, "Petróleo Brent (1 mês): gráfico indisponível nesta execução")
    c.setFont(SANS, 7)
    c.setFillColor(CINZA_EDITORIAL)
    c.drawString(MARGEM, y_grafico_topo - altura_grafico - 10, "Petróleo Brent — fechamento diário, últimos 30 dias (Yahoo Finance)")

    y_noticias = y_grafico_topo - altura_grafico - 26
    y_noticias = _secao_noticias(c, "Notícias — Internacional", exterior.get("noticias"), exterior.get("noticias_erro"),
                                  MARGEM, y_noticias, largura_util, max_itens=5)

    c.setFont(SERIF_BOLD, 11)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y_noticias - 4, "Tendências e riscos a acompanhar")
    y_interp = y_noticias - 20
    for item in exterior.get("interpretacoes") or []:
        x_tag = _tag_chip(c, item.get("tag"), MARGEM, y_interp - 2)
        y_interp = _desenhar_paragrafo(c, item.get("texto", ""), x_tag, y_interp, largura_util - (x_tag - MARGEM),
                                        fonte=SANS, tamanho=8, cor=CINZA_EDITORIAL, max_linhas=2)
        y_interp -= 6
    _rodape(c, agora, 3, 4)


def _pagina_empresas(c, edicao):
    agora = edicao["agora"]
    _cabecalho(c, agora, "EMPRESAS, SETORES E AGENDA")
    largura_util = PAGINA_LARGURA - 2 * MARGEM
    y = Y_TITULO_PAGINA_INTERNA
    c.setFont(*FONTE_TITULO_PAGINA_INTERNA)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y, "Empresas e Setores")

    empresas = edicao.get("empresas") or {}
    cards = empresas.get("cards") or []
    y_cards_topo = y - 20
    largura_card = (largura_util - 12) / 2
    altura_card = 96
    altura_foto = 46
    for i, card in enumerate(cards[:4]):
        col = i % 2
        linha = i // 2
        x_card = MARGEM + col * (largura_card + 12)
        y_card = y_cards_topo - linha * (altura_card + 10) - altura_card
        c.setFillColor(BRANCO)
        c.setStrokeColor(CINZA_CLARO)
        c.roundRect(x_card, y_card, largura_card, altura_card, 4, stroke=1, fill=1)
        imagem_bytes = _baixar_imagem_card(card.get("imagem"))
        if imagem_bytes:
            try:
                c.drawImage(ImageReader(io.BytesIO(imagem_bytes)), x_card + 4, y_card + altura_card - altura_foto - 4,
                            width=largura_card - 8, height=altura_foto, preserveAspectRatio=True, anchor="n", mask="auto")
            except Exception:
                _placeholder_foto(c, x_card + 4, y_card + altura_card - altura_foto - 4, largura_card - 8, altura_foto, card.get("titulo"))
        else:
            _placeholder_foto(c, x_card + 4, y_card + altura_card - altura_foto - 4, largura_card - 8, altura_foto, card.get("titulo"))
        x_tag = _tag_chip(c, card.get("tag"), x_card + 4, y_card + altura_card - altura_foto - 16)
        texto = card.get("resumo") or card.get("titulo") or ""
        _desenhar_paragrafo(c, texto, x_card + 4, y_card + altura_card - altura_foto - 28,
                             largura_card - 8, fonte=SANS, tamanho=7.5, cor=AZUL_MARINHO, max_linhas=3,
                             link=card.get("link_original") or card.get("link"))

    if not cards:
        _desenhar_paragrafo(
            c, "Sem fatos relevantes confirmados com ticker identificável nesta coleta — "
            "ver BRASIL/EXTERIOR para o noticiário macro.",
            MARGEM, y_cards_topo - 10, largura_util, fonte=SANS, tamanho=8.5, cor=CINZA_EDITORIAL,
        )

    n_linhas_cards = max((len(cards[:4]) + 1) // 2, 1 if cards else 0)
    y_agenda = y_cards_topo - n_linhas_cards * (altura_card + 10) - 16

    c.setFont(SERIF_BOLD, 13)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y_agenda, "Agenda de hoje")
    y_agenda -= 16
    agenda = empresas.get("agenda")
    if agenda is None:
        y_agenda = _desenhar_paragrafo(c, "Agenda do dia indisponível nesta execução.", MARGEM, y_agenda,
                                        largura_util, fonte=SANS, tamanho=8.5, cor=CINZA_EDITORIAL)
    elif not agenda:
        y_agenda = _desenhar_paragrafo(c, "Nenhum evento relevante identificado para hoje.", MARGEM, y_agenda,
                                        largura_util, fonte=SANS, tamanho=8.5, cor=CINZA_EDITORIAL)
    else:
        linhas_agenda = [
            {
                "empresa": f"{e['empresa']} ({e['ticker']})",
                "evento": f"{e['tipo_evento']} {e.get('periodo', '')}".strip(),
                "horario": e.get("horario", ""),
                "status": f"{e['status_rotulo']}",
            }
            for e in agenda
        ]
        y_agenda = _tabela(
            c, linhas_agenda,
            [("empresa", "Empresa", 1.3), ("evento", "Evento", 1.0), ("horario", "Horário", 0.6), ("status", "Status", 1.1)],
            MARGEM, y_agenda, largura_util,
        )
    y_agenda -= 18

    c.setFont(SERIF_BOLD, 11)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y_agenda, "Fontes e metodologia")
    y_fontes = y_agenda - 14
    for linha in edicao.get("fontes") or []:
        y_fontes = _desenhar_paragrafo(c, f"• {linha}", MARGEM, y_fontes, largura_util, fonte=SANS, tamanho=7, cor=CINZA_EDITORIAL)
        y_fontes -= 2

    y_fontes -= 8
    c.setFont(SERIF_BOLD, 9)
    c.setFillColor(AZUL_MARINHO)
    c.drawString(MARGEM, y_fontes, "Limitações")
    y_fontes -= 12
    for linha in edicao.get("limitacoes") or []:
        y_fontes = _desenhar_paragrafo(c, f"• {linha}", MARGEM, y_fontes, largura_util, fonte=SANS, tamanho=7, cor=CINZA_EDITORIAL)
        y_fontes -= 2

    _rodape(c, agora, 4, 4)


def gerar_pdf(edicao: dict) -> bytes:
    """Monta as 4 páginas editoriais e devolve os bytes do PDF - nunca
    escreve em disco (o chamador decide o destino: anexo de e-mail, ou um
    arquivo local em uso manual/teste). Levanta a exceção original em
    qualquer falha de desenho (nunca mascara um bug de layout) - quem chama
    (jobs/morning_call.py) decide degradar pra envio sem anexo."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Pregão Morning Call — {edicao['agora'].strftime('%d/%m/%Y')}")
    c.setAuthor("Pregão")
    _pagina_capa(c, edicao)
    c.showPage()
    _pagina_brasil(c, edicao)
    c.showPage()
    _pagina_exterior(c, edicao)
    c.showPage()
    _pagina_empresas(c, edicao)
    c.showPage()
    c.save()
    return buffer.getvalue()


def gerar_pdf_do_momento(agora=None) -> bytes:
    """Conveniência pra uso manual/CLI: monta a edição (dados reais) e
    gera o PDF numa chamada só. jobs/morning_call.py NÃO usa esta função -
    chama montar_edicao()/gerar_pdf() separadamente pra poder tratar a
    falha de cada etapa com o log específico dela."""
    from data.morning_call_editorial import montar_edicao
    return gerar_pdf(montar_edicao(agora))
