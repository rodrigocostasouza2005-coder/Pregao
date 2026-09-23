# -*- coding: utf-8 -*-
"""Utilitarios compartilhados pelos coletores de research: headers de
requisicao, timeouts e checagem de robots.txt antes de qualquer coleta."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import streamlit as st

HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
TIMEOUT = 10  # segundos por requisicao HTTP individual (robots.txt, home da casa, download de relatorio)
TEMPO_MAX_COLETA_S = 25  # orcamento total pra coletar todas as casas pendentes numa unica abertura da aba
TTL_COLETA = 30 * 60  # 30 min, conforme pedido


@st.cache_resource(show_spinner=False)
def _robots_parser(dominio: str):
    """Baixa e parseia o robots.txt com timeout explicito - RobotFileParser.
    read() sozinho usa urlopen sem timeout, que pode ficar pendurado
    indefinidamente se o dominio nao responder (ja aconteceu em teste)."""
    rp = RobotFileParser()
    rp.set_url(f"https://{dominio}/robots.txt")
    try:
        r = requests.get(f"https://{dominio}/robots.txt", headers=HEADERS, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None
        rp.parse(r.text.splitlines())
    except Exception:
        return None
    return rp


def permitido(url: str) -> bool:
    """Confere o robots.txt do dominio antes de coletar. Se o robots.txt
    nao puder ser lido (erro, timeout ou ausente), assume permitido (mesmo
    comportamento 'fail open' do RobotFileParser padrao)."""
    dominio = urlparse(url).netloc
    rp = _robots_parser(dominio)
    if rp is None:
        return True
    return rp.can_fetch(HEADERS["User-Agent"], url)
