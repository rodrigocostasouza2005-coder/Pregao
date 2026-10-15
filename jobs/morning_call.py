# -*- coding: utf-8 -*-
"""Morning Call factual independente de carteiras e do Radar de quedas."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta
from data.mercado import obter_cotacoes_lote
from data.news import obter_top_mercado_tudo
from data.prices import obter_cotacao_indice
from data.supabase_client import obter_cliente
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")
TICKERS_REFERENCIA = ["^BVSP", "USDBRL=X", "ES=F", "NQ=F", "GC=F", "BZ=F"]


def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def _linha_cotacao(titulo, ticker):
    cot = obter_cotacao_indice(titulo, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        return f"- {titulo}: indisponível ({cot.get('erro', 'sem dado') if isinstance(cot, dict) else 'sem dado'})"
    variacao = cot.get("variacao_pct")
    barra = cot.get("_barra_em") or "barra indisponível"
    coleta = cot.get("_coletado_em") or "coleta indisponível"
    return f"- {titulo}: {_fmt_num(cot.get('preco'))}; variação da última barra: {_fmt_num(variacao)}%; barra: {barra}; coleta: {coleta}"


def montar_morning_call(agora=None):
    """Monta texto sem IA: cada número é lido dos provedores existentes."""
    agora = agora or datetime.now(TZ_SP)
    linhas = [
        f"MORNING CALL — {agora.strftime('%d/%m/%Y')}",
        "Pregão | Briefing informativo baseado nos últimos dados disponíveis",
        "",
        "1. MERCADOS",
        _linha_cotacao("Ibovespa", "^BVSP"),
        _linha_cotacao("Dólar (USD/BRL)", "USDBRL=X"),
        _linha_cotacao("S&P 500 futuro", "ES=F"),
        _linha_cotacao("Nasdaq futuro", "NQ=F"),
        _linha_cotacao("Ouro", "GC=F"),
        _linha_cotacao("Petróleo Brent", "BZ=F"),
        "",
        "2. MACRO BRASIL",
    ]
    for nome, fn in (("Selic", obter_selic_meta), ("CDI", obter_cdi),
                     ("Focus IPCA", obter_focus_ipca), ("Focus Selic", obter_focus_selic)):
        try:
            dado = fn()
            if isinstance(dado, pd.DataFrame) and not dado.empty:
                # Selic/CDI sao series por "data"; Focus e' 1 linha por ano de
                # referencia ("ano_referencia", sem coluna "data") - bug real
                # corrigido (2026-10-15): o codigo so conhecia a coluna "data",
                # entao toda linha de Focus caia no fallback "data não
                # informada" truncado em 10 chars ("data não i") e
                # ano_referencia/numero_respondentes apareciam formatados como
                # dinheiro (ex: "2.026,00" em vez de "2026").
                coluna_rotulo = "data" if "data" in dado.columns else (
                    "ano_referencia" if "ano_referencia" in dado.columns else None
                )
                colunas_inteiras = {"ano_referencia", "numero_respondentes"}
                colunas_valor = [col for col in dado.columns if col != coluna_rotulo]
                amostra = dado.tail(3)
                for _, registro in amostra.iterrows():
                    bruto_rotulo = registro.get(coluna_rotulo) if coluna_rotulo else None
                    data_reg = (
                        f"{int(bruto_rotulo)}" if coluna_rotulo == "ano_referencia" and pd.notna(bruto_rotulo)
                        else str(bruto_rotulo)[:10] if pd.notna(bruto_rotulo) else "data não informada"
                    )
                    valores = []
                    for coluna in colunas_valor:
                        valor = registro.get(coluna)
                        if not pd.notna(valor):
                            continue
                        if coluna in colunas_inteiras:
                            valores.append(f"{coluna}={int(valor)}")
                        elif isinstance(valor, (int, float)):
                            valores.append(f"{coluna}={_fmt_num(valor)}")
                        else:
                            valores.append(f"{coluna}={str(valor)[:19]}")
                    linhas.append(f"- {nome} ({data_reg}): " + (", ".join(valores) if valores else "sem valor estruturado"))
            else:
                linhas.append(f"- {nome}: indisponível")
        except Exception:
            linhas.append(f"- {nome}: indisponível")
    linhas += ["", "3. NOTÍCIAS", "Manchetes disponíveis; confira as fontes originais antes de tomar decisões."]
    try:
        noticias = obter_top_mercado_tudo()
        if isinstance(noticias, tuple):
            candidatos = [item for grupo in noticias if isinstance(grupo, list) for item in grupo]
        elif isinstance(noticias, list):
            candidatos = noticias
        else:
            candidatos = []
        for item in candidatos[:12]:
            titulo = str(item.get("titulo") or item.get("title") or "").strip()
            link = str(item.get("link") or item.get("url") or "").strip()
            if titulo:
                linhas.append(f"- {titulo}" + (f" — {link}" if link else ""))
    except Exception:
        linhas.append("- Notícias indisponíveis nesta execução.")
    linhas += [
        "", "4. CENÁRIOS CONDICIONAIS",
        "- Risco global: acompanhe a direção dos futuros americanos, dólar e commodities; confirme os movimentos nas fontes originais.",
        "- Brasil: observe juros futuros, câmbio e notícias fiscais/políticas; o efeito depende da surpresa frente às expectativas.",
        "- Empresas: valide comunicados oficiais e resultados antes de atribuir causalidade a movimentos de preço.",
        "", "LIMITAÇÕES",
        "- Fontes gratuitas podem ter atraso e indisponibilidade; este briefing não garante cotação em tempo real.",
        "- Não foram incluídos preços ou fatos que não puderam ser confirmados nesta execução.",
        "- Conteúdo informativo, não constitui recomendação de investimento.",
    ]
    return "\n".join(linhas)


def executar():
    # Self-test de escrita+leitura ANTES do envio (mesmo motivo de
    # coletor_local.py/jobs/radar_quedas.py: diagnostico claro na raiz
    # em vez de uma falha de persistencia sem explicacao).
    diagnostico = diagnosticar_persistencia()
    if diagnostico["ok"]:
        print("[morning_call] persistencia (self-test escrita+leitura): OK")
    else:
        print(
            f"[morning_call] persistencia (self-test escrita+leitura): FALHOU "
            f"na etapa {diagnostico['etapa']} - {diagnostico['detalhe']}"
        )

    agora = datetime.now(TZ_SP)
    texto = montar_morning_call(agora)
    resultado = enviar_email(f"[PREGÃO] Morning Call — {agora.strftime('%d/%m/%Y')}", texto)
    cliente = obter_cliente()
    persistiu = False
    if cliente is not None:
        try:
            cliente.table("morning_call_execucoes").insert({
                "executado_em": agora.isoformat(),
                "status": "ENVIADO" if resultado["ok"] else "FALHA_ENVIO",
                "erro": resultado["erro"],
                "destinatario": __import__("os").getenv("EMAIL_TO", ""),
                "conteudo": texto,
            }).execute()
            persistiu = True
        except Exception as exc:
            print(f"[morning_call] falha ao registrar execução: {exc!r}")
    print(f"[morning_call] envio_ok={resultado['ok']} erro={resultado['erro']}")
    # Visibilidade no painel SAÚDE DOS DADOS, mesmo motivo do Radar: sem
    # isto, o job rodando mas falhando no envio (ou nem rodando mais)
    # não aparecia em lugar nenhum fora do log do GitHub Actions.
    registrar_tentativa(
        "MORNING CALL",
        "Macro (BCB) + Mercado (yfinance) + NEWS agregados, e-mail (Resend/SMTP)",
        execucao_ok=resultado["ok"],
        persistencia_ok=persistiu,
        erro=resultado["erro"],
        categoria="Morning Call",
    )
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(executar())
