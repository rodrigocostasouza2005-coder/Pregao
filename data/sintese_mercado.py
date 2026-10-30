# -*- coding: utf-8 -*-
"""ANALISTA DE MERCADO (síntese executiva) - camada de interpretação
sobre dados JÁ coletados/persistidos pelo Pregão. NÃO é um coletor novo:
toda chamada em _coletar_fatos() reaproveita funções existentes
(data/prices.py, data/mercado.py, data/macro.py, data/news.py,
data/eventos.py, data/market_researcher.py) - zero requisição de rede
nova além do que essas funções já fazem (e já cacheiam via
st.cache_data). A IA (Groq, mesma credencial/modelo de
data/research/resumir.py e data/news.py) só INTERPRETA o que já foi
coletado - nunca recebe instrução pra inventar fato, preço, notícia ou
evento que não esteja no payload.

Fluxo: coleta fatos com fonte+horário -> 1 única chamada ao Groq pedindo
JSON estrito -> valida campos -> cacheia por bucket de tempo
(data/ia_cache.py, mesmo padrão de research/news - nunca TTL explícito,
a chave muda de bucket em bucket) -> se a geração falhar (IA
indisponível, resposta malformada), cai pra última síntese válida
persistida (data/ia_cache.py:obter_mais_recente_concluido), sinalizada
como ANTERIOR por quem consome (nunca apresentada como desta rodada).

Regras inegociáveis (mesmas de data/research/resumir.py - ver
_PROMPT_SISTEMA abaixo):
- nunca inventa causalidade, preço-alvo, recomendação de operação ou
  número que não veio dos fatos coletados;
- correlação não é causa - só conecta dois fatos quando o próprio
  conjunto de fatos sustenta a conexão, e sinaliza quando é uma leitura
  (não um fato relatado pela fonte);
- cada achado cita a fonte e o horário do dado que embasa ele;
- sem dado suficiente numa seção, a seção fica vazia - nunca preenchida
  com algo genérico só pra não parecer vazia;
- confiança é SEMPRE qualitativa (alta/média/baixa) com justificativa -
  nunca um número de probabilidade inventado.

--- Metodologia (2026-10-26): adaptação do skill "market-researcher" -----

Estrutura inspirada nos agentes oficiais `market-researcher` e
`competitive-analysis` do pacote "Claude for Financial Services"
(anthropics/financial-services, licença Apache-2.0 - ver atribuição
completa no corpo da PR). Esses agentes rodam via Claude Code/Managed
Agents com MCP pago (CapIQ/FactSet) - nada disso foi importado como
código ou dependência; só a DISCIPLINA ANALÍTICA foi portada pro
pipeline Groq que o Pregão já tinha (ver docs/market-researcher-
integracao.md pra auditoria completa de que mais já foi adaptado de lá
em sessões anteriores - comps/thesis-tracker/earnings-reviewer já
existem em módulos próprios, não repetidos aqui).

Dessa adaptação vieram os dois campos novos abaixo (`cenarios` e
`observar_proximas_sessoes`), que fecham a lacuna real entre o que a
síntese já fazia (resumo + movimentos + oportunidades/riscos + o que
não sabemos) e os dois pontos do skill oficial que ainda faltavam:
cenário alternativo (adaptado de "bull/base/bear", mas SEM
probabilidade numérica - o skill oficial usa %, aqui isso seria uma
probabilidade inventada, proibida) e uma lista curta do que observar
nas próximas sessões (equivalente aos "catalysts"/"signposts" do skill
oficial, mas só com catalisadores que já apareceram nos fatos
coletados - nunca um evento novo inventado pela IA)."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import requests

import config
from data import eventos, ia_cache, macro, market_researcher, mercado, news, prices

_URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
_MAX_TOKENS = 3000
_TIMEOUT_S = 45
# 20min: mesma ordem de grandeza do cache de NEWS (ver mencao a "cache de
# 20 minutos" no pedido) - muda bucket, muda chave, sem TTL explicito na
# tabela (mesmo padrao de data/ia_cache.py:chave_news).
_BUCKET_MINUTOS = 20
_VERSAO_CHAVE = "v1"
_ORIGEM = "sintese_mercado"
_QTD_NOTICIAS = 10
_QTD_ALTAS_BAIXAS = 5
_QTD_EVENTOS = 8

_PROMPT_SISTEMA = (
    "Você é um analista de mercado sênior preparando a síntese executiva matinal do "
    "terminal Pregão para um investidor brasileiro. Você recebe um payload JSON com "
    "FATOS já coletados (cotações, variações, notícias com fonte e data, indicadores "
    "macro, eventos de calendário, e uma lista de fontes com problema de atualização) - "
    "nunca dados que você mesmo buscou ou lembra de outro contexto.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- Use SOMENTE os fatos do payload. Nunca invente preço, variação, notícia, data, "
    "evento, recomendação, preço-alvo ou declaração que não esteja literalmente ali.\n"
    "- Correlação não é causa: só afirme que um evento EXPLICA um movimento quando o "
    "payload sustenta essa relação (ex: notícia e variação do mesmo ativo/setor no "
    "mesmo dia). Quando você mesmo está conectando pontos que o payload não conecta "
    "explicitamente, isso é uma LEITURA sua - escreva 'o que sugere...'/'isso pode "
    "indicar...', nunca como se fosse um fato relatado pela fonte.\n"
    "- 'confianca' é SEMPRE qualitativa ('alta', 'média' ou 'baixa') com uma frase "
    "curta explicando o porquê (convergência de fontes, qualidade do dado, etc). NUNCA "
    "um número/percentual de probabilidade - isso seria inventado.\n"
    "- Nunca recomende comprar/vender nem defina preço-alvo. 'Merece investigar' é "
    "diferente de 'recomendação de compra' - trate sempre como o primeiro.\n"
    "- Se não houver fatos suficientes para uma seção, devolva a lista/texto vazio "
    "para ela - nunca preencha com algo genérico.\n"
    "- Todo item de 'movimentos' e 'oportunidades_riscos' precisa citar 'fonte' (nome "
    "da fonte do payload) e, quando o fato tiver, a data/horário do dado.\n"
    "- 'cenarios': no máximo 3 leituras do que pode acontecer a partir de agora, cada "
    "uma com 'tipo' EXATAMENTE 'principal' (a leitura mais consistente com os fatos "
    "coletados agora - só 1 'principal') ou 'alternativo' (até 2, cenários que os "
    "mesmos fatos também sustentam, mas com menos peso). NUNCA inclua probabilidade "
    "numérica/percentual - isso seria inventado. Cada cenário tem 'condicao' (o que "
    "precisaria se confirmar pra esse cenário prevalecer) e 'sinalizadores' (o que, "
    "nos PRÓPRIOS fatos coletados ou no que normalmente se observaria, indicaria esse "
    "cenário se fortalecendo). Sem fatos suficientes pra sustentar nem 1 cenário, "
    "devolva lista vazia.\n"
    "- 'observar_proximas_sessoes': no máximo 6 itens curtos do que acompanhar nas "
    "próximas sessões - priorize o que já está na agenda/calendário do payload ou nos "
    "próprios 'movimentos'/'oportunidades_riscos' que você já identificou. NUNCA cite "
    "um evento/data que não esteja no payload.\n"
    "- Responda APENAS com um objeto JSON válido, sem markdown, sem texto antes ou "
    "depois, no formato exato:\n"
    "{\n"
    '  "resumo_executivo": {"texto": "string, 4-8 frases, estado observado do mercado, '
    'fatores aparentes, principais riscos", "ressalvas": "string curta ou vazia sobre '
    'dados indisponíveis/desatualizados relevantes pra esta leitura"},\n'
    '  "movimentos": [{"evento": "string", "fonte": "string", "data_fonte": "string ou '
    'null", "por_que_importa": "string", "impacto_possivel": "string", "horizonte": '
    '"string curta ou vazia", "confianca": "alta|media|baixa", "confianca_motivo": '
    '"string"}],\n'
    '  "oportunidades_riscos": [{"ativo_ou_setor": "string", "catalisador": "string", '
    '"argumento_favoravel": "string", "argumento_contrario": "string", '
    '"acompanhar": "string", "fonte": "string", "data_fonte": "string ou null"}],\n'
    '  "cenarios": [{"tipo": "principal|alternativo", "cenario": "string", "condicao": '
    '"string", "sinalizadores": "string"}],\n'
    '  "observar_proximas_sessoes": [{"item": "string", "motivo": "string", "fonte": '
    '"string ou null", "data_fonte": "string ou null"}],\n'
    '  "o_que_nao_sabemos": ["string"]\n'
    "}\n"
    "Máximo 6 itens em 'movimentos', 5 em 'oportunidades_riscos', 3 em 'cenarios', 6 em "
    "'observar_proximas_sessoes', 6 em 'o_que_nao_sabemos'. Escreva em português do "
    "Brasil, tom de terminal profissional, sem exagero ('despencou', 'disparou', "
    "'colapsou' só se o fato for realmente desse tamanho)."
)


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except AttributeError:
        return str(dt)


def _snapshot_indice(nome: str, simbolo_indice: str | None, ticker: str | None) -> dict:
    """1 linha do painel MERCADO AGORA (mesmas funções de
    ui/visao_geral.py:_painel_mercado_agora) - preço/variação reais ou
    None (nunca inventado) quando a fonte falhar."""
    try:
        if simbolo_indice:
            cot = prices.obter_cotacao_indice(nome, simbolo_indice)
        else:
            cot = prices.obter_cotacao(ticker)
        if cot.get("erro"):
            return {"nome": nome, "preco": None, "variacao_pct": None, "erro": cot["erro"]}
        return {
            "nome": nome, "preco": cot.get("preco"), "variacao_pct": cot.get("variacao_pct"),
            "em_cache": bool(prices.rotulo_cotacao_em_cache(cot)),
        }
    except Exception as exc:
        return {"nome": nome, "preco": None, "variacao_pct": None, "erro": repr(exc)}


def _coletar_fatos() -> dict:
    """Agrega fatos de todas as fontes já existentes - cada bloco é
    independente (try/except próprio): a falha de UMA fonte nunca
    derruba as demais, só entra na lista 'fontes_indisponiveis' pra a
    IA (e o usuário) saberem que aquele pedaço do cenário está ausente,
    nunca silenciosamente ignorado."""
    agora = datetime.now(timezone.utc)
    fatos: dict = {"gerado_em": _iso(agora), "fontes_indisponiveis": []}

    try:
        fatos["mercado_agora"] = [
            _snapshot_indice("IBOVESPA", config.SIMBOLO_IBOVESPA, None),
            _snapshot_indice("DÓLAR", "USDBRL=X", None),
            _snapshot_indice("PETR4", None, "PETR4"),
            _snapshot_indice("VALE3", None, "VALE3"),
        ]
    except Exception as exc:
        fatos["mercado_agora"] = []
        fatos["fontes_indisponiveis"].append(f"cotações principais: {exc!r}")

    try:
        cdi_df = macro.obter_cdi(dias_historico=5)
        fatos["cdi_anualizado_pct"] = (
            float(cdi_df["cdi_anualizado_pct"].iloc[-1]) if cdi_df is not None and not cdi_df.empty else None
        )
    except Exception as exc:
        fatos["cdi_anualizado_pct"] = None
        fatos["fontes_indisponiveis"].append(f"MACRO (BCB - CDI): {exc!r}")

    try:
        globais = mercado.obter_mercados_globais()
        fatos["mercados_globais"] = [
            {"nome": g.get("nome"), "preco": g.get("preco"), "variacao_pct": g.get("variacao_pct")}
            for g in (globais or [])
        ]
    except Exception as exc:
        fatos["mercados_globais"] = []
        fatos["fontes_indisponiveis"].append(f"mercados globais: {exc!r}")

    try:
        altas, baixas = mercado.obter_altas_baixas(n=_QTD_ALTAS_BAIXAS)
        fatos["maiores_altas"] = [{"ticker": p["ticker"], "variacao_pct": p["variacao_pct"]} for p in altas]
        fatos["maiores_baixas"] = [{"ticker": p["ticker"], "variacao_pct": p["variacao_pct"]} for p in baixas]
    except Exception as exc:
        fatos["maiores_altas"], fatos["maiores_baixas"] = [], []
        fatos["fontes_indisponiveis"].append(f"maiores altas/baixas: {exc!r}")

    try:
        setorial = mercado.obter_desempenho_setorial()
        fatos["desempenho_setorial"] = [
            {"setor": s["setor"], "variacao_media_pct": round(s["variacao_media_pct"], 2)}
            for s in (setorial or [])[:6]
        ]
    except Exception as exc:
        fatos["desempenho_setorial"] = []
        fatos["fontes_indisponiveis"].append(f"desempenho setorial: {exc!r}")

    try:
        fatos["cenario_global"] = macro.obter_cenario_global() or []
    except Exception as exc:
        fatos["cenario_global"] = []
        fatos["fontes_indisponiveis"].append(f"MACRO (Cenário Global): {exc!r}")

    try:
        focus_ipca = macro.obter_focus_ipca()
        focus_selic = macro.obter_focus_selic()
        fatos["focus"] = {
            "ipca_ultima_linha": (focus_ipca.tail(1).to_dict("records")[0] if focus_ipca is not None and not focus_ipca.empty else None),
            "selic_ultima_linha": (focus_selic.tail(1).to_dict("records")[0] if focus_selic is not None and not focus_selic.empty else None),
        }
    except Exception as exc:
        fatos["focus"] = {"ipca_ultima_linha": None, "selic_ultima_linha": None}
        fatos["fontes_indisponiveis"].append(f"MACRO (Focus): {exc!r}")

    try:
        itens_news = news.obter_top_mercado_tudo("TODOS") or []
        fatos["noticias"] = [
            {
                "titulo": n.get("titulo"), "fonte": n.get("veiculo") or n.get("fonte"),
                "link": n.get("link"), "data": _iso(n.get("data")),
            }
            for n in itens_news[:_QTD_NOTICIAS]
        ]
    except Exception as exc:
        fatos["noticias"] = []
        fatos["fontes_indisponiveis"].append(f"notícias: {exc!r}")

    try:
        snapshot = eventos.obter_snapshot_calendario() or {}
        hoje = datetime.now(timezone.utc).date()
        limite = hoje + timedelta(days=21)
        proximos = []
        for ev in (snapshot.get("eventos") or []):
            try:
                data_ev = datetime.fromisoformat(str(ev.get("data"))[:10]).date()
            except (ValueError, TypeError):
                continue
            if hoje <= data_ev <= limite:
                proximos.append({
                    "ticker": ev.get("ticker"), "empresa": ev.get("empresa"),
                    "data": str(data_ev), "status": ev.get("status"), "fonte": ev.get("fonte"),
                })
        proximos.sort(key=lambda e: e["data"])
        fatos["agenda"] = proximos[:_QTD_EVENTOS]
        fatos["agenda_atualizada_em"] = snapshot.get("atualizado_em")
    except Exception as exc:
        fatos["agenda"] = []
        fatos["agenda_atualizada_em"] = None
        fatos["fontes_indisponiveis"].append(f"calendário: {exc!r}")

    try:
        achados = market_researcher.achados_qualidade_coletores() or []
        fatos["qualidade_dados"] = [
            {"coletor": a["coletor"], "estado": a["rotulo_estado"], "critico": a["critico"]}
            for a in achados[:10]
        ]
    except Exception as exc:
        fatos["qualidade_dados"] = []
        fatos["fontes_indisponiveis"].append(f"painel de saúde dos dados: {exc!r}")

    return fatos


def _chamar_groq(chave: str, modelo: str, mensagens: list, max_tokens: int) -> tuple:
    """POST generico pro endpoint de chat completions da Groq - mesmo
    padrao de data/research/resumir.py:_chamar_groq (copia local de
    proposito: o projeto ja tem 3 copias independentes dessa mesma
    chamada, uma por modulo - data/news.py, data/cvm.py,
    data/research/resumir.py -, nenhuma importada entre si; uma 4a copia
    aqui segue a convenção já estabelecida em vez de criar um acoplamento
    novo entre módulos de dados que hoje não se conhecem)."""
    try:
        r = requests.post(
            _URL_GROQ,
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": mensagens,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT_S,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except Exception as e:
        return None, str(e)


def _chamar_groq_com_fallback(chave: str, modelo_principal: str, modelo_fallback: str, mensagens: list, max_tokens: int) -> tuple:
    """Mesma resiliencia de data/research/resumir.py:_chamar_groq_com_fallback
    (tenta principal, 1 unica tentativa de fallback se falhar - nunca
    martela indefinidamente). Retorna (conteudo, motivo_seguro, modelo_usado)."""
    conteudo, motivo = _chamar_groq(chave, modelo_principal, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_principal
    print(f"[sintese_mercado] modelo principal ({modelo_principal}) falhou: {motivo}")
    conteudo, motivo = _chamar_groq(chave, modelo_fallback, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_fallback
    print(f"[sintese_mercado] modelo fallback ({modelo_fallback}) falhou: {motivo}")
    return None, ("cota" if motivo == "cota" else "indisponivel"), modelo_fallback


def _extrair_json(conteudo: str) -> dict | None:
    """Parse defensivo: o modelo pode envolver o JSON em ```json ... ```
    mesmo com response_format=json_object pedido (achado conhecido de
    modelos OSS via Groq) - tenta direto, depois tenta extrair o maior
    trecho entre a 1a '{' e a ultima '}'. None (nunca levanta excecao)
    se nenhuma das duas formas resultar em JSON valido."""
    if not conteudo:
        return None
    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        pass
    inicio, fim = conteudo.find("{"), conteudo.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        return None
    try:
        return json.loads(conteudo[inicio:fim + 1])
    except json.JSONDecodeError:
        return None


_CONFIANCAS_VALIDAS = {"alta", "media", "média", "baixa"}
_TIPOS_CENARIO_VALIDOS = {"principal", "alternativo"}

# Whitelist explícita de campos por item (em vez de **item) - garante que
# nenhum campo fora do schema pedido (ex: 'recomendacao', 'preco_alvo', se
# o modelo algum dia tentar injetar isso) sobrevive à validação, mesma
# regra já aplicada a recomendacao/preco_alvo em RESEARCH > Casas de
# Análise (só existem depois de um resumo por IA - aqui nem existem,
# nunca são um campo esperado neste painel).
_CAMPOS_MOVIMENTO = (
    "evento", "fonte", "data_fonte", "por_que_importa", "impacto_possivel",
    "horizonte", "confianca", "confianca_motivo",
)
_CAMPOS_OPORTUNIDADE = (
    "ativo_ou_setor", "catalisador", "argumento_favoravel", "argumento_contrario",
    "acompanhar", "fonte", "data_fonte",
)
_CAMPOS_CENARIO = ("tipo", "cenario", "condicao", "sinalizadores")
_CAMPOS_OBSERVAR = ("item", "motivo", "fonte", "data_fonte")


def _filtrar_campos(item: dict, campos: tuple) -> dict:
    return {campo: item.get(campo) for campo in campos}


def _validar_e_limpar(dados: dict) -> dict | None:
    """Validação de campo (pedida explicitamente na missão) - nunca
    confia ciegamente na saída do modelo. Remove item malformado em vez
    de invalidar a síntese inteira (um item ruim não derruba os bons),
    mas EXIGE resumo_executivo.texto não vazio - sem isso não há síntese
    utilizável, mesmo que os demais blocos existam. Todo item é
    reconstruído por whitelist de campo (_filtrar_campos) - nunca um
    `**item` que deixaria passar uma chave extra que o modelo tenha
    inventado (ex: 'recomendacao', 'preco_alvo')."""
    if not isinstance(dados, dict):
        return None
    resumo = dados.get("resumo_executivo")
    texto = (resumo or {}).get("texto") if isinstance(resumo, dict) else None
    if not isinstance(texto, str) or not texto.strip():
        return None

    movimentos = []
    for item in (dados.get("movimentos") or []):
        if not isinstance(item, dict) or not item.get("evento") or not item.get("fonte"):
            continue
        confianca = str(item.get("confianca") or "").strip().lower()
        limpo = _filtrar_campos(item, _CAMPOS_MOVIMENTO)
        if confianca not in _CONFIANCAS_VALIDAS:
            confianca = "baixa"
            limpo["confianca_motivo"] = (limpo.get("confianca_motivo") or "") + \
                " (confiança não informada pela análise; marcada como baixa por padrão)"
        limpo["confianca"] = confianca
        movimentos.append(limpo)

    oportunidades = [
        _filtrar_campos(item, _CAMPOS_OPORTUNIDADE)
        for item in (dados.get("oportunidades_riscos") or [])
        if isinstance(item, dict) and item.get("ativo_ou_setor") and item.get("fonte")
    ]

    cenarios = []
    tem_principal = False
    for item in (dados.get("cenarios") or []):
        if not isinstance(item, dict) or not str(item.get("cenario") or "").strip():
            continue
        tipo = str(item.get("tipo") or "").strip().lower()
        if tipo == "principal" and not tem_principal:
            tem_principal = True
        else:
            tipo = "alternativo"  # nunca mais de 1 "principal" - demais ficam "alternativo"
        limpo = _filtrar_campos(item, _CAMPOS_CENARIO)
        limpo["tipo"] = tipo
        cenarios.append(limpo)
    # corte pro limite de 3 PRESERVA o "principal" (se existir) em vez de um
    # corte bruto por posição - se a IA (por erro) mandar mais de 3 cenários
    # e o "principal" não estiver entre os 3 primeiros da lista, um
    # cenarios[:3] ingênuo descartaria justamente a leitura mais
    # consistente com os fatos, deixando só alternativos na UI.
    principal = next((c for c in cenarios if c["tipo"] == "principal"), None)
    alternativos = [c for c in cenarios if c["tipo"] != "principal"]
    if principal:
        cenarios = [principal] + alternativos[:2]
    else:
        cenarios = alternativos[:3]

    observar = [
        _filtrar_campos(item, _CAMPOS_OBSERVAR)
        for item in (dados.get("observar_proximas_sessoes") or [])
        if isinstance(item, dict) and str(item.get("item") or "").strip()
    ]
    nao_sabemos = [s for s in (dados.get("o_que_nao_sabemos") or []) if isinstance(s, str) and s.strip()]

    return {
        "resumo_executivo": {"texto": texto.strip(), "ressalvas": (resumo.get("ressalvas") or "").strip()},
        "movimentos": movimentos[:6],
        "oportunidades_riscos": oportunidades[:5],
        "cenarios": cenarios[:3],
        "observar_proximas_sessoes": observar[:6],
        "o_que_nao_sabemos": nao_sabemos[:6],
    }


def _gerar_sintese() -> dict:
    """gerar_fn chamado por data/ia_cache.py:obter_resumo_com_cache -
    SEM argumentos (closure), por contrato daquele módulo. Retorna dict
    com 'resumo' truthy SÓ quando a geração funcionou de ponta a ponta -
    é esse campo que decide se o cache persiste o resultado."""
    fatos = _coletar_fatos()
    chave_api, modelo = config.obter_credenciais_groq()
    if not chave_api:
        return {"resumo": None, "motivo": "GROQ_API_KEY não configurada", "fatos": fatos}

    mensagens = [
        {"role": "system", "content": _PROMPT_SISTEMA},
        {"role": "user", "content": json.dumps(fatos, ensure_ascii=False, default=str)},
    ]
    conteudo, motivo, modelo_usado = _chamar_groq_com_fallback(
        chave_api, modelo, config.obter_modelo_groq_fallback(), mensagens, _MAX_TOKENS,
    )
    if conteudo is None:
        return {"resumo": None, "motivo": motivo, "fatos": fatos}

    dados = _validar_e_limpar(_extrair_json(conteudo) or {})
    if dados is None:
        print("[sintese_mercado] resposta da IA não passou da validação de estrutura")
        return {"resumo": None, "motivo": "resposta da IA em formato inesperado", "fatos": fatos}

    return {
        "resumo": dados["resumo_executivo"]["texto"],
        "modelo": modelo_usado,
        "dados": dados,
        "fontes_indisponiveis": fatos.get("fontes_indisponiveis") or [],
        "fatos_gerado_em": fatos.get("gerado_em"),
    }


def _bucket_atual() -> str:
    agora = datetime.now(timezone.utc)
    bucket = (agora.hour * 60 + agora.minute) // _BUCKET_MINUTOS
    return f"{agora.date().isoformat()}T{bucket:03d}"


def _chave_sintese(bucket: str) -> str:
    return hashlib.sha256(f"{_VERSAO_CHAVE}|{_ORIGEM}|{bucket}".encode("utf-8")).hexdigest()


def obter_sintese_mercado() -> dict:
    """Ponto de entrada único da UI (ui/visao_geral.py). Sempre retorna
    um dict com 'ok' (bool) - nunca lança excecao, nunca bloqueia a
    VISÃO GERAL mesmo com Groq/Supabase fora do ar:
    - ok=True, atual=True: síntese gerada ou cacheada DESTA rodada.
    - ok=True, atual=False: Groq falhou agora, mas havia uma síntese
      anterior válida - 'gerado_em' é o horário dela (dessa rodada
      ANTERIOR), nunca maquiado como se fosse de agora.
    - ok=False: nunca houve síntese válida (Groq nunca configurado/
      disponível ainda) - quem chama mostra indisponibilidade, nunca
      inventa um resumo."""
    chave = _chave_sintese(_bucket_atual())
    try:
        resultado = ia_cache.obter_resumo_com_cache(chave, _ORIGEM, _ORIGEM, _gerar_sintese)
    except Exception as exc:
        print(f"[sintese_mercado] obter_resumo_com_cache falhou: {exc!r}")
        resultado = _gerar_sintese()

    if resultado.get("resumo") and resultado.get("dados"):
        return {
            "ok": True, "atual": True, "gerado_em": resultado.get("fatos_gerado_em"),
            "modelo": resultado.get("modelo"), "dados": resultado["dados"],
            "fontes_indisponiveis": resultado.get("fontes_indisponiveis") or [],
        }

    anterior = ia_cache.obter_mais_recente_concluido(_ORIGEM)
    dados_anteriores = (anterior or {}).get("resultado") or {}
    if dados_anteriores.get("dados"):
        return {
            "ok": True, "atual": False, "gerado_em": dados_anteriores.get("fatos_gerado_em") or anterior.get("criado_em"),
            "modelo": dados_anteriores.get("modelo"), "dados": dados_anteriores["dados"],
            "fontes_indisponiveis": dados_anteriores.get("fontes_indisponiveis") or [],
            "motivo_atual_indisponivel": resultado.get("motivo"),
        }

    return {"ok": False, "motivo": resultado.get("motivo") or "síntese indisponível"}
