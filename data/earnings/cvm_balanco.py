# -*- coding: utf-8 -*-
"""Balanco Patrimonial (Ativo+Passivo) CONSOLIDADO de empresas brasileiras -
dados abertos da CVM (ITR), mesmo zip anual/convencoes de cvm_dre.py
(_baixar_csv_do_zip duplicado aqui de proposito - ver docstring de
cvm_dre.py pelo motivo de nao importar isso de data/cvm.py).

--- Por que BPA/BPP sao mais simples que a DRE -----------------------------

O Balanco e' uma FOTOGRAFIA no fim do periodo (saldo), nao um FLUXO
acumulado - nao existe aqui o problema de "trimestre isolado vs
acumulado" que a DRE/DFC tem (ver cvm_dre.py). Cada conta tem 1 unico
valor por DT_REFER, direto.

--- Codigos confirmados contra dado real (nao adivinhados) -----------------

Confirmados em 2026-11-01 via DS_CONTA de PETR4 e WEGE3 (download real do
zip ITR do ano corrente): "1.01.01" = "Caixa e Equivalentes de Caixa",
"2.01.04" = "Emprestimos e Financiamentos" (circulante, JA' inclui
financiamento por arrendamento/IFRS16 na agregacao da propria CVM -
nao desmembramos isso, usamos o total que a empresa reporta no nivel
pai), "2.02.01" = mesma conta nao-circulante, "2.03" = "Patrimonio
Liquido Consolidado".

--- Instituicao financeira/seguradora: bloqueado, nao aproximado ----------

Confirmado com ITUB4 (2026-11-01): o codigo "2.03" la' e' "Passivos
Financeiros ao Custo Amortizado" (um PASSIVO, nao patrimonio!) e
"1.01.01" nem existe - o plano de contas regulatorio (COSIF) usa outra
estrutura inteira. Mesmo guard de reviewer.py (SETORES_PLANO_CONTAS_
INCOMPATIVEL) se aplica aqui - quem chama (reviewer.py) deve checar
ANTES de chamar este modulo; aqui dentro nao repetimos o guard (evita
dependencia circular com config/reviewer), mas documentamos a mesma
limitacao."""

import io
import zipfile

import pandas as pd
import requests
import streamlit as st

from data.coletores_status import registrar_tentativa
from data.cvm import obter_cnpj

_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 30
_URL_ITR = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip"

_TTL_BALANCO = 6 * 60 * 60  # mesmo TTL de cvm_dre.py - fonte nao atualiza mais que ~1x/dia util

_NOME_COLETOR = "CVM (Balanco trimestral)"
_FONTE_COLETOR = "dados.cvm.gov.br (ITR - BPA/BPP consolidado)"

# Plano de contas INDUSTRIAL/COMERCIAL (grupo 1 = Ativo, grupo 2 =
# Passivo) - NAO se aplica a instituicoes financeiras/seguradoras (ver
# guard em reviewer.py, SETORES_PLANO_CONTAS_INCOMPATIVEL).
CONTAS_BPA = {
    "1.01.01": "caixa_equivalentes",
}
CONTAS_BPP = {
    "2.01.04": "divida_curto_prazo",
    "2.02.01": "divida_longo_prazo",
    "2.03": "patrimonio_liquido",
}


def _baixar_csv_do_zip(url: str, nome_no_zip: str):
    """Mesmo padrao de cvm_dre.py:_baixar_csv_do_zip (duplicado, mesmo
    motivo: nao criar acoplamento entre modulos de Earnings)."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open(nome_no_zip) as f:
            return pd.read_csv(f, sep=";", encoding="latin1")
    except Exception:
        return None


@st.cache_data(ttl=_TTL_BALANCO, show_spinner="consultando Balanco trimestral da CVM…")
def _bpa_itr_ano(ano: int):
    df = _baixar_csv_do_zip(_URL_ITR.format(ano=ano), f"itr_cia_aberta_BPA_con_{ano}.csv")
    if df is None:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"download/parse do BPA {ano} falhou", categoria="Earnings")
        return None
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(df), categoria="Earnings")
    return df


@st.cache_data(ttl=_TTL_BALANCO, show_spinner="consultando Balanco trimestral da CVM…")
def _bpp_itr_ano(ano: int):
    df = _baixar_csv_do_zip(_URL_ITR.format(ano=ano), f"itr_cia_aberta_BPP_con_{ano}.csv")
    if df is None:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"download/parse do BPP {ano} falhou", categoria="Earnings")
        return None
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(df), categoria="Earnings")
    return df


def _valor_conta(m: pd.DataFrame, codigo: str):
    """So' a linha ORDEM_EXERC='ÚLTIMO' (saldo real NO FIM do trimestre
    pedido). Bug real encontrado na validacao com dado real (2026-11-01):
    BPA/BPP tem DUAS linhas por CD_CONTA+DT_REFER - 'ÚLTIMO' (saldo do
    trimestre) e 'PENÚLTIMO' (saldo comparativo, sempre 31/12 do ano
    anterior - IGUAL pra Q1 e Q2 do MESMO ano, confirmado contra a PETR4
    real: 67253000 nas duas submissoes). Sem este filtro, .iloc[0]
    pegava a linha PENÚLTIMO (aparecia primeiro no CSV) - dívida líquida
    saía IDÊNTICA em todos os trimestres do mesmo ano, sempre o saldo de
    31/12 do ano anterior, nunca o saldo real do trimestre."""
    linha = m[(m["CD_CONTA"] == codigo) & (m["ORDEM_EXERC"] == "ÚLTIMO")]
    if linha.empty:
        return None
    return float(linha.iloc[0]["VL_CONTA"])


def obter_balanco_trimestral(ticker: str, ano: int, trimestre: int) -> dict | None:
    """Balanco (BPA+BPP) consolidado no FIM do trimestre pedido (1, 2 ou
    3 - mesma limitacao de escopo de cvm_dre.py quanto a Q4: BPA/BPP de
    Q4 SERIA o balanco de 31/12, disponivel na DFP anual, mas esta 1a
    versao so' consome o dataset ITR, que cobre so' 1-3; adicionar DFP
    fica para uma proxima rodada se fizer falta).

    None se: ticker sem CNPJ mapeado, fonte CVM indisponivel, trimestre
    fora de 1-3, ou CNPJ sem registro nesse DT_REFER. Nunca inventa
    numero - conta ausente fica None.

    Retorna {"ticker", "cnpj", "empresa", "ano", "trimestre",
    "dt_referencia", "moeda", "escala_moeda", "caixa_equivalentes",
    "divida_curto_prazo", "divida_longo_prazo", "divida_total",
    "patrimonio_liquido", "fonte_url", "fonte_nome"}."""
    if trimestre not in (1, 2, 3):
        return None
    cnpj = obter_cnpj(ticker)
    if not cnpj:
        return None
    bpa = _bpa_itr_ano(ano)
    bpp = _bpp_itr_ano(ano)
    if bpa is None or bpp is None:
        return None

    mes_dia_fim = {1: "03-31", 2: "06-30", 3: "09-30"}[trimestre]
    dt_refer = f"{ano:04d}-{mes_dia_fim}"

    m_bpa = bpa[(bpa["CNPJ_CIA"] == cnpj) & (bpa["DT_REFER"].astype(str) == dt_refer)]
    m_bpp = bpp[(bpp["CNPJ_CIA"] == cnpj) & (bpp["DT_REFER"].astype(str) == dt_refer)]
    if m_bpa.empty or m_bpp.empty:
        return None
    if "VERSAO" in m_bpa.columns:
        m_bpa = m_bpa[m_bpa["VERSAO"] == m_bpa["VERSAO"].max()]
    if "VERSAO" in m_bpp.columns:
        m_bpp = m_bpp[m_bpp["VERSAO"] == m_bpp["VERSAO"].max()]

    caixa = _valor_conta(m_bpa, "1.01.01")
    divida_cp = _valor_conta(m_bpp, "2.01.04")
    divida_lp = _valor_conta(m_bpp, "2.02.01")
    patrimonio = _valor_conta(m_bpp, "2.03")
    divida_total = (divida_cp or 0.0) + (divida_lp or 0.0) if (divida_cp is not None or divida_lp is not None) else None

    primeira = m_bpp.iloc[0]
    return {
        "ticker": ticker.upper(), "cnpj": cnpj, "empresa": str(primeira.get("DENOM_CIA") or ""),
        "ano": ano, "trimestre": trimestre, "dt_referencia": str(dt_refer),
        "moeda": str(primeira.get("MOEDA") or ""), "escala_moeda": str(primeira.get("ESCALA_MOEDA") or ""),
        "caixa_equivalentes": caixa,
        "divida_curto_prazo": divida_cp, "divida_longo_prazo": divida_lp, "divida_total": divida_total,
        "patrimonio_liquido": patrimonio,
        "fonte_url": _URL_ITR.format(ano=ano),
        "fonte_nome": "CVM - dados.cvm.gov.br (ITR, Balanco Patrimonial consolidado)",
    }
