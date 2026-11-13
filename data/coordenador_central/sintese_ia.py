# -*- coding: utf-8 -*-
"""SINTESE QUALITATIVA DO COMITÊ (IA real, missão "PREGÃO 2.1 — IA real
híbrida", 2026-11-13).

data/coordenador_central/consolidacao.py permanece 100% determinístico
de propósito (ver docstring dele: "ZERO chamada de IA nova aqui") - os
testes existentes (tests/test_coordenador_central_consolidacao.py)
dependem disso, e o score/confiança/divergência CONTINUAM sendo a fonte
de verdade numérica, calculados por consolidacao.py/pareceres.py, NUNCA
recalculados aqui.

Este módulo é uma CAMADA SEPARADA, opt-in (ver data/coordenador_central/
fluxos.py, parâmetro `sintese_ia`): lê o `consolidado` DEPOIS que
consolidacao.consolidar() já terminou (pareceres de cada especialista,
divergência entre eles, categoria de confiança) e escreve, em prosa, o
PORQUÊ da convergência/divergência - citando explicitamente qual
especialista disse o quê. A IA nunca:
- recalcula recomendação, preço-alvo, upside ou a categoria de
  confiança (todos já vêm prontos do determinístico, só são repassados
  no payload pra a IA EXPLICAR);
- emite uma recomendação de compra/venda própria - só organiza e
  confronta o que os especialistas JÁ concluíram, nunca substitui a
  conclusão deles;
- inventa um especialista, tese ou número que não esteja no payload."""

import hashlib
import json
import time

import requests

import config
from data import ia_cache, ia_hibrida_telemetria

_URL_GROQ_COORD = "https://api.groq.com/openai/v1/chat/completions"
_MAX_TOKENS_SINTESE_COMITE = 600
_TIMEOUT_S_SINTESE_COMITE = 30
_ORIGEM_CACHE_SINTESE_COMITE = "coordenador_sintese_divergencia"
_ORIGEM_TELEMETRIA_SINTESE_COMITE = "coordenador_sintese_divergencia"
_VERSAO_CHAVE_SINTESE_COMITE = "v1"

_PROMPT_SISTEMA_SINTESE_COMITE = (
    "Você é o secretário de um comitê de investimentos, escrevendo em português do Brasil a MINUTA que "
    "explica o que o comitê concluiu. Você recebe um payload JSON com os pareceres JÁ emitidos por cada "
    "especialista do comitê (id, recomendação, preço-alvo quando houver, e a tese/racional que cada um já "
    "escreveu), uma checagem de divergência entre eles JÁ calculada deterministicamente, e a categoria de "
    "confiança final JÁ decidida (com a justificativa de quem decidiu). Nenhum desses dados foi gerado por "
    "você - são fatos prontos.\n\n"
    "SEU PAPEL (e só isso):\n"
    "- Explicar, citando o id de cada especialista, O QUE sustenta a recomendação dele (reaproveite a "
    "tese/racional já dada, não invente uma nova).\n"
    "- Se os especialistas DIVERGEM, explicar qual é o ponto real de desacordo (ex: um pondera mais "
    "fundamentos qualitativos, outro um número de valuation específico) - sem decidir quem está certo.\n"
    "- Se os especialistas CONVERGEM, explicar o que, nos pareceres deles, sustenta esse consenso.\n"
    "- A categoria de confiança do payload é a palavra final sobre o nível de confiança - nunca a "
    "recalcule nem a contradiga; só explique o raciocínio por trás dela em prosa.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- Use SOMENTE o conteúdo do payload. Nunca invente recomendação, preço-alvo, upside, número ou "
    "especialista que não esteja ali.\n"
    "- Nunca emita uma recomendação de compra/venda PRÓPRIA deste comitê - você só organiza e confronta o "
    "que os especialistas já concluíram.\n"
    "- 'especialistas_citados' lista APENAS os ids que você de fato usou, exatamente como aparecem no "
    "payload.\n"
    "- Responda APENAS com um objeto JSON válido, sem markdown, sem texto antes ou depois, no formato "
    "exato:\n"
    "{\n"
    '  "leitura": "string, 3-6 frases explicando o porquê da convergência/divergência",\n'
    '  "fator_decisivo": "string curta - o ponto específico (especialista(s)/número já dado) que mais '
    'pesa nesta leitura",\n'
    '  "especialistas_citados": ["id", ...]\n'
    "}\n"
    "Tom profissional de comitê de investimentos, sem exagero, sem opinião pessoal sobre se a tese está "
    "certa ou errada."
)


def _chamar_groq_coord(chave: str, modelo: str, mensagens: list, max_tokens: int) -> tuple:
    """Cópia local do POST genérico ao endpoint de chat completions da
    Groq - mesmo padrão (cópia independente, nunca importada entre
    módulos de dados diferentes) de data/sintese_mercado.py:
    _chamar_groq e data/market_researcher.py:_chamar_groq_mr."""
    try:
        r = requests.post(
            _URL_GROQ_COORD,
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo, "messages": mensagens, "temperature": 0.2,
                "max_tokens": max_tokens, "reasoning_effort": config.GROQ_REASONING_EFFORT,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT_S_SINTESE_COMITE,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except Exception as e:
        return None, str(e)


def _chamar_groq_coord_com_fallback(chave: str, modelo_principal: str, modelo_fallback: str, mensagens: list, max_tokens: int) -> tuple:
    conteudo, motivo = _chamar_groq_coord(chave, modelo_principal, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_principal
    print(f"[coordenador_central.sintese_ia] modelo principal ({modelo_principal}) falhou: {motivo}")
    conteudo, motivo = _chamar_groq_coord(chave, modelo_fallback, mensagens, max_tokens)
    if conteudo is not None:
        return conteudo, None, modelo_fallback
    print(f"[coordenador_central.sintese_ia] modelo fallback ({modelo_fallback}) falhou: {motivo}")
    return None, ("cota" if motivo == "cota" else "indisponivel"), modelo_fallback


def _extrair_json_coord(conteudo: str) -> dict | None:
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


def _montar_payload_sintese_comite(consolidado: dict) -> dict | None:
    """Payload ENVIADO a IA - repasse direto do que consolidacao.py/
    pareceres.py já calcularam (nenhum cálculo novo aqui). None quando
    não há pelo menos 2 pareceres com recomendação (payload de 0-1
    especialista não tem o que confrontar - quem chama decide não gastar
    a chamada de IA nesse caso)."""
    pareceres = (consolidado.get("pareceres_analistas") or {}).get("analistas") or []
    analistas_payload = [
        {
            "id": a.get("id"), "nome": a.get("nome"), "recomendacao": a.get("recomendacao"),
            "preco_alvo": a.get("preco_alvo"), "preco_atual": a.get("preco_atual"),
            "tese": (a.get("tese") or "")[:600],
            "pros": (a.get("pros") or [])[:3], "contras": (a.get("contras") or [])[:3],
        }
        for a in pareceres
        if a.get("recomendacao")
    ]
    if len(analistas_payload) < 2:
        return None
    divergencia_comite = (consolidado.get("divergencias") or {}).get("entre_analistas_comite")
    confianca = consolidado.get("confianca") or {}
    sinal_comite = consolidado.get("sinal_comite") or {}
    return {
        "ticker": consolidado.get("ticker"),
        "pareceres": analistas_payload,
        "divergencia_entre_especialistas_ja_calculada": divergencia_comite,
        "confianca_ja_decidida": {
            "categoria": confianca.get("categoria"), "justificativa": confianca.get("justificativa"),
        },
        "numeros_ja_calculados": {
            "preco_atual": sinal_comite.get("preco_atual"),
            "preco_alvo_consenso": sinal_comite.get("preco_alvo_consenso"),
            "preco_alvo_modelo": sinal_comite.get("preco_alvo_modelo"),
            "upside_modelo_pct": sinal_comite.get("upside_modelo_pct"),
        },
        "pontos_atencao_ja_calculados": consolidado.get("pontos_atencao") or [],
    }


def _validar_sintese_comite(dados, ids_reais: set) -> dict | None:
    if not isinstance(dados, dict):
        return None
    leitura = dados.get("leitura")
    if not isinstance(leitura, str) or not leitura.strip():
        return None
    fator_decisivo = dados.get("fator_decisivo")
    fator_decisivo = fator_decisivo.strip() if isinstance(fator_decisivo, str) else ""
    especialistas_citados = [
        i for i in (dados.get("especialistas_citados") or []) if isinstance(i, str) and i in ids_reais
    ]
    return {"leitura": leitura.strip(), "fator_decisivo": fator_decisivo, "especialistas_citados": especialistas_citados}


def _chave_sintese_comite(payload: dict) -> str:
    """Muda de chave sempre que a recomendação/preço-alvo/categoria de
    confiança de qualquer especialista mudar (mesmo princípio de
    data/ia_cache.py:chave_news - identidade do conteúdo, não TTL)."""
    identidade_pareceres = sorted(
        f"{a['id']}|{a.get('recomendacao')}|{a.get('preco_alvo')}" for a in payload["pareceres"]
    )
    confianca = payload["confianca_ja_decidida"].get("categoria")
    identidade = (
        _VERSAO_CHAVE_SINTESE_COMITE + "|" + str(payload.get("ticker")) + "|" + confianca + "|"
        + "|".join(identidade_pareceres)
    )
    return hashlib.sha256(identidade.encode("utf-8")).hexdigest()


def sintetizar_leitura_comite(consolidado: dict) -> dict:
    """Síntese qualitativa real (IA, Groq) do PORQUÊ da convergência/
    divergência entre os especialistas do Comitê, a partir do
    `consolidado` já produzido por consolidacao.consolidar() - ver
    docstring do módulo pro contrato completo (o que a IA faz/nunca
    faz). Opt-in: quem decide chamar é data/coordenador_central/
    fluxos.py (parâmetro `sintese_ia`) - nunca acionada automaticamente
    por consolidacao.consolidar(), que permanece 100% determinístico.

    Retorno SEMPRE tem 'disponivel' (bool):
    - disponivel=False: menos de 2 especialistas com recomendação (nada
      pra confrontar - NENHUMA chamada de IA é feita nesse caso) OU a
      IA/Supabase falhou nesta rodada (ver 'motivo').
    - disponivel=True: 'leitura'/'fator_decisivo'/'especialistas_citados'/
      'modelo'.

    Nunca lança exceção."""
    payload = _montar_payload_sintese_comite(consolidado)
    if payload is None:
        return {"disponivel": False, "motivo": "menos de 2 especialistas com recomendação disponível - nada para confrontar"}

    ids_reais = {a["id"] for a in payload["pareceres"]}
    chave_cache = _chave_sintese_comite(payload)
    ticker = payload.get("ticker")

    def _gerar() -> dict:
        chave_api, modelo = config.obter_credenciais_groq()
        entrada_hash = ia_hibrida_telemetria.hash_entrada(payload)
        fontes = [{"especialista_id": a["id"], "recomendacao": a.get("recomendacao")} for a in payload["pareceres"]]
        entrada_resumo = f"{len(payload['pareceres'])} especialista(s) para {ticker}: " + ", ".join(
            f"{a['id']}={a.get('recomendacao')}" for a in payload["pareceres"]
        )
        if not chave_api:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_COMITE, provedor="groq", modelo=None,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, motivo_falha="GROQ_API_KEY não configurada",
            )
            return {"resumo": None, "motivo": "GROQ_API_KEY não configurada"}

        mensagens = [
            {"role": "system", "content": _PROMPT_SISTEMA_SINTESE_COMITE},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]
        inicio = time.monotonic()
        conteudo, motivo, modelo_usado = _chamar_groq_coord_com_fallback(
            chave_api, modelo, config.obter_modelo_groq_fallback(), mensagens, _MAX_TOKENS_SINTESE_COMITE,
        )
        duracao_ms = int((time.monotonic() - inicio) * 1000)

        if conteudo is None:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_COMITE, provedor="groq", modelo=modelo_usado,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, duracao_ms=duracao_ms, motivo_falha=motivo,
            )
            return {"resumo": None, "motivo": motivo}

        dados = _validar_sintese_comite(_extrair_json_coord(conteudo), ids_reais)
        if dados is None:
            ia_hibrida_telemetria.registrar_execucao(
                origem=_ORIGEM_TELEMETRIA_SINTESE_COMITE, provedor="groq", modelo=modelo_usado,
                entrada_hash=entrada_hash, sucesso=False, ticker=ticker, entrada_resumo=entrada_resumo,
                fontes=fontes, duracao_ms=duracao_ms, motivo_falha="resposta da IA em formato inesperado",
            )
            return {"resumo": None, "motivo": "resposta da IA em formato inesperado"}

        ia_hibrida_telemetria.registrar_execucao(
            origem=_ORIGEM_TELEMETRIA_SINTESE_COMITE, provedor="groq", modelo=modelo_usado,
            entrada_hash=entrada_hash, sucesso=True, ticker=ticker, entrada_resumo=entrada_resumo,
            fontes=fontes, duracao_ms=duracao_ms, resultado_resumo=dados["leitura"],
        )
        return {"resumo": dados["leitura"], "modelo": modelo_usado, "dados": dados}

    try:
        resultado = ia_cache.obter_resumo_com_cache(chave_cache, str(ticker), _ORIGEM_CACHE_SINTESE_COMITE, _gerar)
    except Exception as exc:
        print(f"[coordenador_central.sintese_ia] sintetizar_leitura_comite: obter_resumo_com_cache falhou: {exc!r}")
        resultado = _gerar()

    if not resultado.get("resumo") or not resultado.get("dados"):
        return {"disponivel": False, "motivo": resultado.get("motivo") or "síntese indisponível"}

    dados = resultado["dados"]
    return {
        "disponivel": True, "modelo": resultado.get("modelo"),
        "leitura": dados["leitura"], "fator_decisivo": dados["fator_decisivo"],
        "especialistas_citados": dados["especialistas_citados"],
    }
