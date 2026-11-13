# -*- coding: utf-8 -*-
"""Camada de dados da CARTEIRA RECOMENDADA (módulo novo, missão "Frente 4"
2026-11-12/13 - agente D da missão noturna).

Constrói uma carteira recomendada a partir das análises REAIS já
produzidas pelo Comitê de Investimentos (data/coordenador_central/*, via
jobs/comite_noturno.py - "Agente B" da mesma missão) - nunca gera sinal,
score ou preço-alvo próprio. Este módulo só SELECIONA, PESA e APRESENTA o
que o Comitê já concluiu, com os critérios explícitos pedidos: qualidade
da empresa + valuation + potencial (proxy único: o `sinal`/`score` do
Comitê, que já combina rentabilidade/margem/alavancagem/caixa/crescimento/
valuation relativo/research independente - ver data/research/sinal.py -
nunca reformulado aqui com um score concorrente), risco (confiança do
Comitê + lista de "contrários"), diversificação setorial e concentração
(limite por ativo e por setor), liquidez (cotação em tempo real quando
disponível), horizonte (documentado como suposição - o Comitê não define
um horizonte por ativo hoje) e cenário macro (Selic/CDI/Focus, mesmas
fontes do Morning Call - data/macro.py).

IMPORTANTE - separação de "carteira pessoal":
Esta carteira é uma recomendação institucional do PREGÃO, conceitualmente
SEPARADA das posições reais do Rodrigo (data/posicoes.py, tabela
posicoes_carteira) e das carteiras PÚBLICAS de terceiros monitoradas pelo
Radar de Quedas (data/radar_quedas.py, ex.: Genial/Itaú/Safra). Este
módulo nunca lê nem escreve nenhuma das duas - zero import de
data/posicoes.py.

Duas camadas:
1. CONSTRUÇÃO EM TEMPO REAL (montar_carteira_recomendada) - sempre
   disponível, não depende de nenhuma tabela nova: lê coordenador_analises
   (já existente) e monta a carteira do momento. histórico_alteracao vem
   vazio aqui ([]) até a 1a revisão persistida.
2. PERSISTÊNCIA (registrar_revisao/salvar_carteira/listar_historico_*/
   obter_ultima_carteira_persistida/registrar_acompanhamento) - segue o
   padrão "TABELA_AUSENTE" do resto do projeto (ex.: data/posicoes.py):
   nenhuma função aqui lança se as tabelas novas (sql/
   carteira_recomendada.sql, proposto mas NÃO aplicado nesta missão - ver
   MANUAL.md) ainda não existirem; elas degradam para None/False com o
   motivo, exatamente como qualquer outra tabela opcional do projeto.

Shape devolvido por montar_carteira_recomendada() - ESTÁVEL, documentado
para a UI (Agente A) consumir (aba nova em ui/navegacao.py, área
"carteira-recomendada"):

{
  "gerado_em": "2026-11-13T09:00:00-03:00",
  "criterios": {...texto explícito de cada critério usado, ver
                _CRITERIOS_EXPLICITOS...},
  "itens": [
    {
      "ticker": "PETR4",
      "setor": "Petróleo e Gás" | None,
      "peso_pct": 12.5,
      "justificativa": "texto curto citando sinal/score/confiança",
      "preco_referencia": 38.42,
      "preco_referencia_em": "2026-11-12T18:00:00+00:00" | None,
      "preco_alvo": 44.10,
      "metodo_preco_alvo": "consenso dos especialistas" | "modelo interno" | ...,
      "cenarios": {
        "conservador": {"preco": 40.5, "retorno_pct": 5.4},
        "base":        {"preco": 44.1, "retorno_pct": 14.8},
        "otimista":    {"preco": 47.6, "retorno_pct": 23.9},
        "aviso": "Cenários condicionais sobre o preço-alvo do Comitê;
                   NUNCA é retorno garantido.",
      } | None (sem preço-alvo confiável),
      "tese": "resumo_executivo do Comitê para este ticker",
      "riscos": ["lista de pontos contrários/atenção do Comitê"],
      "criterio_saida": "texto determinístico (ver _criterio_saida)",
      "data_revisao": "2026-12-13" (cadência padrão; ver _CADENCIA_REVISAO_DIAS),
      "liquidez": {"volume": 1234567, "consultado_em": "..."} | None,
      "confianca_comite": "ALTA" | "MÉDIA" | "BAIXA",
      "sinal_comite": "COMPRA",
      "score_comite": 6,
      "origem_analise_id": "uuid-hex",
      "origem_analise_em": "2026-11-12T03:10:00+00:00",
      "historico_alteracao": [],
    },
    ...
  ],
  "resumo": {
    "n_ativos": 8,
    "peso_total_pct": 100.0,
    "diversificacao_setorial": {"Petróleo e Gás": 12.5, ...},
    "setores_cobertos": 6,
    "concentracao_maxima_pct": 15.0,
    "horizonte": "texto",
    "correlacao": None,  # GAP documentado - ver _CRITERIOS_EXPLICITOS
    "cenario_macro": {...Selic/CDI/Focus, mesmas fontes do Morning Call},
  },
  "avisos": [...disclaimers: nunca garantido, fonte do universo, gaps...],
  "fonte_universo": "texto",
  "universo_consultado": 37,   # quantas análises CONCLUIDAs foram vistas
  "universo_elegivel": 14,     # quantas tinham sinal=COMPRA e dado suficiente
}
"""
from datetime import datetime, timedelta, timezone

TABELA_ITENS = "carteira_recomendada_itens"
TABELA_HISTORICO = "carteira_recomendada_historico"
TABELA_ACOMPANHAMENTO = "carteira_recomendada_acompanhamento"

_LIMITE_CONSULTADO_PADRAO = 500
_LIMITE_ATIVOS_PADRAO = 10
_MAXIMO_POR_SETOR_PADRAO = 3
_PESO_MAXIMO_PCT_PADRAO = 15.0
_CADENCIA_REVISAO_DIAS = 30
# Sinais aceitos como "elegível" pra entrar na carteira recomendada - só
# COMPRA (nunca NEUTRO/VENDA/INSUFICIENTE): esta é uma carteira de
# POSIÇÕES recomendadas, não um ranking completo do universo.
_SINAL_ELEGIVEL = "COMPRA"
# Confiança mínima pra entrar (BAIXA entra mas com destaque no risco;
# INSUFICIENTE nunca entra - mesma régua que data/research/sinal.py já
# usa pra classificar confiança).
_CONFIANCA_EXCLUIDA = {"INSUFICIENTE"}

_CRITERIOS_EXPLICITOS = {
    "qualidade_empresa_valuation_potencial": (
        "Proxy único: sinal/score do Comitê de Investimentos "
        "(data/research/sinal.py:calcular_sinal_comite), que já combina "
        "rentabilidade (ROE), margem líquida, alavancagem (dívida líquida/"
        "EBITDA), geração de caixa, crescimento de receita, valuation "
        "relativo (P/L vs. mediana setorial) e research independente. "
        "Este módulo nunca recalcula um score próprio - evita 2 fontes de "
        "verdade divergentes sobre o mesmo ativo."
    ),
    "risco": (
        "Confiança do Comitê (ALTA/MÉDIA/BAIXA/INSUFICIENTE) + lista de "
        "critérios 'contrários' (pontos negativos) da própria análise. "
        "INSUFICIENTE nunca entra na carteira."
    ),
    "diversificacao_setorial": (
        "Classificação setorial curada (data/research/classificacao.py, "
        "config.IBOVESPA_SETORES); no máximo "
        f"{_MAXIMO_POR_SETOR_PADRAO} ativos por setor nesta rodada."
    ),
    "liquidez": (
        "Volume da sessão mais recente (data/prices.py:obter_cotacao), "
        "consultado só para os ativos finalmente selecionados - nunca "
        "usado pra excluir um ativo nesta primeira versão (sem um piso "
        "de liquidez definido pelo Rodrigo ainda); aparece como "
        "informação de apoio na ficha de cada ativo."
    ),
    "horizonte": (
        "Suposição declarada, não um dado do Comitê: horizonte médio/longo "
        "prazo (o Comitê de Investimentos não define um horizonte por "
        "ativo hoje - GAP conhecido, documentado em vez de inventado)."
    ),
    "correlacao": (
        "GAP conhecido: não existe hoje no projeto um motor de correlação "
        "entre ativos. Não preenchido com número nesta missão para não "
        "inventar dado - aparece como None/ausente em todas as saídas."
    ),
    "concentracao": (
        f"Peso máximo de {_PESO_MAXIMO_PCT_PADRAO:.1f}% por ativo nesta "
        "rodada (parâmetro de montar_carteira_recomendada)."
    ),
    "cenario_macro": (
        "Selic meta, CDI e Boletim Focus (IPCA/Selic) - mesmas fontes já "
        "usadas pelo Morning Call (data/macro.py) - como contexto da "
        "rodada, nunca como critério de inclusão/exclusão individual."
    ),
}


def _agora_utc():
    return datetime.now(timezone.utc)


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


# ---------------------------------------------------------------------------
# 1. Leitura do universo (coordenador_analises, consumido - nunca editado)
# ---------------------------------------------------------------------------

def _analises_concluidas_recentes(limite_consultado: int, provedor_analises=None) -> list | None:
    """CONCLUIDA mais recente de cada ticker, dentre as `limite_consultado`
    análises mais recentes de TODO o universo (não é 1 análise por
    ticker dentro do próprio limite - a mesma estratégia de paginação em
    Python que jobs/comite_noturno.py:_tickers_com_analise_recente já usa,
    só que aqui dedupe por ticker em vez de montar um set). None só se o
    Supabase estiver indisponível; [] se não houver nenhuma análise
    CONCLUIDA ainda (estado normal antes do Comitê rodar pela 1a vez)."""
    if provedor_analises is None:
        from data.coordenador_central.persistencia import listar_analises_recentes
        provedor_analises = listar_analises_recentes
    linhas = provedor_analises(limite_consultado)
    if linhas is None:
        return None
    mais_recente_por_ticker = {}
    for linha in linhas:
        if linha.get("status") != "CONCLUIDA":
            continue
        ticker = str(linha.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        existente = mais_recente_por_ticker.get(ticker)
        if existente is None or (linha.get("iniciado_em") or "") > (existente.get("iniciado_em") or ""):
            mais_recente_por_ticker[ticker] = linha
    return list(mais_recente_por_ticker.values())


def _extrair_sinal(linha: dict) -> dict | None:
    """Campos do sinal_comite + resumo executivo de 1 linha de
    coordenador_analises - None quando a análise não tem sinal_comite
    (resultado ausente/malformado; nunca inventa um sinal)."""
    resultado = linha.get("resultado") or {}
    if not isinstance(resultado, dict):
        return None
    sinal_comite = resultado.get("sinal_comite") or {}
    sinal = sinal_comite.get("sinal")
    if not sinal:
        return None
    return {
        "ticker": str(linha.get("ticker") or "").strip().upper(),
        "sinal": sinal,
        "score": sinal_comite.get("score"),
        "confianca": sinal_comite.get("confianca"),
        "justificativa_sinal": sinal_comite.get("justificativa"),
        "favoraveis": list(sinal_comite.get("favoraveis") or []),
        "contrarios": list(sinal_comite.get("contrarios") or []),
        "preco_atual": _numero(sinal_comite.get("preco_atual")),
        "preco_atual_consultado_em": sinal_comite.get("preco_atual_consultado_em"),
        "preco_alvo_consenso": _numero(sinal_comite.get("preco_alvo_consenso")),
        "preco_alvo_modelo": _numero(sinal_comite.get("preco_alvo_modelo")),
        "metodo_preco_alvo_modelo": sinal_comite.get("metodo_preco_alvo_modelo"),
        "preco_alvo_pl_setorial": _numero(sinal_comite.get("preco_alvo_pl_setorial")),
        "resumo_executivo": resultado.get("resumo_executivo"),
        "analise_id": linha.get("id"),
        "analise_em": linha.get("iniciado_em"),
    }


# ---------------------------------------------------------------------------
# 2. Cenários e critério de saída (derivados, nunca um número novo)
# ---------------------------------------------------------------------------

_AVISO_CENARIO = ("Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de "
                  "Investimentos - nunca é retorno garantido nem previsão de probabilidade.")


def _preco_alvo_e_metodo(sinal: dict) -> tuple:
    """Preço-alvo único pra esta carteira: consenso dos especialistas
    primeiro (visão mais ampla), senão o do modelo interno. None quando
    nenhum dos dois está disponível (item ainda entra na carteira pelo
    sinal, mas sem cenários de preço)."""
    if sinal.get("preco_alvo_consenso") is not None:
        return sinal["preco_alvo_consenso"], "consenso dos especialistas do Comitê"
    if sinal.get("preco_alvo_modelo") is not None:
        return sinal["preco_alvo_modelo"], sinal.get("metodo_preco_alvo_modelo") or "modelo interno do Comitê"
    return None, None


def _cenarios(preco_atual, preco_alvo, preco_alvo_pl_setorial) -> dict | None:
    """3 cenários determinísticos a partir de números JÁ calculados pelo
    Comitê (nunca um preço novo):
    - base: o preço-alvo escolhido (_preco_alvo_e_metodo).
    - otimista: o maior entre preço-alvo escolhido e preço-alvo por P/L
      setorial (quando este for mais otimista) - nunca inventado, é outro
      campo que o próprio Comitê já calculou.
    - conservador: ponto médio entre o preço atual e o preço-alvo base -
      metade do caminho até a tese se confirmar, não um novo modelo.
    None se preço atual ou preço-alvo base não estiverem disponíveis."""
    if preco_atual is None or preco_atual <= 0 or preco_alvo is None:
        return None
    conservador = preco_atual + (preco_alvo - preco_atual) / 2
    otimista = preco_alvo
    if preco_alvo_pl_setorial is not None and preco_alvo_pl_setorial > preco_alvo:
        otimista = preco_alvo_pl_setorial

    def _cenario(preco):
        retorno_pct = ((preco - preco_atual) / preco_atual) * 100
        return {"preco": round(preco, 2), "retorno_pct": round(retorno_pct, 1)}

    return {
        "conservador": _cenario(conservador),
        "base": _cenario(preco_alvo),
        "otimista": _cenario(otimista),
        "aviso": _AVISO_CENARIO,
    }


def _criterio_saida(sinal: dict) -> str:
    """Texto determinístico - sempre o mesmo gatilho pro mesmo tipo de
    situação, nunca um texto gerado por IA pra este campo (critério de
    saída precisa ser auditável e estável)."""
    base = ("Reavaliar a posição se o Comitê de Investimentos rebaixar o sinal deste "
            "ativo para NEUTRO ou VENDA na próxima rodada, ")
    if sinal.get("confianca") == "BAIXA":
        return base + "ou antes disso - a confiança atual já é BAIXA, revisão prioritária na próxima rodada do Comitê."
    return base + "ou se a tese resumida na análise não se confirmar até a data de revisão."


# ---------------------------------------------------------------------------
# 3. Construção da carteira (em tempo real - não depende de tabela nova)
# ---------------------------------------------------------------------------

def _classificar_setor(ticker: str):
    try:
        from data.research.classificacao import classificar_setor
        return classificar_setor(ticker)
    except Exception:
        return None


def _liquidez(ticker: str, provedor_cotacao=None) -> dict | None:
    """Volume da cotação mais recente - melhor esforço, nunca derruba a
    construção da carteira se o provedor (yfinance) falhar ou estiver
    indisponível neste ambiente (ex.: execução em teste, sem rede)."""
    try:
        if provedor_cotacao is None:
            from data.prices import obter_cotacao
            provedor_cotacao = obter_cotacao
        cotacao = provedor_cotacao(ticker) or {}
        volume = cotacao.get("volume")
        if volume is None:
            return None
        return {"volume": volume, "consultado_em": cotacao.get("cotacao_em")}
    except Exception as exc:
        print(f"[carteira_recomendada] liquidez indisponível para {ticker}: {exc!r}")
        return None


def _contexto_macro() -> dict:
    """Mesmas fontes (Selic/CDI/Focus) do Morning Call - nunca uma leitura
    nova. Melhor esforço: cada fonte que falhar vira None, nunca derruba
    o resto da carteira."""
    contexto = {}
    try:
        from data.macro import obter_cdi, obter_focus_ipca, obter_selic_meta
        for nome, fn in (("selic_meta", obter_selic_meta), ("cdi", obter_cdi), ("focus_ipca", obter_focus_ipca)):
            try:
                contexto[nome] = fn()
            except Exception as exc:
                print(f"[carteira_recomendada] contexto macro ({nome}) indisponível: {exc!r}")
                contexto[nome] = None
    except Exception as exc:
        print(f"[carteira_recomendada] contexto macro indisponível: {exc!r}")
    return contexto


def montar_carteira_recomendada(
    limite_ativos: int = _LIMITE_ATIVOS_PADRAO,
    limite_consultado: int = _LIMITE_CONSULTADO_PADRAO,
    maximo_por_setor: int = _MAXIMO_POR_SETOR_PADRAO,
    peso_maximo_pct: float = _PESO_MAXIMO_PCT_PADRAO,
    agora=None,
    provedor_analises=None,
    provedor_cotacao=None,
    incluir_liquidez: bool = True,
    incluir_macro: bool = True,
) -> dict:
    """Monta a carteira recomendada do momento - nunca persiste nada (ver
    salvar_carteira pra persistência). Determinístico dado o mesmo
    conjunto de análises CONCLUIDA: útil pra teste sem rede/Supabase via
    `provedor_analises`/`provedor_cotacao` injetados.

    Seleção: só sinal COMPRA, confiança != INSUFICIENTE, ordenado por
    score desc (maior convicção primeiro); limite por setor aplicado na
    MESMA ordem (um ativo de score menor só entra se o setor dele ainda
    não atingiu `maximo_por_setor`). Peso: igual entre os selecionados,
    nunca acima de `peso_maximo_pct` - o excedente de quem bateria no teto
    é redistribuído pelos demais (nunca descartado nem deixa a soma
    diferente de 100%, exceto quando o teto por si só impede 100% - nesse
    caso a soma fica abaixo de 100% e o resumo mostra isso, nunca força um
    peso maior que o teto)."""
    agora = agora or _agora_utc()
    linhas = _analises_concluidas_recentes(limite_consultado, provedor_analises)
    if linhas is None:
        return {
            "gerado_em": agora.isoformat(),
            "criterios": _CRITERIOS_EXPLICITOS,
            "itens": [],
            "resumo": None,
            "avisos": ["Não foi possível consultar as análises do Comitê de Investimentos "
                       "(Supabase indisponível) - carteira não pôde ser montada nesta execução."],
            "fonte_universo": _FONTE_UNIVERSO,
            "universo_consultado": None,
            "universo_elegivel": 0,
        }

    sinais = [s for s in (_extrair_sinal(linha) for linha in linhas) if s is not None]
    elegiveis = [
        s for s in sinais
        if s["sinal"] == _SINAL_ELEGIVEL and s.get("confianca") not in _CONFIANCA_EXCLUIDA
    ]
    elegiveis.sort(key=lambda s: (s.get("score") if s.get("score") is not None else -999), reverse=True)

    selecionados = []
    contagem_setor = {}
    for sinal in elegiveis:
        if len(selecionados) >= limite_ativos:
            break
        setor = _classificar_setor(sinal["ticker"])
        if setor and contagem_setor.get(setor, 0) >= maximo_por_setor:
            continue
        selecionados.append((sinal, setor))
        if setor:
            contagem_setor[setor] = contagem_setor.get(setor, 0) + 1

    n = len(selecionados)
    peso_igual = min(peso_maximo_pct, 100.0 / n) if n else 0.0

    itens = []
    diversificacao = {}
    for sinal, setor in selecionados:
        ticker = sinal["ticker"]
        preco_alvo, metodo = _preco_alvo_e_metodo(sinal)
        cenarios = _cenarios(sinal.get("preco_atual"), preco_alvo, sinal.get("preco_alvo_pl_setorial"))
        liquidez = _liquidez(ticker, provedor_cotacao) if incluir_liquidez else None
        item = {
            "ticker": ticker,
            "setor": setor,
            "peso_pct": round(peso_igual, 2),
            "justificativa": (sinal.get("justificativa_sinal") or
                               f"Sinal {sinal['sinal']} do Comitê (score {sinal.get('score')}, confiança {sinal.get('confianca')})."),
            "preco_referencia": sinal.get("preco_atual"),
            "preco_referencia_em": sinal.get("preco_atual_consultado_em"),
            "preco_alvo": preco_alvo,
            "metodo_preco_alvo": metodo,
            "cenarios": cenarios,
            "tese": sinal.get("resumo_executivo"),
            "riscos": sinal.get("contrarios") or [],
            "criterio_saida": _criterio_saida(sinal),
            "data_revisao": (agora + timedelta(days=_CADENCIA_REVISAO_DIAS)).date().isoformat(),
            "liquidez": liquidez,
            "confianca_comite": sinal.get("confianca"),
            "sinal_comite": sinal.get("sinal"),
            "score_comite": sinal.get("score"),
            "origem_analise_id": sinal.get("analise_id"),
            "origem_analise_em": sinal.get("analise_em"),
            "historico_alteracao": [],
        }
        itens.append(item)
        if setor:
            diversificacao[setor] = round(diversificacao.get(setor, 0.0) + peso_igual, 2)

    resumo = {
        "n_ativos": n,
        "peso_total_pct": round(sum(i["peso_pct"] for i in itens), 2),
        "diversificacao_setorial": diversificacao,
        "setores_cobertos": len(diversificacao),
        "concentracao_maxima_pct": peso_maximo_pct,
        "horizonte": _CRITERIOS_EXPLICITOS["horizonte"],
        "correlacao": None,
        "cenario_macro": _contexto_macro() if incluir_macro else None,
    }

    avisos = [
        "Carteira recomendada informativa - NÃO constitui recomendação de investimento "
        "personalizada nem garante rentabilidade; cenários são condicionais.",
        f"Universo considerado: {len(linhas)} tickers com análise CONCLUIDA mais recente "
        f"dentre as últimas {limite_consultado} análises do Comitê.",
        _CRITERIOS_EXPLICITOS["correlacao"],
    ]
    if not itens:
        avisos.append("Nenhum ativo com sinal COMPRA e confiança suficiente no momento - "
                       "carteira vazia não é erro, é o estado real do universo analisado hoje.")

    return {
        "gerado_em": agora.isoformat(),
        "criterios": _CRITERIOS_EXPLICITOS,
        "itens": itens,
        "resumo": resumo,
        "avisos": avisos,
        "fonte_universo": _FONTE_UNIVERSO,
        "universo_consultado": len(linhas),
        "universo_elegivel": len(elegiveis),
    }


_FONTE_UNIVERSO = (
    "Comitê de Investimentos (jobs/comite_noturno.py, análise noturna automática) via "
    "coordenador_analises (data/coordenador_central/*) - cobre watchlists reais dos "
    "usuários + carteiras públicas vigentes (Genial/Itaú/Safra, data/radar_quedas.py) "
    "como universo de entrada, nunca como fonte do sinal em si."
)


# ---------------------------------------------------------------------------
# 4. Persistência (tabelas PROPOSTAS, NÃO aplicadas nesta missão - ver
#    sql/carteira_recomendada.sql). Segue o padrão "degrada sem lançar"
#    de data/posicoes.py: tabela ausente -> None/False, nunca exceção.
# ---------------------------------------------------------------------------

def _cliente_ou_none():
    try:
        from data.supabase_client import obter_cliente
        return obter_cliente()
    except Exception:
        return None


def salvar_carteira(itens: list, agora=None) -> bool:
    """Substitui o snapshot vigente em carteira_recomendada_itens por
    `itens` (shape de montar_carteira_recomendada()['itens']) - 1 UPSERT
    por ticker, nunca um DELETE em massa sem filtro (regra do projeto:
    "nunca deletar em massa tabela compartilhada" - cada linha é
    substituída pelo PRÓPRIO ticker, nunca a tabela inteira é limpa
    primeiro). False (sem lançar) se a tabela ainda não existir ou o
    Supabase estiver indisponível."""
    cliente = _cliente_ou_none()
    if cliente is None or not itens:
        return False
    agora = agora or _agora_utc()
    try:
        for item in itens:
            cliente.table(TABELA_ITENS).upsert({
                "ticker": item["ticker"],
                "setor": item.get("setor"),
                "peso_pct": item.get("peso_pct"),
                "justificativa": item.get("justificativa"),
                "preco_referencia": item.get("preco_referencia"),
                "preco_alvo": item.get("preco_alvo"),
                "tese": item.get("tese"),
                "riscos": item.get("riscos"),
                "criterio_saida": item.get("criterio_saida"),
                "data_revisao": item.get("data_revisao"),
                "origem_analise_id": item.get("origem_analise_id"),
                "atualizado_em": agora.isoformat(),
            }, on_conflict="ticker").execute()
        return True
    except Exception as exc:
        print(f"[carteira_recomendada] salvar_carteira falhou (tabela ainda não existe?): {exc!r}")
        return False


def obter_ultima_carteira_persistida() -> list | None:
    """Snapshot persistido mais recente - None se Supabase indisponível
    OU tabela ainda não existir (sql/carteira_recomendada.sql não
    aplicado); [] se a tabela existe mas está vazia."""
    cliente = _cliente_ou_none()
    if cliente is None:
        return None
    try:
        resp = cliente.table(TABELA_ITENS).select("*").order("peso_pct", desc=True).execute()
        return resp.data or []
    except Exception as exc:
        print(f"[carteira_recomendada] obter_ultima_carteira_persistida indisponível: {exc!r}")
        return None


def registrar_revisao(ticker: str, campo: str, valor_anterior, valor_novo, motivo: str, agora=None) -> bool:
    """1 linha de histórico (nunca sobrescreve a anterior - histórico é
    append-only) em carteira_recomendada_historico. False sem lançar se
    a tabela não existir ainda."""
    cliente = _cliente_ou_none()
    if cliente is None:
        return False
    agora = agora or _agora_utc()
    try:
        cliente.table(TABELA_HISTORICO).insert({
            "ticker": ticker,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "motivo": motivo,
            "registrado_em": agora.isoformat(),
        }).execute()
        return True
    except Exception as exc:
        print(f"[carteira_recomendada] registrar_revisao falhou (tabela ainda não existe?): {exc!r}")
        return False


def listar_historico_alteracoes(ticker: str | None = None, limite: int = 100) -> list | None:
    """Histórico de alterações - de 1 ticker (ticker=...) ou de toda a
    carteira. None se Supabase indisponível/tabela ausente; [] se a
    tabela existe mas não há histórico ainda (carteira recém-criada)."""
    cliente = _cliente_ou_none()
    if cliente is None:
        return None
    try:
        consulta = cliente.table(TABELA_HISTORICO).select("*").order("registrado_em", desc=True).limit(limite)
        if ticker:
            consulta = consulta.eq("ticker", ticker.strip().upper())
        return consulta.execute().data or []
    except Exception as exc:
        print(f"[carteira_recomendada] listar_historico_alteracoes indisponível: {exc!r}")
        return None


def registrar_acompanhamento(data_referencia, itens_com_preco_atual: list) -> bool:
    """1 linha por ativo em carteira_recomendada_acompanhamento - captura
    recomendado (peso/preço de referência na data da recomendação, já
    conhecidos) vs. efetivo (preço atual em `data_referencia`, informado
    por quem chama) pra permitir comparar desempenho esperado x realizado
    ao longo do tempo. Pensado pra rodar periodicamente (job futuro,
    fora do escopo desta missão) - aqui só a gravação. False sem lançar
    se a tabela não existir ainda."""
    cliente = _cliente_ou_none()
    if cliente is None or not itens_com_preco_atual:
        return False
    try:
        linhas = [{
            "ticker": item["ticker"],
            "data_referencia": data_referencia.isoformat() if hasattr(data_referencia, "isoformat") else data_referencia,
            "peso_recomendado_pct": item.get("peso_pct"),
            "preco_referencia": item.get("preco_referencia"),
            "preco_atual": item.get("preco_atual"),
            "retorno_pct": item.get("retorno_pct"),
        } for item in itens_com_preco_atual]
        cliente.table(TABELA_ACOMPANHAMENTO).insert(linhas).execute()
        return True
    except Exception as exc:
        print(f"[carteira_recomendada] registrar_acompanhamento falhou (tabela ainda não existe?): {exc!r}")
        return False


def obter_acompanhamento(ticker: str | None = None, limite: int = 200) -> list | None:
    """Histórico de acompanhamento - None se Supabase indisponível/tabela
    ausente; [] se a tabela existe mas não há registro ainda."""
    cliente = _cliente_ou_none()
    if cliente is None:
        return None
    try:
        consulta = (cliente.table(TABELA_ACOMPANHAMENTO).select("*")
                    .order("data_referencia", desc=True).limit(limite))
        if ticker:
            consulta = consulta.eq("ticker", ticker.strip().upper())
        return consulta.execute().data or []
    except Exception as exc:
        print(f"[carteira_recomendada] obter_acompanhamento indisponível: {exc!r}")
        return None
