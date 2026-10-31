# -*- coding: utf-8 -*-
"""Cruzamento com outras fontes do PREGAO (secao 6 do pedido) - reusa
data/market_researcher.py:cobertura_cruzada_casas (cobertura das casas
de research por ticker) e data/news.py:obter_noticias (noticias por
ticker), NUNCA cria um motor de verificacao paralelo. Dado o que essas
fontes trazem, decide nivel_evidencia/estado do Sinal - mas e'
DELIBERADAMENTE conservador: contexto (outra fonte tambem falou do
MESMO ticker/tema recentemente) nunca e' tratado como confirmacao da
AFIRMACAO especifica do post (isso exigiria comparar semanticamente a
alegacao com o texto da outra fonte, que este modulo nao faz - fazer
isso sem essa comparacao seria inventar confirmacao, o que a secao 6
proibe explicitamente: 'nao afirmar que foi confirmada quando so'
achou outra publicacao repetindo a mesma alegacao'). CONFIRMADO so'
e' atingido se `evidencias_confirmacao` vier preenchido com uma fonte
PRIMARIA explicita - este modulo nunca preenche isso por conta propria
na versao atual, so' prepara o campo pra uma promocao manual/futura."""

from datetime import datetime, timezone

from data import x_signals
from data.market_researcher import cobertura_cruzada_casas
from data.news import obter_noticias


def _chave_acontecimento(ticker: str | None, tema: str | None, horario_publicacao) -> str:
    """Dedup por FATO: ticker + tema normalizado + dia (UTC) - mesmo
    espirito de data/news.py:_agrupar, bem mais simples (sem clusterizar
    texto, so' bucket grosseiro) - suficiente pra marcar mesma_origem,
    nunca usado pra subir nivel de evidencia por si so."""
    dia = (horario_publicacao or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    tema_norm = (tema or "").strip().lower()[:40]
    return f"{(ticker or 'geral').upper()}|{tema_norm}|{dia}"


def _contexto_research(ticker: str) -> list[dict]:
    if not ticker:
        return []
    cruzado = cobertura_cruzada_casas(ticker)
    if not cruzado or cruzado.get("cobertura") is None:
        return []
    return [
        {"fonte": "research_casa", "casa": item.get("casa"), "link": item.get("link"),
         "data": item.get("data")}
        for item in (cruzado.get("cobertura") or [])[:5]
    ]


def _contexto_news(ticker: str) -> list[dict]:
    if not ticker:
        return []
    try:
        noticias = obter_noticias(ticker) or []
    except Exception:
        return []
    return [
        {"fonte": "news", "titulo": n.get("titulo"), "link": n.get("link"), "data": n.get("data")}
        for n in noticias[:5]
    ]


def cruzar_fontes(sinal, classificacao: dict, *, chaves_ja_vistas: set) -> dict:
    """Retorna dict com chave_acontecimento/mesma_origem/fontes_cruzadas/
    evidencias_confirmacao/nivel_evidencia/estado prontos pra persistir.
    `chaves_ja_vistas` e' atualizado in-place (mesmo set reutilizado
    pelo lote inteiro em cruzar_lote, pra detectar duplicata DENTRO do
    mesmo ciclo de coleta, alem do que ja esta' persistido)."""
    ticker = classificacao.get("ticker")
    chave = _chave_acontecimento(ticker, classificacao.get("tema"), sinal.horario_publicacao)
    ja_persistido = False
    try:
        from data.x_radar.store import existe_chave_acontecimento
        ja_persistido = existe_chave_acontecimento(chave, excluir_post_id=sinal.post_id)
    except Exception:
        ja_persistido = False
    mesma_origem = (chave in chaves_ja_vistas) or ja_persistido
    chaves_ja_vistas.add(chave)

    fontes_cruzadas = _contexto_research(ticker) + _contexto_news(ticker)

    if not classificacao.get("ok") or classificacao.get("categoria") == "sem_relevancia":
        nivel = x_signals.NivelEvidencia.NAO_CONFIRMADO
    elif fontes_cruzadas:
        nivel = x_signals.NivelEvidencia.EM_VERIFICACAO
    else:
        nivel = x_signals.NivelEvidencia.NAO_CONFIRMADO

    return {
        "chave_acontecimento": chave,
        "mesma_origem": mesma_origem,
        "fontes_cruzadas": fontes_cruzadas,
        "evidencias_confirmacao": [],  # nunca preenchido automaticamente - ver docstring do modulo
        "nivel_evidencia": nivel.value,
        "estado": x_signals.EstadoSinal.EM_VERIFICACAO.value if fontes_cruzadas else x_signals.EstadoSinal.DETECTADO.value,
    }


def enriquecer_lote(classificados: list[dict]) -> list[dict]:
    """classificados: lista de {'sinal':Sinal, 'classificacao':dict}
    (saida de classificador.classificar_lote). Adiciona 'cruzamento' a
    cada item, na mesma ordem."""
    chaves_vistas: set = set()
    for item in classificados:
        item["cruzamento"] = cruzar_fontes(item["sinal"], item["classificacao"], chaves_ja_vistas=chaves_vistas)
    return classificados
