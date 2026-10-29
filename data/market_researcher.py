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
from data.market_makers import contexto_ticker
from data.radar import linha_valuation
from data.research import CASAS
from data.research.store import listar_itens
from data.supabase_client import obter_cliente

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


# ============================================================
# ANÁLISE POR TICKER - agregador PURO dos módulos acima + fundamentos
# (data/radar.py:linha_valuation) - nenhuma consulta nova, nenhum
# coletor novo, nenhuma chamada de IA. "Preparo da evolução" pedido:
# uma função de leitura que já junta tudo que o comitê de investimentos
# olharia pra 1 ativo, sem inventar uma conclusão em prosa por cima -
# cada bloco é exatamente o que o módulo de origem já produz, com a
# fonte/data dele preservada.
# ============================================================

def analise_ticker(ticker: str, janela: str = "7 DIAS") -> dict:
    """Visão agregada de 1 ticker: fundamentos (linha_valuation),
    catalisadores/mudança de tese/risco de indicador (contexto_ticker,
    data/market_makers.py) e cobertura de research entre casas
    (cobertura_cruzada_casas, acima). Cada bloco é None quando a fonte
    dele falha - nunca interrompe os demais nem inventa valor. `fontes_
    indisponiveis` lista, por nome, quais blocos falharam nesta chamada
    (lista vazia = todos os blocos responderam, não necessariamente com
    dado - um bloco pode responder com tudo None/[] legitimamente)."""
    ticker = (ticker or "").strip().upper()
    fontes_indisponiveis = []

    try:
        fundamentos = linha_valuation(ticker)
    except Exception as exc:
        print(f"[market_researcher] fundamentos indisponíveis pra {ticker}: {exc!r}")
        fundamentos = None
        fontes_indisponiveis.append("fundamentos")

    try:
        contexto = contexto_ticker(ticker, janela)
    except Exception as exc:
        print(f"[market_researcher] contexto de mercado indisponível pra {ticker}: {exc!r}")
        contexto = None
        fontes_indisponiveis.append("contexto_mercado")

    try:
        cobertura = cobertura_cruzada_casas(ticker)
    except Exception as exc:
        print(f"[market_researcher] cobertura de research indisponível pra {ticker}: {exc!r}")
        cobertura = None
        fontes_indisponiveis.append("cobertura_research")

    return {
        "ticker": ticker,
        "gerado_em": datetime.now(timezone.utc),
        "fundamentos": fundamentos,
        "catalisadores": (contexto or {}).get("catalisadores"),
        "mudancas_tese": (contexto or {}).get("mudancas"),
        "riscos_indicadores": (contexto or {}).get("riscos"),
        "interpretacao_movimento": (contexto or {}).get("interpretacao"),
        "cobertura_research": cobertura,
        "fontes_indisponiveis": fontes_indisponiveis,
    }


# ============================================================
# MEMÓRIA OPERACIONAL PERSISTENTE (sql/market_researcher_achados.sql)
#
# Upsert por `chave` (coletor|categoria|tipo) - um achado que continua
# acontecendo ATUALIZA a mesma linha (ultima_ocorrencia_em, ocorrencias
# +1), nunca acumula 1 linha por checagem. Achado aberto que deixa de
# aparecer na lista atual é marcado RESOLVIDO automaticamente - fecha o
# ciclo sem exigir ação manual por achado.
#
# Acionado pelo clique em "ATUALIZAR" (ui/saude_dados_tab.py) OU pelo
# job agendado jobs/coordenador.py (auditoria "Coordenador de
# Inteligência", 2026-10-29 - ver docs/auditoria-coordenador-
# inteligencia-20261029.md) - os dois caminhos chamam a mesma função,
# sem duplicar lógica.
# ============================================================
_TABELA_ACHADOS = "market_researcher_achados"

# Estados de triagem manual (Coordenador/Backoffice, 2026-10-29) - além
# de ABERTO/RESOLVIDO (os únicos que este módulo escrevia antes), a
# interface web agora permite o Rodrigo avançar um achado pra
# INVESTIGANDO/AGUARDANDO_INTERVENCAO/INCONCLUSIVO (ver
# web/lib/server/dominio/backoffice.ts:definirEstadoIncidente). Esses 3
# nunca são escritos por este módulo - só lidos/preservados.
_ESTADOS_TRIAGEM_MANUAL = ("INVESTIGANDO", "AGUARDANDO_INTERVENCAO", "INCONCLUSIVO")


def _chave_achado(coletor: str, categoria: str, tipo: str) -> str:
    return f"{coletor}|{categoria}|{tipo}"


def registrar_achados_atuais() -> dict:
    """Snapshot dos achados ATUAIS (achados_qualidade_coletores) na
    memória operacional persistente. Nunca lança excecao - banco fora
    do ar degrada pra {"ok": False, ...}."""
    cliente = obter_cliente()
    if cliente is None:
        return {"ok": False, "motivo": "Supabase indisponível"}
    achados_atuais = achados_qualidade_coletores()
    agora = datetime.now(timezone.utc).isoformat()
    chaves_atuais = set()
    try:
        for a in achados_atuais:
            chave = _chave_achado(a["coletor"], a["categoria"], a["codigo_estado"])
            chaves_atuais.add(chave)
            existente = (
                cliente.table(_TABELA_ACHADOS).select("id,ocorrencias")
                .eq("chave", chave).limit(1).execute()
            )
            if existente.data:
                linha = existente.data[0]
                atualizacao = {
                    "ultima_ocorrencia_em": agora, "ocorrencias": linha["ocorrencias"] + 1,
                    "descricao": a["rotulo_estado"],
                }
                # Nunca sobrescreve uma triagem manual em andamento (achado
                # real, 2026-10-29: antes desta checagem, rodar este job de
                # hora em hora - jobs/coordenador.py - resetava pra ABERTO
                # qualquer achado que o Rodrigo tivesse marcado
                # INVESTIGANDO/AGUARDANDO_INTERVENCAO/INCONCLUSIVO na
                # interface web, apagando o trabalho de triagem a cada
                # execução). Só reabre explicitamente um achado já
                # RESOLVIDO (o problema voltou a acontecer) - nunca um em
                # triagem manual.
                status_atual = linha.get("status")
                if status_atual not in _ESTADOS_TRIAGEM_MANUAL:
                    atualizacao["status"] = "ABERTO"
                cliente.table(_TABELA_ACHADOS).update(atualizacao).eq("id", linha["id"]).execute()
            else:
                cliente.table(_TABELA_ACHADOS).insert({
                    "chave": chave, "coletor": a["coletor"], "categoria": a["categoria"],
                    "tipo": a["codigo_estado"], "descricao": a["rotulo_estado"],
                    "severidade": "CRITICO" if a["critico"] else "ATENCAO", "status": "ABERTO",
                    "primeira_ocorrencia_em": agora, "ultima_ocorrencia_em": agora, "ocorrencias": 1,
                }).execute()

        abertos = cliente.table(_TABELA_ACHADOS).select("id,chave").eq("status", "ABERTO").execute()
        for linha in (abertos.data or []):
            if linha["chave"] not in chaves_atuais:
                cliente.table(_TABELA_ACHADOS).update(
                    {"status": "RESOLVIDO", "resolvido_em": agora}
                ).eq("id", linha["id"]).execute()
        return {"ok": True, "achados_atuais": len(achados_atuais)}
    except Exception as exc:
        print(f"[market_researcher] registrar_achados_atuais falhou: {exc!r}")
        return {"ok": False, "motivo": repr(exc)}


def historico_achado(coletor: str, categoria: str, tipo: str) -> dict | None:
    """Histórico persistido de UM achado específico (ocorrências, desde
    quando) - usado pra enriquecer a linha correspondente em
    "ACHADOS PRIORIZADOS" sem precisar listar a tabela inteira. None se
    o banco estiver indisponível OU não houver registro ainda (os dois
    casos tratados como "sem histórico disponível" por quem chama)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table(_TABELA_ACHADOS).select("*")
            .eq("chave", _chave_achado(coletor, categoria, tipo)).limit(1).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        print(f"[market_researcher] historico_achado falhou: {exc!r}")
        return None


def listar_achados_historico(status: str = None) -> list | None:
    """Histórico completo persistido - None se banco indisponível, []
    se ainda não há nenhum registro."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        consulta = cliente.table(_TABELA_ACHADOS).select("*").order("ultima_ocorrencia_em", desc=True)
        if status:
            consulta = consulta.eq("status", status)
        return consulta.execute().data or []
    except Exception as exc:
        print(f"[market_researcher] listar_achados_historico falhou: {exc!r}")
        return None
