# -*- coding: utf-8 -*-
"""Saúde de EXECUÇÃO dos 3 workflows agendados do GitHub Actions que
disparam e-mail/análise (Radar + Morning Call, ambos em
.github/workflows/radar-morning-call.yml; Comitê Noturno, em
.github/workflows/comite-noturno.yml) - missão "agendamento" 2026-11-13.

Causa raiz confirmada nesta missão (ver MANUAL.md, "Disparo externo dos
agendamentos"): o `schedule` do GitHub Actions atrasa/descarta disparos
sob carga, sem relação com o código deste repositório - medido de novo
hoje (2026-11-13): nenhum `schedule` disparou entre ~01h e ~17h UTC
(Radar+Morning Call) nem entre ~03h e ~17h40 UTC (Coletores), e o
Morning Call do dia só foi ENTREGUE (não gerado - entregue) às 17:08
UTC (14:08 BRT), ~8h depois do horário previsto (06h30 BRT). Não há
correção de código pra isso (é a infraestrutura do GitHub); este módulo
é a MITIGAÇÃO de monitoramento: nunca inventa "verde" quando não há
disparo - torna o atraso/ausência visível no próprio app.

Deliberadamente SEPARADO de data/saude_dados.py/ui/saude_dados_tab.py
(CLAUDE.md, regra 8: "Saúde dos Dados é frente separada" - essa aba e
sua lógica não devem ser tocadas junto de outra mudança). Este módulo
só LÊ tabelas que já existem e já são escritas por outro código
(data/coletores_status.py via jobs/morning_call.py e
jobs/radar_quedas.py; coordenador_execucoes via jobs/comite_noturno.py,
reaproveitando data/coordenador_central/execucoes_agendadas.py que já
existe) - nenhuma tabela nova, nenhum escritor novo.

Cada `saude_*` devolve um dict com o MESMO formato:
{
    "rotulo": str,
    "ultima_tentativa_em": str|None (ISO, UTC),
    "ultimo_sucesso_em": str|None (ISO, UTC),
    "ultimo_erro": str|None,
    "execucao_ok": bool|None (última tentativa, não último sucesso),
    "disponivel": bool (False = Supabase fora do ar/sem credencial -
        "sem dado", nunca um estado inventado),
    "atrasado": bool|None (None = fora da janela em que isso é avaliável,
        ou "disponivel" é False),
    "motivo_atraso": str|None,
}

"atrasado" é None sempre que `disponivel` é False (nunca finge saber se
está atrasado sem dado real) ou fora da janela aplicável (ex: Radar
fora do horário de pregão nunca é "atrasado" por definição)."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from data import coletores_status
from data.coordenador_central import execucoes_agendadas

TZ_SP = ZoneInfo("America/Sao_Paulo")

# Mesmos limiares de jobs/morning_call.py / data/morning_call_editorial.py
# (fonte única - nunca duplicar o número com valor diferente aqui).
_MC_LIMITE_HORARIO_PREVISTO = time(7, 30)
_MC_CORTE_ENVIO_AGENDADO = time(17, 0)

# Radar: .github/workflows/radar-morning-call.yml - "4,19,34,49 13-19 * * 1-5"
# + "4 20 * * 1-5" (13h-20h59 UTC = 10h-17h59 BRT, a cada 15min, seg-sex).
_RADAR_INICIO_BRT = time(10, 0)
_RADAR_FIM_BRT = time(18, 0)
_RADAR_GAP_MAXIMO_MIN = 35  # 2x o intervalo nominal (15min) + folga

# Comitê Noturno: .github/workflows/comite-noturno.yml - "45 22 * * 1-5"
# (19h45 BRT) + reservas até ~20h49 BRT (ver mesmo arquivo).
_COMITE_HORARIO_PREVISTO = time(19, 45)
_COMITE_LIMITE_ALERTA = time(21, 0)


def _to_utc(iso_texto):
    if not iso_texto:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dia_util(data_: date) -> bool:
    return data_.weekday() < 5  # 0=segunda ... 4=sexta


def _saude_generica(nome_painel: str, rotulo: str) -> dict:
    """Monta o formato comum a partir de data/coletores_status.py (usado
    por MORNING CALL e RADAR DE QUEDAS) - `obter_status` já devolve None
    tanto se o Supabase está fora do ar quanto se esse `nome` nunca
    registrou nada (NUNCA_EXECUTADO); os dois casos são "sem dado" aqui
    (mesmo espírito de data/saude_dados.py, só que fora dela)."""
    status = coletores_status.obter_status(nome_painel)
    base = {
        "rotulo": rotulo,
        "ultima_tentativa_em": None,
        "ultimo_sucesso_em": None,
        "ultimo_erro": None,
        "execucao_ok": None,
        "disponivel": False,
        "atrasado": None,
        "motivo_atraso": None,
    }
    if status is None:
        return base
    base["disponivel"] = True
    base["ultima_tentativa_em"] = status.get("ultima_tentativa_em")
    base["ultimo_sucesso_em"] = status.get("ultimo_sucesso_em")
    base["ultimo_erro"] = status.get("ultimo_erro")
    base["execucao_ok"] = status.get("execucao_ok")
    return base


def saude_morning_call(agora=None) -> dict:
    """Morning Call (jobs/morning_call.py, nome "MORNING CALL" em
    coletores_status) - esperado 1x por dia útil, pronto até
    _MC_LIMITE_HORARIO_PREVISTO (07h30 BRT); "atrasado" só é avaliado em
    dia útil, depois desse horário. Nunca marca atraso num fim de
    semana/feriado nem antes do horário previsto (sem gatilho ainda não
    é atraso)."""
    agora = agora or datetime.now(TZ_SP)
    saude = _saude_generica("MORNING CALL", "Morning Call")
    if not saude["disponivel"]:
        return saude
    if not _dia_util(agora.date()) or agora.time() < _MC_LIMITE_HORARIO_PREVISTO:
        return saude
    ultimo_sucesso = _to_utc(saude["ultimo_sucesso_em"])
    enviado_hoje = (
        ultimo_sucesso is not None
        and ultimo_sucesso.astimezone(TZ_SP).date() == agora.date()
    )
    if enviado_hoje:
        saude["atrasado"] = False
        return saude
    saude["atrasado"] = True
    if agora.time() >= _MC_CORTE_ENVIO_AGENDADO:
        saude["motivo_atraso"] = (
            f"sem edição enviada hoje até agora ({agora.strftime('%H:%M')} BRT) - "
            f"passou do corte de envio agendado ({_MC_CORTE_ENVIO_AGENDADO.strftime('%H:%M')} BRT); "
            "só um disparo manual (workflow_dispatch) ainda envia."
        )
    else:
        saude["motivo_atraso"] = (
            f"sem edição enviada hoje até agora ({agora.strftime('%H:%M')} BRT) - "
            f"previsto para {_MC_LIMITE_HORARIO_PREVISTO.strftime('%H:%M')} BRT."
        )
    return saude


def saude_radar(agora=None) -> dict:
    """Radar de Quedas (jobs/radar_quedas.py, nome "RADAR DE QUEDAS" em
    coletores_status) - esperado a cada ~15min em horário de pregão
    (10h-18h BRT, dia útil); "atrasado" só é avaliado dentro dessa
    janela (fora dela, a ausência de disparo recente é esperada, não um
    problema)."""
    agora = agora or datetime.now(TZ_SP)
    saude = _saude_generica("RADAR DE QUEDAS", "Radar de Quedas")
    if not saude["disponivel"]:
        return saude
    dentro_da_janela = (
        _dia_util(agora.date())
        and _RADAR_INICIO_BRT <= agora.time() <= _RADAR_FIM_BRT
    )
    if not dentro_da_janela:
        return saude
    ultima_tentativa = _to_utc(saude["ultima_tentativa_em"])
    if ultima_tentativa is None:
        saude["atrasado"] = True
        saude["motivo_atraso"] = "nenhuma tentativa registrada ainda hoje, dentro do horário de pregão."
        return saude
    gap_min = (agora.astimezone(timezone.utc) - ultima_tentativa).total_seconds() / 60
    if gap_min > _RADAR_GAP_MAXIMO_MIN:
        saude["atrasado"] = True
        saude["motivo_atraso"] = (
            f"última tentativa há {gap_min:.0f}min (esperado a cada ~15min em horário de pregão)."
        )
    else:
        saude["atrasado"] = False
    return saude


def saude_comite_noturno(agora=None) -> dict:
    """Comitê de Investimentos - análise noturna (jobs/comite_noturno.py,
    tabela coordenador_execucoes, tipo "comite_noturno") - reaproveita
    data/coordenador_central/execucoes_agendadas.py (já existe, já serve
    ui/coordenador_tab.py) em vez de consultar o Supabase de novo aqui.
    Esperado 1x por dia útil, a partir de 19h45 BRT; "atrasado" só
    avaliado em dia útil, depois de _COMITE_LIMITE_ALERTA (folga pras
    reservas de .github/workflows/comite-noturno.yml)."""
    agora = agora or datetime.now(TZ_SP)
    rotulo = execucoes_agendadas.ROTULOS_TIPO.get("comite_noturno", "Comitê de Investimentos (análise noturna)")
    base = {
        "rotulo": rotulo,
        "ultima_tentativa_em": None,
        "ultimo_sucesso_em": None,
        "ultimo_erro": None,
        "execucao_ok": None,
        "disponivel": False,
        "atrasado": None,
        "motivo_atraso": None,
    }
    execucoes = execucoes_agendadas.listar_ultimas_execucoes()
    if execucoes is None:
        return base
    base["disponivel"] = True
    execucao = next((e for e in execucoes if e.get("tipo") == "comite_noturno"), None)
    if execucao is not None:
        status = execucao.get("status")
        ok = status == "OK"
        base["ultima_tentativa_em"] = execucao.get("iniciado_em")
        base["ultimo_sucesso_em"] = execucao.get("concluido_em") if status in ("OK", "PARCIAL") else None
        base["ultimo_erro"] = execucao.get("erro")
        base["execucao_ok"] = ok if status in ("OK", "ERRO") else None
    if not _dia_util(agora.date()) or agora.time() < _COMITE_LIMITE_ALERTA:
        return base
    inicio = _to_utc(base["ultima_tentativa_em"])
    rodou_hoje = inicio is not None and inicio.astimezone(TZ_SP).date() == agora.date()
    if rodou_hoje:
        base["atrasado"] = False
        return base
    base["atrasado"] = True
    base["motivo_atraso"] = (
        f"nenhuma rodada iniciada hoje até agora ({agora.strftime('%H:%M')} BRT) - "
        f"previsto a partir de {_COMITE_HORARIO_PREVISTO.strftime('%H:%M')} BRT."
    )
    return base


def saude_agendamentos(agora=None) -> list:
    """As 3 linhas, na ordem em que aparecem no dia (Morning Call ->
    Radar -> Comitê Noturno) - ponto de entrada único pra UI (ver
    ui/sistema_tab.py)."""
    agora = agora or datetime.now(TZ_SP)
    return [
        saude_morning_call(agora),
        saude_radar(agora),
        saude_comite_noturno(agora),
    ]
