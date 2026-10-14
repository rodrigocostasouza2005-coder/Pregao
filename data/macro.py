# -*- coding: utf-8 -*-
"""Indicadores macro: IPCA/Selic/CDI (SGS do BC), expectativas Focus (Olinda),
curva de juros prefixada (ANBIMA ETTJ) e cenario global (ouro/Brent/WTI/
minerio de ferro/Treasuries 10A/VIX via yfinance). Nunca inventa dados: se
uma fonte falhar, a funcao retorna None (ou [], pro cenario global) e quem
chama deve avisar o usuario."""

from datetime import date, datetime, timedelta
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from config import CENARIO_GLOBAL
from data.coletores_status import registrar_tentativa
from data.mercado import _baixar_lote_bruto, _linha_papel

TZ = ZoneInfo("America/Sao_Paulo")
_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial)"}
_TIMEOUT = 15
_TTL_SERIES = 4 * 3600
_TTL_CURVA = 6 * 3600

_SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
_FOCUS_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
_ANBIMA_ETTJ_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"

# codigos das series no SGS (https://www3.bcb.gov.br/sgspub)
_SGS_IPCA_MENSAL = 433
_SGS_IPCA_12M = 13522
_SGS_SELIC_META = 432
_SGS_CDI_DIARIO = 12
_SGS_CDI_ANUALIZADO = 4389


def _serie_sgs(codigo: int, dias_historico: int) -> pd.DataFrame:
    """Busca uma serie do SGS entre (hoje - dias_historico) e hoje, devolve
    DataFrame [data, valor] com data tz-aware (America/Sao_Paulo) e valor em
    float. Lanca excecao se falhar (quem chama decide como tratar).

    Usa o endpoint por intervalo de datas (.../dados?dataInicial=...), NAO
    o .../dados/ultimos/{n}: testado na pratica, esse ultimo rejeita com
    HTTP 400 qualquer N > 20 ('A quantidade maxima de valores deve ser 20'),
    o que e pouco pra qualquer historico de grafico."""
    hoje = datetime.now(TZ).date()
    inicio = hoje - timedelta(days=dias_historico)
    url = (
        _SGS_BASE.format(codigo=codigo)
        + f"?formato=json&dataInicial={inicio.strftime('%d/%m/%Y')}&dataFinal={hoje.strftime('%d/%m/%Y')}"
    )
    # O SGS ocasionalmente demora mais que o timeout normal. Repetir
    # falhas transitórias (timeout, conexão, HTTP 429/5xx) evita marcar
    # a série como indisponível por uma única resposta lenta. Não repete
    # erros HTTP permanentes nem altera/estima os dados retornados.
    ultima_excecao = None
    for tentativa in range(3):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=(5, 25))
            if r.status_code == 429 or r.status_code >= 500:
                r.raise_for_status()
            r.raise_for_status()
            dados = r.json()
            break
        except requests.RequestException as e:
            ultima_excecao = e
            transitório = (
                isinstance(e, (requests.Timeout, requests.ConnectionError))
                or (getattr(getattr(e, "response", None), "status_code", 0) in (429, 500, 502, 503, 504))
            )
            if not transitório or tentativa == 2:
                raise
            time.sleep(1 + tentativa)
    else:
        raise ultima_excecao

    if not dados:
        raise ValueError(f"SGS {codigo} retornou lista vazia")
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", dayfirst=True).dt.tz_localize(TZ)
    df["valor"] = df["valor"].astype(float)
    return df[["data", "valor"]]


@st.cache_data(ttl=_TTL_SERIES, show_spinner="atualizando indicadores macro…")
def obter_ipca(dias_historico: int = 760) -> pd.DataFrame | None:
    """IPCA mensal (% a.m.) e acumulado 12 meses (%), lado a lado por data,
    cobrindo os ultimos `dias_historico` dias corridos (padrao ~25 meses).
    None se qualquer uma das duas series falhar."""
    try:
        mensal = _serie_sgs(_SGS_IPCA_MENSAL, dias_historico).rename(columns={"valor": "ipca_mensal_pct"})
        doze_meses = _serie_sgs(_SGS_IPCA_12M, dias_historico).rename(columns={"valor": "ipca_12m_pct"})
        df = pd.merge(mensal, doze_meses, on="data", how="outer").sort_values("data").reset_index(drop=True)
        # registro de SAUDE DOS DADOS (ver data/saude_dados.py) - so'
        # numa execucao real (cache miss). Ate' 2026-10-13, "MACRO
        # (BCB)" era o UNICO registro pra IPCA/Selic/CDI juntos (IPCA
        # como ponto representativo) - gap de escopo corrigido nesta
        # sessao: Selic/CDI/Focus agora tem linha propria (ver
        # obter_selic_meta/obter_cdi/obter_focus_ipca/obter_focus_selic
        # abaixo), entao uma falha isolada numa dessas series deixa de
        # ficar escondida atras de um IPCA que continua OK.
        registrar_tentativa("MACRO (BCB)", "Banco Central (SGS)", execucao_ok=True,
                             registros_novos=len(df), categoria="Macro")
        return df
    except Exception as e:
        registrar_tentativa("MACRO (BCB)", "Banco Central (SGS)", execucao_ok=False,
                             erro=str(e)[:300], categoria="Macro")
        return None


@st.cache_data(ttl=_TTL_SERIES, show_spinner="atualizando indicadores macro…")
def obter_selic_meta(dias_historico: int = 400) -> pd.DataFrame | None:
    """Historico da meta Selic definida pelo Copom (% a.a.), cobrindo os
    ultimos `dias_historico` dias corridos. A serie tem um ponto por dia
    (repete o valor vigente entre uma decisao do Copom e outra)."""
    # registro de SAUDE DOS DADOS (gap de escopo ja catalogado em
    # BACKLOG.md, resolvido nesta sessao de continuacao 2026-10-13):
    # antes, so' obter_ipca chamava registrar_tentativa - "MACRO (BCB)"
    # usava IPCA como ponto representativo da fonte inteira, entao uma
    # falha ISOLADA da Selic (ex: BC renomeia/descontinua o codigo SGS
    # 432) nunca aparecia no painel enquanto IPCA continuasse OK. Linha
    # separada, mesmo padrao ja usado hoje pra CVM (FCA)/NEWS
    # (watchlist).
    try:
        df = _serie_sgs(_SGS_SELIC_META, dias_historico).rename(columns={"valor": "selic_meta_pct"})
        registrar_tentativa("MACRO (BCB - Selic)", "Banco Central (SGS)", execucao_ok=True,
                             registros_novos=len(df), categoria="Macro")
        return df
    except Exception as e:
        registrar_tentativa("MACRO (BCB - Selic)", "Banco Central (SGS)", execucao_ok=False,
                             erro=str(e)[:300], categoria="Macro")
        return None


@st.cache_data(ttl=_TTL_SERIES, show_spinner="atualizando indicadores macro…")
def obter_cdi(dias_historico: int = 90) -> pd.DataFrame | None:
    """CDI diario (% a.d.) e CDI anualizado base 252 (% a.a.), lado a lado
    por data, cobrindo os ultimos `dias_historico` dias corridos. None se
    qualquer uma das duas series falhar."""
    # registro de SAUDE DOS DADOS - mesmo motivo/padrao de obter_selic_meta acima.
    try:
        diario = _serie_sgs(_SGS_CDI_DIARIO, dias_historico).rename(columns={"valor": "cdi_diario_pct"})
        anualizado = _serie_sgs(_SGS_CDI_ANUALIZADO, dias_historico).rename(columns={"valor": "cdi_anualizado_pct"})
        df = pd.merge(diario, anualizado, on="data", how="outer").sort_values("data").reset_index(drop=True)
        registrar_tentativa("MACRO (BCB - CDI)", "Banco Central (SGS)", execucao_ok=True,
                             registros_novos=len(df), categoria="Macro")
        return df
    except Exception as e:
        registrar_tentativa("MACRO (BCB - CDI)", "Banco Central (SGS)", execucao_ok=False,
                             erro=str(e)[:300], categoria="Macro")
        return None


def _focus_anual(indicador: str, ano: int, base_calculo: int = 0) -> dict | None:
    """Ultima leitura das expectativas de mercado (Focus) pra um indicador e
    ano de referencia. base_calculo=0 usa a serie completa (todos os
    informantes do mes), igual ao numero publicado no relatorio Focus
    semanal do BC (base_calculo=1 e uma variante 'suavizada' considerando so
    os ultimos 30 dias corridos, com menos respondentes)."""
    # a API OData da olinda exige espacos como %20 (nao aceita '+', que e o
    # que requests manda por padrao ao montar querystring via `params`)
    filtro = f"Indicador eq '{indicador}' and DataReferencia eq '{ano}' and baseCalculo eq {base_calculo}"
    query = (
        f"$filter={quote(filtro, safe=chr(39))}"
        "&$orderby=" + quote("Data desc")
        + "&$top=1&$format=json"
    )
    url = f"{_FOCUS_BASE}?{query}"
    r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    valores = r.json().get("value", [])
    if not valores:
        return None
    v = valores[0]
    return {
        "ano_referencia": ano,
        "mediana_pct": float(v["Mediana"]),
        "media_pct": float(v["Media"]),
        "numero_respondentes": int(v["numeroRespondentes"]),
        "data_calculo": pd.to_datetime(v["Data"]).tz_localize(TZ),
    }


def _focus_multi_ano(indicador: str, quantidade_anos: int = 3) -> pd.DataFrame | None:
    ano_atual = datetime.now(TZ).year
    linhas = []
    anos_com_erro = []
    for ano in range(ano_atual, ano_atual + quantidade_anos):
        try:
            linha = _focus_anual(indicador, ano)
        except Exception as e:
            # Isola falha por ano: dados validos dos outros anos continuam
            # disponiveis, mas a coleta precisa sinalizar que ficou parcial.
            anos_com_erro.append(f"{ano}: {str(e)[:120]}")
            continue
        if linha is not None:
            linhas.append(linha)
    if not linhas:
        return None
    df = pd.DataFrame(linhas)
    df.attrs["coleta_parcial"] = bool(anos_com_erro)
    df.attrs["erro_coleta"] = "; ".join(anos_com_erro)[:300] if anos_com_erro else None
    return df


@st.cache_data(ttl=_TTL_SERIES, show_spinner="atualizando indicadores macro…")
def obter_focus_ipca() -> pd.DataFrame | None:
    """Expectativa de mercado (Focus/BC) pra IPCA do ano corrente e dos
    dois seguintes: mediana, media e numero de respondentes. None se a
    consulta falhar ou nao vier nenhum dado."""
    # registro de SAUDE DOS DADOS - mesmo motivo/padrao de
    # obter_selic_meta/obter_cdi acima. _focus_multi_ano ja isola por
    # ano (nunca lanca excecao - ver seu docstring/comentario), entao
    # None aqui so' pode significar "nenhum dos 3 anos teve dado valido".
    df = _focus_multi_ano("IPCA")
    if df is None:
        registrar_tentativa("MACRO (BCB - Focus IPCA)", "Banco Central (Olinda/Expectativas)",
                             execucao_ok=False, erro="nenhum dos 3 anos teve dado valido", categoria="Macro")
    else:
        parcial = bool(df.attrs.get("coleta_parcial", False))
        registrar_tentativa("MACRO (BCB - Focus IPCA)", "Banco Central (Olinda/Expectativas)",
                             execucao_ok=True, registros_novos=len(df), categoria="Macro",
                             parcial=parcial, erro=df.attrs.get("erro_coleta"))
    return df


@st.cache_data(ttl=_TTL_SERIES, show_spinner="atualizando indicadores macro…")
def obter_focus_selic() -> pd.DataFrame | None:
    """Expectativa de mercado (Focus/BC) pra Selic (fim de periodo) do ano
    corrente e dos dois seguintes. None se a consulta falhar ou nao vier
    dado."""
    df = _focus_multi_ano("Selic")
    if df is None:
        registrar_tentativa("MACRO (BCB - Focus Selic)", "Banco Central (Olinda/Expectativas)",
                             execucao_ok=False, erro="nenhum dos 3 anos teve dado valido", categoria="Macro")
    else:
        parcial = bool(df.attrs.get("coleta_parcial", False))
        registrar_tentativa("MACRO (BCB - Focus Selic)", "Banco Central (Olinda/Expectativas)",
                             execucao_ok=True, registros_novos=len(df), categoria="Macro",
                             parcial=parcial, erro=df.attrs.get("erro_coleta"))
    return df


def _numero_br(txt: str) -> float:
    """Converte '1.260' (milhar) ou '13,3917' (decimal) no formato da
    ANBIMA pra float."""
    return float(txt.strip().replace(".", "").replace(",", "."))


def _buscar_ettj_anbima(dt_ref: str) -> str:
    """POST no form real da ANBIMA (CZ.asp -> CZ-down.asp). dt_ref vazio
    devolve a curva mais recente publicada; caso contrario, formato
    DDMMYYYY (testado manualmente - e o unico que o form aceita, YYYYMMDD
    da erro 500)."""
    headers = {**_HEADERS, "Referer": "https://www.anbima.com.br/informacoes/est-termo/CZ.asp"}
    r = requests.post(
        _ANBIMA_ETTJ_URL, headers=headers, timeout=_TIMEOUT,
        data={"Dt_Ref": dt_ref, "Idioma": "PT", "saida": "csv"},
    )
    r.raise_for_status()
    r.encoding = "iso-8859-1"
    return r.text


def _parse_ettj_anbima(texto: str) -> pd.DataFrame:
    linhas = texto.splitlines()
    if not linhas or not linhas[0].strip():
        raise ValueError("resposta vazia (provavelmente dia sem pregao/publicacao)")

    data_referencia = pd.to_datetime(linhas[0].split(";")[0], format="%d/%m/%Y", dayfirst=True).tz_localize(TZ)

    inicio = next(i for i, l in enumerate(linhas) if l.startswith("PREFIXADOS (CIRCULAR"))
    fim = next(i for i in range(inicio + 2, len(linhas)) if not linhas[i].strip())

    registros = []
    for linha in linhas[inicio + 2 : fim]:
        dias_str, taxa_str = linha.split(";")
        registros.append({
            "dias_uteis": int(dias_str.replace(".", "")),
            "taxa_aa_pct": _numero_br(taxa_str),
            "data_referencia": data_referencia,
        })
    if not registros:
        raise ValueError("bloco PREFIXADOS sem vertices")
    return pd.DataFrame(registros)


@st.cache_data(ttl=_TTL_CURVA, show_spinner="atualizando curva de juros…")
def obter_curva_pre(data_referencia: date | None = None) -> pd.DataFrame | None:
    """Curva de juros prefixada (dias uteis x taxa % a.a.), fonte ANBIMA ETTJ
    (bloco 'PREFIXADOS - CIRCULAR 3.361'), com poucos vertices padronizados.

    Optamos pela ANBIMA em vez das taxas referenciais DI x Pre da B3: o
    servico legado da B3 (www2.bmf.com.br/.../lum-taxas-referenciais-bmf)
    esta retornando erro ('Unspecified error') de forma consistente,
    independente da data pedida - parece descontinuado. A curva prefixada
    da ANBIMA e a proxy oficial mais usada no mercado pra curva de juros
    domestica quando a fonte direta da B3 nao esta disponivel, e o endpoint
    responde de forma estavel em CSV simples, sem JS/autenticacao.

    O form real (CZ.asp) confirma, testado na pratica, que aceita data de
    referencia passada via POST (campo Dt_Ref, formato DDMMYYYY - e o unico
    formato aceito, YYYYMMDD da erro 500). Se 'data_referencia' cair num dia
    sem publicacao (fim de semana/feriado), tenta ate 6 dias corridos pra
    tras ate achar o ultimo pregao.

    IMPORTANTE (descoberto testando): esse endpoint so mantem uma janela
    'rolante' de ~5-6 pregoes (mais ou menos 1 semana util) de historico -
    datas mais antigas que isso vem vazias, mesmo sendo dia util. Ou seja,
    'ha 1 semana' funciona, mas 'ha 1 mes' normalmente retorna None por
    estar fora dessa janela. Nao ha (testado) outro parametro nesse form pra
    pedir historico mais longo; pra isso seria preciso outra fonte (ex.
    arquivo historico da propria ANBIMA, fora do escopo desta funcao).

    Retorna colunas [dias_uteis, taxa_aa_pct, data_referencia]. None se a
    fonte falhar, nao publicar em nenhum dos dias tentados, ou o formato
    mudar."""
    try:
        if data_referencia is None:
            df = _parse_ettj_anbima(_buscar_ettj_anbima(""))
        else:
            df = None
            for volta in range(7):
                dia = data_referencia - timedelta(days=volta)
                texto = _buscar_ettj_anbima(dia.strftime("%d%m%Y"))
                if not texto.strip():
                    continue
                try:
                    df = _parse_ettj_anbima(texto)
                except Exception:
                    # bug real corrigido (auditoria 2026-10-10): resposta
                    # NAO-vazia mas malformada so' PRA ESSE dia (layout
                    # mudou, mensagem de erro/manutencao no lugar do CSV)
                    # lancava StopIteration/ValueError que escapava do
                    # loop inteiro (so' havia o try/except externo),
                    # abortando a tentativa nos outros 6 dias mesmo que
                    # algum deles tivesse publicacao valida - contradizia
                    # o proprio docstring ("tenta ate 6 dias corridos pra
                    # tras ate achar o ultimo pregao"). Agora so' pula pro
                    # dia anterior.
                    continue
                break
            if df is None:
                raise ValueError(f"sem publicacao da ANBIMA nos 7 dias antes de {data_referencia}")
        registrar_tentativa("MACRO (ANBIMA)", "ANBIMA (ETTJ)", execucao_ok=True,
                             registros_novos=len(df), categoria="Macro")
        return df
    except Exception as e:
        registrar_tentativa("MACRO (ANBIMA)", "ANBIMA (ETTJ)", execucao_ok=False,
                             erro=str(e)[:300], categoria="Macro")
        return None


def obter_cenario_global() -> list:
    """Cenario global (ouro, petroleo Brent/WTI, minerio de ferro,
    Treasuries 10 anos, VIX) - config.CENARIO_GLOBAL, reusando o mesmo
    mecanismo de lote de data/mercado.py:obter_mercados_globais (todos os
    symbols ja vem no formato exato que o yfinance espera, sem sufixo
    '.SA'). [] se o lote falhar."""
    # registro de SAUDE DOS DADOS (achado real, auditoria missao
    # coletores 2026-10-13, continuacao): _baixar_lote_bruto nunca
    # registrava nada - esta funcao e data/mercado.py:
    # obter_mercados_globais sao os 2 unicos call-sites, nenhum
    # instrumentado antes desta correcao.
    nomes = list(CENARIO_GLOBAL.keys())
    symbols = tuple(CENARIO_GLOBAL.values())
    df = _baixar_lote_bruto(symbols)
    if df is None:
        registrar_tentativa("MACRO (Cenário Global)", "yfinance (ouro/petróleo/minério/Treasuries/VIX)",
                             execucao_ok=False, erro="yf.download retornou vazio (2 tentativas)", categoria="Macro")
        return []
    resultado = []
    for nome, symbol in zip(nomes, symbols):
        linha = _linha_papel(df, nome, symbol)
        if linha:
            resultado.append({"nome": nome, "preco": linha["preco"], "variacao_pct": linha["variacao_pct"]})
    fonte = "yfinance (ouro/petróleo/minério/Treasuries/VIX)"
    nome_coletor = "MACRO (Cenário Global)"
    ausentes = [nome for nome, symbol in zip(nomes, symbols)
                if not _linha_papel(df, nome, symbol)]
    if not resultado:
        registrar_tentativa(nome_coletor, fonte, execucao_ok=False,
                             erro="Lote retornou dados, mas nenhum ativo global pôde ser interpretado",
                             registros_novos=0, categoria="Macro")
        return []
    if ausentes:
        registrar_tentativa(nome_coletor, fonte, execucao_ok=True, parcial=True,
                             erro="Ativos sem dados: " + ", ".join(ausentes),
                             registros_novos=len(resultado), categoria="Macro")
    else:
        registrar_tentativa(nome_coletor, fonte, execucao_ok=True,
                             registros_novos=len(resultado), categoria="Macro")
    return resultado
