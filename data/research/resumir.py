# -*- coding: utf-8 -*-
"""Resumo automatico de relatorios via LLM gratuito (Groq, free tier -
API compativel com OpenAI, sem SDK extra: so `requests`).

Fluxo: baixa o relatorio (HTML ou PDF) -> extrai texto (nunca copiado
verbatim pro resumo) -> resume com o LLM num formato fixo -> grava no
Supabase (tabela research_itens, ver data/research/store.py) pra nunca
resumir o mesmo link duas vezes. Se qualquer etapa falhar, retorna
resumo=None com o motivo - nunca inventa conteudo."""

import re
from datetime import datetime, timezone
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
    "FATO vs VISAO DA CASA/ANALISTA vs SUA LEITURA (separacao obrigatoria, mesmo dentro "
    "do texto corrido - nao precisa virar secao separada, mas a distincao tem que ficar "
    "clara pra quem le): um FATO e' algo que aconteceu/foi divulgado (resultado, numero, "
    "evento, declaracao textual) - escreva direto, sem atribuicao extra. Uma OPINIAO, "
    "EXPECTATIVA ou INTERPRETACAO vinda da casa/analista/empresa precisa continuar "
    "atribuida a quem a' disse ('Segundo a Genial...', 'o analista espera...', 'a visao "
    "da XP e'...', 'a empresa projeta...') - nunca apresente a tese de uma casa como se "
    "fosse um fato do mercado. Se VOCE (o sistema) precisar conectar pontos que o texto "
    "nao conecta explicitamente pra dar sentido a narrativa, isso e' uma LEITURA SUA, nao "
    "uma afirmacao da fonte - sinalize com uma expressao como 'o que sugere...', 'isso "
    "pode indicar...', nunca apresente como se a fonte tivesse dito isso literalmente. "
    "Na duvida entre tratar algo como fato ou como opiniao da casa, trate como opiniao "
    "da casa e atribua.\n\n"
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

_PROMPT_DADOS_ESTRUTURADOS = (
    "Leia o texto do relatorio e responda EXATAMENTE neste formato, "
    "2 linhas, nada mais, sem nenhum comentario antes ou depois:\n"
    "PRECO_ALVO: <numero, so' digitos e separador decimal, sem 'R$' "
    "nem texto - ex: 48.50> ou NAO_IDENTIFICADO\n"
    "RECOMENDACAO: <a palavra/expressao EXATA usada no texto, ex: "
    "COMPRA, MANTER, NEUTRO, VENDA, OUTPERFORM> ou NAO_IDENTIFICADO\n\n"
    "Regras obrigatorias, sem excecao:\n"
    "- preco-alvo e recomendacao SO contam se estiverem EXPLICITAMENTE "
    "escritos no texto - nunca estime, calcule, deduza ou arredonde um "
    "valor que nao esteja literalmente ali;\n"
    "- se o documento mencionar mais de um preco-alvo (ex: cenario base "
    "e otimista, ou precos-alvo de varios tickers diferentes), use o "
    "preco-alvo PRINCIPAL/BASE do ticker que da' titulo ao relatorio;\n"
    "- se nao houver preco-alvo OU recomendacao explicitos no texto, "
    "responda NAO_IDENTIFICADO pro campo correspondente - no caso de "
    "duvida, SEMPRE prefira NAO_IDENTIFICADO a arriscar um valor errado."
)

# tipos de documento onde faz sentido PROCURAR preco-alvo/recomendacao -
# nao vale gastar uma chamada de IA a mais em MACRO/NEWSLETTER/LIVE, que
# na pratica nunca tem isso (ver _FOCO_POR_TIPO: so' ACOES segue o fio
# resultado->valuation->recomendacao)
_TIPOS_COM_DADOS_ESTRUTURADOS = {"ACOES"}


def _extrair_dados_estruturados(texto: str, titulo: str, chave: str, modelo: str) -> tuple:
    """Chamada adicional pequena e barata (max_tokens=60, mesmo texto ja'
    carregado - NENHUMA nova requisicao de rede) pra extrair preco-alvo/
    recomendacao de forma estruturada, SEM tocar no resumo narrativo
    (resumir_com_groq) - documentos sofisticados continuam com a mesma
    nota em prosa de sempre; isso so' alimenta campos extras (ver
    store.salvar_resumo) usados por 'O QUE MUDOU'/Research Radar.
    Retorna (preco_alvo: float|None, recomendacao: str|None) - None pros
    dois se a chamada falhar ou nada for identificado (nunca inventa)."""
    conteudo, motivo = _chamar_groq(
        chave, modelo,
        [
            {"role": "system", "content": _PROMPT_DADOS_ESTRUTURADOS},
            {"role": "user", "content": f"Titulo: {titulo}\n\nTexto:\n{texto[:_LIMITE_TEXTO_DIRETO]}"},
        ],
        max_tokens=60,
    )
    if conteudo is None:
        return None, None

    preco_alvo = None
    m_preco = re.search(r"PRECO_ALVO:\s*([^\n]+)", conteudo, re.IGNORECASE)
    if m_preco:
        valor = m_preco.group(1).strip()
        if "NAO_IDENTIFICADO" not in valor.upper() and "NÃO_IDENTIFICADO" not in valor.upper():
            valor_limpo = re.sub(r"[^\d,.]", "", valor).replace(",", ".")
            try:
                preco_alvo = float(valor_limpo) if valor_limpo else None
            except ValueError:
                preco_alvo = None

    recomendacao = None
    m_rec = re.search(r"RECOMENDACAO:\s*([^\n]+)", conteudo, re.IGNORECASE)
    if m_rec:
        valor = m_rec.group(1).strip().strip(".")
        if valor and "NAO_IDENTIFICADO" not in valor.upper() and "NÃO_IDENTIFICADO" not in valor.upper():
            recomendacao = valor.upper()

    return preco_alvo, recomendacao


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
        "Ignore trechos de saudacao, publicidade ou conversa sem conteudo de mercado. "
        "Preserve SEMPRE, dentro da narrativa (nao como ficha separada): quem no programa "
        "disse o que' (apresentador/economista/analista citado pelo nome - a regra de "
        "atores ja' vale, mas aqui e' ainda mais importante por ser um programa com "
        "varias vozes); quais ativos/tickers especificos foram mencionados (nomeie-os, "
        "nao resuma como 'as acoes' ou 'o mercado'); os numeros citados; e, quando o "
        "programa trouxer uma visao/expectativa de alguem (nao so' fato reportado), deixe "
        "claro que e' a visao dessa pessoa/casa (ver regra FATO vs VISAO DA CASA acima)."
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


def _log_erro_ia(modelo: str, tipo_erro: str, detalhe: str):
    """Diagnostico tecnico (resiliencia do Research, 2026-10-01) - NUNCA
    mostrado ao usuario (ver _chamar_groq_com_fallback, que so' repassa
    pra UI um motivo de um conjunto pequeno e seguro: None/'cota'/
    'indisponivel'). print() de proposito, nao logging - mesmo padrao ja
    usado em data/research/__init__.py:coletar_casa: Streamlit Cloud
    captura stdout no painel de Logs, da' pra depurar sem expor nada pro
    usuario final. provedor e' sempre Groq neste modulo (unico provedor
    de IA do research hoje)."""
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[research-ia] {agora} provedor=Groq modelo={modelo} tipo_erro={tipo_erro} detalhe={detalhe}")


def _chamar_groq_com_fallback(
    chave: str, modelo_principal: str, modelo_fallback: str, mensagens: list, max_tokens: int,
    pular_principal: bool = False,
) -> tuple:
    """Resiliencia do pipeline de resumo (2026-10-01): tenta modelo_principal;
    se falhar (cota/rate-limit OU qualquer erro tecnico - timeout, 5xx,
    conexao - nunca por falta de conteudo, que nem chega aqui), tenta
    modelo_fallback UMA unica vez - nunca repete indefinidamente nem fica
    martelando uma fonte ja' sabida esgotada. Mesma chave/conta Groq, SEM
    credencial nova (ver config.GROQ_MODELO_FALLBACK).

    Retorna (conteudo, motivo_seguro, usou_fallback). motivo_seguro e'
    SEMPRE None, 'cota' ou 'indisponivel' - NUNCA o texto cru da excecao
    (HTTP status, stack trace, nome de excecao) - isso so' vai pro log
    tecnico via _log_erro_ia, nunca pra UI (ver ui/research_tab.py).

    pular_principal=True pula direto pro fallback sem tentar o principal
    de novo - usado quando o principal ja' confirmou falha NESTA MESMA
    geracao de resumo (ver _condensar_texto_longo, que processa varios
    pedacos em sequencia e nao vale a pena retentar um modelo que acabou
    de falhar ha' poucos segundos, especialmente cota - a janela de rate
    limit nao reseta nesse intervalo)."""
    if not pular_principal:
        conteudo, motivo = _chamar_groq(chave, modelo_principal, mensagens, max_tokens)
        if conteudo is not None:
            return conteudo, None, False
        _log_erro_ia(modelo_principal, "cota" if motivo == "cota" else "erro_tecnico", motivo)

    conteudo, motivo = _chamar_groq(chave, modelo_fallback, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, True
    _log_erro_ia(modelo_fallback, "cota" if motivo == "cota" else "erro_tecnico", motivo)
    return None, ("cota" if motivo == "cota" else "indisponivel"), True


def _condensar_texto_longo(texto: str, chave: str, modelo: str, modelo_fallback: str) -> tuple:
    """Documento acima de _LIMITE_TEXTO_DIRETO: divide em pedacos de
    _TAMANHO_CHUNK chars, extrai so' os fatos/numeros/nomes de CADA pedaco
    (chamada leve, _PROMPT_EXTRACAO_CHUNK) e junta os extratos num texto
    condensado - isso vira o 'texto' que alimenta o resumo narrativo de
    verdade (resumir_com_groq), preservando informacao que estaria depois
    do corte de um truncamento cru. Retorna (texto_condensado, motivo,
    pular_principal) - texto_condensado=None se QUALQUER pedaco falhar de
    verdade mesmo com fallback - melhor avisar que o resumo nao pode ser
    gerado do que resumir so' metade do conteudo sem avisar.
    pular_principal=True quando o modelo principal falhou em algum pedaco
    (cota ou erro tecnico) - repassado pra resumir_com_groq pular direto
    pro fallback na chamada narrativa final tambem, em vez de tentar de
    novo um modelo que acabou de falhar poucos segundos atras."""
    pedacos = [texto[i:i + _TAMANHO_CHUNK] for i in range(0, len(texto), _TAMANHO_CHUNK)]
    extratos = []
    pular_principal = False
    for pedaco in pedacos:
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            chave, modelo, modelo_fallback,
            [
                {"role": "system", "content": _PROMPT_EXTRACAO_CHUNK},
                {"role": "user", "content": pedaco},
            ],
            max_tokens=800,
            pular_principal=pular_principal,
        )
        pular_principal = pular_principal or usou_fallback
        if conteudo is None:
            return None, motivo, pular_principal
        if "SEM_CONTEUDO_RELEVANTE" not in conteudo:
            extratos.append(conteudo.strip())
    if not extratos:
        return None, "conteúdo sem informação de mercado relevante (após leitura por partes)", pular_principal
    return "\n\n".join(extratos), None, pular_principal


def resumir_com_groq(texto: str, titulo: str, casa: str = "", tipo: str = "") -> tuple:
    """Resume via Groq (free tier), com fallback automatico de modelo
    (2026-10-01, resiliencia - ver _chamar_groq_com_fallback) se o
    principal esgotar cota/rate-limit ou falhar por erro tecnico: mesma
    conta/chave Groq, so' um segundo modelo id
    (config.GROQ_MODELO_FALLBACK) - sem credencial nova. So' retorna
    resumo=None (e' quando a UI mostra "Resumo indisponível") se os DOIS
    modelos falharem. Retorna (resumo, motivo_falha, dados_estruturados).
    motivo_falha e' sempre None, 'cota' ou 'indisponivel' - nunca o texto
    cru de uma excecao (isso so' vai pro log tecnico, nunca pra UI).
    dados_estruturados = {"preco_alvo": float|None, "recomendacao": str|None}
    - sempre {} (nunca None) quando resumo != None, pra quem chama poder
    fazer dados_estruturados.get(...) sem checar None antes.

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
    modelo_fallback = config.obter_modelo_groq_fallback()
    if not chave:
        return None, "GROQ_API_KEY não configurada em st.secrets", {}

    pular_principal = False
    if len(texto) > _LIMITE_TEXTO_DIRETO:
        texto, motivo, pular_principal = _condensar_texto_longo(texto, chave, modelo, modelo_fallback)
        if texto is None:
            return None, motivo, {}

    foco = _detectar_foco(casa, tipo)
    prompt_sistema = _PROMPT_SISTEMA + _FOCO_POR_TIPO.get(foco, "")

    conteudo, motivo, _ = _chamar_groq_com_fallback(
        chave, modelo, modelo_fallback,
        [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Titulo: {titulo}\n\nTexto do relatorio:\n{texto}"},
        ],
        max_tokens=config.GROQ_MAX_TOKENS,
        pular_principal=pular_principal,
    )
    if conteudo is None:
        return None, motivo, {}

    dados_estruturados = {}
    if tipo in _TIPOS_COM_DADOS_ESTRUTURADOS:
        # mesma chamada/texto ja' carregado - so' mais uma requisicao HTTP
        # leve (max_tokens=60) pra Groq, nenhum novo download de pagina.
        # Falha aqui nunca derruba o resumo narrativo (ja pronto acima) -
        # so' os campos extra ficam None.
        preco_alvo, recomendacao = _extrair_dados_estruturados(texto, titulo, chave, modelo)
        dados_estruturados = {"preco_alvo": preco_alvo, "recomendacao": recomendacao}

    return _normalizar_formatacao(conteudo), None, dados_estruturados


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

    Retorna {resumo, motivo_indisponivel, preco_alvo, recomendacao};
    resumo=None se qualquer etapa falhar (nao grava nada nesse caso).
    preco_alvo/recomendacao vem de _extrair_dados_estruturados (so' pra
    tipo ACOES) - None quando nao se aplica ou nao foi identificado no
    texto, nunca um valor inventado."""
    extrator = extrator_texto or obter_texto_relatorio
    texto, motivo = extrator(link)
    if texto is None:
        return {"resumo": None, "motivo_indisponivel": motivo, "preco_alvo": None, "recomendacao": None}

    resumo, motivo, dados_estruturados = resumir_com_groq(texto, titulo, casa=casa, tipo=tipo)
    if resumo is None:
        return {"resumo": None, "motivo_indisponivel": motivo, "preco_alvo": None, "recomendacao": None}

    preco_alvo = dados_estruturados.get("preco_alvo")
    recomendacao = dados_estruturados.get("recomendacao")
    store.salvar_resumo(link, resumo, config.obter_modelo_groq(), preco_alvo=preco_alvo, recomendacao=recomendacao)
    return {"resumo": resumo, "motivo_indisponivel": None, "preco_alvo": preco_alvo, "recomendacao": recomendacao}
