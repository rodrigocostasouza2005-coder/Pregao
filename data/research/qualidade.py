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
    r"-?(?:R\$|US\$)\s*-?[\d.,]+|-?\d+(?:[.,]\d+)?\s*%|-?\d+(?:[.,]\d+)?\s*p\.?p\.?",
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
    """Remove unidade/espacos/sinal/pontuacao de fim de frase e normaliza
    pra uma chave numerica comparavel. '48,50' e '48.50' viram a mesma
    chave (so' 1 separador presente - decimal, nunca milhar, ver
    paragrafo abaixo), e agora TAMBEM 'R$ 1.234,56' (formato BR completo:
    ponto de milhar + virgula decimal) e 'R$ 1234,56' (mesmo valor sem o
    separador de milhar) viram a MESMA chave - bug real corrigido em
    revisao tecnica (2026-10-23): antes, com os DOIS separadores
    presentes, a funcao nao mexia em nada e devolvia '1.234,56' literal,
    nunca igual a '1234,56' calculado do resumo - um resumo fiel que so'
    omitisse o separador de milhar (parafrase natural de LLM) era
    rejeitado pelo gate como se o numero fosse outro.

    Algoritmo (quando HA' 2 separadores, '.' e ',', no mesmo numero): o
    ULTIMO que aparece (o mais a direita) e' sempre o decimal - convencao
    universal (BR 1.234,56 e' igual ao valor de EUA/UK 1,234.56, so' com
    os simbolos trocados; o separador de milhar SEMPRE vem antes do
    decimal, nunca depois) - qualquer ocorrencia do OUTRO separador antes
    dele e' removida (agrupamento de milhar, sem valor). Com SO' 1 tipo
    de separador presente (caso ambiguo em isolamento - ex: '1.234'
    poderia ser 1234 ou 1,234 - sem saber a convencao da fonte),
    continua tratando como decimal, igual a antes - nao assume milhar
    sem a segunda pista.

    Sinal negativo (ex: 'R$ -50,00', '-15%'): preservado na chave (prefixo
    '-') - numeros com sinais diferentes NUNCA contam como o mesmo valor,
    mesmo com a mesma magnitude (bug relacionado corrigido junto: a regex
    de extracao, ver _PADRAO_NUMERO_COM_UNIDADE, antes nem capturava o
    sinal - '-15%' virava '15%' silenciosamente, deixando o gate incapaz
    de notar um resumo que inverte alta/queda mantendo so' a magnitude).

    `bruto.rstrip(".,")` primeiro: sem isso, um numero no FIM de uma
    frase (ex: 'R$ 48,00.') engole o ponto final no match da regex (o
    ponto e' parte da classe [\\d.,]) e confunde a deteccao de separador
    decimal - achado real ao escrever os testes deste gate."""
    bruto = bruto.rstrip(".,")
    negativo = "-" in bruto
    s = re.sub(r"[^\d.,]", "", bruto)
    if not s:
        return ""
    pos_decimal = max(s.rfind("."), s.rfind(","))
    if pos_decimal == -1:
        chave = s
    else:
        parte_inteira = re.sub(r"[.,]", "", s[:pos_decimal])
        parte_decimal = s[pos_decimal + 1:]
        chave = f"{parte_inteira}.{parte_decimal}" if parte_decimal else (parte_inteira or "0")
    if "." in chave:
        chave = chave.rstrip("0").rstrip(".")
    if not chave or chave == "0":
        return chave
    return f"-{chave}" if negativo else chave


def _numeros_do_texto(texto: str) -> set:
    return {_normalizar_numero(n) for n in _PADRAO_NUMERO_COM_UNIDADE.findall(texto or "")}


# Vocabulário de métricas financeiras conhecidas pra checagem de
# ATRIBUIÇÃO (numeros_com_metrica_trocada abaixo) - termos compostos
# (ex: "lucro liquido") E suas raízes (ex: "lucro") ficam ambos na lista
# de propósito: um resumo que só disser "lucro" ainda reconhece a
# métrica (mais genérica), mas "lucro liquido" por perto casa com a
# frase mais específica primeiro (ver _metrica_mais_proxima, desempate
# por comprimento). NÃO é exaustivo - métrica fora desta lista
# simplesmente não participa da checagem de atribuição (nem bloqueia,
# nem libera - ver docstring de numeros_com_metrica_trocada: ausência de
# métrica reconhecida nunca reprova, só reduz o que dá pra conferir).
_METRICAS_FINANCEIRAS = (
    "receita liquida", "receita bruta", "receita",
    "lucro liquido", "lucro bruto", "lucro operacional", "lucro",
    "margem bruta", "margem ebitda", "margem liquida", "margem operacional", "margem",
    "ebitda", "ebit",
    "divida liquida", "divida bruta", "divida", "alavancagem",
    "caixa liquido", "caixa", "fluxo de caixa",
    "custo", "custos", "despesa", "despesas",
    "producao", "vendas", "faturamento",
)

_FIM_DE_FRASE = (".", "!", "?", ";")


def _metrica_mais_proxima(texto_norm: str, pos_fim_numero: int, janela: int = 80) -> str | None:
    """Métrica financeira conhecida (ver _METRICAS_FINANCEIRAS) mais
    próxima ANTES de um número (posição `pos_fim_numero`, o FIM do match
    do número em `texto_norm` - já passado por _sem_acento), dentro de
    uma janela de `janela` caracteres, sem atravessar fim de frase
    anterior (sentença diferente = contexto diferente, nunca associado).
    Em empate de posição (ex: "lucro" é substring de "lucro liquido"),
    prefere o termo MAIS LONGO/específico. None se nenhuma métrica
    conhecida estiver nesse raio - caso comum e esperado (nem todo número
    tem uma métrica-palavra por perto, ex: datas, tickers, contagens).

    Só olha pra TRÁS (métrica ANTES do número, ex: "lucro cresceu 8%",
    "margem de 42%") - padrão dominante em texto financeiro em
    português. NÃO cobre métrica DEPOIS do número (ex: "8% de
    crescimento no lucro") - limitação documentada, não ambígua: textos
    assim ficam sem métrica reconhecida (None) e simplesmente não entram
    na checagem de atribuição, nunca geram falso positivo por isso."""
    inicio_janela = max(0, pos_fim_numero - janela)
    trecho = texto_norm[inicio_janela:pos_fim_numero]
    corte_frase = max((trecho.rfind(c) for c in _FIM_DE_FRASE), default=-1)
    if corte_frase != -1:
        trecho = trecho[corte_frase + 1:]
    melhor_metrica, melhor_pos = None, -1
    for m in _METRICAS_FINANCEIRAS:
        p = trecho.rfind(m)
        if p == -1:
            continue
        if p > melhor_pos or (p == melhor_pos and len(m) > len(melhor_metrica or "")):
            melhor_pos, melhor_metrica = p, m
    return melhor_metrica


def numeros_com_metrica_trocada(resumo: str, texto_original: str) -> list:
    """Números do resumo cuja métrica financeira mais próxima (ver
    _metrica_mais_proxima) diverge de TODAS as métricas mais próximas do
    MESMO número (mesmo valor normalizado) no texto original - sintoma
    de atribuição errada: o número existe no original, mas colado numa
    métrica DIFERENTE (ex: original tem "margem bruta de 42%,
    crescimento do lucro líquido de 15% e receita de 8%"; resumo diz
    "o lucro cresceu 8%" - 8% existe no original, mas perto de
    'receita', nunca de 'lucro').

    Conservador DE PROPÓSITO (nunca inventa uma atribuição que não
    consegue confirmar NEM desmentir): só reprova quando o resumo tem
    uma métrica reconhecida por perto E o original também tem (pelo
    menos 1) métrica reconhecida perto de alguma ocorrência do MESMO
    número, mas são métricas DIFERENTES. Se qualquer um dos lados não
    tiver métrica reconhecida nas redondezas (vocabulário limitado, ver
    _METRICAS_FINANCEIRAS, ou métrica depois do número, ver
    _metrica_mais_proxima), não reprova por isso - preferível deixar
    passar um caso que não consegue confirmar a reprovar um resumo fiel
    por um gap do vocabulário/heurística."""
    resumo_norm = _sem_acento(resumo or "")
    original_norm = _sem_acento(texto_original or "")
    problemas = []
    vistos = set()
    for m in _PADRAO_NUMERO_COM_UNIDADE.finditer(resumo_norm):
        bruto = m.group(0)
        if bruto in vistos:
            continue
        vistos.add(bruto)
        chave = _normalizar_numero(bruto)
        if not chave:
            continue
        metrica_resumo = _metrica_mais_proxima(resumo_norm, m.end())
        if metrica_resumo is None:
            continue
        metricas_originais = {
            _metrica_mais_proxima(original_norm, m2.end())
            for m2 in _PADRAO_NUMERO_COM_UNIDADE.finditer(original_norm)
            if _normalizar_numero(m2.group(0)) == chave
        } - {None}
        if not metricas_originais:
            continue
        # compatibilidade por substring (nunca igualdade exata): "lucro"
        # (resumo) tem que casar com "lucro liquido" (original) - mesma
        # metrica-raiz, so' mais generica - mas "margem bruta" NUNCA
        # casa com "margem ebitda" (nenhuma e' substring da outra) -
        # bug real encontrado ao rodar os testes existentes deste gate:
        # igualdade exata rejeitava um resumo FIEL so' por generalizar
        # "lucro liquido" pra "lucro".
        if any(metrica_resumo in m or m in metrica_resumo for m in metricas_originais):
            continue
        problemas.append(
            f"\"{bruto}\" associado a '{metrica_resumo}' no resumo, mas no original "
            f"aparece perto de {', '.join(sorted(metricas_originais))!r}"
        )
    return problemas


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
    números sem base -> número com métrica trocada -> tickers sem base
    -> causalidade sem evidência), ou None se o resumo passou nas 4
    checagens. Usada por resumir.py:_gerar_resumo antes de cachear/
    persistir qualquer resumo novo."""
    nums = numeros_sem_base(resumo, texto_original)
    if nums:
        return f"número(s) sem base no texto original: {', '.join(nums)}"
    trocados = numeros_com_metrica_trocada(resumo, texto_original)
    if trocados:
        return f"número(s) possivelmente associado(s) à métrica errada: {'; '.join(trocados)}"
    tickers = tickers_sem_base(resumo, texto_original, titulo)
    if tickers:
        return f"ticker(s) sem base no texto original: {', '.join(tickers)}"
    return causalidade_sem_evidencia(resumo, texto_original)
