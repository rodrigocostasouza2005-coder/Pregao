# Harness visual LOCAL (sem login/auth) - valida a reformulacao de MAIS >
# CONFIGURACOES. Esse bloco (`if rota == ("mais", "config"):`) vive
# INLINE em app.py (nao e' uma funcao em ui/*.py) e e' o ULTIMO bloco do
# arquivo - em vez de reimplementar o markup numa copia (que poderia
# divergir do codigo real sem ninguem notar), este harness LE o texto
# literal de app.py a partir dessa linha (ate o fim do arquivo) e executa
# ele com exec(), fornecendo so' as variaveis/imports que o bloco usa
# (prefs, usuario admin, registros de paineis, etc.) - e' o MESMO codigo
# que roda em producao, so' sem o resto do app (login/rede/outras rotas)
# em volta.
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
RAIZ = Path(__file__).resolve().parents[3]

import streamlit as st

import config
from data import diagnostico
from data.research import CASAS as CASAS_RESEARCH
from ui import design_system, navegacao, paineis
from ui.macro_tab import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_MACRO
from ui.mercado_tab import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_MERCADO
from ui.visao_geral import REGISTRO_PAINEIS as _REGISTRO_PAINEIS_VISAO_GERAL

st.set_page_config(page_title="harness config", layout="wide")
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

usuario = {"email": "admin@exemplo.com", "sub": "s-admin"}
# admin=True pra exercitar tambem o painel DIAGNOSTICO DE FONTES (so'
# admin, dentro do mesmo bloco "mais"/"config" em app.py) - mesma tecnica
# de monkeypatch de tests/test_usuarios_tab.py.
config.obter_emails_admin = lambda: [usuario["email"]]
prefs = dict(config.PREFS_PADRAO)
abas_visiveis = [a for a in prefs["abas_visiveis"] if a in config.ABAS_DISPONIVEIS]
rota = ("mais", "config")


def _persistir_prefs():
    """Stub - nunca escreve de verdade (sem Supabase neste harness); so
    existe pra o bloco poder chamar sem lancar, se o botao SALVAR for
    clicado."""
    return True


# monkeypatch leve so' pra diagnostico.testar_fonte nao bater rede de
# verdade SE alguem clicar "TESTAR TODAS AS FONTES" durante uma inspecao
# manual deste harness - nao afeta o screenshot estatico (botao nao e'
# clicado pelo shot.py).
diagnostico.testar_fonte = MagicMock(return_value={
    "nome": "exemplo", "ok": True, "status": "200", "tempo_ms": 120, "tamanho_bytes": 4096,
})

_fonte_app = (RAIZ / "app.py").read_text(encoding="utf-8")
_marcador = 'if rota == ("mais", "config"):'
_bloco = _fonte_app[_fonte_app.index(_marcador):]
exec(compile(_bloco, str(RAIZ / "app.py"), "exec"))
