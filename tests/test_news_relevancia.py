# -*- coding: utf-8 -*-
"""Testes do motor de RELEVÂNCIA/DEDUP/SCORE de data/news.py - ate
2026-10-08 esse nucleo (_relevante, _tokens_similaridade/_similaridade,
_calcular_score) nao tinha NENHUM teste direto (tests/test_news_fase3.py
so' cobre o que a FASE 3 acrescentou - imagem/teaser/merge cronologico;
tests/test_calendario_ui.py e tests/test_research_news_context.py so'
mockam obter_noticias por fora). Cobre os cenarios que decidem se uma
noticia e' "da empresa" ou so' mencao de passagem, se 2 titulos sao o
MESMO fato, e como o score de confiabilidade reage a fonte/sensacionalismo/
rumor.

Puro (sem rede/IA). Uso: python tests/test_news_relevancia.py (venv)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.news import _calcular_score, _relevante, _similaridade, _tokens_similaridade

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


# ============================================================
# _relevante: empresa precisa aparecer no TÍTULO (nome ou ticker),
# nunca basta aparecer "em algum lugar da matéria" (isso é feito fora,
# na extração do título mesmo).
# ============================================================

def test_1_ticker_no_titulo_e_relevante():
    _checar("1 ticker aparece literalmente no titulo -> relevante",
            _relevante("PETR4", "Petrobras", "PETR4 anuncia novo investimento em refino"))


def test_2_nome_curto_da_empresa_no_titulo_e_relevante():
    _checar("2 nome comum da empresa (sem o ticker) no titulo -> relevante",
            _relevante("PETR4", "Petrobras", "Petrobras anuncia novo investimento em refino"))


def test_3_mencao_de_passagem_nao_e_relevante():
    # empresa NAO aparece no titulo - so' apareceria no corpo da materia
    # (ex: lista de altas do dia citando varios papeis) - nao conta.
    _checar("3 titulo sem o nome/ticker da empresa -> NAO relevante (mencao de passagem)",
            not _relevante("PETR4", "Petrobras", "Ibovespa fecha em alta puxado por bancos e mineradoras"))


def test_4_alias_bdr_com_todas_as_palavras_e_relevante():
    # BDR estrangeiro: cobertura de imprensa usa o nome local (2 palavras),
    # que nunca bate com o nome_curto (1 palavra) derivado do yfinance.
    _checar("4a alias de 2 palavras, AMBAS no titulo -> relevante",
            _relevante("MELI34", "MercadoLibre, Inc.", "Mercado Livre anuncia expansão no Brasil",
                       aliases=("Mercado Livre", "MELI")))
    _checar("4b so' 1 das 2 palavras do alias no titulo -> NAO relevante (evita falso positivo)",
            not _relevante("MELI34", "MercadoLibre, Inc.", "Mercado fecha em alta hoje",
                            aliases=("Mercado Livre",)))


def test_5_nome_longo_com_pontuacao_colada_nao_quebra_relevancia():
    # achado real documentado no proprio docstring de _nome_curto: nome
    # com pontuacao colada na 1a palavra (longName do yfinance pra' BDR)
    # nao pode fazer _relevante falhar por comparar 'mercadolibre,' (com
    # virgula) contra o token tokenizado (sem virgula).
    _checar("5 alias bate mesmo com nome_empresa tendo pontuacao colada",
            _relevante("MELI34", "MercadoLibre, Inc.", "MELI34 sobe forte na B3 hoje"))


# ============================================================
# _tokens_similaridade / _similaridade: 2 titulos sobre o MESMO fato
# devem ter sobreposicao alta, mesmo com verbos/veiculos diferentes.
# ============================================================

def test_6_sinonimos_de_verbo_aumentam_similaridade():
    # "dispara"/"sobe" sao canonizados pro mesmo token (_SINONIMOS) -
    # 2 veiculos descrevendo o MESMO fato com verbos diferentes devem
    # ficar bem mais parecidos do que se o sinonimo nao existisse.
    a = _tokens_similaridade("Petrobras dispara 8% após anúncio de dividendos extraordinários", "PETR4")
    b = _tokens_similaridade("Ação da Petrobras sobe 8% com anúncio de dividendos extraordinários", "PETR4")
    sim = _similaridade(a, b)
    _checar("6 titulos sobre o mesmo fato (verbos sinonimos) tem similaridade ALTA (>= limiar de agrupamento)",
            sim >= 0.55, f"(sim={sim:.2f})")


def test_7_titulos_sobre_fatos_diferentes_tem_similaridade_baixa():
    a = _tokens_similaridade("Petrobras anuncia novo investimento em refino no Nordeste", "PETR4")
    b = _tokens_similaridade("Petrobras reduz preço da gasolina nas refinarias", "PETR4")
    sim = _similaridade(a, b)
    _checar("7 titulos sobre fatos DIFERENTES (mesma empresa) tem similaridade BAIXA (< limiar)",
            sim < 0.55, f"(sim={sim:.2f})")


def test_8_similaridade_com_conjunto_vazio_e_zero_nunca_quebra():
    _checar("8 conjunto vazio de um lado -> 0.0 (nunca ZeroDivisionError)",
            _similaridade(set(), {"a", "b"}) == 0.0 and _similaridade(set(), set()) == 0.0)


def test_9_ticker_e_stopword_nao_contam_pra_similaridade():
    tokens = _tokens_similaridade("A Petrobras e a Vale sobem com o mercado", "PETR4")
    _checar("9a stopwords ('a', 'e', 'o', 'com') nunca entram nos tokens", not ({"a", "e", "o", "com"} & tokens))
    _checar("9b o proprio ticker (lowercase) nunca entra nos tokens", "petr4" not in tokens)


# ============================================================
# _calcular_score: regras determinísticas (sem IA) de confiabilidade.
# ============================================================

def test_10_fonte_confiavel_aumenta_score_e_registra_a_regra():
    score, regras = _calcular_score(["Petrobras anuncia dividendos"], ["Valor Econômico"])
    _checar("10a fonte confiavel (Valor) aumenta o score acima do base (50)", score > 50, f"(score={score})")
    _checar("10b regra de veiculo confiavel e' registrada (nunca escondida)",
            any("confiável" in r for r in regras), f"(regras={regras})")


def test_11_multiplas_fontes_independentes_aumentam_score():
    score_1fonte, _ = _calcular_score(["Petrobras anuncia dividendos"], ["Valor Econômico"])
    score_3fontes, regras = _calcular_score(
        ["Petrobras anuncia dividendos"] * 3, ["Valor Econômico", "InfoMoney", "Exame"],
    )
    _checar("11a 3 fontes independentes pontuam MAIS que 1 fonte so'",
            score_3fontes > score_1fonte, f"(1fonte={score_1fonte}, 3fontes={score_3fontes})")
    _checar("11b regra de multiplas fontes registrada", any("fontes independentes" in r for r in regras))


def test_12_linguagem_sensacionalista_reduz_score():
    score_normal, _ = _calcular_score(["Petrobras anuncia dividendos extraordinários"], ["Veículo Teste"])
    score_sensacionalista, regras = _calcular_score(["URGENTE: Petrobras BOMBA de dividendos!!"], ["Veículo Teste"])
    _checar("12a titulo sensacionalista pontua MENOS que o equivalente normal",
            score_sensacionalista < score_normal, f"(normal={score_normal}, sensacionalista={score_sensacionalista})")
    _checar("12b regra de linguagem sensacionalista registrada (nunca escondida)",
            any("sensacionalista" in r for r in regras), f"(regras={regras})")


def test_13_termo_de_rumor_reduz_score():
    score_normal, _ = _calcular_score(["Petrobras anuncia fusão com concorrente"], ["Veículo Teste"])
    score_rumor, regras = _calcular_score(["Petrobras estuda fusão com concorrente, dizem fontes"], ["Veículo Teste"])
    _checar("13a termo de rumor ('estuda') pontua MENOS que uma afirmacao direta",
            score_rumor < score_normal, f"(normal={score_normal}, rumor={score_rumor})")
    _checar("13b regra de termo de rumor registrada", any("rumor" in r for r in regras))


def test_14_score_fica_sempre_entre_0_e_100():
    score_min, _ = _calcular_score(["URGENTE BOMBA rumor fontes dizem estuda pode!!"], ["Blog Qualquer"])
    score_max, _ = _calcular_score(
        ["Petrobras anuncia dividendos"] * 5,
        ["Valor Econômico", "InfoMoney", "Exame", "Reuters", "Bloomberg"],
    )
    _checar("14a score nunca fica negativo", score_min >= 0, f"(score_min={score_min})")
    _checar("14b score nunca passa de 100", score_max <= 100, f"(score_max={score_max})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE RELEVANCIA/DEDUP/SCORE (NEWS) PASSARAM")
