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
   obter_ultima_carteira_persistida/registrar_acompanhamento/
   comparar_carteira_persistida_com_atual) - segue o padrão
   "TABELA_AUSENTE" do resto do projeto (ex.: data/posicoes.py): nenhuma
   função aqui lança se as tabelas (sql/carteira_recomendada.sql,
   APLICADAS em produção em 2026-11-14, com aprovação explícita) ficarem
   indisponíveis por qualquer motivo; elas degradam para None/False com o
   motivo, exatamente como qualquer outra tabela opcional do projeto.
   comparar_carteira_persistida_com_atual é o elo que fecha o ciclo
   "persistir histórico, acompanhar recomendações e comparar resultados":
   pega o snapshot salvo por salvar_carteira, busca o preço ATUAL de cada
   ticker e grava a checagem via registrar_acompanhamento.
   O job que roda este ciclo 1x/dia (monta -> compara com o snapshot
   anterior -> salva -> registra só o que mudou no histórico -> grava o
   acompanhamento do dia) é jobs/carteira_recomendada_job.py, plugado no
   mesmo agendamento noturno do Comitê de Investimentos
   (jobs/comite_noturno.py via .github/workflows/comite-noturno.yml) -
   missão de 2026-11-14.

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
      "confianca_comite": "ALTA" | "MEDIA" | "BAIXA",
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
    "cenario_macro": {  # valor MAIS RECENTE de cada série, nunca a série
                         # histórica inteira (ver _contexto_macro) -
                         # mesmo contrato de _linha_macro em
                         # data/morning_call_editorial.py
      "Selic meta": {"valor": 13.75, "unidade": "% a.a.", "referencia": "...",
                      "detalhe": None, "erro": None},
      "CDI": {...}, "Focus IPCA 2026": {...}, "Focus Selic 2026": {...}, ...
    },
  },
  "avisos": [...disclaimers: nunca garantido, fonte do universo, gaps...],
  "fonte_universo": "texto",
  "universo_consultado": 37,   # quantas análises CONCLUIDAs foram vistas
  "universo_elegivel": 14,     # quantas tinham sinal=COMPRA e dado suficiente
}
"""
from datetime import date, datetime, timedelta, timezone

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
        "Confiança do Comitê (ALTA/MEDIA/BAIXA/INSUFICIENTE) + lista de "
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
    nova. Reaproveita data/morning_call_editorial.py:_macro_rows (já
    reduz cada série ao valor MAIS RECENTE, com o mesmo fallback Selic
    via Copom que o Morning Call usa) em vez de reimplementar a extração
    aqui.

    BUG corrigido nesta validação (2026-11-13): a versão anterior
    guardava o retorno CRU de obter_selic_meta/obter_cdi/obter_focus_ipca
    em cada chave - um DataFrame de até ~400 linhas de histórico, não um
    "contexto da rodada". Isso nunca quebrou a montagem da carteira em si
    (o shape não é validado por schema), mas tornava `resumo` não
    serializável em JSON e inútil pra qualquer UI/consumidor que espere
    um valor atual (ex.: 'Selic meta: 13,75% a.a.'), não uma série. Agora
    cada indicador vira {"valor", "unidade", "referencia", "detalhe",
    "erro"} - mesmo contrato de _linha_macro.

    Melhor esforço: indicador que falhar entra com valor=None + motivo em
    "erro" (nunca derruba o resto da carteira)."""
    try:
        from data.morning_call_editorial import _macro_rows
    except Exception as exc:
        print(f"[carteira_recomendada] contexto macro indisponível: {exc!r}")
        return {}
    contexto = {}
    try:
        for linha in _macro_rows():
            nome = linha.get("indicador")
            if not nome:
                continue
            contexto[nome] = {
                "valor": linha.get("valor"),
                "unidade": linha.get("unidade"),
                "referencia": linha.get("referencia"),
                "detalhe": linha.get("detalhe"),
                "erro": linha.get("erro"),
            }
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
# 4. Persistência (tabelas APLICADAS em produção em 2026-11-14 - ver
#    sql/carteira_recomendada.sql). Segue o padrão "degrada sem lançar"
#    de data/posicoes.py: tabela ausente/Supabase indisponível -> None/
#    False, nunca exceção. Chamadas 1x/dia por jobs/carteira_recomendada_job.py.
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
    ao longo do tempo. Pensado pra rodar periodicamente (job futuro, fora
    do escopo desta missão) - aqui só a gravação. UPSERT por
    (ticker, data_referencia) - mesma chave unique de sql/
    carteira_recomendada.sql - nunca um INSERT simples: uma reexecução no
    mesmo dia (retry de job, chamada manual 2x) sobrescreve a checagem do
    dia em vez de lançar erro de unicidade; nunca apaga checagens de
    outras datas. False sem lançar se a tabela não existir ainda."""
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
        cliente.table(TABELA_ACOMPANHAMENTO).upsert(linhas, on_conflict="ticker,data_referencia").execute()
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


def comparar_carteira_persistida_com_atual(
    data_referencia=None,
    provedor_cotacao=None,
    persistir: bool = True,
    agora=None,
) -> list | None:
    """Compara a recomendação de X dias atrás (snapshot PERSISTIDO em
    carteira_recomendada_itens - peso/preço no momento em que
    salvar_carteira rodou) com o preço ATUAL de cada ticker, calculando
    retorno_pct = (preco_atual - preco_referencia) / preco_referencia *
    100. É o elo que faltava entre salvar_carteira (grava o snapshot de
    hoje) e registrar_acompanhamento (grava 1 checagem já calculada):
    aqui a checagem é CALCULADA a partir do snapshot vigente + cotação
    real, e persistida automaticamente se `persistir=True` (padrão -
    UPSERT por (ticker, data_referencia), seguro reexecutar no mesmo dia).

    None se obter_ultima_carteira_persistida() retornar None (tabela
    ausente OU Supabase indisponível - NUNCA finge sucesso); [] se não há
    snapshot persistido ainda (salvar_carteira nunca rodou - estado normal
    antes da 1a rodada). Cotação que falhar entra na comparação com
    preco_atual/retorno_pct = None (melhor esforço por ticker - nunca
    derruba a comparação dos demais, mesmo padrão de _liquidez)."""
    itens = obter_ultima_carteira_persistida()
    if itens is None:
        return None
    if not itens:
        return []
    if provedor_cotacao is None:
        from data.prices import obter_cotacao
        provedor_cotacao = obter_cotacao
    agora = agora or _agora_utc()
    data_referencia = data_referencia or agora.date()
    data_referencia_iso = data_referencia.isoformat() if hasattr(data_referencia, "isoformat") else data_referencia

    comparacoes = []
    for item in itens:
        ticker = item.get("ticker")
        preco_referencia = _numero(item.get("preco_referencia"))
        preco_atual = None
        try:
            cotacao = provedor_cotacao(ticker) or {}
            preco_atual = _numero(cotacao.get("preco"))
        except Exception as exc:
            print(f"[carteira_recomendada] cotação atual indisponível para {ticker}: {exc!r}")
        retorno_pct = None
        if preco_referencia is not None and preco_referencia > 0 and preco_atual is not None:
            retorno_pct = round(((preco_atual - preco_referencia) / preco_referencia) * 100, 2)
        comparacoes.append({
            "ticker": ticker,
            "peso_pct": item.get("peso_pct"),
            "preco_referencia": preco_referencia,
            "preco_atual": preco_atual,
            "retorno_pct": retorno_pct,
            "data_referencia": data_referencia_iso,
        })

    if persistir:
        ok = registrar_acompanhamento(data_referencia, comparacoes)
        if not ok:
            print("[carteira_recomendada] comparar_carteira_persistida_com_atual: "
                  "registrar_acompanhamento falhou (tabela ainda não existe?) - "
                  "comparação calculada mas não persistida.")
    return comparacoes


# ---------------------------------------------------------------------------
# 5. ACOMPANHAMENTO DE TESES (missão "Radar inteligente e acompanhamento de
#    teses", 2026-11-23) - responde, por ativo, "por que entrou, qual era a
#    tese/preço original, o que o Comitê já reavaliou desde então, como o
#    preço evoluiu e qual é o ESTADO da tese" - 100% derivado do que já está
#    persistido (itens/histórico/acompanhamento); NUNCA chama o Comitê/IA de
#    novo (evita a reanálise cara que a missão pede pra evitar - o único
#    dado buscado "ao vivo" aqui é cotação atual via data/prices.py, já
#    cacheada em 30s, e o histórico do Ibovespa pra benchmark, já cacheado
#    em 5min, ambos reaproveitados do resto do projeto).
#
#    Regra inegociável: o ESTADO nunca é decidido a partir de preço/retorno
#    isolado (ver _classificar_estado) - só a partir do que o PRÓPRIO
#    Comitê já reavaliou e registrou no histórico (sinal_comite/
#    confianca_comite/tese, ver _CAMPOS_MONITORADOS em
#    jobs/carteira_recomendada_job.py). Preço/retorno aparecem só como
#    CONTEXTO complementar no resultado, nunca como insumo da classificação.
# ---------------------------------------------------------------------------

TESE_PRESERVADA = "PRESERVADA"
TESE_FORTALECIDA = "FORTALECIDA"
TESE_ENFRAQUECIDA = "ENFRAQUECIDA"
TESE_EM_REVISAO = "EM_REVISAO"
TESE_INVALIDADA = "INVALIDADA"
TESE_DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"

_SINAIS_NAO_COMPRA = {"VENDA", "NEUTRO"}
_RANKING_CONFIANCA = {"BAIXA": 0, "MEDIA": 1, "ALTA": 2}
_BENCHMARK_SYMBOL = "^BVSP"
_BENCHMARK_NOME = "IBOVESPA"
# Tolerância pra achar o pregão do benchmark mais próximo da data de
# entrada (fins de semana/feriados nunca batem exato) - acima disso, sem
# cotação confiável o bastante pra esse ponto de partida, melhor não
# comparar do que comparar com um pregão distante demais.
_BENCHMARK_TOLERANCIA_DIAS = 5


def _eventos_ordenados_asc(historico: list) -> list:
    """`historico` vem de listar_historico_alteracoes() - mais recente
    primeiro (ver ali). Devolve a MESMA lista em ordem cronológica (mais
    antigo primeiro) - mais natural pra montar uma linha do tempo "o que
    aconteceu desde a entrada" na UI, sem reordenar nada no banco (só um
    sorted() em memória)."""
    return sorted(historico or [], key=lambda h: h.get("registrado_em") or "")


def _evento_entrada(historico: list) -> dict | None:
    """O evento 'entrada_na_carteira' MAIS ANTIGO desse ticker (append-
    only - nunca sobrescrito) - única fonte confiável de "por que entrou
    e com que preço/tese/sinal original", mesmo depois que
    carteira_recomendada_itens (preco_referencia/tese/sinal_comite) já
    tiver sido sobrescrita por rodadas posteriores (upsert por ticker, ver
    salvar_carteira). None se o ticker nunca gerou esse evento (ex: entrou
    antes desta missão de histórico existir, ou histórico indisponível)."""
    entradas = [h for h in (historico or []) if h.get("campo") == "entrada_na_carteira"]
    if not entradas:
        return None
    return min(entradas, key=lambda h: h.get("registrado_em") or "")


def _evento_saida(historico: list) -> dict | None:
    """O evento 'saida_da_carteira' MAIS RECENTE - um ticker pode sair e
    voltar a entrar; interessa a saída mais recente pra avaliar o estado
    de quem está fora hoje."""
    saidas = [h for h in (historico or []) if h.get("campo") == "saida_da_carteira"]
    if not saidas:
        return None
    return max(saidas, key=lambda h: h.get("registrado_em") or "")


def _ultimo_evento_campo(historico: list, campo: str, antes_de: str | None = None) -> dict | None:
    """Evento MAIS RECENTE de `campo` nesse histórico (opcionalmente só
    antes de um timestamp `antes_de`, ISO - usado pra olhar 'qual era o
    sinal bem antes da saída', nunca o estado pós-saída, que nem existe
    pra esse ticker). None se nunca houve esse campo no histórico."""
    candidatos = [
        h for h in (historico or [])
        if h.get("campo") == campo and (antes_de is None or (h.get("registrado_em") or "") <= antes_de)
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda h: h.get("registrado_em") or "")


def _classificar_estado(item_atual: dict | None, historico: list | None) -> dict:
    """Classifica o ESTADO da tese - NUNCA a partir de preço/retorno
    isolado (regra da missão: queda/alta de preço nunca é sinal
    automático de compra/venda nem de tese fortalecida/enfraquecida), só
    a partir do que o próprio Comitê de Investimentos já reavaliou e
    registrou no histórico (sinal_comite/confianca_comite/tese - ver
    _CAMPOS_MONITORADOS em jobs/carteira_recomendada_job.py:
    calcular_revisoes, que grava esses campos quando mudam).

    Vocabulário fechado (ver TESE_*). Ordem de prioridade determinística
    quando há mais de 1 sinal: mudança de SINAL do Comitê > mudança de
    CONFIANÇA > mudança de texto da TESE > nenhuma mudança registrada.
    `historico=None` (Supabase indisponível) -> DADOS_INSUFICIENTES, nunca
    assume um estado sem conseguir checar.

    LIMITAÇÃO REAL CONHECIDA (2026-11-23, documentada - não corrigida
    nesta missão): carteira_recomendada_itens NUNCA teve colunas pra
    sinal_comite/confianca_comite (confirmado contra produção real, ver
    migration proposta e NÃO aplicada no final de sql/
    carteira_recomendada.sql) - sem essas colunas,
    jobs/carteira_recomendada_job.py:calcular_revisoes() NÃO monitora
    mudança contínua de sinal_comite/confianca_comite (removido de
    _CAMPOS_MONITORADOS de propósito - monitorar sem a coluna geraria
    falso positivo em toda rodada, ver comentário lá). Na prática, HOJE
    os ramos de SINAL/CONFIANÇA abaixo são código morto em produção (o
    histórico real nunca contém um evento campo="sinal_comite"/
    "confianca_comite" - só existe no payload JSONB aninhado do evento
    'entrada_na_carteira', que não bate com o filtro de campo usado
    aqui) - a classificação cai direto pra mudança de TESE (texto) ou
    PRESERVADA/DADOS_INSUFICIENTES, nunca finge ter avaliado um sinal
    que não existe. Os testes destes ramos (TestClassificarEstado) são a
    ESPECIFICAÇÃO de como a função deve se comportar assim que a
    migration for autorizada/aplicada e _CAMPOS_MONITORADOS reincluir os
    3 campos - zero mudança necessária aqui quando esse dia chegar."""
    if historico is None:
        return {
            "classificacao": TESE_DADOS_INSUFICIENTES,
            "motivo": "Histórico de revisões indisponível (Supabase fora do ar) - estado da "
                      "tese não pode ser avaliado com segurança agora.",
            "baseado_em": [],
        }

    entrada = _evento_entrada(historico)

    if item_atual is None:
        saida = _evento_saida(historico)
        if saida is None and entrada is None:
            return {
                "classificacao": TESE_DADOS_INSUFICIENTES,
                "motivo": "Ativo não está na carteira atual e não há histórico de entrada/saída "
                          "registrado - sem dado suficiente pra avaliar.",
                "baseado_em": [],
            }
        corte = saida.get("registrado_em") if saida else None
        sinal_antes = _ultimo_evento_campo(historico, "sinal_comite", antes_de=corte)
        if sinal_antes and str(sinal_antes.get("valor_novo") or "").upper() in _SINAIS_NAO_COMPRA:
            return {
                "classificacao": TESE_INVALIDADA,
                "motivo": f"Comitê rebaixou o sinal para {sinal_antes['valor_novo']} antes da saída da carteira.",
                "baseado_em": [e for e in (sinal_antes, saida) if e],
            }
        return {
            "classificacao": TESE_EM_REVISAO,
            "motivo": "Ativo saiu da carteira sem rebaixamento de sinal registrado pelo Comitê "
                      "(provável redistribuição por concentração/seleção, não invalidação de "
                      "tese) - merece revisão manual.",
            "baseado_em": [saida] if saida else [],
        }

    sinal_evt = _ultimo_evento_campo(historico, "sinal_comite")
    if sinal_evt and str(sinal_evt.get("valor_novo") or "").upper() in _SINAIS_NAO_COMPRA:
        return {
            "classificacao": TESE_INVALIDADA,
            "motivo": f"Comitê rebaixou o sinal deste ativo para {sinal_evt['valor_novo']} na revisão mais recente.",
            "baseado_em": [sinal_evt],
        }

    confianca_evt = _ultimo_evento_campo(historico, "confianca_comite")
    if confianca_evt:
        antes = _RANKING_CONFIANCA.get(str(confianca_evt.get("valor_anterior") or "").upper())
        depois = _RANKING_CONFIANCA.get(str(confianca_evt.get("valor_novo") or "").upper())
        if antes is not None and depois is not None and depois < antes:
            return {
                "classificacao": TESE_ENFRAQUECIDA,
                "motivo": f"Confiança do Comitê caiu de {confianca_evt['valor_anterior']} para {confianca_evt['valor_novo']}.",
                "baseado_em": [confianca_evt],
            }
        if antes is not None and depois is not None and depois > antes:
            return {
                "classificacao": TESE_FORTALECIDA,
                "motivo": f"Confiança do Comitê subiu de {confianca_evt['valor_anterior']} para {confianca_evt['valor_novo']}.",
                "baseado_em": [confianca_evt],
            }

    tese_evt = _ultimo_evento_campo(historico, "tese")
    if tese_evt:
        return {
            "classificacao": TESE_EM_REVISAO,
            "motivo": "O resumo da tese do Comitê foi reescrito desde a entrada - revisar o que mudou.",
            "baseado_em": [tese_evt],
        }

    if entrada is None:
        return {
            "classificacao": TESE_DADOS_INSUFICIENTES,
            "motivo": "Ativo presente na carteira, mas sem evento de entrada registrado no "
                      "histórico (provavelmente entrou antes do início deste rastreamento) - "
                      "sem baseline confiável.",
            "baseado_em": [],
        }

    return {
        "classificacao": TESE_PRESERVADA,
        "motivo": "Nenhuma mudança de sinal, confiança ou tese registrada pelo Comitê desde a entrada.",
        "baseado_em": [entrada],
    }


def _preco_e_data_entrada(historico: list | None, acompanhamento: list | None) -> tuple:
    """Preço e data de entrada mais confiáveis disponíveis: prioridade pro
    evento 'entrada_na_carteira' (append-only, nunca sobrescrito - ver
    _evento_entrada) quando ele já carrega preco_referencia (captura
    ampliada em 2026-11-23, ver jobs/carteira_recomendada_job.py); senão
    cai pro PRIMEIRO registro de carteira_recomendada_acompanhamento
    (ordenado por data_referencia) desse ticker, que também captura o
    preço do primeiro dia em que o ativo foi acompanhado. (None, None) se
    nenhuma das duas fontes tiver dado - nunca inventa um valor."""
    entrada = _evento_entrada(historico or [])
    if entrada:
        valor = entrada.get("valor_novo") or {}
        preco = _numero(valor.get("preco_referencia"))
        if preco is not None:
            return preco, entrada.get("registrado_em")
    linhas = list(acompanhamento or [])
    if not linhas:
        return None, None
    primeira = min(linhas, key=lambda a: a.get("data_referencia") or "")
    return _numero(primeira.get("preco_referencia")), primeira.get("data_referencia")


def _retorno_pct(preco_de, preco_para):
    if preco_de is None or preco_para is None or preco_de <= 0:
        return None
    return round(((preco_para - preco_de) / preco_de) * 100, 2)


def _benchmark_desde(data_entrada_iso: str | None, provedor_historico=None) -> dict | None:
    """Retorno do Ibovespa entre a data de entrada e o pregão mais recente
    disponível - mesmo índice já usado no resto do projeto pra ativos de
    B3 (data/prices.py:_BENCHMARK_POR_MERCADO), nunca uma série nova.
    data/prices.py:obter_historico já é cacheado (ttl=300s) - chamar esta
    função várias vezes na mesma renderização (1x por ativo da carteira)
    não dispara 1 requisição de rede por ativo.

    Melhor esforço: None (nunca 0.0 fabricado) se a data de entrada não
    tiver cotação do benchmark dentro da tolerância da janela consultada
    (ex: entrada mais antiga que o histórico disponível) ou o provedor
    falhar - degrade silencioso, mesmo padrão do resto do módulo."""
    if not data_entrada_iso:
        return None
    try:
        data_entrada = date.fromisoformat(str(data_entrada_iso)[:10])
    except ValueError:
        return None
    if provedor_historico is None:
        from data.prices import obter_historico
        provedor_historico = obter_historico
    dias_passados = (_agora_utc().date() - data_entrada).days
    if dias_passados <= 25:
        periodo = "1M"
    elif dias_passados <= 85:
        periodo = "3M"
    elif dias_passados <= 170:
        periodo = "6M"
    else:
        periodo = "1A"
    try:
        df = provedor_historico(_BENCHMARK_SYMBOL, periodo)
    except Exception as exc:
        print(f"[carteira_recomendada] benchmark indisponível: {exc!r}")
        return None
    if df is None or df.empty:
        return None
    try:
        diffs = (df["Data"].dt.date - data_entrada).apply(lambda d: abs(d.days))
        idx_entrada = diffs.idxmin()
        if int(diffs.loc[idx_entrada]) > _BENCHMARK_TOLERANCIA_DIAS:
            return None
        preco_entrada = float(df.loc[idx_entrada, "Close"])
        preco_atual = float(df.iloc[-1]["Close"])
    except Exception as exc:
        print(f"[carteira_recomendada] benchmark malformado: {exc!r}")
        return None
    return {
        "indice": _BENCHMARK_NOME,
        "preco_entrada": round(preco_entrada, 2),
        "preco_atual": round(preco_atual, 2),
        "retorno_pct": _retorno_pct(preco_entrada, preco_atual),
    }


def estado_tese(
    ticker: str,
    provedor_cotacao=None,
    provedor_historico_benchmark=None,
    itens_atuais=None,
) -> dict | None:
    """Visão de acompanhamento de UMA tese da Carteira Recomendada - "por
    que entrou, tese/preço de referência original, riscos, eventos
    posteriores (mudança de sinal/confiança/tese/preço-alvo), evolução de
    preço, desempenho acumulado x Ibovespa e ESTADO da tese" (objetivo da
    missão "Radar inteligente e acompanhamento de teses"). 100% derivado
    de dado JÁ PERSISTIDO (itens/histórico/acompanhamento) - nunca chama
    o Comitê/IA de novo; o único dado "vivo" buscado aqui é cotação atual
    (fallback, já cacheada) e o histórico do Ibovespa pro benchmark
    (idem) - sem reanálise cara nenhuma.

    `itens_atuais` (opcional): a UI que chama isto pra VÁRIOS tickers na
    mesma renderização (ex: 1 chamada por ativo da Carteira Recomendada,
    ver ui/carteira_recomendada_tab.py) deve buscar
    obter_ultima_carteira_persistida() UMA VEZ e passar aqui - sem isso,
    cada chamada buscaria a tabela inteira de novo (até 10 round-trips
    idênticos ao Supabase na mesma renderização, mesmo achado de
    performance já corrigido em data/radar_quedas.py:listar_carteiras).
    None (padrão) busca sozinho, pra quem chama isto pra 1 ticker só.

    None só quando NENHUM dado existir pra esse ticker em nenhuma das 3
    fontes E todas responderam normalmente (nunca esteve na carteira,
    nunca gerou histórico, nunca foi acompanhado) - "este ticker nunca
    passou pela Carteira Recomendada". Indisponibilidade de uma fonte
    (Supabase fora do ar) nunca é confundida com isso - aparece dentro do
    resultado via estado=DADOS_INSUFICIENTES + avisos, nunca como None."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None

    historico = listar_historico_alteracoes(ticker)
    acompanhamento = obter_acompanhamento(ticker)
    if itens_atuais is None:
        itens_atuais = obter_ultima_carteira_persistida()
    item_atual = None
    if itens_atuais is not None:
        item_atual = next((i for i in itens_atuais if i.get("ticker") == ticker), None)

    nunca_rastreado = item_atual is None and historico == [] and acompanhamento == []
    if nunca_rastreado:
        return None

    preco_entrada, data_entrada = _preco_e_data_entrada(historico, acompanhamento)

    preco_atual = _numero((item_atual or {}).get("preco_referencia"))
    if preco_atual is None and acompanhamento:
        mais_recente = max(acompanhamento, key=lambda a: a.get("data_referencia") or "")
        preco_atual = _numero(mais_recente.get("preco_atual"))
    if preco_atual is None:
        try:
            if provedor_cotacao is None:
                from data.prices import obter_cotacao
                provedor_cotacao = obter_cotacao
            cotacao = provedor_cotacao(ticker) or {}
            preco_atual = _numero(cotacao.get("preco"))
        except Exception as exc:
            print(f"[carteira_recomendada] cotação atual indisponível para estado_tese({ticker}): {exc!r}")

    estado = _classificar_estado(item_atual, historico)
    entrada_evt = _evento_entrada(historico or [])
    retorno_acumulado_pct = _retorno_pct(preco_entrada, preco_atual)
    benchmark = _benchmark_desde(data_entrada, provedor_historico_benchmark)
    retorno_relativo_pct = None
    if retorno_acumulado_pct is not None and benchmark is not None and benchmark.get("retorno_pct") is not None:
        retorno_relativo_pct = round(retorno_acumulado_pct - benchmark["retorno_pct"], 2)

    avisos = []
    if historico is None:
        avisos.append("Histórico de revisões indisponível (Supabase fora do ar) - eventos podem estar incompletos.")
    if acompanhamento is None:
        avisos.append("Acompanhamento diário indisponível (Supabase fora do ar).")
    elif not acompanhamento:
        avisos.append("Nenhum acompanhamento diário persistido ainda pra este ativo.")
    if preco_entrada is None:
        avisos.append("Preço de entrada não pôde ser recuperado - retorno acumulado indisponível.")
    if preco_entrada is not None and benchmark is None:
        avisos.append("Benchmark (Ibovespa) indisponível para o período desde a entrada.")

    return {
        "ticker": ticker,
        "em_carteira": item_atual is not None,
        "motivo_entrada": (item_atual or {}).get("justificativa") or (entrada_evt or {}).get("motivo"),
        "data_entrada": data_entrada,
        "preco_entrada": preco_entrada,
        "tese_original": ((entrada_evt or {}).get("valor_novo") or {}).get("tese"),
        "tese_atual": (item_atual or {}).get("tese"),
        "preco_alvo_atual": (item_atual or {}).get("preco_alvo"),
        "riscos_atuais": (item_atual or {}).get("riscos") or [],
        "criterio_saida_atual": (item_atual or {}).get("criterio_saida"),
        # sinal/confiança/score "_na_entrada": capturados 1x no evento
        # JSONB de entrada (sem depender de coluna nova - ver docstring
        # acima). "_atual": lido de item_atual (carteira_recomendada_itens)
        # - SEMPRE None hoje, pois essa tabela nunca teve essas 3 colunas
        # (achado real 2026-11-23, migration proposta e NÃO aplicada em
        # sql/carteira_recomendada.sql); mantido no shape pra já existir
        # e virar automaticamente real assim que a migration + salvar_
        # carteira() forem atualizados - nunca um erro, só um campo vazio
        # até lá.
        "sinal_na_entrada": ((entrada_evt or {}).get("valor_novo") or {}).get("sinal_comite"),
        "confianca_na_entrada": ((entrada_evt or {}).get("valor_novo") or {}).get("confianca_comite"),
        "score_na_entrada": ((entrada_evt or {}).get("valor_novo") or {}).get("score_comite"),
        "sinal_atual": (item_atual or {}).get("sinal_comite"),
        "confianca_atual": (item_atual or {}).get("confianca_comite"),
        "score_atual": (item_atual or {}).get("score_comite"),
        "eventos": _eventos_ordenados_asc(historico or []),
        "preco_atual": preco_atual,
        "retorno_acumulado_pct": retorno_acumulado_pct,
        "benchmark": benchmark,
        "retorno_relativo_pct": retorno_relativo_pct,
        "estado": estado,
        "avisos": avisos,
    }
