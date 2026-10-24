# -*- coding: utf-8 -*-
"""Registro das casas de research: um coletor por casa, todos no mesmo
formato (casa, titulo, data, autor, tipo, setor, tickers, link).

Pra ligar/desligar uma casa (por padrao ou por usuario, via prefs), mexa
so nessa lista - a UI (ui/research_tab.py) le CASAS pra montar o filtro.

Verificado na pratica quais casas de research tem conteudo publico
coletavel sem login:
- Genial Analisa: publica, coletavel (JSON __NEXT_DATA__ da home).
- XP Investimentos: publica, coletavel (API do WordPress, wp-json/wp/v2 -
  ver xp.py). Campos confirmados com requisicao real feita fora do
  sandbox (2026-09-23) - IP deste sandbox de dev continua bloqueado pelo
  CDN da XP, mas o coletor esta ativo por padrao.
- BTG Research: API real (content.btgpactual.com/api/research/content-hub/
  analysis/filter) coletavel - achado que corrigiu a investigacao anterior
  (2026-10-17): o campo "tier" (AREA_PUBLICA/AREA_LOGADA) JA' vem no
  proprio lote, nao so' no detalhe - coletor filtra por AREA_PUBLICA antes
  de persistir, nunca toca em conteudo de area logada (ver data/research/
  btg.py e CASAS['btg'] abaixo pros detalhes completos da investigacao).
- Itau BBA, BB Investimentos, Santander, Safra, Agora/Bradesco, Inter:
  ainda nao investigadas (ver BACKLOG.md; reconhecimento rapido de
  reachability em data/diagnostico.py).

Os itens coletados sao persistidos no Supabase (tabela research_itens,
ver data/research/store.py) - a aba RESEARCH sempre le do banco primeiro
(preparar_leitura, rapido) e so depois dispara coleta pras casas
desatualizadas (coletar_pendentes, com timeout por requisicao e orcamento
total de tempo - ver data/research/base.py); a coleta roda no maximo a
cada 30min por casa (store.precisa_recoletar)."""

import time

import streamlit as st

from data.coletores_status import registrar_tentativa

from . import btg, genial, genial_lives, montebravo, nord, store, xp
from .base import TEMPO_MAX_COLETA_S

# nao tenta recoletar a mesma casa antes desse tempo desde a ULTIMA
# TENTATIVA (sucesso ou falha) - existe pra nao martelar uma fonte que
# acabou de falhar a cada interacao do usuario na aba RESEARCH (era o
# caso real do Genial/XP quando bloqueados em producao: cada rerun
# tentava de novo, ate ~25s de orcamento, deixando a aba lenta em TODA
# interacao, nao so na primeira). store.precisa_recoletar() so evita
# recoleta apos SUCESSO (coletado_em so avanca quando salva); este
# cooldown cobre a lacuna de tentativas que falharam.
_COOLDOWN_FALHA_S = 10 * 60

CASAS = [
    {
        "id": "genial",
        "nome": "Genial Analisa",
        "fonte": "analisa.genialinvestimentos.com.br",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": genial.obter_relatorios,
        "extrator_texto": None,  # generico (baixa a pagina publica do relatorio)
        # diagnostico de producao (2026-09-24): bloqueada no Streamlit
        # Cloud (~20s pra desistir, orcamento de _tentar_buscar). O app
        # nao tenta mais coletar essa casa - so le o que o
        # coletor_local.py (fora do Cloud) ja tiver salvo no Supabase.
        "tentar_coleta_automatica": False,
        # achado real (auditoria 2026-10-15): sem isso, SAUDE DOS DADOS
        # so mostrava "obter_relatorios retornou None apos Xs" - o motivo
        # especifico (timeout/HTTP-2-reset/orcamento esgotado) so
        # aparecia no print(), nunca no painel. Opcional - casas sem essa
        # chave continuam exatamente como antes.
        "motivo_falha": genial.motivo_ultima_falha,
        # achado real (auditoria 2026-10-18, correcao do exit code de
        # coletor_local.py): sem isso, uma falha aqui (bloqueio de WAF
        # ja' documentado, cronico desde 24/09) derrubava o exit code
        # igual a uma regressao nova em qualquer outra casa - opcional,
        # casa sem essa chave continua tratada como 'erro' (nunca
        # bloqueio conhecido por padrao), ver _classificar_falha.
        "categoria_falha": genial.categoria_ultima_falha,
    },
    {
        "id": "xp",
        "nome": "XP Investimentos",
        "fonte": "conteudos.xpi.com.br (WP REST)",
        "ativa_por_padrao": True,  # campos confirmados com requisicao real (fora do sandbox), ver xp.py
        "disponivel": True,
        "obter_relatorios": xp.obter_relatorios,
        "extrator_texto": xp.obter_texto_aberto,  # nunca baixa a pagina publica (paywall)
        "tentar_coleta_automatica": False,  # idem Genial - bloqueada no Cloud (403), ver coletor_local.py
        "motivo_falha": xp.motivo_ultima_falha,
        "categoria_falha": xp.categoria_ultima_falha,  # ver comentario equivalente em Genial Analisa acima
    },
    {
        # Ligada em 2026-09-28 a pedido explicito do Rodrigo ("quero a
        # transcricao das lives da Genial") - ver ATENCAO no topo de
        # genial_lives.py: ignora deliberadamente o robots.txt do
        # YouTube (que proibe /feeds/videos.xml pra bots genericos),
        # excecao unica no projeto, justificada por uso pessoal/nao
        # comercial e volume baixo. Nao copiar esse padrao pra outra
        # fonte sem a mesma decisao explicita.
        "id": "genial_lives",
        "nome": "Genial (Lives)",
        "fonte": "YouTube RSS (canal Genial Analisa)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": genial_lives.obter_relatorios,
        "extrator_texto": genial_lives.obter_texto_transcricao,
        # achado real (2026-10-17): a execucao de producao no GitHub
        # Actions (run 38989522110) mostrou essa casa falhando ("[research]
        # coleta Genial (Lives) falhou apos 4.5s") sem nenhum detalhe -
        # motivo_ultima_falha novo em genial_lives.py (mesmo padrao de
        # genial.py/xp.py) pra essa falha aparecer em SAUDE DOS DADOS.
        "motivo_falha": genial_lives.motivo_ultima_falha,
    },
    {
        # Investigado de novo em 2026-10-17 (reinvestigacao da mesma
        # sessao, apos pedido explicito do Rodrigo pra nao parar so' no
        # diagnostico): a conclusao anterior ("tier so' aparece no
        # detalhe, filtrar exigiria N+1 requisicoes contra conteudo ja'
        # recebido") estava ERRADA - testada de novo com requisicao real,
        # o campo "tier" ("AREA_PUBLICA"/"AREA_LOGADA") JA' vem no proprio
        # POST /filter em lote, item por item, sem precisar de nenhuma
        # chamada de detalhe. Confirmado com 300 itens reais (12 paginas),
        # tier presente em 100% deles, 123/300 (41%) e 68/200 (34%) em
        # amostras distintas "AREA_PUBLICA" - volume real suficiente pra
        # coletor. robots.txt de content.btgpactual.com permite tudo
        # ("Allow: /"); nenhum bloqueio observado em dezenas de requisicoes
        # reais, com o UA identificado do projeto OU um UA de navegador
        # comum - sem diferenca nenhuma (diferente de genial.py/xp.py,
        # que SAO bloqueados por fingerprint/WAF - aqui nao ha' bloqueio
        # algum pra contornar).
        #
        # Coletor implementado (data/research/btg.py) filtra por
        # tier=="AREA_PUBLICA" ANTES de qualquer persistencia - usa o
        # controle de acesso que a BTG expoe, em vez de ignora-lo; nunca
        # inclui item AREA_LOGADA nem item sem tier reconhecido. A pagina
        # www.btgpactual.com/acoes/ultimos-relatorios (SPA diferente,
        # dominio diferente) continua bloqueada pra Chromium/Playwright
        # (0/8 tentativas, auditorias anteriores) - mas o coletor nunca
        # depende dela, le direto a API publica de content.btgpactual.com.
        #
        # Link persistido e' o endpoint de detalhe da API (real, publico,
        # estavel, unico por item) - nao foi encontrada no bundle Angular
        # publico (111 chunks JS verificados) uma rota de pagina com slug
        # amigavel confirmada; usar o endpoint de API e' honesto (nao
        # inventa uma URL de pagina nao verificada).
        "id": "btg",
        "nome": "BTG Pactual Research",
        "fonte": "content.btgpactual.com (API de research, filtrado por tier publico)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": btg.obter_relatorios,
        # nao usa o generico (baixa a pagina com curl_cffi impersonate,
        # pensado pra HTML/PDF) - link e' um endpoint JSON da propria API
        # publica; obter_texto_publico reconsulta e RECONFIRMA tier antes
        # de devolver texto (defesa em profundidade contra item que tenha
        # virado AREA_LOGADA depois da coleta).
        "extrator_texto": btg.obter_texto_publico,
        "motivo_falha": btg.motivo_ultima_falha,
    },
    {
        # Adicionada em 22/10/2026: feed RSS público do WordPress oficial
        # (robots.txt permite tudo), sondado de verdade a partir do runner do
        # GitHub Actions - análises de empresas e carta mensal; imprensa e
        # eventos ficam fora (ver montebravo.py). Texto para resumo: página
        # pública do próprio post (extrator genérico, respeita robots).
        "id": "montebravo",
        "nome": "Monte Bravo",
        "fonte": "montebravo.com.br (feed RSS do blog, seção de análise)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": montebravo.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": montebravo.motivo_ultima_falha,
    },
    {
        # Adicionada em 24/10/2026 (pedido explicito do Rodrigo, lista de
        # 10 casas prioritarias): sem feed RSS (/feed/ e /blog/feed/ dao
        # HTTP 404) - descoberta via /blog/sitemap.xml, publico e listado
        # no proprio robots.txt ("Allow: /"). So entram posts com ticker
        # B3 + "resultado(s)" no slug (ver nord.py) - a categoria mais
        # claramente "research de acoes" confirmada com texto real
        # (recomendacao explicita no post da Petrobras 1T26, assinado por
        # analista nomeado). Sem isso, o sitemap tem ~7700 URLs, a maioria
        # conteudo educacional/opiniao ("X vale a pena investir"), que nao
        # e' research. Ainda NAO testada a partir do Streamlit Cloud/
        # GitHub Actions (so' deste ambiente de dev) - se bloquear la',
        # vira candidata a tentar_coleta_automatica=False como Genial/XP.
        "id": "nord",
        "nome": "Nord Research",
        "fonte": "nordinvestimentos.com.br (sitemap do blog, posts de resultado por ticker)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": nord.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": nord.motivo_ultima_falha,
    },
]


def coletar_casa(casa: dict) -> tuple[int, bool]:
    """Busca relatorios de uma casa na fonte real e grava no Supabase
    (upsert por link, coletado_em=agora). Retorna (n_itens, ok) - ok=False
    se a fonte ou o Supabase falharem. Funcao separada (nao inline no
    fluxo de leitura da UI) pra poder ser chamada tambem por um job
    agendado no futuro (GitHub Actions, fase opcional do roadmap), sem
    depender da UI nem do gate de 30min - so import data.research e chama
    coletar_casa(casa) ou coletar_todas_disponiveis() direto.

    Print() de proposito (nao logging): Streamlit Cloud captura stdout no
    painel de Logs - da pra conferir dali se a fonte esta respondendo a
    partir do servidor do Cloud (pode se comportar diferente do ambiente
    local, ex: bloqueio de WAF por IP/regiao)."""
    inicio = time.monotonic()
    itens = casa["obter_relatorios"]()
    duracao = time.monotonic() - inicio
    # registro de SAUDE DOS DADOS (ver data/saude_dados.py/coletores_status.py)
    # - mesmo padrao ja usado em data/news.py, data/mercado.py, data/macro.py,
    # data/cvm.py: registra no PONTO REAL de coleta, nao em quem chama, pra
    # cobrir tanto a coleta ao vivo (genial_lives, via coletar_pendentes) quanto
    # a coleta standalone (coletor_local.py, via coletar_todas_disponiveis).
    if itens is None:
        print(f"[research] coleta {casa['nome']} falhou apos {duracao:.1f}s")
        motivo_especifico = None
        obter_motivo = casa.get("motivo_falha")
        if obter_motivo is not None:
            try:
                motivo_especifico = obter_motivo()
            except Exception:
                motivo_especifico = None
        erro = f"obter_relatorios retornou None apos {duracao:.1f}s"
        if motivo_especifico:
            erro = f"{erro}; {motivo_especifico}"
        registrar_tentativa(
            casa["nome"], casa.get("fonte", casa["nome"]), execucao_ok=False,
            erro=erro, categoria="Research",
        )
        return 0, False
    ok = store.salvar_itens(itens)
    print(f"[research] coleta {casa['nome']}: {len(itens)} itens em {duracao:.1f}s (salvou={ok})")
    registrar_tentativa(
        casa["nome"], casa.get("fonte", casa["nome"]), execucao_ok=True,
        persistencia_ok=ok, registros_novos=len(itens), categoria="Research",
    )
    return len(itens), ok


def _classificar_falha(casa: dict) -> str:
    """Classifica a falha de `casa` (so' chamada quando coletar_casa
    devolveu ok=False) pra coletor_local.py decidir se ela sozinha deve
    derrubar o exit code (ver _falha_critica la'). Regra dura (pedido
    explicito, achado real auditoria 2026-10-18): 'bloqueio_externo_
    conhecido' SO' quando a casa expoe 'categoria_falha' (callable) E ele
    devolve exatamente essa string - campo ausente, excecao ao chamar, ou
    qualquer valor diferente (incluindo None/vazio) sempre volta 'erro'.
    Nunca usa um flag estatico por casa (ex: 'essa casa e bloqueada,
    ignora falha dela') - a classificacao e' sempre da falha ESPECIFICA
    que aconteceu agora, lida do motivo real (ver categoria_ultima_falha
    em genial.py/xp.py) - uma falha nova/diferente na mesma casa (ex: a
    XP comecar a devolver HTTP 500 em vez do 403 do Akamai) continua
    'erro', nao fica mascarada so' porque a casa 'e' conhecida por
    falhar'."""
    obter_categoria = casa.get("categoria_falha")
    if obter_categoria is None:
        return "erro"
    try:
        categoria = obter_categoria()
    except Exception:
        return "erro"
    return categoria if categoria == "bloqueio_externo_conhecido" else "erro"


def coletar_todas_disponiveis() -> dict:
    """Coleta (sem gate de tempo) todas as casas marcadas como disponiveis.
    Pensada pra ser chamada por um job agendado, nao pelo app ao vivo (o
    app usa obter_relatorios_unificado, que respeita o gate de 30min).
    Retorna {nome_da_casa: {'coletados': N, 'ok': bool, 'categoria_falha':
    str | None}} - 'categoria_falha' so' e' diferente de None quando
    ok=False (ver _classificar_falha); usado por coletor_local.py pra
    decidir o exit code sem derrubar a build por um bloqueio externo ja'
    documentado (ex: Akamai na Genial/XP), mas sem mascarar nenhuma falha
    nova ou falha de persistencia (que continua sempre 'erro')."""
    resultado = {}
    for casa in CASAS:
        if not casa["disponivel"]:
            continue
        coletados, ok = coletar_casa(casa)
        entrada = {"coletados": coletados, "ok": ok, "categoria_falha": None}
        if not ok:
            entrada["categoria_falha"] = _classificar_falha(casa)
        resultado[casa["nome"]] = entrada
    return resultado


def preparar_leitura(casas_ativas=None):
    """So a leitura do que ja esta salvo no Supabase (rapida, sem tocar em
    nenhuma fonte externa) - pensada pra UI desenhar a tela imediatamente
    com isso antes de tentar coletar algo novo. Retorna (relatorios,
    falhas, casas_para_coletar, nomes_para_ler):
    - falhas: casas indisponiveis ou erro de leitura do banco;
    - casas_para_coletar: casas ativas+disponiveis cuja ultima coleta
      salva tem mais de 30min (store.precisa_recoletar) - quem chama
      decide se/quando coletar (ver coletar_pendentes);
    - nomes_para_ler: nomes de casa usados pra reler o banco depois de
      coletar (ver ler_itens_salvos)."""
    if casas_ativas is None:
        casas_ativas = [c["id"] for c in CASAS if c["ativa_por_padrao"]]

    falhas = []
    nomes_para_ler = []
    casas_para_coletar = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas:
            continue
        if not casa["disponivel"]:
            falhas.append(f"{casa['nome']} ({casa.get('motivo_indisponivel', 'indisponível')})")
            continue
        nomes_para_ler.append(casa["nome"])
        if not casa.get("tentar_coleta_automatica", True):
            continue
        if store.precisa_recoletar(casa["nome"]):
            casas_para_coletar.append(casa)

    if not nomes_para_ler:
        return [], falhas, casas_para_coletar, nomes_para_ler

    relatorios = store.listar_itens(nomes_para_ler)
    if relatorios is None:
        falhas.append("Supabase (leitura do research)")
        return [], falhas, casas_para_coletar, nomes_para_ler
    return relatorios, falhas, casas_para_coletar, nomes_para_ler


def ler_itens_salvos(nomes: list):
    """So a leitura do banco (sem gate nem coleta) - usado pra reler apos
    coletar_pendentes(). None se o banco estiver fora do ar."""
    return store.listar_itens(nomes)


def ultimas_coletas_formatadas(casas_ativas: list) -> str:
    """Texto "última coleta: <casa> hh:mm · <casa> hh:mm" (fuso
    America/Sao_Paulo) com o horario da ultima coleta BEM-SUCEDIDA de
    cada casa ativa+disponivel - transparencia de quando os dados foram
    atualizados de verdade. Especialmente util quando a coleta pelo
    proprio servidor (Cloud) esta bloqueada e quem mantem os dados
    frescos e' o coletor_local.py rodando na maquina do usuario (ver
    coletor_local.py e docs/agendador_tarefas.md)."""
    from zoneinfo import ZoneInfo

    tz_br = ZoneInfo("America/Sao_Paulo")
    partes = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas or not casa["disponivel"]:
            continue
        ultima = store.ultima_coleta_em(casa["nome"])
        if ultima is None:
            partes.append(f"{casa['nome']}: nunca")
        else:
            partes.append(f"{casa['nome']}: {ultima.astimezone(tz_br).strftime('%d/%m %H:%M')}")
    return " · ".join(partes)


@st.cache_resource(show_spinner=False)
def _ultimas_tentativas() -> dict:
    """casa_id -> time.monotonic() da ultima tentativa de coleta (sucesso
    OU falha). st.cache_resource = estado compartilhado entre sessoes e
    reruns no MESMO processo do servidor (reseta em redeploy) - e' o
    cooldown de _COOLDOWN_FALHA_S."""
    return {}


_INTERVALO_LIMPEZA_S = 60 * 60  # limpeza de itens antigos roda no maximo 1x por hora


def coletar_pendentes(casas: list) -> list:
    """Coleta uma lista de casas (ja filtradas como pendentes por
    preparar_leitura), respeitando um orcamento total de tempo
    (base.TEMPO_MAX_COLETA_S) e um cooldown por casa desde a ultima
    tentativa (_COOLDOWN_FALHA_S) - se estourar o orcamento, ou se a casa
    tiver falhado ha pouco tempo, pula e deixa pra proxima chamada (a
    casa nao coletada continua 'pendente' porque seu coletado_em nao foi
    atualizado). Retorna as falhas (nomes de casa que nao atualizaram,
    por erro, cooldown ou tempo esgotado).

    Tambem aproveita esse ponto de atividade pra rodar a limpeza de itens
    com mais de store.RETENCAO_DIAS (store.apagar_itens_antigos),
    throttled a 1x por hora (_INTERVALO_LIMPEZA_S) via o mesmo cache de
    tentativas - nao vale a pena bater no banco toda vez so' pra isso."""
    tentativas = _ultimas_tentativas()
    ultima_limpeza = tentativas.get("_limpeza")
    if ultima_limpeza is None or (time.monotonic() - ultima_limpeza) >= _INTERVALO_LIMPEZA_S:
        store.apagar_itens_antigos()
        tentativas["_limpeza"] = time.monotonic()

    falhas = []
    limite = time.monotonic() + TEMPO_MAX_COLETA_S
    for casa in casas:
        agora = time.monotonic()
        ultima_tentativa = tentativas.get(casa["id"])
        if ultima_tentativa is not None and (agora - ultima_tentativa) < _COOLDOWN_FALHA_S:
            falhas.append(f"{casa['nome']} (tentativa recente, aguardando)")
            continue
        if agora > limite:
            falhas.append(f"{casa['nome']} (tempo esgotado)")
            continue
        _, ok = coletar_casa(casa)
        tentativas[casa["id"]] = time.monotonic()
        if not ok:
            falhas.append(casa["nome"])
    return falhas
