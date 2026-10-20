# -*- coding: utf-8 -*-
"""Camada de apresentação (ReportLab/Platypus) do Morning Call em PDF.

Consome SÓ o dict devolvido por data/morning_call_editorial.py:montar_edicao
- nunca chama provedor de dado nenhum (dados != layout). A única chamada de
rede daqui é o download best-effort da foto de uma matéria já validada como
imagem editorial por data/news.py; qualquer falha = matéria sem foto (nunca
um placeholder).

Direção editorial (redesenho de 2026-10-18): jornal econômico, não
dashboard. Papel branco, texto em grafite, uma serifada editorial (Source
Serif 4) pra manchete e corpo, uma sans (Libre Franklin) só pra rótulos,
legendas e fontes, e a mono do terminal (IBM Plex Mono) pra números. Linhas
finas no lugar de caixas; âmbar do Pregão (#FFA028) só como acento (filete
do masthead, marcador de editoria, ponto final do gráfico). Vermelho/verde
só em variação de preço.

Paginação feita pelo Platypus (não por coordenadas fixas): colunas
balanceadas por editoria, manchete sempre presa ao primeiro parágrafo (nunca
órfã no pé da coluna), parágrafos sem linha órfã/viúva, e o número de
páginas decorre do conteúdo (a camada de dados já limita a extensão).
"""
import io
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, FrameBreak, Image as ImagemFlowable, KeepTogether,
    NextPageTemplate, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

try:
    import requests
except Exception:  # pragma: no cover - requests já é dependência do projeto
    requests = None

try:
    from PIL import Image
except Exception:  # pragma: no cover - Pillow já é dependência transitiva (streamlit)
    Image = None

PAGINA_LARGURA, PAGINA_ALTURA = A4
MM = 2.834645669
MARGEM_X = 17 * MM
MARGEM_TOPO = 16 * MM
MARGEM_BASE = 15 * MM
LARGURA_UTIL = PAGINA_LARGURA - 2 * MARGEM_X
ALTURA_UTIL_INTERNA = PAGINA_ALTURA - MARGEM_TOPO - 24 - MARGEM_BASE - 4
ENTRE_COLUNAS = 6 * MM

# Paleta - papel branco, tinta grafite; âmbar só como acento.
TINTA = HexColor("#161514")
TINTA_SUAVE = HexColor("#3B3835")
CINZA = HexColor("#6F6A63")
FILETE = HexColor("#CFC9BF")
AMBAR = HexColor("#FFA028")
ALTA = HexColor("#1E7A4C")
BAIXA = HexColor("#B4291F")

_DIR_FONTES = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_ARQUIVOS_FONTE = {
    "PregaoDisplay": "SourceSerif4Display-Bold.ttf",
    "PregaoDisplaySemi": "SourceSerif4Display-SemiBold.ttf",
    "PregaoDisplayItalico": "SourceSerif4Display-Italic.ttf",
    "PregaoSerif": "SourceSerif4Text-Regular.ttf",
    "PregaoSerifSemi": "SourceSerif4Text-SemiBold.ttf",
    "PregaoSerifItalico": "SourceSerif4Text-Italic.ttf",
    "PregaoSans": "LibreFranklin-Regular.ttf",
    "PregaoSansMedia": "LibreFranklin-Medium.ttf",
    "PregaoSansNegrito": "LibreFranklin-Bold.ttf",
    "PregaoMono": "IBMPlexMono-Regular.ttf",
    "PregaoMonoMedia": "IBMPlexMono-Medium.ttf",
}
# Fallback base-14 (sem acento garantido em todos os leitores, mas o PDF
# ainda sai) se os arquivos de fonte faltarem no ambiente - o e-mail nunca
# deixa de levar o anexo por causa de fonte.
_FALLBACK_BASE14 = {
    "PregaoDisplay": "Times-Bold", "PregaoDisplaySemi": "Times-Bold",
    "PregaoDisplayItalico": "Times-Italic", "PregaoSerif": "Times-Roman",
    "PregaoSerifSemi": "Times-Bold", "PregaoSerifItalico": "Times-Italic",
    "PregaoSans": "Helvetica", "PregaoSansMedia": "Helvetica", "PregaoSansNegrito": "Helvetica-Bold",
    "PregaoMono": "Courier", "PregaoMonoMedia": "Courier-Bold",
}
F = dict(_FALLBACK_BASE14)
FONTES_EMBUTIDAS = False


def _registrar_fontes():
    """Registra as TTF de assets/fonts (embutidas e subsetadas pelo
    ReportLab no PDF). Idempotente. Falha -> mantém o fallback base-14."""
    global FONTES_EMBUTIDAS
    if FONTES_EMBUTIDAS:
        return True
    try:
        registradas = set(pdfmetrics.getRegisteredFontNames())
        for nome, arquivo in _ARQUIVOS_FONTE.items():
            if nome not in registradas:
                pdfmetrics.registerFont(TTFont(nome, str(_DIR_FONTES / arquivo)))
        pdfmetrics.registerFontFamily("PregaoSerif", normal="PregaoSerif", bold="PregaoSerifSemi",
                                      italic="PregaoSerifItalico", boldItalic="PregaoSerifSemi")
        pdfmetrics.registerFontFamily("PregaoSans", normal="PregaoSans", bold="PregaoSansNegrito",
                                      italic="PregaoSans", boldItalic="PregaoSansNegrito")
        F.update({nome: nome for nome in _ARQUIVOS_FONTE})
        FONTES_EMBUTIDAS = True
    except Exception as exc:
        print(f"[morning_call_pdf] fontes de assets/fonts indisponíveis ({exc!r}) - usando base-14")
    return FONTES_EMBUTIDAS


_DIAS_SEMANA_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
_MESES_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
)
_MESES_CURTOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _data_extenso_pt_br(agora):
    """'Segunda-feira, 19 de outubro de 2026' sem depender de locale do SO
    (no runner do GitHub Actions, sem pt_BR, strftime('%A') sai em inglês)."""
    dia_semana = _DIAS_SEMANA_PT[agora.weekday()]
    mes = _MESES_PT[agora.month - 1]
    return f"{dia_semana.capitalize()}, {agora.day} de {mes} de {agora.year}"


# ============================================================
# Números
# ============================================================

def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def _casas_ativo(nome, preco):
    """Casas decimais por tipo de ativo - índice de ações sem centavos,
    câmbio com 4 (padrão de mesa), o resto com 2."""
    nome_baixo = (nome or "").lower()
    if "dólar" in nome_baixo or "usd" in nome_baixo:
        return 4
    if "ibovespa" in nome_baixo:
        return 0
    return 2


def _prefixo_ativo(nome):
    nome_baixo = (nome or "").lower()
    if "dólar" in nome_baixo or "usd" in nome_baixo:
        return "R$ "
    if "petróleo" in nome_baixo or "ouro" in nome_baixo:
        return "US$ "
    return ""


def _texto_variacao(variacao_pct):
    """Sinal sempre explícito, com o sinal de menos tipográfico (U+2212)."""
    if variacao_pct is None:
        return "—"
    if abs(variacao_pct) < 0.005:
        return "0,00%"
    sinal = "+" if variacao_pct > 0 else "−"
    return f"{sinal}{_fmt_num(abs(variacao_pct))}%"


def _cor_variacao(variacao_pct):
    if variacao_pct is None or abs(variacao_pct) < 0.005:
        return CINZA
    return ALTA if variacao_pct > 0 else BAIXA


def _nome_curto_ativo(nome):
    return {"Dólar (USD/BRL)": "Dólar", "S&P 500 futuro": "S&P 500 fut.", "Nasdaq futuro": "Nasdaq fut.",
            "Petróleo Brent": "Brent"}.get(nome, nome)


def _referencia_curta(barra_fmt):
    """'17/10 17:00 (horário de Brasília)' -> '17/10 17:00'."""
    if not barra_fmt:
        return "—"
    return str(barra_fmt).replace("(horário de Brasília)", "").strip()


# ============================================================
# Estilos tipográficos
# ============================================================

def _estilos():
    e = {}

    def estilo(nome, **kw):
        base = dict(fontName=F["PregaoSerif"], fontSize=9.4, leading=12.9, textColor=TINTA,
                    allowWidows=0, allowOrphans=0)
        base.update(kw)
        e[nome] = ParagraphStyle(nome, **base)

    estilo("manchete_capa", fontName=F["PregaoDisplay"], fontSize=29, leading=31.5, spaceAfter=6)
    estilo("linha_fina_capa", fontName=F["PregaoDisplayItalico"], fontSize=12.5, leading=16.2,
           textColor=TINTA_SUAVE, spaceAfter=10)
    estilo("manchete_abre", fontName=F["PregaoDisplaySemi"], fontSize=19, leading=22, spaceAfter=5)
    estilo("linha_fina", fontName=F["PregaoDisplayItalico"], fontSize=11.2, leading=14.6,
           textColor=TINTA_SUAVE, spaceAfter=7)
    estilo("manchete", fontName=F["PregaoDisplaySemi"], fontSize=14, leading=16.6, spaceAfter=4)
    estilo("manchete_coluna", fontName=F["PregaoDisplaySemi"], fontSize=17.5, leading=20.4, spaceAfter=5)
    estilo("chamada", fontName=F["PregaoDisplaySemi"], fontSize=13, leading=15.4, spaceAfter=3)
    estilo("corpo", alignment=TA_JUSTIFY)
    estilo("corpo_seguinte", alignment=TA_JUSTIFY, firstLineIndent=9)
    estilo("corpo_estreito", alignment=TA_LEFT)
    estilo("corpo_estreito_seguinte", alignment=TA_LEFT, firstLineIndent=9)
    estilo("corpo_chamada", fontSize=9, leading=12.2, textColor=TINTA_SUAVE)
    estilo("curta", fontName=F["PregaoSerifSemi"], fontSize=9.8, leading=12.4, spaceAfter=1.5)
    estilo("fonte", fontName=F["PregaoSans"], fontSize=6.9, leading=9, textColor=CINZA, spaceBefore=3)
    estilo("nota", fontName=F["PregaoSans"], fontSize=7.2, leading=9.8, textColor=CINZA)
    estilo("aviso", fontName=F["PregaoSerifItalico"], fontSize=9.4, leading=12.9, textColor=CINZA)
    estilo("tabela", fontName=F["PregaoSans"], fontSize=8.1, leading=10.6)
    estilo("tabela_num", fontName=F["PregaoMono"], fontSize=8, leading=10.2, alignment=TA_RIGHT)
    estilo("tabela_num_texto", fontName=F["PregaoSans"], fontSize=8, leading=10.2, alignment=TA_RIGHT,
           textColor=CINZA)
    estilo("tabela_cab", fontName=F["PregaoSansMedia"], fontSize=6.6, leading=8.4, textColor=CINZA)
    estilo("tabela_cab_num", fontName=F["PregaoSansMedia"], fontSize=6.6, leading=8.4, textColor=CINZA,
           alignment=TA_RIGHT)
    estilo("indice", fontName=F["PregaoSans"], fontSize=8, leading=12.5, textColor=TINTA_SUAVE)
    estilo("remissao", fontName=F["PregaoSansMedia"], fontSize=7, leading=9, textColor=TINTA, spaceBefore=2)
    # radar setorial: 4 blocos de ~130 palavras precisam caber 2 por coluna
    estilo("radar_corpo", fontSize=8.7, leading=11.3, alignment=TA_LEFT)
    estilo("radar_rotulo", fontName=F["PregaoSansNegrito"], fontSize=6.4, leading=8, textColor=CINZA,
           spaceBefore=4, spaceAfter=1.5)
    estilo("subtitulo_secao", fontName=F["PregaoSansNegrito"], fontSize=7.2, leading=9.5, textColor=TINTA,
           spaceBefore=6, spaceAfter=6)
    return e


# ============================================================
# Flowables próprios
# ============================================================

class Filete(Flowable):
    """Linha horizontal fina - substitui as caixas/cards do layout antigo."""

    def __init__(self, espessura=0.4, cor=FILETE, antes=6, depois=6, largura=None):
        super().__init__()
        self.espessura, self.cor, self.antes, self.depois, self.largura_fixa = espessura, cor, antes, depois, largura

    def wrap(self, largura_disp, altura_disp):
        self.largura = self.largura_fixa or largura_disp
        return self.largura, self.antes + self.espessura + self.depois

    def draw(self):
        self.canv.setStrokeColor(self.cor)
        self.canv.setLineWidth(self.espessura)
        y = self.depois + self.espessura / 2
        self.canv.line(0, y, self.largura, y)


class CabecalhoEditoria(Flowable):
    """Abertura de editoria: filete preto de largura total, marcador âmbar
    e o nome da editoria em versaletes espaçados - a mesma assinatura em
    todas as editorias (consistência), sem caixa nem fundo. Registra a
    página em que caiu, pro índice da capa."""

    ALTURA = 30

    def __init__(self, nome, chave, registro, nota=None):
        super().__init__()
        self.nome, self.chave, self.registro, self.nota = nome, chave, registro, nota
        self.keepWithNext = 1

    def wrap(self, largura_disp, altura_disp):
        self.largura = largura_disp
        return largura_disp, self.ALTURA

    def draw(self):
        c = self.canv
        if self.registro is not None:
            self.registro.setdefault("paginas", {})[self.chave] = c.getPageNumber()
            self.registro.setdefault("cabecalhos", []).append(
                (self.chave, c.getPageNumber(), c.absolutePosition(0, 0)[1]))
        topo = self.ALTURA - 2
        c.setStrokeColor(TINTA)
        c.setLineWidth(1.6)
        c.line(0, topo, self.largura, topo)
        c.setFillColor(AMBAR)
        c.rect(0, topo - 16, 3.2, 10, stroke=0, fill=1)
        c.setFillColor(TINTA)
        c.setFont(F["PregaoSansNegrito"], 9.5)
        c.drawString(9, topo - 14.2, _espacar(self.nome.upper()))
        if self.nota:
            c.setFont(F["PregaoSans"], 7)
            c.setFillColor(CINZA)
            c.drawRightString(self.largura, topo - 13.8, self.nota)


class GraficoLinha(Flowable):
    """Gráfico de linha vetorial (nunca imagem rasterizada) a partir de uma
    série REAL [(data, valor)] - sem ponto inventado. Eixo mínimo: 3 linhas
    de grade finas com o valor na margem direita (mono), datas inicial e
    final, último ponto marcado em âmbar."""

    def __init__(self, serie, altura=96, casas=0, titulo="", fonte=""):
        super().__init__()
        self.serie = [(d, float(v)) for d, v in serie]
        self.altura_graf = altura
        self.casas = casas
        self.titulo = titulo
        self.fonte = fonte

    def wrap(self, largura_disp, altura_disp):
        self.largura = largura_disp
        return largura_disp, self.altura_graf + 32

    def draw(self):
        c = self.canv
        valores = [v for _, v in self.serie]
        minimo, maximo = min(valores), max(valores)
        folga = (maximo - minimo) * 0.08 or 1.0
        lo, hi = minimo - folga, maximo + folga
        margem_dir = 44
        largura_plot = self.largura - margem_dir
        base = 14
        topo = base + self.altura_graf

        c.setFont(F["PregaoSansNegrito"], 7.2)
        c.setFillColor(TINTA)
        c.drawString(0, topo + 8, self.titulo)
        c.setFont(F["PregaoMono"], 6.4)
        for frac in (0.0, 0.5, 1.0):
            valor = lo + (hi - lo) * frac
            y = base + self.altura_graf * frac
            c.setStrokeColor(FILETE)
            c.setLineWidth(0.35)
            c.line(0, y, largura_plot, y)
            c.setFillColor(CINZA)
            c.drawRightString(self.largura, y - 2.2, _fmt_num(valor, self.casas))

        n = len(valores)
        pontos = [(largura_plot * i / (n - 1), base + self.altura_graf * (v - lo) / (hi - lo))
                  for i, v in enumerate(valores)]
        c.setStrokeColor(TINTA)
        c.setLineWidth(1.1)
        caminho = c.beginPath()
        caminho.moveTo(*pontos[0])
        for p in pontos[1:]:
            caminho.lineTo(*p)
        c.drawPath(caminho, stroke=1, fill=0)
        c.setFillColor(AMBAR)
        c.circle(pontos[-1][0], pontos[-1][1], 2.3, stroke=0, fill=1)

        c.setFont(F["PregaoSans"], 6.4)
        c.setFillColor(CINZA)
        c.drawString(0, base - 9, _data_curta(self.serie[0][0]))
        c.drawRightString(largura_plot, base - 9, _data_curta(self.serie[-1][0]))


class Rotulo(Flowable):
    """Rótulo em versalete espaçado (editoria de chamada, 'NESTA EDIÇÃO')
    desenhado direto no canvas - dentro de um Paragraph o espaçamento
    entre letras é normalizado e as palavras grudam."""

    def __init__(self, texto, cor=CINZA, tamanho=6.8, depois=3):
        super().__init__()
        self.texto, self.cor, self.tamanho, self.depois = texto, cor, tamanho, depois

    def wrap(self, largura_disp, altura_disp):
        return largura_disp, self.tamanho + 2 + self.depois

    def draw(self):
        self.canv.setFont(F["PregaoSansNegrito"], self.tamanho)
        self.canv.setFillColor(self.cor)
        self.canv.drawString(0, self.depois + 1, _espacar(self.texto.upper()))


class Marcador(Flowable):
    """Flowable de altura zero que registra (página, y) de um ponto do fluxo
    - usado pelos testes de paginação (manchete e 1º parágrafo da mesma
    matéria sempre na mesma página/coluna)."""

    def __init__(self, registro, rotulo):
        super().__init__()
        self.registro, self.rotulo = registro, rotulo

    def wrap(self, *_a):
        return 0, 0

    def draw(self):
        if self.registro is not None:
            self.registro.setdefault("marcas", []).append(
                (self.rotulo, self.canv.getPageNumber(), self.canv.absolutePosition(0, 0)))


class Grupo:
    """Unidade indivisível dentro de Colunas (ex.: manchete + 1º parágrafo
    - a manchete nunca fica órfã no pé de uma coluna). Só é quebrada se
    for maior que uma coluna inteira vazia."""

    def __init__(self, flows):
        self.flows = [f for f in flows if f is not None]


def _altura_flow(f, largura):
    _, h = f.wrap(largura, PAGINA_ALTURA * 4)
    return h + f.getSpaceBefore() + f.getSpaceAfter()


def _encher_coluna(unidades, largura, altura):
    """Coloca unidades numa coluna de `altura` - devolve (colocados,
    restantes). Paragraph é quebrado pelo próprio split do ReportLab
    (respeita allowOrphans/allowWidows=0 dos estilos); Grupo que não cabe
    vai inteiro pra próxima coluna, salvo se a coluna estiver vazia."""
    colocados, usado = [], 0.0
    fila = list(unidades)
    while fila:
        u = fila.pop(0)
        if not colocados and isinstance(u, Filete):
            continue  # separador nunca abre uma coluna
        livre = altura - usado
        if isinstance(u, Grupo):
            h = sum(_altura_flow(f, largura) for f in u.flows)
            if h <= livre + 0.01:
                colocados += u.flows
                usado += h
                continue
            if colocados or h <= ALTURA_UTIL_INTERNA:
                # não cabe aqui, mas cabe numa coluna de página inteira:
                # vai inteiro pra próxima coluna/página (nunca deixa a
                # manchete órfã no pé da página)
                fila.insert(0, u)
                break
            # grupo maior que uma coluna de página inteira: única situação
            # em que vira fluxo comum (quebrável)
            fila = list(u.flows) + fila
            continue
        h = _altura_flow(u, largura)
        if h <= livre + 0.01:
            colocados.append(u)
            usado += h
            continue
        partes = u.split(largura, livre - u.getSpaceBefore()) if livre > 20 else []
        if partes and len(partes) > 1:
            primeira = partes[0]
            colocados.append(primeira)
            usado += _altura_flow(primeira, largura)
            fila = partes[1:] + fila
        else:
            fila.insert(0, u)
        break
    return colocados, fila


def _colunas_ou_corrido(unidades):
    """Texto de uma unidade só (ex.: um parágrafo + fonte) em 2 colunas
    deixa uma delas vazia - nesse caso vai corrido, na largura toda."""
    if len(unidades) == 1:
        u = unidades[0]
        return list(u.flows) if isinstance(u, Grupo) else [u]
    return [Colunas(unidades)] if unidades else []


class Colunas(Flowable):
    """N colunas que se equilibram quando o conteúdo cabe na página e
    continuam na página seguinte quando não cabe (split). Substitui o
    BalancedColumns do ReportLab, que quebrava página a cada matéria."""

    def __init__(self, unidades, n=2, espaco=ENTRE_COLUNAS, fixas=None):
        super().__init__()
        self.unidades = list(unidades)
        self.n = n
        self.espaco = espaco
        self.fixas = fixas  # lista de listas: uma lista de flows por coluna, sem equilibrar
        self._layout = None

    def _largura_coluna(self, largura):
        return (largura - self.espaco * (self.n - 1)) / self.n

    def _distribuir(self, largura, altura):
        lc = self._largura_coluna(largura)
        restantes = list(self.unidades)
        colunas = []
        for _ in range(self.n):
            colocados, restantes = _encher_coluna(restantes, lc, altura)
            colunas.append(colocados)
        return colunas, restantes

    def wrap(self, largura_disp, altura_disp):
        self.largura = largura_disp
        lc = self._largura_coluna(largura_disp)
        if self.fixas is not None:
            self._layout = [list(c) for c in self.fixas]
            altura = max((sum(_altura_flow(f, lc) for f in c) for c in self._layout), default=0)
            self.altura = altura
            return largura_disp, altura
        total = 0.0
        for u in self.unidades:
            total += sum(_altura_flow(f, lc) for f in (u.flows if isinstance(u, Grupo) else [u]))
        # menor altura em que tudo cabe nas n colunas - começando de
        # total/n, mas nunca abaixo da maior unidade indivisível (senão um
        # Grupo pequeno seria partido só pra "equilibrar")
        maior_grupo = max((sum(_altura_flow(f, lc) for f in u.flows) for u in self.unidades
                           if isinstance(u, Grupo)), default=0)
        alvo = max(total / self.n, min(maior_grupo, altura_disp))
        while alvo <= altura_disp + 0.5:
            colunas, restantes = self._distribuir(largura_disp, alvo)
            if not restantes:
                self._layout = colunas
                self.altura = max(sum(_altura_flow(f, lc) for f in c) for c in colunas)
                return largura_disp, self.altura
            alvo += 6
        self._layout = None
        self.altura = total
        return largura_disp, total  # maior que o disponível -> o Frame chama split()

    def split(self, largura_disp, altura_disp):
        if self.fixas is not None:
            return []
        colunas, restantes = self._distribuir(largura_disp, altura_disp)
        if not any(colunas):
            return []
        cheia = Colunas([], n=self.n, espaco=self.espaco, fixas=colunas)
        if not restantes:
            return [cheia]
        return [cheia, Colunas(restantes, n=self.n, espaco=self.espaco)]

    def draw(self):
        lc = self._largura_coluna(self.largura)
        for i, coluna in enumerate(self._layout or []):
            x = i * (lc + self.espaco)
            y = self.altura
            for f in coluna:
                _, h = f.wrap(lc, PAGINA_ALTURA * 4)
                y -= f.getSpaceBefore() + h
                f.drawOn(self.canv, x, y)
                y -= f.getSpaceAfter()


def _espacar(texto, espacos=1):
    """Versaletes 'espaçados' sem depender de charSpace (que o
    drawString do ReportLab aplica de forma inconsistente entre leitores):
    insere espaço fino (U+2009) entre letras."""
    sep = "\u2009" * espacos
    return " \u2009\u2009".join(sep.join(palavra) for palavra in texto.split())


def _data_curta(valor):
    try:
        if isinstance(valor, str):
            valor = datetime.fromisoformat(valor)
        return f"{valor.day} {_MESES_CURTOS[valor.month - 1]}"
    except Exception:
        return ""


def _momento_publicacao(iso, agora):
    """'17 out, 18h42' (ou só '18h42' se for do mesmo dia da edição)."""
    if not iso:
        return ""
    try:
        quando = datetime.fromisoformat(str(iso))
        if quando.tzinfo is not None and agora.tzinfo is not None:
            quando = quando.astimezone(agora.tzinfo)
    except ValueError:
        return ""
    hora = f"{quando.hour}h{quando.minute:02d}"
    if quando.date() == agora.date():
        return hora
    return f"{quando.day} {_MESES_CURTOS[quando.month - 1]}, {hora}"


# ============================================================
# Texto
# ============================================================

def _t(texto):
    """Escapa texto vindo de fonte externa pra markup do Paragraph."""
    return escape(str(texto or "").strip())


_RE_FIM_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9\"“])")


def _dividir_linha_fina(corpo):
    """(linha_fina, paragrafos_restantes) - a linha-fina da manchete é a
    PRIMEIRA FRASE do próprio texto da matéria (nunca um texto novo), e
    ela sai do corpo pra não se repetir logo abaixo. Frase curta demais
    (< 60 caracteres) ou texto de uma frase só não vira linha-fina."""
    if not corpo:
        return None, []
    primeiro = corpo[0].strip()
    partes = _RE_FIM_FRASE.split(primeiro, maxsplit=1)
    if len(partes) < 2 and len(corpo) < 2:
        return None, list(corpo)
    frase = partes[0].strip()
    if len(frase) < 60:
        return None, list(corpo)
    resto_primeiro = partes[1].strip() if len(partes) > 1 else ""
    restantes = ([resto_primeiro] if resto_primeiro else []) + [p for p in corpo[1:] if p.strip()]
    return frase, restantes


def _linha_fonte(item, agora, estilos):
    """'INFOMONEY · 17 out, 18h42 · texto completo' - o veículo original
    sempre visível; o link (quando existe) vai no próprio nome do veículo e
    em 'texto completo'. Nunca inventa veículo nem URL."""
    partes = []
    veiculo = item.get("veiculo")
    link = item.get("link_original") or item.get("link")
    link_valido = link if link and str(link).startswith(("http://", "https://")) else None
    if veiculo:
        rotulo = _t(veiculo.upper())
        partes.append(f'<a href="{escape(link_valido, {'"': "&quot;"})}" color="#3B3835">{rotulo}</a>' if link_valido else rotulo)
    momento = _momento_publicacao(item.get("data"), agora)
    if momento:
        partes.append(_t(momento))
    if link_valido:
        partes.append(f'<a href="{escape(link_valido, {'"': "&quot;"})}" color="#6F6A63"><u>texto completo</u></a>')
    if not partes:
        return None
    return Paragraph(" · ".join(partes), estilos["fonte"])


# ============================================================
# Imagens (best-effort, só da matéria)
# ============================================================

_HEADERS_IMAGEM = {"User-Agent": "Mozilla/5.0 (compatible; PregaoBot/1.0)"}


def _baixar_imagem_card(url, timeout=(3, 6), tamanho_max=4_000_000):
    """Download best-effort de uma foto já validada por data/news.py no
    momento do cache; reconfere Content-Type e tamanho. Falha -> None."""
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


def _foto(item, largura, estilos, altura_max=None):
    """[Imagem, crédito] proporcional (nunca distorcida) ou [] - foto
    pequena demais pra largura (seria ampliada e ficaria borrada) é
    descartada em vez de publicada."""
    bruto = _baixar_imagem_card(item.get("imagem"))
    if not bruto:
        return []
    try:
        leitor = ImageReader(io.BytesIO(bruto))
        w, h = leitor.getSize()
        if w < 480 or h < 240:
            return []
        altura = largura * h / w
        if altura_max and altura > altura_max:
            altura = altura_max
            largura_img = altura * w / h
        else:
            largura_img = largura
        img = ImagemFlowable(io.BytesIO(bruto), width=largura_img, height=altura)
        img.hAlign = "LEFT"
        credito = f"Foto: reprodução/{_t(item.get('veiculo'))}" if item.get("veiculo") else "Foto: reprodução"
        return [img, Paragraph(credito, estilos["nota"]), Spacer(1, 6)]
    except Exception:
        return []


# ============================================================
# Matérias
# ============================================================

def _texto_materia(item, estilos, registro, com_linha_fina):
    """(cabeça, parágrafos) de uma matéria: cabeça = linha-fina opcional;
    parágrafos = corpo restante (a 1ª frase vira linha-fina só quando
    `com_linha_fina`, e então sai do corpo pra não se repetir)."""
    if com_linha_fina:
        linha_fina, paragrafos = _dividir_linha_fina(item.get("corpo") or [])
    else:
        linha_fina, paragrafos = None, list(item.get("corpo") or [])
    return linha_fina, [p for p in paragrafos if p.strip()]


def _texto_longo(item, estilos, limite=7):
    """True se o corpo da matéria (sem a linha-fina) passa de `limite`
    linhas numa coluna - só então ela ganha abertura própria em largura
    total com texto em 2 colunas; texto curto em 2 colunas deixava uma
    coluna só com a linha da fonte."""
    _, paragrafos = _dividir_linha_fina(item.get("corpo") or [])
    lc = (LARGURA_UTIL - ENTRE_COLUNAS) / 2
    altura = sum(_altura_flow(Paragraph(_t(p), estilos["corpo"]), lc) for p in paragrafos if p.strip())
    return altura > limite * estilos["corpo"].leading


def _unidades_materia(item, agora, estilos, registro, estilo_manchete="manchete"):
    """Matéria comum dentro de Colunas: Grupo(manchete + 1º parágrafo) -
    nunca manchete órfã - e os parágrafos seguintes soltos (quebram entre
    colunas sem órfã/viúva)."""
    titulo = item.get("titulo") or ""
    _, paragrafos = _texto_materia(item, estilos, registro, com_linha_fina=False)
    cabeca = [Marcador(registro, ("manchete", titulo)), Paragraph(_t(titulo), estilos[estilo_manchete])]
    unidades = []
    fonte = _linha_fonte(item, agora, estilos)
    if paragrafos:
        cabeca += [Marcador(registro, ("corpo", titulo)), Paragraph(_t(paragrafos[0]), estilos["corpo"])]
        resto = [Paragraph(_t(p), estilos["corpo_seguinte"]) for p in paragrafos[1:]]
        unidades.append(Grupo(cabeca))
        unidades += resto
    else:
        unidades.append(Grupo(cabeca))
    return _prender_fonte(unidades, fonte)


def _prender_fonte(unidades, fonte):
    """A linha de fonte nunca fica sozinha no topo de uma coluna: vai no
    mesmo Grupo do último parágrafo da matéria."""
    if fonte is None:
        return unidades
    if unidades and isinstance(unidades[-1], Grupo):
        unidades[-1].flows.append(fonte)
    elif unidades:
        unidades[-1] = Grupo([unidades[-1], fonte])
    else:
        unidades.append(Grupo([fonte]))
    return unidades


def _unidade_curta(item, agora, estilos):
    """Nota curta: matéria sem texto publicável (sem resumo cacheado) -
    só manchete e fonte, nunca um texto inventado pra preencher."""
    flows = [Paragraph(_t(item.get("titulo")), estilos["curta"])]
    fonte = _linha_fonte(item, agora, estilos)
    if fonte is not None:
        flows.append(fonte)
    flows.append(Spacer(1, 7))
    return Grupo(flows)


def _bloco_abre(item, agora, estilos, registro, estilo_manchete, estilo_linha_fina, largura_texto,
                altura_foto_max=170, estilo_corpo="corpo"):
    """Matéria de abertura: manchete + linha-fina em largura total e o
    texto em 2 colunas equilibradas (com a foto no topo da 1ª, se houver
    uma foto editorial válida)."""
    titulo = item.get("titulo") or ""
    linha_fina, paragrafos = _texto_materia(item, estilos, registro, com_linha_fina=True)
    topo = [Marcador(registro, ("manchete", titulo)), Paragraph(_t(titulo), estilos[estilo_manchete])]
    if linha_fina:
        topo.append(Paragraph(_t(linha_fina), estilos[estilo_linha_fina]))
    lc = (largura_texto - ENTRE_COLUNAS) / 2
    unidades = list(_foto(item, lc, estilos, altura_max=altura_foto_max))
    if paragrafos:
        unidades.append(Grupo([Marcador(registro, ("corpo", titulo)),
                               Paragraph(_t(paragrafos[0]), estilos[estilo_corpo])]))
        unidades += [Paragraph(_t(p), estilos[estilo_corpo + "_seguinte"]) for p in paragrafos[1:]]
    return topo, _prender_fonte(unidades, _linha_fonte(item, agora, estilos))


def _texto_editoria_vazia(janela):
    if janela is not None and hasattr(janela, "strftime"):
        return (f"Nenhuma notícia desta editoria publicada desde {janela.strftime('%d/%m às %H:%M')} "
                "(horário de Brasília) nas fontes consultadas.")
    return "Nenhuma notícia desta editoria nas fontes consultadas para esta edição."


def _editoria(nome, chave, itens, erro, agora, estilos, registro, excluir=None, edicao_janela=None):
    """Uma editoria inteira. A hierarquia vem do conteúdo, não de um molde
    fixo: a matéria mais importante com texto abre a editoria (manchete
    maior, linha-fina, texto em 2 colunas); as demais com texto seguem em
    2 colunas equilibradas; as sem texto viram 'Curtas'."""
    itens = [i for i in (itens or []) if i is not excluir and i.get("titulo")]
    cabecalho = CabecalhoEditoria(nome, chave, registro)
    if not itens:
        if erro:
            aviso = f"Noticiário desta editoria indisponível nesta edição ({_t(erro)})."
        else:
            aviso = _texto_editoria_vazia(edicao_janela)
        return [CondPageBreak(80), KeepTogether([cabecalho, Paragraph(aviso, estilos["aviso"])]), Spacer(1, 16)]

    ordenados = sorted(itens, key=lambda i: i.get("importancia") or 0, reverse=True)
    com_texto = [i for i in ordenados if i.get("corpo")]
    sem_texto = [i for i in ordenados if not i.get("corpo")]
    # nunca abre uma editoria no pé da página: sem espaço pra cabeçalho +
    # a primeira matéria, a editoria começa na página seguinte
    flows = [CondPageBreak(ESPACO_MIN_EDITORIA)]
    primeiro_bloco = [cabecalho]

    if com_texto:
        abre = com_texto[0]
        resto = com_texto[1:]
        if _texto_longo(abre, estilos):
            topo, unidades = _bloco_abre(abre, agora, estilos, registro, "manchete_abre", "linha_fina",
                                         LARGURA_UTIL)
            primeiro_bloco += topo
            flows.append(KeepTogether(primeiro_bloco))
            flows.append(Colunas(unidades))
        else:
            # texto curto demais pra 2 colunas próprias: a matéria mais
            # importante abre o fluxo de colunas com manchete maior
            flows.append(KeepTogether(primeiro_bloco))
            resto = [abre] + resto
            primeiro_bloco = None
        if resto:
            if primeiro_bloco is not None:
                flows.append(Filete(antes=8, depois=9))
            unidades = []
            for n, item in enumerate(resto):
                if n:
                    unidades.append(Filete(antes=6, depois=8))
                destaque = n == 0 and primeiro_bloco is None
                unidades += _unidades_materia(item, agora, estilos, registro,
                                              estilo_manchete="manchete_coluna" if destaque else "manchete")
            flows.append(Colunas(unidades))

    if sem_texto:
        rotulo = Paragraph("CURTAS" if com_texto else "MANCHETES", estilos["subtitulo_secao"])
        notas = [_unidade_curta(item, agora, estilos) for item in sem_texto]
        if com_texto:
            flows.append(Filete(antes=6, depois=4))
            flows.append(KeepTogether([rotulo, Colunas(notas)]) if len(notas) <= 4 else rotulo)
            if len(notas) > 4:
                flows.append(Colunas(notas))
        else:
            flows.append(KeepTogether([cabecalho, rotulo]))
            flows.append(Colunas(notas))
    flows.append(Spacer(1, 18))
    return flows


# ============================================================
# Radar setorial
# ============================================================

def _fato_radar(fonte, estilos):
    """'VALOR ECONÔMICO (16/10): “manchete”.' - veículo com link."""
    link = str(fonte.get("link") or "")
    veiculo = _t(str(fonte.get("veiculo") or "").upper())
    if link.startswith(("http://", "https://")):
        veiculo = f'<a href="{escape(link, {'"': "&quot;"})}" color="#3B3835"><u>{veiculo}</u></a>'
    data = fonte.get("data")
    quando = f" ({data.strftime('%d/%m')})" if hasattr(data, "strftime") else ""
    titulo = _t(str(fonte.get("titulo") or "").rstrip(" ."))
    return Paragraph(f'<font name="{F["PregaoSansMedia"]}" size="7">{veiculo}</font>{quando}: '
                     f'\u201c{titulo}\u201d.', estilos["radar_corpo"])


def _bloco_radar(bloco, estilos):
    def rotulo(texto):
        return Paragraph(texto, estilos["radar_rotulo"])

    flows = [Paragraph(_t(bloco.get("nome")), estilos["manchete"]),
             rotulo("O QUE ACONTECEU")]
    flows += [_fato_radar(f, estilos) for f in bloco.get("fontes") or []]
    flows += [rotulo("POR QUE IMPORTA"),
              Paragraph(_t(bloco.get("por_que_importa")), estilos["radar_corpo"]),
              rotulo("EMPRESAS E ATIVOS RELACIONADOS"),
              Paragraph(_t(bloco.get("empresas")), estilos["radar_corpo"]),
              rotulo("O QUE ACOMPANHAR"),
              Paragraph(_t(bloco.get("acompanhar")), estilos["radar_corpo"]),
              Spacer(1, 3)]
    return Grupo(flows)


def _radar(edicao, estilos, registro):
    """Quatro setores em rodízio (data/radar_setorial.py). Fato (manchetes
    com veículo e data) separado de contexto (textos fixos do catálogo).
    Sem radar ou sem setor com evidência: diz isso, não preenche."""
    if "radar" not in edicao:
        return []
    radar = edicao.get("radar")
    cabecalho = CabecalhoEditoria("Radar setorial", "radar", registro)
    setores = (radar or {}).get("setores") or []
    if not setores:
        aviso = ("Radar setorial indisponível nesta edição." if radar is None else
                 "Nenhum setor do rodízio teve notícias suficientes de fontes verificáveis nesta edição.")
        return [CondPageBreak(80), KeepTogether([cabecalho, Paragraph(aviso, estilos["aviso"])]), Spacer(1, 16)]
    explicacao = Paragraph(
        "Quatro setores por edição, em rodízio. \u201cO que aconteceu\u201d reproduz manchetes publicadas, "
        "com veículo e data; \u201cPor que importa\u201d e \u201cO que acompanhar\u201d são contexto "
        "explicativo fixo do Pregão. Não é recomendação de compra ou venda.", estilos["nota"])
    unidades = []
    for n, bloco in enumerate(setores):
        if n:
            unidades.append(Filete(antes=4, depois=8))
        unidades.append(_bloco_radar(bloco, estilos))
    flows = [CondPageBreak(ESPACO_MIN_EDITORIA), KeepTogether([cabecalho, explicacao, Spacer(1, 6)]),
             Colunas(unidades)]
    excluidos = (radar or {}).get("excluidos") or []
    if excluidos:
        nomes = ", ".join(_t(e.get("nome")) for e in excluidos)
        flows.append(Paragraph(f"Fora desta edição por falta de notícias verificáveis suficientes: {nomes}.",
                               estilos["nota"]))
    flows.append(Spacer(1, 16))
    return flows


# ============================================================
# Mercados (dados) e agenda
# ============================================================

def _estilo_tabela(*extras):
    """TableStyle com a fonte do jornal declarada: sem isso o ReportLab
    declara Helvetica (fonte padrão de tabela) em toda página."""
    return TableStyle([("FONTNAME", (0, 0), (-1, -1), F["PregaoSans"])] + list(extras))


_ESTILO_TABELA_BASE = [
    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 4.0),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4.0),
    ("LINEBELOW", (0, 0), (-1, 0), 0.8, TINTA),
    ("LINEBELOW", (0, 1), (-1, -1), 0.3, FILETE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F7F5F0")]),
]


def _tabela_ativos(indicadores, estilos):
    linhas = [[Paragraph("ATIVO", estilos["tabela_cab"]), Paragraph("ÚLTIMO", estilos["tabela_cab_num"]),
               Paragraph("VAR. DIA", estilos["tabela_cab_num"]), Paragraph("REFERÊNCIA", estilos["tabela_cab_num"])]]
    for ind in indicadores:
        nome = ind.get("nome") or ""
        if ind.get("erro") or ind.get("preco") is None:
            linhas.append([Paragraph(_t(nome), estilos["tabela"]), Paragraph("indisponível", estilos["tabela_num"]),
                           Paragraph("—", estilos["tabela_num"]), Paragraph("—", estilos["tabela_num"])])
            continue
        preco = f"{_prefixo_ativo(nome)}{_fmt_num(ind['preco'], _casas_ativo(nome, ind['preco']))}"
        var = ind.get("variacao_pct")
        cor = _cor_variacao(var).hexval().replace("0x", "#")
        linhas.append([
            Paragraph(_t(nome), estilos["tabela"]),
            Paragraph(_t(preco), estilos["tabela_num"]),
            Paragraph(f'<font color="{cor}">{_t(_texto_variacao(var))}</font>', estilos["tabela_num"]),
            Paragraph(_t(_referencia_curta(ind.get("barra_fmt"))), estilos["tabela_num"]),
        ])
    tabela = Table(linhas, colWidths=[None, 34 * MM, 24 * MM, 28 * MM], hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(*_ESTILO_TABELA_BASE))
    return tabela


def _valor_macro(linha):
    """Linha normalizada de data/morning_call_editorial.py:_macro_rows ->
    texto do valor. Sem valor -> 'indisponível' (nunca um número
    estimado); o motivo vai na nota abaixo da tabela."""
    valor = linha.get("valor")
    if valor is None:
        return "indisponível"
    return f"{_fmt_num(valor)}{linha.get('unidade') or ''}"


def _nota_macro(linhas_macro):
    partes = ["Selic meta e CDI anualizado (base 252): Banco Central, SGS. Focus: mediana das "
              "projeções do mercado para o ano indicado, data do boletim na referência"]
    respondentes = [f"{_t(l.get('indicador'))}: {_t(l['detalhe'])}" for l in linhas_macro
                    if l.get("detalhe") and l.get("valor") is not None]
    if respondentes:
        partes.append("; ".join(respondentes))
    motivos = {}
    for l in linhas_macro:
        if l.get("valor") is None and l.get("erro"):
            motivos.setdefault(str(l["erro"]), []).append(str(l.get("indicador")))
    for motivo, nomes in motivos.items():
        partes.append(f"Indisponível ({_t(', '.join(nomes))}): {_t(motivo)}")
    return ". ".join(partes) + "."


def _tabela_macro(linhas_macro, estilos):
    linhas = [[Paragraph("INDICADOR", estilos["tabela_cab"]), Paragraph("REFERÊNCIA", estilos["tabela_cab"]),
               Paragraph("VALOR", estilos["tabela_cab_num"])]]
    for linha in linhas_macro:
        referencia = str(linha.get("referencia") or "—")
        # "indisponível" em fonte de texto: na mono da coluna numérica a
        # palavra quebrava em duas linhas ("indisponíve / l") na edição real
        estilo_valor = "tabela_num" if linha.get("valor") is not None else "tabela_num_texto"
        linhas.append([Paragraph(_t(linha.get("indicador")), estilos["tabela"]),
                       Paragraph(_t(referencia), estilos["tabela"]),
                       Paragraph(_t(_valor_macro(linha)), estilos[estilo_valor])])
    tabela = Table(linhas, colWidths=[None, 30 * MM, 22 * MM], hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(*_ESTILO_TABELA_BASE))
    return tabela


def _nota_ativos(edicao, ativos):
    partes = ["Referência: horário do último negócio informado pela fonte (horário de Brasília) ou "
              "\u201cfech.\u201d com a data da sessão; variação contra o fechamento da sessão anterior. "
              "Fonte: Yahoo Finance"]
    if any(a.get("nome") == "Dólar (USD/BRL)" for a in ativos):
        partes.append("Dólar: cotação USDBRL=X do mercado internacional, pode diferir do dólar "
                      "à vista negociado no Brasil")
    if edicao.get("mercados_nota"):
        partes.append(str(edicao["mercados_nota"]).rstrip("."))
    return ". ".join(partes) + "."


def _mercados(edicao, estilos, registro):
    brasil = edicao.get("brasil") or {}
    exterior = edicao.get("exterior") or {}
    ativos = [i for i in (brasil.get("indicadores") or []) if "nome" in i] + list(exterior.get("indicadores") or [])
    macro = [i for i in (brasil.get("indicadores") or []) if "indicador" in i]
    if not ativos and not macro:
        return []

    topo, esquerda, direita = [], [], []
    if ativos:
        topo += [Paragraph("BOLSAS, CÂMBIO E COMMODITIES", estilos["subtitulo_secao"]),
                 _tabela_ativos(ativos, estilos),
                 Paragraph(_t(_nota_ativos(edicao, ativos)), estilos["nota"]), Spacer(1, 10)]
    if macro:
        esquerda += [Paragraph("JUROS E EXPECTATIVAS", estilos["subtitulo_secao"]),
                     _tabela_macro(macro, estilos),
                     Paragraph(_nota_macro(macro), estilos["nota"])]

    cabecalho = CabecalhoEditoria("Mercados", "mercados", registro)
    if esquerda and direita:
        baixo = [Colunas([], fixas=[esquerda, direita])]
    else:
        baixo = esquerda + direita
    flows = [CondPageBreak(ESPACO_MIN_EDITORIA), KeepTogether([cabecalho] + topo + baixo)]
    flows.append(Spacer(1, 16))
    return flows


def _texto_agenda_vazia(agora):
    """Sem eventos no calendário NÃO prova que nenhuma empresa divulga
    nada hoje: o calendário do Pregão cobre as empresas do Ibovespa, a
    partir de datas anunciadas e de prazos regulatórios da CVM."""
    base = ("O calendário do Pregão não registra divulgação de resultados de empresas do Ibovespa "
            "para hoje. O calendário reúne datas anunciadas e prazos da CVM e pode não incluir "
            "todos os eventos.")
    if agora is not None and hasattr(agora, "weekday") and agora.weekday() >= 5:
        return "Não há pregão hoje (fim de semana). " + base
    return base


def _agenda(edicao, estilos, registro):
    empresas = edicao.get("empresas") or {}
    agenda = empresas.get("agenda")
    flows = [CabecalhoEditoria("Agenda do dia", "agenda", registro)]
    if agenda is None:
        flows.append(Paragraph("Agenda de resultados indisponível nesta edição.", estilos["aviso"]))
        return flows + [Spacer(1, 14)]
    if not agenda:
        flows.append(Paragraph(_t(_texto_agenda_vazia(edicao.get("agora"))), estilos["aviso"]))
        return flows + [Spacer(1, 14)]
    linhas = [[Paragraph("EMPRESA", estilos["tabela_cab"]), Paragraph("EVENTO", estilos["tabela_cab"]),
               Paragraph("HORÁRIO", estilos["tabela_cab"]), Paragraph("SITUAÇÃO DA DATA", estilos["tabela_cab"])]]
    notas = {}
    for e in agenda:
        empresa = f"{_t(e.get('empresa'))} <font name=\"{F['PregaoMono']}\" size=\"7\" color=\"#6F6A63\">{_t(e.get('ticker'))}</font>"
        evento = " ".join(x for x in (str(e.get("tipo_evento") or "").capitalize(), e.get("periodo") or "") if x)
        linhas.append([Paragraph(empresa, estilos["tabela"]), Paragraph(_t(evento), estilos["tabela"]),
                       Paragraph(_t(e.get("horario")), estilos["tabela"]),
                       Paragraph(_t(str(e.get("status_rotulo") or "").lower()), estilos["tabela"])])
        if e.get("status_rotulo") and e.get("status_nota"):
            notas[str(e["status_rotulo"]).lower()] = e["status_nota"]
    tabela = Table(linhas, colWidths=[None, 38 * MM, 38 * MM, 30 * MM], hAlign="LEFT", repeatRows=1)
    tabela.setStyle(_estilo_tabela(*_ESTILO_TABELA_BASE))
    bloco = flows + [tabela]
    if notas:
        texto = " ".join(f"<i>{_t(k.capitalize())}</i>: {_t(v)}" for k, v in notas.items())
        bloco.append(Paragraph(texto, estilos["nota"]))
    return [KeepTogether(bloco), Spacer(1, 16)]


def _colofao(edicao, estilos, registro, largura=None):
    """Fontes e notas da edição, discretas e no fim (não espalhadas)."""
    fontes = list(edicao.get("fontes") or [])
    limitacoes = list(edicao.get("limitacoes") or [])
    if not fontes and not limitacoes:
        return []
    texto = []
    if fontes:
        texto.append("<b>Fontes.</b> " + " ".join(_t(f) for f in fontes))
    if limitacoes:
        texto.append("<b>Sobre esta edição.</b> " + " ".join(_t(l) for l in limitacoes))
    estilo = ParagraphStyle("colofao", parent=estilos["nota"], fontName=F["PregaoSans"], fontSize=6.6, leading=8.8)
    if largura is not None:  # versão de capa: um parágrafo por bloco, na coluna estreita
        return [Filete(espessura=0.6, cor=TINTA, antes=14, depois=5)] + [
            Paragraph(t, ParagraphStyle("colofao_capa", parent=estilo, spaceAfter=3)) for t in texto]
    return [KeepTogether([Filete(espessura=0.6, cor=TINTA, antes=2, depois=5),
                          Paragraph(" ".join(texto), estilo)])]


# ============================================================
# Capa
# ============================================================

ESPACO_MIN_EDITORIA = 190
ALTURA_MASTHEAD = 112
LARGURA_ESQ_CAPA = 0.66
ALTURA_FAIXA_MERCADOS = 50


def _desenhar_masthead(c, agora):
    topo = PAGINA_ALTURA - MARGEM_TOPO
    c.setFillColor(TINTA)
    c.setFont(F["PregaoSansNegrito"], 7.2)
    c.drawString(MARGEM_X, topo - 7, _espacar("MORNING CALL"))
    c.setFont(F["PregaoSans"], 7.2)
    c.setFillColor(CINZA)
    c.drawRightString(PAGINA_LARGURA - MARGEM_X, topo - 7, "PRÉ-ABERTURA · SÃO PAULO")
    c.setStrokeColor(TINTA)
    c.setLineWidth(0.5)
    c.line(MARGEM_X, topo - 12, PAGINA_LARGURA - MARGEM_X, topo - 12)

    c.setFillColor(TINTA)
    c.setFont(F["PregaoDisplay"], 52)
    c.drawCentredString(PAGINA_LARGURA / 2, topo - 62, _espacar("PREGÃO"))

    y_regua = topo - 78
    c.setStrokeColor(TINTA)
    c.setLineWidth(1.8)
    c.line(MARGEM_X, y_regua, PAGINA_LARGURA - MARGEM_X, y_regua)
    c.setStrokeColor(AMBAR)
    c.setLineWidth(1.8)
    c.line(PAGINA_LARGURA / 2 - 22, y_regua, PAGINA_LARGURA / 2 + 22, y_regua)
    c.setFillColor(TINTA_SUAVE)
    c.setFont(F["PregaoSerifItalico"], 9)
    c.drawString(MARGEM_X, y_regua - 13, _data_extenso_pt_br(agora))
    c.setFont(F["PregaoSans"], 7.2)
    c.setFillColor(CINZA)
    c.drawRightString(PAGINA_LARGURA - MARGEM_X, y_regua - 12.5,
                      f"Edição gerada às {agora.strftime('%H:%M')}, horário de Brasília")
    c.setStrokeColor(TINTA)
    c.setLineWidth(0.5)
    c.line(MARGEM_X, y_regua - 19, PAGINA_LARGURA - MARGEM_X, y_regua - 19)


def _desenhar_faixa_mercados(c, edicao, y_topo):
    """Linha tipográfica de mercado logo abaixo do masthead - nome, valor e
    variação de cada ativo, separados por filetes verticais finos (nunca
    cards). Ativo sem dado aparece como 'indisponível', nunca some."""
    brasil = edicao.get("brasil") or {}
    exterior = edicao.get("exterior") or {}
    ativos = [i for i in (brasil.get("indicadores") or []) if "nome" in i][:2] + list(exterior.get("indicadores") or [])
    if not ativos:
        return
    largura = LARGURA_UTIL / len(ativos)
    y_nome = y_topo - 11
    y_valor = y_topo - 23
    y_var = y_topo - 33
    for n, ind in enumerate(ativos):
        x = MARGEM_X + n * largura
        if n:
            c.setStrokeColor(FILETE)
            c.setLineWidth(0.4)
            c.line(x - 5, y_topo - 36, x - 5, y_topo - 4)
        nome = _nome_curto_ativo(ind.get("nome") or "")
        c.setFont(F["PregaoSansMedia"], 6.6)
        c.setFillColor(CINZA)
        c.drawString(x, y_nome, nome.upper())
        if ind.get("erro") or ind.get("preco") is None:
            c.setFont(F["PregaoSans"], 7.5)
            c.drawString(x, y_valor, "indisponível")
            continue
        valor = _fmt_num(ind["preco"], _casas_ativo(ind.get("nome"), ind["preco"]))
        c.setFont(F["PregaoMonoMedia"], 8.6)
        c.setFillColor(TINTA)
        c.drawString(x, y_valor, valor)
        var = ind.get("variacao_pct")
        c.setFont(F["PregaoMono"], 7.6)
        c.setFillColor(_cor_variacao(var))
        c.drawString(x, y_var, _texto_variacao(var))
    c.setStrokeColor(TINTA)
    c.setLineWidth(0.5)
    c.line(MARGEM_X, y_topo - ALTURA_FAIXA_MERCADOS + 6, PAGINA_LARGURA - MARGEM_X, y_topo - ALTURA_FAIXA_MERCADOS + 6)


_EDITORIA_DE = (("brasil", "Brasil"), ("empresas", "Empresas"), ("exterior", "Mundo"))


def _editoria_do_item(item, edicao):
    for chave, nome in _EDITORIA_DE:
        secao = edicao.get(chave) or {}
        lista = secao.get("cards" if chave == "empresas" else "noticias") or []
        if any(i is item for i in lista):
            return nome
    return None


def _bloco_chamada(item, edicao, agora, estilos, paginas=None, destaque=False):
    """Chamada de capa: editoria, título, primeira frase da matéria (nunca
    texto novo) e remissão 'Brasil, pág. 2' quando a matéria completa
    está dentro; sem texto publicável, a fonte original no lugar."""
    editoria, chave = _editoria_do_item(item, edicao), _chave_do_item(item, edicao)
    bloco = []
    if editoria:
        bloco.append(Rotulo(editoria))
    bloco.append(Paragraph(_t(item.get("titulo")), estilos["manchete" if destaque else "chamada"]))
    corpo = item.get("corpo") or []
    if corpo:
        primeira = _RE_FIM_FRASE.split(corpo[0].strip(), maxsplit=1)[0]
        bloco.append(Paragraph(_t(primeira), estilos["linha_fina" if destaque else "corpo_chamada"]))
    pagina = (paginas or {}).get(chave)
    if corpo and pagina:
        bloco.append(Paragraph(f"{_t(editoria)}, pág. {pagina}", estilos["remissao"]))
    else:
        fonte = _linha_fonte(item, agora, estilos)
        if fonte is not None:
            bloco.append(fonte)
    return bloco


def _chave_do_item(item, edicao):
    for chave, _ in _EDITORIA_DE:
        secao = edicao.get(chave) or {}
        lista = secao.get("cards" if chave == "empresas" else "noticias") or []
        if any(i is item for i in lista):
            return chave
    return None


def _indice(paginas_indice, estilos):
    pag = ParagraphStyle("pag", parent=estilos["indice"], fontName=F["PregaoMono"], alignment=TA_RIGHT)
    linhas = [[Paragraph(_t(nome), estilos["indice"]), Paragraph(str(numero), pag)]
              for nome, numero in paginas_indice]
    tabela = Table(linhas, colWidths=[None, 12 * MM], hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                                   ("LINEBELOW", (0, 0), (-1, -1), 0.3, FILETE)))
    return [Filete(espessura=0.6, cor=TINTA, antes=12, depois=5),
            Rotulo("Nesta edição"), tabela]


def _caber(blocos, largura, altura, fixos_no_fim=()):
    """Mantém os blocos (cada um uma lista de flows) que cabem em `altura`,
    na ordem, sem cortar nenhum ao meio - garante que nada da capa
    transborde pra página 2. `fixos_no_fim` (ex.: índice) sempre entra."""
    reservado = _altura(list(fixos_no_fim), largura) if fixos_no_fim else 0
    saida, usado = [], 0.0
    for bloco in blocos:
        h = _altura(bloco, largura)
        if usado + h + reservado > altura:
            break
        saida += bloco
        usado += h
    return saida + list(fixos_no_fim)


def _capa(edicao, estilos, registro, paginas_indice, altura_colunas, paginas=None):
    """Fluxo da capa. Frame 'topo': manchete + linha-fina em largura total
    (altura medida). Frame 'esquerda' (2/3): texto da manchete em 2 colunas
    e, abaixo, a segunda matéria mais importante com texto. Frame
    'direita' (1/3): chamadas curtas e o índice. Cada coluna é medida e
    só recebe o que cabe inteiro (nunca transborda pra página 2)."""
    agora = edicao["agora"]
    capa = edicao.get("capa") or {}
    manchete = capa.get("manchete")
    chamadas = list(capa.get("chamadas") or [])
    largura_esq = LARGURA_UTIL * LARGURA_ESQ_CAPA
    largura_dir = LARGURA_UTIL - largura_esq - ENTRE_COLUNAS

    topo, blocos_esq = [], []
    if manchete:
        topo_m, unidades = _bloco_abre(manchete, agora, estilos, registro, "manchete_capa", "linha_fina_capa",
                                       largura_esq, altura_foto_max=230, estilo_corpo="corpo_estreito")
        topo = topo_m
        if unidades:
            blocos_esq.append(_colunas_ou_corrido(unidades))
    else:
        erro = (edicao.get("brasil") or {}).get("noticias_erro")
        aviso = ("A coleta de notícias falhou nesta manhã; esta edição traz apenas dados de mercado e agenda."
                 if erro else "Nenhuma notícia confirmada na coleta desta manhã; esta edição traz apenas "
                              "dados de mercado e agenda.")
        topo.append(Paragraph(aviso, estilos["linha_fina_capa"]))

    # segunda matéria (a chamada mais importante COM texto) abaixo da
    # manchete, em 2 colunas - o resto das chamadas vai pra direita
    # Capa de jornal: só a manchete sai na íntegra aqui (e por isso não se
    # repete dentro). As demais são chamadas - título, primeira frase e a
    # remissão pra página onde a matéria completa está.
    secundarias = [c for c in chamadas if c.get("corpo")][:2]
    inicio_secundarias = len(blocos_esq)
    for item in secundarias:
        blocos_esq.append([Filete(antes=10, depois=8)]
                          + _bloco_chamada(item, edicao, agora, estilos, paginas, destaque=True))
    serie = (edicao.get("brasil") or {}).get("historico_ibov") or []
    if len(serie) >= 2:
        blocos_esq.append([Filete(antes=10, depois=8),
                           GraficoLinha(serie, altura=56, casas=0, titulo="IBOVESPA, FECHAMENTO DIÁRIO NO ÚLTIMO MÊS"),
                           Paragraph("Pontos. Fonte: Yahoo Finance.", estilos["nota"])])

    esquerda = _caber(blocos_esq, largura_esq, altura_colunas)
    publicadas = {id(f) for f in esquerda}
    usadas = [item for item, bloco in zip(secundarias, blocos_esq[inicio_secundarias:])
              if all(id(f) in publicadas for f in bloco)]
    chamadas = [c for c in chamadas if not any(c is u for u in usadas)]
    blocos_dir = []
    for n, item in enumerate(chamadas):
        bloco = ([Filete(antes=7, depois=7)] if n else []) + _bloco_chamada(item, edicao, agora, estilos, paginas)
        blocos_dir.append(bloco)
    indice = _indice(paginas_indice, estilos) if paginas_indice else []
    # Fontes e notas da edição: no pé da coluna das chamadas quando cabe
    # (como o expediente de um jornal), senão no fim da edição.
    colofao = _colofao(edicao, estilos, registro, largura=largura_dir)
    fixos = indice + colofao
    if colofao and _altura(fixos, largura_dir) > altura_colunas:
        fixos, colofao_na_capa = indice, False
    else:
        colofao_na_capa = bool(colofao)
    direita = _caber(blocos_dir, largura_dir, altura_colunas, fixos_no_fim=fixos)
    return topo, esquerda, direita, colofao_na_capa


def _altura(flows, largura):
    total = 0
    for f in flows:
        _, h = f.wrap(largura, PAGINA_ALTURA)
        total += h + f.getSpaceBefore() + f.getSpaceAfter()
    return total


# ============================================================
# Documento
# ============================================================

class _Documento(BaseDocTemplate):
    pass


def _cabecalho_interno(edicao):
    agora = edicao["agora"]

    def desenhar(c, doc):
        c.saveState()
        topo = PAGINA_ALTURA - MARGEM_TOPO
        c.setFillColor(TINTA)
        c.setFont(F["PregaoDisplay"], 12.5)
        c.drawString(MARGEM_X, topo - 9, "PREGÃO")
        c.setFont(F["PregaoSans"], 7.2)
        c.setFillColor(CINZA)
        c.drawString(MARGEM_X + stringWidth("PREGÃO", F["PregaoDisplay"], 12.5) + 8, topo - 8.4, "Morning Call")
        c.drawRightString(PAGINA_LARGURA - MARGEM_X, topo - 8.4, _data_extenso_pt_br(agora))
        c.setStrokeColor(TINTA)
        c.setLineWidth(0.5)
        c.line(MARGEM_X, topo - 15, PAGINA_LARGURA - MARGEM_X, topo - 15)
        _rodape(c, doc)
        c.restoreState()
    return desenhar


def _rodape(c, doc):
    c.setFont(F["PregaoMono"], 7)
    c.setFillColor(CINZA)
    c.drawCentredString(PAGINA_LARGURA / 2, MARGEM_BASE - 14, str(c.getPageNumber()))
    c.setFont(F["PregaoSans"], 6.4)
    c.drawString(MARGEM_X, MARGEM_BASE - 14, "Conteúdo informativo; não constitui recomendação de investimento.")


def _montar(edicao, registro, paginas_indice, paginas=None):
    """Uma passada completa de montagem. Devolve os bytes do PDF."""
    estilos = _estilos()
    agora = edicao["agora"]
    buffer = io.BytesIO()
    doc = _Documento(buffer, pagesize=A4, leftMargin=MARGEM_X, rightMargin=MARGEM_X,
                     topMargin=MARGEM_TOPO, bottomMargin=MARGEM_BASE,
                     title=f"Pregão — Morning Call, {agora.strftime('%d/%m/%Y')}", author="Pregão",
                     subject="Morning Call", creator="Pregão",
                     # fonte inicial do canvas: o ReportLab declara
                     # Helvetica em toda página por padrão, mesmo sem usar
                     initialFontName=F["PregaoSans"], initialFontSize=8, initialLeading=10)

    largura_esq = LARGURA_UTIL * LARGURA_ESQ_CAPA
    largura_dir = LARGURA_UTIL - largura_esq - ENTRE_COLUNAS
    base = MARGEM_BASE + 4
    y_conteudo = PAGINA_ALTURA - MARGEM_TOPO - ALTURA_MASTHEAD - ALTURA_FAIXA_MERCADOS
    # 1ª medida só do topo (manchete + linha-fina), pra saber quanto sobra
    # pras colunas; depois monta a capa já com essa altura disponível
    topo_previa, _, _, _ = _capa(edicao, estilos, None, [], altura_colunas=PAGINA_ALTURA)
    altura_topo = _altura(topo_previa, LARGURA_UTIL) + 4 if topo_previa else 0
    y_colunas = y_conteudo - altura_topo
    topo, esquerda, direita, colofao_na_capa = _capa(edicao, estilos, registro, paginas_indice,
                                                     altura_colunas=y_colunas - base - 2, paginas=paginas)
    frames_capa = [
        Frame(MARGEM_X, y_colunas, LARGURA_UTIL, max(altura_topo, 1), id="topo",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(MARGEM_X, base, largura_esq, y_colunas - base, id="esquerda",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(MARGEM_X + largura_esq + ENTRE_COLUNAS, base, largura_dir, y_colunas - base, id="direita",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
    ]

    def desenhar_capa(c, d):
        c.saveState()
        _desenhar_masthead(c, agora)
        _desenhar_faixa_mercados(c, edicao, PAGINA_ALTURA - MARGEM_TOPO - ALTURA_MASTHEAD)
        # filete vertical entre a manchete e as chamadas
        c.setStrokeColor(FILETE)
        c.setLineWidth(0.4)
        x = MARGEM_X + largura_esq + ENTRE_COLUNAS / 2
        c.line(x, base, x, y_colunas - 2)
        _rodape(c, d)
        c.restoreState()

    frame_interno = Frame(MARGEM_X, MARGEM_BASE + 4, LARGURA_UTIL,
                          PAGINA_ALTURA - MARGEM_TOPO - 24 - MARGEM_BASE - 4, id="interno",
                          leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=frames_capa, onPage=desenhar_capa),
        PageTemplate(id="interna", frames=[frame_interno], onPage=_cabecalho_interno(edicao)),
    ])

    historia = [NextPageTemplate("interna")]
    historia += topo or [Spacer(1, 1)]
    historia.append(FrameBreak())
    historia += esquerda or [Spacer(1, 1)]
    historia.append(FrameBreak())
    historia += direita or [Spacer(1, 1)]
    historia.append(FrameBreak())

    manchete = (edicao.get("capa") or {}).get("manchete")
    brasil = edicao.get("brasil") or {}
    exterior = edicao.get("exterior") or {}
    empresas = edicao.get("empresas") or {}
    historia += _editoria("Brasil", "brasil", brasil.get("noticias"), brasil.get("noticias_erro"),
                          agora, estilos, registro, excluir=manchete,
                          edicao_janela=edicao.get("janela_noticias"))
    historia += _editoria("Empresas e setores", "empresas", empresas.get("cards"), empresas.get("noticias_erro"),
                          agora, estilos, registro, excluir=manchete,
                          edicao_janela=edicao.get("janela_noticias"))
    historia += _editoria("Mundo", "exterior", exterior.get("noticias"), exterior.get("noticias_erro"),
                          agora, estilos, registro, excluir=manchete,
                          edicao_janela=edicao.get("janela_noticias"))
    historia += _radar(edicao, estilos, registro)
    historia += _mercados(edicao, estilos, registro)
    historia += _agenda(edicao, estilos, registro)
    if not colofao_na_capa:
        historia += _colofao(edicao, estilos, registro)
    doc.build(historia)
    registro["total_paginas"] = doc.page
    return buffer.getvalue()


_NOMES_INDICE = (("brasil", "Brasil"), ("empresas", "Empresas e setores"), ("exterior", "Mundo"),
                 ("radar", "Radar setorial"), ("mercados", "Mercados"), ("agenda", "Agenda do dia"))


def gerar_pdf(edicao: dict, registro: dict = None) -> bytes:
    """Monta o jornal e devolve os bytes do PDF (nunca escreve em disco).
    Duas passadas: a 1ª descobre em que página cada editoria caiu, a 2ª
    imprime o índice da capa com esses números (o índice tem altura fixa
    por editoria, então a 2ª passada não desloca nada). Levanta a exceção
    original em falha de desenho - jobs/morning_call.py degrada pra envio
    sem anexo.

    `registro` (opcional, usado pelos testes) recebe as páginas de cada
    editoria, as marcas de posição das manchetes/corpos e o total de
    páginas da passada final."""
    _registrar_fontes()
    rascunho = {}
    _montar(edicao, rascunho, paginas_indice=[(nome, "") for chave, nome in _NOMES_INDICE],
            paginas={chave: 9 for chave, _ in _NOMES_INDICE})
    paginas = rascunho.get("paginas", {})
    indice = [(nome, paginas[chave]) for chave, nome in _NOMES_INDICE if chave in paginas]
    final = registro if registro is not None else {}
    final.clear()
    return _montar(edicao, final, paginas_indice=indice, paginas=paginas)


def gerar_pdf_do_momento(agora=None) -> bytes:
    """Conveniência pra uso manual/CLI: monta a edição com dados reais e
    gera o PDF. jobs/morning_call.py NÃO usa esta função (chama as duas
    etapas separadas pra logar a falha de cada uma)."""
    from data.morning_call_editorial import montar_edicao
    return gerar_pdf(montar_edicao(agora))


if __name__ == "__main__":  # pragma: no cover - uso manual: python -m jobs.morning_call_pdf saida.pdf
    import sys
    destino = sys.argv[1] if len(sys.argv) > 1 else "morning_call.pdf"
    with open(destino, "wb") as arquivo:
        arquivo.write(gerar_pdf_do_momento())
    print(f"PDF gerado em {destino}")
