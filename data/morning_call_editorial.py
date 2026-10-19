# -*- coding: utf-8 -*-
"""Camada de preparação editorial do Morning Call em PDF.

Monta uma estrutura de dados pura (dict), sem nenhum import de biblioteca
de PDF/gráfico - jobs/morning_call_pdf.py (camada de apresentação,
ReportLab) consome o dict devolvido por montar_edicao() e nunca chama
provedor nenhum diretamente. Separação exigida pela missão: dados !=
layout, cada camada testável sem a outra (sem rede em teste de nenhuma
das duas).

Reaproveita os MESMOS provedores que jobs/morning_call.py já usa
(data/prices.py, data/macro.py, data/news.py, data/eventos.py) - nunca
reconsulta nem reformula um número/fato com regra própria diferente da
do e-mail em texto simples (mesma fonte única de verdade).

Separação fato/comentário: o jornal publica só FATO com fonte (cotação,
indicador, matéria com veículo e link; o texto vem do bloco RESUMO do
resumo já cacheado, nunca da LEITURA DE MERCADO do modelo). ACOMPANHAR
marca evento futuro da agenda. As 3 "interpretações" genéricas fixas que
saíam em toda edição foram retiradas (eram iguais todo dia - enchimento,
não informação).
"""
import re
import unicodedata
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import config
from data.eventos import (
    PRIORIDADE_STATUS, STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado,
)
from data.macro import (
    motivo_indisponivel, obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta,
    obter_selic_meta_copom,
)
from data.news import (
    obter_resumos_prontos, obter_top_mercado, obter_top_mercado_internacional, separar_secoes_resumo,
)
from data.news import eh_fonte_confiavel
from data.prices import obter_cotacao_indice, obter_historico
from data.radar_setorial import montar_radar

TZ_SP = ZoneInfo("America/Sao_Paulo")

TAG_FATO = "FATO"
TAG_ACOMPANHAR = "ACOMPANHAR"

_NOTA_STATUS_EVENTO = {
    STATUS_PRAZO_CVM: "prazo MÁXIMO regulatório da CVM (Instrução CVM 480/2009) — não é data anunciada pela empresa.",
    STATUS_CONFIRMADO: "data CONFIRMADA pela própria empresa/fonte oficial.",
    STATUS_ESTIMADO: "data ESTIMADA por fonte externa — ainda não confirmada pela empresa.",
}

LIMITACOES_PADRAO = (
    "Fontes gratuitas podem ter atraso e indisponibilidade; esta edição "
    "não garante cotação em tempo real.",
    "Não foram incluídos preços ou fatos que não puderam ser confirmados "
    "nesta execução.",
    "A agenda lista eventos previstos, não resultados já divulgados.",
    "Conteúdo informativo, não constitui recomendação de investimento.",
)

FONTES_PADRAO = (
    "Cotações: Yahoo Finance (yfinance) — dados podem ter atraso conforme o provedor.",
    "Indicadores macro: Banco Central do Brasil (Selic/CDI) e Boletim Focus (BCB).",
    "Agenda de resultados: CVM (Instrução CVM 480/2009) — ver nota de confiabilidade em cada evento.",
    "Notícias: Google News (agregador); veículo original e link em cada manchete.",
)


def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def brt_label(iso_str):
    """Converte um ISO 8601 com fuso (de hist.index[-1].isoformat(), que
    vem no fuso LOCAL DA FONTE/bolsa - ex: Nova York pra futuros dos EUA,
    São Paulo pro Ibovespa) pra um rótulo SEMPRE em horário de Brasília,
    explícito ('horário de Brasília') - causa real do sintoma relatado
    ("barras de datas e fusos diferentes", relatório de 17/10/2026): cada
    índice aparecia com o horário/fuso CRU da própria fonte, nunca
    convertido pra um fuso comum, então duas linhas lado a lado pareciam
    inconsistentes mesmo as duas estando corretas na sua própria fonte.

    Usa datetime.fromisoformat (nunca aritmética manual de offset) +
    .astimezone(TZ_SP) - única forma correta de converter um ISO com
    offset/zoneinfo próprio pra outro fuso (ver ZoneInfo, nunca
    timedelta fixo: alguns fusos de origem observam horário de verão,
    BRT não desde 2019 - um deslocamento fixo erraria o resultado em
    parte do ano)."""
    if not iso_str:
        return "indisponível"
    try:
        momento = datetime.fromisoformat(iso_str)
        if momento.tzinfo is None:
            return str(iso_str)
        return momento.astimezone(TZ_SP).strftime("%d/%m %H:%M") + " (horário de Brasília)"
    except (TypeError, ValueError):
        return str(iso_str)


def _referencia_cotacao(cot):
    """Rótulo de referência de uma cotação + data da sessão (date).

    Causa dos horários '16/10 00:00', '16/10 01:00' e '17/10 20:00' na
    edição de 18/10/2026: _barra_em é o índice da barra DIÁRIA do Yahoo,
    que fica sempre à meia-noite no fuso da bolsa (São Paulo, Nova York,
    Londres no câmbio) - convertida para Brasília virava um 'horário' que
    não é de negócio nenhum. Agora: com o horário do último negócio da
    fonte (regularMarketTime, mesmo dia da barra) mostra esse horário em
    Brasília; sem ele, só 'fech. dd/mm' da sessão - nunca um horário
    inventado. A data da sessão é a do fuso da própria bolsa."""
    sessao = None
    try:
        barra = datetime.fromisoformat(cot.get("_barra_em"))
        sessao = barra.date()
    except (TypeError, ValueError):
        barra = None
    negocio = cot.get("_negocio_em")
    if negocio:
        rotulo = brt_label(negocio)
    elif sessao:
        rotulo = f"fech. {sessao.strftime('%d/%m')}"
    else:
        rotulo = None
    if rotulo and cot.get("_fallback_cache"):
        rotulo += " (cache)"
    return rotulo, sessao


def _indicador(nome, ticker):
    """Mesma leitura 1x de data/prices.py:obter_cotacao_indice usada pelo
    e-mail em texto simples - nunca um valor novo/recalculado aqui."""
    cot = obter_cotacao_indice(nome, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        erro = cot.get("erro", "sem dado") if isinstance(cot, dict) else "sem dado"
        return {"nome": nome, "preco": None, "variacao_pct": None, "barra_fmt": None, "sessao": None,
                "erro": erro}
    rotulo, sessao = _referencia_cotacao(cot)
    return {
        "nome": nome,
        "preco": cot.get("preco"),
        "variacao_pct": cot.get("variacao_pct"),
        "barra_fmt": rotulo,
        "sessao": sessao,
        "erro": None,
    }


_DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
                "sábado", "domingo")


def nota_sessao(indicadores, agora):
    """Aviso quando as cotações vêm de uma sessão anterior ao dia da
    edição (fim de semana, feriado, antes da abertura): a 'variação' é a
    da última sessão, não a de hoje. None quando todas são de hoje."""
    sessoes = [i.get("sessao") for i in indicadores if i.get("sessao")]
    if not sessoes:
        return None
    ultima = max(sessoes)
    if ultima >= agora.date():
        return None
    texto = (f"Cotações e variações referem-se à última sessão disponível "
             f"({_DIAS_SEMANA[ultima.weekday()]}, {ultima.strftime('%d/%m')}), "
             f"comparada com a sessão anterior")
    if agora.weekday() >= 5:
        texto += "; não há pregão no fim de semana"
    return texto + "."


def sessao_mercado(indicadores):
    """Data (date) da sessão de mercado que a edição mostra - a do
    primeiro indicador com sessão conhecida (Ibovespa vem primeiro), ou
    None quando nenhuma cotação saiu. O masthead mostra essa data
    separada do horário de geração: domingo à tarde a edição é 'gerada
    dom 18/10, 14h59' mas os mercados são o fechamento de sex 16/10."""
    for indicador in indicadores or []:
        if indicador and indicador.get("sessao"):
            return indicador["sessao"]
    return None


def _serie_fechamento(ticker, periodo_label="1M"):
    """Série (data, close) pro mini-gráfico de página - None/lista vazia
    em qualquer falha (ticker sem histórico, fonte fora do ar) nunca
    propaga exceção pra quem monta a edição; jobs/morning_call_pdf.py
    trata lista vazia como "gráfico indisponível", nunca inventa ponto."""
    try:
        df = obter_historico(ticker, periodo_label)
        if df is None or df.empty:
            return []
        pontos = df[["Data", "Close"]].dropna()
        return [(row["Data"], float(row["Close"])) for _, row in pontos.iterrows()]
    except Exception:
        return []


def _data_br(valor):
    try:
        return pd.Timestamp(valor).strftime("%d/%m/%Y")
    except Exception:
        return None


def _linha_macro(indicador, valor, unidade, referencia, detalhe=None, erro=None):
    """Contrato de uma linha da tabela macro do PDF - valor numérico +
    unidade + referência já legíveis; nunca nome de coluna do DataFrame."""
    return {"indicador": indicador, "valor": valor, "unidade": unidade,
            "referencia": referencia or "—", "detalhe": detalhe, "erro": erro}


def _taxa_plausivel(valor):
    """float da taxa anual (%) só se for número finito entre 0 e 100 -
    qualquer outra coisa (texto, NaN, negativo, absurdo) é tratada como
    dado inválido, nunca publicada como valor."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    if v != v or not (0 < v < 100):
        return None
    return v


_NOME_STATUS_SGS = {"selic": "MACRO (BCB - Selic)", "cdi": "MACRO (BCB - CDI)"}


def ultima_coleta_valida(chave):
    """'dd/mm/aaaa hh:mm' do último sucesso registrado no painel de saúde
    dos dados (data/coletores_status.py, somente leitura) - é o momento em
    que alguma execução do Pregão (app ou job) conseguiu ler a série. O
    VALOR daquela leitura não é guardado, então nunca é exibido. None se
    não houver registro ou o banco estiver fora do ar."""
    try:
        from data.coletores_status import obter_status
        status = obter_status(_NOME_STATUS_SGS[chave]) or {}
        bruto = status.get("ultimo_sucesso_em")
        if not bruto:
            return None
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).astimezone(TZ_SP).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return None


def _macro_rows(agora=None, provedores=None):
    """Linhas da tabela macro do PDF, normalizadas.

    Causa dos defeitos da edição de 18/10/2026 (auditoria): (1) as linhas
    eram montadas com o nome cru das colunas ("mediana pct: 3,79; media
    pct...; numero respondentes...") e o renderer procurava chaves que não
    existem nos dados reais ("valor"/"mediana"), caindo nesse texto bruto;
    (2) o Focus usava dado.iloc[-1], a ÚLTIMA linha da tabela por ano - o
    ano corrente + 2 (2028), não o ano corrente. Agora: Selic meta e CDI
    anualizado com a data da leitura; Focus IPCA e Selic para o ano
    corrente e o seguinte, com a data do boletim; sem dado -> 'indisponível'
    com o motivo (nunca um valor estimado)."""
    agora = agora or datetime.now(TZ_SP)
    provedores = provedores or {}
    selic_fn = provedores.get("selic", obter_selic_meta)
    cdi_fn = provedores.get("cdi", obter_cdi)
    focus_ipca_fn = provedores.get("focus_ipca", obter_focus_ipca)
    focus_selic_fn = provedores.get("focus_selic", obter_focus_selic)
    linhas = []

    copom_fn = provedores.get("selic_copom", obter_selic_meta_copom)

    def _selic_pelo_copom():
        """Plano B oficial da meta Selic (histórico do Copom, bcb.gov.br)."""
        try:
            meta = copom_fn()
        except Exception:
            meta = None
        if not meta or _taxa_plausivel(meta.get("valor")) is None:
            return None
        reuniao = f"{meta['reuniao']}ª reunião do Copom, " if meta.get("reuniao") else "Copom, "
        return _linha_macro("Selic meta", float(meta["valor"]), "% a.a.",
                            f"vigente desde {_data_br(meta.get('vigente_desde'))}",
                            detalhe=f"fonte: {reuniao}histórico oficial em bcb.gov.br (SGS indisponível)")

    def _serie(nome, fn, coluna, chave_motivo):
        try:
            dado = fn()
        except Exception as exc:
            dado = None
            motivo = str(exc)[:200]
        else:
            motivo = None
        if isinstance(dado, pd.DataFrame) and not dado.empty and coluna in dado.columns:
            validos = dado.dropna(subset=[coluna])
            if not validos.empty:
                ultimo = validos.iloc[-1]
                valor = _taxa_plausivel(ultimo[coluna])
                if valor is not None:
                    linhas.append(_linha_macro(nome, valor, "% a.a.", _data_br(ultimo.get("data"))))
                    return
                motivo = motivo or f"valor recebido fora da faixa de uma taxa anual ({ultimo[coluna]!r})"
        if chave_motivo == "selic":
            linha_copom = _selic_pelo_copom()
            if linha_copom:
                linhas.append(linha_copom)
                return
        motivo = motivo or motivo_indisponivel(chave_motivo) or "Banco Central (SGS) sem dado nesta execução"
        if chave_motivo == "selic" and motivo_indisponivel("selic_copom"):
            motivo += f"; {motivo_indisponivel('selic_copom')}"
        ultima = ultima_coleta_valida(chave_motivo)
        if ultima:
            motivo += f"; última coleta válida registrada em {ultima} (horário de Brasília)"
        linhas.append(_linha_macro(nome, None, "% a.a.", None, erro=motivo))

    _serie("Selic meta", selic_fn, "selic_meta_pct", "selic")
    _serie("CDI", cdi_fn, "cdi_anualizado_pct", "cdi")

    for nome, fn in (("Focus IPCA", focus_ipca_fn), ("Focus Selic", focus_selic_fn)):
        try:
            dado = fn()
        except Exception:
            dado = None
        anos = (agora.year, agora.year + 1)
        if not isinstance(dado, pd.DataFrame) or dado.empty or "ano_referencia" not in dado.columns:
            linhas.append(_linha_macro(f"{nome} {anos[0]}", None, "%", None,
                                       erro="Boletim Focus sem dado nesta execução"))
            continue
        for ano in anos:
            sel = dado[dado["ano_referencia"].astype(int) == ano]
            if sel.empty or pd.isna(sel.iloc[0].get("mediana_pct")):
                linhas.append(_linha_macro(f"{nome} {ano}", None, "%", None,
                                           erro=f"Focus sem projeção para {ano}"))
                continue
            r = sel.iloc[0]
            resp = r.get("numero_respondentes")
            detalhe = f"{int(resp)} respondentes" if pd.notna(resp) else None
            boletim = _data_br(r.get("data_calculo"))
            linhas.append(_linha_macro(f"{nome} {ano}", float(r["mediana_pct"]), "%",
                                       f"boletim {boletim}" if boletim else None, detalhe=detalhe))
    return linhas


def _coletar_noticias():
    """Coleta as notícias das editorias: pool Brasil (obter_top_mercado)
    e pool internacional (obter_top_mercado_internacional), cada um com o
    próprio ranking. BR com ticker reconhecido -> empresas; BR sem ticker
    -> Brasil; INT -> Mundo.

    Causa da editoria Mundo vazia na edição de 18/10/2026: a coleta usava
    obter_top_mercado_tudo(), que junta os dois pools e corta o TOTAL nas
    20 mais importantes - naquele dia as 20 eram todas do pool Brasil
    (821 itens contra 110), e o internacional sumia inteiro. As funções
    usadas aqui são as mesmas do app (abas BRASIL/INTERNACIONAL do TOP
    MERCADO), sem nenhuma alteração no pipeline de notícias.

    erro != None distingue "a coleta falhou" de "funcionou mas não achou
    nada" (listas vazias). Um pool falhar sozinho não derruba o outro:
    o erro vem por região."""
    erros = {}
    pools = {}
    for regiao, fn in (("BR", obter_top_mercado), ("INT", obter_top_mercado_internacional)):
        try:
            itens = fn()
        except Exception as exc:
            erros[regiao] = f"{type(exc).__name__}: {exc}"
            itens = None
        if itens is None and regiao not in erros:
            erros[regiao] = "coleta do Google News falhou nesta execução"
        pools[regiao] = itens if isinstance(itens, list) else []
    brasil, empresas, exterior = [], [], []
    for item in pools["BR"] + pools["INT"]:
        regiao = editoria_por_assunto(item.get("titulo"), item.get("regiao") or "BR")
        if regiao == "INT":
            exterior.append({**item, "regiao": "INT"})
        elif e_noticia_de_empresa(item.get("titulo")):
            empresas.append({**item, "regiao": "BR"})
        else:
            brasil.append({**item, "regiao": "BR"})
    return erros, brasil, empresas, exterior


# --- Editoria pelo ASSUNTO, não pela coleta --------------------------
# Causa (edição de 18/10/2026): a editoria vinha da coleta - tudo do pool
# Google News Brasil caía em "Brasil", inclusive "Déficit orçamentário dos
# EUA se aproxima de US$ 2 trilhões" e "Bitcoin... após Warsh, do Fed" (o
# próprio pool BR busca o tema "Fed"). Regra: título com marcador
# estrangeiro e SEM marcador brasileiro vai pra Mundo; título com marcador
# brasileiro vindo do pool internacional vai pra Brasil; sem marcador
# nenhum, fica na editoria da coleta.
_MARCADORES_EXTERIOR = (
    "eua", "estados unidos", "americano", "americana", "americanos", "fed", "federal reserve", "trump",
    "wall street", "treasury", "treasuries", "casa branca", "powell", "warsh", "china", "chines", "chinesa",
    "pequim", "europa", "europeu", "europeia", "bce", "zona do euro", "japao", "reino unido", "alemanha",
    "nasdaq", "s&p 500", "dow jones", "russia", "ucrania", "israel", "ira", "argentina", "milei",
)
_MARCADORES_BRASIL = (
    "brasil", "brasileiro", "brasileira", "brasileiros", "brasileiras", "ibovespa", "b3", "copom", "selic",
    "ipca", "lula", "haddad", "galipolo", "tesouro direto", "bndes", "petrobras", "real", "reais", "r$",
    "brazil", "brazilian", "sao paulo", "brasilia", "stf", "congresso", "camara", "senado", "inss",
)


def _tem_marcador(texto, marcadores):
    return any(re.search(rf"(?<![a-z0-9]){re.escape(m)}(?![a-z0-9])", texto) for m in marcadores)


def editoria_por_assunto(titulo, regiao_coleta):
    """'BR' ou 'INT' pelo assunto do título; sem marcador, a da coleta."""
    texto = _sem_acento(titulo).lower()
    exterior = _tem_marcador(texto, _MARCADORES_EXTERIOR)
    brasil = _tem_marcador(texto, _MARCADORES_BRASIL) or bool(_TICKER_NO_TITULO.search(str(titulo or "")))
    if exterior and not brasil:
        return "INT"
    if brasil and not exterior and regiao_coleta == "INT":
        return "BR"
    return regiao_coleta


# --- Empresas: só com a empresa no PRÓPRIO título ----------------------
# Causa (18/10/2026): "Plano econômico de Flávio pode garantir equilíbrio
# fiscal..." caiu em Empresas porque os tickers vêm de TODOS os títulos do
# grupo de notícias (data/news.py:_processar_pool). Aqui vale só o título
# publicado: ticker de ação escrito nele ou nome de empresa conhecida
# (config.NOMES_ATIVOS_BUSCA, somente leitura). Resumo de pregão que só
# cita a empresa como motor do índice ("Ibovespa reage com Petrobras...")
# continua em Brasil.
_TICKER_NO_TITULO = re.compile(r"\b[A-Z]{4}(?:3|4|5|6|11|32|33|34)\b")
_INICIO_RESUMO_DE_PREGAO = re.compile(r"^\s*(ibovespa|bolsa|b3|d[oó]lar|mercado|mercados|juros|tesouro direto)\b",
                                      re.IGNORECASE)
_NOMES_GENERICOS_DEMAIS = {"B3"}  # a bolsa, não a empresa B3SA3, na maioria dos títulos


def _nomes_de_empresas():
    nomes = set()
    for nome in getattr(config, "NOMES_ATIVOS_BUSCA", {}).values():
        base = re.sub(r"\s*\(.*?\)\s*", " ", str(nome)).strip()
        if base and base not in _NOMES_GENERICOS_DEMAIS:
            nomes.add(base)
    return sorted(nomes, key=len, reverse=True)


_NOMES_EMPRESAS = _nomes_de_empresas()


def e_noticia_de_empresa(titulo):
    titulo = str(titulo or "")
    if _INICIO_RESUMO_DE_PREGAO.match(titulo):
        return False
    if _TICKER_NO_TITULO.search(titulo):
        return True
    # nome com maiúscula, palavra inteira; "Vale a pena"/"Vale + infinitivo" não é a Vale
    return any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])(?! a pena)(?! [a-zà-ú]+(?:ar|er|ir)\b)", titulo)
               for n in _NOMES_EMPRESAS)


# Itens de serviço que o pool de "negócios" do Google News às vezes traz
# e que não são notícia de mercado (achado real: "Resultado da Quina" no
# topo da edição de 18/10/2026). Filtro editorial do PDF, por título.
_TERMOS_FORA_DE_PAUTA = ("quina", "mega-sena", "mega sena", "lotofacil", "lotomania", "loteria",
                         "dupla sena", "timemania", "dia de sorte", "+milionaria", "horoscopo",
                         # anúncio de passagem ("... a partir de R$ 351 ida e volta"), visto na
                         # editoria Brasil da edição real de 18/10/2026
                         "ida e volta")


# Colunas de aconselhamento pessoal do feed do MarketWatch ("I'm 64 with
# two sons...", "I'm 63 and diagnosed with lymphoma...") apareceram na
# editoria Mundo da edição real de 18/10/2026: carta de leitor em 1ª
# pessoa, não notícia de mercado.
_CARTA_DE_LEITOR = re.compile(r"^(i['\u2019]m|i am|my|we['\u2019]re|should i)\b", re.IGNORECASE)


# Mesma carta de leitor, mas aberta por uma citação: "‘Some people did
# everything right’: I lost my home in the Great Recession..." (Mundo,
# edição de 18/10/2026) escapava da regra acima.
_CARTA_COM_CITACAO = re.compile(r"^[\"'‘’“”].{3,}?[\"'‘’“”]\s*:\s*(i\b|i['’]m\b|my\b|we\b)", re.IGNORECASE)

# Matéria de serviço de finanças pessoais ("Tesouro Selic, Tesouro Reserva
# ou CDB: qual rende mais R$ 10 mil...") - útil no app, não é fato de mercado.
_SERVICO_FINANCAS_PESSOAIS = ("qual rende mais", "quanto rende", "onde investir", "vale a pena investir",
                              "quanto eu teria", "como investir", "how much should i", "should i ")


def _fora_de_pauta(titulo):
    texto = _sem_acento(titulo).lower()
    titulo_limpo = str(titulo or "").strip()
    if _CARTA_DE_LEITOR.match(titulo_limpo) or _CARTA_COM_CITACAO.match(titulo_limpo):
        return True
    if any(t in texto for t in _SERVICO_FINANCAS_PESSOAIS):
        return True
    return any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", texto) for t in _TERMOS_FORA_DE_PAUTA)


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or "")) if not unicodedata.combining(c))


def inicio_janela_noticias(agora):
    """06:00 (Brasília) do dia útil anterior ao da edição. Segunda-feira
    -> sexta 06:00 (cobre o fim de semana); domingo -> sexta 06:00."""
    dia = agora.date() - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return datetime.combine(dia, time(6, 0), tzinfo=TZ_SP)


def _data_item(item):
    try:
        momento = datetime.fromisoformat(str(item.get("data")))
    except (TypeError, ValueError):
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=TZ_SP)


_PERCENTUAL = re.compile(r"\d+(?:[.,]\d+)?\s?%")
_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "em", "com", "a", "o", "as", "os", "no", "na",
                    "nos", "nas", "por", "para", "que", "hoje", "fecha", "sobe", "cai", "alta", "queda",
                    "the", "of", "to", "in", "and", "on", "for"}


def _assinatura(titulo):
    texto = _sem_acento(titulo).lower()
    pcts = {p.replace(" ", "").replace(".", ",") for p in _PERCENTUAL.findall(texto)}
    palavras = {w for w in re.findall(r"[a-z]{4,}", texto) if w not in _PALAVRAS_VAZIAS}
    return pcts, palavras


def _mesmo_fato(a, b):
    """Duas manchetes sobre o mesmo número do mesmo assunto ('IBOVESPA
    fecha hoje com alta de 0,54%' x 'Ibovespa sobe 0,54% ...') - o
    agrupador do pipeline de notícias deixou as duas em grupos separados
    na edição de 18/10/2026. Regra estrita de propósito: mesmo percentual
    E ao menos uma palavra de conteúdo em comum."""
    pa, wa = _assinatura(a.get("titulo"))
    pb, wb = _assinatura(b.get("titulo"))
    return bool(pa & pb) and bool(wa & wb)


# Piso de relevância financeira. Causa (Mundo, 18/10/2026: "Deep-fried
# and built to go viral: ... fair foods"): o ranking de importância de
# data/news.py soma recência e veículo, sem exigir assunto de mercado - uma
# matéria recente de 1 veículo entrava sozinha. Agora a matéria precisa de
# assunto financeiro substantivo no título (termo de mercado/economia,
# empresa ou ticker, "%"). Quantidade de veículos NÃO basta: "Saiba como
# emitir a nova Certidão Única de Débitos do Estado de São Paulo" (validação
# real de 18/10/2026) era replicada por vários veículos e entrava.
_TERMOS_FINANCEIROS = (
    # pt
    "acao", "acoes", "bolsa", "bolsas", "ibovespa", "mercado", "mercados", "dolar", "cambio", "juros", "selic",
    "copom", "inflacao", "ipca", "igp", "pib", "fiscal", "deficit", "superavit", "divida", "tesouro", "imposto",
    "tributaria", "arrecadacao", "orcamento", "petroleo", "brent", "minerio", "commodities", "commodity", "ouro",
    "bitcoin", "cripto", "lucro", "prejuizo", "receita", "balanco", "resultado", "resultados", "dividendos",
    "dividendo", "trimestre", "investidores", "investimento", "credito", "banco central", "bancos", "fed", "economia",
    "economico", "economica", "emprego", "desemprego", "salario", "tarifa", "tarifas", "exportacao",
    "exportacoes", "importacao", "safra", "ipo", "aquisicao", "fusao", "privatizacao", "valor de mercado",
    "preco", "precos", "titulos", "debentures", "rating", "recessao", "eleicao", "eleicoes", "pesquisa",
    # regulação, tributação, crédito, indicadores, instituições
    "regulacao", "regulamentacao", "regulador", "reguladora", "cvm", "cade", "aneel", "anatel", "anp", "ans",
    "tributo", "tributos", "tributacao", "icms", "imposto de renda", "reforma tributaria", "emprestimo",
    "emprestimos", "financiamento", "inadimplencia", "endividamento", "caged", "pnad", "producao industrial",
    "varejo", "fmi", "banco mundial", "bce", "opep", "empresa", "empresas", "companhia", "estatal", "estatais",
    # en
    "stock", "stocks", "shares", "market", "markets", "investors", "earnings", "revenue", "profit", "guidance",
    "inflation", "rates", "rate", "yields", "bond", "bonds", "treasury", "dollar", "oil", "gold", "economy",
    "economic", "recession", "gdp", "jobs", "payrolls", "tariff", "tariffs", "deal", "merger", "acquisition",
    "ipo", "bank", "banks", "central bank", "deficit", "debt", "crypto", "bitcoin", "s&p", "nasdaq", "dow",
    "wall street", "trade", "prices", "price", "sales", "layoffs", "valuation", "funding",
    "imf", "world bank", "ecb", "opec", "budget", "tax", "taxes", "credit", "loans", "lending", "regulators",
    "regulation", "antitrust", "company", "companies",
)

# Formato de serviço/tutorial/utilidade pública ("Saiba como emitir...",
# "Como consultar...", "passo a passo", "how to"). Não exclui sozinho: a
# matéria só fica se o título também tiver tema de impacto de mercado
# (_TERMOS_IMPACTO_MERCADO, empresa ou ticker) - "Saiba como fica o IR com
# a reforma tributária" entra; "Saiba como emitir a certidão" sai.
_FORMATO_SERVICO = re.compile(
    r"^(saiba|veja|entenda|confira|aprenda|descubra)\s+(como|onde|quando|quem|qual|quais)\b"
    r"|^como\s+(emitir|tirar|fazer|consultar|solicitar|pedir|baixar|acessar|renovar|agendar|cadastrar|obter"
    r"|regularizar|declarar|sacar|receber)\b"
    r"|\bpasso\s+a\s+passo\b|\btutorial\b|^how\s+to\b")

# Subconjunto estrito pro formato de serviço: tema com impacto material no
# mercado (fica de fora o vocabulário que aparece em serviço ao cidadão -
# "receita", "imposto", "tesouro", "credito", "preco" etc.).
_TERMOS_IMPACTO_MERCADO = (
    "ibovespa", "bolsa", "acoes", "mercado", "mercados", "dolar", "cambio", "juros", "selic", "copom", "inflacao",
    "ipca", "pib", "fiscal", "deficit", "reforma tributaria", "lucro", "prejuizo", "balanco", "resultado",
    "resultados", "dividendos", "dividendo", "fed", "banco central", "regulacao", "cvm",
    "stocks", "markets", "earnings", "inflation", "rates", "tariffs",
)


def tem_relevancia_financeira(item):
    """Piso de relevância do PDF, pelo ASSUNTO do título (nunca pela
    quantidade de veículos): termo de mercado/economia, "%", ticker da B3
    ou empresa acompanhada. Matéria em formato de serviço/tutorial precisa
    de tema de impacto de mercado (_TERMOS_IMPACTO_MERCADO, empresa ou
    ticker) - utilidade pública sem impacto financeiro sai."""
    titulo = item.get("titulo") or ""
    texto = _sem_acento(titulo).lower().strip()
    empresa = bool(_TICKER_NO_TITULO.search(titulo)) or e_noticia_de_empresa(titulo)
    if _FORMATO_SERVICO.search(texto):
        return empresa or _tem_marcador(texto, _TERMOS_IMPACTO_MERCADO)
    return empresa or "%" in texto or _tem_marcador(texto, _TERMOS_FINANCEIROS)


def filtrar_noticias(itens, agora, exigir_relevancia=False):
    """Seleção editorial do PDF (não altera o pipeline de notícias):
    descarta itens fora da janela da edição (publicados antes de 06:00 do
    dia útil anterior, ou com data no futuro), itens fora de pauta
    (loterias) e duplicatas do mesmo fato (fica o de maior importância).
    Item sem data é descartado - não dá pra afirmar que é recente.

    `exigir_relevancia=True` (caminho do PDF) aplica também o piso de
    tem_relevancia_financeira; o e-mail de texto chama sem ele."""
    inicio = inicio_janela_noticias(agora)
    limite_futuro = agora + timedelta(hours=1)
    candidatos = []
    for item in itens or []:
        momento = _data_item(item)
        if momento is None or momento < inicio or momento > limite_futuro:
            continue
        if _fora_de_pauta(item.get("titulo")):
            continue
        if exigir_relevancia and not tem_relevancia_financeira(item):
            continue
        candidatos.append(item)
    candidatos.sort(key=lambda i: i.get("importancia") or 0, reverse=True)
    escolhidos = []
    for item in candidatos:
        if any(_mesmo_fato(item, e) for e in escolhidos):
            continue
        escolhidos.append(item)
    return escolhidos


def _item_fato(item, pronto=None):
    """Manchete -> {titulo, link, veiculo, tag=FATO, ...} - veículo
    atribuído explicitamente (nunca um fato sem fonte visível no PDF).

    `pronto` = resultado JÁ CACHEADO do resumo desse grupo (ver
    _resumos_cacheados) - "corpo" recebe só os parágrafos do bloco RESUMO
    (separar_secoes_resumo); a LEITURA DE MERCADO (interpretação do
    modelo) fica de fora do jornal de propósito: o PDF publica fato com
    fonte, não opinião gerada. Sem resumo cacheado, corpo=[] e o renderer
    publica só a manchete com a fonte (nunca inventa texto)."""
    veiculos = item.get("veiculos") or []
    pronto = pronto or {}
    corpo = []
    if pronto.get("resumo"):
        try:
            corpo, _leitura = separar_secoes_resumo(pronto["resumo"])
        except Exception:
            corpo = []
    return {
        "titulo": str(item.get("titulo") or "").strip(),
        "link": str(item.get("link") or "").strip() or None,
        "veiculo": veiculos[0] if veiculos else None,
        "tag": TAG_FATO,
        "importancia": item.get("importancia") or 0,
        "data": item.get("data"),
        "tickers": list(item.get("tickers") or []),
        "corpo": corpo,
        "imagem": pronto.get("imagem"),
        "link_original": pronto.get("link_original"),
    }


def _resumos_cacheados(itens):
    """{link_do_grupo: resultado} dos resumos JÁ cacheados - uma única
    leitura em lote (obter_resumos_prontos nunca gera resumo nem chama IA).
    Falha de leitura -> {} (a edição sai só com manchetes, nunca quebra)."""
    grupos = [{"titulo": i.get("titulo"), "fontes": i.get("fontes") or [], "link": i.get("link")}
              for i in itens if i.get("link")]
    if not grupos:
        return {}
    try:
        return obter_resumos_prontos(grupos) or {}
    except Exception:
        return {}


# "IBOVESPA fecha hoje com alta de 0,54%" virou manchete de uma edição de
# DOMINGO (publicada no sábado, sobre o pregão de sexta). O título é da
# fonte e não é reescrito; a edição marca quando ele usa referência
# relativa ("hoje", "nesta sexta"...) e foi publicado em outro dia.
_REFERENCIA_RELATIVA = re.compile(
    r"\b(hoje|ontem|amanha|nesta|neste|esta semana|today|yesterday|tomorrow|this week)\b", re.IGNORECASE)


def titulo_relativo_de_outro_dia(item, agora):
    if not _REFERENCIA_RELATIVA.search(_sem_acento(item.get("titulo"))):
        return False
    momento = _data_item(item)
    return momento is not None and momento.astimezone(TZ_SP).date() != agora.date()


def selecionar_manchete(fatos, n_chamadas=5, agora=None):
    """(manchete, chamadas) da capa - a manchete é a matéria de MAIOR
    importância editorial (data/news.py:_calcular_importancia: veículos,
    recência, termos de mercado) entre as que têm texto publicável;
    nunca a que tem mais texto ou foto. Sem nenhuma matéria com texto, a
    de maior importância vira manchete só com título. Sem nenhuma
    notícia -> (None, []): a capa não inventa manchete."""
    ordenados = sorted(fatos, key=lambda f: f.get("importancia") or 0, reverse=True)
    if not ordenados:
        return None, []
    com_texto = [f for f in ordenados if f.get("corpo")]
    candidatas = com_texto or ordenados
    manchete = candidatas[0]
    if agora is not None and titulo_relativo_de_outro_dia(manchete, agora):
        # prefere um título sem "hoje/nesta..." de outro dia, desde que
        # tenha importância comparável (>= 80% da primeira)
        limite = (manchete.get("importancia") or 0) * 0.8
        alternativa = next((f for f in candidatas[1:] if (f.get("importancia") or 0) >= limite
                            and not titulo_relativo_de_outro_dia(f, agora)), None)
        manchete = alternativa or manchete
    chamadas = [f for f in ordenados if f is not manchete][:n_chamadas]
    return manchete, chamadas


def _linha_evento(evento):
    status = evento.get("status")
    rotulo_status = STATUS_LABEL.get(status, status or "status desconhecido")
    nota_status = _NOTA_STATUS_EVENTO.get(status, "nível de confiabilidade da data não identificado.")
    empresa = evento.get("empresa") or evento.get("ticker") or "Empresa não identificada"
    return {
        "empresa": empresa,
        "ticker": evento.get("ticker") or "?",
        "tipo_evento": evento.get("tipo_evento") or "EVENTO",
        "periodo": evento.get("periodo") or "",
        "horario": evento.get("horario") or "sem horário divulgado",
        "status_rotulo": rotulo_status,
        "status_nota": nota_status,
        "tag": TAG_ACOMPANHAR,
    }


def _agenda_hoje(agora):
    try:
        tickers = list(config.IBOVESPA_SETORES.keys())
        eventos = calcular_calendario_cacheado(tickers, hoje=agora.date())
        eventos_hoje = [e for e in eventos if e.get("data") == agora.date()]
        eventos_hoje.sort(key=lambda e: (e.get("horario") or "99:99", e.get("ticker") or ""))
        return [_linha_evento(e) for e in eventos_hoje]
    except Exception:
        return None


def _noticias_do_setor(setor):
    """Notícias candidatas de um setor: uma busca dedicada no Google News
    com a consulta do catálogo (últimos 3 dias) mais o ranking geral do
    Brasil (obter_top_mercado, já cacheado). A busca dedicada usa as
    funções de leitura do coletor (data/news.py: _buscar_feed_de_url e
    _processar_pool - mesmo parse, agrupamento e data), sem alterá-lo: é
    uma requisição por setor, contra ~10 de obter_top_mercado(setor), que
    recoleta o pool inteiro a cada chamada. None só se as duas falharem."""
    from urllib.parse import quote

    from data import news as coletor
    from data.radar_setorial import CATALOGO

    url = coletor._RSS_URL.format(termo=quote(f"{CATALOGO[setor]['consulta']} when:3d"))
    feed = coletor._buscar_feed_de_url(url)
    dedicadas = [] if feed is None else coletor._processar_pool(
        {e.get("link"): (e, None) for e in feed}, "TODOS", "BR")
    gerais = obter_top_mercado()
    if feed is None and gerais is None:
        return None
    return dedicadas + list(gerais or [])


def _radar_setorial(agora, publicados=None):
    """Radar setorial (data/radar_setorial.py) com as notícias do coletor
    filtrado por setor (mesma função da aba TOP MERCADO do app) e as
    mesmas regras editoriais desta edição: janela, fora de pauta,
    duplicata. `publicados` = fatos já publicados nas editorias: o radar
    não os reaproveita como evidência (ver montar_radar). Falha geral ->
    None (a seção diz que não saiu)."""
    try:
        return montar_radar(
            agora, buscar=_noticias_do_setor, inicio=inicio_janela_noticias(agora),
            confiavel=eh_fonte_confiavel, mesmo_fato=_mesmo_fato, fora_de_pauta=_fora_de_pauta,
            publicados=publicados,
        )
    except Exception as exc:
        print(f"[morning_call] radar setorial indisponível: {exc!r}")
        return None


# ============================================================
# Síntese analítica da página 2 (PR da "página 2 analítica", 2026-10-19)
# ============================================================
#
# Objetivo: a página 2 deixa de ser uma lista de manchetes (layout de
# agregador) e passa a ser 5 blocos curtos (ver sintese_pagina2) que
# conectam fato -> por que importa -> o que acompanhar, usando SÓ o que
# já está em `edicao` (nenhuma rede nova, nenhuma 2ª consulta às fontes).
#
# Determinístico primeiro, Groq depois (nunca o contrário): toda frase
# analítica nasce de um template fixo que só concatena fato real (título
# + veículo + data, já presentes no item) com uma cláusula curta e FIXA
# de "por que esse tema importa" (_CLAUSULA_TEMA) - zero invenção
# possível, porque não há geração livre de texto nesse caminho. O Groq
# (_sintese_mercados_ia) é só um POLIMENTO de prosa OPCIONAL por cima
# desse texto determinístico, nunca a fonte dos fatos: o prompt manda
# reescrever só o texto dado, e _ia_nao_adiciona_numero valida que
# nenhum número novo (%, R$, pontos) aparece na saída antes de usar -
# se falhar a validação, falhar a chamada, ou GROQ_API_KEY ausente, o
# texto determinístico (sempre correto, sempre disponível) é o que vai
# pro PDF. Essa é a mesma lição que já levou a remover as "3
# interpretações genéricas fixas" de uma versão anterior deste módulo
# (ver docstring do arquivo): texto igual todo dia é enchimento, não
# informação - aqui o fato mudando todo dia é que ancora cada frase.

_TEMAS_SINTESE = (
    ("juros", ("selic", "copom", "fed", "juros", "taxa de juros", "banco central")),
    ("inflacao", ("inflacao", "ipca", "igp", "cpi", "nucleo de inflacao", "precos ao consumidor")),
    ("cambio", ("dolar", "cambio", "usd/brl", "moeda")),
    ("fiscal", ("fiscal", "deficit", "superavit", "divida publica", "orcamento", "arcabouco fiscal",
               "arrecadacao")),
    ("commodities", ("petroleo", "brent", "minerio", "ouro", "commodities", "commodity", "opep")),
    ("bolsa", ("ibovespa", "bolsa", "s&p 500", "nasdaq", "wall street")),
    ("empresas", ("lucro", "prejuizo", "balanco", "resultado", "resultados", "receita", "dividendo",
                 "dividendos", "valor de mercado")),
)

# Cláusula curta e FIXA por tema - nunca cita número/entidade do dia (só
# o fato real que vem antes dela faz isso); troque com cautela, cada uma
# precisa ser verdadeira em qualquer dia em que aquele tema aparecer.
_CLAUSULA_TEMA = {
    "juros": "tema que afeta diretamente o custo de crédito e a precificação de títulos de renda fixa",
    "inflacao": "indicador acompanhado de perto pelo Banco Central nas decisões de juros",
    "cambio": "variável que pesa sobre custos e receitas de empresas com exposição ao dólar",
    "fiscal": "fator observado por investidores na avaliação do risco fiscal do país",
    "commodities": "insumo relevante para Petrobras, Vale e outros pesos do Ibovespa",
    "bolsa": "termômetro do apetite por risco dos investidores",
    "empresas": "fator com efeito direto sobre os fundamentos da companhia citada",
}

_NOME_TEMA = {
    "juros": "juros", "inflacao": "a inflação", "cambio": "o câmbio", "fiscal": "o quadro fiscal",
    "commodities": "as commodities", "bolsa": "a bolsa", "empresas": "os resultados corporativos",
}


def _tema_do_item(item):
    """Tema do item pelo PRÓPRIO título/corpo (nunca por regra externa de
    coleta) - mesmo espírito de editoria_por_assunto. None se nenhum
    termo bater (fica sem cláusula de 'por que importa', nunca inventa
    uma)."""
    corpo_amostra = " ".join((item.get("corpo") or [])[:1])[:220]
    texto = _sem_acento(f"{item.get('titulo') or ''} {corpo_amostra}").lower()
    for tema, palavras in _TEMAS_SINTESE:
        if any(p in texto for p in palavras):
            return tema
    return None


def _sem_manchete(itens, manchete):
    """Itens da editoria SEM a matéria que já abriu a capa (evita repetir
    literalmente a manchete da capa na página 2 - ela já foi mostrada)."""
    if not itens:
        return []
    return [i for i in itens if manchete is None or i is not manchete]


def _frase_fato(item):
    """'<Título>, segundo <veículo>.' - a MESMA frase-fato em todo bloco
    da página 2 (B/C/D reaproveitam); nunca reescreve o título (ele é a
    manchete real, já aprovada pelo piso de relevância)."""
    titulo = (item.get("titulo") or "").strip().rstrip(". ")
    veiculo = item.get("veiculo") or "fonte não identificada"
    return f"{titulo}, segundo {veiculo}."


def _clausula_tema(item):
    tema = _tema_do_item(item)
    if tema is None:
        return ""
    return f" É um {_CLAUSULA_TEMA[tema]}."


def _segunda_frase_real(item, ja_usadas):
    """1 frase ADICIONAL de corpo (texto real já validado pelo pipeline de
    notícias, nunca gerada aqui) que ainda não apareceu em outro bloco
    desta edição - é o que deixa aprofundar (B/C/D) diferente de repetir
    A. `ja_usadas` é um set mutável (by referência) com as frases já
    publicadas nesta edição inteira, pra nenhuma frase real sair 2x."""
    for frase in (item.get("corpo") or [])[:3]:
        frase = frase.strip()
        if frase and frase not in ja_usadas:
            ja_usadas.add(frase)
            return frase
    return None


def _paragrafos_mercados_determinista(brasil, exterior, empresas):
    """Seção A ("O que move os mercados"), sempre disponível (sem rede,
    sem IA): 1 frase-fato + cláusula de tema por editoria com conteúdo,
    juntando Brasil+Mundo numa frase SÓ quando os temas do topo de cada
    pool coincidem (conexão sustentada pelo próprio tema, nunca uma
    causalidade inventada - a frase deixa isso explícito). Devolve
    (paragrafos, itens_citados) - itens_citados alimenta B/C/D pra não
    repetir o mesmo item sem acrescentar nada."""
    topo_br = brasil[0] if brasil else None
    topo_ext = exterior[0] if exterior else None
    topo_emp = empresas[0] if empresas else None
    citados = []
    paragrafos = []

    tema_br = _tema_do_item(topo_br) if topo_br else None
    tema_ext = _tema_do_item(topo_ext) if topo_ext else None

    if topo_br and tema_br and tema_br == tema_ext:
        paragrafos.append(
            f"{_NOME_TEMA[tema_br].capitalize()} aparece nos dois lados nesta edição: no Brasil, "
            f"{_frase_fato(topo_br)} No exterior, {_frase_fato(topo_ext)} As fontes consultadas não "
            "estabelecem relação causal direta entre os dois movimentos; a coincidência de tema é o que "
            "justifica juntá-los aqui."
        )
        citados += [topo_br, topo_ext]
    else:
        if topo_br:
            paragrafos.append(f"No Brasil, {_frase_fato(topo_br)}{_clausula_tema(topo_br)}")
            citados.append(topo_br)
        if topo_ext:
            paragrafos.append(f"No exterior, {_frase_fato(topo_ext)}{_clausula_tema(topo_ext)}")
            citados.append(topo_ext)

    if topo_emp and all(topo_emp is not c for c in citados):
        paragrafos.append(f"Em empresas, {_frase_fato(topo_emp)}{_clausula_tema(topo_emp)}")
        citados.append(topo_emp)

    if not paragrafos:
        paragrafos = ["Sem notícias com relevância financeira suficiente nas fontes consultadas "
                      "para esta edição."]
    return paragrafos[:3], citados


_NUMERO_NOVO = re.compile(r"(?:r\$\s?)?\d+(?:[.,]\d+)?\s?(?:%|pontos?|bilh(?:ao|oes)|milh(?:ao|oes))?",
                          re.IGNORECASE)


def _numeros(texto):
    return {_sem_acento(n).lower().replace(" ", "") for n in _NUMERO_NOVO.findall(texto or "")}


#  SEM acento de propósito: comparada contra _sem_acento(texto_ia) em
# _ia_sintese_segura - uma entrada acentuada aqui nunca bateria contra o
# texto já normalizado (bug real encontrado por teste, 2026-10-19).
_FRASES_RECOMENDACAO = ("compre", "venda", "recomendamos comprar", "recomendamos vender",
                        "e hora de comprar", "e hora de vender", "vale a pena comprar", "vale a pena vender")


def _ia_sintese_segura(texto_ia, texto_base):
    """Guarda-corpo antes de aceitar QUALQUER texto do Groq pra página 2:
    nenhum número novo (o Groq só pode reorganizar os números que já
    estavam no texto determinístico, nunca somar/inventar outro), nenhuma
    frase de recomendação de compra/venda, tamanho plausível pra prosa
    (não um bloco vazio nem um ensaio). Falhar qualquer checagem == usar
    o texto determinístico (nunca um meio-termo)."""
    if not texto_ia or not texto_ia.strip():
        return False
    if len(texto_ia) > len(texto_base) * 2.5 + 200:
        return False
    if _numeros(texto_ia) - _numeros(texto_base):
        return False
    texto_norm = _sem_acento(texto_ia).lower()
    if any(f in texto_norm for f in _FRASES_RECOMENDACAO):
        return False
    return True


def _chamar_groq_sintese(prompt_usuario):
    chave, modelo = config.obter_credenciais_groq()
    if not chave:
        return None
    try:
        import requests
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "system", "content": (
                        "Você é um editor financeiro brasileiro. Reescreva o texto do usuário em 2 ou 3 "
                        "parágrafos curtos, mais fluidos, SEM adicionar nenhum fato, número, data, nome de "
                        "empresa ou causalidade que não esteja no texto original. Nunca recomende compra ou "
                        "venda. Se não houver nada a melhorar, devolva o texto original sem alteração."
                    )},
                    {"role": "user", "content": prompt_usuario},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
                "reasoning_effort": config.GROQ_REASONING_EFFORT,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        print(f"[morning_call] síntese via Groq indisponível: {exc!r}")
        return None


def _sintese_mercados_ia(paragrafos_base):
    """Tenta um polimento de prosa dos parágrafos determinísticos via
    Groq; devolve (paragrafos_finais, modo) - modo='ia' só quando a
    chamada respondeu E passou por _ia_sintese_segura; qualquer outro
    caso devolve os parágrafos determinísticos originais com modo
    'fallback' (edição continua idêntica sem Groq configurado/disponível)."""
    texto_base = "\n\n".join(paragrafos_base)
    resposta = _chamar_groq_sintese(texto_base)
    if resposta and _ia_sintese_segura(resposta, texto_base):
        novos = [p.strip() for p in resposta.split("\n\n") if p.strip()]
        if novos:
            return novos[:3], "ia"
    return paragrafos_base, "fallback"


def _bloco_brasil_foco(brasil, ja_usadas):
    """B: tema doméstico MAIS relevante - 1 item só, fato + tema +
    (quando existir) 1 frase real adicional do próprio corpo, nunca
    repetida de outro bloco."""
    if not brasil:
        return None
    item = brasil[0]
    texto = _frase_fato(item) + _clausula_tema(item)
    extra = _segunda_frase_real(item, ja_usadas)
    if extra:
        texto += f" {extra}"
    return {"item": item, "texto": texto}


def _bloco_empresas_foco(empresas, ja_usadas, limite=3):
    """C: até `limite` notícias corporativas com impacto material - cada
    uma só com o que a própria matéria afirma (nunca conclusão sobre
    fundamentos a partir da variação do dia)."""
    blocos = []
    for item in (empresas or [])[:limite]:
        texto = _frase_fato(item) + _clausula_tema(item)
        extra = _segunda_frase_real(item, ja_usadas)
        if extra:
            texto += f" {extra}"
        blocos.append({"item": item, "texto": texto})
    return blocos


def _bloco_cenario_internacional(exterior, ja_citados_a, ja_usadas, limite=3):
    """D: cenário internacional - prioriza itens que a seção A ainda NÃO
    citou (acrescenta informação em vez de repetir); se só sobrar o item
    já citado em A, ainda assim entra aqui com uma frase real adicional
    (aprofundar é aceitável, repetir sem nada novo não)."""
    candidatos = [i for i in (exterior or []) if all(i is not c for c in ja_citados_a)] or list(exterior or [])[:1]
    blocos = []
    for item in candidatos[:limite]:
        ja_citado_em_a = any(item is c for c in ja_citados_a)
        extra = _segunda_frase_real(item, ja_usadas)
        if ja_citado_em_a and not extra:
            continue  # sem informação nova pra acrescentar: não repete
        texto = _frase_fato(item) + _clausula_tema(item)
        if extra:
            texto += f" {extra}"
        blocos.append({"item": item, "texto": texto})
    return blocos


def _bloco_acompanhar(agenda, limite=5):
    """E: só eventos REAIS da agenda (data/eventos.py, já no dict) - data/
    horário só quando o status é CONFIRMADO ou ESTIMADO (nunca inventa
    uma data pra evento sem nenhuma fonte); vazio -> lista vazia (o PDF
    mostra a mesma mensagem honesta já usada na Agenda do dia). Prioriza
    CONFIRMADO > ESTIMADO > PRAZO_CVM (PRIORIDADE_STATUS) e limita a
    `limite` linhas - a agenda completa já tem tabela própria na página
    de Mercados/Agenda; aqui é só o que merece destaque na análise."""
    ordenados = sorted(agenda or [], key=lambda e: PRIORIDADE_STATUS.get(e.get("status_rotulo"), 0), reverse=True)
    linhas = []
    vistos = set()  # (empresa, tipo, periodo, horario, status): mesmo evento repetido na agenda não duplica a linha
    for evento in ordenados:
        empresa = evento.get("empresa") or evento.get("ticker") or "Empresa não identificada"
        tipo = str(evento.get("tipo_evento") or "evento").lower()
        horario = evento.get("horario") or "sem horário divulgado"
        status = str(evento.get("status_rotulo") or "").lower()
        periodo = evento.get("periodo") or "período não informado"
        chave = (empresa, tipo, periodo, horario, status)
        if chave in vistos:
            continue
        vistos.add(chave)
        linhas.append(f"{empresa}: {tipo} ({periodo}), {horario} — data {status or 'sem status informado'}.")
        if len(linhas) >= limite:
            break
    return linhas


def sintese_pagina2(edicao, agora=None):
    """Monta os 5 blocos da página 2 analítica a partir do que JÁ está em
    `edicao` (sem nenhuma consulta nova a fonte/rede/IA fora do polimento
    opcional da seção A) - ver cabeçalho da seção acima pro porquê de
    cada escolha de design. Nunca lança exceção: falha em qualquer bloco
    degrada pra lista/texto vazio honesto, igual ao resto do módulo."""
    manchete = (edicao.get("capa") or {}).get("manchete")
    brasil = _sem_manchete((edicao.get("brasil") or {}).get("noticias"), manchete)
    exterior = _sem_manchete((edicao.get("exterior") or {}).get("noticias"), manchete)
    empresas = _sem_manchete((edicao.get("empresas") or {}).get("cards"), manchete)

    paragrafos_base, citados_a = _paragrafos_mercados_determinista(brasil, exterior, empresas)
    paragrafos_mercados, modo_mercados = _sintese_mercados_ia(paragrafos_base)

    ja_usadas = set()  # frases de corpo já publicadas nesta edição, não repete em outro bloco
    brasil_foco = _bloco_brasil_foco(brasil, ja_usadas)
    empresas_foco = _bloco_empresas_foco(empresas, ja_usadas)
    cenario_internacional = _bloco_cenario_internacional(exterior, citados_a, ja_usadas)
    acompanhar = _bloco_acompanhar((edicao.get("empresas") or {}).get("agenda"))

    return {
        "mercados": {"paragrafos": paragrafos_mercados, "modo": modo_mercados},
        "brasil_foco": brasil_foco,
        "empresas_foco": empresas_foco,
        "cenario_internacional": cenario_internacional,
        "acompanhar": acompanhar,
    }


def montar_edicao(agora=None):
    """Monta a edição completa do Morning Call em PDF - um dict puro
    (capa/brasil/exterior/empresas/fontes/limitações), sem nenhuma
    dependência de ReportLab/Pillow. Cada seção degrada graciosamente
    (lista vazia/None + motivo) em vez de lançar exceção - mesmo espírito
    de jobs/morning_call.py: falha de UMA fonte nunca derruba a edição
    inteira nem é omitida em silêncio."""
    agora = agora or datetime.now(TZ_SP)

    ibov = _indicador("Ibovespa", "^BVSP")
    dolar = _indicador("Dólar (USD/BRL)", "USDBRL=X")
    sp500 = _indicador("S&P 500 futuro", "ES=F")
    nasdaq = _indicador("Nasdaq futuro", "NQ=F")
    ouro = _indicador("Ouro", "GC=F")
    petroleo = _indicador("Petróleo Brent", "BZ=F")

    # Uma única coleta de notícias - as 3 seções e a capa precisam ver
    # EXATAMENTE o mesmo conjunto de itens.
    erros_noticias, brasil_bruto, empresas_bruto, exterior_bruto = _coletar_noticias()
    # filtro editorial (janela, fora de pauta, duplicatas) no pool Brasil
    # inteiro antes de separar Brasil/Empresas, pra dedupe valer entre as duas
    # + piso de relevância financeira (só no PDF; o e-mail de texto não usa)
    br_ok = {id(i) for i in filtrar_noticias((brasil_bruto or []) + (empresas_bruto or []), agora,
                                             exigir_relevancia=True)}
    brasil_bruto = [i for i in brasil_bruto or [] if id(i) in br_ok]
    empresas_bruto = [i for i in empresas_bruto or [] if id(i) in br_ok]
    exterior_bruto = filtrar_noticias(exterior_bruto or [], agora, exigir_relevancia=True)
    erro_br = erros_noticias.get("BR")
    erro_int = erros_noticias.get("INT")
    # Limite de extensão da edição (o PDF cresce com o conteúdo, mas não
    # sem limite): as N mais importantes de cada editoria.
    def _top(itens, limite):
        return sorted(itens, key=lambda i: i.get("importancia") or 0, reverse=True)[:limite]

    brasil_sel = _top(brasil_bruto, 8)
    exterior_sel = _top(exterior_bruto, 8)
    empresas_sel = _top(empresas_bruto, 6)
    prontos = _resumos_cacheados(brasil_sel + exterior_sel + empresas_sel)

    def _fatos(itens):
        return [_item_fato(i, prontos.get(i.get("link"))) for i in itens]

    noticias_brasil = _fatos(brasil_sel)
    noticias_exterior_fatos = _fatos(exterior_sel)
    noticias_empresas = _fatos(empresas_sel)
    todos_fatos = noticias_brasil + noticias_empresas + noticias_exterior_fatos
    for fato in todos_fatos:
        # "hoje/nesta semana" num título de outro dia: o PDF diz quando saiu
        fato["publicado_outro_dia"] = titulo_relativo_de_outro_dia(fato, agora)
    manchete, chamadas = selecionar_manchete(todos_fatos, agora=agora)

    edicao = {
        "agora": agora,
        "capa": {
            "indicadores": [ibov, dolar],
            "destaques": sorted(todos_fatos, key=lambda f: f["importancia"], reverse=True)[:3],
            "manchete": manchete,
            "chamadas": chamadas,
        },
        "brasil": {
            "indicadores": [ibov, dolar] + _macro_rows(agora),
            "historico_ibov": _serie_fechamento("^BVSP", "1M"),
            "noticias": noticias_brasil or None,
            "noticias_erro": erro_br,
        },
        "exterior": {
            "indicadores": [sp500, nasdaq, ouro, petroleo],
            "historico_petroleo": _serie_fechamento("BZ=F", "1M"),
            "noticias": noticias_exterior_fatos or None,
            "noticias_erro": erro_int,
        },
        "empresas": {
            "cards": noticias_empresas,
            "agenda": _agenda_hoje(agora),
            "noticias_erro": erro_br,
        },
        "radar": _radar_setorial(agora, publicados=todos_fatos),
        "sessao_mercado": sessao_mercado([ibov, dolar, sp500, nasdaq, ouro, petroleo]),
        "mercados_nota": nota_sessao([ibov, dolar, sp500, nasdaq, ouro, petroleo], agora),
        "janela_noticias": inicio_janela_noticias(agora),
        "limitacoes": LIMITACOES_PADRAO,
        "fontes": FONTES_PADRAO,
    }
    edicao["sintese_pagina2"] = sintese_pagina2(edicao, agora)
    return edicao
