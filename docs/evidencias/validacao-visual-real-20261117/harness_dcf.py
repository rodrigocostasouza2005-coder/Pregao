# Harness visual LOCAL (sem login/auth/Supabase/rede) - exercita
# ui/dcf_operacional.py (render_dcf_operacional) com premissas
# MOCKADAS (claramente ficticias - WACC/crescimento/FCF nao sao dado
# real de nenhuma empresa) passadas direto pro motor real de
# data/coordenador_central/dcf_operacional.py (calcular_dcf_operacional
# + calcular_cenarios_dcf_operacional + calcular_sensibilidade_dcf_operacional,
# sem nenhuma logica de calculo reimplementada aqui). Mesmo padrao de
# docs/evidencias/experiencia-design-system-20261111/harness_workspace.py.
#
# render_dcf_operacional() envolve tudo num st.expander(expanded=False)
# - pra capturar o conteudo calculado (hero de preco, cenarios,
# sensibilidade, projecao) sem exigir clique real num app headless,
# o st.expander do modulo e' trocado (monkeypatch SO' no harness, nunca
# em ui/dcf_operacional.py) por uma versao que forca expanded=True.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.dcf_operacional as dcf_operacional
from data.coordenador_central.dcf_operacional import (
    calcular_cenarios_dcf_operacional,
    calcular_dcf_operacional,
    calcular_sensibilidade_dcf_operacional,
)

st.set_page_config(page_title="harness dcf operacional", layout="wide")
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

# Monkeypatch SO' do harness: forca o expander a abrir expandido, pra
# screenshot mostrar o conteudo calculado sem depender de clique real.
_orig_expander = st.expander


def _expander_sempre_aberto(*args, **kwargs):
    kwargs["expanded"] = True
    return _orig_expander(*args, **kwargs)


st.expander = _expander_sempre_aberto

# Premissas 100% MOCKADAS (ficticias, pra evidencia visual - nunca dado
# real de nenhuma empresa). Valores em unidade absoluta (R$), nao em
# milhoes - igual ao que ui/dcf_operacional.py monta antes de chamar o
# motor (campo "receita" do formulario vem em milhoes e e' multiplicado
# por 1_000_000 ali; aqui construimos o dict ja' na unidade que o motor
# espera).
_PREMISSAS_MOCK = {
    "receita_base": 12_000_000_000.0,
    "aliquota_impostos": 0.34,
    "wacc": 0.12,
    "g_terminal": 0.04,
    "divida_liquida": 3_500_000_000.0,
    "acoes": 2_000_000_000.0,
    "moeda": "BRL",
    "fonte_premissas": "MOCK - premissas ficticias geradas so' pra este harness de evidencia visual, nao e' dado real de nenhuma empresa",
    "data_base": None,
    "crescimento_receita": [0.08, 0.07, 0.065, 0.06, 0.05],
    "margem_ebit": [0.22, 0.225, 0.23, 0.235, 0.24],
    "da_sobre_receita": [0.05, 0.05, 0.05, 0.05, 0.05],
    "capex_sobre_receita": [0.06, 0.06, 0.055, 0.055, 0.05],
    "capital_giro_sobre_receita_incremental": [0.10, 0.10, 0.10, 0.10, 0.10],
}
# 11.00 (nao 28.50) de proposito: fica proximo do preco-alvo base
# (R$ 11,21), fazendo a tabela de sensibilidade cruzar o zero - metade
# das celulas em alta (verde) e metade em baixa (vermelho), pra
# confirmar visualmente as DUAS cores do codigo de sinal (nao so' uma).
_PRECO_ATUAL_MOCK = 11.00

resultado = calcular_dcf_operacional(_PREMISSAS_MOCK, preco_atual=_PRECO_ATUAL_MOCK)
cenarios = calcular_cenarios_dcf_operacional(
    _PREMISSAS_MOCK, delta_otimista_pp=2.0, delta_pessimista_pp=-2.0, preco_atual=_PRECO_ATUAL_MOCK,
)
sensibilidade = calcular_sensibilidade_dcf_operacional(_PREMISSAS_MOCK, preco_atual=_PRECO_ATUAL_MOCK)

st.session_state["coord_dcf_operacional_resultado"] = resultado
st.session_state["coord_dcf_operacional_cenarios"] = cenarios
st.session_state["coord_dcf_operacional_sensibilidade"] = sensibilidade

dcf_operacional.render_dcf_operacional()
