# -*- coding: utf-8 -*-
"""Fonte REAL e oficial de URL institucional/RI por ticker (fase
COLETOR DE DATAS DE RESULTADOS, 2026-10-02).

Achado verificado nesta sessão com request direto a dados.cvm.gov.br
(não inventado): o sub-arquivo "geral" do FCA (Formulário Cadastral) da
CVM tem o campo `Pagina_Web` - o site institucional oficial de cada
companhia, registrado pela PRÓPRIA empresa junto à CVM (não um texto
livre extraído de PDF, um campo estruturado do cadastro oficial).
Exemplos reais conferidos: PETR4 -> "http://www.petrobras.com.br",
ITUB4 -> "www.itau.com.br/relacoes-com-investidores" (às vezes já é a
própria página de RI), AMBEV -> "http://ri.ambev.com.br".

Reaproveita helpers privados de data/cvm.py (download+parse de zip CVM,
headers, timeout, cache de CNPJ) em vez de duplicar essa lógica - mesmo
domínio/formato de arquivo que data/cvm.py já baixa pro FCA (só um
sub-arquivo diferente dentro do mesmo zip).

LIMITAÇÃO DOCUMENTADA: este módulo só resolve a URL oficial (geralmente
a home institucional, às vezes já a página de RI) - NUNCA tenta adivinhar
sub-páginas (ex: "/calendario-de-eventos") que não estejam literalmente
neste campo, pra não inventar URL nenhuma. Ver data/eventos_coleta.py
pra o que é feito com essa URL."""

from datetime import datetime

import streamlit as st

from data.cvm import _TZ_SP, _URL_FCA, _baixar_csv_do_zip, obter_cnpj

_TTL_PAGINA_WEB = 24 * 60 * 60  # 24h - mesmo criterio do cadastro FCA em data/cvm.py (muda raramente)


@st.cache_data(ttl=_TTL_PAGINA_WEB, show_spinner=False)
def _pagina_web_ano(ano: int):
    return _baixar_csv_do_zip(_URL_FCA.format(ano=ano), f"fca_cia_aberta_geral_{ano}.csv")


def obter_url_ri(ticker: str) -> str | None:
    """URL institucional oficial do ticker (campo Pagina_Web do FCA da
    CVM, registrado pela própria empresa) - None se o ticker não tiver
    CNPJ mapeado, a fonte falhar, ou o campo vier vazio. Tenta o ano
    corrente e cai pro anterior (mesmo padrão de
    data.cvm._mapa_ticker_cnpj) - nunca inventa uma URL que não esteja
    literalmente no cadastro."""
    cnpj = obter_cnpj(ticker)
    if not cnpj:
        return None

    ano_atual = datetime.now(_TZ_SP).year
    for ano in (ano_atual, ano_atual - 1):
        df = _pagina_web_ano(ano)
        if df is None or df.empty or "Pagina_Web" not in df.columns:
            continue
        sub = df[df["CNPJ_Companhia"].str.strip() == cnpj]
        if sub.empty:
            continue
        pagina = str(sub.iloc[0]["Pagina_Web"] or "").strip()
        if not pagina or pagina.lower() == "nan":
            continue
        if not pagina.lower().startswith("http"):
            pagina = f"https://{pagina}"
        return pagina
    return None
