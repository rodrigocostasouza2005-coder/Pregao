# -*- coding: utf-8 -*-
"""RADAR X - INTELIGENCIA SOCIAL (2026-10-30, pedido explicito do
Rodrigo). Camada que agrega descoberta (data/x_signals.py) +
classificacao + relevancia/credibilidade + cruzamento com outras fontes
do PREGAO + persistencia (sql/x_radar.sql) - NAO e' um segundo Research,
nao e' um segundo Coordenador: reusa cobertura_cruzada_casas
(data/market_researcher.py), obter_noticias (data/news.py), o cache de
IA (data/ia_cache.py) e o registro generico de coletores
(data/coletores_status.py). Ver docs/x-radar-inteligencia-social-
20261030.md pra decisao completa (credencial/custo).

UNIVERSO (CONTAS/TERMOS/TICKERS_FOCO/SETORES/MACRO_ASSUNTOS) e'
deliberadamente um dict Python, nao uma tabela - mesmo padrao de CASAS
em data/research/__init__.py: editar essa lista nunca exige migracao
nem mudanca estrutural de codigo, so' editar o arquivo.

Import: so' data/x_radar/conector.py importa data.x_signals direto
(ver docstring la' e tests/test_x_signals.py test_7). ui/research_tab.py
e jobs/coordenador.py importam SO data.x_radar (este pacote), nunca
data.x_signals."""

VERSAO_CLASSIFICADOR = "x_radar_v1_20261030"

# --- Categoria A/C: empresas B3 + casas de research ja cobertas pelo projeto ---
TICKERS_FOCO = [
    "PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "B3SA3", "RENT3",
    "SUZB3", "GGBR4", "CSNA3", "PRIO3", "RAIL3", "LREN3", "MGLU3", "BBAS3",
]

CONTAS_MONITORADAS = [
    # casas de research oficiais ja presentes em data/research/__init__.py:CASAS
    {"handle": "GenialInveste", "tipo": "institucional", "categoria": "casa_analise"},
    {"handle": "XPInvestimentos", "tipo": "institucional", "categoria": "casa_analise"},
    {"handle": "BTGPactual", "tipo": "institucional", "categoria": "casa_analise"},
    {"handle": "NordResearch", "tipo": "institucional", "categoria": "casa_analise"},
    {"handle": "montebravoinv", "tipo": "institucional", "categoria": "casa_analise"},
    # banco central / autoridades (categoria D)
    {"handle": "BancoCentralBR", "tipo": "institucional", "categoria": "macro"},
    {"handle": "cvmoficial", "tipo": "institucional", "categoria": "macro"},
]
# gestores/investidores/analistas (categoria B) - lista inicial vazia de
# proposito: adicionar um handle aqui SEM verificar se e' conta real e
# publica seria inventar fonte - Rodrigo preenche apos validar cada uma.
CONTAS_GESTORES_INVESTIDORES: list[dict] = []

TERMOS_ACOES = [
    "resultado trimestral", "preço-alvo", "preco-alvo", "recomendação de compra",
    "valuation", "margem líquida", "ROIC", "ROE", "fluxo de caixa", "dividendos",
    "fusão e aquisição", "mudança de tese", "guidance",
]

SETORES_MONITORADOS = [
    "bancos", "seguradoras", "energia elétrica", "petróleo e gás", "mineração",
    "siderurgia", "varejo", "consumo", "construção civil", "tecnologia",
    "telecomunicações", "agronegócio",
]

MACRO_ASSUNTOS = [
    "Copom", "Selic", "IPCA", "inflação", "câmbio", "curva de juros",
    "política fiscal", "política monetária", "petróleo", "minério de ferro",
    "China", "Estados Unidos",
]

CATEGORIAS_PUBLICACAO = (
    "fato_confirmado", "opiniao_analista", "tese_investimento",
    "estimativa_projecao", "rumor_nao_confirmado", "noticia",
    "comentario_macro", "sem_relevancia",
)


def montar_query(*, tickers: list[str] | None = None, termos: list[str] | None = None,
                  contas: list[str] | None = None, max_chars: int = 480) -> str:
    """Monta a query de busca no formato da API do X (termos/cashtags/
    from: combinados com OR) - corta em max_chars (480, com margem pro
    limite de 512 do tier Basic) priorizando tickers > contas > termos,
    nunca corta no meio de um token."""
    partes = []
    for t in (tickers or TICKERS_FOCO):
        partes.append(t)  # busca como termo (cashtag $TICKER so cobre letras na API do X, tickers da B3 tem numero)
    for c in (contas or [c["handle"] for c in CONTAS_MONITORADAS]):
        partes.append(f"from:{c}")
    for termo in (termos or []):
        partes.append(f'"{termo}"')

    query = " OR ".join(partes) + " lang:pt -is:retweet"
    if len(query) <= max_chars:
        return query
    # corta token a token (nunca no meio de uma palavra/termo)
    acumulado = []
    tamanho = len(" lang:pt -is:retweet")
    for p in partes:
        if tamanho + len(p) + 4 > max_chars:
            break
        acumulado.append(p)
        tamanho += len(p) + 4
    return " OR ".join(acumulado) + " lang:pt -is:retweet"


def executar_ciclo() -> dict:
    """Ponto de entrada unico chamado por jobs/coordenador.py (3a funcao
    independente, mesmo padrao de registrar_achados_atuais/
    obter_sintese_mercado - nunca lanca, sempre devolve {'ok':...}).

    Sequencia: verifica credencial (data.x_signals.status_credencial) ->
    se nao 'ok', devolve ok=False com o motivo exato (NUNCA tenta
    coletar) -> senao, coleta (conector.coletar) -> classifica
    (classificador.classificar_lote) -> cruza com outras fontes
    (cruzamento.enriquecer_lote) -> persiste (store.persistir_lote) ->
    registra tentativa em coletores_status (mesmo painel de SAUDE DOS
    DADOS que todo outro coletor usa)."""
    from data import x_signals
    from data.coletores_status import registrar_tentativa
    from data.x_radar import classificador, conector, cruzamento, relevancia, store

    status = x_signals.status_credencial()
    if status["estado"] != "ok":
        registrar_tentativa("X Radar (Inteligência Social)", "api.x.com (desligado)",
                             execucao_ok=True, persistencia_ok=True, registros_novos=0,
                             categoria="Research", erro=None, parcial=False)
        return {"ok": False, "motivo": status["motivo"], "estado": status["estado"], "sinais_novos": 0}

    try:
        sinais_brutos, info_consumo = conector.coletar()
        store.registrar_consumo(info_consumo)
        classificados = classificador.classificar_lote(sinais_brutos)
        enriquecidos = cruzamento.enriquecer_lote(classificados)
        enriquecidos = relevancia.aplicar_relevancia_credibilidade(enriquecidos)
        novos = store.persistir_lote(enriquecidos)
        registrar_tentativa("X Radar (Inteligência Social)", "api.x.com", execucao_ok=True,
                             persistencia_ok=True, registros_novos=novos, categoria="Research")
        return {"ok": True, "sinais_novos": novos, "estado": "ok", "motivo": None}
    except Exception as exc:
        registrar_tentativa("X Radar (Inteligência Social)", "api.x.com", execucao_ok=False,
                             persistencia_ok=False, registros_novos=0, categoria="Research", erro=repr(exc))
        return {"ok": False, "motivo": repr(exc), "estado": "erro_execucao", "sinais_novos": 0}
