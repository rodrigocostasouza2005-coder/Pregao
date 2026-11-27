# -*- coding: utf-8 -*-
"""Isolamento da suite em relacao a CREDENCIAIS REAIS da maquina onde ela
roda (auditoria completa 2026-11-26, Topico 7a).

Problema real: a suite passava no CI (que nao tem credencial nenhuma) e
tinha testes falhando na maquina do Rodrigo, que tem
.streamlit/secrets.toml de PRODUCAO ([supabase] + [groq]). A causa nao e'
ordem de testes em si - e' que o estado de credencial vaza pra dentro dos
testes por dois caminhos globais:

1. data/supabase_client.py:obter_cliente() e' decorada com
   @st.cache_resource - um SINGLETON de processo. Com secrets.toml real
   presente, o primeiro teste que a chama sem mockar cria um cliente
   Supabase DE VERDADE, e esse cliente fica no cache pro resto da suite
   inteira. Levantamento desta auditoria: 111 testes chegam a chamar
   obter_cliente() sem substitui-lo - no CI todos recebem None
   ("Supabase indisponivel", o caminho que eles esperam), e na maquina do
   Rodrigo recebem um cliente real, que LE e ESCREVE em producao
   (coletores_status, eventos, etc.) e devolve dado real onde o teste
   esperava vazio. Mesmo teste, resultado diferente por maquina.
2. config.py:obter_credenciais_groq() le os.getenv("GROQ_API_KEY") e
   st.secrets["groq"]["api_key"] - com secrets.toml real, codigo que
   checa "IA configurada?" muda de caminho no meio da suite.

Alem disso, o cache de obter_cliente() nao e' limpo entre testes:
tests/test_supabase_client.py injeta valores de proposito (ex: a string
"cliente-fake") e limpa no fim - mas se um assert dele falhar antes do
clear(), o valor injetado fica no cache e contamina todos os testes
seguintes.

Correcao (fixture autouse): antes de CADA teste, remove as variaveis de
ambiente de credencial, troca st.secrets por um dict vazio e limpa o
cache de obter_cliente() - ou seja, todo teste comeca no MESMO estado do
CI, "sem credencial nenhuma", em qualquer maquina. Limpa de novo no fim,
pra nenhum valor injetado por um teste sobreviver pro proximo.

Isto NAO enfraquece nenhum teste: quem precisa de credencial/cliente
configura o seu (monkeypatch.setenv/patch.object) DEPOIS desta fixture,
no proprio teste - e continua funcionando igual (ver
tests/test_supabase_client.py, que injeta env + create_client e segue
passando). O que deixa de ser possivel e' um teste pegar silenciosamente
a credencial de producao da maquina de quem roda a suite.
"""
import os
import sys
from pathlib import Path

import pytest
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.supabase_client as supabase_client

_ENV_CREDENCIAIS = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "GROQ_API_KEY")


def _limpar_cache_cliente():
    """st.cache_resource expoe .clear(); se a API mudar, nunca derruba a
    suite por causa do isolamento."""
    try:
        supabase_client.obter_cliente.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def sem_credencial_real(monkeypatch):
    for nome in _ENV_CREDENCIAIS:
        monkeypatch.delenv(nome, raising=False)
    # dict vazio = mesmo efeito pratico de nao ter .streamlit/secrets.toml
    # (todo acesso a st.secrets no projeto esta' dentro de try/except ou
    # usa .get com default - ver config.py/data/supabase_client.py).
    monkeypatch.setattr(st, "secrets", {}, raising=False)
    _limpar_cache_cliente()
    yield
    _limpar_cache_cliente()


def pytest_report_header(config):
    presentes = [nome for nome in _ENV_CREDENCIAIS if os.getenv(nome)]
    if presentes:
        return (
            "conftest: credenciais presentes no ambiente "
            f"({', '.join(presentes)}) - NEUTRALIZADAS por teste "
            "(fixture sem_credencial_real)"
        )
    return "conftest: nenhuma credencial real no ambiente"
