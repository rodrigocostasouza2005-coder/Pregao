# -*- coding: utf-8 -*-
"""SAUDE DOS DADOS - painel de monitoramento dos coletores do PREGAO.

Isolado de proposito (nao importa nada de data/research/genial.py,
data/eventos.py, data/eventos_coleta.py nem coletor_local.py alem das
funcoes de LEITURA ja existentes e publicas) - essa aba nao escreve
nada nesses modulos, so' le o que eles ja expoem.

Dois tipos de coletor nesta auditoria (ver PROGRESSO.md/BACKLOG.md,
auditoria 2026-10-09):

- INSTRUMENTADO: registra cada tentativa via
  `data.coletores_status.registrar_tentativa` (NEWS, MERCADO, MACRO,
  CVM - instrumentados nesta mesma sessao). Classificacao usa
  execucao_ok/persistencia_ok/erro reais da tentativa mais recente.
- SOMENTE_LEITURA: ainda NAO registra tentativas (Research
  Genial/XP/Lives, Calendario - coletores de outra frente/sessao,
  nao tocados aqui pra nao conflitar). Classificacao usa so' a idade
  do ULTIMO DADO persistido (`ultima_coleta_em`/snapshot) - nunca
  finge saber se a tentativa mais recente falhou ou nao, porque essa
  informacao simplesmente nao existe ainda pra esses coletores.

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
        "nome": "MERCADO", "fonte": "yfinance (cotacoes em lote)",
        "categoria": "Cotacoes", "frequencia_esperada": "sob demanda (cache 90s)",
        "idade_maxima_horas": 2, "instrumentado": True,
    },
    {
        "nome": "MACRO (BCB)", "fonte": "Banco Central (SGS - IPCA/Selic/CDI)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 4h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "MACRO (ANBIMA)", "fonte": "ANBIMA (ETTJ - curva pre)",
        "categoria": "Macro", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "CVM", "fonte": "dados.cvm.gov.br (FCA/IPE)",
        "categoria": "CVM", "frequencia_esperada": "sob demanda (cache 6h)",
        "idade_maxima_horas": 30, "instrumentado": True,
    },
    {
        "nome": "Genial Analisa", "fonte": "analisa.genialinvestimentos.com.br",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": False,
        "leitor": _leitor_research("Genial Analisa"),
    },
    {
        "nome": "XP Investimentos", "fonte": "conteudos.xpi.com.br (WP REST)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": False,
        "leitor": _leitor_research("XP Investimentos"),
    },
    {
        "nome": "Genial (Lives)", "fonte": "YouTube RSS (canal Genial Analisa)",
        "categoria": "Research", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 72, "instrumentado": False,
        "leitor": _leitor_research("Genial (Lives)"),
    },
    {
        "nome": "CALENDARIO", "fonte": "RI das empresas + NEWS + prazo CVM",
        "categoria": "Calendario", "frequencia_esperada": "coletor_local.py, ~30min (seg-sex 07-20h)",
        "idade_maxima_horas": 48, "instrumentado": False,
        "leitor": _leitor_calendario(),
    },
]


def obter_painel_saude() -> list:
    """Monta o painel completo: pra cada coletor do REGISTRO_COLETORES,
    busca o status (instrumentado -> tabela coletores_status; somente-
    leitura -> leitor dedicado) e classifica. Nunca lanca excecao -
    qualquer falha de leitura individual vira NAO_COMPROVADO pra aquele
    coletor, sem derrubar o painel inteiro."""
    painel = []
    for c in REGISTRO_COLETORES:
        try:
            if c["instrumentado"]:
                status = coletores_status.obter_status(c["nome"])
            else:
                status = c["leitor"]()
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
