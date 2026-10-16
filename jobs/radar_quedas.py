# -*- coding: utf-8 -*-
"""Worker independente: monitoramento de quedas e entrega resiliente de e-mails."""
from datetime import datetime
from zoneinfo import ZoneInfo

from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.radar_quedas import processar_monitoramento
from data.supabase_client import obter_cliente
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")
STATUS_REPROCESSAVEIS = ("PENDENTE_ENVIO", "FALHA_ENVIO")


def _alertas_pendentes(cliente):
    """Busca alertas persistidos ainda não entregues, inclusive de execuções anteriores."""
    try:
        resposta = (
            cliente.table("radar_alertas_queda")
            .select("*")
            .in_("status", list(STATUS_REPROCESSAVEIS))
            .order("alertado_em")
            .limit(200)
            .execute()
        )
        return resposta.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao recuperar alertas pendentes: {exc!r}")
        return None


def _texto_alerta(alerta):
    return (
        f"RADAR DE QUEDAS — {alerta['ticker']}\n\n"
        f"Variação diária: {float(alerta['variacao_pct']):.2f}%\n"
        f"Preço: {float(alerta['preco_atual']):.2f}\n"
        f"Fechamento anterior: {float(alerta['fechamento_anterior']):.2f}\n"
        f"Cotação: {alerta.get('cotacao_em', 'indisponível')} "
        f"({alerta.get('tipo_cotacao', 'provedor não informado')})\n"
        f"Casas: {', '.join(alerta.get('casas') or [])}\n"
        f"Carteiras: {', '.join(alerta.get('carteiras') or [])}\n"
        f"Fontes: {' | '.join(alerta.get('fontes') or [])}\n\n"
        "Alerta informativo, não constitui recomendação de investimento."
    )


def _enviar_alerta(cliente, alerta):
    """Envia e persiste o resultado. Falhas permanecem elegíveis para retry."""
    alerta_id = alerta.get("id")
    if alerta_id is None:
        print(f"[radar_quedas] alerta sem id persistido; envio ignorado: {alerta.get('ticker')}")
        return False

    envio = enviar_email(
        f"[PREGÃO] Queda >4% — {alerta['ticker']}",
        _texto_alerta(alerta),
    )
    status = "ENVIADO" if envio["ok"] else "FALHA_ENVIO"
    atualizacao = {
        "status": status,
        "email_enviado_em": datetime.now(TZ_SP).isoformat() if envio["ok"] else None,
        "erro_envio": envio["erro"],
    }
    try:
        cliente.table("radar_alertas_queda").update(atualizacao).eq("id", alerta_id).execute()
    except Exception as exc:
        # O email pode já ter saído. Log explícito porque um retry posterior
        # pode duplicá-lo se a gravação do status falhar após a entrega.
        print(
            f"[radar_quedas] email_ok={envio['ok']} mas falhou ao salvar "
            f"status do alerta id={alerta_id}: {exc!r}"
        )
        return False

    print(f"[radar_quedas] ticker={alerta['ticker']} status={status} erro={envio['erro']}")
    return bool(envio["ok"])


def executar():
    # Self-test de escrita+leitura ANTES de tentar persistir qualquer
    # coisa (mesmo motivo de coletor_local.py: 1 diagnostico claro na
    # raiz em vez de N excecoes "42501" repetidas, uma por tabela).
    diagnostico = diagnosticar_persistencia()
    if diagnostico["ok"]:
        print("[radar_quedas] persistencia (self-test escrita+leitura): OK")
    else:
        print(
            f"[radar_quedas] persistencia (self-test escrita+leitura): FALHOU "
            f"na etapa {diagnostico['etapa']} - {diagnostico['detalhe']}"
        )

    resultado = processar_monitoramento()
    cliente = obter_cliente()
    if cliente is None:
        print("[radar_quedas] Supabase indisponível; não é possível recuperar alertas pendentes.")
        return 1

    # Não depender apenas de alertas_novos: eles deixam de aparecer nessa lista
    # após a primeira inserção, mesmo se o envio falhar. Reconsultar o banco
    # recupera pendências após timeout, falha SMTP ou interrupção do runner.
    pendentes = _alertas_pendentes(cliente)
    if pendentes is None:
        # Ainda tenta os alertas recém-criados, caso a consulta de recuperação falhe.
        pendentes = resultado.get("alertas_novos", [])

    ids_vistos = set()
    entregues = 0
    falhas = 0
    for alerta in pendentes:
        alerta_id = alerta.get("id")
        if alerta_id is None or alerta_id in ids_vistos:
            continue
        ids_vistos.add(alerta_id)
        if _enviar_alerta(cliente, alerta):
            entregues += 1
        else:
            falhas += 1

    print(
        f"[radar_quedas] coleta_ok={resultado.get('coleta_ok')} "
        f"novos={len(resultado.get('alertas_novos', []))} "
        f"pendentes_processados={len(ids_vistos)} entregues={entregues} falhas={falhas} "
        f"erro_coleta={resultado.get('erro', '')}"
    )
    # Visibilidade no painel SAÚDE DOS DADOS: sem isto, o Radar podia parar
    # de rodar (ou falhar silenciosamente) sem nenhuma linha refletindo
    # isso - a tabela radar_alertas_queda só registra ALERTAS, não a
    # tentativa de execução em si (uma rodada sem nenhuma queda >4% é
    # sucesso legítimo e não deixaria rastro nenhum sem isto).
    registrar_tentativa(
        "RADAR DE QUEDAS",
        "Carteiras recomendadas (Genial + Safra) + cotações (variação diária)",
        execucao_ok=bool(resultado.get("coleta_ok")),
        persistencia_ok=(falhas == 0),
        registros_novos=len(resultado.get("alertas_novos", [])),
        erro=resultado.get("erro") or (f"{falhas} alerta(s) sem envio confirmado" if falhas else None),
        categoria="Radar",
        # Parcial tanto por falha de ENVIO (falhas>0) quanto por falha de
        # COLETA numa fonte só (resultado["erro"] setado mesmo com
        # coleta_ok=True - ver processar_monitoramento: "Execução parcial: ...").
        parcial=bool(resultado.get("coleta_ok")) and bool(falhas or resultado.get("erro")),
    )
    # Falha de fonte também deve ser visível como execução falha, mesmo que
    # uma pendência antiga tenha sido entregue nesta rodada.
    return 0 if resultado.get("coleta_ok") and falhas == 0 else 1


if __name__ == "__main__":
    raise SystemExit(executar())
