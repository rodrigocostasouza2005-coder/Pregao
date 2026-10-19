# Harness visual LOCAL (dados sintéticos, imagens servidas em localhost:8765).
# Exercita o código real de leitura/mescla (obter_resumos_prontos com
# ia_cache.obter_varios mockado) e os componentes reais da UI.
import sys
from unittest.mock import patch

sys.path.insert(0, "/home/user/Pregao")
import streamlit as st

import config
import data.ia_cache as ia_cache
import data.news as news
import ui.news_tab as nt

st.set_page_config(page_title="harness", layout="wide")
with open(config.BASE_DIR / "style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
nt.injetar_fallback_imagem()
nt._injetar_css()

IMG = "http://localhost:8765/img/"


def g(titulo, slug, veiculo, imp=None, tickers=()):
    link = f"https://news.google.com/rss/articles/{slug}"
    d = {"titulo": titulo, "titulos": [titulo], "link": link, "fontes": [{"veiculo": veiculo, "link": link}],
         "veiculos": [veiculo], "data": "2026-10-19T09:30:00-03:00", "selo": "CONFIRMADA", "score": 80,
         "fontes_count": 2, "tickers": list(tickers), "regras": []}
    if imp is not None:
        d["importancia"] = imp
        d["regiao"] = "BR"
        d["criterio_ranking"] = ["3 veículos", "recente"]
    return d


grupos = [
    g("Vale amplia produção de cobre no Pará e eleva guidance", "vale", "Valor Econômico", 95, ("VALE3",)),
    g("Petrobras inicia operação de nova plataforma no pré-sal", "petr", "InfoMoney", 90, ("PETR4",)),
    g("Powell sinaliza cautela com cortes de juros nos EUA", "fed", "Reuters", 85),
    g("Itaú reporta lucro recorde no 3º trimestre", "itau", "Estadão", 80, ("ITUB4",)),
    g("Dólar fecha em alta de 0,8% com exterior negativo", "dolar", "UOL", 70),
    g("Ibovespa fecha em queda puxado por bancos", "ibov", "UOL", 65),
    g("Copom: ata reforça juros altos por mais tempo", "copom", "Folha", 60),
    g("Magazine Luiza anuncia reestruturação de dívida", "mglu", "Exame", 55, ("MGLU3",)),
]
ch = lambda x: news._chave_grupo(x)
ci = lambda x: ia_cache.chave_imagem_news(news._chave_grupo(x))
linhas = {
    ch(grupos[0]): {"resumo": "RESUMO:\nA Vale elevou a projeção de produção de cobre para 2026 após ramp-up em Carajás. A mineradora citou ganhos de eficiência.", "imagem": IMG + "vale-cobre.jpg", "imagem_status": "confirmada"},
    ci(grupos[1]): {"imagem": IMG + "petrobras-plataforma.jpg", "imagem_status": "confirmada"},  # só registro de imagem (sem resumo)
    ch(grupos[2]): {"resumo": "RESUMO:\nPowell disse que o Fed seguirá dependente de dados. Mercado reduziu apostas de corte em dezembro.", "imagem": IMG + "fed-powell.jpg"},
    ci(grupos[3]): {"imagem": IMG + "itau-agencia.jpg", "imagem_status": "nao_verificada"},
    ch(grupos[4]): {"resumo": "RESUMO:\nO dólar subiu 0,8%.", "imagem": IMG + "fechamento-padrao.jpg"},  # repetida em matéria diferente
    ch(grupos[5]): {"resumo": "RESUMO:\nO Ibovespa caiu 1,1%.", "imagem": IMG + "fechamento-padrao.jpg"},
    ci(grupos[6]): {"imagem": None, "imagem_status": "ausente"},
    ch(grupos[7]): {"resumo": "RESUMO:\nA varejista renegociou debêntures.", "imagem": "http://localhost:8765/img/QUEBRADA-404.jpg"},
}

with patch.object(ia_cache, "obter_varios", side_effect=lambda chaves: {c: linhas[c] for c in chaves if c in linhas}):
    prontos = news.obter_resumos_prontos(grupos)

st.markdown('<div class="painel-titulo">BASELINE (sem miniatura)</div>', unsafe_allow_html=True)
nt._renderizar_lista(grupos[:3], mostrar_ticker=True, prefixo="base", watchlist=["VALE3"])
st.markdown('<div class="painel-titulo">TOP MERCADO (lista wire com miniatura)</div>', unsafe_allow_html=True)
nt._renderizar_lista(grupos, mostrar_ticker=True, prefixo="top", watchlist=["VALE3"], resumos_prontos=prontos)

st.markdown('<div class="painel-titulo">NOTÍCIAS (feed editorial)</div>', unsafe_allow_html=True)
for i, n in enumerate(grupos):
    nt._cartao_noticia(n, i, True, "feed", ["VALE3"], prontos.get(n["link"]))

st.markdown('<div class="painel-titulo">MODAL — capa (retrato recortado / sem foto)</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    nt._renderizar_capa(prontos[grupos[2]["link"]]["imagem"], "Reuters")
    st.markdown(f"<div class='news-headline'>{grupos[2]['titulo']}</div>", unsafe_allow_html=True)
with c2:
    nt._renderizar_capa(prontos[grupos[6]["link"]]["imagem"], "Folha")
    st.markdown(f"<div class='news-headline'>{grupos[6]['titulo']}</div>", unsafe_allow_html=True)

st.code("\n".join(f"{n['titulo'][:45]:<46} -> {prontos.get(n['link'], {}).get('imagem_status')!s:<18} {str(prontos.get(n['link'], {}).get('imagem'))[-28:]}" for n in grupos))
