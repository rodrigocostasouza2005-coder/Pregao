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
    "ESTRUTURA - POUCOS BLOCOS, NUNCA UM TEMPLATE FIXO: o erro mais comum e' fragmentar "
    "demais (um bloco pra petroleo, outro pra dolar, outro pra juros, outro pra bolsas...) "
    "quando tudo isso e' A MESMA HISTORIA. Prefira 2 a 4 blocos no total (raramente mais), "
    "cada um cobrindo uma historia/tema COMPLETO, nao um dado isolado. Regra pratica: se "
    "um assunto so' teria 1-2 frases sozinho, ele quase certamente pertence dentro do "
    "bloco de outro assunto relacionado, nao merece bloco proprio. Exemplo: Trump + Ira + "
    "petroleo + inflacao + Fed + dolar e' UMA SO historia encadeada (ator -> decisao -> "
    "motivo -> reacao do petroleo -> efeito sobre inflacao/juros/dolar) e pode virar 1-2 "
    "paragrafos conectados dentro do MESMO bloco, nao 4 blocos separados. Cada bloco tem "
    "um titulo curto em maiusculas (ex: GEOPOLITICA E PETROLEO, EUA E MERCADOS) seguido "
    "de texto corrido (NO MAXIMO 4 frases por bloco) - titulos e quantidade de blocos se "
    "adaptam ao conteudo real, nunca uma lista fixa preenchida a forca. Use bullets ('- ') SO' no bloco final de pontos "
    "pra acompanhar (se existir) - o resto e' sempre texto corrido conectado, nunca fatos "
    "soltos em sequencia. So' crie um bloco dedicado a setores quando houver fundamento "
    "real pra VARIOS setores; se for so' um impacto pontual, incorpore numa frase dentro "
    "do bloco relacionado (ex: '...o que favorece produtores da commodity, mas eleva "
    "custos de empresas intensivas em combustivel') em vez de criar um bloco SETORES so' "
    "pra isso.\n\n"
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
    "PRECISAO FACTUAL VEM ANTES DE FLUIDEZ: reproduza EXATAMENTE os percentuais, precos, "
    "valores, probabilidades, datas, siglas de indicadores (ex: PCE, JOLTS, CPI) e nomes "
    "(pessoas/empresas) como aparecem na fonte. NUNCA 'corrija', complete ou troque uma "
    "sigla por outra parecida (se a fonte disser PCE, nao escreva PCI; se disser JOLTS, "
    "nao vire JS) - se um trecho de audio/transcricao estiver ambiguo ou a sigla nao for "
    "clara, mantenha exatamente como veio ou omita a sigla, nunca invente a expansao.\n\n"
    "SEM CONTRADICAO: antes de finalizar, revise se a nota nao contem duas afirmacoes "
    "incompativeis (ex: dizer 'expectativa de ALTA de juros' e depois citar 'X% de "
    "chance de CORTE' sem explicar a diferenca). Se a propria fonte tiver informacoes "
    "conflitantes, nao tente resolver a contradicao por conta propria - relate com "
    "cautela (ex: 'o mercado ainda diverge sobre...') ou omita a parte inconsistente.\n\n"
    "TOM: terminal profissional, sem exagero - evite 'despencou', 'disparou', 'colapsou', "
    "'crise', 'choque' a nao ser que a fonte realmente descreva um movimento desse "
    "tamanho; prefira 'avancou', 'recuou', 'subiu', 'caiu', 'ganhou/perdeu forca', "
    "'ficou pressionado'.\n\n"
    "'PARA ACOMPANHAR' (quando existir) precisa ser especifico - cada ponto diz O QUE "
    "acompanhar E POR QUE (ex: 'o petroleo, porque uma alta adicional pressionaria ainda "
    "mais as expectativas de inflacao nos EUA'), nunca algo generico como 'monitorar o "
    "mercado' ou 'acompanhar a volatilidade'.\n\n"
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
    "de 100-150 palavras pra conteudo curto/pobre em informacao, 180-300 num conteudo "
    "normal, 300-500 num Morning Call/Live longa com bastante conteudo real (uma "
    "transcricao de 30min bem aproveitada NAO cabe em 100 palavras) - nunca estufe o "
    "texto artificialmente so' pra bater um numero de palavras, mas tambem nunca corte "
    "informacao relevante so' pra ficar curto: quanto mais conteudo real houver, mais "
    "completo o resumo deve ser;\n"
    "- portugues natural de mercado financeiro, nunca robotico ou generico (evite 'o "
    "cenario apresenta riscos para os investidores', prefira algo como 'a alta do "
    "petroleo aumenta a pressao sobre as expectativas de inflacao e pode dificultar "
    "cortes de juros mais rapidos').\n\n"
    "Antes de responder, confira internamente (sem escrever isso na resposta): o "
    "acontecimento principal esta claro? as pessoas relevantes foram nomeadas? existe "
    "causa->consequencia? os numeros/siglas batem exatamente com a fonte? nao ha "
    "contradicao? nao inventei nada? da pra entender a noticia so' lendo a nota?"
)

# limite de caracteres pra mandar o texto DIRETO pro resumo narrativo (ver
# resumir_com_groq) - acima disso, condensa por partes antes (ver
# _condensar_texto_longo) em vez de truncar cru (bug real ate 2026-09-30:
# texto[:12000] cortava relatorio/Morning Call longo no meio, podia perder
# numero/guidance/preco-alvo que estava so' depois do corte)
_LIMITE_TEXTO_DIRETO = 12000
_TAMANHO_CHUNK = 10000

_PROMPT_EXTRACAO_CHUNK = (
    "Voce esta vendo so' UM PEDACO de um conteudo maior (nao o documento "
    "inteiro). Extraia em topicos curtos e objetivos todo fato, numero, "
    "nome (pessoa/empresa/indicador), data, guidance, preco-alvo, "
    "recomendacao e citacao relevante que aparecer NESTE PEDACO - sem "
    "narrativa, sem introducao, sem comentario seu, so' os pontos. Nunca "
    "invente nada que nao esteja no texto. Se este pedaco nao tiver "
    "nenhuma informacao de mercado relevante (saudacao, publicidade, "
    "repeticao, transicao), responda exatamente: SEM_CONTEUDO_RELEVANTE"
)

# instrucoes extras por tipo de conteudo, anexadas ao prompt de sistema -
# ajustam so' a PRIORIZACAO do que entra no resumo (o formato de secoes
# acima e' sempre o mesmo). Chave = resultado de _detectar_foco().
_FOCO_POR_TIPO = {
    "MORNING_CALL": (
        "\n\nEste conteudo e' a transcricao de um programa de mercado ao vivo da manha "
        "(Morning Call, Resumo da Manha, Fechamento de Mercado ou similar), que normalmente "
        "passa por varios temas (geopolitica, juros, commodities, bolsas, agenda do dia) - "
        "mas isso NAO significa um bloco pra cada tema. Identifique qual e' a HISTORIA "
        "PRINCIPAL do episodio (o que puxa os outros movimentos) e conecte os temas "
        "derivados dela no mesmo bloco; so' abra um segundo bloco pra um tema realmente "
        "independente (ex: agenda politica local, quando nao tiver relacao com o resto). "
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


def _chamar_groq(chave: str, modelo: str, mensagens: list, max_tokens: int) -> tuple:
    """POST generico pro endpoint de chat completions da Groq. Retorna
    (conteudo, motivo_falha) - motivo_falha='cota' especificamente em erro
    429 (rate limit/cota esgotada), pra UI mostrar um aviso diferenciado.
    Usado tanto pelo resumo narrativo final quanto pela extracao por
    pedaco de texto longo (ver _condensar_texto_longo)."""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": mensagens,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except Exception as e:
        return None, str(e)


def _condensar_texto_longo(texto: str, chave: str, modelo: str) -> tuple:
    """Documento acima de _LIMITE_TEXTO_DIRETO: divide em pedacos de
    _TAMANHO_CHUNK chars, extrai so' os fatos/numeros/nomes de CADA pedaco
    (chamada leve, _PROMPT_EXTRACAO_CHUNK) e junta os extratos num texto
    condensado - isso vira o 'texto' que alimenta o resumo narrativo de
    verdade (resumir_com_groq), preservando informacao que estaria depois
    do corte de um truncamento cru. Retorna (texto_condensado, motivo) -
    None se QUALQUER pedaco falhar de verdade (erro/cota) - melhor avisar
    que o resumo nao pode ser gerado do que resumir so' metade do conteudo
    sem avisar."""
    pedacos = [texto[i:i + _TAMANHO_CHUNK] for i in range(0, len(texto), _TAMANHO_CHUNK)]
    extratos = []
    for pedaco in pedacos:
        conteudo, motivo = _chamar_groq(
            chave, modelo,
            [
                {"role": "system", "content": _PROMPT_EXTRACAO_CHUNK},
                {"role": "user", "content": pedaco},
            ],
            max_tokens=800,
        )
        if conteudo is None:
            return None, motivo
        if "SEM_CONTEUDO_RELEVANTE" not in conteudo:
            extratos.append(conteudo.strip())
    if not extratos:
        return None, "conteúdo sem informação de mercado relevante (após leitura por partes)"
    return "\n\n".join(extratos), None


def resumir_com_groq(texto: str, titulo: str, casa: str = "", tipo: str = "") -> tuple:
    """Resume via Groq (free tier). Retorna (resumo, motivo_falha).
    motivo_falha='cota' especificamente em erro 429 (rate limit/cota
    esgotada), pra UI mostrar um aviso diferenciado.

    casa/tipo (opcionais, vem do item de research - ver CASAS em
    data/research/__init__.py) so' ajustam a PRIORIZACAO do prompt via
    _detectar_foco/_FOCO_POR_TIPO - nunca mudam o formato de secoes nem
    liberam o modelo a inventar informacao.

    Texto acima de _LIMITE_TEXTO_DIRETO passa primeiro por
    _condensar_texto_longo (resumo por partes) em vez de ser truncado cru -
    uma transcricao de Morning Call de 30min (~36 mil chars) nao cabia
    inteira antes; agora o conteudo depois do caractere 12000 nao e' mais
    simplesmente descartado."""
    chave, modelo = config.obter_credenciais_groq()
    if not chave:
        return None, "GROQ_API_KEY não configurada em st.secrets"

    if len(texto) > _LIMITE_TEXTO_DIRETO:
        texto, motivo = _condensar_texto_longo(texto, chave, modelo)
        if texto is None:
            return None, motivo

    foco = _detectar_foco(casa, tipo)
    prompt_sistema = _PROMPT_SISTEMA + _FOCO_POR_TIPO.get(foco, "")

    conteudo, motivo = _chamar_groq(
        chave, modelo,
        [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Titulo: {titulo}\n\nTexto do relatorio:\n{texto}"},
        ],
        max_tokens=config.GROQ_MAX_TOKENS,
    )
    if conteudo is None:
        return None, motivo
    return _normalizar_formatacao(conteudo), None


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
