# -*- coding: utf-8 -*-
"""Documentos oficiais da CVM (fato relevante, comunicado ao mercado,
aviso aos acionistas/proventos, calendario de eventos corporativos) via
dados abertos da CVM - fase CVM.

--- Fonte escolhida e por que -----------------------------------------

dados.cvm.gov.br (arquivos IPE/FCA em CSV, formato documentado) em vez
de scraping direto do RAD/ENET (rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx).

RAD/ENET e' o sistema onde as companhias protocolam de verdade (teria
defasagem zero, e' a fonte primaria), mas e' uma pagina ASP.NET WebForms
classica: consulta por __VIEWSTATE/postback, sem endpoint JSON publico.
Da' pra automatizar, mas e' fragil (quebra a cada mudanca de layout da
CVM) e complexo pra manter sozinho. dados.cvm.gov.br publica os MESMOS
registros extraidos desses protocolos, em CSV estavel (mesmo link de
download direto pro documento original no proprio RAD) - resolve o
essencial ("documento oficial + link") sem o risco de scraping de
formulario.

--- Defasagem real (testado nesta sessao, 23/09/2026) ------------------

A CVM declara periodicidade "Semanal" pro dataset IPE (pagina do
dataset em dados.cvm.gov.br/dataset/cia_aberta-doc-ipe). Na pratica, o
arquivo do ano corrente e' atualizado quase todo dia util: testando ao
vivo, a "ultima atualizacao" e as linhas mais recentes do CSV eram de
2-3 dias atras. Ou seja: pior caso contratual ~7 dias, caso tipico
observado ~1-3 dias. E' bem mais lento que "imediato" (a propria
exigencia legal pra Fato Relevante, Instrucao CVM 358), mas aceitavel
pra um terminal pessoal que ja assume cotacao com atraso de ~15min
(yfinance) - a interface deixa isso explicito, mesmo padrao do aviso de
atraso da cotacao em app.py.

Se um dia a defasagem incomodar, o proximo passo seria portar isso pro
COLETOR LOCAL (fora do Streamlit Cloud) com scraping do RAD/ENET de
verdade - fica pra depois, nao e' o escopo desta fase.

--- Dados usados --------------------------------------------------------

- CAD (cadastro de companhias): tem CNPJ e Codigo_CVM, mas NAO tem o
  codigo de negociacao da B3 (ticker) - e' registro na CVM, nao na bolsa.
- FCA (Formulario Cadastral), sub-arquivo "valor_mobiliario": tem
  Codigo_Negociacao (ex: 'PETR4') ligado ao CNPJ_Companhia - essa e' a
  fonte real do mapa ticker->CNPJ (usar CAD pra isso nao funcionaria).
- IPE (Informe Periodico e Eventual): um registro por documento
  protocolado, com Categoria/Tipo/Especie/Assunto/Data_Entrega/
  Link_Download. Categoria bate quase literalmente com o que foi pedido:
  'Fato Relevante', 'Comunicado ao Mercado', 'Aviso aos Acionistas',
  'Relatorio Proventos' e ate 'Calendario de Eventos Corporativos' ja
  existem como categorias oficiais da CVM - ver _CATEGORIAS_RELEVANTES.
"""

import io
import re
import unicodedata
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from data.research import store

_TZ_SP = ZoneInfo("America/Sao_Paulo")
_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 30

_URL_FCA = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
_URL_IPE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"

_TTL_MAPA_TICKER = 24 * 60 * 60  # 24h - cadastro de valores mobiliarios muda raramente
_TTL_DOCUMENTOS = 6 * 60 * 60    # 6h - fonte atualiza ~1x/dia util, nao ha ganho em checar mais que isso

RETENCAO_DIAS = 5  # feed "vivo" (cvm_documentos) - nao guarda historico, ver apagar_documentos_antigos

# Categoria oficial da CVM (coluna 'Categoria' do IPE) -> codigo interno
# usado na interface. So essas entram no feed - o IPE tem dezenas de
# outras categorias (Assembleia, Demonstracoes Financeiras, Estatuto
# Social, politicas internas etc.) fora do escopo desta fase.
_CATEGORIAS_RELEVANTES = {
    "Fato Relevante": "FATO_RELEVANTE",
    "Comunicado ao Mercado": "COMUNICADO",
    "Aviso aos Acionistas": "PROVENTOS",
    "Relatório Proventos": "PROVENTOS",
    "Calendário de Eventos Corporativos": "CALENDARIO",
    "Dados Econômico-Financeiros": "RESULTADOS",
}

# a categoria "Dados Economico-Financeiros" e' bem mais ampla que so'
# resultado trimestral/anual (tem relatorio de agente fiduciario,
# relatorio de agencia de rating, laudo de avaliacao etc. - confirmado
# checando os valores reais da coluna "Tipo" no CSV de 2026) - so' esses
# "Tipo" especificos contam como resultado financeiro de verdade pro
# painel RESULTADOS; o resto da categoria fica de fora
_TIPOS_RESULTADOS = {
    "Demonstrações Financeiras Intermediárias",
    "Demonstrações Financeiras Anuais Completas",
    "Demonstrações Financeiras Adicionais",
    "Press-release",
}

TIPO_LABEL = {
    "FATO_RELEVANTE": "FATO RELEVANTE",
    "COMUNICADO": "COMUNICADO",
    "PROVENTOS": "PROVENTOS",
    "CALENDARIO": "CALENDÁRIO",
    "RESULTADOS": "RESULTADOS",
}

# so esses tipos "confirmam" noticia (ver documento_confirmador) - aviso
# de proventos/calendario nao tem o formato de "confirmar um fato" que
# uma noticia relataria
_TIPOS_CONFIRMADORES = {"FATO_RELEVANTE", "COMUNICADO"}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokenizar(texto: str) -> set:
    palavras = re.findall(r"[a-z0-9]+", _sem_acento(texto))
    return {p for p in palavras if len(p) >= 3}


def _baixar_csv_do_zip(url: str, nome_no_zip: str):
    """Baixa um zip de dados abertos da CVM e le o CSV de dentro (';' +
    latin1, padrao desses arquivos). None se a fonte falhar ou o arquivo
    nao existir (ex: ano ainda sem FCA publicado) - nunca inventa dado."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open(nome_no_zip) as f:
            return pd.read_csv(f, sep=";", encoding="latin1")
    except Exception:
        return None


@st.cache_data(ttl=_TTL_MAPA_TICKER, show_spinner=False)
def _mapa_ticker_cnpj() -> dict:
    """{ticker: cnpj}, construido a partir do FCA (Formulario Cadastral)
    - unica fonte da CVM que liga o codigo de negociacao da B3 ao CNPJ.
    Tenta o ano corrente; se vier vazio (ex: dias de janeiro antes da
    empresa refazer o FCA do ano novo), cai pro ano anterior."""
    ano = datetime.now(_TZ_SP).year
    for tentativa in (ano, ano - 1):
        df = _baixar_csv_do_zip(
            _URL_FCA.format(ano=tentativa),
            f"fca_cia_aberta_valor_mobiliario_{tentativa}.csv",
        )
        if df is None or df.empty:
            continue
        df = df.dropna(subset=["Codigo_Negociacao"])
        if not df.empty:
            return dict(zip(df["Codigo_Negociacao"].str.strip(), df["CNPJ_Companhia"].str.strip()))
    return {}


def testar_conexao() -> tuple:
    """So' testa se o IPE do ano corrente baixa e tem linhas - usado pelo
    painel DIAGNOSTICO DE FONTES. Retorna (ok, detalhe)."""
    ano = datetime.now(_TZ_SP).year
    df = _ipe_ano(ano)
    if df is None or df.empty:
        return False, "download do IPE falhou ou veio vazio"
    return True, f"OK ({len(df)} linhas no IPE de {ano})"


def obter_cnpj(ticker: str):
    """CNPJ do ticker (ver _mapa_ticker_cnpj), ou None se nao encontrado
    (ticker novo demais, BDR, ou fora do cadastro de valores mobiliarios)."""
    return _mapa_ticker_cnpj().get(ticker.upper())


@st.cache_data(ttl=_TTL_DOCUMENTOS, show_spinner=False)
def _ipe_ano(ano: int):
    """DataFrame bruto do IPE de um ano inteiro (~30-40 mil linhas, todas
    as companhias), so' com as colunas usadas. None se a fonte falhar.
    Cacheado por ano - baixado uma vez e reaproveitado pra qualquer
    ticker (filtrar em memoria e' muito mais barato que uma requisicao
    por empresa)."""
    df = _baixar_csv_do_zip(_URL_IPE.format(ano=ano), f"ipe_cia_aberta_{ano}.csv")
    if df is None:
        return None
    colunas = [
        "CNPJ_Companhia", "Categoria", "Tipo", "Especie", "Assunto",
        "Data_Referencia", "Data_Entrega", "Link_Download",
    ]
    return df[[c for c in colunas if c in df.columns]]


def _parse_data(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").replace(tzinfo=_TZ_SP)
    except Exception:
        return None


def _limpar_texto(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    # o Assunto as vezes concatena varios itens separados por '||'
    # (visto na pratica, ex: reapresentacoes com mais de um motivo)
    texto = str(valor).replace("||", " · ").strip()
    return texto or None


def _documentos_brutos(cnpj: str):
    """Linhas do IPE (ano corrente + anterior, pra nao perder documentos
    de dezembro na virada do ano) do CNPJ dado, ja filtradas pelas
    categorias relevantes. None se as duas tentativas de fonte falharem;
    [] se pelo menos uma respondeu mas nao achou nada pro CNPJ."""
    ano = datetime.now(_TZ_SP).year
    partes = []
    alguma_ok = False
    for tentativa in (ano, ano - 1):
        df = _ipe_ano(tentativa)
        if df is None:
            continue
        alguma_ok = True
        sub = df[(df["CNPJ_Companhia"] == cnpj) & (df["Categoria"].isin(_CATEGORIAS_RELEVANTES))]
        # dentro de "Dados Economico-Financeiros", filtra so' os Tipo que
        # sao resultado de verdade (ver _TIPOS_RESULTADOS) - as outras
        # categorias nao tem esse problema de granularidade
        eh_resultados = sub["Categoria"] == "Dados Econômico-Financeiros"
        sub = sub[~eh_resultados | sub["Tipo"].isin(_TIPOS_RESULTADOS)]
        if not sub.empty:
            partes.append(sub)
    if not alguma_ok:
        return None
    if not partes:
        return []
    return pd.concat(partes).to_dict("records")


def obter_documentos_cvm(ticker: str):
    """Documentos oficiais recentes (fato relevante, comunicado ao
    mercado, proventos, calendario) de um ticker. None se a fonte
    falhar; [] se respondeu mas o ticker nao tem CNPJ mapeado ou nao ha
    documento algum. Cada item: {ticker, tipo, tipo_label,
    categoria_original, assunto, data (isoformat), data_referencia,
    link, destaque (bool - True so' pra Fato Relevante)}."""
    cnpj = obter_cnpj(ticker)
    if not cnpj:
        return []
    brutos = _documentos_brutos(cnpj)
    if brutos is None:
        return None

    resultado = []
    for linha in brutos:
        data_entrega = _parse_data(linha.get("Data_Entrega"))
        if data_entrega is None:
            continue
        tipo = _CATEGORIAS_RELEVANTES[linha["Categoria"]]
        resultado.append({
            "ticker": ticker,
            "tipo": tipo,
            "tipo_label": TIPO_LABEL[tipo],
            "categoria_original": linha["Categoria"],
            "assunto": _limpar_texto(linha.get("Assunto")) or _limpar_texto(linha.get("Tipo")) or linha["Categoria"],
            "data": data_entrega.isoformat(),
            "data_referencia": linha.get("Data_Referencia"),
            "link": linha["Link_Download"],
            "destaque": tipo == "FATO_RELEVANTE",
        })
    resultado.sort(key=lambda d: d["data"], reverse=True)
    return resultado


def obter_documentos_watchlist(tickers: list) -> tuple:
    """Agrega obter_documentos_cvm de varios tickers. Retorna (documentos,
    falhas). Ao final de uma coleta com sucesso, grava no Supabase (ver
    salvar_documentos) - efeito colateral deliberado aqui (e' o ponto
    natural em que a watchlist inteira acabou de ser coletada de verdade,
    sem gravar 1x por ticker isolado toda vez que o painel da EQUITY for
    aberto). NAO chama apagar_documentos_antigos aqui: agora que
    documentos CVM ficam na mesma tabela research_itens (ver comentario
    em salvar_documentos), a limpeza ja' e' feita pelo mecanismo
    throttled de data/research/__init__.py:coletar_pendentes (1x/hora) -
    chamar de novo aqui bateria no banco a cada render da EQUITY, sem
    gate nenhum."""
    todos = []
    falhas = []
    for ticker in tickers:
        docs = obter_documentos_cvm(ticker)
        if docs is None:
            falhas.append(ticker)
            continue
        todos.extend(docs)
    todos.sort(key=lambda d: d["data"], reverse=True)
    if todos:
        salvar_documentos(todos)
    return todos, falhas


def documento_confirmador(ticker: str, titulo: str, data_iso: str):
    """Pro selo CONFIRMADA das noticias (data/news.py chama isso): procura
    um Fato Relevante ou Comunicado ao Mercado do mesmo ticker, com
    assunto parecido com o titulo da noticia (sobreposicao de palavras,
    mesmo principio do agrupamento de noticias - sem IA, deterministico)
    e distancia de ate 2 dias da data da noticia. Retorna
    {tipo_label, assunto, data, link} do melhor documento encontrado, ou
    None se nao achar nada (fonte fora do ar tambem retorna None aqui -
    "nao confirmado" e' o padrao seguro, nunca inventar confirmacao)."""
    docs = obter_documentos_cvm(ticker)
    if not docs:
        return None
    try:
        data_noticia = datetime.fromisoformat(data_iso)
    except Exception:
        return None

    tokens_noticia = _tokenizar(titulo)
    if not tokens_noticia:
        return None

    melhor = None
    for doc in docs:
        if doc["tipo"] not in _TIPOS_CONFIRMADORES:
            continue
        try:
            data_doc = datetime.fromisoformat(doc["data"])
        except Exception:
            continue
        if abs((data_noticia.date() - data_doc.date()).days) > 2:
            continue
        tokens_doc = _tokenizar(doc["assunto"])
        if not tokens_doc:
            continue
        sobreposicao = len(tokens_noticia & tokens_doc) / min(len(tokens_noticia), len(tokens_doc))
        if sobreposicao >= 0.4 and (melhor is None or sobreposicao > melhor[0]):
            melhor = (sobreposicao, doc)

    if melhor is None:
        return None
    _, doc = melhor
    return {"tipo_label": doc["tipo_label"], "assunto": doc["assunto"], "data": doc["data"], "link": doc["link"]}


# --- Persistencia no Supabase ---------------------------------------------
# Reusa a tabela research_itens (ver data/research/store.py, sql/research.sql)
# em vez de criar uma tabela cvm_documentos nova - decisao explicita (nao
# criar tabela nova no Supabase pra esta fase). O schema de research_itens
# ja cobre tudo que um documento CVM precisa (link/titulo/data/tipo/
# tickers/resumo), so' "casa" vira o marcador fixo "CVM" pra distinguir
# desses itens dos relatorios de research de verdade.
_CASA_CVM = "CVM"


def salvar_documentos(documentos: list) -> bool:
    """Converte pro formato de data/research/store.salvar_itens (upsert
    em lote por link, mesmo mecanismo dos outros coletores de research)."""
    if not documentos:
        return True
    itens = [
        {
            "link": d["link"], "casa": _CASA_CVM, "titulo": d["assunto"],
            "data": d["data"][:10] if d.get("data") else "",
            "autor": "", "tipo": d["tipo"], "tickers": [d["ticker"]],
        }
        for d in documentos
    ]
    return store.salvar_itens(itens)


def apagar_documentos_antigos(dias: int = RETENCAO_DIAS) -> int:
    """Retencao dos documentos CVM salvos - delega pro mesmo mecanismo
    generico de data/research/store.apagar_itens_antigos (opera sobre
    TODA research_itens, nao so' CVM, mas o criterio - 'data'/'coletado_em'
    velhos - e' o mesmo que faria sentido aqui; nao vale duplicar a
    logica so' pra filtrar por casa)."""
    return store.apagar_itens_antigos(dias)


# --- Resumo por IA (Groq, sob demanda) ------------------------------------

_MODELO_GROQ_CVM = "openai/gpt-oss-20b"
_TTL_RESUMO = 24 * 60 * 60  # 24h em memoria (st.cache_data), mesmo padrao de data/news.py

_PROMPT_SISTEMA_CVM = (
    "Voce resume documentos oficiais da CVM (fatos relevantes, comunicados "
    "ao mercado, avisos aos acionistas) em portugues, em no maximo 4 linhas "
    "curtas, SEMPRE com suas proprias palavras - nunca copie frases literais "
    "do documento. Va direto ao fato ou comunicado, sem introducoes como "
    "'a empresa comunica que'. O texto foi extraido automaticamente de um "
    "PDF e pode ter formatacao quebrada - ignore ruido de layout. Se nao "
    "houver conteudo suficiente pra resumir, responda exatamente: SEM_CONTEUDO"
)


def _extrair_texto_pdf(conteudo: bytes):
    try:
        import pypdf
    except ImportError:
        return None
    try:
        leitor = pypdf.PdfReader(io.BytesIO(conteudo))
        paginas = [p.extract_text() or "" for p in leitor.pages[:10]]
        texto = "\n".join(paginas).strip()
        return texto or None
    except Exception:
        return None


def _baixar_texto_documento(link: str) -> tuple:
    """Baixa o documento (PDF na pratica - confirmado testando o
    Link_Download real do IPE, apesar do Content-Type as vezes vir
    'text/html') e extrai o texto. Retorna (texto, motivo_falha)."""
    try:
        r = requests.get(link, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        return None, f"erro ao baixar: {e}"
    texto = _extrair_texto_pdf(r.content)
    if not texto or len(texto) < 200:
        return None, "conteúdo muito curto (PDF protegido/escaneado ou formato inesperado)"
    return texto, None


def _resumir_com_groq(texto: str, assunto: str) -> tuple:
    try:
        chave = st.secrets["groq"]["api_key"]
    except Exception:
        return None, "GROQ_API_KEY não configurada em st.secrets"

    texto_truncado = texto[:8000]
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": _MODELO_GROQ_CVM,
                "messages": [
                    {"role": "system", "content": _PROMPT_SISTEMA_CVM},
                    {"role": "user", "content": f"Assunto: {assunto}\n\nTexto do documento:\n{texto_truncado}"},
                ],
                "temperature": 0.2,
                "max_tokens": 400,
                "reasoning_effort": "low",
            },
            timeout=30,
        )
        if r.status_code == 429:
            return None, "cota"
        r.raise_for_status()
        resumo = r.json()["choices"][0]["message"]["content"].strip()
        if resumo == "SEM_CONTEUDO":
            return None, "conteúdo insuficiente pra resumir"
        return resumo, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=_TTL_RESUMO, show_spinner=False)
def obter_resumo_documento(link: str, assunto: str) -> dict:
    """Resumo de um documento CVM - baixa+extrai+resume via Groq, sempre
    em palavras proprias. Sob demanda (chamado so' quando o usuario abre
    o card), nunca automatico. Retorna {resumo, motivo_indisponivel};
    resumo=None se qualquer etapa falhar - nunca inventa conteudo."""
    texto, motivo = _baixar_texto_documento(link)
    if texto is None:
        return {"resumo": None, "motivo_indisponivel": motivo}
    resumo, motivo_groq = _resumir_com_groq(texto, assunto)
    if resumo is None:
        return {"resumo": None, "motivo_indisponivel": motivo_groq}
    return {"resumo": resumo, "motivo_indisponivel": None}
