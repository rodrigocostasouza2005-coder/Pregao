# -*- coding: utf-8 -*-
"""Modulo 3 (Morning Call Editor) - ponte ENTRE o Earnings Reviewer
(reviewer.py) e a sintese editorial do Morning Call, sem tocar jobs/
morning_call.py nem ui/morning_call_tab.py.

--- Por que uma ponte separada em vez de editar o Morning Call direto ---

Em 2026-10-22, enquanto este modulo era construido, uma outra sessao
estava reconstruindo ATIVAMENTE a UX de ui/morning_call_tab.py (e por
extensao a forma como jobs/morning_call.py expoe conteudo estruturado -
ver data/morning_call_editorial.py:montar_edicao). Editar esses arquivos
"ás ciegas" em paralelo arriscava um conflito de merge grande e silencioso
sem nenhum ganho real agora. Este modulo faz a parte que NAO depende do
resultado dessa reconstrucao: transforma 1 nota do Earnings Reviewer
(reviewer.montar_nota_br/montar_nota_internacional) numa CHAMADA EDITORIAL
pronta (titulo + resumo factual + link pra fonte), no MESMO formato de
bullet que jobs/morning_call.py:_linhas_noticias ja usa ("- texto — link"),
e deliberadamente PARA AI' - nao insere nada no texto do Morning Call.

--- Integracao pendente (documentada, nao implementada aqui) ------------

Quando a reconstrucao da UX estabilizar, o passo que falta e' 1 linha em
jobs/morning_call.py:montar_morning_call, na secao "5. EMPRESAS E
SETORES": chamar `editorial.montar_chamadas_editoriais(notas)` pras
empresas com earnings review do dia e estender `linhas` com
`chamada_para_bullet(c)` pra cada uma, do MESMO jeito que
`_linhas_noticias(noticias_br_empresa, 10)` ja faz - nenhuma mudanca de
estrutura, so' mais uma fonte de bullet na mesma secao.

Nunca inventa numero: cada chamada e' só os fatos já calculados pelo
Earnings Reviewer (receita/lucro + variação a/a e t/t quando disponíveis)
mais, no máximo, 1 interpretação já marcada [INTERPRETAÇÃO] pelo próprio
reviewer.py - nunca uma nova."""


def _escala_para_unidade(escala_moeda: str | None) -> float:
    return {"MIL": 1_000.0, "MILHAO": 1_000_000.0}.get((escala_moeda or "").upper(), 1.0)


def _fmt_moeda(valor: float | None, moeda: str | None, escala_moeda: str | None = None) -> str:
    if valor is None:
        return "indisponível"
    absoluto = valor * _escala_para_unidade(escala_moeda)
    simbolo = {"REAL": "R$", "USD": "US$"}.get((moeda or "").upper(), f"{moeda or ''} ")
    grandeza = abs(absoluto)
    if grandeza >= 1e9:
        texto = f"{grandeza / 1e9:.1f} bi"
    elif grandeza >= 1e6:
        texto = f"{grandeza / 1e6:.1f} mi"
    else:
        texto = f"{grandeza:,.0f}".replace(",", ".")
    sinal = "-" if absoluto < 0 else ""
    return f"{sinal}{simbolo}{texto}"


def _fmt_variacao(pct: float | None, rotulo: str) -> str | None:
    if pct is None:
        return None
    direcao = "alta" if pct > 0.05 else ("queda" if pct < -0.05 else "estabilidade")
    return f"{direcao} de {abs(pct):.1f}% {rotulo}"


def montar_chamada_editorial(nota: dict) -> dict | None:
    """1 chamada editorial a partir de 1 nota do Earnings Reviewer.
    None quando a nota nao estiver disponivel (reviewer.py ja devolveu
    disponivel=False) - a ausencia de resultado nunca gera chamada
    generica/vazia."""
    if not nota.get("disponivel"):
        return None

    receita = nota.get("metricas", {}).get("receita_liquida", {})
    lucro = nota.get("metricas", {}).get("lucro_liquido_consolidado") \
        or nota.get("metricas", {}).get("lucro_liquido_controladora") or {}
    moeda, escala = nota.get("moeda"), nota.get("escala_moeda")

    empresa = nota.get("empresa") or nota["ticker"]
    titulo = f"{empresa} ({nota['ticker']}): resultado do {nota['periodo_label']}"

    fatos = []
    if receita.get("atual") is not None:
        variacoes = [v for v in (
            _fmt_variacao(receita.get("yoy_variacao_pct"), "a/a"),
            _fmt_variacao(receita.get("qoq_variacao_pct"), "t/t"),
        ) if v]
        sufixo = f" ({'; '.join(variacoes)})" if variacoes else ""
        fatos.append(f"receita líquida de {_fmt_moeda(receita['atual'], moeda, escala)}{sufixo}")
    if lucro.get("atual") is not None:
        variacoes = [v for v in (
            _fmt_variacao(lucro.get("yoy_variacao_pct"), "a/a"),
            _fmt_variacao(lucro.get("qoq_variacao_pct"), "t/t"),
        ) if v]
        sufixo = f" ({'; '.join(variacoes)})" if variacoes else ""
        fatos.append(f"lucro líquido de {_fmt_moeda(lucro['atual'], moeda, escala)}{sufixo}")

    if not fatos:
        return None  # nenhum numero disponivel - nunca gera chamada so' com o titulo

    resumo = "; ".join(fatos) + "."
    fonte = (nota.get("fontes") or [{}])[0]
    return {
        "ticker": nota["ticker"], "titulo": titulo, "resumo": resumo,
        "interpretacao": (nota.get("interpretacoes") or [None])[0],
        "link": fonte.get("url"), "fonte_nome": fonte.get("nome"),
        "periodo_label": nota["periodo_label"],
    }


def montar_chamadas_editoriais(notas: list) -> list:
    """Filtra/monta chamadas pra uma lista de notas - mantem so' as
    disponiveis e com pelo menos 1 numero (ver montar_chamada_editorial).
    Ordem preservada (quem chama decide a prioridade editorial)."""
    chamadas = [montar_chamada_editorial(nota) for nota in notas]
    return [c for c in chamadas if c is not None]


def chamada_para_bullet(chamada: dict) -> str:
    """Bullet no MESMO formato de jobs/morning_call.py:_linhas_noticias
    ("- texto — link") - pronto pra entrar na secao EMPRESAS E SETORES
    quando a integracao (ver docstring do modulo) for ligada."""
    texto = f"{chamada['titulo']}: {chamada['resumo']}"
    return f"- {texto}" + (f" — {chamada['link']}" if chamada.get("link") else "")
