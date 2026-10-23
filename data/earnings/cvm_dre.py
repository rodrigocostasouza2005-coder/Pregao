# -*- coding: utf-8 -*-
"""DRE (Demonstracao do Resultado) CONSOLIDADA de empresas brasileiras -
dados abertos da CVM (ITR/DFP), mesma fonte/convencoes de data/cvm.py
(User-Agent, cache, registrar_tentativa pro painel de SAUDE DOS DADOS).

--- Por que ITR/DFP (bulk CSV) em vez do IPE que data/cvm.py ja usa ------

data/cvm.py:obter_documentos_cvm da' o DOCUMENTO (titulo + link pro PDF)
quando a empresa reporta resultado - nao os NUMEROS da demonstracao.
ITR (trimestral)/DFP (anual) sao datasets SEPARADOS da CVM com os valores
de cada conta da DRE ja' extraidos e padronizados (CD_CONTA segue o
plano de contas oficial), por empresa/periodo - e' a fonte real pra
calcular variacao de receita/margem/lucro sem parsear PDF.

--- Trimestre isolado vs acumulado --------------------------------------

A partir do 2o trimestre do ano, a CVM traz DUAS linhas 'ULTIMO' pra
mesma conta: uma acumulada (ex: DT_INI_EXERC=01/01, DT_FIM_EXERC=30/06 -
semestre) e, quando a empresa desagrega (pratica comum, nao obrigatoria),
uma so' do trimestre isolado (DT_INI_EXERC=01/04, DT_FIM_EXERC=30/06).
Este modulo SO' usa a linha isolada (duracao <= ~100 dias) - nunca
deriva o trimestre por subtracao entre acumulados (acumulado - acumulado
anterior), que teria que reconciliar reclassificacoes/ajustes entre
re-apresentacoes e sairia do escopo desta 1a versao. Se a empresa nao
desagregar, o valor fica None (indisponivel), nunca inventado.

--- Escopo: so' trimestres 1-3 (ITR) ------------------------------------

Q4 exigiria subtrair 9 meses (ITR do 3o tri) do ano inteiro (DFP) - mesma
derivacao por subtracao que este modulo evita de proposito. Ver
LIMITACOES em reviewer.py."""

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

_TTL_DRE = 6 * 60 * 60  # mesmo TTL de data/cvm.py:_TTL_DOCUMENTOS - fonte nao atualiza mais que ~1x/dia util

_NOME_COLETOR = "CVM (DRE trimestral)"
_FONTE_COLETOR = "dados.cvm.gov.br (ITR - DRE consolidada)"

# Contas do plano de contas INDUSTRIAL/COMERCIAL da CVM (grupo 3 = DRE).
# NAO se aplica a instituicoes financeiras/seguradoras, que tem plano de
# contas proprio (ex: 3.01 vira "Receitas de Intermediacao Financeira"
# num banco) - ver reviewer.py, que sinaliza isso como limitacao
# explicita em vez de forcar o rotulo "receita_liquida" errado.
CONTAS_DRE = {
    "3.01": "receita_liquida",
    "3.02": "custo_vendas",
    "3.03": "resultado_bruto",
    "3.05": "ebit",
    "3.07": "resultado_antes_tributos",
    "3.11": "lucro_liquido_consolidado",
    "3.11.01": "lucro_liquido_controladora",
}


def _baixar_csv_do_zip(url: str, nome_no_zip: str):
    """Mesmo padrao de data/cvm.py:_baixar_csv_do_zip (duplicado aqui de
    proposito - este modulo nao deve importar internals de data/cvm.py
    alem da funcao publica obter_cnpj, pra nao criar acoplamento com um
    modulo que a sessao concorrente de Morning Call/CVM tambem toca)."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open(nome_no_zip) as f:
            return pd.read_csv(f, sep=";", encoding="latin1")
    except Exception:
        return None


@st.cache_data(ttl=_TTL_DRE, show_spinner="consultando DRE trimestral da CVM…")
def _dre_itr_ano(ano: int):
    """DRE consolidada (DRE_con) de TODAS as companhias pra 1 ano de ITR -
    baixado 1x, reaproveitado pra qualquer ticker (mesmo raciocinio de
    data/cvm.py:_ipe_ano). Registra tentativa no painel de SAUDE DOS
    DADOS (data/saude_dados.py) - None se a fonte falhar ou faltar coluna
    obrigatoria; nunca inventa DataFrame vazio como se fosse sucesso."""
    df = _baixar_csv_do_zip(_URL_ITR.format(ano=ano), f"itr_cia_aberta_DRE_con_{ano}.csv")
    if df is None:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"download/parse do zip ITR {ano} falhou", categoria="Earnings")
        return None
    obrigatorias = {"CNPJ_CIA", "DT_REFER", "DENOM_CIA", "ORDEM_EXERC",
                     "DT_INI_EXERC", "DT_FIM_EXERC", "CD_CONTA", "VL_CONTA",
                     "MOEDA", "ESCALA_MOEDA"}
    ausentes = obrigatorias - set(df.columns)
    if ausentes:
        registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=False,
                             erro=f"ITR {ano} sem colunas obrigatorias: {', '.join(sorted(ausentes))}",
                             categoria="Earnings")
        return None
    registrar_tentativa(_NOME_COLETOR, _FONTE_COLETOR, execucao_ok=True,
                         registros_novos=len(df), categoria="Earnings")
    return df


def _linha_trimestre_isolado(linhas: pd.DataFrame):
    """Dentre linhas da MESMA conta/ordem_exerc, a que cobre so' o
    trimestre isolado (duracao <= 100 dias) - None se so' existir a
    linha acumulada (empresa nao desagregou)."""
    for _, linha in linhas.iterrows():
        ini, fim = pd.Timestamp(linha["DT_INI_EXERC"]), pd.Timestamp(linha["DT_FIM_EXERC"])
        if (fim - ini).days <= 100:
            return linha
    return None


def _valor_trimestre_isolado(m: pd.DataFrame, codigo: str, ordem_exerc: str):
    linhas = m[(m["CD_CONTA"] == codigo) & (m["ORDEM_EXERC"] == ordem_exerc)]
    linha = _linha_trimestre_isolado(linhas)
    return float(linha["VL_CONTA"]) if linha is not None else None


def obter_dre_trimestral(ticker: str, ano: int, trimestre: int) -> dict | None:
    """DRE consolidada de UM trimestre isolado (1, 2 ou 3 - ver docstring
    do modulo pelo porque Q4 nao e' suportado aqui) + a MESMA conta do
    MESMO trimestre no ano anterior (comparacao YoY, ja' vem no proprio
    arquivo da CVM via ORDEM_EXERC='PENÚLTIMO' - nenhuma chamada extra).

    None se: ticker sem CNPJ mapeado (data/cvm.py:obter_cnpj), fonte CVM
    indisponivel, trimestre fora de 1-3, ou CNPJ sem nenhum registro no
    ano pedido. Nunca inventa numero - conta sem linha isolada reportada
    fica com valor None nos dois lados (atual/ano_anterior).

    Retorna {"ticker", "cnpj", "empresa", "ano", "trimestre",
    "dt_referencia", "moeda", "escala_moeda", "contas": {rotulo: {"atual":
    float|None, "ano_anterior": float|None}}, "fonte_url", "fonte_nome"}."""
    if trimestre not in (1, 2, 3):
        return None
    cnpj = obter_cnpj(ticker)
    if not cnpj:
        return None
    df = _dre_itr_ano(ano)
    if df is None:
        return None
    m = df[df["CNPJ_CIA"] == cnpj]
    if m.empty:
        return None

    # DT_REFER = data-fim do trimestre pedido, nunca "a mais recente do
    # arquivo" - bug real corrigido aqui (2026-10-22): sem este filtro,
    # pedir o 1T devolvia os numeros do 2T sempre que o 2T ja' estivesse
    # no mesmo arquivo anual. ITR da CVM usa fim de trimestre civil
    # (31/03, 30/06, 30/09) - mesma convencao nos 2 anos conferidos
    # manualmente contra o arquivo real.
    mes_dia_fim = {1: "03-31", 2: "06-30", 3: "09-30"}[trimestre]
    dt_refer = f"{ano:04d}-{mes_dia_fim}"
    m = m[m["DT_REFER"].astype(str) == dt_refer]
    if m.empty:
        return None
    if "VERSAO" in m.columns:
        m = m[m["VERSAO"] == m["VERSAO"].max()]

    contas = {
        rotulo: {
            "atual": _valor_trimestre_isolado(m, codigo, "ÚLTIMO"),
            "ano_anterior": _valor_trimestre_isolado(m, codigo, "PENÚLTIMO"),
        }
        for codigo, rotulo in CONTAS_DRE.items()
    }
    primeira = m.iloc[0]
    return {
        "ticker": ticker.upper(), "cnpj": cnpj, "empresa": str(primeira.get("DENOM_CIA") or ""),
        "ano": ano, "trimestre": trimestre, "dt_referencia": str(dt_refer),
        "moeda": str(primeira.get("MOEDA") or ""), "escala_moeda": str(primeira.get("ESCALA_MOEDA") or ""),
        "contas": contas,
        "fonte_url": _URL_ITR.format(ano=ano),
        "fonte_nome": "CVM - dados.cvm.gov.br (ITR, DRE consolidada)",
    }
