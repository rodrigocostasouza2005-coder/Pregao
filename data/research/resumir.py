# -*- coding: utf-8 -*-
"""Resumo automatico de relatorios via LLM gratuito (Groq, free tier -
API compativel com OpenAI, sem SDK extra: so `requests`).

Fluxo: baixa o relatorio (HTML ou PDF) -> extrai texto (nunca copiado
verbatim pro resumo) -> resume com o LLM num formato fixo -> grava no
Supabase (tabela research_itens, ver data/research/store.py) pra nunca
resumir o mesmo link duas vezes. Se qualquer etapa falhar, retorna
resumo=None com o motivo - nunca inventa conteudo."""

import re
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

import config
from . import store
from .base import HEADERS, TIMEOUT, permitido

_PROMPT_SISTEMA = (
    "Voce e um analista de mercado escrevendo uma nota rapida em portugues logo depois "
    "de ler/assistir o conteudo, SEMPRE com suas proprias palavras (nunca copie frases "
    "do texto original). NAO escreva uma ficha tecnica - escreva uma nota narrativa, do "
    "jeito que um analista contaria o fato pra um colega: quem fez/disse o que, por que "
    "isso aconteceu, como o mercado reagiu, e o que isso afeta.\n\n"
    "O TITULO faz parte do conteudo jornalistico, nao e' so' um rotulo: se ele traz um "
    "fato relevante (evento, ator, ativo, direcao de preco), esse fato PRECISA aparecer "
    "na nota, mesmo que o corpo do texto fornecido seja pobre. Nunca copie o titulo "
    "literalmente - transforme-o em narrativa.\n\n"
    "REGRA MAIS IMPORTANTE - PESSOAS E ATORES: se uma pessoa, banco central, empresa ou "
    "instituicao relevante aparecer no conteudo (ex: um presidente, um dirigente de "
    "banco central, um CEO, um analista citado, uma empresa especifica), NUNCA substitua "
    "isso por um conceito generico. Erre pro lado de nomear: 'a tensao geopolitica "
    "aumentou' esta ERRADO se o texto identifica QUEM fez o que' - o certo e' algo como "
    "'Donald Trump rejeitou uma proposta de tregua com o Ira, elevando o risco percebido "
    "de interrupcao no fornecimento de petroleo'. Quando houver uma declaracao "
    "relevante, use a cadeia QUEM -> O QUE DISSE/FEZ -> CONSEQUENCIA (ex: 'Powell "
    "sinalizou maior cautela com cortes de juros, reforcando a percepcao de uma politica "
    "monetaria mais restritiva'), nunca so' 'Fed hawkish -> dolar sobe'.\n\n"
    "CAUSA -> CONSEQUENCIA: nao liste acontecimentos soltos (ex: 'petroleo sobe 3,3%. "
    "dolar sobe. bolsas caem.'). Explique a conexao entre eles SEMPRE que o conteudo "
    "sustentar essa relacao - o leitor precisa entender POR QUE o numero esta "
    "acontecendo, nao so' que ele aconteceu. Quando nao houver base pra uma relacao "
    "causal, descreva o fato com linguagem neutra em vez de inventar a causa.\n\n"
    "ESTRUTURA - LIVRE, NAO USE UM TEMPLATE FIXO: nao existe uma lista obrigatoria de "
    "secoes (nada de sempre 'CONTEXTO/MERCADO/DRIVERS/IMPACTOS/ATENCAO' na mesma ordem "
    "pra toda noticia - isso deixa o resultado artificial e previsivel). Em vez disso, "
    "organize o conteudo em 2 a 5 blocos tematicos curtos, cada um com um titulo curto "
    "em maiusculas (ex: GEOPOLITICA/PETROLEO, JUROS/DOLAR, BOLSAS, SETORES, PARA "
    "ACOMPANHAR) seguido de texto corrido explicando aquele tema - os titulos e a "
    "quantidade de blocos devem se adaptar ao que a noticia realmente tem, nunca uma "
    "lista fixa preenchida a forca. Agrupe informacoes relacionadas no MESMO bloco em "
    "vez de espalhar (ex: se o texto fala de Trump, Ira e petroleo, isso e' UM bloco de "
    "geopolitica/petroleo, nao three blocos separados). Use bullets ('- ') APENAS onde "
    "isso realmente ajudar (tipicamente no bloco final de pontos pra acompanhar) - o "
    "resto e' texto corrido, nunca uma noticia inteira em bullets. Um bloco de impacto "
    "por setor so' deve existir quando houver fundamento real pra mais de um setor - "
    "nunca invente impacto setorial sem uma relacao financeira direta e evidente.\n\n"
    "FORMATACAO: escreva em texto simples (o resultado e' inserido direto num HTML "
    "simples). A UNICA tag permitida e' <b>...</b>, usada com moderacao pra destacar "
    "nomes de pessoas/empresas, ativos e os numeros mais importantes (ex: '<b>Donald "
    "Trump</b> rejeitou...', 'o petroleo subiu <b>3,30%, para US$ 107,90</b>'). PROIBIDO "
    "usar qualquer asterisco (*) em QUALQUER parte da resposta - nao existe **negrito** "
    "nem *italico* markdown aqui, so' a tag <b>texto</b>; nenhuma outra tag HTML alem de "
    "<b> em hipotese nenhuma (nada de <i>, <p>, <br>, #, markdown de nenhum tipo). O "
    "titulo de cada bloco e' uma frase curta de 2 a 4 PALAVRAS em MAIUSCULAS, SEM "
    "nenhum asterisco/tag ao redor (exemplo de titulo correto: 'GEOPOLITICA/PETROLEO' - "
    "exemplo ERRADO/PROIBIDO: '**Petroleo sobe com tensao no Oriente Medio**'), numa "
    "linha propria, com uma linha em branco antes e depois.\n\n"
    "NUNCA crie um bloco final resumindo ou repetindo os blocos anteriores (ex: nao crie "
    "um bloco tipo 'RESUMO DE IMPACTO' ou 'EM RESUMO' juntando de novo o que ja foi dito) "
    "- cada bloco aparece uma unica vez, o ultimo bloco e' 'PARA ACOMPANHAR' (so' quando "
    "houver pontos concretos) e acabou ali.\n\n"
    "NUMEROS: nao transforme a nota numa lista de numeros - selecione so' os que "
    "realmente ajudam a entender a noticia (preco+variacao quando o preco for relevante "
    "e' melhor que so' a variacao; priorize precos, variacoes, receita, EBITDA, lucro, "
    "margens, guidance, valuation e indicadores macro citados no texto).\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- nunca invente declaracoes, pessoas, numeros, precos-alvo, recomendacoes, "
    "resultados, guidance, eventos, causalidade, impacto setorial ou opiniao de analista "
    "que nao estejam no texto ou no titulo fornecidos;\n"
    "- se uma informacao nao existir na fonte, NAO mencione o campo - nunca escreva "
    "'nao informado', 'nao disponivel', 'riscos nao identificados' ou equivalente, so' "
    "omita;\n"
    "- nunca repita a mesma informacao em blocos diferentes - cada bloco precisa "
    "acrescentar algo novo;\n"
    "- tamanho total proporcional a quantidade de informacao real disponivel: por volta "
    "de 80-120 palavras pra noticia curta/pobre em informacao, 120-180 numa noticia "
    "normal, 150-250 num Morning Call, ate uns 300 quando o conteudo for excepcionalmente "
    "completo - isso e' o teto, nunca ultrapasse; nunca estufe o texto artificialmente "
    "so' pra bater um numero minimo de palavras - se houver pouca informacao, seja "
    "curto;\n"
    "- portugues natural de mercado financeiro, nunca robotico ou generico (evite 'o "
    "cenario apresenta riscos para os investidores', prefira algo como 'a alta do "
    "petroleo aumenta a pressao sobre as expectativas de inflacao e pode dificultar "
    "cortes de juros mais rapidos')."
)

# instrucoes extras por tipo de conteudo, anexadas ao prompt de sistema -
# ajustam so' a PRIORIZACAO do que entra no resumo (o formato de secoes
# acima e' sempre o mesmo). Chave = resultado de _detectar_foco().
_FOCO_POR_TIPO = {
    "MORNING_CALL": (
        "\n\nEste conteudo e' a transcricao de um programa de mercado ao vivo da manha "
        "(Morning Call, Resumo da Manha, Fechamento de Mercado ou similar). Siga o fio "
        "geopolitica -> macro -> juros -> commodities -> bolsas -> setores -> agenda do "
        "dia, mas so' com os temas que o episodio realmente cobriu (nao force todos). "
        "Ignore trechos de saudacao, publicidade ou conversa sem conteudo de mercado."
    ),
    "ACOES": (
        "\n\nEste conteudo e' um relatorio de research sobre uma empresa/acao. Siga o "
        "fio empresa -> resultado -> receita/EBITDA/lucro/margem -> guidance -> "
        "valuation -> recomendacao -> riscos, so' com o que estiver no texto. Se um "
        "analista for citado pelo nome, use a cadeia nome do analista -> tese -> "
        "numeros -> conclusao. Mencione preco-alvo ou recomendacao SOMENTE se estiverem "
        "explicitos no texto."
    ),
    "MACRO": (
        "\n\nEste conteudo e' sobre um indicador ou evento macroeconomico. Siga o fio "
        "indicador/evento -> autoridade/dirigente que falou (nomeie-a) -> o que foi "
        "dito ou o resultado divulgado -> reacao dos mercados -> implicacoes e proximos "
        "dados relevantes."
    ),
}


def _normalizar_formatacao(texto: str) -> str:
    """O prompt proibe markdown (o resultado e' inserido como HTML puro via
    unsafe_allow_html, com <b> como unica tag permitida), mas na pratica o
    modelo (gpt-oss-20b, reasoning_effort=low - rapido, nao muito obediente
    a instrucao de formatacao) as vezes volta a usar **negrito** markdown
    mesmo assim. Em vez de brigar so' via prompt (nao 100% confiavel),
    normaliza aqui: converte **texto** -> <b>texto</b> e limpa qualquer
    asterisco/cerquilha solta que sobrar - garante o resultado certo
    independente do modelo obedecer ou nao."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"[*#]", "", texto)
    return texto.strip()


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
        return _normalizar_formatacao(resumo), None
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
