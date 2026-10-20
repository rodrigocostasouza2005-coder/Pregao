# Harness visual LOCAL (manchetes/imagens reais coletadas via rede real
# nesta sessao, resumos sinteticos de comprimentos variados pra exercitar
# o card em cenarios distintos) - exercita o componente real
# (ui.news_tab._cartao_noticia), nunca um mock da renderizacao.
import sys
sys.path.insert(0, ".")
import streamlit as st

import config
import ui.news_tab as nt

st.set_page_config(page_title="harness-cards", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
nt.injetar_fallback_imagem()
nt._injetar_css()


def g(titulo, link, veiculo, tickers=()):
    return {"titulo": titulo, "titulos": [titulo], "link": link, "fontes": [{"veiculo": veiculo, "link": link}],
            "veiculos": [veiculo], "data": "2026-10-19T09:30:00-03:00", "selo": "CONFIRMADA", "score": 80,
            "fontes_count": 2, "tickers": list(tickers), "regras": []}


RESUMO_CURTO = "RESUMO:\nO dólar subiu 0,8% nesta sessão."
RESUMO_LONGO = (
    "RESUMO:\nA Vale elevou a projeção de produção de cobre para 2026 após o ramp-up da "
    "operação em Carajás, citando ganhos de eficiência operacional e menor tempo de parada "
    "programada. A companhia também revisou para cima o guidance de minério de ferro, "
    "apontando demanda chinesa mais resiliente do que o esperado no início do ano."
)
RESUMO_MEDIO = (
    "RESUMO:\nPowell disse que o Fed seguirá dependente de dados econômicos para decidir o "
    "ritmo de cortes de juros. O mercado reduziu apostas de um corte em dezembro após a fala."
)

itens = [
    (g("Vale amplia produção de cobre no Pará e eleva guidance de minério de ferro pra 2026",
       "https://valor.globo.com/x1", "Valor Econômico", ("VALE3",)),
     {"resumo": RESUMO_LONGO, "imagem": "https://s2-valor.glbimg.com/vzTzbD17suhklDT5OkVUtEL164k=/1200x/smart/filters:cover():strip_icc()/i.s3.glbimg.com/v1/AUTH_63b422c2caee4269b8b34177e8876b93/internal_photos/bs/2025/7/l/NNovYsQ7A1KNyLWhuUbg/foto24opin-201-col-op1-a14.jpg",
      "qualidade_texto": "full_text"}),
    (g("Eleições legislativas dos EUA podem ter um risco subestimado pelo mercado, aponta UBS",
       "https://infomoney.com.br/x2", "InfoMoney"),
     {"resumo": RESUMO_MEDIO,
      "imagem": "https://www.infomoney.com.br/wp-content/uploads/2024/02/eleicoes-nos-eua.jpg",
      "qualidade_texto": "full_text"}),
    (g("Ouro cai com pressão dos Treasuries e alta do dólar global", "https://moneytimes.com.br/x3", "MoneyTimes"),
     {"resumo": RESUMO_CURTO, "imagem": "https://www.moneytimes.com.br/uploads/2025/12/prata-e-ouro.png",
      "qualidade_texto": "partial_text"}),
    (g("MOVI3: preço-alvo dispara, mas a tese depende da queda da Selic", "https://acionista.com.br/x4", "Acionista", ("MOVI3",)),
     {"resumo": RESUMO_MEDIO, "imagem": "https://acionista.com.br/wp-content/uploads/2025/08/Acoes-scaled.jpg",
      "qualidade_texto": "snippet_only"}),
    (g("Copom: ata reforça juros altos por mais tempo", "https://folha.com/x5", "Folha"),
     {"resumo": RESUMO_CURTO, "imagem": None, "qualidade_texto": "extraction_failed"}),
    (g("Reuters: AI stocks bounce back after bruising selloff, CoreWeave gets Goldman upgrade",
       "https://reuters.com/x6", "Reuters"),
     None),  # sem resumo (bloqueado) - ainda assim card nao quebra
]

st.markdown('<div class="painel-titulo">NOTÍCIAS (feed editorial) — harness local, dados reais de manchete/imagem</div>', unsafe_allow_html=True)
for i, (n, resultado) in enumerate(itens):
    nt._cartao_noticia(n, i, True, "harness", ["VALE3", "MOVI3"], resultado)
