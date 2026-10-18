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
from data.macro import obter_cdi, obter_focus_ipca, obter_focus_selic, obter_selic_meta
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
            "selic": obter_selic_meta, "cdi": obter_cdi,
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


_RE_TITULO_SECAO = re.compile(r"^\d+\.\s")
_RE_MANCHETE_COM_LINK = re.compile(r"^- (.+?) — (https?://\S+)$")
_RE_CHAMADA_TAG = re.compile(r"^- \[([^\]]+)\]\s*(.*)$")

# Identidade visual do Morning Call - MESMA paleta do PDF editorial
# (jobs/morning_call_pdf.py, PR #62: papel branco + tinta grafite, âmbar
# só como acento - fontes embutidas Source Serif 4/Libre Franklin/IBM
# Plex Mono) - mesmos valores hex, pra e-mail e PDF nunca mais destoarem
# (gap que o próprio PR #62 deixou registrado: "o HTML do e-mail continua
# com a identidade antiga... fica pra um PR separado" - este é esse PR).
# E-mail não pode embutir as TTF (clientes de e-mail bloqueiam
# @font-face), por isso usa pilha de fonte web-safe com o mesmo ESPÍRITO
# tipográfico (serifada pra manchete, sans humanista pro corpo) - nunca
# a fonte exata, que não existe fora do PDF.
_TINTA = "#161514"
_TINTA_SUAVE = "#3B3835"
_CINZA = "#6F6A63"
_FILETE = "#CFC9BF"
_BRANCO = "#FFFFFF"
_FUNDO = "#EFEAE2"
_AMBAR = "#FFA028"
_ALTA = "#1E7A4C"
_BAIXA = "#B4291F"
_SERIF = "Georgia,'Times New Roman',Times,serif"
_SANS = "Arial,Helvetica,sans-serif"


def _extrair_manchetes(texto: str, limite: int = 3) -> list:
    """Manchetes com link (formato "- título — URL", emitido por
    _linhas_noticias em BRASIL/EXTERIOR/EMPRESAS E SETORES) na ordem em
    que aparecem no texto - mesma fonte única de sempre, nenhuma nova
    consulta/ranking. Linha de mercado ("- Ibovespa: 148.320,50; ...")
    nunca bate nesse padrão (usa ": ", não " — "), por isso nunca vira
    manchete por engano."""
    manchetes = []
    for linha in texto.split("\n"):
        m = _RE_MANCHETE_COM_LINK.match(linha.strip())
        if m:
            manchetes.append({"titulo": m.group(1), "link": m.group(2)})
            if len(manchetes) >= limite:
                break
    return manchetes


def _extrair_resumo_executivo(texto: str) -> list:
    """As 2 primeiras linhas de "1. RESUMO EXECUTIVO" (Ibovespa/Dólar -
    ver montar_morning_call) - nunca a 3ª linha fixa ("Detalhamento
    completo... nas seções abaixo"), que não faz sentido numa versão
    resumida sem essas seções."""
    linhas = texto.split("\n")
    dentro = False
    bullets = []
    for linha in linhas:
        linha_strip = linha.strip()
        if linha_strip == "1. RESUMO EXECUTIVO":
            dentro = True
            continue
        if dentro:
            if _RE_TITULO_SECAO.match(linha_strip):
                break
            if linha_strip.startswith("- "):
                bullets.append(linha_strip[2:])
    return bullets[:2]


_TAGS_FORA_DA_CAPA = {"INTERPRETAÇÃO"}  # 3 bullets de "6. TENDÊNCIAS E
# RISCOS A ACOMPANHAR" (ver montar_morning_call) - análise completa só
# faz sentido com o resto da seção ao redor, que só está no PDF; sem o
# filtro, inflava a capa de volta pra "quase texto inteiro", contra o
# pedido explícito de "chamadas curtas".


def _extrair_chamadas_tag(texto: str) -> list:
    """Bullets "- [TAG] resto" em qualquer lugar do texto, EXCETO as em
    _TAGS_FORA_DA_CAPA - genérico de propósito (hoje só "[RADAR
    SETORIAL]", injetada por _com_chamada_radar antes de LIMITAÇÕES),
    pra qualquer chamada futura NO MESMO FORMATO aparecer na capa sem
    precisar de código novo aqui, mas sem reintroduzir seção inteira por
    engano. Nunca confundida com manchete: essa tem link (" — URL"),
    chamada de tag não tem."""
    chamadas = []
    for linha in texto.split("\n"):
        m = _RE_CHAMADA_TAG.match(linha.strip())
        if m and m.group(1) not in _TAGS_FORA_DA_CAPA:
            chamadas.append({"tag": m.group(1), "texto": m.group(2)})
    return chamadas


def _cor_bullet_resumo(bullet_texto: str) -> str:
    if "alta" in bullet_texto:
        return _ALTA
    if "queda" in bullet_texto:
        return _BAIXA
    return _TINTA_SUAVE


def montar_morning_call_html(texto: str) -> str:
    """HTML construído a partir do MESMO texto simples (fonte única -
    nunca reconsulta nem reformula dado): não é mais a reprodução
    completa de todas as seções, e sim uma CAPA DE JORNAL - manchete
    principal + chamadas secundárias + resumo de mercado + uma chamada
    evidente pra abrir o PDF completo (anexo), que tem Brasil/Exterior/
    Empresas e Setores/Mercados/Agenda Econômica/Fontes na íntegra (ver
    jobs/morning_call_pdf.py, PR #62). Compatível com clientes de e-mail
    comuns: tabela única pra centralizar a largura de leitura (técnica
    padrão pra Outlook, que ignora `margin:auto` em bloco solto), só
    tags básicas (h1/h2/p/a/table) com estilo inline, sem CSS externo/
    JS/<style>. Links (reaproveitados de data/news.py) continuam
    clicáveis; nenhum conteúdo novo é adicionado - só uma SELEÇÃO do
    texto já gerado, nunca um fato reformulado ou um número novo."""
    linhas = texto.split("\n")
    titulo = linhas[0] if linhas else ""
    byline = linhas[1] if len(linhas) > 1 else ""

    manchetes = _extrair_manchetes(texto, limite=3)
    resumo_bullets = _extrair_resumo_executivo(texto)

    partes = []

    # -- manchete principal + chamadas secundárias -------------------
    if manchetes:
        principal = manchetes[0]
        partes.append(
            f'<tr><td style="padding:22px 28px 4px 28px;">'
            f'<a href="{_html_escape.escape(principal["link"])}" '
            f'style="font-family:{_SERIF};font-size:23px;line-height:1.3;font-weight:bold;'
            f'color:{_TINTA};text-decoration:none;">{_html_escape.escape(principal["titulo"])}</a>'
            f'</td></tr>'
        )
        for item in manchetes[1:]:
            partes.append(
                f'<tr><td style="padding:10px 28px 0 28px;border-top:1px solid {_FILETE};">'
                f'<a href="{_html_escape.escape(item["link"])}" '
                f'style="font-family:{_SERIF};font-size:15px;line-height:1.35;font-weight:bold;'
                f'color:{_TINTA};text-decoration:none;">{_html_escape.escape(item["titulo"])}</a>'
                f'</td></tr>'
            )
    else:
        partes.append(
            f'<tr><td style="padding:22px 28px 4px 28px;font-family:{_SANS};font-size:13px;'
            f'font-style:italic;color:{_CINZA};">Sem manchete de destaque confirmada nesta '
            f'coleta — veja Brasil/Exterior no PDF em anexo.</td></tr>'
        )

    # -- resumo do dia (Ibovespa/Dólar) -------------------------------
    if resumo_bullets:
        linhas_resumo = "".join(
            f'<span style="display:block;margin-top:4px;color:{_cor_bullet_resumo(b)};">'
            f'{_html_escape.escape(b)}</span>'
            for b in resumo_bullets
        )
        partes.append(
            f'<tr><td style="padding:16px 28px 0 28px;font-family:{_SANS};font-size:12.5px;'
            f'line-height:1.5;">'
            f'<span style="font-family:{_SANS};font-size:10px;font-weight:bold;letter-spacing:1px;'
            f'color:{_CINZA};">RESUMO DO DIA</span>{linhas_resumo}</td></tr>'
        )

    # -- CTA pro PDF em anexo (nunca um link - é um anexo, não uma URL) --
    partes.append(
        f'<tr><td style="padding:22px 28px 0 28px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_TINTA};">'
        f'<tr><td style="padding:3px;background-color:{_AMBAR};font-size:1px;line-height:1px;">&nbsp;</td></tr>'
        f'<tr><td style="padding:16px 20px;">'
        f'<span style="display:block;font-family:{_SANS};font-size:9.5px;font-weight:bold;'
        f'letter-spacing:1.5px;color:{_AMBAR};">EDIÇÃO COMPLETA EM PDF</span>'
        f'<span style="display:block;margin-top:5px;font-family:{_SERIF};font-size:14px;'
        f'color:{_BRANCO};">Brasil, Exterior, Empresas e Setores, Mercados, Agenda Econômica e '
        f'Fontes — no PDF anexado a este e-mail.</span>'
        f'</td></tr></table></td></tr>'
    )

    # -- chamadas "[TAG] resto" (hoje só RADAR SETORIAL) --------------
    for chamada in _extrair_chamadas_tag(texto):
        partes.append(
            f'<tr><td style="padding:10px 28px 0 28px;font-family:{_SANS};font-size:11px;'
            f'line-height:1.5;color:{_TINTA_SUAVE};">'
            f'<span style="display:inline-block;background-color:{_AMBAR};color:{_TINTA};'
            f'font-size:9px;font-weight:bold;letter-spacing:0.5px;padding:1px 6px;'
            f'margin-right:6px;">{_html_escape.escape(chamada["tag"])}</span>'
            f'{_html_escape.escape(chamada["texto"])}</td></tr>'
        )

    corpo = "".join(partes)

    return (
        '<!doctype html>'
        '<html lang="pt-BR">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>'
        f'<body style="margin:0;padding:0;background-color:{_FUNDO};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_FUNDO};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;width:100%;background-color:{_BRANCO};">'
        f'<tr><td style="padding:20px 28px 0 28px;">'
        f'<h1 style="display:inline;margin:0;padding:0;font-family:{_SERIF};font-size:26px;'
        f'font-weight:bold;color:{_TINTA};">PREGÃO</h1>'
        f'<span style="font-family:{_SANS};font-size:10px;color:{_CINZA};letter-spacing:2px;'
        f'padding-left:8px;">MORNING CALL</span>'
        f'</td></tr>'
        f'<tr><td style="padding:6px 28px 0 28px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background-color:{_TINTA};font-size:2px;line-height:2px;">&nbsp;</td></tr>'
        f'</table></td></tr>'
        f'<tr><td style="padding:6px 28px 0 28px;font-family:{_SANS};font-size:11px;'
        f'color:{_CINZA};">{_html_escape.escape(titulo)} · {_html_escape.escape(byline)}</td></tr>'
        + corpo +
        f'<tr><td style="padding:24px 28px 20px 28px;font-family:{_SANS};font-size:9.5px;'
        f'color:{_CINZA};border-top:1px solid {_FILETE};margin-top:20px;">'
        'PREGÃO · Terminal de Mercado · Conteúdo informativo, não constitui recomendação de '
        'investimento.</td></tr>'
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
    radar = edicao.get("radar") if isinstance(edicao, dict) else None
    return {
        "nome": f"pregao-morning-call-{agora.strftime('%Y-%m-%d')}.pdf",
        "conteudo": pdf_bytes,
        "tipo_mime": "application/pdf",
        # nomes dos setores do radar QUE ESTÃO no PDF anexo (chamada no e-mail);
        # jobs/email_utils.py só lê nome/conteudo/tipo_mime
        "radar_setores": [b.get("nome") for b in (radar or {}).get("setores") or [] if b.get("nome")],
    }


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
