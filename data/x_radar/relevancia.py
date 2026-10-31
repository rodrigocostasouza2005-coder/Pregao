# -*- coding: utf-8 -*-
"""Relevancia e credibilidade (secao 5 do pedido) - DOIS indicadores
separados, cada um com motivo explicito (nunca uma nota sem explicacao).
Credibilidade NUNCA e' inventada pra conta sem historico (fica None,
nao 0 - 0 pareceria 'sem credibilidade confirmada', que e' uma
afirmacao, nao a ausencia de dado). Segue regua pedida: seguidores/
curtidas/reposts nunca entram em nenhum dos dois calculos - nao sao
coletados por nenhuma chamada deste projeto, de proposito."""

from datetime import datetime, timezone

_PESO_TICKER_FOCO = 30
_PESO_CATEGORIA = {
    "fato_confirmado": 30, "tese_investimento": 25, "estimativa_projecao": 20,
    "opiniao_analista": 15, "rumor_nao_confirmado": 10, "comentario_macro": 15,
    "noticia": 15, "sem_relevancia": 0,
}
_PESO_CATALISADOR = 20
_PESO_ATUALIDADE_24H = 15
_PESO_INVESTIGACAO = 10


def calcular_relevancia(classificacao: dict, *, ticker_e_foco: bool,
                         horario_publicacao: datetime | None) -> tuple[int, str]:
    """Score 0-100 + motivo textual - soma de fatores objetivos, nunca
    um numero solto. Cada fator presente no motivo explica exatamente
    por que a nota ficou do jeito que ficou (pedido explicito da secao
    5: 'o sistema deve explicar por que uma publicacao foi classificada
    como relevante')."""
    if not classificacao.get("ok"):
        return 0, "classificacao indisponivel (falha de IA) - relevancia nao calculada"

    pontos = 0
    motivos = []

    if ticker_e_foco:
        pontos += _PESO_TICKER_FOCO
        motivos.append(f"ticker monitorado (+{_PESO_TICKER_FOCO})")

    categoria = classificacao.get("categoria") or "sem_relevancia"
    peso_cat = _PESO_CATEGORIA.get(categoria, 0)
    if peso_cat:
        pontos += peso_cat
        motivos.append(f"categoria={categoria} (+{peso_cat})")

    if classificacao.get("catalisador"):
        pontos += _PESO_CATALISADOR
        motivos.append(f"catalisador identificado (+{_PESO_CATALISADOR})")

    if horario_publicacao is not None:
        agora = datetime.now(timezone.utc)
        idade_h = (agora - horario_publicacao).total_seconds() / 3600
        if idade_h <= 24:
            pontos += _PESO_ATUALIDADE_24H
            motivos.append(f"publicado ha {idade_h:.1f}h (+{_PESO_ATUALIDADE_24H})")

    if classificacao.get("necessita_investigacao"):
        pontos += _PESO_INVESTIGACAO
        motivos.append(f"sinaliza necessidade de investigacao (+{_PESO_INVESTIGACAO})")

    if not motivos:
        return 0, "nenhum fator de relevancia identificado (sem ticker monitorado, sem catalisador, categoria sem peso)"
    return min(pontos, 100), "; ".join(motivos)


def calcular_credibilidade(autor: str, historico_autor: list[dict] | None) -> tuple[int | None, str | None]:
    """historico_autor: sinais ANTERIORES do mesmo autor, ja com estado
    final (confirmado/refutado) - None ou [] (sem historico) sempre
    retorna (None, None), NUNCA 0: autor novo nao e' 'baixa
    credibilidade', e' 'sem dado ainda'. Only conta estados finais
    (confirmado/refutado) - detectado/em_verificacao nao contam (ainda
    nao sabemos se a aposta anterior se confirmou)."""
    if not historico_autor:
        return None, None

    finais = [s for s in historico_autor if s.get("estado") in ("confirmado", "refutado")]
    if not finais:
        return None, None

    confirmados = sum(1 for s in finais if s["estado"] == "confirmado")
    total = len(finais)
    score = round((confirmados / total) * 100)
    motivo = f"{confirmados}/{total} publicacao(oes) anteriores confirmadas (de {len(historico_autor)} com historico)"
    return score, motivo


def aplicar_relevancia_credibilidade(enriquecidos: list[dict]) -> list[dict]:
    """Chamada pelo orquestrador (data/x_radar/__init__.py:executar_ciclo)
    DEPOIS do cruzamento - preenche classificacao['relevancia'/
    'relevancia_motivo'/'credibilidade'/'credibilidade_motivo'] in-place
    pra data/x_radar/store.py persistir."""
    from data.x_radar import TICKERS_FOCO
    from data.x_radar.store import historico_autor

    for item in enriquecidos:
        sinal, classificacao = item["sinal"], item["classificacao"]
        ticker_e_foco = (classificacao.get("ticker") or "") in TICKERS_FOCO
        score_rel, motivo_rel = calcular_relevancia(
            classificacao, ticker_e_foco=ticker_e_foco, horario_publicacao=sinal.horario_publicacao)
        classificacao["relevancia"], classificacao["relevancia_motivo"] = score_rel, motivo_rel

        historico = historico_autor(sinal.autor, excluir_post_id=sinal.post_id)
        score_cred, motivo_cred = calcular_credibilidade(sinal.autor, historico)
        classificacao["credibilidade"], classificacao["credibilidade_motivo"] = score_cred, motivo_cred
    return enriquecidos
