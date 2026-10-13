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
        return "PARCIAL", ESTADOS["PARCIAL"] + " (algumas fontes/itens nao confirmados)"

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
        "nome": "MERCADO", "fonte": "yfinance (cotacoes em lote)",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 90s)",
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
        "nome": "CALENDARIO", "fonte": "RI das empresas + NEWS + prazo CVM",
        "categoria": "Calendario", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": True,
        "leitor": _leitor_hibrido("CALENDARIO", _leitor_calendario()),
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
    coletor, sem derrubar o painel inteiro."""
    painel = []
    for c in REGISTRO_COLETORES:
        try:
            status = c["leitor"]() if "leitor" in c else coletores_status.obter_status(c["nome"])
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
