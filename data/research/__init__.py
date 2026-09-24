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
- BTG Research: API interna identificada mas bloqueada por bot-detection
  (Akamai) - ver genial.py/relatorio da tarefa pros detalhes tecnicos.
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

from . import genial, store, xp
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
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": genial.obter_relatorios,
        "extrator_texto": None,  # generico (baixa a pagina publica do relatorio)
    },
    {
        "id": "xp",
        "nome": "XP Investimentos",
        "ativa_por_padrao": True,  # campos confirmados com requisicao real (fora do sandbox), ver xp.py
        "disponivel": True,
        "obter_relatorios": xp.obter_relatorios,
        "extrator_texto": xp.obter_texto_aberto,  # nunca baixa a pagina publica (paywall)
    },
    {
        "id": "btg",
        "nome": "BTG Research",
        "ativa_por_padrao": False,
        "disponivel": False,
        "obter_relatorios": None,
        "extrator_texto": None,
        "motivo_indisponivel": (
            "API interna identificada, mas bloqueada por bot-detection (Akamai) - "
            "precisa de navegador real (Playwright/Chromium) pra passar do desafio JS."
        ),
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
    if itens is None:
        print(f"[research] coleta {casa['nome']} falhou apos {duracao:.1f}s")
        return 0, False
    ok = store.salvar_itens(itens)
    print(f"[research] coleta {casa['nome']}: {len(itens)} itens em {duracao:.1f}s (salvou={ok})")
    return len(itens), ok


def coletar_todas_disponiveis() -> dict:
    """Coleta (sem gate de tempo) todas as casas marcadas como disponiveis.
    Pensada pra ser chamada por um job agendado, nao pelo app ao vivo (o
    app usa obter_relatorios_unificado, que respeita o gate de 30min).
    Retorna {nome_da_casa: {'coletados': N, 'ok': bool}}."""
    resultado = {}
    for casa in CASAS:
        if not casa["disponivel"]:
            continue
        coletados, ok = coletar_casa(casa)
        resultado[casa["nome"]] = {"coletados": coletados, "ok": ok}
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
