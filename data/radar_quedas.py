# -*- coding: utf-8 -*-
"""Radar persistente de quedas em carteiras recomendadas.

Fontes estruturadas habilitadas: recomendações públicas da Genial Analisa
e a carteira mensal pública "Top 10 Ações" da Safra Corretora (2026-10-16
- ver data/research/safra_carteiras.py pra evidência real de que essa
fonte é acessível, diferente de Genial/XP/BTG, bloqueadas na borda
Akamai mesmo fora do sandbox). Cada casa é tratada de forma INDEPENDENTE
em processar_monitoramento(): uma fonte bloqueada nunca invalida nem
desativa as recomendações vigentes de outra fonte que respondeu
normalmente. Outras casas só entram quando houver coletor de carteiras
públicas acessível e dados de validade confiáveis.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from data.prices import obter_cotacao, obter_data_ultimo_pregao
from data.research.genial_carteiras import coletar_carteiras as _coletar_genial
from data.research.safra_carteiras import coletar_carteiras as _coletar_safra
from data.supabase_client import obter_cliente

TZ_SP = ZoneInfo("America/Sao_Paulo")
LIMIAR_VARIACAO = -4.0
# Carteiras aqui sao produtos MENSAIS (Genial/Safra) - uma linha "vigente"
# cuja ultima confirmacao real (verificado_em) passou desse limite quer
# dizer que a fonte ficou fora do ar por tempo demais pra continuar
# confiando nela como "carteira atual" (ver listar_carteiras). Folga de
# ~10 dias alem do ciclo mensal de 30/31 dias pra nao expirar por um
# fim de semana prolongado ou alguns dias de bloqueio pontual da fonte.
IDADE_MAXIMA_CARTEIRA_DIAS = 40
# Limite BEM mais curto que IDADE_MAXIMA_CARTEIRA_DIAS - so' pra rotular
# "atualizada" vs "desatualizada" na UI (ver resumo_fontes_vigentes). O
# cron roda a cada 15min em dia de pregao (.github/workflows/radar-
# morning-call.yml) e salvar_carteiras() bate verificado_em em TODA
# confirmacao bem-sucedida, mesmo sem mudanca de composicao - uma casa
# saudavel nunca deveria ficar mais que um fim de semana (~65h entre a
# ultima execucao de sexta e a primeira de segunda) sem confirmar. 72h
# cobre um fim de semana normal + folga, sem marcar falso-desatualizada
# toda segunda de manha antes do primeiro cron do dia.
IDADE_FRESCA_HORAS = 72
CASA_GENIAL = "Genial Analisa"
CASA_SAFRA = "Safra Corretora"
# Casas com coletor de carteira configurado (ordem de exibicao na UI). Uma
# casa daqui sem carteira vigente aparece como INDISPONIVEL - nunca some
# da tela, pra cobertura parcial nao parecer cobertura completa.
CASAS_MONITORADAS = (CASA_SAFRA, CASA_GENIAL)
# So' pra UI destacar "chegando perto do gatilho" - nao gera alerta nem
# e-mail (a regra de alerta continua LIMIAR_VARIACAO, estrita).
LIMIAR_ATENCAO = -2.5


def calcular_queda(preco_atual, fechamento_anterior):
    """Retorna variação percentual válida; None para valores inválidos."""
    try:
        atual, anterior = float(preco_atual), float(fechamento_anterior)
    except (TypeError, ValueError):
        return None
    if atual <= 0 or anterior <= 0:
        return None
    variacao = round((atual / anterior - 1) * 100, 8)
    return variacao if variacao == variacao and abs(variacao) != float("inf") else None


def deve_alertar(variacao_pct):
    """Regra estrita: -4,00% não alerta; -4,01% alerta."""
    try:
        return float(variacao_pct) < LIMIAR_VARIACAO
    except (TypeError, ValueError):
        return False


def normalizar_ticker(valor):
    ticker = str(valor or "").strip().upper()
    return ticker if ticker and len(ticker) <= 12 else ""


def coletar_carteiras_genial():
    """Coleta somente carteiras mensais oficiais e validadas da Genial."""
    return _coletar_genial()


def coletar_carteiras_safra():
    """Coleta a carteira mensal pública "Top 10 Ações" da Safra Corretora."""
    return _coletar_safra()


def salvar_carteiras(casa, itens):
    """Upsert + reativação ESCOPADOS a uma única casa - uma falha ou
    ausência de outra casa nunca desativa as recomendações vigentes
    desta (ver processar_monitoramento, que chama isto por fonte)."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        if itens:
            cliente.table("radar_carteiras_recomendadas").upsert(
                itens, on_conflict="casa,ticker,carteira"
            ).execute()
        cliente.table("radar_carteiras_recomendadas").update(
            {"vigente": False}
        ).eq("casa", casa).execute()
        chaves = {(i["ticker"], i["carteira"]) for i in itens}
        # Reativa somente as recomendações confirmadas nesta coleta.
        for ticker, carteira in chaves:
            cliente.table("radar_carteiras_recomendadas").update(
                {"vigente": True, "verificado_em": datetime.now(timezone.utc).isoformat(),
                 "status_coleta": "COLETADO"}
            ).eq("casa", casa).eq("ticker", ticker).eq("carteira", carteira).execute()
        return True
    except Exception as exc:
        print(f"[radar_quedas] falha ao persistir carteiras ({casa}): {exc!r}")
        return False


def _carteira_expirada(linha, agora=None):
    """True se `verificado_em` da linha passou de IDADE_MAXIMA_CARTEIRA_DIAS
    - a fonte confirmou essa recomendação pela última vez há tempo demais
    pra continuar tratando como carteira atual (ver constante acima).
    Campo ausente/malformado -> False (fail open, mesmo espírito do resto
    do projeto: nunca trava por um dado opcional malformado)."""
    agora = agora or datetime.now(timezone.utc)
    verificado = linha.get("verificado_em")
    if not verificado:
        return False
    try:
        quando = datetime.fromisoformat(str(verificado).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (agora - quando) > timedelta(days=IDADE_MAXIMA_CARTEIRA_DIAS)


def listar_carteiras():
    """Recomendações vigentes (todas as casas), excluindo as EXPIRADAS
    (ver _carteira_expirada) - uma carteira mensal cuja fonte parou de
    confirmar há tempo demais não é apresentada como atual, mesmo que a
    flag `vigente` no banco ainda esteja True (ela só vira False quando a
    PRÓPRIA fonte confirma uma mudança - ver salvar_carteiras)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (cliente.table("radar_carteiras_recomendadas").select("*")
                .eq("vigente", True).order("casa").execute())
        linhas = resp.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao ler carteiras: {exc!r}")
        return None
    agora = datetime.now(timezone.utc)
    return [linha for linha in linhas if not _carteira_expirada(linha, agora)]


def avaliar_ticker(ticker, cotacao, recomendacoes, agora=None):
    """Gera um evento candidato se preço e fechamento anterior forem válidos."""
    agora = agora or datetime.now(TZ_SP)
    if not isinstance(cotacao, dict) or cotacao.get("erro"):
        return None
    preco = cotacao.get("preco")
    anterior = cotacao.get("fechamento_anterior")
    if anterior is None:
        # O provedor existente expõe previousClose internamente, mas o retorno
        # padrão não o publica. Não substituímos por preço estimado.
        return None
    variacao = calcular_queda(preco, anterior)
    if variacao is None or not deve_alertar(variacao):
        return None
    relacionados = [r for r in recomendacoes if normalizar_ticker(r.get("ticker")) == ticker]
    if not relacionados:
        return None
    # "pregao" = data da ultima negociacao segundo o provedor (ver
    # processar_monitoramento/obter_data_ultimo_pregao), nao a data do
    # relogio: num feriado em dia util o Yahoo devolve a cotacao do pregao
    # anterior, e usar a data de hoje criava um evento "novo" duplicado.
    pregao = cotacao.get("pregao") or agora.date()
    return {
        "ticker": ticker, "empresa": next((r.get("empresa") for r in relacionados if r.get("empresa")), ""),
        "preco_atual": float(preco), "fechamento_anterior": float(anterior),
        "variacao_pct": variacao, "cotacao_em": cotacao.get("cotacao_em") or agora.isoformat(),
        "tipo_cotacao": cotacao.get("tipo_cotacao") or "ATRASADA/PROVEDOR GRATUITO",
        "pregao": pregao.isoformat(),
        "casas": sorted({r.get("casa", "") for r in relacionados if r.get("casa")}),
        "carteiras": sorted({r.get("carteira", "") for r in relacionados if r.get("carteira")}),
        "fontes": sorted({r.get("fonte_url", "") for r in relacionados if r.get("fonte_url")}),
        "status": "PENDENTE_ENVIO",
    }


def _mesma_cotacao(anterior, alerta, tolerancia=1e-6):
    """True se preco_atual/fechamento_anterior do alerta novo baterem com o
    ULTIMO alerta persistido desse ticker (qualquer pregao). O calendario
    de pregoes da B3 nao esta' modelado aqui (cron roda todo dia util,
    sem excluir feriado) - num feriado o yfinance devolve a MESMA cotacao
    do ultimo pregao real (sem negocio novo), e o pregao calculado (data
    de hoje) muda mesmo sem evento de mercado novo. Sem esta checagem,
    isso duplicaria o e-mail do mesmo evento de queda sob uma chave
    (ticker, pregao) nova."""
    try:
        return (
            abs(float(anterior.get("preco_atual")) - float(alerta.get("preco_atual"))) < tolerancia
            and abs(float(anterior.get("fechamento_anterior")) - float(alerta.get("fechamento_anterior"))) < tolerancia
        )
    except (TypeError, ValueError):
        return False


def registrar_alerta(alerta):
    """Idempotência no banco por ticker + pregão; não duplica entre carteiras.

    Tambem nao duplica quando a cotacao do pregao novo e' IDENTICA ao
    ultimo alerta ja' persistido desse ticker (ver _mesma_cotacao) - sinal
    de que nao houve negociacao nova (feriado em dia util, por exemplo),
    nao um evento de queda novo."""
    cliente = obter_cliente()
    if cliente is None:
        return False, None
    try:
        existente = (cliente.table("radar_alertas_queda").select("id")
                     .eq("ticker", alerta["ticker"]).eq("pregao", alerta["pregao"])
                     .limit(1).execute())
        if existente.data:
            return True, None
        ultimo = (cliente.table("radar_alertas_queda").select("preco_atual,fechamento_anterior")
                  .eq("ticker", alerta["ticker"]).order("pregao", desc=True).limit(1).execute())
        if ultimo.data and _mesma_cotacao(ultimo.data[0], alerta):
            print(
                f"[radar_quedas] cotação de {alerta['ticker']} idêntica ao último alerta "
                f"já registrado (pregão {alerta['pregao']}); sem negociação nova detectada "
                "(provável feriado) - não duplica envio"
            )
            return True, None
        resp = cliente.table("radar_alertas_queda").insert(alerta).execute()
        return bool(resp.data), (resp.data[0].get("id") if resp.data else None)
    except Exception as exc:
        print(f"[radar_quedas] falha ao registrar alerta: {exc!r}")
        return False, None


def processar_monitoramento():
    """Atualiza cada fonte de carteira de forma INDEPENDENTE e avalia as
    recomendações vigentes resultantes. Envio fica no worker.

    coleta_ok=True se PELO MENOS UMA fonte persistiu uma composição
    válida nesta execução (ver `status_fontes` no retorno pro detalhe por
    casa) - uma fonte bloqueada/vazia/com falha de persistência NUNCA
    impede a avaliação das recomendações de outra fonte que respondeu
    normalmente, nem desativa as recomendações vigentes da própria fonte
    que falhou agora (permanecem vigentes até ELA MESMA confirmar uma
    mudança real numa execução futura - mesmo motivo de salvar_carteiras
    só desativar/reativar pela própria casa). Só retorna coleta_ok=False
    (monitoramento totalmente suspenso) quando TODAS as fontes
    configuradas falharem/forem rejeitadas nesta execução."""
    status_fontes = {}
    pelo_menos_uma_ok = False
    for casa, coletor in ((CASA_GENIAL, coletar_carteiras_genial), (CASA_SAFRA, coletar_carteiras_safra)):
        snapshot = coletor()
        if snapshot is None:
            status_fontes[casa] = "fonte indisponível"
            continue
        # Uma resposta vazia pode indicar mudança no HTML/PDF ou coleta
        # parcial. Não desativa a última carteira válida DESTA casa até
        # confirmar que a fonte entregou uma composição real; isso evita
        # transformar falha de parsing em "zero ativos".
        if not snapshot:
            status_fontes[casa] = "snapshot vazio, rejeitado (carteira anterior preservada)"
            continue
        if not salvar_carteiras(casa, snapshot):
            status_fontes[casa] = "falha ao persistir (carteira anterior preservada)"
            continue
        status_fontes[casa] = f"ok ({len(snapshot)} recomendações)"
        pelo_menos_uma_ok = True

    resumo_fontes = "; ".join(f"{casa}: {status}" for casa, status in status_fontes.items())
    if not pelo_menos_uma_ok:
        return {
            "coleta_ok": False, "alertas_novos": [],
            "erro": f"Todas as fontes de recomendações indisponíveis ou rejeitadas nesta execução. {resumo_fontes}",
            "fontes": status_fontes,
        }
    recomendacoes = listar_carteiras()
    if recomendacoes is None:
        return {"coleta_ok": True, "alertas_novos": [], "erro": f"Supabase indisponível para leitura. {resumo_fontes}", "fontes": status_fontes}
    tickers = sorted({normalizar_ticker(r.get("ticker")) for r in recomendacoes} - {""})
    novos = []
    falhas_cotacao = 0
    for ticker in tickers:
        cotacao = obter_cotacao(ticker)
        if isinstance(cotacao, dict) and not cotacao.get("erro"):
            pregao = obter_data_ultimo_pregao(ticker)
            if pregao is not None:
                cotacao = {**cotacao, "pregao": pregao}
        else:
            # Sem isto, um provedor de cotação bloqueado (ex: IP de
            # datacenter do runner, diferente do IP onde o app roda - já
            # documentado pra yfinance em data/prices.py) faz TODOS os
            # tickers caírem em avaliar_ticker()->None silenciosamente: a
            # execução reporta coleta_ok=True e "nenhuma queda" fica
            # indistinguível de "não conseguimos nem checar". Ver
            # jobs/radar_quedas.py, que propaga este dado pro painel
            # SAÚDE DOS DADOS via `erro`/`parcial`.
            falhas_cotacao += 1
        alerta = avaliar_ticker(ticker, cotacao, recomendacoes)
        if alerta:
            ok, alerta_id = registrar_alerta(alerta)
            if ok and alerta_id is not None:
                alerta["id"] = alerta_id
                novos.append(alerta)
    mensagens = []
    if any(not status.startswith("ok") for status in status_fontes.values()):
        mensagens.append(f"Execução parcial: {resumo_fontes}")
    if falhas_cotacao:
        mensagens.append(
            f"Cotação indisponível para {falhas_cotacao}/{len(tickers)} ticker(s) monitorado(s) "
            "(provedor de cotação - ver data/prices.py:obter_cotacao)"
        )
    return {
        "coleta_ok": True, "alertas_novos": novos, "total_tickers": len(tickers),
        "fontes": status_fontes, "cotacoes_falhas": falhas_cotacao,
        "erro": ("; ".join(mensagens) if mensagens else None),
    }


@st.cache_data(ttl=60, show_spinner=False)
def alertas_periodo(dias=7):
    """Alertas com pregao nos ultimos `dias` dias corridos (hoje incluso),
    mais recente primeiro - filtrado NO BANCO (substitui o antigo
    alertas_recentes(limite=100), cujo corte fixo podia esconder alertas
    antigos dentro do periodo pedido). None se o Supabase estiver indisponivel."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    desde = (datetime.now(TZ_SP).date() - timedelta(days=max(int(dias), 1) - 1)).isoformat()
    try:
        resp = (cliente.table("radar_alertas_queda").select("*")
                .gte("pregao", desde)
                .order("pregao", desc=True).order("variacao_pct").limit(1000).execute())
        return resp.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao ler alertas: {exc!r}")
        return None


def classificar_variacao(variacao_pct):
    """Estado de um ativo monitorado pra UI: ALERTA (regra estrita do
    monitor, deve_alertar), ATENCAO (<= LIMIAR_ATENCAO, ainda sem alerta),
    NORMAL, ou SEM_COTACAO (variacao None)."""
    if variacao_pct is None:
        return "SEM_COTACAO"
    if deve_alertar(variacao_pct):
        return "ALERTA"
    if variacao_pct <= LIMIAR_ATENCAO:
        return "ATENCAO"
    return "NORMAL"


def linhas_monitorados(recomendacoes, cotacoes):
    """Uma linha por TICKER monitorado (consolida casas/carteiras), com a
    variacao do dia calculada pela MESMA regra do monitor (calcular_queda
    sobre preco/fechamento anterior). Pura (sem rede) - recomendacoes vem
    de listar_carteiras(), cotacoes de obter_cotacao() por ticker.
    Ordenada da maior queda pra maior alta; sem cotacao vai pro fim."""
    por_ticker = {}
    for r in recomendacoes or []:
        ticker = normalizar_ticker(r.get("ticker"))
        if not ticker:
            continue
        linha = por_ticker.setdefault(ticker, {"ticker": ticker, "empresa": "", "casas": set(), "carteiras": set()})
        linha["empresa"] = linha["empresa"] or (r.get("empresa") or "")
        if r.get("casa"):
            linha["casas"].add(r["casa"])
        if r.get("carteira"):
            linha["carteiras"].add(r["carteira"])
    linhas = []
    for ticker, linha in por_ticker.items():
        cot = cotacoes.get(ticker) if isinstance(cotacoes, dict) else None
        valida = isinstance(cot, dict) and not cot.get("erro")
        preco = cot.get("preco") if valida else None
        anterior = cot.get("fechamento_anterior") if valida else None
        variacao = calcular_queda(preco, anterior) if valida else None
        linhas.append({
            "ticker": ticker, "empresa": linha["empresa"],
            "casas": sorted(linha["casas"]), "carteiras": sorted(linha["carteiras"]),
            "preco": preco if variacao is not None else None,
            "fechamento_anterior": anterior if variacao is not None else None,
            "variacao_pct": variacao,
            "distancia_gatilho_pp": (variacao - LIMIAR_VARIACAO) if variacao is not None else None,
            "estado": classificar_variacao(variacao),
        })
    linhas.sort(key=lambda l: (l["variacao_pct"] is None, l["variacao_pct"] if l["variacao_pct"] is not None else 0))
    return linhas


@st.cache_data(ttl=60, show_spinner=False)
def painel_monitorados():
    """linhas_monitorados() sobre as carteiras vigentes + cotacao atual de
    cada ticker (obter_cotacao, cache proprio de 30s). None se o Supabase
    estiver indisponivel; [] se nenhuma carteira vigente."""
    recomendacoes = listar_carteiras()
    if recomendacoes is None:
        return None
    tickers = sorted({normalizar_ticker(r.get("ticker")) for r in recomendacoes} - {""})
    cotacoes = {t: obter_cotacao(t) for t in tickers}
    return linhas_monitorados(recomendacoes, cotacoes)


def _desatualizada(verificado_em, agora=None):
    """True se `verificado_em` passou de IDADE_FRESCA_HORAS - distinto de
    _carteira_expirada (IDADE_MAXIMA_CARTEIRA_DIAS): uma linha pode estar
    "vigente" (ainda aparece em listar_carteiras, dentro do prazo de
    expiracao) mas com a ultima confirmacao velha o bastante pra avisar o
    usuario, sem ainda justificar remover a carteira da lista. Mesmo
    fail-open de _carteira_expirada: campo ausente/malformado -> False."""
    agora = agora or datetime.now(timezone.utc)
    if not verificado_em:
        return False
    try:
        quando = datetime.fromisoformat(str(verificado_em).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (agora - quando) > timedelta(hours=IDADE_FRESCA_HORAS)


def resumo_fontes_vigentes():
    """Resumo por casa (CASA_GENIAL/CASA_SAFRA) das carteiras VIGENTES e
    NAO EXPIRADAS (reaproveita listar_carteiras, sem nenhuma chamada de
    rede nova) - pra UI responder 'quais fontes estao atualizadas agora'
    sem precisar abrir SAUDE DOS DADOS. Cada casa presente carrega
    "desatualizada" (ver _desatualizada/IDADE_FRESCA_HORAS) pra UI
    distinguir "atualizada" de "vigente mas sem confirmacao recente" -
    sem isso, uma carteira confirmada ha' 39 dias (ainda dentro de
    IDADE_MAXIMA_CARTEIRA_DIAS=40, ainda listada) apareceria como
    "atualizada" igual a uma confirmada ha' 1 hora. Uma casa AUSENTE do
    resultado significa que ela nao tem nenhuma recomendacao vigente e
    nao-expirada agora (bloqueada na ultima coleta, nunca coletada, ou
    expirada por IDADE_MAXIMA_CARTEIRA_DIAS) - UI decide o rotulo "sem
    dados"/"indisponivel", esta funcao so' agrega o fato. None se o
    Supabase estiver indisponivel pra leitura (mesmo contrato de
    listar_carteiras)."""
    linhas = listar_carteiras()
    if linhas is None:
        return None
    por_casa = {}
    for linha in linhas:
        casa = linha.get("casa") or "—"
        info = por_casa.setdefault(casa, {"ativos": set(), "verificado_em": None, "carteiras": set(), "data_publicacao": None})
        if linha.get("ticker"):
            info["ativos"].add(linha["ticker"])
        if linha.get("carteira"):
            info["carteiras"].add(linha["carteira"])
        publicacao = linha.get("data_publicacao")
        if publicacao and (info["data_publicacao"] is None or str(publicacao) > str(info["data_publicacao"])):
            info["data_publicacao"] = publicacao
        verificado = linha.get("verificado_em")
        if verificado and (info["verificado_em"] is None or str(verificado) > str(info["verificado_em"])):
            info["verificado_em"] = verificado
    return {
        casa: {
            "ativos": len(info["ativos"]),
            "verificado_em": info["verificado_em"],
            "desatualizada": _desatualizada(info["verificado_em"]),
            "carteiras": sorted(info["carteiras"]),
            "data_publicacao": info["data_publicacao"],
        }
        for casa, info in por_casa.items()
    }
