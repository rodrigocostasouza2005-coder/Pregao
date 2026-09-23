# -*- coding: utf-8 -*-
"""Utilitarios compartilhados pelos coletores de research: headers de
requisicao, TTL de cache e checagem de robots.txt antes de qualquer
coleta."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import streamlit as st

HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
TIMEOUT = 20
TTL_COLETA = 30 * 60  # 30 min, conforme pedido


@st.cache_resource(show_spinner=False)
def _robots_parser(dominio: str):
    rp = RobotFileParser()
    rp.set_url(f"https://{dominio}/robots.txt")
    try:
        rp.read()
    except Exception:
        return None
    return rp


def permitido(url: str) -> bool:
    """Confere o robots.txt do dominio antes de coletar. Se o robots.txt
    nao puder ser lido, assume permitido (mesmo comportamento 'fail open'
    do RobotFileParser padrao pra ausencia de arquivo)."""
    dominio = urlparse(url).netloc
    rp = _robots_parser(dominio)
    if rp is None:
        return True
    return rp.can_fetch(HEADERS["User-Agent"], url)
