# -*- coding: utf-8 -*-
"""SAUDE DOS DADOS - painel de monitoramento dos coletores do PREGAO.

Isolado de proposito (nao importa nada de data/research/genial.py,
data/eventos.py, data/eventos_coleta.py nem coletor_local.py alem das
funcoes de LEITURA ja existentes e publicas) - essa aba nao escreve
nada nesses modulos, so' le o que eles ja expoem.

Dois tipos de coletor:

- INSTRUMENTADO: registra cada tentativa via
  `data.coletores_status.registrar_tentativa` (NEWS, MERCADO, MACRO,
  CVM - auditoria 2026-10-09; Genial Analisa/XP Investimentos/
  Genial (Lives)/CALENDARIO - auditoria 2026-10-10, direto no ponto
  real de coleta em `data/research/__init__.py:coletar_casa` e
  `coletor_local.py`, ja que esses 4 so' rodam de verdade na maquina
  local do Rodrigo via `coletor_local.py`, nunca neste sandbox).
  Classificacao usa execucao_ok/persistencia_ok/erro reais da
  tentativa mais recente.
- HIBRIDO (os 4 acima, ate' o Rodrigo rodar o `coletor_local.py`
  atualizado pela 1a vez): como `coletores_status` comeca vazio pra
  eles, cai pro mesmo leitor SOMENTE_LEITURA de antes (so' a idade do
  ULTIMO DADO persistido) em vez de mostrar NUNCA_EXECUTADO e esconder
  dado antigo real que ja existe - ver `_leitor_hibrido`. Assim que
  existir pelo menos 1 tentativa real registrada, usa ela sempre (nunca
  volta pro fallback).

Nenhum dos dois finge saber mais do que realmente sabe: HIBRIDO nunca
afirma execucao_ok/persistencia_ok reais enquanto so' tem o fallback
(ver `_status_somente_leitura`), so' INSTRUMENTADO com tentativa real
registrada classifica por execucao_ok/persistencia_ok de verdade.

Nunca inventa estado "verde" por ausencia de evidencia - ver
`classificar_estado` abaixo, o caso sem dado nenhum sempre cai em
NUNCA_EXECUTADO/NAO_COMPROVADO.
"""

from datetime import datetime, timezone

from data import coletores_status

_TERMOS_INDISPONIBILIDADE = (
    "timeout", "timed out", "conexao", "conexão", "connection",
    "bloquead", "403", "waf", "dns", "ssl", "indispon", "unreachable",
)

# (codigo, rotulo-base) - o rotulo final em obter_painel_saude() inclui
# detalhe especifico (erro real, horas de atraso, etc.)
ESTADOS = {
    "SUCESSO_COM_NOVIDADE": "Coleta OK - dados novos",
    "SUCESSO_SEM_NOVIDADE": "Coleta OK - sem novidades",
    "PARCIAL": "Coleta parcial",
    "FALHA_EXECUCAO": "Falha de execucao",
    "FALHA_PERSISTENCIA": "Falha de persistencia",
    "DADOS_DESATUALIZADOS": "Dados desatualizados",
    "FONTE_INDISPONIVEL": "Fonte indisponivel",
    "NAO_COMPROVADO": "Nao comprovado",
    "NUNCA_EXECUTADO": "Nunca executado",
}

# estados que a UI pinta como alerta (amarelo/vermelho) vs neutro/ok
_ESTADOS_ALERTA = {
    "FALHA_EXECUCAO", "FALHA_PERSISTENCIA", "FONTE_INDISPONIVEL",
    "DADOS_DESATUALIZADOS", "PARCIAL",
}
_ESTADOS_DESCONHECIDO = {"NAO_COMPROVADO", "NUNCA_EXECUTADO"}


def _idade_horas(timestamp_iso: str) -> float:
    ts = datetime.fromisoformat(timestamp_iso)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 3600


def classificar_estado(status: dict | None, idade_maxima_horas: float | None = None) -> tuple:
    """Classifica UM coletor num dos estados de ESTADOS, a partir do
    registro de tentativa (dict com execucao_ok/persistencia_ok/parcial/
    registros_novos/ultimo_erro/ultimo_sucesso_em) - mesmo schema tanto
    pra tentativa instrumentada real quanto pra status sintetico
    SOMENTE_LEITURA (ver `_status_somente_leitura`). Retorna
    (codigo, rotulo_detalhado). Funcao pura - testavel sem rede/banco."""
    if status is None:
        return "NUNCA_EXECUTADO", ESTADOS["NUNCA_EXECUTADO"] + " (sem evidencia nenhuma)"

    ultimo_sucesso_em = status.get("ultimo_sucesso_em")
    execucao_ok = status.get("execucao_ok")
    persistencia_ok = status.get("persistencia_ok", True)
    parcial = status.get("parcial", False)
    registros_novos = status.get("registros_novos")
    erro = (status.get("ultimo_erro") or "")

    if ultimo_sucesso_em is None:
        if execucao_ok is False and erro:
            return "NAO_COMPROVADO", f"{ESTADOS['NAO_COMPROVADO']} (nenhum sucesso ainda; ultimo erro: {erro})"
        return "NAO_COMPROVADO", ESTADOS["NAO_COMPROVADO"] + " (nenhum sucesso confirmado ainda)"

    idade_h = _idade_horas(ultimo_sucesso_em)
    desatualizado = idade_maxima_horas is not None and idade_h > idade_maxima_horas

    if execucao_ok is False:
        erro_lower = erro.lower()
        if any(termo in erro_lower for termo in _TERMOS_INDISPONIBILIDADE):
            return "FONTE_INDISPONIVEL", f"{ESTADOS['FONTE_INDISPONIVEL']}: {erro or 'sem detalhe'}"
        return "FALHA_EXECUCAO", f"{ESTADOS['FALHA_EXECUCAO']}: {erro or 'sem detalhe'}"

    if persistencia_ok is False:
        return "FALHA_PERSISTENCIA", ESTADOS["FALHA_PERSISTENCIA"] + " (coleta OK, gravacao falhou)"

    if desatualizado:
        return "DADOS_DESATUALIZADOS", f"{ESTADOS['DADOS_DESATUALIZADOS']} (ultimo sucesso ha {idade_h:.0f}h)"

    if parcial:
        detalhe = f": {erro}" if erro else " (algumas fontes/itens nao confirmados)"
        return "PARCIAL", ESTADOS["PARCIAL"] + detalhe

    if registros_novos:
        return "SUCESSO_COM_NOVIDADE", f"{ESTADOS['SUCESSO_COM_NOVIDADE']} ({registros_novos})"

    return "SUCESSO_SEM_NOVIDADE", ESTADOS["SUCESSO_SEM_NOVIDADE"]


def _status_somente_leitura(ultimo_dado_em) -> dict | None:
    """Sintetiza um status minimo a partir so' do timestamp do ULTIMO
    DADO persistido (sem info de tentativa) - usado pelos coletores que
    ainda nao instrumentam tentativa (ver docstring do modulo). Nunca
    afirma execucao_ok/persistencia_ok reais - so' usa o que e'
    realmente sabido (que em algum momento um dado bom foi salvo)."""
    if ultimo_dado_em is None:
        return None
    if hasattr(ultimo_dado_em, "isoformat"):
        ultimo_dado_em = ultimo_dado_em.isoformat()
    return {
        "execucao_ok": None,
        "persistencia_ok": True,
        "parcial": False,
        "registros_novos": None,
        "ultimo_erro": None,
        "ultimo_sucesso_em": ultimo_dado_em,
    }


def _leitor_research(casa: str):
    def _ler():
        from data.research.store import ultima_coleta_em
        return _status_somente_leitura(ultima_coleta_em(casa))
    return _ler


def _leitor_calendario():
    def _ler():
        from data.eventos import obter_snapshot_calendario
        snap = obter_snapshot_calendario()
        if not snap:
            return None
        return _status_somente_leitura(snap.get("atualizado_em"))
    return _ler


def _leitor_hibrido(nome: str, leitor_fallback):
    """Tentativa real registrada (`coletores_status`) quando existir;
    cai pro `leitor_fallback` (SOMENTE_LEITURA, so' idade do ultimo dado
    persistido) enquanto nenhuma tentativa real ainda foi gravada - evita
    que virar INSTRUMENTADO esconda dado antigo real que ja existia antes
    da 1a execucao do coletor com o registro novo (ver docstring do
    modulo)."""
    def _ler():
        status = coletores_status.obter_status(nome)
        if status is not None:
            return status
        return leitor_fallback()
    return _ler


# Registro dos coletores conhecidos (auditoria 2026-10-09). `idade_maxima_horas`
# e' a folga acima da frequencia esperada antes de marcar DADOS_DESATUALIZADOS
# (nao e' a frequencia em si - um coletor de 30min que atrasa 1h nao e'
# necessariamente "desatualizado", mas atrasar 24h+ sim).
REGISTRO_COLETORES = [
    {
        "nome": "NEWS", "fonte": "Google News + extracao (InfoMoney/Money Times/trafilatura)",
        "categoria": "Noticias", "frequencia_esperada": "sob demanda (cache 20min)",
        "idade_maxima_horas": 6, "instrumentado": True,
    },
    {
        "nome": "NEWS (Brasil)", "fonte": "Google News Brasil (RSS de negócios + temas)",
        "categoria": "Noticias", "frequencia_esperada": "sob demanda (cache 20min)",
        "idade_maxima_horas": 6, "instrumentado": True,
    },
    {
        "nome": "NEWS (Internacional)", "fonte": "Google News EUA + CNBC/MarketWatch/Yahoo Finance",
        "categoria": "Noticias", "frequencia_esperada": "sob demanda (cache 20min)",
        "idade_maxima_horas": 6, "instrumentado": True,
    },
    {
        # linha separada (achado real, auditoria missao coletores
        # 2026-10-13): "NEWS" (acima) so' media' obter_top_mercado_tudo -
        # a busca POR TICKER (obter_noticias_watchlist, o que a aba
        # NOTICIAS de verdade usa) e' outro caminho de codigo/fonte, podia
        # quebrar isolado sem aparecer aqui. Ver data/news.py:
        # obter_noticias_watchlist.
        "nome": "NEWS (watchlist)", "fonte": "Google News (busca por ticker)",
        "categoria": "Noticias", "frequencia_esperada": "sob demanda (cache 20min)",
        "idade_maxima_horas": 6, "instrumentado": True,
    },
    {
        # linha nova (BACKLOG.md "NEWS - obter_noticias fora da watchlist
        # agregada sem instrumentacao de SAUDE DOS DADOS"): data/news.py:
        # obter_noticias(ticker) e' chamado DIRETO (sem passar por
        # obter_noticias_watchlist) por ui/research_tab.py, ui/
        # calendario_tab.py e a visao de ticker unico de ui/news_tab.py -
        # se quebrasse isolado bem no momento em que so' esses 3
        # consumidores estao ativos, SAUDE DOS DADOS nao captava. Nome
        # separado de "NEWS (watchlist)" de proposito, mesmo os dois
        # chamando literalmente a mesma funcao (ver docstring de
        # obter_noticias em data/news.py) - evita que o upsert de um
        # caminho sobrescreva o status do outro.
        "nome": "NEWS (ticker único)", "fonte": "Google News (busca por ticker)",
        "categoria": "Noticias", "frequencia_esperada": "sob demanda (cache 20min)",
        "idade_maxima_horas": 6, "instrumentado": True,
    },
    {
        "nome": "MERCADO", "fonte": "yfinance (cotacoes em lote)",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 90s)",
        "idade_maxima_horas": 2, "instrumentado": True,
    },
    {
        # linha nova (auditoria 2026-10-22): data/prices.py:obter_cotacao
        # (cotacao de 1 ticker por vez, via fast_info) tinha ZERO chamadas
        # a registrar_tentativa, mesmo sendo o caminho usado pela pagina
        # do ticker, Radar de Quedas (1x por ticker monitorado) e Morning
        # Call - ja' documentado como ponto de falha silenciosa no proprio
        # comentario de data/radar_quedas.py:processar_monitoramento
        # ("provedor de cotacao bloqueado faz TODOS os tickers carem
        # silenciosamente"). Nome diferente de "MERCADO" (lote, acima) -
        # caminho de codigo diferente, pode falhar isolado.
        "nome": "MERCADO (cotação individual)", "fonte": "yfinance (fast_info, por ticker)",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 30s)",
        "idade_maxima_horas": 2, "instrumentado": True,
    },
    {
        # linha nova (achado real, auditoria missao coletores 2026-10-13,
        # continuacao): data/ibovespa.py:obter_composicao_oficial nunca
        # chamava registrar_tentativa - alimenta obter_panorama_ibovespa/
        # altas-baixas/mais-negociados/setorial/treemap (data/mercado.py)
        # e _nome_empresa do CALENDARIO, mas nao tinha NENHUMA
        # representacao neste painel (nem falha, nem "nunca executado" -
        # a linha simplesmente nao existia). idade_maxima_horas bem maior
        # que o cache (24h, so' muda em rebalanceamento quadrimestral da
        # B3): atraso curto nao e' sinal real de problema.
        "nome": "B3 (composição Ibovespa)", "fonte": "sistemaswebb3-listados.b3.com.br",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 24h)",
        "idade_maxima_horas": 48, "instrumentado": True,
    },
    {
        # linha nova (achado real, auditoria missao coletores 2026-10-13,
        # continuacao): data/mercado.py:_baixar_lote_bruto (indices
        # globais) nunca chamava registrar_tentativa - nenhuma linha
        # representava essa fonte neste painel.
        "nome": "MERCADO (Globais)", "fonte": "yfinance (índices globais)",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 90s)",
        "idade_maxima_horas": 2, "instrumentado": True,
    },
    {
        # fonte atualizada (continuacao 2026-10-13): representa so' o
        # IPCA agora - Selic/CDI/Focus ganharam linha propria abaixo
        # (gap de escopo ja catalogado em BACKLOG.md, resolvido nesta
        # sessao). Nome da linha ("MACRO (BCB)") mantido inalterado de
        # proposito, pra nao perder o historico ja registrado em
        # producao sob esse nome.
        "nome": "MACRO (BCB)", "fonte": "Banco Central (SGS - IPCA)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "MACRO (BCB - Selic)", "fonte": "Banco Central (SGS)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "MACRO (BCB - CDI)", "fonte": "Banco Central (SGS)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "MACRO (BCB - Focus IPCA)", "fonte": "Banco Central (Olinda/Expectativas)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "MACRO (BCB - Focus Selic)", "fonte": "Banco Central (Olinda/Expectativas)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        # linha nova (achado real, auditoria missao coletores 2026-10-13,
        # continuacao): data/macro.py:obter_cenario_global (ouro/
        # petroleo/minerio/Treasuries/VIX, mesmo _baixar_lote_bruto de
        # MERCADO (Globais) acima, symbols diferentes) nunca chamava
        # registrar_tentativa.
        "nome": "MACRO (Cenário Global)", "fonte": "yfinance (ouro/petróleo/minério/Treasuries/VIX)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 90s)",
        "idade_maxima_horas": 2, "instrumentado": True,
    },
    {
        "nome": "MACRO (ANBIMA)", "fonte": "ANBIMA (ETTJ - curva pre)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "CVM", "fonte": "dados.cvm.gov.br (IPE)",
        "categoria": "CVM", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        # linha separada (achado real, auditoria missao coletores
        # 2026-10-13): o FCA (mapa ticker->CNPJ, usado por obter_cnpj/
        # obter_documentos_cvm) nunca chamava registrar_tentativa - so' o
        # IPE (acima) chamava. Se o FCA quebrasse isolado (ex: CVM
        # renomeia a coluna Codigo_Negociacao), obter_cnpj passava a
        # devolver None pra TODO ticker (CVM tab e CALENDARIO sem
        # nenhum documento) enquanto este painel continuava mostrando
        # "CVM: Coleta OK" - ver data/cvm.py:_mapa_ticker_cnpj.
        "nome": "CVM (FCA)", "fonte": "dados.cvm.gov.br (FCA - mapa ticker->CNPJ)",
        "categoria": "CVM", "frequencia_esperada": "sob demanda (cache 24h)",
        "idade_maxima_horas": 48, "instrumentado": True,
    },
    {
        # Coleta agregada da watchlist CVM usada na aba CVM/EQUITY; distingue
        # falha da fonte por ticker e falha de persistência dos documentos.
        "nome": "CVM (watchlist)", "fonte": "dados.cvm.gov.br (IPE/FCA - documentos por ticker)",
        "categoria": "CVM", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "Genial Analisa", "fonte": "analisa.genialinvestimentos.com.br",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("Genial Analisa", _leitor_research("Genial Analisa")),
    },
    {
        "nome": "XP Investimentos", "fonte": "conteudos.xpi.com.br (WP REST)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("XP Investimentos", _leitor_research("XP Investimentos")),
    },
    {
        "nome": "Genial (Lives)", "fonte": "YouTube RSS (canal Genial Analisa)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 72, "instrumentado": True,
        "leitor": _leitor_hibrido("Genial (Lives)", _leitor_research("Genial (Lives)")),
    },
    {
        # linha nova (auditoria 2026-10-22): "BTG Pactual Research" e' casa
        # ativa_por_padrao=True em data/research/__init__.py:CASAS (coleta de
        # verdade, registro em research_itens com casa="BTG Pactual Research" -
        # ver data/research/btg.py:_NOME_CASA) mas nao constava neste painel -
        # ficava sem nenhuma representacao (nem OK nem falha).
        "nome": "BTG Pactual Research", "fonte": "content.btgpactual.com (API de research, filtrado por tier publico)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("BTG Pactual Research", _leitor_research("BTG Pactual Research")),
    },
    {
        # linha nova (auditoria 2026-10-22): mesmo gap do BTG acima - "Monte
        # Bravo" tambem ativa_por_padrao=True (ver data/research/montebravo.py:
        # _NOME_CASA) e tambem nao constava neste painel.
        "nome": "Monte Bravo", "fonte": "montebravo.com.br (feed RSS do blog, seção de análise)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("Monte Bravo", _leitor_research("Monte Bravo")),
    },
    {
        # linha nova (24/10/2026): mesmo gap do BTG/Monte Bravo acima -
        # "Nord Research" tambem ativa_por_padrao=True (ver data/research/
        # nord.py:_NOME_CASA). idade_maxima_horas mais alta que as outras
        # casas (120h = 5 dias): sem feed RSS, so' publica posts de
        # resultado quando ha' temporada de balanco - semanas sem nenhum
        # resultado novo sao normais, nao e' sinal de coletor quebrado.
        "nome": "Nord Research", "fonte": "nordinvestimentos.com.br (sitemap do blog, posts de resultado por ticker)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 120, "instrumentado": True,
        "leitor": _leitor_hibrido("Nord Research", _leitor_research("Nord Research")),
    },
    {
        "nome": "CALENDARIO", "fonte": "RI das empresas + NEWS + prazo CVM",
        "categoria": "Calendario", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("CALENDARIO", _leitor_calendario()),
    },
    {
        # linha nova (Modulo 2 - Earnings Reviewer, 2026-10-22):
        # data/earnings/cvm_dre.py ja' chama registrar_tentativa - essa
        # linha so' expõe isso no painel (mesmo padrao das demais fontes
        # instrumentadas, nao hibridas: sem coletor_local envolvido, roda
        # sob demanda quando alguem abre uma nota de resultado BR).
        "nome": "CVM (DRE trimestral)", "fonte": "dados.cvm.gov.br (ITR - DRE consolidada)",
        "categoria": "Earnings", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "SEC EDGAR (XBRL)", "fonte": "data.sec.gov (companyconcept, us-gaap)",
        "categoria": "Earnings", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        # linha nova (achado real, auditoria geral de coletores 2026-10-30):
        # data/earnings/reviewer.py:salvar_versao persistia em
        # earnings_reviews sem NENHUM registrar_tentativa - a tabela em
        # si nem existia no Supabase ainda (migracao sql/earnings_reviews.sql
        # nunca tinha sido rodada), e essa falha ficava completamente
        # invisivel no painel de saude. Instrumentado agora; continua
        # sob demanda (mesmo padrao de CVM DRE/SEC EDGAR acima - decisao
        # deliberada, nao agendado no coletor_local.py).
        "nome": "EARNINGS REVIEWER (persistencia)", "fonte": "earnings_reviews (Supabase)",
        "categoria": "Earnings", "frequencia_esperada": "sob demanda (quando uma nota e' gerada)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        # linha nova (auditoria 2026-10-15): jobs/radar_quedas.py (GitHub
        # Actions, a cada 15min em pregao) nunca chamava registrar_tentativa -
        # a tabela radar_alertas_queda so' registra ALERTAS de queda, nao a
        # tentativa de execucao - uma rodada sem queda >4% (sucesso legitimo)
        # nao deixava rastro nenhum neste painel.
        "nome": "RADAR DE QUEDAS", "fonte": "Carteiras recomendadas (Genial + Safra) + cotacoes",
        "categoria": "Radar", "frequencia_esperada": ".github/workflows/radar-morning-call.yml, 15min (seg-sex, pregao)",
        "idade_maxima_horas": 1, "instrumentado": True,
    },
    {
        # linha nova (auditoria 2026-10-22): "RADAR DE QUEDAS" acima e'
        # AGREGADO das 2 casas - uma falha isolada de 1 delas (ex: Genial
        # carteiras fora do ar, Safra OK) ficava indistinguivel de "tudo
        # OK" pra quem olha so' essa linha. jobs/radar_quedas.py:
        # _registrar_tentativas_por_casa ja' grava status por casa
        # separado (dado que processar_monitoramento() ja' calculava mas
        # nao chegava ao painel). Nome com sufixo "(carteiras)" de
        # proposito - NUNCA "Genial Analisa" sozinho, que e' outra fonte
        # (research da Genial, nao carteira recomendada) e colidiria no
        # upsert por nome.
        "nome": "Genial Analisa (carteiras)", "fonte": "analisa.genialinvestimentos.com.br (carteiras recomendadas)",
        "categoria": "Radar", "frequencia_esperada": ".github/workflows/radar-morning-call.yml, 15min (seg-sex, pregao)",
        "idade_maxima_horas": 1, "instrumentado": True,
    },
    {
        "nome": "Safra Corretora (carteiras)", "fonte": "safra.com.br (carteiras recomendadas, HTML + PDF mensal)",
        "categoria": "Radar", "frequencia_esperada": ".github/workflows/radar-morning-call.yml, 15min (seg-sex, pregao)",
        "idade_maxima_horas": 1, "instrumentado": True,
    },
    {
        # linha nova (auditoria 2026-10-15): mesmo gap do RADAR - jobs/
        # morning_call.py tinha sua propria tabela (morning_call_execucoes)
        # mas nunca aparecia no painel central.
        "nome": "MORNING CALL", "fonte": "Macro+Mercado+NEWS agregados, e-mail (Resend/SMTP)",
        "categoria": "Morning Call", "frequencia_esperada": ".github/workflows/radar-morning-call.yml, diario 07h BRT (seg-sex)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        # linha nova (incidente 2026-10-23): P/L, P/VP e DY apareceram em
        # branco simultaneamente em TODA a watchlist (ANALISES > Empresas
        # > Fundamentos e o comparativo da watchlist, que chamam a MESMA
        # data/prices.py:obter_indicadores) - investigacao confirmou que
        # esse caminho nunca tinha nenhuma linha aqui, nem instrumentacao
        # nenhuma (nem coletor_local.py, nem registrar_tentativa) - zero
        # jeito de confirmar em producao se foi excecao de rede, Yahoo
        # respondendo vazio sem excecao (bloqueio/rate-limit), ou outra
        # causa. Instrumentado agora em data/prices.py:_tk_info_com_retry
        # (func auxiliar de obter_indicadores) - ver docstring la' pra
        # como as 2 causas ficam diferenciadas no erro registrado.
        # idade_maxima_horas=30 (mesma folga x2.5 do TTL de 12h ja usada
        # pros outros coletores "sob demanda" acima, ex: CVM DRE/SEC XBRL).
        "nome": "EQUITY (Fundamentos)", "fonte": "yfinance (tk.info - P/L, P/VP, DY, ROE, margens, dívida líquida)",
        "categoria": "Fundamentos", "frequencia_esperada": "sob demanda (cache 12h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
]


def diagnostico_infraestrutura() -> bool | str | None:
    """Repassa `coletores_status.tabela_disponivel()` pro uso da UI (ver
    ui/saude_dados_tab.py) - checagem de infraestrutura, separada de
    `obter_painel_saude()` de proposito: quando ela da' qualquer coisa
    diferente de True, TODOS os coletores sem fallback hibrido abaixo
    aparecem NUNCA_EXECUTADO/NAO_COMPROVADO ao mesmo tempo - nao porque
    pararam de rodar, mas porque o proprio registro de tentativas esta'
    inacessivel. Sem este diagnostico, as causas (coletor realmente
    nunca rodou vs. infraestrutura de status quebrada - e, dentro desse
    2o caso, tabela ausente vs. credencial/conexao ruim vs. outro motivo,
    ver tabela_disponivel) ficam indistinguiveis pra quem le' o painel."""
    return coletores_status.tabela_disponivel()


def obter_painel_saude() -> list:
    """Monta o painel completo: pra cada coletor do REGISTRO_COLETORES,
    busca o status (instrumentado -> tabela coletores_status; somente-
    leitura -> leitor dedicado) e classifica. Nunca lanca excecao -
    qualquer falha de leitura individual vira NAO_COMPROVADO pra aquele
    coletor, sem derrubar o painel inteiro.

    N+1 real corrigido (auditoria de performance 2026-10-24): antes,
    cada um dos coletores SEM leitor dedicado (24 de 30 em
    REGISTRO_COLETORES) chamava coletores_status.obter_status(nome)
    individualmente - 24 round-trips sequenciais ao Supabase por
    carregamento desta aba, mesma classe de problema já corrigida em
    outros pontos do app (obter_cotacoes_lote, paralelização de
    data/market_makers.py:_riscos). obter_todos_status() já existia
    como alternativa em lote (1 única consulta, mesmo schema de linha
    por nome) e não era usada aqui - agora é chamada 1x antes do loop."""
    todos_status = coletores_status.obter_todos_status()
    painel = []
    for c in REGISTRO_COLETORES:
        try:
            status = c["leitor"]() if "leitor" in c else todos_status.get(c["nome"])
        except Exception:
            status = None
        codigo, rotulo = classificar_estado(status, c.get("idade_maxima_horas"))
        painel.append({
            "nome": c["nome"], "fonte": c["fonte"], "categoria": c["categoria"],
            "frequencia_esperada": c["frequencia_esperada"],
            "instrumentado": c["instrumentado"],
            "codigo_estado": codigo, "rotulo_estado": rotulo,
            "status_bruto": status,
            "alerta": codigo in _ESTADOS_ALERTA,
            "desconhecido": codigo in _ESTADOS_DESCONHECIDO,
        })
    return painel


_CAMPOS_OBRIGATORIOS_COLETOR = (
    "nome", "fonte", "categoria", "frequencia_esperada", "instrumentado",
)
_COLETORES_CRITICOS = {
    "NEWS", "NEWS (Brasil)", "NEWS (Internacional)", "NEWS (watchlist)", "NEWS (ticker único)",
    "MERCADO", "MACRO (BCB)", "CVM", "CVM (FCA)", "CVM (watchlist)", "CALENDARIO",
}


# --- Consumo efetivo (presenca nos consumidores) ---------------------
# Modulo 1 (auditoria 2026-10-22): obter_painel_saude() acima so' mede
# COLETA e PERSISTENCIA - nunca se o dado persistido chegou a ser USADO
# por um consumidor real. Uma secao do Morning Call pode "existir" (titulo
# presente - jobs/morning_call.py:gerar_preview ja valida isso) e ainda
# sair vazia (so' a frase de fallback, ex. "Nenhuma manchete macro do
# Brasil nesta coleta.") mesmo com coleta OK e itens novos persistidos.
# Esta secao NUNCA declara o coletor quebrado por isso - pode ser filtro
# editorial legitimo (relevancia/dedup/limite, ver
# data/morning_call_editorial.py:filtrar_noticias) - so' torna a
# divergencia visivel pra quem olha o painel decidir.
_SEM_VALOR = object()  # sentinela pra distinguir "edicao nao passada" (busca
# a real) de "edicao=None passado explicitamente" (ex: teste simulando banco
# indisponivel) em obter_painel_consumo() abaixo.

ESTADOS_CONSUMO = {
    "CONSUMO_COM_ITENS": "Usado na última edição",
    "CONSUMO_SEM_ITENS": "Ausente na última edição (filtro editorial pode ser legítimo - ver seção)",
    "CONSUMO_DESCONHECIDO": "Sem edição recente do Morning Call para conferir",
}

# Fonte (mesmo nome de REGISTRO_COLETORES) -> secoes de
# jobs.morning_call.SECOES_OBRIGATORIAS onde ela deveria aparecer.
SECOES_POR_FONTE_CONSUMO = {
    "NEWS (Brasil)": ("2. BRASIL",),
    "NEWS (Internacional)": ("3. EXTERIOR",),
    "NEWS (watchlist)": ("5. EMPRESAS E SETORES",),
}


def _ultima_edicao_morning_call():
    from data.morning_call_historico import listar_edicoes
    try:
        edicoes = listar_edicoes()
    except Exception:
        return None
    if not edicoes:
        return None
    return next((e for e in edicoes if e.get("conteudo")), None)


def obter_painel_consumo(edicao=_SEM_VALOR) -> list:
    """Painel COMPLEMENTAR a obter_painel_saude(): pra cada fonte com
    secao conhecida no Morning Call (SECOES_POR_FONTE_CONSUMO), conta
    quantos itens com link apareceram na ULTIMA edicao publicada
    (jobs/morning_call.py:contar_itens_por_secao). `edicao` e'
    injetavel pra teste puro (dict com "conteudo"/"data" ou None); por
    padrao busca a edicao real via _ultima_edicao_morning_call(). Nunca
    lanca excecao - qualquer falha individual cai em CONSUMO_DESCONHECIDO,
    nunca finge sucesso nem derruba o painel inteiro (mesmo espirito de
    obter_painel_saude)."""
    from jobs.morning_call import contar_itens_por_secao

    if edicao is _SEM_VALOR:
        edicao = _ultima_edicao_morning_call()

    painel = []
    for fonte, secoes in SECOES_POR_FONTE_CONSUMO.items():
        if not edicao or not edicao.get("conteudo"):
            painel.append({
                "fonte": fonte, "secoes": secoes, "itens": None,
                "data_edicao": None, "codigo_estado": "CONSUMO_DESCONHECIDO",
                "rotulo_estado": ESTADOS_CONSUMO["CONSUMO_DESCONHECIDO"],
            })
            continue
        try:
            contagem = contar_itens_por_secao(edicao["conteudo"])
        except Exception:
            contagem = {}
        total = sum(contagem.get(secao, 0) for secao in secoes)
        codigo = "CONSUMO_COM_ITENS" if total else "CONSUMO_SEM_ITENS"
        rotulo = ESTADOS_CONSUMO[codigo]
        if total:
            rotulo = f"{rotulo} ({total} iten(s))"
        painel.append({
            "fonte": fonte, "secoes": secoes, "itens": total,
            "data_edicao": edicao.get("data"), "codigo_estado": codigo,
            "rotulo_estado": rotulo,
        })
    return painel


def auditar_registro_coletores(registro=None) -> list:
    """Retorna problemas estruturais no inventario, sem rede ou banco."""
    itens = REGISTRO_COLETORES if registro is None else registro
    problemas = []
    nomes = {}
    for indice, item in enumerate(itens):
        if not isinstance(item, dict):
            problemas.append({"codigo": "ITEM_INVALIDO", "coletor": f"#{indice + 1}", "detalhe": "Entrada nao e dicionario."})
            continue
        nome = item.get("nome")
        identificador = str(nome).strip() if nome is not None else f"#{indice + 1}"
        faltantes = [campo for campo in _CAMPOS_OBRIGATORIOS_COLETOR if campo not in item or item[campo] is None or (isinstance(item[campo], str) and not item[campo].strip())]
        if faltantes:
            problemas.append({"codigo": "METADADO_AUSENTE", "coletor": identificador, "detalhe": "Campos ausentes/vazios: " + ", ".join(faltantes)})
        if nome is not None:
            chave = str(nome).strip().casefold()
            if chave in nomes:
                problemas.append({"codigo": "NOME_DUPLICADO", "coletor": identificador, "detalhe": f"Nome tambem aparece na entrada #{nomes[chave] + 1}."})
            else:
                nomes[chave] = indice
        idade = item.get("idade_maxima_horas")
        if not isinstance(idade, (int, float)) or isinstance(idade, bool) or idade <= 0:
            problemas.append({"codigo": "IDADE_MAXIMA_INVALIDA", "coletor": identificador, "detalhe": "idade_maxima_horas deve ser numero positivo."})
        if "instrumentado" in item and not isinstance(item["instrumentado"], bool):
            problemas.append({"codigo": "INSTRUMENTACAO_INVALIDA", "coletor": identificador, "detalhe": "instrumentado deve ser booleano."})
    presentes = {str(item.get("nome", "")).strip() for item in itens if isinstance(item, dict)}
    for nome in sorted(_COLETORES_CRITICOS - presentes):
        problemas.append({"codigo": "COLETOR_CRITICO_AUSENTE", "coletor": nome, "detalhe": "Coletor critico esperado nao consta no inventario."})
    return problemas
