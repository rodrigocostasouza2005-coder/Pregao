# -*- coding: utf-8 -*-
"""Persistencia dos itens de research no Supabase (tabela research_itens,
ver sql/research.sql). So metadados do relatorio + resumo por IA com
palavras proprias sao gravados - nunca o texto completo do relatorio
original."""

from datetime import datetime, timedelta, timezone

from data.supabase_client import obter_cliente

TTL_RECOLETA_MIN = 30
RETENCAO_DIAS = 5

# Tamanho do lote na consulta das versoes atuais feita por
# _versionar_antes_do_upsert. Bug real (auditoria 2026-11-26): o
# `select(...).in_("link", links)` era montado com TODOS os links do lote
# de uma vez e o PostgREST recebe o filtro `in` na QUERY STRING - numa
# coleta grande (CVM, ~700 documentos numa rodada; links de 100+
# caracteres cada) a URL estourava antes de sair da maquina
# (httpx.InvalidURL: "query too long", ou "JSON could not be generated"),
# a excecao caia no except de melhor-esforco e NENHUMA versao anterior era
# arquivada - silenciosamente, so' com um print no console. Dividir em
# lotes mantem cada URL curta; 150 links por consulta deixa a query
# string na casa de ~20 KB no pior caso realista, bem abaixo de qualquer
# limite de cliente/servidor.
_LOTE_CONSULTA_VERSIONAMENTO = 150

# Ultima falha TOTAL de versionamento (todos os lotes da consulta
# falharam) - setada por salvar_itens e consumida por
# data/research/__init__.py:coletar_casa, que e' quem tem o contexto da
# casa pra registrar isso em registrar_tentativa (SAUDE DOS DADOS). Antes
# desta correcao a falha morria num print: nunca chegava a nenhum
# registro persistido. Leitura/escrita sempre no mesmo passo sequencial
# de coleta (nenhum coletor de research roda em paralelo).
_ultima_falha_versionamento = None


def consumir_falha_versionamento() -> str | None:
    """Devolve (e zera) a descricao da ultima falha TOTAL de
    versionamento registrada por salvar_itens. None quando a ultima
    chamada de salvar_itens conseguiu consultar as versoes atuais (o caso
    normal) - 'zera ao ler' garante que a falha de uma casa nunca seja
    atribuida a' casa seguinte."""
    global _ultima_falha_versionamento
    falha, _ultima_falha_versionamento = _ultima_falha_versionamento, None
    return falha


def _linha_para_item(linha: dict) -> dict:
    """Converte uma linha do banco pro mesmo formato que os coletores
    (data/research/genial.py etc.) retornam, mais resumo/modelo_resumo
    quando ja tiverem sido gerados."""
    return {
        "casa": linha["casa"], "titulo": linha["titulo"], "data": linha.get("data") or "",
        "autor": linha.get("autor") or "", "tipo": linha["tipo"],
        "tickers": linha.get("tickers") or [], "link": linha["link"],
        "resumo": linha.get("resumo"), "modelo_resumo": linha.get("modelo_resumo"),
        "preco_alvo": linha.get("preco_alvo"), "recomendacao": linha.get("recomendacao"),
        "coletado_em": linha.get("coletado_em"),
        # fase 3 (feed editorial NEWS+RESEARCH): timestamp completo de
        # publicacao, hoje so' preenchido pelas lives da Genial (ver
        # data/research/genial_lives.py) - None pras demais casas/linhas
        # coletadas antes dessa coluna existir (coluna pode nem existir
        # ainda no banco - .get() cobre os dois casos sem quebrar).
        "publicado_em": linha.get("publicado_em"),
    }


def listar_itens(casas: list) -> list | None:
    """Itens salvos das casas dadas (nomes, ex: 'Genial Analisa'), mais
    recentes primeiro. None se o banco estiver fora do ar."""
    if not casas:
        return []
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("research_itens")
            .select("*")
            .in_("casa", casas)
            .order("data", desc=True)
            .execute()
        )
        return [_linha_para_item(r) for r in resp.data]
    except Exception as exc:
        print(f"[research.store] listar_itens({casas!r}) falhou: {exc!r}")
        return None


def ultima_coleta_em(casa: str) -> datetime | None:
    """Timestamp da coleta mais recente salva pra uma casa. None se nao
    houver nenhum item salvo ou o banco estiver fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        resp = (
            cliente.table("research_itens")
            .select("coletado_em")
            .eq("casa", casa)
            .order("coletado_em", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return datetime.fromisoformat(resp.data[0]["coletado_em"])
    except Exception as exc:
        print(f"[research.store] ultima_coleta_em({casa!r}) falhou: {exc!r}")
        return None


def precisa_recoletar(casa: str, minutos: int = TTL_RECOLETA_MIN) -> bool:
    """True se a casa nunca foi coletada ou a ultima coleta salva tem mais
    de `minutos`. Se o banco estiver fora do ar (ultima_coleta_em -> None
    de forma indistinguivel de 'nunca coletado'), tambem retorna True -
    quem chama decide o que fazer se a coleta/gravacao falhar de novo."""
    ultima = ultima_coleta_em(casa)
    if ultima is None:
        return True
    return (datetime.now(timezone.utc) - ultima) > timedelta(minutes=minutos)


# Colunas ADITIVAS do contrato ampliado (auditoria de arquitetura
# 2026-11-12 - ver data/research/base.py, topo do modulo, pra que' serve
# cada uma) - podem nao existir ainda no banco de quem esta rodando (ver
# sql/research_itens_contrato_padrao.sql, PROPOSTO mas nunca aplicado por
# este agente). 'publicado_em' (fase 3) e' a mais antiga do grupo, mesmo
# padrao defensivo desde entao: so' entram no payload quando pelo menos 1
# item do LOTE realmente tiver o campo, e se o UPSERT falhar por causa
# delas, salvar_itens tenta de novo SEM elas antes de desistir - nunca
# quebra a coleta de TODAS as casas so' porque uma coluna nova ainda nao
# existe no banco de quem esta rodando.
_CAMPOS_AMPLIADOS_CONTRATO = (
    "publicado_em", "empresa", "setor", "preco_referencia", "horizonte",
    "texto_integral_disponivel",
)

# Campos que, se DIFERENTES do que ja' esta' salvo pro mesmo link,
# caracterizam uma "nova versao" do relatorio (ex: fonte corrigiu o
# titulo, ou repetiu o mesmo link com data de republicacao diferente) -
# usado so' por _arquivar_versao_anterior (ver docstring la'). Nao inclui
# 'autor'/'tickers' de proposito: variam menos e mudanca isolada neles
# tende a ser normalizacao de parsing, nao uma nova versao de conteudo.
_CAMPOS_VERSAO = ("titulo", "data")


def contar_duplicados(itens: list) -> int:
    """Quantos itens de `itens` tem um link JA' visto antes na MESMA
    lista (len(itens) - numero de links UNICOS) - metrica pura (ver
    data/research/__init__.py:coletar_casa), nunca usada pra decisao de
    persistencia (salvar_itens abaixo faz o dedup de verdade, por conta
    propria). Item sem 'link' e' ignorado (nunca lanca KeyError so' pra
    contar). [] -> 0."""
    if not itens:
        return 0
    links = [it.get("link") for it in itens if it.get("link")]
    return len(links) - len(set(links))


def salvar_itens(itens: list) -> bool:
    """Upsert em lote por link. So envia as colunas de metadado (nunca
    resumo/modelo_resumo) - o upsert do PostgREST so mexe nas colunas
    presentes no payload, entao resumos ja salvos de uma coleta anterior
    nao sao apagados quando o item e' recoletado.

    Deduplica por link antes de enviar (mantem a ultima ocorrencia) - um
    upsert com o mesmo link repetido dentro do MESMO lote falha inteiro
    no Postgres ("ON CONFLICT DO UPDATE command cannot affect row a
    second time"); pode acontecer se a fonte listar o mesmo relatorio em
    mais de uma categoria (confirmado em teste com a XP).

    Colunas ADITIVAS do contrato ampliado (ver _CAMPOS_AMPLIADOS_CONTRATO)
    so' vao no payload quando pelo menos 1 item do lote tiver o campo - e
    se o UPSERT falhar por causa delas (Supabase do usuario ainda sem
    rodar a migracao proposta), tenta de novo SEM elas antes de desistir:
    nunca quebra a coleta de TODAS as casas so' porque uma coluna nova
    ainda nao existe no banco de quem esta rodando.

    Versionamento (auditoria de arquitetura 2026-11-12): ANTES do upsert,
    arquiva em research_itens_historico (tabela PROPOSTA, melhor esforco -
    ver _versionar_antes_do_upsert abaixo) a linha anterior de todo link
    cujo titulo/data vai mudar nesta coleta - uma nova versao de
    relatorio nunca mais sobrescreve a anterior em silencio total, mesmo
    antes da migracao ser aplicada (degrada pra 'sem historico', nunca
    pra 'upsert falhou')."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    if not itens:
        return True
    itens = list({it["link"]: it for it in itens}.values())
    agora = datetime.now(timezone.utc).isoformat()

    global _ultima_falha_versionamento
    _ultima_falha_versionamento = None  # nunca herda a falha da casa anterior
    _versionar_antes_do_upsert(cliente, itens)

    campos_presentes = [
        campo for campo in _CAMPOS_AMPLIADOS_CONTRATO
        if any(it.get(campo) not in (None, "") for it in itens)
    ]
    linhas = [
        {
            "link": it["link"], "casa": it["casa"], "titulo": it["titulo"],
            "data": it.get("data") or None, "autor": it.get("autor") or None,
            "tipo": it["tipo"], "tickers": it.get("tickers") or [],
            "coletado_em": agora,
            **{campo: it.get(campo) for campo in campos_presentes},
        }
        for it in itens
    ]
    try:
        cliente.table("research_itens").upsert(linhas, on_conflict="link").execute()
        return True
    except Exception as exc:
        if not campos_presentes:
            print(f"[research.store] salvar_itens falhou ({len(linhas)} linha(s)): {exc!r}")
            return False
        print(
            f"[research.store] salvar_itens falhou com {campos_presentes!r} presente(s) "
            f"({len(linhas)} linha(s)): {exc!r} - tentando de novo sem essas colunas"
        )
        linhas_legado = [{k: v for k, v in linha.items() if k not in campos_presentes} for linha in linhas]
        try:
            cliente.table("research_itens").upsert(linhas_legado, on_conflict="link").execute()
            return True
        except Exception as exc2:
            print(f"[research.store] salvar_itens falhou mesmo sem {campos_presentes!r}: {exc2!r}")
            return False


def _ler_versoes_atuais(cliente, links: list) -> tuple[list, int, int]:
    """Linhas atuais de research_itens pros `links` dados, consultadas em
    lotes de _LOTE_CONSULTA_VERSIONAMENTO (ver o comentario da constante:
    um unico `in_` com todos os links estourava a URL em coleta grande).

    Devolve (linhas, lotes_com_falha, total_de_lotes). Um lote que falha
    nunca derruba os outros - versionar as versoes anteriores que DERAM
    pra ler e' melhor que nao versionar nenhuma; o chamador usa a
    contagem pra saber se a falha foi total (ai' sim e' registrada de
    verdade, ver consumir_falha_versionamento)."""
    linhas = []
    lotes_com_falha = 0
    total_lotes = 0
    for inicio in range(0, len(links), _LOTE_CONSULTA_VERSIONAMENTO):
        fatia = links[inicio:inicio + _LOTE_CONSULTA_VERSIONAMENTO]
        total_lotes += 1
        try:
            resp = cliente.table("research_itens").select("*").in_("link", fatia).execute()
            linhas.extend(resp.data or [])
        except Exception as exc:
            lotes_com_falha += 1
            print(
                f"[research.store] versionamento: leitura das versoes atuais falhou no lote "
                f"{total_lotes} ({len(fatia)} link(s)) (ignorado): {exc!r}"
            )
    return linhas, lotes_com_falha, total_lotes


def _versionar_antes_do_upsert(cliente, itens: list) -> None:
    """Implementacao real de _arquivar_versao_anterior (ver docstring de
    salvar_itens) - funcao separada (nao inline) pra poder ser testada
    isolada, mockando so' `cliente`. Melhor esforco SEMPRE: qualquer
    excecao (leitura OU escrita) so' loga e retorna, nunca propaga -
    quem chama (salvar_itens) sempre segue pro upsert principal.

    A consulta das versoes atuais e' fatiada (_ler_versoes_atuais); se
    TODOS os lotes falharem - ou seja, fatiar nao resolveu -, a falha fica
    registrada em _ultima_falha_versionamento pra chegar ao painel de
    Saude dos Dados via coletar_casa, em vez de morrer num print."""
    global _ultima_falha_versionamento
    links = [it["link"] for it in itens if it.get("link")]
    if not links:
        return
    existentes, lotes_com_falha, total_lotes = _ler_versoes_atuais(cliente, links)
    if lotes_com_falha and lotes_com_falha == total_lotes:
        _ultima_falha_versionamento = (
            f"VERSIONAMENTO: consulta das versoes atuais falhou em {lotes_com_falha}/"
            f"{total_lotes} lote(s) de ate' {_LOTE_CONSULTA_VERSIONAMENTO} links "
            f"({len(links)} links no total) - nenhuma versao anterior foi arquivada "
            "nesta coleta (upsert principal nao foi afetado)"
        )
    if not existentes:
        return
    por_link_novo = {it["link"]: it for it in itens}
    agora = datetime.now(timezone.utc).isoformat()
    linhas_historico = []
    for anterior in existentes:
        novo = por_link_novo.get(anterior["link"])
        if novo is None:
            continue
        mudou = any((anterior.get(c) or None) != (novo.get(c) or None) for c in _CAMPOS_VERSAO)
        if not mudou:
            continue
        linhas_historico.append({
            "link": anterior["link"], "casa": anterior.get("casa"), "titulo": anterior.get("titulo"),
            "data": anterior.get("data"), "autor": anterior.get("autor"), "tipo": anterior.get("tipo"),
            "tickers": anterior.get("tickers") or [], "resumo": anterior.get("resumo"),
            "modelo_resumo": anterior.get("modelo_resumo"), "preco_alvo": anterior.get("preco_alvo"),
            "recomendacao": anterior.get("recomendacao"), "coletado_em": anterior.get("coletado_em"),
            "substituido_em": agora,
        })
    if not linhas_historico:
        return
    try:
        cliente.table("research_itens_historico").insert(linhas_historico).execute()
        print(f"[research.store] versionamento: {len(linhas_historico)} versao(oes) anterior(es) arquivada(s)")
    except Exception as exc:
        # tabela PROPOSTA (sql/research_itens_historico.sql) pode nao
        # existir ainda no banco de quem esta rodando - versionamento e'
        # aditivo/melhor-esforco, nunca bloqueia o upsert principal.
        print(f"[research.store] versionamento: insert no historico falhou (tabela pode nao existir ainda, ignorado): {exc!r}")


# Nord (data/research/nord.py) não tem RSS - descoberta é via sitemap/
# lastmod, com latência real de semanas a meses entre a publicação do
# post ('data') e o momento em que o coletor o encontra (confirmado com
# coleta real em 2026-11-02: 8 itens recém-coletados com 'data' 80-90
# dias atrás - cadência trimestral de resultado, não uma falha). Bug
# real encontrado na mesma auditoria: a regra de 'data velha' abaixo
# apagava esses itens na limpeza seguinte à própria coleta que os
# inseriu - o coletor reportava "8 itens, persistência OK" mas
# `research_itens` nunca tinha o registro correspondente por mais de
# ~1h. Pras demais casas (RSS, descoberta próxima da publicação) essa
# regra nunca pega item recém-coletado de verdade; pra Nord, SEMPRE
# pegaria - por isso essa casa é excluída da deleção por 'data velha',
# retendo pelos 5 dias de `coletado_em` normais (mesmo tempo de vida que
# as demais casas têm na prática).
_CASAS_RETENCAO_SO_POR_COLETA = {"Nord Research"}


def apagar_itens_antigos(dias: int = RETENCAO_DIAS) -> int:
    """Apaga da tabela research_itens os itens cuja DATA DE PUBLICACAO
    ('data') OU cujo COLETADO_EM tenham mais de `dias` dias - research e'
    conteudo perecivel, nao guarda historico longo. E' OR (nao AND)
    porque cobrem casos diferentes: 'data' velha pega um relatorio antigo
    que a fonte continua listando (coletado_em fica sempre fresco a cada
    recoleta, nunca dispararia sozinho pras casas com descoberta proxima
    da publicacao); 'coletado_em' velho pega um item que sumiu da fonte e
    parou de ser recoletado (poderia nao ter 'data' valida pra comparar).
    Casas em `_CASAS_RETENCAO_SO_POR_COLETA` (ver comentario acima) ficam
    de fora da deleção por 'data velha' - só saem pela regra de
    'coletado_em'. Rodado em duas chamadas separadas (nao um OR so' do
    PostgREST) pra nao arriscar apagar item com 'data' vazia so' por
    causa da comparacao textual. Retorna quantas linhas foram removidas
    ao todo, ou -1 se o banco estiver fora do ar."""
    cliente = obter_cliente()
    if cliente is None:
        return -1
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    limite_data = limite.strftime("%Y-%m-%d")
    limite_coletado = limite.isoformat()
    total = 0
    try:
        query = cliente.table("research_itens").delete().neq("data", "").lt("data", limite_data)
        for casa in _CASAS_RETENCAO_SO_POR_COLETA:
            query = query.neq("casa", casa)
        resp = query.execute()
        total += len(resp.data)
    except Exception as exc:
        print(f"[research.store] apagar_itens_antigos (filtro 'data' < {limite_data!r}) falhou: {exc!r}")
        return -1
    try:
        resp = cliente.table("research_itens").delete().lt("coletado_em", limite_coletado).execute()
        total += len(resp.data)
    except Exception as exc:
        print(f"[research.store] apagar_itens_antigos (filtro 'coletado_em' < {limite_coletado!r}) falhou: {exc!r}")
        return -1
    return total


def salvar_premissas(
    link: str, casa: str, titulo: str, tickers: list, data_publicacao,
    tipo_documento, premissas: list, projecoes: dict,
    recomendacao, preco_alvo, modelo, riscos: list = None,
) -> bool:
    """Upsert por link na tabela PERMANENTE research_premissas (ver
    sql/research_premissas.sql) - diferente de salvar_resumo (research_itens,
    apagada em 5 dias por apagar_itens_antigos), esta tabela nunca e'
    limpa: guarda so' a ESTRUTURA extraida por IA (tipo de documento,
    premissas da tese, projecoes citadas, riscos apontados) + metadado
    minimo (casa/titulo/tickers/data) pra o documento continuar
    identificavel mesmo depois que a linha original de research_itens
    tiver sido apagada. Nunca o texto completo do relatorio. True se
    salvou, False se o banco estiver fora do ar ou a escrita falhar.

    'riscos' (coluna aditiva nova, ver sql/research_premissas_riscos.sql)
    so' vai no payload quando informado - e se o UPSERT falhar por causa
    dela (Supabase do usuario ainda sem rodar essa migracao), tenta de
    novo SEM essa coluna antes de desistir: mesmo padrao ja usado em
    salvar_itens pra 'publicado_em' - nunca quebra premissas/projecoes/
    recomendacao so' porque uma coluna nova ainda nao existe no banco de
    quem esta rodando."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    linha = {
        "link": link, "casa": casa, "titulo": titulo,
        "tickers": tickers or [], "data_publicacao": data_publicacao or None,
        "tipo_documento": tipo_documento, "premissas": premissas or [],
        "projecoes": projecoes or {}, "recomendacao": recomendacao,
        "preco_alvo": preco_alvo, "modelo_extracao": modelo,
    }
    if riscos is not None:
        linha["riscos"] = riscos
    try:
        cliente.table("research_premissas").upsert(linha, on_conflict="link").execute()
        return True
    except Exception as exc:
        if riscos is None:
            print(f"[research.store] salvar_premissas({link!r}) falhou: {exc!r}")
            return False
        print(
            f"[research.store] salvar_premissas({link!r}) falhou com 'riscos' presente: "
            f"{exc!r} - tentando de novo sem essa coluna"
        )
        try:
            cliente.table("research_premissas").upsert(
                {k: v for k, v in linha.items() if k != "riscos"}, on_conflict="link",
            ).execute()
            return True
        except Exception as exc2:
            print(f"[research.store] salvar_premissas({link!r}) falhou mesmo sem 'riscos': {exc2!r}")
            return False


def listar_premissas(tickers: list = None, casa=None) -> list | None:
    """Le a biblioteca PERMANENTE de premissas/projecoes (research_premissas)
    - diferente de listar_itens, nunca filtra por data/retencao (essa
    tabela nao perece). tickers filtra por qualquer overlap com a coluna
    tickers (array); casa filtra por casa - aceita `str` (1 casa exata,
    comportamento original, retrocompativel) OU `list[str]` (qualquer
    uma das casas da lista, via IN) OU None (todas). Mais recente
    primeiro (extraido_em). None se o banco estiver fora do ar - mesma
    convencao de listar_itens (distinguir de lista vazia)."""
    cliente = obter_cliente()
    if cliente is None:
        return None
    try:
        consulta = cliente.table("research_premissas").select("*")
        if tickers:
            consulta = consulta.overlaps("tickers", tickers)
        if isinstance(casa, (list, tuple, set)):
            if casa:
                consulta = consulta.in_("casa", list(casa))
        elif casa:
            consulta = consulta.eq("casa", casa)
        resp = consulta.order("extraido_em", desc=True).execute()
        return resp.data
    except Exception as exc:
        print(f"[research.store] listar_premissas(tickers={tickers!r}, casa={casa!r}) falhou: {exc!r}")
        return None


def salvar_resumo(link: str, resumo: str, modelo: str, preco_alvo: float = None, recomendacao: str = None) -> bool:
    """Grava o resumo (palavras proprias, nunca o texto original) de um
    item ja existente, mais preco_alvo/recomendacao quando extraidos
    (ver data/research/resumir.py:_extrair_dados_estruturados) - None
    grava None mesmo (nao omite a coluna), pra um resumo regerado sem
    preco-alvo identificado limpar um valor antigo que porventura exista.
    True se salvou."""
    cliente = obter_cliente()
    if cliente is None:
        return False
    try:
        cliente.table("research_itens").update(
            {"resumo": resumo, "modelo_resumo": modelo, "preco_alvo": preco_alvo, "recomendacao": recomendacao}
        ).eq("link", link).execute()
        return True
    except Exception as exc:
        print(f"[research.store] salvar_resumo({link!r}) falhou: {exc!r}")
        return False
