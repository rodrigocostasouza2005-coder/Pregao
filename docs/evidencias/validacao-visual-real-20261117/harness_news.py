# Harness visual LOCAL (sem login/auth, sem Supabase/rede real) para
# capturar evidencia visual da area NOTICIAS (ui/news_tab.py, subaba
# "Empresas") - mesmo padrao dos demais harnesses desta missao. Adaptado de
# docs/evidencias/news-card-redesign-20261019/harness_cards.py, que so'
# exercitava o componente de card isolado (_cartao_noticia); aqui chamamos
# o PONTO DE ENTRADA real (render_news, o que o app.py de fato chama pra
# aba NEWS) pra ter uma captura "landing" representativa, no mesmo padrao
# das outras 3 areas desta missao (render_* completo, nao so' o componente).
#
# news_tab.py mudou (commit 3e33101, 2026-11-06) depois da ultima captura
# salva (news-card-redesign-20261019, 2026-10-19) - harness refeito do zero
# pra refletir o codigo atual.
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

import config
import ui.news_tab as nt

st.set_page_config(page_title="harness news - feed editorial", layout="wide")
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
st.markdown("<style>body{background:var(--bg);} .stApp{background:var(--bg);}</style>", unsafe_allow_html=True)

PREFS = dict(config.PREFS_PADRAO)
PREFS["watchlist"] = ["PETR4", "VALE3", "MOVI3"]

RESUMO_VALE = (
    "RESUMO:\nA Vale elevou a projeção de produção de cobre para 2026 após o ramp-up da "
    "operação em Carajás, citando ganhos de eficiência operacional e menor tempo de parada "
    "programada. A companhia também revisou para cima o guidance de minério de ferro, "
    "apontando demanda chinesa mais resiliente do que o esperado no início do ano."
)
RESUMO_PETR = (
    "RESUMO:\nA Petrobras anunciou programa de recompra de ações de até R$ 5 bilhões, com "
    "prazo de 12 meses. A companhia citou geração de caixa consistente e disciplina de "
    "capital como justificativa para a decisão."
)
RESUMO_POWELL = (
    "RESUMO:\nPowell disse que o Fed seguirá dependente de dados econômicos para decidir o "
    "ritmo de cortes de juros. O mercado reduziu apostas de um corte em dezembro após a fala."
)
RESUMO_MOVI = (
    "RESUMO:\nAnalistas elevaram o preço-alvo de MOVI3, mas ponderam que a tese de valorização "
    "depende da trajetória de queda da Selic ao longo de 2027 para reduzir o custo de capital "
    "da locadora."
)
RESUMO_DOLAR = "RESUMO:\nO dólar subiu 0,8% nesta sessão, em dia de cautela global antes da divulgação de dados de inflação nos EUA."


def _n(titulo, link, veiculo, selo, data, tickers=()):
    return {
        "titulo": titulo, "titulos": [titulo], "link": link, "fontes": [{"veiculo": veiculo, "link": link}],
        "veiculos": [veiculo], "data": data, "selo": selo, "score": 80, "fontes_count": 2,
        "tickers": list(tickers), "regras": [],
    }


_NOTICIAS = [
    _n("Vale amplia produção de cobre no Pará e eleva guidance de minério de ferro pra 2026",
       "https://exemplo.com/vale-cobre-2026", "Valor Econômico", "CONFIRMADA",
       "2026-11-17T09:30:00-03:00", ("VALE3",)),
    _n("Petrobras anuncia programa de recompra de ações de até R$ 5 bilhões",
       "https://exemplo.com/petrobras-recompra", "InfoMoney", "CONFIRMADA",
       "2026-11-17T08:10:00-03:00", ("PETR4",)),
    _n("Powell reforça dependência de dados para decidir ritmo de cortes de juros",
       "https://exemplo.com/powell-juros", "MoneyTimes", "PROVÁVEL",
       "2026-11-16T19:45:00-03:00", ()),
    _n("MOVI3: preço-alvo dispara, mas a tese depende da queda da Selic", "https://exemplo.com/movi3-tese",
       "Acionista", "NÃO CONFIRMADA", "2026-11-16T14:20:00-03:00", ("MOVI3",)),
    _n("Dólar sobe 0,8% com cautela global antes de dados de inflação nos EUA",
       "https://exemplo.com/dolar-sobe", "Folha", "CONFIRMADA", "2026-11-16T10:05:00-03:00", ()),
]

# Sem URL de imagem real (http/https) de proposito - imagem=None faz o
# card cair no mesmo fallback que uma noticia real sem foto cacheada usa
# (injetar_fallback_imagem/CSS, ver ui/news_tab.py), evitando qualquer
# chamada de rede de verdade durante a captura (achado desta missao: usar
# URL de placeholder externo travava page.goto(wait_until="networkidle")
# no Playwright esperando a imagem terminar de carregar).
_RESUMOS_PRONTOS = {
    "https://exemplo.com/vale-cobre-2026": {
        "resumo": RESUMO_VALE, "imagem": None, "qualidade_texto": "full_text",
    },
    "https://exemplo.com/petrobras-recompra": {
        "resumo": RESUMO_PETR, "imagem": None, "qualidade_texto": "full_text",
    },
    "https://exemplo.com/powell-juros": {
        "resumo": RESUMO_POWELL, "imagem": None, "qualidade_texto": "partial_text",
    },
    "https://exemplo.com/movi3-tese": {
        "resumo": RESUMO_MOVI, "imagem": None, "qualidade_texto": "snippet_only",
    },
    "https://exemplo.com/dolar-sobe": {
        "resumo": RESUMO_DOLAR, "imagem": None, "qualidade_texto": "extraction_failed",
    },
}

# render_news (@st.fragment) chama _renderizar_feed_editorial internamente,
# que TAMBEM e' @st.fragment - em bare mode (sem sessao real do Streamlit),
# uma funcao @st.fragment chamada "normal" (nao via .__wrapped__) nao
# executa o corpo (mesmo achado documentado nos harnesses de dialog desta
# missao). Como render_news so' e' alcancavel por fora via .__wrapped__,
# precisamos tambem destravar a chamada INTERNA trocando a referencia do
# fragment aninhado pela sua versao .__wrapped__.
with patch.object(nt, "obter_noticias_watchlist", return_value=(_NOTICIAS, [])), \
     patch.object(nt, "_lives_para_feed", return_value=[]), \
     patch.object(nt, "obter_resumos_prontos", return_value=_RESUMOS_PRONTOS), \
     patch.object(nt, "_renderizar_feed_editorial", nt._renderizar_feed_editorial.__wrapped__):
    nt.render_news.__wrapped__(PREFS)
