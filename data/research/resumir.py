# -*- coding: utf-8 -*-
"""Resumo automatico de relatorios via LLM gratuito (Groq, free tier -
API compativel com OpenAI, sem SDK extra: so `requests`).

Fluxo: baixa o relatorio (HTML ou PDF) -> extrai texto (nunca copiado
verbatim pro resumo) -> resume com o LLM num formato fixo -> grava no
Supabase (tabela research_itens, ver data/research/store.py) pra nunca
resumir o mesmo link duas vezes. Se qualquer etapa falhar, retorna
resumo=None com o motivo - nunca inventa conteudo."""

from io import BytesIO

import requests
import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

import config
from . import store
from .base import HEADERS, TIMEOUT, permitido

_PROMPT_SISTEMA = (
    "Voce resume relatorios de research financeiro em portugues, em no maximo 6 linhas, "
    "SEMPRE com suas proprias palavras (nunca copie frases do texto original). "
    "Formato fixo, uma linha por item, comecando exatamente assim:\n"
    "TESE: ...\n"
    "NUMEROS-CHAVE: ...\n"
    "RECOMENDACAO / PRECO-ALVO: ...\n"
    "RISCOS: ...\n"
    "Se alguma informacao nao estiver no texto, escreva 'nao informado' nesse campo - "
    "nunca invente numeros, tickers ou recomendacoes que nao estejam no texto fornecido."
)


def _extrair_texto_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    linhas = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
    return "\n".join(linhas)


def _extrair_texto_pdf(conteudo: bytes) -> str | None:
    try:
        import pypdf
    except ImportError:
        return None
    try:
        leitor = pypdf.PdfReader(BytesIO(conteudo))
        paginas = [p.extract_text() or "" for p in leitor.pages[:15]]
        texto = "\n".join(paginas).strip()
        return texto or None
    except Exception:
        return None


def obter_texto_relatorio(link: str) -> tuple:
    """Baixa e extrai o texto de um relatorio (HTML ou PDF). Retorna
    (texto, motivo_falha) - texto=None se nao der pra extrair (exige
    login, PDF protegido/escaneado, pypdf ausente etc), com o motivo.

    Usa curl_cffi (impersonate="chrome") em vez de `requests` puro: as
    paginas de relatorio (testado com a Genial) ficam atras do mesmo WAF
    por fingerprint de TLS que a home - com `requests` normal a conexao
    simplesmente nao responde (timeout), curl_cffi contorna reproduzindo
    o handshake TLS de um Chrome de verdade."""
    if not permitido(link):
        return None, "bloqueado pelo robots.txt"
    try:
        r = cffi_requests.get(link, headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        return None, f"erro ao baixar: {e}"

    ctype = r.headers.get("Content-Type", "")
    if "pdf" in ctype or link.lower().endswith(".pdf"):
        texto = _extrair_texto_pdf(r.content)
        if texto is None:
            return None, "PDF nao pode ser lido (biblioteca pypdf ausente ou arquivo protegido/escaneado)"
        return texto, None

    texto = _extrair_texto_html(r.text)
    if len(texto) < 200:
        return None, "conteudo muito curto (provavelmente exige login)"
    return texto, None


def resumir_com_groq(texto: str, titulo: str) -> tuple:
    """Resume via Groq (free tier). Retorna (resumo, motivo_falha).
    motivo_falha='cota' especificamente em erro 429 (rate limit/cota
    esgotada), pra UI mostrar um aviso diferenciado."""
    try:
        chave = st.secrets["groq"]["api_key"]
    except Exception:
        return None, "GROQ_API_KEY nao configurada em st.secrets"

    texto_truncado = texto[:12000]
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": config.obter_modelo_groq(),
                "messages": [
                    {"role": "system", "content": _PROMPT_SISTEMA},
                    {"role": "user", "content": f"Titulo: {titulo}\n\nTexto do relatorio:\n{texto_truncado}"},
                ],
                "temperature": 0.2,
                "max_tokens": 400,
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        resumo = r.json()["choices"][0]["message"]["content"].strip()
        return resumo, None
    except Exception as e:
        return None, str(e)


def obter_resumo(link: str, titulo: str, extrator_texto=None) -> dict:
    """Resumo de um relatorio: extrai texto+resume via Groq e grava no
    Supabase (upsert pelo link, ja existente na tabela - ver
    store.salvar_resumo). Quem chama deve conferir antes se o item ja tem
    resumo salvo (rel.get('resumo')) pra nao gastar cota de IA a toa.

    extrator_texto: funcao (link)->(texto, motivo_falha) pra casas que nao
    podem usar o download generico da pagina publica (ex: XP, onde o
    conteudo pago fica na mesma pagina do trecho aberto - ver
    CASAS[i]['extrator_texto'] em data/research/__init__.py). None usa o
    generico (obter_texto_relatorio, baixa a pagina do link).

    Retorna {resumo, motivo_indisponivel}; resumo=None se qualquer etapa
    falhar (nao grava nada nesse caso)."""
    extrator = extrator_texto or obter_texto_relatorio
    texto, motivo = extrator(link)
    if texto is None:
        return {"resumo": None, "motivo_indisponivel": motivo}

    resumo, motivo = resumir_com_groq(texto, titulo)
    if resumo is None:
        return {"resumo": None, "motivo_indisponivel": motivo}

    store.salvar_resumo(link, resumo, config.obter_modelo_groq())
    return {"resumo": resumo, "motivo_indisponivel": None}
