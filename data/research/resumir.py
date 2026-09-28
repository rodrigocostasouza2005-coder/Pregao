# -*- coding: utf-8 -*-
"""Resumo automatico de relatorios via LLM gratuito (Groq, free tier -
API compativel com OpenAI, sem SDK extra: so `requests`).

Fluxo: baixa o relatorio (HTML ou PDF) -> extrai texto (nunca copiado
verbatim pro resumo) -> resume com o LLM num formato fixo -> grava no
Supabase (tabela research_itens, ver data/research/store.py) pra nunca
resumir o mesmo link duas vezes. Se qualquer etapa falhar, retorna
resumo=None com o motivo - nunca inventa conteudo."""

from io import BytesIO

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

import config
from . import store
from .base import HEADERS, TIMEOUT, permitido

_PROMPT_SISTEMA = (
    "Voce e um analista que escreve briefings de mercado financeiro em portugues para "
    "quem acompanha o mercado de perto, SEMPRE com suas proprias palavras (nunca copie "
    "frases do texto original).\n\n"
    "O TITULO faz parte do conteudo jornalistico, nao e' so' um rotulo: se ele traz um "
    "fato relevante (evento, ativo, direcao de preco, relacao de causa), esse fato "
    "PRECISA aparecer no resumo, mesmo que o corpo do texto fornecido seja pobre. Nunca "
    "copie o titulo literalmente - transforme-o em contexto jornalistico.\n\n"
    "Antes de escrever, analise internamente (sem mostrar essa analise na resposta): "
    "qual o evento principal, quais ativos/empresas/indicadores estao envolvidos, quais "
    "numeros aparecem, que relacao causa->consequencia o texto realmente sustenta (nunca "
    "invente uma causa que o texto nao sustente), e quais riscos ou proximos eventos "
    "importam para quem acompanha o mercado.\n\n"
    "Escreva a resposta em TEXTO PURO, sem nenhuma formatacao markdown (sem **negrito**, "
    "sem *italico*, sem listas com # ou numeros) - o resultado e' exibido como texto "
    "simples, entao qualquer simbolo de markdown apareceria literalmente na tela. Cada "
    "secao comeca exatamente com o cabecalho em maiusculas seguido de dois-pontos, sem "
    "nenhum simbolo antes ou depois dele (ex: 'CONTEXTO:', nunca '**CONTEXTO:**'), com "
    "uma linha em branco entre secoes:\n\n"
    "CONTEXTO: texto corrido com NO MAXIMO 4 frases explicando o que aconteceu, por que "
    "aconteceu e por que isso importa para o mercado.\n\n"
    "MERCADO: NO MAXIMO 6 numeros, um por linha comecando com '- ', preservando o sinal "
    "(+/-) - se o texto trouxer mais de 6, escolha os 6 mais relevantes pro mercado "
    "(indices/moeda/juros/commodity principal do episodio), nao liste todas as "
    "commodities so' porque foram citadas. Omita esta secao inteira (cabecalho incluido) "
    "se o texto nao trouxer nenhum numero.\n\n"
    "DRIVERS: NO MAXIMO 4 fatores (os mais decisivos pro movimento do mercado, nao todos "
    "os fatores mencionados), em linhas comecando com '- ', preferindo causa -> "
    "consequencia SOMENTE quando o texto sustentar essa relacao; caso contrario, "
    "descreva o fator com linguagem neutra (ex: 'o movimento ocorre em meio a...'), sem "
    "inventar a causa.\n\n"
    "IMPACTOS: NO MAXIMO 2 frases corridas (nao uma frase por classe de ativo) sobre "
    "quais ativos, setores ou empresas podem ser afetados e por que - so' quando isso "
    "puder ser sustentado pelo conteudo, sem sugerir recomendacao de investimento. Omita "
    "esta secao inteira se nao houver base nenhuma.\n\n"
    "ATENCAO: NO MAXIMO 4 linhas comecando com '- ' com pontos especificos (nunca "
    "genericos) a acompanhar dai pra frente.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- nunca invente numeros, precos-alvo, recomendacoes, resultados, guidance ou "
    "relacoes de causa que nao estejam no texto ou no titulo fornecidos;\n"
    "- se uma informacao (ex: preco-alvo, recomendacao) nao existir na fonte, NAO "
    "mencione o campo - nunca escreva 'nao informado', 'nao disponivel', 'sem dados' ou "
    "equivalente;\n"
    "- nunca repita a mesma informacao em duas secoes diferentes - cada secao precisa "
    "acrescentar algo novo;\n"
    "- tamanho total proporcional a quantidade de informacao real disponivel: por volta "
    "de 80-120 palavras quando o conteudo for curto/pobre em informacao, 120-180 num "
    "conteudo normal, 180-250 quando houver bastante informacao relevante (ex: Morning "
    "Call ou research completo) - 250 palavras e' o TETO mesmo nesse caso, nunca "
    "ultrapasse; se o conteudo tiver mais driver/numero do que cabe nesse limite, "
    "escolha os mais relevantes pro mercado e deixe o resto de fora. Nunca estufe o "
    "texto artificialmente so' pra bater um numero minimo de palavras - se houver pouca "
    "informacao, seja curto;\n"
    "- tom de quem acompanha mercado financeiro profissionalmente, nunca robotico ou "
    "generico (evite frases como 'o cenario apresenta riscos para os investidores')."
)

# instrucoes extras por tipo de conteudo, anexadas ao prompt de sistema -
# ajustam so' a PRIORIZACAO do que entra no resumo (o formato de secoes
# acima e' sempre o mesmo). Chave = resultado de _detectar_foco().
_FOCO_POR_TIPO = {
    "MORNING_CALL": (
        "\n\nEste conteudo e' a transcricao de um programa de mercado ao vivo da manha "
        "(Morning Call, Resumo da Manha, Fechamento de Mercado ou similar). Priorize, "
        "nesta ordem: cenario internacional, futuros, bolsas, commodities, dolar, juros, "
        "macroeconomia, agenda de eventos do dia e impactos para o Brasil. Ignore trechos "
        "de saudacao, publicidade ou conversa que nao tragam conteudo de mercado."
    ),
    "ACOES": (
        "\n\nEste conteudo e' um relatorio de research sobre uma empresa/acao. Priorize, "
        "quando presentes no texto: empresa, resultado, receita, EBITDA, lucro, margens, "
        "guidance, valuation, recomendacao e preco-alvo do relatorio, e riscos. Mencione "
        "preco-alvo ou recomendacao SOMENTE se estiverem explicitos no texto."
    ),
    "MACRO": (
        "\n\nEste conteudo e' sobre um indicador ou evento macroeconomico. Priorize: qual "
        "indicador/evento, o resultado, a comparacao com a expectativa ou o valor "
        "anterior (quando disponivel no texto), a reacao dos mercados, as implicacoes e "
        "os proximos dados/eventos relevantes."
    ),
}


def _detectar_foco(casa: str, tipo: str) -> str | None:
    """Mapeia (casa, tipo) do relatorio pra uma chave de _FOCO_POR_TIPO, ou
    None se nenhum foco especifico se aplicar (usa so' o prompt generico).
    Lives da Genial (Morning Call, Resumo da Manha, Fechamento de Mercado
    etc - ver data/research/genial_lives.py) sao todas comentario de
    mercado ao vivo, tratadas com o mesmo foco independente do subtitulo
    exato do programa."""
    if casa == "Genial (Lives)":
        return "MORNING_CALL"
    if tipo in _FOCO_POR_TIPO:
        return tipo
    return None


def _extrair_texto_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    linhas = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
    return "\n".join(linhas)


def _extrair_texto_pdf(conteudo: bytes) -> str | None:
    try:
        import pypdf
    except ImportError:
        return None
    try:
        leitor = pypdf.PdfReader(BytesIO(conteudo))
        paginas = [p.extract_text() or "" for p in leitor.pages[:15]]
        texto = "\n".join(paginas).strip()
        return texto or None
    except Exception:
        return None


def obter_texto_relatorio(link: str) -> tuple:
    """Baixa e extrai o texto de um relatorio (HTML ou PDF). Retorna
    (texto, motivo_falha) - texto=None se nao der pra extrair (exige
    login, PDF protegido/escaneado, pypdf ausente etc), com o motivo.

    Usa curl_cffi (impersonate="chrome") em vez de `requests` puro: as
    paginas de relatorio (testado com a Genial) ficam atras do mesmo WAF
    por fingerprint de TLS que a home - com `requests` normal a conexao
    simplesmente nao responde (timeout), curl_cffi contorna reproduzindo
    o handshake TLS de um Chrome de verdade."""
    if not permitido(link):
        return None, "bloqueado pelo robots.txt"
    try:
        r = cffi_requests.get(link, headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        return None, f"erro ao baixar: {e}"

    ctype = r.headers.get("Content-Type", "")
    if "pdf" in ctype or link.lower().endswith(".pdf"):
        texto = _extrair_texto_pdf(r.content)
        if texto is None:
            return None, "PDF nao pode ser lido (biblioteca pypdf ausente ou arquivo protegido/escaneado)"
        return texto, None

    texto = _extrair_texto_html(r.text)
    if len(texto) < 200:
        return None, "conteudo muito curto (provavelmente exige login)"
    return texto, None


def resumir_com_groq(texto: str, titulo: str, casa: str = "", tipo: str = "") -> tuple:
    """Resume via Groq (free tier). Retorna (resumo, motivo_falha).
    motivo_falha='cota' especificamente em erro 429 (rate limit/cota
    esgotada), pra UI mostrar um aviso diferenciado.

    casa/tipo (opcionais, vem do item de research - ver CASAS em
    data/research/__init__.py) so' ajustam a PRIORIZACAO do prompt via
    _detectar_foco/_FOCO_POR_TIPO - nunca mudam o formato de secoes nem
    liberam o modelo a inventar informacao."""
    chave, modelo = config.obter_credenciais_groq()
    if not chave:
        return None, "GROQ_API_KEY não configurada em st.secrets"

    foco = _detectar_foco(casa, tipo)
    prompt_sistema = _PROMPT_SISTEMA + _FOCO_POR_TIPO.get(foco, "")

    texto_truncado = texto[:12000]
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Titulo: {titulo}\n\nTexto do relatorio:\n{texto_truncado}"},
                ],
                "temperature": 0.2,
                "max_tokens": config.GROQ_MAX_TOKENS,
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        resumo = r.json()["choices"][0]["message"]["content"].strip()
        return resumo, None
    except Exception as e:
        return None, str(e)


def obter_resumo(link: str, titulo: str, extrator_texto=None, casa: str = "", tipo: str = "") -> dict:
    """Resumo de um relatorio: extrai texto+resume via Groq e grava no
    Supabase (upsert pelo link, ja existente na tabela - ver
    store.salvar_resumo). Quem chama deve conferir antes se o item ja tem
    resumo salvo (rel.get('resumo')) pra nao gastar cota de IA a toa.

    extrator_texto: funcao (link)->(texto, motivo_falha) pra casas que nao
    podem usar o download generico da pagina publica (ex: XP, onde o
    conteudo pago fica na mesma pagina do trecho aberto - ver
    CASAS[i]['extrator_texto'] em data/research/__init__.py). None usa o
    generico (obter_texto_relatorio, baixa a pagina do link).

    casa/tipo: repassados pra resumir_com_groq so' pra ajustar a
    priorizacao do resumo (ver _detectar_foco) - opcionais, "" usa o
    prompt generico.

    Retorna {resumo, motivo_indisponivel}; resumo=None se qualquer etapa
    falhar (nao grava nada nesse caso)."""
    extrator = extrator_texto or obter_texto_relatorio
    texto, motivo = extrator(link)
    if texto is None:
        return {"resumo": None, "motivo_indisponivel": motivo}

    resumo, motivo = resumir_com_groq(texto, titulo, casa=casa, tipo=tipo)
    if resumo is None:
        return {"resumo": None, "motivo_indisponivel": motivo}

    store.salvar_resumo(link, resumo, config.obter_modelo_groq())
    return {"resumo": resumo, "motivo_indisponivel": None}
