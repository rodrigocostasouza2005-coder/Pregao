# -*- coding: utf-8 -*-
"""MARKET RESEARCHER: camada de avaliacao de qualidade e comparacao
entre fontes - NAO e' uma pagina nova, NAO e' um coletor novo. E' uma
fachada sobre o que ja existe:

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
  data/market_makers.py): cada bloco degrada sozinho.

ARQUITETURA HIBRIDA (missao "PREGAO 2.1 — IA real hibrida", 2026-11-13):
sintese_qualitativa_research() ao final deste modulo e' a UNICA funcao
daqui que chama IA de verdade (Groq, mesma credencial/modelo ja usados em
data/news.py e data/sintese_mercado.py) - nunca pra recalcular
recomendacao/preco-alvo/divergencia (isso continua 100% deterministico,
ja' calculado por data/research/comparador.py), so' pra LER o research ja'
coletado (research_itens/research_premissas, via comparar_ticker) e
sintetizar em prosa o que as casas estao dizendo em conjunto -
convergencia/divergencia nas PREMISSAS/RISCOS qualitativos, nao so' na
recomendacao numerica (essa checagem ja existe, deterministica, em
_divergencia_recomendacao do comparador). Opt-in explicito (nunca
acionada pelos agregadores puramente deterministicos acima) - quem
decide gastar a chamada e' o Coordenador Central (ver
data/coordenador_central/fluxos.py, parametro sintese_ia)."""
import hashlib
import json
import time
from datetime import datetime, timezone

import requests

import config
from data import ia_cache, ia_hibrida_telemetria, saude_dados
from data.earnings import reviewer as earnings_reviewer
from data.market_makers import contexto_ticker
from data.radar import comparaveis_setor, linha_valuation
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


def consenso_research(cobertura: dict | None) -> dict:
    """A partir do dict de cobertura_cruzada_casas, monta o resumo direto
    pra seção "Consenso de Research" da Conclusão de Investimento:
    quantas casas cobrem vs. não cobrem, lista por casa (recomendação/
    preço-alvo/data/link) e divergência (se houver) - nenhum cálculo
    novo, só reorganiza o que cobertura_cruzada_casas já devolve.
    `disponivel`=False quando o banco de research está fora do ar
    (distinto de "disponivel=True, n_casas_cobrindo=0" = banco respondeu
    e nenhuma casa monitorada publicou). Ausência de cobertura NUNCA é
    tratada como sinal positivo/negativo aqui - só contagem/fato."""
    if cobertura is None or cobertura.get("cobertura") is None:
        return {"disponivel": False, "motivo": "banco de research indisponível nesta checagem."}
    itens = cobertura.get("cobertura") or []
    sem_cobertura = cobertura.get("sem_cobertura") or []
    return {
        "disponivel": True,
        "n_casas_cobrindo": len(itens),
        "n_casas_sem_cobertura": len(sem_cobertura),
        "casas_sem_cobertura": sem_cobertura,
        "itens": itens,
        "divergencia": cobertura.get("divergencia"),
    }


def _pais_code(ticker: str) -> str:
    try:
        return "BR" if config.info_ativo(ticker).get("pais") == "Brasil" else "US"
    except Exception:
        return "BR"


def historico_fundamentos(ticker: str) -> dict:
    """Série histórica trimestral real (Earnings Reviewer) pra 1
    ticker - só Brasil nesta versão (ver serie_historica_br). Isolado
    por try/except (mesmo padrão dos demais blocos deste módulo): uma
    falha aqui nunca derruba o restante de analise_ticker."""
    if _pais_code(ticker) != "BR":
        return {
            "disponivel": False,
            "motivo": "série histórica trimestral só cobre empresas brasileiras nesta versão "
                      "(CVM) - calendário fiscal de empresa internacional não é detectado "
                      "automaticamente (ver limitações do Earnings Reviewer).",
        }
    return earnings_reviewer.serie_historica_br(ticker)


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
    data/market_makers.py), cobertura de research entre casas
    (cobertura_cruzada_casas, acima), histórico trimestral de
    fundamentos (historico_fundamentos, 2026-10-30) e comparativo
    setorial de múltiplos (data/radar.py:comparaveis_setor, 2026-10-30 -
    antes só usado num diálogo isolado em Fundamentos). Cada bloco é
    None quando a fonte dele falha - nunca interrompe os demais nem
    inventa valor. `fontes_indisponiveis` lista, por nome, quais blocos
    falharam nesta chamada (lista vazia = todos os blocos responderam,
    não necessariamente com dado - um bloco pode responder com tudo
    None/[] legitimamente)."""
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

    try:
        historico = historico_fundamentos(ticker)
    except Exception as exc:
        print(f"[market_researcher] histórico de fundamentos indisponível pra {ticker}: {exc!r}")
        historico = None
        fontes_indisponiveis.append("historico_fundamentos")

    try:
        setorial = comparaveis_setor(ticker)
    except Exception as exc:
        print(f"[market_researcher] comparativo setorial indisponível pra {ticker}: {exc!r}")
        setorial = None
        fontes_indisponiveis.append("comparativo_setorial")

    return {
        "ticker": ticker,
        "gerado_em": datetime.now(timezone.utc),
        "fundamentos": fundamentos,
        "catalisadores": (contexto or {}).get("catalisadores"),
        "mudancas_tese": (contexto or {}).get("mudancas"),
        "riscos_indicadores": (contexto or {}).get("riscos"),
        "interpretacao_movimento": (contexto or {}).get("interpretacao"),
        "cobertura_research": cobertura,
        "fundamentos_historicos": historico,
        "comparativo_setorial": setorial,
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
                cliente.table(_TABELA_ACHADOS).select("id,ocorrencias,status")
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


# ============================================================
# SINTESE QUALITATIVA DO RESEARCH (IA real, missao "PREGAO 2.1",
# 2026-11-13) - ver docstring do modulo pro principio geral.
#
# O QUE A IA FAZ: le as premissas/riscos/projecoes/recomendacao JA
# extraidos por casa (data/research/comparador.py:comparar_ticker, que
# por sua vez le research_premissas - biblioteca PERMANENTE) e escreve,
# em portugues corrido, o que as casas monitoradas estao dizendo em
# CONJUNTO sobre a empresa - convergencias e divergencias nas premissas/
# riscos qualitativos (nao so' na recomendacao numerica, que ja' tem
# checagem deterministica propria em _divergencia_recomendacao).
#
# O QUE A IA NUNCA FAZ: recalcular recomendacao/preco-alvo/dispersao/
# divergencia (todos esses numeros continuam vindo 100% do comparador
# deterministico, so' repassados no payload pra IA EXPLICAR, nunca
# recalcular); inventar casa, trecho, data ou link que nao esteja no
# payload; emitir recomendacao de compra/venda propria.
# ============================================================

_URL_GROQ_MR = "https://api.groq.com/openai/v1/chat/completions"
_MAX_TOKENS_SINTESE_RESEARCH = 700
_TIMEOUT_S_SINTESE_RESEARCH = 30
_ORIGEM_CACHE_SINTESE_RESEARCH = "market_researcher_sintese_research"
_ORIGEM_TELEMETRIA_SINTESE_RESEARCH = "market_researcher_sintese_research"
_VERSAO_CHAVE_SINTESE_RESEARCH = "v1"
_MAX_ITENS_POR_CASA = 6  # premissas/riscos por casa no payload - teto pra nao explodir tokens com 1 casa muito prolixa

_PROMPT_SISTEMA_SINTESE_RESEARCH = (
    "Você é um analista de research que organiza, em português do Brasil, o que casas de análise "
    "de investimento JÁ publicaram sobre uma empresa listada na B3. Você recebe um payload JSON com, "
    "por casa: recomendação e preço-alvo (já extraídos e categorizados por um módulo determinístico - "
    "NUNCA recalcule esses números), data de publicação, link, e as premissas/riscos/projeções "
    "extraídos literalmente do relatório daquela casa. Também recebe checagens de divergência JÁ "
    "calculadas deterministicamente (dispersão de preço-alvo, divergência de recomendação, divergência "
    "de premissas) - são fatos prontos, você só os EXPLICA em prosa, nunca os recalcula nem contradiz.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- Use SOMENTE o conteúdo do payload. Nunca invente casa, recomendação, preço-alvo, trecho, data ou "
    "link que não esteja ali.\n"
    "- Toda afirmação sobre o que 'as casas dizem' precisa citar explicitamente QUAL casa disse o quê - "
    "nunca uma generalização sem atribuição.\n"
    "- Separe claramente convergências (o que as casas concordam, mesmo que com palavras diferentes) de "
    "divergências (onde elas discordam de fato - recomendação, premissa ou leitura de risco).\n"
    "- Nunca emita uma recomendação de compra/venda própria - seu papel é relatar o que as casas JÁ "
    "disseram, nunca substituir ou somar a elas uma conclusão nova.\n"
    "- Com apenas 1 casa cobrindo, não há o que comparar - 'convergencias'/'divergencias' ficam vazias, "
    "mas 'sintese' ainda resume o que essa única casa diz.\n"
    "- Sem nenhum conteúdo qualitativo real no payload, devolva 'sintese' vazia - nunca preencha com "
    "algo genérico.\n"
    "- 'casas_citadas': liste APENAS os nomes de casa que você de fato usou na síntese, exatamente como "
    "aparecem no payload (nunca um nome inventado ou abreviado diferente).\n"
    "- Responda APENAS com um objeto JSON válido, sem markdown, sem texto antes ou depois, no formato "
    "exato:\n"
    "{\n"
    '  "sintese": "string, 3-6 frases, o que as casas estão dizendo em conjunto sobre a empresa",\n'
    '  "convergencias": ["string, cada uma citando a(s) casa(s)"],\n'
    '  "divergencias": ["string, cada uma citando as casas em lados opostos"],\n'
    '  "pontos_atencao": ["string, riscos citados por mais de uma casa ou com mais peso"],\n'
    '  "casas_citadas": ["string - nome exato da casa"]\n'
    "}\n"
    "Máximo 6 itens em 'convergencias', 6 em 'divergencias', 6 em 'pontos_atencao'. Tom de research "
    "profissional, sem exagero, sem opinião pessoal sobre se a tese está certa ou errada."
)


def _chamar_groq_mr(chave: str, modelo: str, mensagens: list, max_tokens: int) -> tuple:
    """Cópia local do POST genérico ao endpoint de chat completions da
    Groq - mesmo padrão (e mesmo motivo de cópia independente, nunca
    importada entre módulos de dados) de data/sintese_mercado.py:
    _chamar_groq. Retorna (conteudo, motivo_falha)."""
    try:
        r = requests.post(
            _URL_GROQ_MR,
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo, "messages": mensagens, "temperature": 0.2,
                "max_tokens": max_tokens, "reasoning_effort": config.GROQ_REASONING_EFFORT,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT_S_SINTESE_RESEARCH,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except Exception as e:
        return None, str(e)


def _chamar_groq_mr_com_fallback(chave: str, modelo_principal: str, modelo_fallback: str, mensagens: list, max_tokens: int) -> tuple:
    conteudo, motivo = _chamar_groq_mr(chave, modelo_principal, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_principal
    print(f"[market_researcher] sintese_qualitativa_research: modelo principal ({modelo_principal}) falhou: {motivo}")
    conteudo, motivo = _chamar_groq_mr(chave, modelo_fallback, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_fallback
    print(f"[market_researcher] sintese_qualitativa_research: modelo fallback ({modelo_fallback}) falhou: {motivo}")
    return None, ("cota" if motivo == "cota" else "indisponivel"), modelo_fallback


def _extrair_json_mr(conteudo: str) -> dict | None:
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


def _montar_payload_sintese_research(comparacao: dict) -> dict:
    """Payload ENVIADO a IA - cada campo e' um repasse direto do que
    comparar_ticker ja' calculou (nenhum calculo novo aqui). Trechos de
    premissas/riscos sao cortados em _MAX_ITENS_POR_CASA por casa - teto
    de tamanho, nunca um corte que troque o CONTEUDO."""
    estado_atual_por_casa = comparacao.get("estado_atual_por_casa") or {}
    casas_payload = {}
    for casa, info in estado_atual_por_casa.items():
        atual = info.get("atual") or {}
        casas_payload[casa] = {
            "recomendacao": atual.get("recomendacao"),
            "categoria_normalizada": info.get("categoria"),
            "preco_alvo": atual.get("preco_alvo"),
            "data_publicacao": atual.get("data_publicacao"),
            "link": atual.get("link"),
            "titulo": atual.get("titulo"),
            "premissas": list(atual.get("premissas") or [])[:_MAX_ITENS_POR_CASA],
            "riscos": list(atual.get("riscos") or [])[:_MAX_ITENS_POR_CASA],
            "projecoes": atual.get("projecoes") or {},
        }
    return {
        "ticker": comparacao.get("ticker"),
        "casas": casas_payload,
        "checagens_deterministicas_ja_calculadas": {
            "dispersao_precos_alvo": comparacao.get("dispersao_precos_alvo"),
            "divergencia_recomendacao": comparacao.get("divergencia_recomendacao"),
            "divergencia_premissas": comparacao.get("divergencia_premissas"),
        },
    }


def _validar_sintese_research(dados, casas_reais: set) -> dict | None:
    """Validação de campo - nunca confia ciegamente na saída do modelo.
    Exige 'sintese' não vazia; descarta qualquer item de
    'casas_citadas' que não seja uma casa real do payload (nunca deixa
    passar uma casa inventada)."""
    if not isinstance(dados, dict):
        return None
    sintese = dados.get("sintese")
    if not isinstance(sintese, str) or not sintese.strip():
        return None
    convergencias = [s for s in (dados.get("convergencias") or []) if isinstance(s, str) and s.strip()][:6]
    divergencias = [s for s in (dados.get("divergencias") or []) if isinstance(s, str) and s.strip()][:6]
    pontos_atencao = [s for s in (dados.get("pontos_atencao") or []) if isinstance(s, str) and s.strip()][:6]
    casas_citadas = [c for c in (dados.get("casas_citadas") or []) if isinstance(c, str) and c in casas_reais]
    return {
        "sintese": sintese.strip(), "convergencias": convergencias, "divergencias": divergencias,
        "pontos_atencao": pontos_atencao, "casas_citadas": casas_citadas,
    }


def _chave_sintese_research(ticker: str, casas_payload: dict) -> str:
    """Muda de chave (cache MISS deliberado) sempre que o CONJUNTO/
    CONTEUDO do research por casa muda - mesmo princípio de
    data/ia_cache.py:chave_news (identidade do documento, não TTL
    explícito)."""
    identidade_casas = sorted(
        f"{casa}|{info.get('recomendacao')}|{info.get('preco_alvo')}|{info.get('data_publicacao')}|{info.get('link')}"
        for casa, info in casas_payload.items()
    )
    identidade = _VERSAO_CHAVE_SINTESE_RESEARCH + "|" + ticker + "|" + "|".join(identidade_casas)
    return hashlib.sha256(identidade.encode("utf-8")).hexdigest()


def sintese_qualitativa_research(ticker: str) -> dict:
    """Síntese qualitativa real (IA, Groq) do que as casas de research
    monitoradas estão dizendo sobre `ticker` - ver cabeçalho da seção
    pro contrato completo (o que a IA faz/nunca faz). Opt-in: quem
    decide chamar é o Coordenador Central (ver data/coordenador_central/
    fluxos.py, parâmetro sintese_ia) - nunca acionada pelos agregadores
    puramente determinísticos deste módulo.

    Retorno SEMPRE tem 'disponivel' (bool):
    - disponivel=False: nenhuma casa cobre o ticker (nada pra
      sintetizar - NENHUMA chamada de IA é feita nesse caso, pra não
      gastar cota à toa) OU a IA/Supabase falhou nesta rodada (ver
      'motivo').
    - disponivel=True: 'sintese'/'convergencias'/'divergencias'/
      'pontos_atencao'/'casas_citadas'/'modelo'/'casas_consideradas'.

    Nunca lança exceção."""
    ticker = (ticker or "").strip().upper()
    # import local: data/research/comparador.py importa DESTE módulo no
    # nível de módulo (cobertura_cruzada_casas/historico_fundamentos) -
    # um import no topo deste arquivo criaria um ciclo de importação.
    from data.research.comparador import comparar_ticker

    try:
        comparacao = comparar_ticker(ticker)
    except Exception as exc:
        print(f"[market_researcher] sintese_qualitativa_research({ticker}): comparar_ticker falhou: {exc!r}")
        return {"disponivel": False, "motivo": "falha ao consultar research consolidado"}

    if not comparacao.get("disponivel"):
        return {"disponivel": False, "motivo": comparacao.get("motivo") or "research consolidado indisponível"}
    casas_reais = set(comparacao.get("casas") or [])
    if not casas_reais:
        # Nenhuma casa cobre este ticker - nada pra sintetizar. Decisão
        # deliberada: NENHUMA chamada de IA aqui (regra inegociável da
        # missão - nunca criar uma chamada de IA artificial só pra dizer
        # que "usa IA"; sem research real, uma síntese seria vazia por
        # definição).
        return {"disponivel": False, "motivo": comparacao.get("motivo") or "nenhuma casa monitorada cobre este ticker"}

    payload = _montar_payload_sintese_research(comparacao)
    chave_cache = _chave_sintese_research(ticker, payload["casas"])

    def _gerar() -> dict:
        chave_api, modelo = config.obter_credenciais_groq()
        entrada_hash = ia_hibrida_telemetria.hash_entrada(payload)
        fontes = [
            {"casa": casa, "link": info.get("link"), "data_publicacao": info.get("data_publicacao")}
            for casa, info in payload["casas"].items()
        ]
        entrada_resumo = f"{len(casas_reais)} casa(s) para {ticker}: {', '.join(sorted(casas_reais))}"
        if not chave_api:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_RESEARCH, provedor="groq", modelo=None,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, motivo_falha="GROQ_API_KEY não configurada",
            )
            return {"resumo": None, "motivo": "GROQ_API_KEY não configurada"}

        mensagens = [
            {"role": "system", "content": _PROMPT_SISTEMA_SINTESE_RESEARCH},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        inicio = time.monotonic()
        conteudo, motivo, modelo_usado = _chamar_groq_mr_com_fallback(
            chave_api, modelo, config.obter_modelo_groq_fallback(), mensagens, _MAX_TOKENS_SINTESE_RESEARCH,
        )
        duracao_ms = int((time.monotonic() - inicio) * 1000)

        if conteudo is None:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_RESEARCH, provedor="groq", modelo=modelo_usado,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, duracao_ms=duracao_ms, motivo_falha=motivo,
            )
            return {"resumo": None, "motivo": motivo}

        dados = _validar_sintese_research(_extrair_json_mr(conteudo), casas_reais)
        if dados is None:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_RESEARCH, provedor="groq", modelo=modelo_usado,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, duracao_ms=duracao_ms, motivo_falha="resposta da IA em formato inesperado",
            )
            return {"resumo": None, "motivo": "resposta da IA em formato inesperado"}

        ia_hibrida_telemetria.registrar_execucao(
            origem=_ORIGEM_TELEMETRIA_SINTESE_RESEARCH, provedor="groq", modelo=modelo_usado,
            entrada_hash=entrada_hash, sucesso=True, ticker=ticker, entrada_resumo=entrada_resumo,
            fontes=fontes, duracao_ms=duracao_ms, resultado_resumo=dados["sintese"],
        )
        return {"resumo": dados["sintese"], "modelo": modelo_usado, "dados": dados}

    try:
        resultado = ia_cache.obter_resumo_com_cache(chave_cache, ticker, _ORIGEM_CACHE_SINTESE_RESEARCH, _gerar)
    except Exception as exc:
        print(f"[market_researcher] sintese_qualitativa_research({ticker}): obter_resumo_com_cache falhou: {exc!r}")
        resultado = _gerar()

    if not resultado.get("resumo") or not resultado.get("dados"):
        return {"disponivel": False, "motivo": resultado.get("motivo") or "síntese indisponível"}

    dados = resultado["dados"]
    return {
        "disponivel": True, "ticker": ticker, "modelo": resultado.get("modelo"),
        "casas_consideradas": sorted(casas_reais),
        "sintese": dados["sintese"], "convergencias": dados["convergencias"],
        "divergencias": dados["divergencias"], "pontos_atencao": dados["pontos_atencao"],
        "casas_citadas": dados["casas_citadas"],
    }
