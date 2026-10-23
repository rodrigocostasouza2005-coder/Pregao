# -*- coding: utf-8 -*-
"""Coletor de datas REAIS de divulgação de resultados (RI → NEWS →
PRAZO CVM), fase COLETOR DE DATAS DE RESULTADOS (2026-10-02).

FLUXO (por ticker): ticker/empresa → período pendente (CVM, ver
data/eventos.py:periodo_pendente) → tenta RI (URL oficial registrada na
CVM, ver data/ir_sources.py) → se não achar data clara, tenta NEWS
(mesma busca genérica já usada em data/news.py) → se nenhuma das duas
achar, mantém PRAZO_CVM (já calculado por
data.eventos.calcular_proximo_resultado).

Reutiliza a ESTRUTURA de eventos de data/eventos.py (mesmo dict shape:
ticker/empresa/periodo/data/horario/status/fonte/origem_url/
tipo_evento/coletado_em, mesmos status/PRIORIDADE_STATUS) - não cria um
segundo formato de evento. Persistência também reaproveita a
infraestrutura Supabase já existente no projeto (data/supabase_client,
mesmo client que research_itens/research_recomendacoes_historico usam)
- não é um banco paralelo, só uma tabela nova (eventos_resultados, ver
sql/eventos.sql) porque nenhuma tabela existente tem esse formato.
PRAZO_CVM nunca é persistido (é uma regra determinística, recalcular é
barato) - só CONFIRMADO/ESTIMADO (as descobertas reais) valem a pena
guardar.

REGRAS DE SEGURANÇA (nunca violadas):
- RI/NEWS só viram CONFIRMADO/ESTIMADO quando o PERÍODO CORRETO (ex:
  "3T26") aparece EXPLICITAMENTE perto de uma data com dia+mês+ANO
  explícitos (nunca infere ano) - sem isso, não marca nada, cai pro
  próximo passo da hierarquia;
- a data extraída precisa cair numa janela de sanidade (entre o início
  do trimestre e o prazo regulatório da CVM + folga - ver
  data.eventos.limites_trimestre/prazo_cvm) - uma data fora dessa
  janela é descartada, mesmo que o regex tenha "batido" nalgum lugar da
  página;
- NUNCA inventa URL: lê a página registrada pela empresa na CVM e, desde
  22/10/2026, só os links de calendário/central de resultados que essa
  MESMA página publica, no mesmo domínio (ver _links_calendario) - nunca
  um sub-caminho adivinhado tipo "/calendario";
- documentos entregues pela própria empresa à CVM (IPE) também valem como
  CONFIRMADO (ver tentar_cvm), com as mesmas regras de período e data;
- notícia só vira ESTIMADO se o veículo passar em
  data.news.eh_fonte_confiavel (mesmo critério já usado pelo selo das
  notícias).

LIMITAÇÃO CONHECIDA (documentada, não escondida): o fetch de RI só lê a
URL EXATA registrada na CVM (geralmente a home institucional, às vezes
já a página de RI) - no mundo real, a data de divulgação normalmente
fica numa subpágina ("Calendário de Eventos"), então a taxa de sucesso
de CONFIRMADO via RI nesta primeira versão tende a ser baixa. Decisão
deliberada: preferir não inventar/adivinhar a URL da subpágina a
arriscar errado (mesma postura da fase V2 do calendário)."""

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from data.eventos import (
    PRIORIDADE_STATUS, STATUS_CONFIRMADO, STATUS_ESTIMADO,
    limites_trimestre, periodo_pendente, prazo_cvm, rotulo_periodo,
)
from data.eventos import calcular_proximo_resultado as _calcular_proximo_resultado
from data.ir_sources import obter_url_ri
from data.news import _buscar_feed, _extrair_veiculo_e_titulo, eh_fonte_confiavel
from data.prices import obter_nome_yf
from data.supabase_client import obter_cliente

_HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
_TIMEOUT = 10
_FOLGA_SANIDADE_DIAS = 15  # tolerancia alem do prazo CVM pra aceitar uma data real (empresa as vezes atrasa um pouco)

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_ORDINAIS_TRIMESTRE = {1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto"}

_PADRAO_DATA_NUMERICA = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_PADRAO_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
    r"\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)


def _tokens_periodo(ano: int, trimestre: int) -> list:
    """Variações textuais que uma empresa/notícia pode usar pra se
    referir ao mesmo período (ex: "3T26", "3º trimestre de 2026") -
    nunca inventa um período diferente do calculado por
    data.eventos.periodo_pendente, só reconhece formas de escrevê-lo."""
    aa = ano % 100
    return [
        f"{trimestre}t{aa:02d}", f"{trimestre}t{ano}", f"t{trimestre}/{aa:02d}", f"t{trimestre} {ano}",
        f"{trimestre}º trimestre de {ano}", f"{trimestre}o trimestre de {ano}",
        f"{_ORDINAIS_TRIMESTRE[trimestre]} trimestre de {ano}",
    ]


def _parse_data_numerica(m) -> date | None:
    dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _parse_data_extenso(m) -> date | None:
    dia = int(m.group(1))
    mes = _MESES.get(m.group(2).lower().replace("ç", "c"))
    if mes is None:
        return None
    try:
        return date(int(m.group(3)), mes, dia)
    except ValueError:
        return None


def extrair_data_do_periodo(texto: str, ano: int, trimestre: int) -> date | None:
    """Procura, numa janela de texto perto de uma menção EXPLÍCITA do
    período certo, uma data com dia+mês+ANO explícitos (nunca infere
    ano). Só aceita se a data cair na janela de sanidade do período
    (entre o início do trimestre e o prazo CVM + folga) - uma data fora
    disso quase certamente é um match errado em outra parte da página,
    nunca usada mesmo que o regex tenha "batido". None se não achar
    nada que atenda as duas condições."""
    texto_lower = texto.lower()
    pos_periodo = None
    for tok in _tokens_periodo(ano, trimestre):
        idx = texto_lower.find(tok)
        if idx != -1:
            pos_periodo = idx
            break
    if pos_periodo is None:
        return None

    janela = texto[max(0, pos_periodo - 150):min(len(texto), pos_periodo + 150)]
    candidatos = [d for m in _PADRAO_DATA_NUMERICA.finditer(janela) if (d := _parse_data_numerica(m))]
    candidatos += [d for m in _PADRAO_DATA_EXTENSO.finditer(janela) if (d := _parse_data_extenso(m))]
    if not candidatos:
        return None

    # Resultado de um trimestre nunca é divulgado antes de ele terminar: a
    # janela começa no dia seguinte ao fim do trimestre. Antes começava no
    # início do trimestre e aceitava a DATA DE REFERÊNCIA ("ITR de
    # 30/09/2026", presente em todo documento do 3T26) como se fosse a data
    # de divulgação.
    _, fim_trimestre = limites_trimestre(ano, trimestre)
    limite_maximo = prazo_cvm(ano, trimestre) + timedelta(days=_FOLGA_SANIDADE_DIAS)
    validos = [d for d in candidatos if fim_trimestre < d <= limite_maximo]
    # Página de RI costuma trazer divulgação E teleconferência perto do
    # período ("Divulgação 3T26: 21/10/2026 · Teleconferência: 22/10/2026");
    # a divulgação nunca vem depois da teleconferência, então vale a MENOR
    # data válida (caso real: WEGE3 ficou com 22/10, dia do call, e o
    # resultado saiu em 21/10).
    return min(validos) if validos else None


def _extrair_texto_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def _montar_evento(ticker: str, empresa: str, ano: int, trimestre: int, status: str, data_evento: date, fonte: str, origem_url: str) -> dict:
    return {
        "ticker": ticker, "empresa": empresa, "periodo": rotulo_periodo(ano, trimestre),
        "data": data_evento, "horario": None, "status": status, "fonte": fonte,
        "origem_url": origem_url, "tipo_evento": "RESULTADO",
        "coletado_em": datetime.now(timezone.utc),
    }


# Texto/endereço de link que a PRÓPRIA página oficial publica para o
# calendário de eventos ou a central de resultados (nunca um caminho
# adivinhado: só links que estão no HTML da página registrada na CVM).
_PALAVRAS_LINK_CALENDARIO = ("calendario", "calendar", "agenda", "central de resultados",
                             "central-de-resultados", "resultados trimestrais", "earnings")
_MAX_LINKS_CALENDARIO = 2
_TIMEOUT_SUBPAGINA = 6


def _dominio_base(host: str) -> str:
    partes = [p for p in (host or "").lower().split(".") if p and p != "www"]
    # "ri.empresa.com.br" e "www.empresa.com.br" -> "empresa.com.br"
    if len(partes) >= 3 and partes[-1] == "br" and partes[-2] in ("com", "net", "org"):
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def _links_calendario(html: str, url_base: str) -> list:
    """Links do mesmo domínio da página oficial cujo texto ou endereço
    indica calendário/agenda/central de resultados - no máximo
    _MAX_LINKS_CALENDARIO, na ordem da página."""
    from urllib.parse import urljoin, urlparse

    dominio = _dominio_base(urlparse(url_base).netloc)
    soup = BeautifulSoup(html, "html.parser")
    achados = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url_base, a["href"].strip())
        partes = urlparse(href)
        if partes.scheme not in ("http", "https") or _dominio_base(partes.netloc) != dominio:
            continue
        rotulo = f"{a.get_text(' ', strip=True)} {partes.path}".lower()
        rotulo = rotulo.replace("á", "a").replace("ê", "e")
        if not any(p in rotulo for p in _PALAVRAS_LINK_CALENDARIO):
            continue
        href = href.split("#", 1)[0]
        if href != url_base and href not in achados:
            achados.append(href)
        if len(achados) >= _MAX_LINKS_CALENDARIO:
            break
    return achados


# Texto/caminho de link que indica "aqui fica o portal de RI de verdade" -
# diferente de _PALAVRAS_LINK_CALENDARIO (achar o calendário DENTRO de um
# site já identificado como o certo), este serve só pra achar O PRÓPRIO
# portal a partir da home institucional - por isso pode cruzar de domínio
# (ver _link_portal_ri). Lista curta e de alto sinal (rótulo de menu
# comum em site institucional BR), nunca um termo genérico que combine
# com conteúdo não relacionado.
_PALAVRAS_PORTAL_RI = (
    "relacao com investidor", "relacoes com investidor", "relacionamento com investidor",
    "investor relations", "investidores",
)
_CAMINHOS_PORTAL_RI = ("/ri", "/investidores", "/investor-relations", "/relacoes-com-investidores",
                       "/relacionamento-com-investidores")


def _link_portal_ri(html: str, url_base: str) -> str | None:
    """1º link (qualquer domínio, diferente de _links_calendario) cujo
    texto ou caminho indica 'aqui é o portal de RI' - achado real desta
    auditoria (22/10/2026): www.petrobras.com.br linka
    investidorpetrobras.com.br, um domínio TOTALMENTE diferente (mesmo
    padrão em várias companhias BR: ri.empresa.com, investidorempresa.
    com.br, empresa-ri.com etc); a versão anterior de tentar_ri só
    seguia link de calendário DENTRO do mesmo domínio da home - pra essas
    empresas nunca achava nada, mesmo quando a própria home publicava o
    link certo. Segue esse link UMA única vez (nunca um 2º salto pra
    fora do portal encontrado) - é a própria página oficial da empresa
    que está indicando onde fica o RI, não um palpite nosso. None se
    nenhum link bater."""
    from urllib.parse import urljoin, urlparse

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(url_base, a["href"].strip())
        partes = urlparse(href)
        if partes.scheme not in ("http", "https"):
            continue
        texto = _sem_acento_simples(a.get_text(" ", strip=True))
        caminho = partes.path.lower().rstrip("/")
        if any(p in texto for p in _PALAVRAS_PORTAL_RI) or any(caminho.endswith(c) for c in _CAMINHOS_PORTAL_RI):
            return href.split("#", 1)[0]
    return None


def _extrair_data_da_pagina(url: str, ano: int, trimestre: int) -> tuple[date | None, str | None]:
    """Busca `url` e tenta achar a data do período direto no texto -
    (data, None) em caso de falha de rede/HTTP, nunca lança exceção (quem
    chama decide o próximo passo da hierarquia). Fatorado de tentar_ri
    pra reaproveitar o mesmo fetch+extração nos 3 lugares onde ele
    acontece (página oficial, link de calendário dela, portal de RI
    cross-domain e o calendário DELE)."""
    try:
        r = cffi_requests.get(url, headers=_HEADERS, impersonate="chrome", timeout=_TIMEOUT_SUBPAGINA)
        r.raise_for_status()
    except Exception:
        return None, None
    return extrair_data_do_periodo(_extrair_texto_html(r.text), ano, trimestre), r.text


def tentar_ri(ticker: str, empresa: str, ano: int, trimestre: int) -> dict | None:
    """Tenta achar uma data CONFIRMADA na URL oficial de RI (ver
    data/ir_sources.py), nos links de calendário/central de resultados
    que a PRÓPRIA página publica (_links_calendario, só no mesmo
    domínio) e, se nada disso achar nada, no portal de RI que a home
    institucional costuma linkar em OUTRO domínio (_link_portal_ri,
    achado desta auditoria de 22/10/2026) - nunca um caminho adivinhado
    em nenhum dos três casos. None se a empresa nao tiver URL registrada,
    a fonte bloquear/falhar (timeout, erro HTTP, certificado) - quem
    chama segue pra proxima fonte, nunca trava o pipeline.

    LIMITAÇÃO QUE CONTINUA (documentada, não escondida): várias centrais
    de resultados modernas são paginas client-side (o HTML cru só tem o
    menu de navegação; a lista de eventos carrega via JS/API depois) -
    confirmado nesta auditoria contra investidorpetrobras.com.br e
    ri.weg.net, ambas alcançadas corretamente pelo salto novo, mas sem
    texto extraível na resposta HTTP crua. Sem executar JavaScript (fora
    do escopo aqui - orçamento de tempo do universo inteiro já é
    apertado, e um navegador automatizado por ticker não é sustentável
    num workflow de 20 min), essas continuam caindo pro PRAZO_CVM."""
    from urllib.parse import urlparse

    url = obter_url_ri(ticker)
    if not url:
        return None
    try:
        r = cffi_requests.get(url, headers=_HEADERS, impersonate="chrome", timeout=_TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None
    data_evento = extrair_data_do_periodo(_extrair_texto_html(r.text), ano, trimestre)
    if data_evento is not None:
        return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento, f"{empresa} RI", url)
    for link in _links_calendario(r.text, url):
        data_evento, _ = _extrair_data_da_pagina(link, ano, trimestre)
        if data_evento is not None:
            return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento,
                                  f"{empresa} RI", link)

    portal = _link_portal_ri(r.text, url)
    if not portal or _dominio_base(urlparse(portal).netloc) == _dominio_base(urlparse(url).netloc):
        return None  # mesmo domínio: _links_calendario acima já cobriu
    data_evento, texto_portal = _extrair_data_da_pagina(portal, ano, trimestre)
    if data_evento is not None:
        return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento, f"{empresa} RI", portal)
    if texto_portal is None:
        return None
    for link in _links_calendario(texto_portal, portal):
        data_evento, _ = _extrair_data_da_pagina(link, ano, trimestre)
        if data_evento is not None:
            return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento,
                                  f"{empresa} RI", link)
    return None


# Documentos que a própria companhia entrega à CVM (IPE) e que costumam
# anunciar a data de divulgação: "Comunicado ao Mercado - Divulgação de
# Resultados do 3T26", aviso de teleconferência, calendário de eventos.
_CATEGORIAS_IPE_DATA = ("Comunicado ao Mercado", "Aviso aos Acionistas", "Calendário de Eventos Corporativos",
                        "Fato Relevante")
_TERMOS_IPE_RESULTADO = ("resultado", "divulga", "teleconfer", "webcast", "earnings", "calendario", "itr")
_MAX_DOCUMENTOS_IPE = 2
# timeout próprio (o de data/cvm.py é 30 s, pensado para o resumo sob
# demanda): na 1ª execução real com 30 s o calendário só cobriu 23 dos 84
# tickers no orçamento de 5 min
_TIMEOUT_DOCUMENTO_CVM = (4, 8)


def _texto_documento_cvm(link: str) -> str | None:
    import requests

    from data.cvm import _extrair_texto_pdf

    try:
        r = requests.get(link, headers=_HEADERS, timeout=_TIMEOUT_DOCUMENTO_CVM)
        r.raise_for_status()
    except Exception:
        return None
    texto = _extrair_texto_pdf(r.content)
    return texto if texto and len(texto) >= 200 else None


def _sem_acento_simples(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)).lower()


def _data_perto_da_data_base(texto: str, ano: int, trimestre: int) -> date | None:
    """Como extrair_data_do_periodo, mas usando a data-base do trimestre
    (ex.: "30/09/2026") como marcador do período - formato das tabelas de
    Calendário de Eventos Corporativos (ITR com data-base e data de envio).
    Só olha os 80 caracteres seguintes à data-base (a linha da tabela)."""
    _, fim = limites_trimestre(ano, trimestre)
    limite_maximo = prazo_cvm(ano, trimestre) + timedelta(days=_FOLGA_SANIDADE_DIAS)
    for marcador in (fim.strftime("%d/%m/%Y"), fim.strftime("%d.%m.%Y")):
        for m in re.finditer(re.escape(marcador), texto):
            trecho = texto[m.end():m.end() + 80]
            for d in (_parse_data_numerica(x) for x in _PADRAO_DATA_NUMERICA.finditer(trecho)):
                if d and fim < d <= limite_maximo:
                    return d
    return None


def tentar_cvm(ticker: str, empresa: str, ano: int, trimestre: int) -> dict | None:
    """Data CONFIRMADA a partir dos documentos que a própria empresa
    entregou à CVM (IPE, dados.cvm.gov.br - fonte oficial e estruturada
    que o projeto já baixa em data/cvm.py). Primeiro o ASSUNTO do
    documento; se ele cita o período/resultado mas não traz a data, o
    texto do próprio documento (link oficial da CVM, no máximo
    _MAX_DOCUMENTOS_IPE por ticker). Mesmas regras de
    extrair_data_do_periodo: período explícito + data com ano + janela de
    sanidade. None se nada for encontrado ou a fonte falhar."""
    from data.cvm import obter_documentos_cvm

    try:
        documentos = obter_documentos_cvm(ticker)
    except Exception:
        logging.exception("Falha ao ler documentos CVM do calendario para %s", ticker)
        return None
    if not documentos:
        return None
    _, fim_trimestre = limites_trimestre(ano, trimestre)
    # calendário anual é entregue no começo do ano; comunicados de
    # divulgação, depois do fim do trimestre
    inicio_busca = date(ano, 1, 1)
    candidatos = []
    for doc in documentos:
        try:
            entregue = date.fromisoformat(str(doc.get("data"))[:10])
        except ValueError:
            continue
        if entregue < inicio_busca or doc.get("categoria_original") not in _CATEGORIAS_IPE_DATA:
            continue
        assunto = str(doc.get("assunto") or "")
        data_evento = extrair_data_do_periodo(assunto, ano, trimestre)
        if data_evento is not None:
            return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento,
                                  f"{empresa} (CVM - {doc['categoria_original']})", doc.get("link"))
        assunto_norm = _sem_acento_simples(assunto)
        eh_calendario = doc.get("categoria_original") == "Calendário de Eventos Corporativos"
        # comunicado de data de divulgação sai depois do fim do trimestre;
        # o calendário anual, no começo do ano
        if not doc.get("link") or (not eh_calendario and entregue <= fim_trimestre):
            continue
        if eh_calendario or any(t in assunto_norm for t in _TERMOS_IPE_RESULTADO):
            candidatos.append(doc)
    # comunicados mais recentes primeiro (obter_documentos_cvm já ordena);
    # só o calendário mais recente, por último
    comunicados = [d for d in candidatos if d.get("categoria_original") != "Calendário de Eventos Corporativos"]
    calendarios = [d for d in candidatos if d.get("categoria_original") == "Calendário de Eventos Corporativos"][:1]
    for doc in (comunicados + calendarios)[:_MAX_DOCUMENTOS_IPE]:
        texto = _texto_documento_cvm(doc["link"])
        if not texto:
            continue
        data_evento = extrair_data_do_periodo(texto, ano, trimestre)
        if data_evento is None and doc.get("categoria_original") == "Calendário de Eventos Corporativos":
            # calendário anual identifica o ITR pela data-base ("30/09/2026"),
            # não por "3T26"; a data-base em si nunca passa na janela
            data_evento = _data_perto_da_data_base(texto, ano, trimestre)
        if data_evento is not None:
            return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento,
                                  f"{empresa} (CVM - {doc['categoria_original']})", doc["link"])
    return None


def tentar_news(ticker: str, empresa: str, ano: int, trimestre: int) -> dict | None:
    """Tenta achar uma data ESTIMADA numa noticia de fonte confiavel
    (mesma busca generica/RSS do Google News que data/news.py ja usa,
    mesmo criterio de confiabilidade - data.news.eh_fonte_confiavel).
    None se a busca falhar ou nenhuma noticia tiver data+periodo
    explicitos."""
    periodo_label = rotulo_periodo(ano, trimestre)
    termo = f"{empresa} resultado {periodo_label} divulgação data"
    try:
        entries = _buscar_feed(termo)
    except Exception:
        # NEWS e' uma fonte secundaria: uma falha de RSS/busca nao pode
        # abortar o ticker nem impedir o fallback deterministico PRAZO_CVM.
        logging.exception("Falha na busca NEWS do calendario para %s", ticker)
        return None
    if not entries:
        return None
    try:
        for entry in entries[:10]:
            titulo, veiculo = _extrair_veiculo_e_titulo(entry)
            if not veiculo or not eh_fonte_confiavel(veiculo):
                continue
            resumo = re.sub(r"<[^>]+>", " ", entry.get("summary") or "")
            data_evento = extrair_data_do_periodo(f"{titulo} {resumo}", ano, trimestre)
            if data_evento is None:
                continue
            link = entry.get("link") or ""
            if not link:
                continue
            return _montar_evento(ticker, empresa, ano, trimestre, STATUS_ESTIMADO, data_evento, veiculo, link)
    except Exception:
        # Feed malformado tambem e' falha da fonte secundaria, nao motivo
        # para descartar o fallback de prazo regulatorio deste ticker.
        logging.exception("Falha ao interpretar NEWS do calendario para %s", ticker)
    return None


_JANELA_REVERIFICACAO_DIAS = 7  # ver _confirmado_precisa_reverificar


def _confirmado_precisa_reverificar(salvo: dict, hoje: date) -> bool:
    """True se um evento ja' CONFIRMADO precisa de 1 nova tentativa de
    RI/NEWS, em vez do atalho direto pro valor salvo (ver coletar_evento).
    Bug real corrigido (auditoria 2026-10-10): o atalho introduzido em
    2026-10-09 pra consertar a "fome" de recurso (ver docstring de
    coletar_evento) tambem eliminou qualquer chance de corrigir um
    CONFIRMADO - uma vez salvo, RI/NEWS NUNCA eram tentados de novo pro
    mesmo (ticker,periodo), nem que a empresa adiasse/corrigisse a data
    (atualizando a MESMA URL de RI ja' registrada na CVM, ver
    data/ir_sources.py). salvar_evento_se_mais_confiavel ja' suporta
    sobrescrever um CONFIRMADO por outro CONFIRMADO com data diferente -
    so' nunca era exercitado, porque o atalho nunca deixava chegar la'.

    So' reverifica (no maximo 1x por _JANELA_REVERIFICACAO_DIAS, pra nao
    reintroduzir o custo de rede em TODA execucao - o mesmo problema que
    o atalho original resolveu) quando a data confirmada AINDA esta' no
    futuro (evento que ja' aconteceu nao tem mais o que corrigir) E a
    ultima verificacao (coletado_em) ja' passou dessa janela. Linha
    salva malformada (sem data/coletado_em parseavel) tambem pede
    reverificacao - mais seguro que confiar numa linha que nao da' pra
    interpretar."""
    try:
        data_confirmada = date.fromisoformat(str(salvo["data_evento"])[:10])
    except (KeyError, ValueError, TypeError):
        return True
    if data_confirmada < hoje:
        return False
    coletado_em = salvo.get("coletado_em")
    if not coletado_em:
        return True
    try:
        verificado_em = datetime.fromisoformat(str(coletado_em)).date()
    except (ValueError, TypeError):
        return True
    return (hoje - verificado_em).days >= _JANELA_REVERIFICACAO_DIAS


def coletar_evento(ticker: str, hoje: date = None) -> dict | None:
    """Pipeline completo pra 1 ticker: RI -> NEWS -> PRAZO_CVM (fallback
    final, sempre disponivel se a CVM responder). None so' se nem o
    PRAZO_CVM puder ser calculado (fonte CVM de verdade indisponivel -
    nunca inventa evento nenhum nesse caso).

    Atalho (bug real de "fome" de recurso corrigido, 2026-10-09): se o
    (ticker,periodo) JA' tem um CONFIRMADO persistido (maior
    confiabilidade possivel - PRIORIDADE_STATUS - nada que RI/NEWS
    possam achar melhora isso) E essa confirmacao ainda nao precisa de
    reverificacao (ver _confirmado_precisa_reverificar), pula RI/NEWS
    direto pro valor ja' salvo, sem nenhuma chamada de rede. Sem isso,
    TODO ticker (mesmo os ja' resolvidos) refazia RI+NEWS (rede, ate'
    ~20s cada) em TODA execucao do coletor - com o orcamento de
    coletar_eventos_universo (_ORCAMENTO_TOTAL_S=5min) e o universo de
    ~84 tickers (config.IBOVESPA_SETORES), os primeiros tickers da lista
    (SEMPRE a MESMA ordem, dict.keys()) consumiam o orcamento inteiro
    so' reconfirmando o que ja' sabiam, e os tickers do final da lista
    NUNCA eram alcancados - nao e' so' lento, e' estagnacao permanente
    (o docstring de coletar_eventos_universo promete "o proximo run
    continua de onde parou", o que so' e' verdade se os ja'-CONFIRMADOS
    pularem a parte cara da rede).

    Reverificacao periodica (bug real corrigido, auditoria 2026-10-10):
    o atalho acima, sem limite, tambem impedia pra sempre a correcao de
    um CONFIRMADO que a empresa depois adia/corrige - ver
    _confirmado_precisa_reverificar."""
    periodo = periodo_pendente(ticker, hoje)
    if periodo is None:
        return None
    ano, trimestre = periodo
    rotulo = rotulo_periodo(ano, trimestre)
    hoje_efetivo = hoje if hoje is not None else date.today()

    salvo = _buscar_evento_salvo(ticker, rotulo)
    if (
        salvo is not None and salvo.get("status") == STATUS_CONFIRMADO
        and not _confirmado_precisa_reverificar(salvo, hoje_efetivo)
    ):
        try:
            return _montar_evento(
                ticker, obter_nome_yf(ticker) or ticker, ano, trimestre, STATUS_CONFIRMADO,
                date.fromisoformat(str(salvo["data_evento"])[:10]), salvo["fonte"], salvo.get("url_fonte"),
            )
        except (KeyError, ValueError, TypeError):
            pass  # linha salva malformada - ignora o atalho, segue o pipeline normal (RI/NEWS/PRAZO_CVM)

    empresa = obter_nome_yf(ticker) or ticker

    # "via" só serve ao log do coletor (de onde veio cada data); não é persistido
    for via, tentativa in (("RI", tentar_ri), ("CVM", tentar_cvm), ("NEWS", tentar_news)):
        evento = tentativa(ticker, empresa, ano, trimestre)
        if evento is not None:
            if isinstance(evento, dict):
                evento.setdefault("via", via)
            return evento

    return _calcular_proximo_resultado(ticker, hoje=hoje)


# ---------------------------------------------------------------------
# Persistencia (Supabase, mesma infraestrutura ja' usada pelo projeto -
# ver sql/eventos.sql; nao e' um banco paralelo, so' uma tabela nova)
# ---------------------------------------------------------------------

def tabela_eventos_disponivel() -> bool | None:
    """Diagnostico (2026-10-05, achado real: a tabela eventos_resultados
    nao existia em producao - sql/eventos.sql nunca tinha sido rodado la
    - e tanto a leitura (data/eventos.py:_buscar_evento_persistido)
    quanto a escrita abaixo degradavam em silencio pro mesmo caminho de
    "nada encontrado", deixando o problema invisivel por dias no log).
    True se a tabela responde a uma consulta trivial, False se existir
    o cliente Supabase mas a consulta falhar (schema/tabela ausente,
    erro de permissao etc), None se o Supabase em si estiver fora do ar
    (obter_cliente()=None). So' pra diagnostico/log (ver
    coletor_local.py) - nunca usada pra decidir o pipeline
    RI->NEWS->PRAZO_CVM em si, que continua degradando com seguranca
    independente disso."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        cliente.table("eventos_resultados").select("ticker").limit(1).execute()
        return True
    except Exception:
        return False


def _buscar_evento_salvo(ticker: str, periodo: str) -> dict | None:
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("eventos_resultados")
            .select("*")
            .eq("ticker", ticker).eq("periodo", periodo)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def salvar_evento_se_mais_confiavel(evento: dict) -> bool:
    """Upsert em eventos_resultados SO' quando o novo status tem
    confiabilidade >= a' do que ja estava salvo pro mesmo
    (ticker,periodo) - nunca regride CONFIRMADO/ESTIMADO de volta pra
    um status pior so' porque uma coleta pontual nao achou nada melhor
    (mesma regra de data.eventos.PRIORIDADE_STATUS). PRAZO_CVM nunca e'
    persistido aqui (so' CONFIRMADO/ESTIMADO - ver docstring do modulo).
    Retorna True se gravou algo NOVO de verdade, False se manteve o que
    ja' estava, o status nao e' persistivel (PRAZO_CVM), ou o banco
    falhou."""
    if evento["status"] not in (STATUS_CONFIRMADO, STATUS_ESTIMADO):
        return False
    cliente = obter_cliente()
    if cliente is None:
        return False
    anterior = _buscar_evento_salvo(evento["ticker"], evento["periodo"])
    if anterior and PRIORIDADE_STATUS[anterior["status"]] > PRIORIDADE_STATUS[evento["status"]]:
        return False
    if (
        anterior and anterior["status"] == evento["status"]
        and anterior.get("data_evento") == evento["data"].isoformat()
    ):
        return False  # idempotente - nada mudou de verdade, nao vale regravar
    try:
        cliente.table("eventos_resultados").upsert(
            {
                "ticker": evento["ticker"], "periodo": evento["periodo"],
                "data_evento": evento["data"].isoformat(), "status": evento["status"],
                "fonte": evento["fonte"], "url_fonte": evento.get("origem_url"),
                "coletado_em": evento["coletado_em"].isoformat() if evento.get("coletado_em") else None,
            },
            on_conflict="ticker,periodo",
        ).execute()
        return True
    except Exception:
        return False


_ORCAMENTO_TOTAL_S = 5 * 60  # mesma ideia de orcamento de data/research/base.py:TEMPO_MAX_COLETA_S


def coletar_eventos_universo(tickers: list, hoje: date = None) -> dict:
    """Roda o pipeline completo (RI->NEWS->PRAZO_CVM) pra uma lista de
    tickers e persiste so' as descobertas reais (CONFIRMADO/ESTIMADO).
    Respeita um orcamento total de tempo (nunca roda indefinidamente) -
    se estourar, para e reporta quantos tickers ficaram de fora (o
    proximo run do coletor continua de onde parou naturalmente, ja que
    tickers ja' resolvidos como CONFIRMADO nao mudam). Retorna
    {"processados", "confirmados", "estimados", "mantidos_prazo_cvm",
    "tempo_esgotado", "tabela_disponivel"} - o ultimo e' so' diagnostico
    (ver tabela_eventos_disponivel), nunca afeta o pipeline em si."""
    limite = time.monotonic() + _ORCAMENTO_TOTAL_S
    stats = {
        "processados": 0, "confirmados": 0, "estimados": 0, "mantidos_prazo_cvm": 0,
        "falhas": 0, "tempo_esgotado": False, "tabela_disponivel": tabela_eventos_disponivel(),
        # já CONFIRMADO/ESTIMADO no banco com a mesma data (nada novo a gravar)
        "ja_registrados": 0, "via": {},
    }
    for ticker in tickers:
        if time.monotonic() > limite:
            stats["tempo_esgotado"] = True
            break
        inicio_ticker = time.monotonic()
        try:
            evento = coletar_evento(ticker, hoje=hoje)
            print(f"[eventos] {ticker}: {(evento or {}).get('status', 'sem período')}"
                  f" {(evento or {}).get('periodo', '')} {(evento or {}).get('data', '')}"
                  f" via {(evento or {}).get('via', '-')} ({(evento or {}).get('fonte', '')})"
                  f" em {time.monotonic() - inicio_ticker:.1f}s")
            if evento is not None:
                if evento["status"] in (STATUS_CONFIRMADO, STATUS_ESTIMADO):
                    via = evento.get("via") or "salvo"
                    stats["via"][via] = stats["via"].get(via, 0) + 1
                if evento["status"] == STATUS_CONFIRMADO:
                    if salvar_evento_se_mais_confiavel(evento):
                        stats["confirmados"] += 1
                    else:
                        stats["ja_registrados"] += 1
                elif evento["status"] == STATUS_ESTIMADO:
                    if salvar_evento_se_mais_confiavel(evento):
                        stats["estimados"] += 1
                    else:
                        stats["ja_registrados"] += 1
                else:
                    stats["mantidos_prazo_cvm"] += 1
        except Exception:
            # Um ticker malformado ou uma excecao inesperada nao deve abortar
            # os demais ativos do universo. A falha fica visivel no log e nas stats.
            stats["falhas"] += 1
            logging.exception("Falha ao coletar evento de resultados para %s", ticker)
        finally:
            stats["processados"] += 1
    return stats
