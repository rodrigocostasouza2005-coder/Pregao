# Harness visual LOCAL (sem login/auth/Supabase/rede) - exercita
# ui/saude_dados_tab.py (render_saude_dados) com um painel de saude
# MOCKADO (coletores/estados ficticios, claramente nao reais) injetado
# via unittest.mock.patch nas funcoes de leitura de data/saude_dados.py
# (obter_painel_saude/obter_painel_consumo/diagnostico_infraestrutura) -
# nenhuma logica de classificacao/HTML de ui/saude_dados_tab.py e'
# tocada ou reimplementada aqui. Mesmo padrao de
# docs/evidencias/experiencia-design-system-20261111/harness_busca_paineis.py
# (patch de funcao de dados, nao da UI).
#
# Cobre de proposito os 4 grupos de cor que ui/saude_dados_tab.py usa
# pra estado de coletor (_COR_POR_ESTADO): alta (verde, sucesso),
# alerta (amarelo, parcial/desatualizado), baixa (vermelho, falha) e
# cinza (nunca executado/nao comprovado) - mais os 3 estados de
# CONSUMO EFETIVO (_COR_POR_ESTADO_CONSUMO: alta/alerta/cinza, nunca
# vermelho ali de proposito, ver docstring do modulo). Um item tem
# registros_novos grande (128430) pra confirmar que
# design_system.numero_financeiro_html renderiza o separador de milhar
# corretamente.
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.saude_dados_tab as saude_dados_tab

st.set_page_config(page_title="harness saude dados", layout="wide")
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

_AGORA = datetime.now(timezone.utc)


def _iso(horas_atras: float) -> str:
    return (_AGORA - timedelta(hours=horas_atras)).isoformat()


# Painel MOCKADO (ficticio) - 8 coletores cobrindo os 4 estados de cor
# reais do painel (_COR_POR_ESTADO em ui/saude_dados_tab.py).
_PAINEL_MOCK = [
    {
        "nome": "NEWS", "fonte": "Google News + extração (MOCK)", "categoria": "Noticias",
        "frequencia_esperada": "sob demanda (cache 20min)", "instrumentado": True,
        "codigo_estado": "SUCESSO_COM_NOVIDADE", "rotulo_estado": "Coleta OK - dados novos (128430)",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(0.2), "ultima_tentativa_em": _iso(0.2),
            "ultimo_erro": None, "registros_novos": 128430,
        },
        "alerta": False, "desconhecido": False,
    },
    {
        "nome": "MERCADO", "fonte": "yfinance - cotações em lote (MOCK)", "categoria": "Cotacoes",
        "frequencia_esperada": "sob demanda (cache 90s)", "instrumentado": True,
        "codigo_estado": "SUCESSO_SEM_NOVIDADE", "rotulo_estado": "Coleta OK - sem novidades",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(0.05), "ultima_tentativa_em": _iso(0.05),
            "ultimo_erro": None, "registros_novos": 0,
        },
        "alerta": False, "desconhecido": False,
    },
    {
        "nome": "MACRO (BCB)", "fonte": "Banco Central - SGS IPCA (MOCK)", "categoria": "Macro",
        "frequencia_esperada": "sob demanda (cache 4h)", "instrumentado": True,
        "codigo_estado": "DADOS_DESATUALIZADOS", "rotulo_estado": "Dados desatualizados (último sucesso há 36h)",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(36), "ultima_tentativa_em": _iso(0.1),
            "ultimo_erro": None, "registros_novos": None,
        },
        "alerta": True, "desconhecido": False,
    },
    {
        "nome": "CVM", "fonte": "dados.cvm.gov.br - IPE (MOCK)", "categoria": "CVM",
        "frequencia_esperada": "sob demanda (cache 6h)", "instrumentado": True,
        "codigo_estado": "FALHA_EXECUCAO", "rotulo_estado": "Falha de execução: timeout ao consultar IPE (mock)",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(50), "ultima_tentativa_em": _iso(0.1),
            "ultimo_erro": "timeout ao consultar IPE (mock)", "registros_novos": None,
        },
        "alerta": True, "desconhecido": False,
    },
    {
        "nome": "CVM (FCA)", "fonte": "dados.cvm.gov.br - FCA (MOCK)", "categoria": "CVM",
        "frequencia_esperada": "sob demanda (cache 24h)", "instrumentado": True,
        "codigo_estado": "FALHA_PERSISTENCIA", "rotulo_estado": "Falha de persistência (coleta OK, gravação falhou)",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(30), "ultima_tentativa_em": _iso(0.1),
            "ultimo_erro": None, "registros_novos": None,
        },
        "alerta": True, "desconhecido": False,
    },
    {
        "nome": "Genial Analisa", "fonte": "analisa.genialinvestimentos.com.br (MOCK)", "categoria": "Research",
        "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)", "instrumentado": True,
        "codigo_estado": "NUNCA_EXECUTADO", "rotulo_estado": "Nunca executado (sem evidência nenhuma)",
        "status_bruto": None,
        "alerta": False, "desconhecido": True,
    },
    {
        "nome": "XP Investimentos", "fonte": "conteudos.xpi.com.br (MOCK)", "categoria": "Research",
        "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)", "instrumentado": False,
        "codigo_estado": "NAO_COMPROVADO", "rotulo_estado": "Não comprovado (nenhum sucesso confirmado ainda)",
        "status_bruto": None,
        "alerta": False, "desconhecido": True,
    },
    {
        "nome": "RADAR DE QUEDAS", "fonte": "Carteiras recomendadas - Genial + Safra (MOCK)", "categoria": "Radar",
        "frequencia_esperada": ".github/workflows/radar-morning-call.yml, 15min (seg-sex, pregão)", "instrumentado": True,
        "codigo_estado": "PARCIAL", "rotulo_estado": "Coleta parcial (algumas fontes/itens não confirmados)",
        "status_bruto": {
            "ultimo_sucesso_em": _iso(0.3), "ultima_tentativa_em": _iso(0.3),
            "ultimo_erro": None, "registros_novos": None,
        },
        "alerta": True, "desconhecido": False,
    },
]

# Consumo efetivo MOCKADO - 3 estados reais de _COR_POR_ESTADO_CONSUMO
# (alta/alerta/cinza; nunca vermelho de propósito, ver docstring do
# módulo de dados).
_CONSUMO_MOCK = [
    {
        "fonte": "NEWS (Brasil)", "secoes": ("2. BRASIL",), "itens": 8,
        "data_edicao": "2026-11-17", "codigo_estado": "CONSUMO_COM_ITENS",
        "rotulo_estado": "Usado na última edição (8 iten(s))",
    },
    {
        "fonte": "NEWS (Internacional)", "secoes": ("3. EXTERIOR",), "itens": 0,
        "data_edicao": "2026-11-17", "codigo_estado": "CONSUMO_SEM_ITENS",
        "rotulo_estado": "Ausente na última edição (filtro editorial pode ser legítimo - ver seção)",
    },
    {
        "fonte": "NEWS (watchlist)", "secoes": ("5. EMPRESAS E SETORES",), "itens": None,
        "data_edicao": None, "codigo_estado": "CONSUMO_DESCONHECIDO",
        "rotulo_estado": "Sem edição recente do Morning Call para conferir",
    },
]

with patch("data.saude_dados.diagnostico_infraestrutura", return_value=True), \
     patch("data.saude_dados.obter_painel_saude", return_value=_PAINEL_MOCK), \
     patch("data.saude_dados.obter_painel_consumo", return_value=_CONSUMO_MOCK):
    saude_dados_tab.render_saude_dados()
