# -*- coding: utf-8 -*-
"""Worker independente: monitoramento de quedas e e-mail por evento."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from data.radar_quedas import processar_monitoramento
from data.supabase_client import obter_cliente
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")


def executar():
    resultado = processar_monitoramento()
    cliente = obter_cliente()
    if cliente is None:
        return 1
    for alerta in resultado.get("alertas_novos", []):
        texto = (
            f"RADAR DE QUEDAS — {alerta['ticker']}\n\n"
            f"Variação diária: {alerta['variacao_pct']:.2f}%\n"
            f"Preço: {alerta['preco_atual']:.2f}\n"
            f"Fechamento anterior: {alerta['fechamento_anterior']:.2f}\n"
            f"Cotação: {alerta['cotacao_em']} ({alerta['tipo_cotacao']})\n"
            f"Casas: {', '.join(alerta['casas'])}\n"
            f"Carteiras: {', '.join(alerta['carteiras'])}\n"
            f"Fontes: {' | '.join(alerta['fontes'])}\n"
            "\nAlerta informativo, não constitui recomendação de investimento."
        )
        envio = enviar_email(f"[PREGÃO] Queda >4% — {alerta['ticker']}", texto)
        try:
            cliente.table("radar_alertas_queda").update({
                "status": "ENVIADO" if envio["ok"] else "FALHA_ENVIO",
                "email_enviado_em": datetime.now(TZ_SP).isoformat() if envio["ok"] else None,
                "erro_envio": envio["erro"],
            }).eq("id", alerta["id"]).execute()
        except Exception as exc:
            print(f"[radar_quedas] falha ao registrar resultado do email: {exc!r}")
    print(f"[radar_quedas] {resultado}")
    return 0 if resultado.get("coleta_ok") else 1


if __name__ == "__main__":
    raise SystemExit(executar())
