# -*- coding: utf-8 -*-
"""Historico de teses de investimento por usuario+ticker (tabela
research_teses, ver sql/research_teses.sql) - adaptacao do skill
"thesis-tracker" do Market Researcher oficial da Anthropic
(plugins/vertical-plugins/equity-research/skills/thesis-tracker) pro
Supabase ja usado pelo projeto.

Cada registrar_versao() grava uma linha NOVA (nunca UPDATE) - log
append-only, mesmo padrao de data/research/historico.py
(research_recomendacoes_historico): "track disconfirming evidence as
rigorously as confirming evidence" (nota do skill original) so' funciona
se nada for sobrescrito - mesmo se a tese nao mudou, o usuario decidiu
revisitar e reafirmar, e isso e' um fato que vale registrar.

Escopo por usuario (usuario_sub, chave do Google login - ver auth.py):
uma tese e' uma leitura pessoal de quem a escreveu, diferente de
research_itens (editorial, compartilhado entre todos os usuarios)."""

from datetime import datetime, timezone

from data.supabase_client import obter_cliente

_CONVICCOES_VALIDAS = ("ALTA", "MEDIA", "BAIXA")
_POSICOES_VALIDAS = ("LONG", "SHORT")


def registrar_versao(
    usuario_sub: str,
    ticker: str,
    tese: str,
    premissas: list[str] | None = None,
    riscos: list[str] | None = None,
    catalisadores: list[str] | None = None,
    conviccao: str | None = None,
    preco_alvo_tese: float | None = None,
    posicao: str | None = None,
) -> dict | None:
    """Grava uma nova versao da tese pra esse usuario+ticker. Levanta
    ValueError se `conviccao`/`posicao` vierem fora do vocabulario
    esperado (erro de programacao/UI, nao de dado externo - falha alto
    e cedo em vez de gravar um valor que a UI depois nao sabe exibir).
    Retorna a linha gravada (dict), ou None se o banco estiver fora do
    ar ou o INSERT falhar."""
    if not tese or not tese.strip():
        raise ValueError("tese nao pode ser vazia - toda versao precisa de uma frase central.")
    if conviccao is not None and conviccao not in _CONVICCOES_VALIDAS:
        raise ValueError(f"conviccao invalida: {conviccao!r} (esperado um de {_CONVICCOES_VALIDAS})")
    if posicao is not None and posicao not in _POSICOES_VALIDAS:
        raise ValueError(f"posicao invalida: {posicao!r} (esperado um de {_POSICOES_VALIDAS})")

    cliente = obter_cliente()
    if cliente is None:
        return None
    linha = {
        "usuario_sub": usuario_sub,
        "ticker": ticker,
        "posicao": posicao,
        "tese": tese.strip(),
        "premissas": list(premissas or []),
        "riscos": list(riscos or []),
        "catalisadores": list(catalisadores or []),
        "conviccao": conviccao,
        "preco_alvo_tese": preco_alvo_tese,
    }
    try:
        resp = cliente.table("research_teses").insert(linha).execute()
        return resp.data[0] if resp.data else linha
    except Exception:
        return None


def historico_tese(usuario_sub: str, ticker: str, limite: int = 10) -> list:
    """Ultimas `limite` versoes (mais recente primeiro) da tese desse
    usuario+ticker. [] se nunca houve nenhuma ou o banco estiver fora
    do ar - nunca distingue os dois casos (mesmo padrao de
    data/research/historico.py:historico_ticker)."""
    cliente = obter_cliente()
    if cliente is None:
        return []
    try:
        resp = (
            cliente.table("research_teses")
            .select("*")
            .eq("usuario_sub", usuario_sub).eq("ticker", ticker)
            .order("registrado_em", desc=True)
            .limit(limite)
            .execute()
        )
        return resp.data
    except Exception:
        return []


def tese_atual(usuario_sub: str, ticker: str) -> dict | None:
    """Versao mais recente da tese, ou None se nunca houve nenhuma ou o
    banco estiver fora do ar."""
    versoes = historico_tese(usuario_sub, ticker, limite=1)
    return versoes[0] if versoes else None


def scorecard(usuario_sub: str, ticker: str) -> dict | None:
    """Resumo pronto pra UI: tese atual + quantas versoes existem +
    data da primeira/ultima. None se nunca houve nenhuma tese
    registrada pra esse usuario+ticker (nao e' erro - so' significa
    'ainda sem tese escrita').

    Nao faz tracking granular por premissa (o skill original sugere uma
    tabela Premissa|Status|Tendencia por item individual) - escopo
    deliberadamente menor nesta primeira versao: o valor real esta' em
    *ter* um historico versionado de tese pra comparar, nao em marcar
    status individual de cada premissa sem uma UI dedicada pra mante-lo
    atualizado (ver docs/market-researcher-integracao.md, secao de
    limitacoes)."""
    versoes = historico_tese(usuario_sub, ticker, limite=50)
    if not versoes:
        return None
    atual = versoes[0]
    return {
        "ticker": ticker,
        "tese_atual": atual.get("tese"),
        "posicao": atual.get("posicao"),
        "premissas": atual.get("premissas") or [],
        "riscos": atual.get("riscos") or [],
        "catalisadores": atual.get("catalisadores") or [],
        "conviccao": atual.get("conviccao"),
        "preco_alvo_tese": atual.get("preco_alvo_tese"),
        "registrado_em": atual.get("registrado_em"),
        "n_versoes": len(versoes),
        "primeira_versao_em": versoes[-1].get("registrado_em"),
    }
