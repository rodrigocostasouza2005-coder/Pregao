# Harness visual LOCAL (sem login/auth) - valida a reformulacao de MAIS >
# USUARIOS (ui/usuarios_tab.py:render_usuarios) direto, sem depender de
# login/Supabase real. Mesmo padrao de
# docs/evidencias/watchlist-bloomberg-20261106/harness_watchlist.py.
# Admin simulado via monkeypatch de config.obter_emails_admin (mesma
# tecnica de tests/test_usuarios_tab.py) + obter_usuarios_admin mockado
# com uma lista de usuarios de exemplo (nenhum dado real de produto).
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.usuarios_tab as usuarios_tab

st.set_page_config(page_title="harness usuarios", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

tema = config.TEMAS["AMBAR"]
_css_vars = (
    f":root {{"
    f"--bg:{tema['fundo']}; --painel-bg:{tema['painel']}; --borda:{tema['borda']}; "
    f"--destaque:{tema['destaque']}; --alta:{tema['alta']}; --baixa:{tema['baixa']}; "
    f"--neutro:{tema['neutro']}; --cinza:{tema['cinza']}; --ciano:{tema['ciano']}; "
    f"--padding-painel:0.4rem; --fonte-base:0.9rem;"
    f"}}"
)
st.markdown(f"<style>{_css_vars}</style>", unsafe_allow_html=True)
st.markdown(
    "<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>",
    unsafe_allow_html=True,
)

_ADMIN = "admin@exemplo.com"
_AGORA = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)

_USUARIOS = [
    {"email": "ana.investidora@exemplo.com",
     "created_at": (_AGORA - timedelta(days=2)).isoformat(),
     "last_seen_at": (_AGORA - timedelta(hours=3)).isoformat(),
     "status_inscricao": "inscrito"},
    {"email": "bruno.trader@exemplo.com",
     "created_at": (_AGORA - timedelta(days=15)).isoformat(),
     "last_seen_at": (_AGORA - timedelta(days=5)).isoformat(),
     "status_inscricao": "recusou"},
    {"email": "carla.b3@exemplo.com",
     "created_at": (_AGORA - timedelta(days=200)).isoformat(),
     "last_seen_at": (_AGORA - timedelta(days=1)).isoformat(),
     "status_inscricao": "inscrito"},
    {"email": "diego.quant@exemplo.com",
     "created_at": None, "last_seen_at": None,
     "status_inscricao": "nao_respondeu"},
    {"email": "=cmd|'/c calc'!A1@exemplo.com",  # prova visual da mitigacao de CSV (nao afeta a tela)
     "created_at": (_AGORA - timedelta(days=40)).isoformat(),
     "last_seen_at": (_AGORA - timedelta(days=40)).isoformat(),
     "status_inscricao": "nao_respondeu"},
]

with patch.object(usuarios_tab.config, "obter_emails_admin", return_value=[_ADMIN]), \
     patch.object(usuarios_tab, "obter_usuarios_admin", return_value=_USUARIOS):
    usuarios_tab.render_usuarios({"email": _ADMIN, "sub": "s-admin"})
