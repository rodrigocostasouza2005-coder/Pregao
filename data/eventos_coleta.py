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
- NUNCA busca uma URL diferente da registrada oficialmente pela empresa
  na CVM (sem inventar sub-caminhos tipo "/calendario") - só lê a
  página exata que a própria empresa registrou;
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

    inicio_trimestre, _ = limites_trimestre(ano, trimestre)
    limite_maximo = prazo_cvm(ano, trimestre) + timedelta(days=_FOLGA_SANIDADE_DIAS)
    validos = [d for d in candidatos if inicio_trimestre <= d <= limite_maximo]
    return validos[0] if validos else None


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


def tentar_ri(ticker: str, empresa: str, ano: int, trimestre: int) -> dict | None:
    """Tenta achar uma data CONFIRMADA na URL oficial de RI (ver
    data/ir_sources.py). None se a empresa nao tiver URL registrada, a
    fonte bloquear/falhar (timeout, erro HTTP, certificado) - quem
    chama segue pra proxima fonte (NEWS), nunca trava o pipeline."""
    url = obter_url_ri(ticker)
    if not url:
        return None
    try:
        r = cffi_requests.get(url, headers=_HEADERS, impersonate="chrome", timeout=_TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None
    texto = _extrair_texto_html(r.text)
    data_evento = extrair_data_do_periodo(texto, ano, trimestre)
    if data_evento is None:
        return None
    return _montar_evento(ticker, empresa, ano, trimestre, STATUS_CONFIRMADO, data_evento, f"{empresa} RI", url)


def tentar_news(ticker: str, empresa: str, ano: int, trimestre: int) -> dict | None:
    """Tenta achar uma data ESTIMADA numa noticia de fonte confiavel
    (mesma busca generica/RSS do Google News que data/news.py ja usa,
    mesmo criterio de confiabilidade - data.news.eh_fonte_confiavel).
    None se a busca falhar ou nenhuma noticia tiver data+periodo
    explicitos."""
    periodo_label = rotulo_periodo(ano, trimestre)
    termo = f"{empresa} resultado {periodo_label} divulgação data"
    entries = _buscar_feed(termo)
    if not entries:
        return None
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

    evento = tentar_ri(ticker, empresa, ano, trimestre)
    if evento is not None:
        return evento

    evento = tentar_news(ticker, empresa, ano, trimestre)
    if evento is not None:
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
        "tempo_esgotado": False, "tabela_disponivel": tabela_eventos_disponivel(),
    }
    for ticker in tickers:
        if time.monotonic() > limite:
            stats["tempo_esgotado"] = True
            break
        evento = coletar_evento(ticker, hoje=hoje)
        stats["processados"] += 1
        if evento is None:
            continue
        if evento["status"] == STATUS_CONFIRMADO:
            if salvar_evento_se_mais_confiavel(evento):
                stats["confirmados"] += 1
        elif evento["status"] == STATUS_ESTIMADO:
            if salvar_evento_se_mais_confiavel(evento):
                stats["estimados"] += 1
        else:
            stats["mantidos_prazo_cvm"] += 1
    return stats
