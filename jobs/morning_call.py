# -*- coding: utf-8 -*-
"""Morning Call factual independente de carteiras e do Radar de quedas."""
import html as html_lib
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta
from data.news import obter_top_mercado_tudo
from data.prices import obter_cotacao_indice
from data.supabase_client import obter_cliente
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")

# Modo da execução: AGENDADO (cron, 08h BRT seg-sex - só 1 envio "oficial"
# por pregão) ou TESTE (workflow_dispatch manual, nunca conta pra
# deduplicação do envio agendado nem pode ser confundido com ele no
# histórico). Lido do ambiente (GitHub Actions passa via env no step) -
# nunca lido de secrets, não é informação sensível.
MODO_AGENDADO = "AGENDADO"
MODO_TESTE = "TESTE"


def _modo_execucao() -> str:
    valor = os.getenv("MORNING_CALL_MODO", MODO_AGENDADO).strip().upper()
    return valor if valor in (MODO_AGENDADO, MODO_TESTE) else MODO_AGENDADO


def _fmt_num(valor, casas=2):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "indisponível"


def _obter_cotacao_fmt(titulo, ticker):
    """Busca a cotação 1x e devolve (dict bruto, linha de texto) - o dict
    bruto alimenta o RESUMO EXECUTIVO sem precisar buscar de novo (mesmo
    cache de 30s de obter_cotacao_indice, mas evita 2 chamadas na mesma
    execução por clareza)."""
    cot = obter_cotacao_indice(titulo, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        erro = cot.get("erro", "sem dado") if isinstance(cot, dict) else "sem dado"
        return cot, f"- {titulo}: indisponível ({erro})"
    variacao = cot.get("variacao_pct")
    barra = cot.get("_barra_em") or "barra indisponível"
    coleta = cot.get("_coletado_em") or "coleta indisponível"
    linha = f"- {titulo}: {_fmt_num(cot.get('preco'))}; variação da última barra: {_fmt_num(variacao)}%; barra: {barra}; coleta: {coleta}"
    return cot, linha


def _bullet_variacao(nome, cot):
    """Bullet factual (nunca interpretativo) pro RESUMO EXECUTIVO - só
    direção e magnitude já calculadas por data/prices.py, nunca um
    número novo."""
    if not isinstance(cot, dict) or cot.get("erro"):
        return f"- {nome}: dado indisponível nesta execução."
    variacao = cot.get("variacao_pct")
    if variacao is None:
        return f"- {nome}: sem variação calculável nesta execução."
    if variacao > 0:
        direcao = "alta"
    elif variacao < 0:
        direcao = "queda"
    else:
        direcao = "estável"
    return f"- {nome}: {direcao} de {_fmt_num(abs(variacao))}% na última barra disponível."


def _linhas_noticias(itens, limite):
    out = []
    for item in itens[:limite]:
        titulo = str(item.get("titulo") or "").strip()
        link = str(item.get("link") or "").strip()
        if titulo:
            out.append(f"- {titulo}" + (f" — {link}" if link else ""))
    return out


def montar_morning_call(agora=None):
    """Monta texto sem IA: cada número é lido dos provedores existentes.

    Estrutura pedida (cabeçalho · resumo executivo · Brasil · Exterior ·
    Empresas e setores · Tendências e riscos · Limitações · Fontes) - sem
    IA: cada linha vem de um provedor já usado em outra aba do PREGÃO
    (data/prices.py, data/macro.py, data/news.py). Notícias já chegam
    classificadas por região ("BR"/"INT") e por ticker detectado no
    título (data/news.py:_processar_pool) - reaproveitado aqui, nunca
    reclassificado com regra própria. Seção/indicador indisponível diz
    isso explicitamente; nunca omitido em silêncio nem substituído por
    número estimado."""
    agora = agora or datetime.now(TZ_SP)

    cot_ibov, linha_ibov = _obter_cotacao_fmt("Ibovespa", "^BVSP")
    cot_dolar, linha_dolar = _obter_cotacao_fmt("Dólar (USD/BRL)", "USDBRL=X")
    _, linha_sp = _obter_cotacao_fmt("S&P 500 futuro", "ES=F")
    _, linha_nasdaq = _obter_cotacao_fmt("Nasdaq futuro", "NQ=F")
    _, linha_ouro = _obter_cotacao_fmt("Ouro", "GC=F")
    _, linha_petroleo = _obter_cotacao_fmt("Petróleo Brent", "BZ=F")

    linhas = [
        f"MORNING CALL — {agora.strftime('%d/%m/%Y')}",
        "Pregão | Briefing informativo baseado nos últimos dados disponíveis",
        "",
        f"Gerado em {agora.strftime('%d/%m/%Y %H:%M')} (horário de Brasília, UTC-3 fixo - "
        "sem horário de verão desde 2019) · período analisado: última barra/leitura "
        "disponível em cada fonte (ver horário por linha abaixo) · fontes consultadas: "
        "Yahoo Finance (cotações), Banco Central do Brasil/Boletim Focus (indicadores), "
        "Google News (notícias) - detalhe completo na seção FONTES.",
        "",
        "1. RESUMO EXECUTIVO",
        _bullet_variacao("Ibovespa", cot_ibov),
        _bullet_variacao("Dólar (USD/BRL)", cot_dolar),
        "- Detalhamento completo de mercados, macro, notícias e riscos nas seções abaixo; "
        "nenhum número deste resumo substitui a conferência na fonte original.",
        "",
        "2. BRASIL",
        linha_ibov,
        linha_dolar,
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

    # Noticias: mesma coleta (data/news.py), nunca refeita/reclassificada
    # com regra propria - so' separa por regiao/tickers que o coletor ja'
    # calcula (BR com ticker reconhecido -> EMPRESAS E SETORES; BR sem
    # ticker -> macro Brasil; INT -> EXTERIOR).
    noticias_erro = None
    noticias_br_macro, noticias_br_empresa, noticias_intl = [], [], []
    try:
        noticias = obter_top_mercado_tudo()
        candidatos = noticias if isinstance(noticias, list) else []
        for item in candidatos:
            if item.get("regiao") == "BR":
                (noticias_br_empresa if item.get("tickers") else noticias_br_macro).append(item)
            else:
                noticias_intl.append(item)
    except Exception as exc:
        noticias_erro = f"{type(exc).__name__}: {exc}"

    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif noticias_br_macro:
        linhas += _linhas_noticias(noticias_br_macro, 8)
    else:
        linhas.append("- Nenhuma manchete macro do Brasil nesta coleta.")

    linhas += ["", "3. EXTERIOR", linha_sp, linha_nasdaq, linha_ouro, linha_petroleo]
    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif noticias_intl:
        linhas += _linhas_noticias(noticias_intl, 8)
    else:
        linhas.append("- Nenhuma manchete internacional nesta coleta.")

    linhas += ["", "4. EMPRESAS E SETORES"]
    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif noticias_br_empresa:
        linhas += _linhas_noticias(noticias_br_empresa, 10)
    else:
        linhas.append(
            "- Nenhuma manchete desta coleta trouxe um ticker identificável; "
            "ver BRASIL/EXTERIOR para o noticiário macro coletado."
        )

    linhas += [
        "", "5. TENDÊNCIAS E RISCOS A ACOMPANHAR",
        "- [INTERPRETAÇÃO] Risco global: acompanhe a direção dos futuros americanos, dólar e "
        "commodities; confirme os movimentos nas fontes originais.",
        "- [INTERPRETAÇÃO] Brasil: observe juros futuros, câmbio e notícias fiscais/políticas; "
        "o efeito depende da surpresa frente às expectativas.",
        "- [INTERPRETAÇÃO] Empresas: valide comunicados oficiais e resultados antes de "
        "atribuir causalidade a movimentos de preço.",
        "", "LIMITAÇÕES",
        "- Fontes gratuitas podem ter atraso e indisponibilidade; este briefing não garante cotação em tempo real.",
        "- Não foram incluídos preços ou fatos que não puderam ser confirmados nesta execução.",
        "- Linhas marcadas [INTERPRETAÇÃO] são leitura de cenário, não fato nem previsão garantida; "
        "o restante do conteúdo é dado reportado pelas fontes citadas.",
        "- Conteúdo informativo, não constitui recomendação de investimento.",
        "", "FONTES",
        "- Cotações: Yahoo Finance (yfinance) - dados podem ter atraso conforme o provedor.",
        "- Indicadores macro: Banco Central do Brasil (Selic/CDI) e Boletim Focus (BCB).",
        "- Notícias: Google News (agregador); veículo original e link de cada manchete nas seções acima.",
    ]
    return "\n".join(linhas)


_URL_RE = re.compile(r'(https?://[^\s<>"]+)')


def _linkificar(texto_escapado: str) -> str:
    return _URL_RE.sub(lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', texto_escapado)


def montar_morning_call_html(texto: str) -> str:
    """HTML mínimo gerado a partir do MESMO texto simples (fonte única -
    nunca reconsulta nem reformula dado), compatível com clientes de
    e-mail comuns: só tags básicas (h1/h2/p/ul/li/a) com estilo inline,
    sem CSS externo/JS. Links (incluindo os das manchetes) continuam
    clicáveis; nenhum conteúdo novo é adicionado."""
    linhas = texto.split("\n")
    partes = [
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'color:#1a1a1a;line-height:1.5;max-width:640px;margin:0 auto;">'
    ]
    buffer_lista: list = []

    def fechar_lista():
        if buffer_lista:
            partes.append("<ul>" + "".join(buffer_lista) + "</ul>")
            buffer_lista.clear()

    for i, linha in enumerate(linhas):
        linha = linha.rstrip()
        if not linha:
            fechar_lista()
            continue
        if i == 0:
            partes.append(f"<h1 style=\"font-size:18px;margin-bottom:4px;\">{html_lib.escape(linha)}</h1>")
            continue
        if i == 1:
            partes.append(f"<p style=\"color:#555;margin-top:0;\">{html_lib.escape(linha)}</p>")
            continue
        if re.match(r"^\d+\.\s", linha) or linha in ("LIMITAÇÕES", "FONTES"):
            fechar_lista()
            partes.append(
                f"<h2 style=\"font-size:15px;border-top:1px solid #ddd;padding-top:8px;\">"
                f"{html_lib.escape(linha)}</h2>"
            )
            continue
        if linha.startswith("- "):
            buffer_lista.append(f"<li>{_linkificar(html_lib.escape(linha[2:]))}</li>")
            continue
        fechar_lista()
        partes.append(f"<p>{_linkificar(html_lib.escape(linha))}</p>")

    fechar_lista()
    partes.append("</div>")
    return "\n".join(partes)


def _ja_enviado_hoje(cliente, pregao: str) -> bool:
    """True só se já existe um envio AGENDADO (não TESTE) com status
    ENVIADO pra esse pregão - usado pra nunca duplicar o Morning Call
    oficial do dia num retry/reexecução. Nunca bloqueia o envio por
    engano: se a consulta falhar (ex: coluna 'pregao'/'modo' ainda não
    migrada via sql/radar_research.sql), assume que não foi enviado
    ainda, só loga - o self-test de persistência em executar() já cobre
    o diagnóstico de schema ausente."""
    try:
        resp = (
            cliente.table("morning_call_execucoes")
            .select("id")
            .eq("pregao", pregao)
            .eq("modo", MODO_AGENDADO)
            .eq("status", "ENVIADO")
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        print(f"[morning_call] falha ao checar envio duplicado (assumindo não enviado): {exc!r}")
        return False


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
    modo = _modo_execucao()
    pregao = agora.date().isoformat()
    cliente = obter_cliente()

    # Retry controlado sem duplicar envio: só se aplica ao envio AGENDADO
    # (workflow_dispatch com job='morning_call' e teste explícito usa
    # MODO_TESTE e nunca é bloqueado por isto nem conta pra deduplicação
    # do envio oficial do dia).
    if modo == MODO_AGENDADO and cliente is not None and _ja_enviado_hoje(cliente, pregao):
        motivo = f"Morning Call de {pregao} já enviado com sucesso nesta execução agendada; envio ignorado para não duplicar."
        print(f"[morning_call] {motivo}")
        registrar_tentativa(
            "MORNING CALL",
            "Macro (BCB) + Mercado (yfinance) + NEWS agregados, e-mail (Resend/SMTP)",
            execucao_ok=True,
            persistencia_ok=True,
            registros_novos=0,
            erro=None,
            categoria="Morning Call",
        )
        return 0

    texto = montar_morning_call(agora)
    html_corpo = montar_morning_call_html(texto)
    assunto = f"[PREGÃO] Morning Call — {agora.strftime('%d/%m/%Y')}"
    if modo == MODO_TESTE:
        assunto += " [TESTE]"
    resultado = enviar_email(assunto, texto, html=html_corpo)
    persistiu = False
    if cliente is not None:
        try:
            cliente.table("morning_call_execucoes").insert({
                "executado_em": agora.isoformat(),
                "pregao": pregao,
                "modo": modo,
                "status": "ENVIADO" if resultado["ok"] else "FALHA_ENVIO",
                "erro": resultado["erro"],
                "destinatario": os.getenv("EMAIL_TO", ""),
                "conteudo": texto,
            }).execute()
            persistiu = True
        except Exception as exc:
            print(f"[morning_call] falha ao registrar execução: {exc!r}")
    print(f"[morning_call] modo={modo} envio_ok={resultado['ok']} erro={resultado['erro']}")
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
