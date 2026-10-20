# Harness visual LOCAL do MODAL (_abrir_card) - o "card" de verdade que o
# Rodrigo quer dizer (abre ao clicar na notícia, não o item da lista).
# @st.dialog não executa em bare mode - chama .__wrapped__ direto, dentro
# de um container com largura parecida com a do dialog "large" real, pra
# aproximar visualmente sem precisar de uma sessão Streamlit real.
import sys
from unittest.mock import patch

sys.path.insert(0, ".")
import streamlit as st

import config
import ui.news_tab as nt

st.set_page_config(page_title="harness-modal", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
st.markdown("<style>.aprox-dialog{max-width:760px;border:1px dashed #444;padding:1.2rem 1.4rem;margin:0 auto 2rem;}</style>", unsafe_allow_html=True)
nt.injetar_fallback_imagem()
nt._injetar_css()

ITEM = {
    "titulo": "Eleições legislativas dos EUA podem ter um risco subestimado pelo mercado, aponta UBS",
    "titulos": ["Eleições legislativas dos EUA podem ter um risco subestimado pelo mercado, aponta UBS"],
    "veiculos": ["InfoMoney"],
    "fontes": [{"veiculo": "InfoMoney", "link": "https://infomoney.com.br/x1"},
               {"veiculo": "Valor Econômico", "link": "https://valor.globo.com/x1"}],
    "fontes_count": 2,
    "data": "2026-10-19T09:30:00-03:00",
    "link": "https://infomoney.com.br/x1",
    "score": 90,
    "selo": "CONFIRMADA",
    "regras": [],
    "cvm_confirmacao": None,
    "tickers": [],
}

RESUMO_COMPLETO = (
    "RESUMO:\n"
    "O UBS avalia que o mercado pode estar subestimando o risco político associado às eleições "
    "legislativas americanas, com potencial de gerar volatilidade adicional em ativos de risco "
    "globais nas próximas semanas.\n\n"
    "O banco citou pesquisas recentes mostrando um cenário mais disputado do que o precificado "
    "atualmente pelos mercados de opções.\n\n"
    "POR QUE IMPORTA:\n"
    "Mudanças na composição do Congresso americano afetam diretamente a agenda fiscal e regulatória "
    "dos próximos dois anos, um fator que o mercado histórico tende a precificar tarde demais.\n\n"
    "LEITURA DE MERCADO:\n"
    "Um resultado eleitoral mais apertado tende a aumentar a volatilidade de curto prazo em bolsas "
    "globais, embora o efeito sobre ativos brasileiros específicos ainda não seja claro a partir do texto."
)

resultado = {
    "resumo": RESUMO_COMPLETO,
    "qualidade_texto": "full_text",
    "parcial": False,
    "modelo": "llama-3.3-70b",
}

with patch.object(nt, "obter_resumo_grupo", return_value=resultado), \
     patch.object(nt, "imagem_pronta_do_grupo", return_value="https://www.infomoney.com.br/wp-content/uploads/2024/02/eleicoes-nos-eua.jpg"), \
     patch.object(nt, "ordenar_fontes_para_resumo", return_value=tuple((f["veiculo"], f["link"]) for f in ITEM["fontes"])):
    st.markdown("<div class='aprox-dialog'>", unsafe_allow_html=True)
    nt._abrir_card.__wrapped__(ITEM, ["VALE3"])
    st.markdown("</div>", unsafe_allow_html=True)
