# -*- coding: utf-8 -*-
"""Classificacao de posts do X via Groq (MESMA credencial/infra de
data/research/resumir.py - config.obter_credenciais_groq + cache global
em data/ia_cache.py, nenhuma arquitetura de IA nova). Cada post vira,
na melhor das hipoteses, uma CATEGORIA entre as 8 pedidas - nunca
infere recomendacao de compra/venda a partir de sentimento, nunca trata
opiniao como fato (ver _PROMPT_SISTEMA abaixo, instrucao explicita)."""

import hashlib
import json
from datetime import datetime, timezone

import requests

import config
from data.ia_cache import obter_resumo_com_cache
from data.x_radar import CATEGORIAS_PUBLICACAO, VERSAO_CLASSIFICADOR

_ORIGEM_CACHE = "x_radar"

_PROMPT_SISTEMA = (
    "Voce e um analista de compliance/pesquisa classificando UMA publicacao do X "
    "(Twitter) sobre o mercado financeiro brasileiro. Responda APENAS em JSON valido, "
    "sem nenhum texto antes ou depois, com estas chaves exatas:\n"
    '{"categoria": uma de ' + json.dumps(list(CATEGORIAS_PUBLICACAO)) + ', '
    '"tipo_conteudo": string curta (ex: "analise fundamentalista", "rumor de M&A"), '
    '"ticker": ticker B3 mencionado ou null, "empresa": nome da empresa ou null, '
    '"setor": setor ou null, "tema": assunto principal em poucas palavras, '
    '"sentimento": "positivo"|"negativo"|"neutro"|"misto", '
    '"argumento_central": 1 frase objetiva do que o autor afirma, '
    '"catalisador": possivel catalisador de preco mencionado, ou null, '
    '"risco": risco mencionado, ou null, '
    '"necessita_investigacao": true|false, '
    '"resumo": resumo de 1-2 frases com SUAS PROPRIAS palavras (nunca copie o texto original)}\n\n'
    "REGRAS OBRIGATORIAS: (1) opiniao de analista/investidor NUNCA e' 'fato_confirmado' - "
    "so' use 'fato_confirmado' se o texto citar uma fonte primaria verificavel (comunicado "
    "oficial, documento regulatorio, numero de um resultado JA publicado); (2) sentimento "
    "positivo NUNCA significa recomendacao de compra - sao conceitos diferentes, nao infira "
    "um do outro; (3) se o texto nao tiver relacao com investimento/mercado, categoria = "
    "'sem_relevancia'; (4) nunca invente ticker/empresa/setor que o texto nao mencione."
)


def _chave_cache(post_id: str) -> str:
    return hashlib.sha256(f"x_radar:{VERSAO_CLASSIFICADOR}:{post_id}".encode("utf-8")).hexdigest()


def _chamar_groq_classificacao(texto: str) -> tuple[dict | None, str | None]:
    """Mesma chamada HTTP de data/research/resumir.py:_chamar_groq (nao
    importada direto - funcao privada de outro modulo - replicada aqui
    com os MESMOS parametros/credencial/modelo). Retorna (json, motivo)."""
    api_key, modelo = config.obter_credenciais_groq()
    if not api_key:
        return None, "sem_credencial"
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": _PROMPT_SISTEMA},
                    {"role": "user", "content": texto[:2000]},
                ],
                "temperature": 0.1,
                "max_tokens": 500,
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        conteudo = r.json()["choices"][0]["message"]["content"].strip()
        return json.loads(conteudo), None
    except json.JSONDecodeError:
        return None, "resposta_invalida"
    except Exception as exc:
        return None, str(exc)[:200]


def classificar_post(sinal) -> dict:
    """Classifica UM Sinal (data/x_signals.py:Sinal) - cacheado por
    post_id+VERSAO_CLASSIFICADOR (ver _chave_cache), nunca gasta cota de
    IA 2x pro mesmo post na mesma versao do classificador. Retorna dict
    com todos os campos de classificacao + 'ok' (bool) + 'motivo_falha'
    (None|'sem_credencial'|'cota'|'indisponivel'|'resposta_invalida')."""

    def _gerar():
        resultado_ia, motivo = _chamar_groq_classificacao(sinal.contexto)
        if resultado_ia is None:
            return {"resumo": None, "ok": False, "motivo_falha": motivo}
        categoria = resultado_ia.get("categoria")
        if categoria not in CATEGORIAS_PUBLICACAO:
            categoria = "sem_relevancia"
        return {
            "resumo": resultado_ia.get("resumo") or sinal.contexto[:200],
            "ok": True, "motivo_falha": None,
            "categoria": categoria,
            "tipo_conteudo": resultado_ia.get("tipo_conteudo"),
            "ticker": (resultado_ia.get("ticker") or "").upper() or None,
            "empresa": resultado_ia.get("empresa"),
            "setor": resultado_ia.get("setor"),
            "tema": resultado_ia.get("tema"),
            "sentimento": resultado_ia.get("sentimento"),
            "argumento_central": resultado_ia.get("argumento_central"),
            "catalisador": resultado_ia.get("catalisador"),
            "risco": resultado_ia.get("risco"),
            "necessita_investigacao": bool(resultado_ia.get("necessita_investigacao")),
            "modelo": config.obter_credenciais_groq()[1],
            "versao_classificador": VERSAO_CLASSIFICADOR,
            "classificado_em": datetime.now(timezone.utc).isoformat(),
        }

    resultado = obter_resumo_com_cache(_chave_cache(sinal.post_id), sinal.link_original, _ORIGEM_CACHE, _gerar)
    resultado.setdefault("ok", bool(resultado.get("resumo")))
    resultado.setdefault("motivo_falha", None if resultado.get("ok") else "indisponivel")
    return resultado


def classificar_lote(sinais: list) -> list[dict]:
    """Classifica cada Sinal; posts cuja IA falhar (sem credencial/cota/
    erro) ENTRAM na lista com ok=False e categoria=None - nunca
    descartados em silencio (quem persiste decide o que fazer, ver
    data/x_radar/store.py), nunca fica 'sem_relevancia' so por falha
    tecnica (isso seria inventar uma classificacao)."""
    classificados = []
    for sinal in sinais:
        classificacao = classificar_post(sinal)
        classificados.append({"sinal": sinal, "classificacao": classificacao})
    return classificados
