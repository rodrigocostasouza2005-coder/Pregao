# -*- coding: utf-8 -*-
"""Morning Call factual independente de carteiras e do Radar de quedas."""
import hashlib
import html as _html_escape
import os
import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import config
from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.eventos import (
    STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_LABEL, STATUS_PRAZO_CVM,
    calcular_calendario_cacheado,
)
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta, obter_selic_meta_copom
from data.morning_call_editorial import (
    _macro_rows, _referencia_cotacao, filtrar_noticias, montar_edicao, nota_sessao,
)
from data.news import obter_top_mercado, obter_top_mercado_internacional
from data.prices import obter_cotacao_indice
from data.supabase_client import obter_cliente
from data.user_prefs import listar_assinantes_morning_call
from jobs.email_utils import enviar_email
from jobs.morning_call_pdf import gerar_pdf

TZ_SP = ZoneInfo("America/Sao_Paulo")

# Secoes que TODO Morning Call gerado precisa conter - usado por
# gerar_preview() pra validar o conteudo sem depender de nenhum secret de
# e-mail estar configurado (ver docstring de gerar_preview). Se o nome de
# uma secao mudar aqui, mudar junto em montar_morning_call.
#
# Estrutura editorial (2026-10-17, reconciliacao #38 x main pos-#40):
# RESUMO EXECUTIVO / BRASIL / EXTERIOR separados / AGENDA DE HOJE (CVM,
# preservada do #40) / EMPRESAS E SETORES / TENDENCIAS E RISCOS (marcadas
# [INTERPRETACAO], nunca confundidas com fato) / LIMITACOES / FONTES -
# exigencia editorial explicita do Rodrigo, recuperada do PR #38 (que
# ficou tecnicamente obsoleto apos o PR #40, mas tinha essa estrutura que
# nenhum outro PR implementou).
SECOES_OBRIGATORIAS = (
    "1. RESUMO EXECUTIVO",
    "2. BRASIL",
    "3. EXTERIOR",
    "4. AGENDA DE HOJE",
    "5. EMPRESAS E SETORES",
    "6. TENDÊNCIAS E RISCOS A ACOMPANHAR",
    "LIMITAÇÕES",
    "FONTES",
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


def _obter_cotacao_fmt(titulo, ticker):
    """Busca a cotação 1x e devolve (dict bruto, linha de texto) - o dict
    bruto alimenta o RESUMO EXECUTIVO (_bullet_variacao) sem precisar
    buscar de novo (mesmo cache de 30s de obter_cotacao_indice, mas evita
    2 chamadas na mesma execução por clareza)."""
    cot = obter_cotacao_indice(titulo, ticker)
    if not isinstance(cot, dict) or cot.get("erro"):
        erro = cot.get("erro", "sem dado") if isinstance(cot, dict) else "sem dado"
        return cot, f"- {titulo}: indisponível ({erro})"
    variacao = cot.get("variacao_pct")
    # mesma referência do PDF (data/morning_call_editorial.py): horário do
    # último negócio em Brasília ou "fech. dd/mm" - antes saía o índice cru
    # da barra diária ("2026-10-16T00:00:00-04:00"), meia-noite do fuso da bolsa
    referencia, _sessao = _referencia_cotacao(cot)
    linha = (f"- {titulo}: {_fmt_num(cot.get('preco'))}; variação sobre o fechamento anterior: "
             f"{_fmt_num(variacao)}%; referência: {referencia or 'indisponível'}")
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
    return f"- {nome}: {direcao} de {_fmt_num(abs(variacao))}% na última sessão disponível."


def _noticias_por_regiao():
    """Pools Brasil e internacional coletados SEPARADOS (mesmas funções das
    abas BRASIL/INTERNACIONAL do app) - o ranking combinado
    (obter_top_mercado_tudo) cortava o top 20 de BR+INT juntos, e num dia
    de muito noticiário no Brasil a seção EXTERIOR saía vazia (edição de
    18/10/2026). Uma região que falha vira um marcador de erro na lista;
    as duas falhando, lança exceção (seção diz que a coleta falhou)."""
    itens, erros = [], 0
    for regiao, fn in (("BR", obter_top_mercado), ("INT", obter_top_mercado_internacional)):
        try:
            resultado = fn()
        except Exception as exc:
            resultado, motivo = None, f"{type(exc).__name__}: {exc}"
        else:
            motivo = "coleta do Google News falhou nesta execução"
        if resultado is None:
            erros += 1
            itens.append({"_erro_regiao": regiao, "erro": motivo})
        else:
            itens += [{**i, "regiao": i.get("regiao") or regiao} for i in resultado]
    if erros == 2:
        raise RuntimeError("coleta do Google News falhou para Brasil e exterior")
    return itens


def _marca_erro(item, erros):
    if "_erro_regiao" in item:
        erros[item["_erro_regiao"]] = item.get("erro")
        return True
    return False


def _linhas_noticias(itens, limite):
    out = []
    for item in itens[:limite]:
        titulo = str(item.get("titulo") or "").strip()
        link = str(item.get("link") or "").strip()
        if titulo:
            out.append(f"- {titulo}" + (f" — {link}" if link else ""))
    return out


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
    no snapshot (ver docstring da função). Preservada tal como veio do
    PR #40 - base técnica desta seção não mudou na reconciliação
    editorial, só a numeração ("3." -> "4.", por entrarem RESUMO
    EXECUTIVO/BRASIL/EXTERIOR na frente).

    Igual às outras seções (ver BRASIL/EXTERIOR/EMPRESAS E SETORES):
    qualquer falha cai num fallback textual, nunca quebra o e-mail
    inteiro. Ausência real de evento hoje também é dita explicitamente,
    nunca omitida em silêncio."""
    linhas = [
        "", "4. AGENDA DE HOJE",
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
    """Monta texto sem IA: cada número é lido dos provedores existentes.

    Estrutura editorial (cabeçalho · resumo executivo · Brasil · Exterior
    · Agenda de hoje · Empresas e setores · Tendências e riscos ·
    Limitações · Fontes) - sem IA: cada linha vem de um provedor já usado
    em outra aba do PREGÃO (data/prices.py, data/macro.py, data/news.py,
    data/eventos.py). Notícias já chegam classificadas por região
    ("BR"/"INT") e por ticker detectado no título
    (data/news.py:_processar_pool) - reaproveitado aqui, nunca
    reclassificado com regra própria: BR com ticker reconhecido vai pra
    EMPRESAS E SETORES, BR sem ticker fica em BRASIL, INT fica em
    EXTERIOR. Seção/indicador indisponível diz isso explicitamente;
    nunca omitido em silêncio nem substituído por número estimado."""
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
        "CVM (agenda de resultados), Google News (notícias) - detalhe completo na seção FONTES.",
        "",
        "1. RESUMO EXECUTIVO",
        _bullet_variacao("Ibovespa", cot_ibov),
        _bullet_variacao("Dólar (USD/BRL)", cot_dolar),
    ]
    sessao = nota_sessao([{"sessao": _referencia_cotacao(c)[1]} for c in (cot_ibov, cot_dolar)
                          if isinstance(c, dict) and not c.get("erro")], agora)
    if sessao:
        linhas.append(f"- {sessao}")
    linhas += [
        "- Detalhamento completo de mercados, macro, agenda, notícias e riscos nas seções "
        "abaixo; nenhum número deste resumo substitui a conferência na fonte original.",
        "",
        "2. BRASIL",
        linha_ibov,
        linha_dolar,
    ]
    # Mesmas linhas normalizadas do PDF (data/morning_call_editorial.py:
    # _macro_rows) - antes o e-mail listava os nomes crus das colunas
    # ("mediana_pct=5,22; media_pct=...; numero_respondentes=144") e as 3
    # linhas do Focus (até o ano corrente + 2). Provedores passados daqui
    # pra continuar sendo os deste módulo.
    for linha in _macro_rows(agora, provedores={
            "selic": obter_selic_meta, "selic_copom": obter_selic_meta_copom, "cdi": obter_cdi,
            "focus_ipca": obter_focus_ipca, "focus_selic": obter_focus_selic}):
        if linha.get("valor") is None:
            linhas.append(f"- {linha['indicador']}: indisponível ({linha.get('erro') or 'sem dado'})")
            continue
        texto = f"- {linha['indicador']} ({linha['referencia']}): {_fmt_num(linha['valor'])}{linha['unidade']}"
        if linha.get("detalhe"):
            texto += f" — mediana de {linha['detalhe']}" if linha["indicador"].startswith("Focus") else f" — {linha['detalhe']}"
        linhas.append(texto)

    # Noticias: mesma coleta (data/news.py), nunca refeita/reclassificada
    # com regra propria - so' separa por regiao/tickers que o coletor ja'
    # calcula (BR com ticker reconhecido -> EMPRESAS E SETORES; BR sem
    # ticker -> macro Brasil; INT -> EXTERIOR).
    noticias_erro = None
    erros_regiao = {}
    noticias_br_macro, noticias_br_empresa, noticias_intl = [], [], []
    try:
        candidatos = filtrar_noticias(
            [i for i in _noticias_por_regiao() if not _marca_erro(i, erros_regiao)], agora)
        for item in candidatos:
            if item.get("regiao") == "BR":
                (noticias_br_empresa if item.get("tickers") else noticias_br_macro).append(item)
            else:
                noticias_intl.append(item)
    except Exception as exc:
        noticias_erro = f"{type(exc).__name__}: {exc}"

    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif erros_regiao.get("BR"):
        linhas.append(f"- Notícias do Brasil indisponíveis nesta execução ({erros_regiao['BR']}).")
    elif noticias_br_macro:
        linhas += _linhas_noticias(noticias_br_macro, 8)
    else:
        linhas.append("- Nenhuma manchete macro do Brasil nesta coleta.")

    linhas += ["", "3. EXTERIOR", linha_sp, linha_nasdaq, linha_ouro, linha_petroleo]
    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif erros_regiao.get("INT"):
        linhas.append(f"- Notícias internacionais indisponíveis nesta execução ({erros_regiao['INT']}).")
    elif noticias_intl:
        linhas += _linhas_noticias(noticias_intl, 8)
    else:
        linhas.append("- Nenhuma manchete internacional nesta coleta.")

    linhas += _secao_agenda(agora)

    linhas += ["", "5. EMPRESAS E SETORES"]
    if noticias_erro:
        linhas.append(f"- Notícias indisponíveis nesta execução ({noticias_erro}).")
    elif noticias_br_empresa:
        linhas += _linhas_noticias(noticias_br_empresa, 10)
    else:
        linhas.append(
            "- Empresas e Setores: sem fatos relevantes confirmados nesta sessão "
            "(nenhuma manchete desta coleta trouxe um ticker identificável; ver "
            "BRASIL/EXTERIOR para o noticiário macro coletado)."
        )

    linhas += [
        "", "6. TENDÊNCIAS E RISCOS A ACOMPANHAR",
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
        "- Agenda de resultados: CVM (Instrução CVM 480/2009) - ver nota de confiabilidade em cada linha.",
        "- Notícias: Google News (agregador); veículo original e link de cada manchete nas seções acima.",
    ]
    return "\n".join(linhas)


_URL_RE = re.compile(r'(https?://[^\s<>"]+)')
_RE_TITULO_SECAO = re.compile(r"^\d+\.\s")
_RE_TAG_BULLET = re.compile(r"^\[([^\]]+)\]\s*(.*)$")

# Identidade visual do Morning Call (mesma paleta/tipografia do PDF
# editorial - jobs/morning_call_pdf.py - pra coerência visual entre as
# 2 versões): azul-marinho + branco quente + cinza editorial + âmbar de
# destaque; serifada pra manchetes/título, sans-serif pro corpo. Só
# fontes web-safe (sem @font-face: clientes de e-mail bloqueiam fonte
# externa) e só estilo inline (sem <style>: Gmail/Outlook descartam ou
# reinterpretam bloco <style> de formas inconsistentes).
_AZUL_MARINHO = "#0E1B2E"
_BRANCO_QUENTE = "#F7F3ED"
_CINZA_EDITORIAL = "#4A4F57"
_AMBAR = "#E8762C"
_CINZA_FUNDO = "#EFEAE2"
_CINZA_BORDA = "#D9D4CC"
_SERIF = "Georgia,'Times New Roman',Times,serif"
_SANS = "Arial,Helvetica,sans-serif"


def _linkificar(texto_escapado: str) -> str:
    return _URL_RE.sub(
        lambda m: f'<a href="{m.group(1)}" style="color:{_AMBAR};text-decoration:underline;">{m.group(1)}</a>',
        texto_escapado,
    )


def montar_morning_call_html(texto: str) -> str:
    """HTML gerado a partir do MESMO texto simples (fonte única - nunca
    reconsulta nem reformula dado), com apresentação editorial (mesma
    identidade visual do PDF - jobs/morning_call_pdf.py: azul-marinho +
    âmbar + serifada/sans-serif), compatível com clientes de e-mail
    comuns: tabela única pra centralizar a largura de leitura (técnica
    padrão pra Outlook, que ignora `margin:auto` em bloco solto), só
    tags básicas (h1/h2/p/ul/li/a/table) com estilo inline, sem CSS
    externo/JS/<style>. Links (incluindo os das manchetes, reaproveitados
    de data/news.py) continuam clicáveis; nenhum conteúdo novo é
    adicionado - texto e HTML nunca divergem em conteúdo, só em
    apresentação (exigido pelo enviar_email(texto, html=...) de
    jobs/email_utils.py).

    Linhas marcadas "[TAG] resto do texto" (hoje só "[INTERPRETAÇÃO]",
    emitidas por montar_morning_call em TENDÊNCIAS E RISCOS) ganham um
    chip âmbar - mesma distinção visual FATO x INTERPRETAÇÃO do PDF,
    lida do PRÓPRIO texto (nenhuma reclassificação nova feita aqui)."""
    linhas = texto.split("\n")
    conteudo: list = []
    buffer_lista: list = []

    def fechar_lista():
        if buffer_lista:
            conteudo.append(
                f'<ul style="margin:0 0 16px 0;padding:0 0 0 20px;font-family:{_SANS};'
                f'font-size:14px;line-height:1.6;color:{_AZUL_MARINHO};">'
                + "".join(buffer_lista) + "</ul>"
            )
            buffer_lista.clear()

    for i, linha in enumerate(linhas):
        linha = linha.rstrip()
        if not linha:
            fechar_lista()
            continue
        if i == 0:
            conteudo.append(
                f'<h1 style="margin:0;padding:0;font-family:{_SERIF};font-size:24px;'
                f'font-weight:bold;color:{_BRANCO_QUENTE};">{_html_escape.escape(linha)}</h1>'
            )
            continue
        if i == 1:
            conteudo.append(
                f'<p style="margin:16px 0 0 0;font-family:{_SANS};font-size:13px;'
                f'font-style:italic;color:{_CINZA_EDITORIAL};">{_html_escape.escape(linha)}</p>'
            )
            continue
        if _RE_TITULO_SECAO.match(linha) or linha in ("LIMITAÇÕES", "FONTES"):
            fechar_lista()
            conteudo.append(
                f'<h2 style="margin:28px 0 14px 0;padding:10px 16px;background-color:{_AZUL_MARINHO};'
                f'border-left:5px solid {_AMBAR};font-family:{_SERIF};font-size:14px;'
                f'font-weight:bold;letter-spacing:1px;text-transform:uppercase;'
                f'color:{_BRANCO_QUENTE};">{_html_escape.escape(linha)}</h2>'
            )
            continue
        if linha.startswith("- "):
            item = linha[2:]
            tag_match = _RE_TAG_BULLET.match(item)
            if tag_match:
                rotulo, resto = tag_match.group(1), tag_match.group(2)
                chip = (
                    f'<span style="display:inline-block;background-color:{_AMBAR};color:{_BRANCO_QUENTE};'
                    f'font-family:{_SANS};font-size:10px;font-weight:bold;letter-spacing:0.5px;'
                    f'padding:1px 6px;border-radius:3px;margin-right:6px;">'
                    f'{_html_escape.escape(rotulo)}</span>'
                )
                texto_item = (
                    f'<span style="font-style:italic;color:{_CINZA_EDITORIAL};">'
                    f'{_linkificar(_html_escape.escape(resto))}</span>'
                )
                buffer_lista.append(f"<li>{chip}{texto_item}</li>")
            else:
                buffer_lista.append(f"<li>{_linkificar(_html_escape.escape(item))}</li>")
            continue
        fechar_lista()
        conteudo.append(
            f'<p style="margin:0 0 20px 0;padding-bottom:12px;border-bottom:1px solid {_CINZA_BORDA};'
            f'font-family:{_SANS};font-size:11px;color:{_CINZA_EDITORIAL};">'
            f'{_linkificar(_html_escape.escape(linha))}</p>'
        )

    fechar_lista()

    return (
        '<!doctype html>'
        '<html lang="pt-BR">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>'
        f'<body style="margin:0;padding:0;background-color:{_CINZA_FUNDO};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_CINZA_FUNDO};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:640px;width:100%;background-color:{_BRANCO_QUENTE};">'
        '<tr><td style="padding:0;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background-color:{_AZUL_MARINHO};padding:22px 28px 20px 28px;">'
        f'<span style="font-family:{_SERIF};font-size:18px;font-weight:bold;color:{_AMBAR};'
        f'letter-spacing:1px;">PREGÃO</span>'
        f'<span style="font-family:{_SANS};font-size:10px;color:{_BRANCO_QUENTE};'
        f'letter-spacing:3px;padding-left:10px;">MORNING CALL</span>'
        '</td></tr>'
        '<tr><td style="padding:0 28px 22px 28px;">' + "".join(conteudo[:1]) + '</td></tr>'
        f'<tr><td style="padding:0 0 3px 0;background-color:{_AMBAR};font-size:1px;line-height:1px;">&nbsp;</td></tr>'
        '<tr><td style="padding:24px 28px 28px 28px;">' + "".join(conteudo[1:]) + '</td></tr>'
        '</table>'
        '</td></tr>'
        '</table>'
        '</td></tr>'
        '</table>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_CINZA_FUNDO};">'
        '<tr><td align="center" style="padding:0 12px 28px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:640px;width:100%;">'
        f'<tr><td align="center" style="font-family:{_SANS};font-size:10px;color:{_CINZA_EDITORIAL};'
        'padding-top:4px;">PREGÃO · Terminal de Mercado · Conteúdo informativo, não constitui '
        'recomendação de investimento.</td></tr>'
        '</table>'
        '</td></tr>'
        '</table>'
        '</body></html>'
    )


def _assunto(agora, teste=False):
    prefixo = "[TESTE] " if teste else ""
    return f"{prefixo}[PREGÃO] Morning Call — {agora.strftime('%d/%m/%Y')}"


def _montar_anexo_pdf(agora):
    """PDF editorial (data/morning_call_editorial.py + jobs/morning_call_pdf.py)
    montado 1x por execução, nunca por assinante - mesmo texto/dado do
    e-mail, camada de apresentação separada. Qualquer falha (dado ou
    ReportLab) devolve None - quem chama decide degradar pra envio sem
    anexo, nunca deixar a falha da apresentação em PDF impedir o e-mail
    (que é o canal garantido)."""
    try:
        edicao = montar_edicao(agora)
        pdf_bytes = gerar_pdf(edicao)
    except Exception as exc:
        print(f"[morning_call] geração do PDF editorial falhou (enviando sem anexo): {exc!r}")
        return None
    print(f"[morning_call] {_resumo_edicao(edicao, pdf_bytes)}")
    radar = edicao.get("radar") if isinstance(edicao, dict) else None
    return {
        "nome": f"pregao-morning-call-{agora.strftime('%Y-%m-%d')}.pdf",
        "conteudo": pdf_bytes,
        "tipo_mime": "application/pdf",
        # nomes dos setores do radar QUE ESTÃO no PDF anexo (chamada no e-mail);
        # jobs/email_utils.py só lê nome/conteudo/tipo_mime
        "radar_setores": [b.get("nome") for b in (radar or {}).get("setores") or [] if b.get("nome")],
    }


def _resumo_edicao(edicao, pdf_bytes):
    """Linha de log da edição montada - o que de fato foi pro anexo, pra
    conferir a execução real no log do Actions (nunca inclui destinatário
    nem segredo)."""
    if not isinstance(edicao, dict):
        return f"PDF gerado ({len(pdf_bytes or b'')} bytes)"
    partes = []
    for chave, campo in (("brasil", "noticias"), ("empresas", "cards"), ("exterior", "noticias")):
        itens = (edicao.get(chave) or {}).get(campo) or []
        com_texto = sum(1 for i in itens if i.get("corpo"))
        partes.append(f"{chave}={len(itens)} ({com_texto} com texto)")
    macro = [i for i in (edicao.get("brasil") or {}).get("indicadores") or [] if "indicador" in i]
    indisponiveis = [i["indicador"] for i in macro if i.get("valor") is None]
    partes.append("macro indisponível: " + (", ".join(indisponiveis) if indisponiveis else "nenhum"))
    radar = edicao.get("radar") or {}
    partes.append("radar: " + (", ".join(b.get("nome", "?") for b in radar.get("setores") or []) or "vazio"))
    agenda = (edicao.get("empresas") or {}).get("agenda")
    partes.append("agenda: " + ("indisponível" if agenda is None else f"{len(agenda)} evento(s)"))
    try:
        from pypdf import PdfReader
        import io
        partes.append(f"PDF {len(PdfReader(io.BytesIO(pdf_bytes)).pages)} página(s), {len(pdf_bytes)} bytes")
    except Exception:
        partes.append(f"PDF {len(pdf_bytes or b'')} bytes")
    return "edição montada: " + "; ".join(partes)


def _com_chamada_radar(texto, anexo_pdf):
    """Chamada curta do radar setorial no e-mail, antes de LIMITAÇÕES -
    só quando o PDF com o radar foi de fato anexado (nunca anuncia o que
    não está no anexo)."""
    setores = (anexo_pdf or {}).get("radar_setores") or []
    if not setores:
        return texto
    chamada = ("- [RADAR SETORIAL] No PDF anexo: " + ", ".join(setores)
               + " - o que aconteceu, por que importa e o que acompanhar em cada setor, com as fontes.")
    if "\nLIMITAÇÕES" in texto:
        return texto.replace("\nLIMITAÇÕES", "\n" + chamada + "\n\nLIMITAÇÕES", 1)
    return texto + "\n\n" + chamada


def gerar_preview(agora=None):
    """Gera o Morning Call COMPLETO (mesmo texto que seria enviado) e
    valida o conteúdo, SEM NUNCA chamar jobs.email_utils.enviar_email -
    modo de teste explícito pedido pra conferir o e-mail de verdade
    (assunto, todas as seções obrigatórias, quantos assinantes ativos
    receberiam) sem disparo real nem dependência de nenhum secret de
    e-mail estar configurado (EMAIL_PROVIDER/EMAIL_FROM/RESEND_API_KEY/
    etc podem estar todos ausentes - gerar_preview nunca olha pra eles).

    "destinatario" aqui é só o EMAIL_TO legado (usado pelo Radar de
    Quedas e por fallback de jobs/email_utils.py, nunca pelos assinantes
    reais do Morning Call - ver enviar_teste); "total_assinantes_ativos"
    é a contagem REAL (lida do Supabase via listar_assinantes_morning_call)
    de quem receberia o envio automático agora - 0 tanto se não há
    nenhum opt-in quanto se o Supabase estiver indisponível (não dá pra
    distinguir os dois aqui sem mudar o contrato de retorno; ver
    executar() pro log que diferencia de verdade os dois casos).

    Uso manual: `python -c "from jobs.morning_call import gerar_preview;
    p = gerar_preview(); print(p['texto']); print(p['valido'],
    p['secoes_faltantes'])"`. Usado por testes (ver
    tests/test_morning_call.py) pra validar as SECOES_OBRIGATORIAS
    sempre com enviar_email mockado/nunca chamado.

    Retorna {"assunto", "destinatario", "total_assinantes_ativos",
    "texto", "html", "secoes_faltantes", "valido"} - "valido" é True só
    se TODAS as SECOES_OBRIGATORIAS aparecem no texto gerado; nunca
    garante que o provedor de e-mail aceitaria o envio, só que o
    CONTEÚDO está completo."""
    agora = agora or datetime.now(TZ_SP)
    texto = montar_morning_call(agora)
    faltantes = [secao for secao in SECOES_OBRIGATORIAS if secao not in texto]
    assinantes = listar_assinantes_morning_call()
    return {
        "assunto": _assunto(agora),
        "destinatario": os.getenv("EMAIL_TO", "").strip(),
        "total_assinantes_ativos": len(assinantes or []),
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
    assinantes. Assunto marcado com "[TESTE]" (ver _assunto) pra nunca
    ser confundido pelo destinatário com o envio oficial do dia.

    Uso manual (nunca disparar para a lista de assinantes - só pra 1
    endereço de teste autorizado):
    `python -c "from jobs.morning_call import enviar_teste; \
    print(enviar_teste('seu-email-de-teste@exemplo.com'))"`

    Também acionável via GitHub Actions (workflow_dispatch, input
    `teste_destinatario`) - ver .github/workflows/radar-morning-call.yml
    e o bloco __main__ deste módulo (env MORNING_CALL_TESTE_PARA)."""
    destinatario_teste = (destinatario_teste or "").strip()
    if not destinatario_teste:
        return {"ok": False, "erro": "destinatario_teste é obrigatório."}
    agora = agora or datetime.now(TZ_SP)
    anexo_pdf = _montar_anexo_pdf(agora)
    texto = _com_chamada_radar(montar_morning_call(agora), anexo_pdf)
    resultado = enviar_email(
        _assunto(agora, teste=True), texto, html=montar_morning_call_html(texto), destinatario=destinatario_teste,
        anexos=[anexo_pdf] if anexo_pdf else None,
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
    #
    # None (nao []) diferencia "Supabase indisponivel" (falha real de
    # infra - nunca reportar como sucesso silencioso) de "ninguem
    # assinou ainda" (estado normal) - distincao trazida da comparacao
    # com o PR #42 concorrente durante a consolidacao (2026-10-17).
    assinantes = listar_assinantes_morning_call(cliente)
    if assinantes is None:
        print(
            "[morning_call] não foi possível consultar os assinantes opt-in "
            "(Supabase indisponível) - nenhum e-mail enviado nesta execução."
        )
        registrar_tentativa(
            "MORNING CALL",
            "Resumo executivo + Brasil/Exterior + Agenda (CVM) + Empresas e Setores "
            "+ NEWS agregados, e-mail (Resend) por assinante",
            execucao_ok=False,
            persistencia_ok=False,
            erro="Não foi possível consultar os assinantes opt-in (Supabase indisponível).",
            categoria="Morning Call",
        )
        return 1
    if not assinantes:
        print(
            "[morning_call] nenhum assinante ativo nesta execução (nenhum usuário "
            "com a preferência ligada e e-mail válido) - nada a enviar."
        )
        registrar_tentativa(
            "MORNING CALL",
            "Resumo executivo + Brasil/Exterior + Agenda (CVM) + Empresas e Setores "
            "+ NEWS agregados, e-mail (Resend) por assinante",
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
            "Resumo executivo + Brasil/Exterior + Agenda (CVM) + Empresas e Setores "
            "+ NEWS agregados, e-mail (Resend) por assinante",
            execucao_ok=True,
            persistencia_ok=True,
            erro=None,
            categoria="Morning Call",
        )
        return 0

    anexo_pdf = _montar_anexo_pdf(agora)
    texto = _com_chamada_radar(montar_morning_call(agora), anexo_pdf)
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
        resultado = enviar_email(
            assunto, texto, html=html, destinatario=email,
            anexos=[anexo_pdf] if anexo_pdf else None,
        )
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
        "Resumo executivo + Brasil/Exterior + Agenda (CVM) + Empresas e Setores "
        "+ NEWS agregados, e-mail (Resend) por assinante",
        execucao_ok=(falhas == 0),
        persistencia_ok=persistencia_ok,
        erro=algum_erro,
        categoria="Morning Call",
        parcial=bool(enviados and falhas),
    )
    # Job do GitHub Actions só fica vermelho em perda TOTAL (zero
    # sucessos) - uma falha isolada (ex: 1 endereço com bounce
    # permanente) não deve gerar alerta a cada execução; o painel
    # SAÚDE DOS DADOS já mostra a falha parcial via `parcial=True` acima.
    return 1 if (falhas and not enviados) else 0


def _main() -> int:
    """Dispatch do entrypoint de linha de comando - função própria (em
    vez de lógica solta dentro de `if __name__ == "__main__":`) só pra
    ficar testável via chamada direta (ver tests/test_morning_call.py),
    sem precisar reexecutar o módulo inteiro com runpy.

    Disparo manual isolado via GitHub Actions (workflow_dispatch, input
    "teste_destinatario") ou shell local - nunca acionado pelo cron (ver
    .github/workflows/radar-morning-call.yml, que só preenche
    MORNING_CALL_TESTE_PARA quando o input foi explicitamente usado).
    Preenchido -> enviar_teste() (isolado, nunca toca assinantes reais
    nem morning_call_execucoes); vazio (cron ou dispatch sem o campo)
    -> executar() normal, pros assinantes opt-in reais."""
    destinatario_teste = os.getenv("MORNING_CALL_TESTE_PARA", "").strip()
    if destinatario_teste:
        resultado_teste = enviar_teste(destinatario_teste)
        return 0 if resultado_teste["ok"] else 1
    return executar()


if __name__ == "__main__":
    raise SystemExit(_main())
