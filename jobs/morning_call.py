# -*- coding: utf-8 -*-
"""Morning Call factual independente de carteiras e do Radar de quedas."""
import hashlib
import html as _html_escape
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import config
from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado,
)
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta
from data.mercado import obter_cotacoes_lote
from data.news import obter_top_mercado_tudo
from data.prices import obter_cotacao_indice
from data.supabase_client import obter_cliente
from data.user_prefs import listar_assinantes_morning_call
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")
TICKERS_REFERENCIA = ["^BVSP", "USDBRL=X", "ES=F", "NQ=F", "GC=F", "BZ=F"]

# Secoes que TODO Morning Call gerado precisa conter - usado por
# gerar_preview() pra validar o conteudo sem depender de nenhum secret de
# e-mail estar configurado (ver docstring de gerar_preview). Se a secao de
# AGENDA/NOTICIAS/etc mudar de nome aqui, mudar junto em montar_morning_call.
SECOES_OBRIGATORIAS = (
    "1. MERCADOS",
    "2. MACRO BRASIL",
    "3. AGENDA DE HOJE",
    "4. NOTÍCIAS",
    "5. CENÁRIOS CONDICIONAIS",
    "LIMITAÇÕES",
)

_NOTA_STATUS_EVENTO = {
    STATUS_PRAZO_CVM: "prazo MÁXIMO regulatório da CVM (Instrução CVM 480/2009) — NÃO é uma data anunciada pela empresa.",
    STATUS_CONFIRMADO: "data CONFIRMADA pela própria empresa/fonte oficial.",
    STATUS_ESTIMADO: "data ESTIMADA por fonte externa — ainda não confirmada pela empresa.",
}


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


def _linha_evento(evento):
    status = evento.get("status")
    rotulo_status = STATUS_LABEL.get(status, status or "status desconhecido")
    nota_status = _NOTA_STATUS_EVENTO.get(status, "nível de confiabilidade da data não identificado.")
    horario = evento.get("horario")
    sufixo_horario = f" às {horario}" if horario else " (sem horário divulgado)"
    empresa = evento.get("empresa") or evento.get("ticker") or "Empresa não identificada"
    tipo = evento.get("tipo_evento") or "EVENTO"
    periodo = f" {evento['periodo']}" if evento.get("periodo") else ""
    return (
        f"- {empresa} ({evento.get('ticker', '?')}): {tipo}{periodo}{sufixo_horario} "
        f"— {rotulo_status}: {nota_status}"
    )


def _secao_agenda(agora):
    """Eventos do CALENDÁRIO (data/eventos.py) com data=hoje (fuso
    America/Sao_Paulo) - hoje só resultados corporativos (ITR/DFP), ver
    docstring do módulo pra por quê não há CONFIRMADO/ESTIMADO de fontes
    adicionais ainda. Usa calcular_calendario_cacheado (mesma função que
    ui/calendario_tab.py usa) pra ler o snapshot já persistido pelo
    coletor em vez de recalcular o universo inteiro (CVM) a cada envio -
    só recalcula ao vivo os tickers que por algum motivo não estiverem
    no snapshot (ver docstring da função).

    Igual às outras seções (ver NOTÍCIAS acima): qualquer falha cai num
    fallback textual, nunca quebra o e-mail inteiro. Ausência real de
    evento hoje também é dita explicitamente, nunca omitida em silêncio."""
    linhas = [
        "", "3. AGENDA DE HOJE",
        "Eventos do calendário de resultados corporativos (CVM) com data de hoje; "
        "o status indica o quão confiável é a data (veja a nota em cada linha).",
    ]
    try:
        tickers = list(config.IBOVESPA_SETORES.keys())
        eventos = calcular_calendario_cacheado(tickers, hoje=agora.date())
        eventos_hoje = [e for e in eventos if e.get("data") == agora.date()]
        if not eventos_hoje:
            linhas.append("- Nenhum evento relevante identificado para hoje.")
        else:
            eventos_hoje.sort(key=lambda e: (e.get("horario") or "99:99", e.get("ticker") or ""))
            for evento in eventos_hoje:
                linhas.append(_linha_evento(evento))
    except Exception:
        linhas.append("- Agenda do dia indisponível nesta execução.")
    return linhas


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
    linhas += _secao_agenda(agora)
    linhas += ["", "4. NOTÍCIAS", "Manchetes disponíveis; confira as fontes originais antes de tomar decisões."]
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
        "", "5. CENÁRIOS CONDICIONAIS",
        "- Risco global: acompanhe a direção dos futuros americanos, dólar e commodities; confirme os movimentos nas fontes originais.",
        "- Brasil: observe juros futuros, câmbio e notícias fiscais/políticas; o efeito depende da surpresa frente às expectativas.",
        "- Empresas: valide comunicados oficiais e resultados antes de atribuir causalidade a movimentos de preço.",
        "", "LIMITAÇÕES",
        "- Fontes gratuitas podem ter atraso e indisponibilidade; este briefing não garante cotação em tempo real.",
        "- Não foram incluídos preços ou fatos que não puderam ser confirmados nesta execução.",
        "- Conteúdo informativo, não constitui recomendação de investimento.",
    ]
    return "\n".join(linhas)


_RE_URL = re.compile(r"(https?://[^\s<>()]+)")
_RE_TITULO_SECAO = re.compile(r"^\d+\.\s")


def montar_morning_call_html(texto: str) -> str:
    """Converte o TEXTO já montado por montar_morning_call() num HTML
    simples compatível com a maioria dos clientes de e-mail: títulos de
    seção numerados (ex: "1. MERCADOS") viram <h2>, demais linhas não
    vazias viram parágrafos, URLs cruas (ex: link de notícia) viram
    links clicáveis. Nunca reconsulta os provedores - só reformata o
    MESMO texto (garante que a versão HTML e a versão texto simples
    nunca divergem em conteúdo, só em apresentação, exigido pelo
    enviar_email(texto, html=...) de jobs/email_utils.py)."""
    linhas_html = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        escapada = _RE_URL.sub(
            lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>',
            _html_escape.escape(linha),
        )
        if _RE_TITULO_SECAO.match(linha) or linha in ("LIMITAÇÕES",):
            linhas_html.append(f"<h2 style='margin:18px 0 6px 0;font-size:16px'>{escapada}</h2>")
        else:
            linhas_html.append(f"<p style='margin:0 0 4px 0'>{escapada}</p>")
    corpo = "\n".join(linhas_html)
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body style='font-family:Arial,Helvetica,sans-serif;font-size:14px;"
        "color:#111;max-width:680px;margin:0 auto'>"
        f"{corpo}"
        "</body></html>"
    )


def _assunto(agora):
    return f"[PREGÃO] Morning Call — {agora.strftime('%d/%m/%Y')}"


def gerar_preview(agora=None):
    """Gera o Morning Call COMPLETO (mesmo texto que seria enviado) e
    valida o conteúdo, SEM NUNCA chamar jobs.email_utils.enviar_email -
    modo de teste explícito pedido pra conferir o e-mail de verdade
    (assunto, todas as seções obrigatórias, quantos assinantes ativos
    receberiam) sem disparo real nem dependência de nenhum secret de
    e-mail estar configurado (EMAIL_PROVIDER/EMAIL_FROM/RESEND_API_KEY/
    etc podem estar todos ausentes - gerar_preview nunca olha pra eles).

    "destinatario" aqui é só o EMAIL_TO legado (usado pelo caminho
    administrativo/teste manual, nunca pelos assinantes reais - ver
    enviar_teste); "total_assinantes_ativos" é a contagem REAL (lida do
    Supabase via listar_assinantes_morning_call) de quem receberia o
    envio automático agora - 0 tanto se não há nenhum opt-in quanto se
    o Supabase estiver indisponível (não dá pra distinguir os dois sem
    uma segunda leitura; ver executar() pro log que diferencia).

    Uso manual: `python -c "from jobs.morning_call import gerar_preview;
    p = gerar_preview(); print(p['texto']); print(p['valido'],
    p['secoes_faltantes'])"`. Usado por testes (ver
    tests/test_morning_call.py) pra validar as 6 seções obrigatórias
    (SECOES_OBRIGATORIAS) sempre com enviar_email mockado/nunca chamado.

    Retorna {"assunto", "destinatario", "total_assinantes_ativos",
    "texto", "secoes_faltantes", "valido"} - "valido" é True só se
    TODAS as SECOES_OBRIGATORIAS aparecem no texto gerado; nunca
    garante que o provedor de e-mail aceitaria o envio, só que o
    CONTEÚDO está completo."""
    agora = agora or datetime.now(TZ_SP)
    texto = montar_morning_call(agora)
    faltantes = [secao for secao in SECOES_OBRIGATORIAS if secao not in texto]
    return {
        "assunto": _assunto(agora),
        "destinatario": os.getenv("EMAIL_TO", "").strip(),
        "total_assinantes_ativos": len(listar_assinantes_morning_call()),
        "texto": texto,
        "html": montar_morning_call_html(texto),
        "secoes_faltantes": faltantes,
        "valido": not faltantes,
    }


def _hash_destinatario(email: str) -> str:
    """Identificador curto e irreversível (sha256[:10]) de um e-mail, só
    pra correlacionar linhas de log da MESMA execução sem nunca expor o
    e-mail completo em stdout/log do GitHub Actions (exigência
    explícita da missão - o e-mail completo só existe na coluna
    `destinatario` do próprio Supabase, nunca em log de texto)."""
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()[:10]


def _ja_enviado_hoje(cliente, agora, destinatario: str) -> bool:
    """True se já existe um registro status="ENVIADO" em
    morning_call_execucoes PRA ESSE `destinatario` com executado_em no
    MESMO dia (fuso America/Sao_Paulo) de `agora` - usado por
    executar() pra nunca disparar um e-mail duplicado pro MESMO
    assinante num reenvio manual (ex: "Re-run failed jobs" no GitHub
    Actions re-rodando um job que já tinha entregue com sucesso pra
    alguns assinantes, ou um operador rodando o script à mão 2x no
    mesmo dia) - a verificação é por destinatário, não mais global:
    um assinante que falhou continua elegível pra retry no mesmo dia
    mesmo que outro já tenha recebido com sucesso.

    cliente=None (Supabase fora do ar/sem credencial) -> False: a
    VERIFICAÇÃO em si falhando nunca BLOQUEIA o envio - mesmo espírito
    de degradação do resto do arquivo (melhor um e-mail duplicado raro
    do que nenhum e-mail em um dia em que o Supabase esteja fora do
    ar). Mesma lógica se a própria consulta lançar excecao."""
    if cliente is None:
        return False
    inicio_dia_br = datetime.combine(agora.date(), time.min, tzinfo=TZ_SP)
    inicio_dia_utc = inicio_dia_br.astimezone(timezone.utc)
    try:
        resp = (
            cliente.table("morning_call_execucoes")
            .select("id")
            .eq("status", "ENVIADO")
            .eq("destinatario", destinatario)
            .gte("executado_em", inicio_dia_utc.isoformat())
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        print(f"[morning_call] falha ao verificar envio duplicado (seguindo com o envio): {exc!r}")
        return False


def enviar_teste(destinatario_teste: str, agora=None) -> dict:
    """Envio ADMINISTRATIVO/manual pra UM único destinatário fixo,
    passado explicitamente por quem chama - nunca usa
    listar_assinantes_morning_call nem a lista real de assinantes, e
    NUNCA grava em morning_call_execucoes (não deve contaminar a
    idempotência diária de nenhum assinante real nem ser contado como
    envio automático nas métricas de executar()). Separação exigida
    pela missão: teste/validação manual vs. envio automático aos
    assinantes.

    Uso manual (nunca disparar para a lista de assinantes - só pra 1
    endereço de teste autorizado):
    `python -c "from jobs.morning_call import enviar_teste; \
    print(enviar_teste('seu-email-de-teste@exemplo.com'))"`"""
    destinatario_teste = (destinatario_teste or "").strip()
    if not destinatario_teste:
        return {"ok": False, "erro": "destinatario_teste é obrigatório."}
    agora = agora or datetime.now(TZ_SP)
    texto = montar_morning_call(agora)
    resultado = enviar_email(
        _assunto(agora), texto, html=montar_morning_call_html(texto), destinatario=destinatario_teste,
    )
    print(f"[morning_call] envio de TESTE administrativo (nao e' assinante real) ok={resultado['ok']} erro={resultado['erro']}")
    return resultado


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
    cliente = obter_cliente()

    # Destinatarios dinamicos: todo usuario autenticado com a preferencia
    # 'morning_call_email_ativo'=True em user_prefs E e-mail valido (ver
    # data/user_prefs.py:listar_assinantes_morning_call) - já vem
    # deduplicado por e-mail. NUNCA usa EMAIL_TO como lista de
    # assinantes (EMAIL_TO so' existe pra jobs/email_utils.py decidir um
    # destinatario quando nenhum e' passado explicitamente - aqui
    # SEMPRE passamos destinatario=email por assinante).
    assinantes = listar_assinantes_morning_call(cliente)
    if not assinantes:
        print(
            "[morning_call] nenhum assinante ativo nesta execução (nenhum usuário "
            "com a preferência ligada e e-mail válido, ou Supabase indisponível) "
            "- nada a enviar."
        )
        registrar_tentativa(
            "MORNING CALL",
            "Macro (BCB) + Mercado (yfinance) + NEWS agregados, e-mail (Resend) por assinante",
            execucao_ok=True,
            persistencia_ok=(cliente is not None),
            erro=None,
            categoria="Morning Call",
        )
        return 0

    # Idempotencia POR ASSINANTE: um retry manual (ou "Re-run failed
    # jobs" no GitHub Actions) rodando executar() de novo no MESMO dia
    # não deve duplicar e-mail pra quem já recebeu com sucesso hoje, mas
    # continua elegível quem ainda não recebeu/falhou antes.
    pendentes = [email for email in assinantes if not _ja_enviado_hoje(cliente, agora, email)]
    if not pendentes:
        print(
            f"[morning_call] Morning Call de {agora.strftime('%d/%m/%Y')} já foi ENVIADO "
            f"hoje pra todos os {len(assinantes)} assinante(s) ativo(s) - pulando "
            "novo envio (retry/re-run, não é erro)."
        )
        registrar_tentativa(
            "MORNING CALL",
            "Macro (BCB) + Mercado (yfinance) + NEWS agregados, e-mail (Resend) por assinante",
            execucao_ok=True,
            persistencia_ok=True,
            erro=None,
            categoria="Morning Call",
        )
        return 0

    texto = montar_morning_call(agora)
    html = montar_morning_call_html(texto)
    assunto = _assunto(agora)

    enviados = 0
    falhas = 0
    persistencia_ok = True
    algum_erro = None
    for email in pendentes:
        # Uma falha de envio/persistência PARA UM assinante nunca pode
        # impedir a tentativa pros demais - cada iteração é independente
        # (mesmo espírito de salvar_carteiras/processar_monitoramento em
        # data/radar_quedas.py: falha parcial nunca é reportada como
        # sucesso total nem interrompe o laço).
        resultado = enviar_email(assunto, texto, html=html, destinatario=email)
        status = "ENVIADO" if resultado["ok"] else "FALHA_ENVIO"
        if resultado["ok"]:
            enviados += 1
        else:
            falhas += 1
            algum_erro = algum_erro or resultado["erro"]
        if cliente is not None:
            try:
                cliente.table("morning_call_execucoes").insert({
                    "executado_em": agora.isoformat(),
                    "status": status,
                    "erro": resultado["erro"],
                    "destinatario": email,
                    "conteudo": texto,
                }).execute()
            except Exception as exc:
                persistencia_ok = False
                print(
                    f"[morning_call] destinatario={_hash_destinatario(email)} "
                    f"envio_ok={resultado['ok']} mas falhou ao registrar execução: {exc!r}"
                )
        print(f"[morning_call] destinatario={_hash_destinatario(email)} envio_ok={resultado['ok']} erro={resultado['erro']}")

    pulados = len(assinantes) - len(pendentes)
    print(
        f"[morning_call] assinantes_ativos={len(assinantes)} enviados={enviados} "
        f"falhas={falhas} ja_enviados_hoje={pulados}"
    )
    # Visibilidade no painel SAÚDE DOS DADOS, mesmo motivo do Radar: sem
    # isto, o job rodando mas falhando no envio (ou nem rodando mais)
    # não aparecia em lugar nenhum fora do log do GitHub Actions. Uma
    # falha parcial (alguns assinantes falharam, outros não) nunca é
    # reportada como sucesso total: execucao_ok só é True se NENHUM
    # assinante elegível falhou.
    registrar_tentativa(
        "MORNING CALL",
        "Macro (BCB) + Mercado (yfinance) + NEWS agregados, e-mail (Resend) por assinante",
        execucao_ok=(falhas == 0),
        persistencia_ok=persistencia_ok,
        erro=algum_erro,
        categoria="Morning Call",
        parcial=bool(enviados and falhas),
    )
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    raise SystemExit(executar())
