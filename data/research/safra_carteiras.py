# -*- coding: utf-8 -*-
"""Coletor da carteira mensal publica "Top 10 Acoes" da Safra Corretora.

Fonte nova (2026-10-16, validada com requisicao real, nao suposicao):
`https://www.safra.com.br/investimentos/renda-variavel/carteiras-recomendadas.htm`
e' uma pagina publica sem login, sem WAF/bot-detection (HTTP 200 com
`requests` puro, headers de User-Agent identificado deste projeto,
`robots.txt` permissivo) - diferente de Genial/XP/BTG, que estao
bloqueados na borda (Akamai) mesmo rodando de uma rede residencial real
(ver PROGRESSO.md, auditoria 2026-10-16). A pagina linka um PDF mensal
("<Mes>_Acoes.pdf") com uma tabela estruturada (codigo, companhia, setor,
cotacao de fechamento do mes anterior, P/L, peso anterior, peso atual) -
extraido aqui via `pypdf` (ja' em requirements.txt).

Mesmo principio do resto do projeto: nunca copia o TEXTO do relatorio (a
analise qualitativa de cada papel, nas paginas seguintes do PDF) - so' a
composicao da carteira (ticker/peso/data), que e' o unico dado que o
Radar de quedas precisa pra funcionar. O disclaimer do PDF (pagina 5,
item 9) proibe reproducao do RELATORIO; isto aqui nunca reproduz o
relatorio, so' extrai metadados de composicao, mesmo tratamento ja' dado
a Genial/XP (ver `base.py`/`xp.py`/`genial.py`)."""
import re
import unicodedata
from datetime import date, datetime, timezone
from io import BytesIO
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

from .base import HEADERS, TIMEOUT, permitido

BASE_URL = "https://www.safra.com.br"
LISTAGEM_URL = BASE_URL + "/investimentos/renda-variavel/carteiras-recomendadas.htm"
CASA = "Safra Corretora"
CARTEIRA = "Top 10 Ações"

MESES = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Vocabulario de setor conhecido na tabela da Safra - so' usado pra
# separar "empresa" de "setor" visualmente (campo "empresa" do alerta);
# se um setor novo nao estiver aqui, o nome inteiro (empresa+setor) cai
# em "empresa" sem quebrar o parsing (degradacao graciosa, nunca
# descarta a linha so' por causa disso - o que o Radar precisa de
# verdade e' so' o ticker).
_SETORES_CONHECIDOS = sorted((
    "Bens de Capital", "Serviços Financeiros", "Saúde",
    "Siderurgia e Mineração", "Petróleo e Gás", "Shoppings Centers",
    "Utilidades Básicas", "Consumo e Varejo", "Educação",
    "Energia Elétrica e Saneamento", "Transportes", "Recursos Naturais",
    "Construção Civil", "Agronegócio", "Tecnologia", "Telecomunicações",
    "Papel e Celulose", "Bebidas", "Alimentos e Bebidas", "Bancos",
), key=len, reverse=True)

# linha da tabela: CODIGO  Empresa [Setor]  12,34  5,6x  7,0%  8,0%
_LINHA_TABELA_RE = re.compile(
    r"^([A-Z][A-Z0-9]{3,5})\s+(.+?)\s+(\d+,\d+)\s+(\d+,\d+)x\s+(\d+,\d+)%\s+(\d+,\d+)%\s*$"
)
MIN_TICKERS = 5  # Top 10 real tem ~10; abaixo disso, parsing suspeito -> rejeita


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(ch for ch in texto if not unicodedata.combining(ch)).casefold()


def _get(url, binario=False):
    """GET simples (requests puro basta - fonte confirmada sem bot-
    detection, ver docstring do modulo). None se bloqueado pelo
    robots.txt, HTTP != 200 ou corpo vazio - nunca lanca excecao pra
    quem chama."""
    if not permitido(url):
        print(f"[radar_safra] coleta bloqueada pelo robots.txt: {url}")
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT * 2)
    except Exception as exc:
        print(f"[radar_safra] falha de conexão: {type(exc).__name__}: {exc} ({url})")
        return None
    if r.status_code != 200 or not r.content:
        print(f"[radar_safra] HTTP {r.status_code} ou corpo vazio: {url}")
        return None
    return r.content if binario else r.text


def _url_pdf_mes(html, hoje):
    """Acha o link do PDF "<Mes>_Acoes.pdf" (NUNCA "_BDRs"/"_FIIs") do mes
    vigente na listagem publica. None se o mes atual ainda nao tiver PDF
    publicado (ex: inicio do mes, antes da atualizacao)."""
    mes = _normalizar(MESES[hoje.month])
    candidatos = re.findall(r'href=[\'"]([^\'"]+\.pdf)[\'"]', html, re.I)
    for href in candidatos:
        href_norm = _normalizar(href)
        if mes in href_norm and "acoes" in href_norm and "bdr" not in href_norm:
            return urljoin(LISTAGEM_URL, href)
    return None


def _separar_empresa_setor(texto):
    """"Weg Bens de Capital" -> ("Weg", "Bens de Capital"). Se nenhum
    setor conhecido bater, devolve o texto inteiro como empresa (nunca
    quebra, so' fica menos bonito)."""
    for setor in _SETORES_CONHECIDOS:
        if texto.endswith(setor):
            empresa = texto[: -len(setor)].strip()
            if empresa:
                return empresa, setor
    return texto.strip(), ""


def _parsear_texto(texto, url, hoje=None):
    """Extrai a composição da carteira a partir do TEXTO já extraído do
    PDF (lista de dicts, mesmo formato de
    `data/research/genial_carteiras.py`). Separado de parsear_pdf() pra
    poder testar o parsing em si com um fixture de texto real, sem
    carregar bytes de PDF binário no repositório de testes. None se a
    tabela não for encontrada ou tiver menos que MIN_TICKERS linhas
    válidas (parsing suspeito/PDF mudou de layout - rejeita em vez de
    salvar parcial)."""
    hoje = hoje or date.today()
    agora = datetime.now(timezone.utc).isoformat()
    # Nao ha' "Publicado em DD de mes de YYYY" explicito no PDF (diferente
    # da Genial) - so' "Outubro de 2026" no cabecalho. Usa o dia 1 do mes
    # vigente como data de publicacao: e' o unico fato verificavel (mes/
    # ano declarados pela propria Safra), nunca inventa um dia especifico.
    data_publicacao = f"{hoje.year}-{hoje.month:02d}-01"

    itens = []
    for linha in texto.splitlines():
        m = _LINHA_TABELA_RE.match(linha.strip())
        if not m:
            continue
        ticker, resto, cotacao, _pl, _peso_anterior, peso_atual = m.groups()
        try:
            # So' usado pra VALIDAR que a linha e' mesmo uma linha de
            # tabela (preco real, nao lixo que por acaso bateu no regex) -
            # nao vai pro payload: "preco_referencia_fonte" nao e' coluna
            # de radar_carteiras_recomendadas (achado real 2026-10-16,
            # validacao com Supabase de producao: upsert falhava inteiro
            # com PGRST204 "Could not find the column"). Criar uma
            # migracao so' pra este campo nao-essencial nao se justifica
            # agora - mesmo schema que genial_carteiras.py ja usa.
            float(cotacao.replace(",", "."))
        except ValueError:
            continue
        empresa, _setor = _separar_empresa_setor(resto)
        itens.append({
            "casa": CASA,
            "carteira": CARTEIRA,
            "ticker": ticker,
            "empresa": empresa,
            "recomendacao": "CARTEIRA MENSAL",
            "preco_alvo": None,  # Top 10 e' alocacao por peso, nao preco-alvo individual
            "data_publicacao": data_publicacao,
            "validade_ate": None,
            "fonte_url": url,
            "verificado_em": agora,
            "status_coleta": "COLETADO",
        })

    tickers_unicos = {item["ticker"] for item in itens}
    if len(tickers_unicos) < MIN_TICKERS:
        print(
            f"[radar_safra] tabela rejeitada: {len(tickers_unicos)} ticker(s) "
            f"encontrados (mínimo {MIN_TICKERS}) - layout do PDF pode ter mudado"
        )
        return None
    return itens


def parsear_pdf(conteudo_pdf, url, hoje=None):
    """Extrai o texto do PDF (bytes) via pypdf e delega o parsing real a
    _parsear_texto(). None se o PDF não puder ser lido."""
    try:
        leitor = PdfReader(BytesIO(conteudo_pdf))
        texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages[:2])
    except Exception as exc:
        print(f"[radar_safra] PDF ilegível: {type(exc).__name__}: {exc}")
        return None
    return _parsear_texto(texto, url, hoje=hoje)


def coletar_carteiras(hoje=None):
    """Retorna snapshot mensal validado da Safra Top 10 Ações; None se a
    fonte estiver indisponível ou o PDF do mês vigente não for
    encontrado/parseável. Mesmo contrato de coletar_carteiras() em
    genial_carteiras.py - plugável em data/radar_quedas.py como fonte
    adicional."""
    hoje = hoje or date.today()
    html = _get(LISTAGEM_URL)
    if not html:
        return None
    url_pdf = _url_pdf_mes(html, hoje)
    if not url_pdf:
        print(f"[radar_safra] PDF do mês vigente ({MESES[hoje.month]}) não encontrado na listagem")
        return None
    conteudo = _get(url_pdf, binario=True)
    if not conteudo:
        return None
    return parsear_pdf(conteudo, url_pdf, hoje=hoje)
