# -*- coding: utf-8 -*-
"""Gate de fidelidade do resumo de research contra o texto original
(Fase 4 da integração "RESEARCH institucional", 2026-10-23) - adapta pro
domínio de research financeiro o MESMO padrão já comprovado em
`data/news.py` (`_causalidade_sem_evidencia`/`_contradicao_titulo_resumo`,
achou um bug real de produção em 2026-10-18), mas reescrito aqui (não
importado de lá) pra não arriscar tocar num arquivo com PRs abertos
concorrentes hoje (#88/#89/#137).

Por que isso importa especificamente pra research: o projeto NUNCA
persiste o texto completo do relatório original (`store.py` docstring:
"nunca o texto completo") - só o resumo em prosa gerada pela IA. Isso
significa que a ÚNICA janela em que dá pra comparar resumo-contra-
original é no MOMENTO DA GERAÇÃO (dentro de `resumir.py:_gerar_resumo`,
antes do texto original ser descartado) - depois disso a comparação é
impossível, pra sempre. Por isso este gate roda ali, não como auditoria
posterior.

Três checagens, todas determinísticas (sem chamada de IA nova):

1. `numeros_sem_base`: todo número com unidade financeira (%, R$, US$)
   que aparece no resumo precisa ter uma ocorrência (exata ou próxima)
   no texto original - número "novo" no resumo é o sintoma mais claro
   de alucinação numérica.
2. `tickers_sem_base`: todo ticker-like (ex: PETR4, VALE3) citado no
   resumo precisa aparecer no título ou no texto original - nunca um
   ticker inventado por associação.
3. `causalidade_sem_evidencia`: toda cláusula causal explícita
   ("por causa de", "impulsionado por" etc.) no resumo precisa ter pelo
   menos 1 palavra de conteúdo em comum com o texto original.

Qualquer uma reprovando => resumo não é cacheado nem persistido (ver
hook em resumir.py:_gerar_resumo) - degrada pra "resumo indisponível"
em vez de mostrar um resumo não confiável. Mesmo princípio do projeto
inteiro: nunca inventar dado."""

import re
import unicodedata

_PADRAO_NUMERO_COM_UNIDADE = re.compile(
    r"(?:R\$|US\$)\s*[\d.,]+|\d+(?:[.,]\d+)?\s*%|\d+(?:[.,]\d+)?\s*p\.?p\.?",
    re.IGNORECASE,
)

_PADRAO_TICKER = re.compile(r"\b[A-Z]{4}\d{1,2}\b")

# tickers genericos que casam o padrao regex mas nao sao tickers reais
# (siglas/abreviacoes de 4 letras + digito que aparecem em texto comum)
_FALSOS_POSITIVOS_TICKER = {"COVID19"}

_CONECTORES_CAUSAIS = (
    "por causa de", "por causa do", "por causa da", "por causa dos", "por causa das",
    "por conta de", "por conta do", "por conta da", "por conta dos", "por conta das",
    "devido a", "devido ao", "devido as", "devido aos",
    "em meio a", "em meio ao", "em meio as", "em meio aos",
    "impulsionado por", "impulsionada por", "motivado por", "motivada por",
    "na esteira de", "diante de", "em resposta a", "em resposta ao", "em resposta as",
    "puxado por", "puxada por", "pressionado por", "pressionada por",
    "influenciado por", "influenciada por",
)

_PALAVRAS_GENERICAS = {
    "mercado", "mercados", "sessao", "dia", "dias", "semana", "hoje",
    "ontem", "pregao", "movimento", "movimentos", "cenario", "ano", "anos",
    "trimestre", "trimestres", "resultado", "resultados", "empresa", "acao",
    "acoes", "relatorio", "analise", "casa",
}

_STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "para", "pra", "por", "com", "sem", "que", "e", "ou", "um",
    "uma", "uns", "umas", "ao", "aos", "se", "ja", "mais", "menos", "muito",
    "pouco", "ser", "esta", "este", "essa", "esse", "foi", "sao", "tem",
}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _normalizar_numero(bruto: str) -> str:
    """Remove unidade/espacos/pontuacao de fim de frase e normaliza
    separador decimal - '48,50' e '48.50' viram a mesma chave de
    comparacao, mas '48,50' e '4.850' continuam DIFERENTES (ponto de
    milhar vs decimal nao e' resolvido aqui de proposito - ambiguo sem
    saber a convencao da fonte; nesse caso prefere marcar como SEM base
    a arriscar um falso negativo).

    `bruto.rstrip(".,")` primeiro: sem isso, um numero no FIM de uma
    frase (ex: 'R$ 48,00.') engole o ponto final no match da regex (o
    ponto e' parte da classe [\\d.,]) e confunde a deteccao de separador
    decimal - achado real ao escrever os testes deste gate.

    Quando "." E "," aparecem JUNTOS no mesmo numero, a convencao BR e'
    inequivoca (ponto = separador de milhar, virgula = decimal) - achado
    real na auditoria de integracao 2026-10-23: 'R$ 1.234,56' no texto
    original e 'R$ 1234,56' no resumo (mesmo valor, so' sem separador de
    milhar - reformatacao plausivel de um LLM) normalizavam pra chaves
    DIFERENTES ('1.234,56' vs '1234.56'), reprovando um resumo fiel.
    Quando SO' "." aparece (sem virgula nenhuma no numero), continua
    ambiguo de proposito (pode ser separador de milhar OU decimal sem
    mais contexto) - nao resolvido aqui, mesmo principio conservador de
    preferir marcar como SEM base a arriscar um falso negativo."""
    s = re.sub(r"[^\d.,]", "", bruto.rstrip(".,"))
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _numeros_do_texto(texto: str) -> set:
    return {_normalizar_numero(n) for n in _PADRAO_NUMERO_COM_UNIDADE.findall(texto or "")}


def numeros_sem_base(resumo: str, texto_original: str) -> list:
    """Lista (ordenada, sem duplicata) dos números com unidade financeira
    do resumo que NÃO aparecem (nem de forma aproximada) no texto
    original. [] se todos tiverem base ou o resumo não citar nenhum
    número com unidade."""
    nums_resumo = _PADRAO_NUMERO_COM_UNIDADE.findall(resumo or "")
    nums_base = _numeros_do_texto(texto_original)
    faltando = []
    for bruto in nums_resumo:
        chave = _normalizar_numero(bruto)
        if chave and chave not in nums_base and bruto not in faltando:
            faltando.append(bruto)
    return faltando


def tickers_sem_base(resumo: str, texto_original: str, titulo: str = "") -> list:
    """Tickers citados no resumo que não aparecem no texto original nem
    no título - nunca um ticker "associado por proximidade temática"
    sem estar escrito na fonte."""
    tickers_resumo = set(_PADRAO_TICKER.findall(resumo or "")) - _FALSOS_POSITIVOS_TICKER
    base = (texto_original or "") + " " + (titulo or "")
    tickers_base = set(_PADRAO_TICKER.findall(base)) - _FALSOS_POSITIVOS_TICKER
    return sorted(tickers_resumo - tickers_base)


def _tokens_conteudo(texto: str) -> set:
    palavras = re.findall(r"[a-z]+", _sem_acento(texto))
    return {p for p in palavras if p not in _STOPWORDS and len(p) > 2}


def _clausulas_causais(resumo: str) -> list:
    """Trecho causal de cada sentença, a partir do FIM do conector (não
    do início dele) - as próprias palavras do conector (ex: o verbo em
    "impulsionado por") não contam como evidência, senão um resumo que
    reusa a palavra "impulsionado" em outro lugar do texto original
    passaria o gate mesmo com a causa real sendo inventada (achado real
    ao escrever os testes deste gate)."""
    sentencas = re.split(r"(?<=[.!?])\s+", resumo or "")
    achadas = []
    for s in sentencas:
        if not s.strip():
            continue
        norm = _sem_acento(s)
        melhor_pos, melhor_fim = -1, -1
        for c in _CONECTORES_CAUSAIS:
            p = norm.find(c)
            if p != -1 and (melhor_pos == -1 or p < melhor_pos):
                melhor_pos, melhor_fim = p, p + len(c)
        if melhor_pos != -1:
            achadas.append(s[melhor_fim:])
    return achadas


def causalidade_sem_evidencia(resumo: str, texto_original: str) -> str | None:
    """Descrição da primeira cláusula causal do resumo sem nenhuma
    palavra de conteúdo em comum com o texto original, ou None se todas
    tiverem base (ou não houver nenhuma cláusula causal)."""
    clausulas = _clausulas_causais(resumo)
    if not clausulas:
        return None
    tokens_base = _tokens_conteudo(texto_original)
    for clausula in clausulas:
        tokens_clausula = _tokens_conteudo(clausula) - _PALAVRAS_GENERICAS
        if len(tokens_clausula) >= 2 and not (tokens_clausula & tokens_base):
            return f"trecho causal sem base no texto original: \"{clausula.strip()}\""
    return None


def validar_fidelidade(resumo: str, texto_original: str, titulo: str = "") -> str | None:
    """Motivo de reprovação (primeiro problema encontrado, nesta ordem:
    números sem base -> tickers sem base -> causalidade sem evidência),
    ou None se o resumo passou nas 3 checagens. Usada por
    resumir.py:_gerar_resumo antes de cachear/persistir qualquer
    resumo novo."""
    nums = numeros_sem_base(resumo, texto_original)
    if nums:
        return f"número(s) sem base no texto original: {', '.join(nums)}"
    tickers = tickers_sem_base(resumo, texto_original, titulo)
    if tickers:
        return f"ticker(s) sem base no texto original: {', '.join(tickers)}"
    return causalidade_sem_evidencia(resumo, texto_original)
