# -*- coding: utf-8 -*-
"""MARKET RESEARCHER: camada de avaliacao de qualidade e comparacao
entre fontes - NAO e' uma pagina nova, NAO e' um coletor novo, NAO faz
nenhuma chamada de IA nova. E' uma fachada sobre o que ja existe:

- data/saude_dados.py (REGISTRO_COLETORES/classificar_estado): quem ja
  distingue "fonte indisponivel" de "fonte que coletou e nao achou
  novidade" e de "nunca executou" - este modulo so' PRIORIZA esses
  achados por impacto, nao recalcula nada.
- data/research/store.py (listar_itens) + data/research/__init__.py
  (CASAS): itens de research ja persistidos, com `tickers`/
  `recomendacao`/`preco_alvo` quando o coletor da casa extrai isso.

Correcao de escopo (23/10/2026): a integracao anterior rotulada "Market
Researcher" (data/research/tese.py, PR #134) e' uma funcionalidade real
e valida - registro de tese PROPRIA do usuario - mas nao e' a camada de
inteligencia/comite de investimentos descrita aqui. Nao foi removida
(preserva trabalho valido); este modulo e' a peca que faltava.

Principios (nunca violados):
- Toda conclusao cita fonte real (nome da casa, data, link) ou declara
  evidencia insuficiente - nunca uma inferencia apresentada como fato.
- "Contradicao de recomendacao" so' e' apontada quando >=2 casas tem o
  CAMPO ESTRUTURADO `recomendacao` preenchido pro mesmo ticker (nunca
  comparando titulo/sentimento de materia, que seria uma inferencia
  nao verificavel) - hoje, na pratica, so' a Genial Analisa extrai esse
  campo de forma confiavel (ver data/research/genial.py), entao esta
  checagem raramente dispara ainda; fica pronta pra quando mais casas
  tiverem o campo.
- Falha de UMA fonte nunca contamina as demais (mesmo padrao de
  data/market_makers.py): cada bloco degrada sozinho."""
from datetime import datetime, timezone

from data import saude_dados
from data.research import CASAS
from data.research.store import listar_itens

# ordem de severidade pra priorizar achados (mais grave primeiro) -
# mesmos codigos de data/saude_dados.py:ESTADOS, nenhum novo criado aqui.
_PRIORIDADE_ESTADO = {
    "FALHA_PERSISTENCIA": 0,
    "FALHA_EXECUCAO": 1,
    "FONTE_INDISPONIVEL": 2,
    "DADOS_DESATUALIZADOS": 3,
    "NUNCA_EXECUTADO": 4,
    "NAO_COMPROVADO": 5,
    "PARCIAL": 6,
    "SUCESSO_SEM_NOVIDADE": 7,
    "SUCESSO_COM_NOVIDADE": 8,
}

# categorias reais de REGISTRO_COLETORES (data/saude_dados.py) cuja
# falha afeta diretamente o pipeline principal (cotação/notícia/macro/
# CVM/Radar/Morning Call) - achado crítico sobe de prioridade mesmo com
# o mesmo codigo_estado de um coletor secundario (Research/Calendario/
# Earnings, ainda importantes mas nao bloqueiam o nucleo do app).
_CATEGORIAS_CRITICAS = {"Noticias", "Cotacoes", "Macro", "CVM", "Radar", "Morning Call"}


def achados_qualidade_coletores() -> list:
    """Achados priorizados (mais grave e mais crítico primeiro) a partir
    do painel de saúde já existente (data/saude_dados.obter_painel_saude)
    - nenhuma consulta nova, só ranking + evidência explícita. [] se o
    painel não puder ser montado (nunca lança exceção)."""
    try:
        painel = saude_dados.obter_painel_saude()
    except Exception as exc:
        print(f"[market_researcher] painel de saúde indisponível: {exc!r}")
        return []

    achados = []
    for item in painel:
        if not item.get("alerta") and not item.get("desconhecido"):
            continue  # SUCESSO_* nunca é um "achado" - só o que precisa de atenção
        codigo = item["codigo_estado"]
        status_bruto = item.get("status_bruto") or {}
        achados.append({
            "coletor": item["nome"],
            "categoria": item["categoria"],
            "codigo_estado": codigo,
            "rotulo_estado": item["rotulo_estado"],
            "critico": item["categoria"] in _CATEGORIAS_CRITICAS,
            "evidencia": {
                "ultimo_sucesso_em": status_bruto.get("ultimo_sucesso_em"),
                "ultima_tentativa_em": status_bruto.get("ultima_tentativa_em"),
                "ultimo_erro": status_bruto.get("ultimo_erro"),
            },
        })
    achados.sort(key=lambda a: (not a["critico"], _PRIORIDADE_ESTADO.get(a["codigo_estado"], 9)))
    return achados


def _casas_ativas_nomes() -> list:
    return [c["nome"] for c in CASAS if c.get("ativa_por_padrao")]


def cobertura_cruzada_casas(ticker: str, dias: int = 30) -> dict:
    """Pra UM ticker: quais casas monitoradas publicaram algo recente
    (fato - quem, quando, link), quais não têm nada (lacuna - fato), e
    se há recomendação estruturada divergente entre casas (só quando o
    dado permite, nunca inferida). None em "itens" = banco indisponível
    (distinto de [] = banco respondeu e não achou nada)."""
    ticker = (ticker or "").strip().upper()
    casas_monitoradas = _casas_ativas_nomes()
    try:
        itens = listar_itens(casas_monitoradas)
    except Exception as exc:
        print(f"[market_researcher] cobertura cruzada indisponível: {exc!r}")
        itens = None

    if itens is None:
        return {"ticker": ticker, "cobertura": None, "sem_cobertura": [], "divergencia": None}

    do_ticker = [i for i in itens if ticker in (i.get("tickers") or [])]
    agora = datetime.now(timezone.utc)
    recentes = []
    for item in do_ticker:
        data_item = item.get("data")
        if not data_item:
            continue
        try:
            dt = datetime.fromisoformat(str(data_item))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (agora - dt).days <= dias:
            recentes.append(item)

    por_casa = {}
    for item in sorted(recentes, key=lambda i: i.get("data") or "", reverse=True):
        por_casa.setdefault(item["casa"], item)  # mais recente primeiro já ordenado

    cobertura = [
        {"casa": casa, "data": item.get("data"), "titulo": item.get("titulo"), "link": item.get("link"),
         "recomendacao": item.get("recomendacao") or None, "preco_alvo": item.get("preco_alvo")}
        for casa, item in por_casa.items()
    ]
    sem_cobertura = sorted(set(casas_monitoradas) - set(por_casa.keys()))

    recomendacoes = {
        casa: item["recomendacao"] for casa, item in por_casa.items() if item.get("recomendacao")
    }
    divergencia = None
    if len(set(recomendacoes.values())) > 1:
        divergencia = {
            "descricao": f"Recomendação estruturada diverge entre casas pra {ticker}.",
            "por_casa": recomendacoes,
        }

    return {
        "ticker": ticker, "janela_dias": dias,
        "cobertura": cobertura, "sem_cobertura": sem_cobertura, "divergencia": divergencia,
    }
