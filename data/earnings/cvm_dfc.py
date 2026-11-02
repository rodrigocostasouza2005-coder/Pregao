# -*- coding: utf-8 -*-
"""Demonstracao do Fluxo de Caixa (DFC) CONSOLIDADA de empresas
brasileiras - dados abertos da CVM (ITR), mesmo zip anual/convencoes de
cvm_dre.py/cvm_balanco.py.

--- Achado real (2026-11-01): DFC nunca desagrega trimestre isolado -------

Diferente da DRE (que as vezes tem uma linha extra so' do trimestre
isolado, ver cvm_dre.py:_linha_trimestre_isolado), o DFC da CVM SEMPRE
reporta acumulado desde 01/01 do ano (confirmado baixando o zip real:
WEGE3 2T26 DT_INI_EXERC=2026-01-01/DT_FIM_EXERC=2026-06-30, 3T26
DT_INI_EXERC=2026-01-01/DT_FIM_EXERC=2026-09-30 - nunca um trimestre
isolado de 01/04 a 30/06, por exemplo). Por isso este modulo NUNCA
pretende devolver um "trimestre isolado" de fluxo de caixa - e' sempre
"acumulado no ano (YTD) até o fim do trimestre pedido", rotulado como
tal em todo lugar que usa este modulo. A comparacao YoY (mesmo YTD um
ano antes, via ORDEM_EXERC='PENÚLTIMO' - já no mesmo arquivo) continua
válida e informativa; o que NÃO fazemos é derivar um trimestre isolado
por subtracao entre dois acumulados (mesmo motivo que levou cvm_dre.py
a evitar isso: reconciliar reclassificacoes/reapresentacoes entre
períodos sairia do escopo desta integracao).

--- Metodo direto (MD) vs indireto (MI) -----------------------------------

A empresa reporta UM dos dois por periodo, nunca os dois (confirmado:
PETR4/WEGE3/ITUB4 - 2026 - só têm DFC_MI). `obter_fluxo_caixa_trimestral`
tenta MI primeiro (tem a linha de depreciação/amortização, usada para
EBITDA histórico) e cai para MD se MI não tiver dado para aquele
CNPJ/período. Os códigos de TOPO (6.01 operacional, 6.02 investimento,
6.03 financiamento) são os mesmos nos dois métodos - só a composição
interna de 6.01 difere (MD não tem a reconciliação lucro->caixa, então
não tem linha de depreciação isolada).

--- Por que CAPEX/dividendos são identificados por TEXTO, não código fixo -

Confirmado com dado real (PETR4, WEGE3): o código exato de depreciação/
CAPEX/dividendos varia por empresa (ex: depreciação é "6.01.01.04" na
PETR4 mas "6.01.01.02" na WEGE3; CAPEX é 1 linha combinada "Aquisições
de ativos imobilizados e intangíveis" na PETR4 mas 2 linhas separadas
"Imobilizado"+"Intangível" na WEGE3). Hardcodar um código fixo
produziria `None` silencioso pra metade das empresas. Em vez disso,
casamos por palavra-chave no DS_CONTA (sem acento, minúsculo) dentro do
grupo certo (6.01.01.* pra depreciação, 6.02.* pra CAPEX, 6.03.* pra
dividendos) - nunca por grupo errado, nunca por valor sem o rótulo
bater. CAPEX soma só linhas com valor NEGATIVO (saída de caixa) que
casam "imobilizado"/"intang" - uma linha de MESMA palavra mas valor
POSITIVO (ex: "Recebimento na venda de Ativo Imobilizado") é alienação,
não aquisição, e é excluída pelo filtro de sinal."""

import io
import re
import unicodedata
import zipfile

import pandas as pd
import requests
import streamlit as st

from data.coletores_status import registrar_tentativa
from data.cvm import obter_cnpj

_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 30
_URL_ITR = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip"

_TTL_DFC = 6 * 60 * 60

_NOME_COLETOR = "CVM (Fluxo de Caixa trimestral)"
_FONTE_COLETOR = "dados.cvm.gov.br (ITR - DFC consolidado)"

_COD_FCO = "6.01"
_COD_INVESTIMENTO = "6.02"
_COD_FINANCIAMENTO = "6.03"


def _baixar_csv_do_zip(url: str, nome_no_zip: str):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open(nome_no_zip) as f:
            return pd.read_csv(f, sep=";", encoding="latin1")
    except Exception:
        return None


@st.cache_data(ttl=_TTL_DFC, show_spinner="consultando Fluxo de Caixa trimestral da CVM…")
def _dfc_itr_ano(ano: int, metodo: str):
    """metodo: 'MI' ou 'MD'."""
    nome = f"itr_cia_aberta_DFC_{metodo}_con_{ano}.csv"
    df = _baixar_csv_do_zip(_URL_ITR.format(ano=ano), nome)
    if df is None:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"download/parse do DFC_{metodo} {ano} falhou", categoria="Earnings")
        return None
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(df), categoria="Earnings")
    return df


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


_RE_DEPRECIACAO = re.compile(r"deprecia|amortiz|exaust")
_RE_CAPEX = re.compile(r"imobilizado|intang")
_RE_DIVIDENDO = re.compile(r"dividendo")


def _valor_conta_exata(m: pd.DataFrame, codigo: str):
    linha = m[m["CD_CONTA"] == codigo]
    if linha.empty:
        return None
    return float(linha.iloc[0]["VL_CONTA"])


def _soma_por_palavra_chave(m: pd.DataFrame, prefixo_grupo: str, padrao: re.Pattern, so_negativos: bool = False) -> float | None:
    """Soma VL_CONTA de todas as linhas cujo CD_CONTA comeca com
    `prefixo_grupo` (ex: '6.02.') E cujo DS_CONTA (sem acento/minusculo)
    bate `padrao`. `so_negativos` filtra so' saida de caixa (exclui
    alienacao/recebimento, que casaria a mesma palavra com sinal
    contrario). None se nenhuma linha bater (nao e' zero - e' ausencia)."""
    candidatos = m[m["CD_CONTA"].astype(str).str.startswith(prefixo_grupo)]
    if candidatos.empty:
        return None
    bateu = candidatos[candidatos["DS_CONTA"].astype(str).apply(lambda s: bool(padrao.search(_sem_acento(s))))]
    if so_negativos:
        bateu = bateu[bateu["VL_CONTA"] < 0]
    if bateu.empty:
        return None
    return float(bateu["VL_CONTA"].sum())


def _extrair_periodo(m: pd.DataFrame, ordem_exerc: str) -> dict:
    sub = m[m["ORDEM_EXERC"] == ordem_exerc]
    if sub.empty:
        return {"fco": None, "capex": None, "dividendos_pagos": None, "depreciacao_amortizacao": None}
    fco = _valor_conta_exata(sub, _COD_FCO)
    capex_bruto = _soma_por_palavra_chave(sub, _COD_INVESTIMENTO + ".", _RE_CAPEX, so_negativos=True)
    capex = abs(capex_bruto) if capex_bruto is not None else None
    dividendos_bruto = _soma_por_palavra_chave(sub, _COD_FINANCIAMENTO + ".", _RE_DIVIDENDO)
    dividendos = abs(dividendos_bruto) if dividendos_bruto is not None else None
    # depreciacao so' existe na reconciliacao do metodo indireto (6.01.01.*)
    depreciacao = _soma_por_palavra_chave(sub, "6.01.01.", _RE_DEPRECIACAO)
    return {
        "fco": fco, "capex": capex, "dividendos_pagos": dividendos,
        "depreciacao_amortizacao": depreciacao,
    }


def obter_fluxo_caixa_trimestral(ticker: str, ano: int, trimestre: int) -> dict | None:
    """Fluxo de caixa ACUMULADO NO ANO (YTD) até o fim do trimestre
    pedido (1, 2 ou 3) + o MESMO acumulado YTD um ano antes (YoY, já no
    mesmo arquivo via ORDEM_EXERC='PENÚLTIMO'). NUNCA um trimestre
    isolado - ver docstring do módulo. Tenta método indireto (MI)
    primeiro, cai pra direto (MD) se MI não tiver dado pro CNPJ/período
    (`metodo` no retorno diz qual foi usado).

    None se: ticker sem CNPJ mapeado, trimestre fora de 1-3, ou nenhum
    dos dois métodos tiver registro pro CNPJ/DT_REFER pedido. Campo
    individual ausente (capex/dividendos/depreciação não casaram
    nenhuma linha) fica None, nunca inventado.

    Retorna {"ticker", "cnpj", "empresa", "ano", "trimestre",
    "dt_referencia", "moeda", "escala_moeda", "metodo",
    "fco_ytd", "fco_ytd_ano_anterior", "capex_ytd", "capex_ytd_ano_anterior",
    "dividendos_pagos_ytd", "dividendos_pagos_ytd_ano_anterior",
    "depreciacao_amortizacao_ytd", "depreciacao_amortizacao_ytd_ano_anterior",
    "fonte_url", "fonte_nome"}."""
    if trimestre not in (1, 2, 3):
        return None
    cnpj = obter_cnpj(ticker)
    if not cnpj:
        return None

    mes_dia_fim = {1: "03-31", 2: "06-30", 3: "09-30"}[trimestre]
    dt_refer = f"{ano:04d}-{mes_dia_fim}"

    for metodo in ("MI", "MD"):
        df = _dfc_itr_ano(ano, metodo)
        if df is None:
            continue
        m = df[(df["CNPJ_CIA"] == cnpj) & (df["DT_REFER"].astype(str) == dt_refer)]
        if m.empty:
            continue
        if "VERSAO" in m.columns:
            m = m[m["VERSAO"] == m["VERSAO"].max()]

        atual = _extrair_periodo(m, "ÚLTIMO")
        anterior = _extrair_periodo(m, "PENÚLTIMO")
        primeira = m.iloc[0]
        return {
            "ticker": ticker.upper(), "cnpj": cnpj, "empresa": str(primeira.get("DENOM_CIA") or ""),
            "ano": ano, "trimestre": trimestre, "dt_referencia": str(dt_refer), "metodo": metodo,
            "moeda": str(primeira.get("MOEDA") or ""), "escala_moeda": str(primeira.get("ESCALA_MOEDA") or ""),
            "fco_ytd": atual["fco"], "fco_ytd_ano_anterior": anterior["fco"],
            "capex_ytd": atual["capex"], "capex_ytd_ano_anterior": anterior["capex"],
            "dividendos_pagos_ytd": atual["dividendos_pagos"],
            "dividendos_pagos_ytd_ano_anterior": anterior["dividendos_pagos"],
            "depreciacao_amortizacao_ytd": atual["depreciacao_amortizacao"],
            "depreciacao_amortizacao_ytd_ano_anterior": anterior["depreciacao_amortizacao"],
            "fonte_url": _URL_ITR.format(ano=ano),
            "fonte_nome": f"CVM - dados.cvm.gov.br (ITR, DFC consolidado, método {metodo})",
        }
    return None
