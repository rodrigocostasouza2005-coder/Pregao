# -*- coding: utf-8 -*-
"""Aba MORNING CALL (ui/morning_call_tab.py): horário fora do previsto
explícito (21/10/2026 a edição saiu às ~12:58 BRT), cores do tema e um
botão por ação."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import ui.morning_call_tab as mc

TZ = ZoneInfo("America/Sao_Paulo")


def test_aviso_de_atraso_so_depois_do_horario_previsto():
    assert mc.aviso_atraso(datetime(2026, 10, 21, 8, 3, tzinfo=TZ)) is None
    assert mc.aviso_atraso(datetime(2026, 10, 21, 9, 7, tzinfo=TZ)) is None
    aviso = mc.aviso_atraso(datetime(2026, 10, 21, 12, 58, tzinfo=TZ))
    assert aviso and "fora do horário previsto" in aviso
    # registro em UTC (como vem do banco) é convertido antes de comparar
    assert mc.aviso_atraso(datetime(2026, 10, 21, 11, 5, tzinfo=ZoneInfo("UTC"))) is None


def test_html_do_briefing_usa_as_cores_do_tema():
    html = mc._bloco_editorial_html("1. RESUMO EXECUTIVO\n- [INTERPRETAÇÃO] Juros devem seguir altos.\n- Fato.")
    assert "var(--destaque)" in html and "var(--painel-bg)" in html and "var(--borda)" in html
    fonte = Path(mc.__file__).read_text(encoding="utf-8")
    trecho = fonte.split("def _bloco_editorial_html", 1)[1].split("def _exibir_texto", 1)[0]
    import re
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", trecho), "cor fixa ignora o tema do usuário (CLARO fica ilegível)"


def test_appteste_edicao_atrasada_mostra_aviso_e_botao_unico():
    from streamlit.testing.v1 import AppTest

    script = '''
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import ui.morning_call_tab as mc
ed = {"data": datetime(2026, 10, 21).date(), "executado_em": datetime(2026, 10, 21, 15, 58, tzinfo=ZoneInfo("UTC")),
      "conteudo": "1. RESUMO EXECUTIVO\\n- Ibovespa abriu em alta.", "status": "ENVIADA"}
with patch.object(mc, "listar_edicoes", return_value=[ed]), \\
     patch.object(mc, "obter_sintese_mercado", return_value={"ok": False, "motivo": "teste"}), \\
     patch.object(mc, "_alertas_confiabilidade_cacheados", return_value=[]):
    mc.render_edicao_atual({})
'''
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "gerada às 12:58" in textos and "fora do horário previsto" in textos
    rotulos = [b.label for b in at.button]
    assert rotulos.count("GERAR JORNAL COMPLETO") == 1
    assert not any("ATUALIZAR" in r for r in rotulos)  # sem prévia ainda, só a ação de gerar


def test_aviso_quando_a_edicao_de_hoje_nao_saiu():
    from datetime import date
    quinta_11h40 = datetime(2026, 10, 22, 11, 40, tzinfo=TZ)
    aviso = mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 21), quinta_11h40)
    assert aviso and "22/10" in aviso and "21/10" in aviso
    # ainda dentro do horário previsto, com edição de hoje, ou fim de semana: nada
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 21), datetime(2026, 10, 22, 9, 0, tzinfo=TZ)) is None
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 22), quinta_11h40) is None
    assert mc.aviso_edicao_de_hoje_ausente(date(2026, 10, 23), datetime(2026, 10, 24, 11, 0, tzinfo=TZ)) is None
    assert "ainda não foi gerada" in mc.aviso_edicao_de_hoje_ausente(None, quinta_11h40)


def test_noticia_vira_manchete_clicavel_e_marca_traducao():
    html_pt = mc._bloco_editorial_html(
        "MORNING CALL — 22/10/2026\nGerado em 22/10/2026 08:03\n\n3. EXTERIOR\n"
        "- Inflação do Reino Unido sobe (original: UK inflation jumps) — https://www.cnbc.com/a\n"
        "- IBM stock falls [em inglês - tradução indisponível nesta edição] — https://www.marketwatch.com/b\n")
    assert "href='https://www.cnbc.com/a'" in html_pt and ">Inflação do Reino Unido sobe</a>" in html_pt
    assert "TRADUZIDO" in html_pt and "original: UK inflation jumps" in html_pt
    assert "EN · SEM TRADUÇÃO" in html_pt and "tradução indisponível nesta edição]" not in html_pt
    assert "cnbc.com ↗" in html_pt
    # cabeçalho sem a caixa "BRIEFING" repetindo o título; "Gerado em" fica como texto discreto
    assert "BRIEFING" not in html_pt and "MORNING CALL — 22/10/2026" not in html_pt
    assert "Gerado em 22/10/2026 08:03" in html_pt


def test_linha_sem_link_continua_texto_e_html_e_escapado():
    out = mc._bloco_editorial_html("1. RESUMO EXECUTIVO\n- Ibovespa <b>sobe</b> 1%\n")
    assert "&lt;b&gt;sobe&lt;/b&gt;" in out
    assert mc._item_noticia_html("Ibovespa sobe 1%") is None


# --- Reconstrução de UX (22/10/2026): indicador vira card, não mais um
# bullet dentro de caixa dentro de caixa (ver docstring de
# ui/morning_call_tab.py e docs/sprint-20261022.md, "Fase 1/2"). -----------

def test_linha_de_cotacao_vira_card_de_indicador_nao_bullet():
    # formato exato de jobs/morning_call.py:_obter_cotacao_fmt
    linha = "Ibovespa: 148.320,50; variação sobre o fechamento anterior: 0,54%; referência: 22/10 09:43 (horário de Brasília)"
    card = mc._indicador_da_linha(linha)
    assert card is not None
    assert "mc-indicador" in card and "148.320,50" in card and "alta" in card
    assert "22/10 09:43 (horário de Brasília)" in card
    # com cache: marca o rótulo entre parênteses
    card_cache = mc._indicador_da_linha(linha + " [último valor válido - cache de 15 min]")
    assert "cache de 15 min" in card_cache
    # negativo usa a classe de baixa
    card_queda = mc._indicador_da_linha(
        "Dólar (USD/BRL): 5,40; variação sobre o fechamento anterior: -1,20%; referência: indisponível")
    assert "baixa" in card_queda
    # indisponível (fonte não respondeu): card com "indisponível", não bullet de texto
    card_erro = mc._indicador_da_linha("Ouro: indisponível nesta edição (a fonte não respondeu)")
    assert card_erro is not None and "indisponível" in card_erro


def test_linha_macro_vira_card_de_indicador():
    # formato exato de jobs/morning_call.py:_macro_rows
    card = mc._indicador_da_linha("Selic meta (vigente desde 30/10/2025): 15,00% a.a.")
    assert card is not None and "15,00% a.a." in card and "vigente desde 30/10/2025" in card
    card_detalhe = mc._indicador_da_linha("Focus IPCA 2026 (boletim 17/10/2026): 4,20% — mediana de 144 respondentes")
    assert card_detalhe is not None and "mediana de 144 respondentes" in card_detalhe
    card_erro = mc._indicador_da_linha("Selic meta: indisponível (BCB não respondeu nesta execução)")
    assert card_erro is not None and "BCB não respondeu nesta execução" in card_erro
    # texto comum (não indicador) não deve ser classificado como card
    assert mc._indicador_da_linha("Nenhuma manchete macro do Brasil nesta coleta.") is None


def test_bloco_editorial_agrupa_indicadores_e_nao_tem_caixa_dupla():
    texto = (
        "2. BRASIL\n"
        "- Ibovespa: 148.320,50; variação sobre o fechamento anterior: 0,54%; referência: 22/10 09:43 (horário de Brasília)\n"
        "- Dólar (USD/BRL): 5,40; variação sobre o fechamento anterior: -0,10%; referência: 22/10 09:43 (horário de Brasília)\n"
        "- Manchete de notícia — https://exemplo.com/a\n"
    )
    out = mc._bloco_editorial_html(texto)
    assert out.count("class='mc-indicadores'") == 1  # um único agrupamento, não 2 cards soltos no meio do texto
    assert "mc-indicador-nome" in out
    assert "mc-secao" in out and "mc-secao-titulo" in out
    # a caixa antiga (seção com borda própria + item com fundo/borda própria) não existe mais
    assert "border-radius:5px" not in out and "border-radius:2px" not in out


def test_estilo_mc_reserva_mono_a_numero_e_usa_fonte_editorial_na_prosa():
    estilo = mc._estilo_mc()
    assert "Georgia" in estilo or "Source Serif" in estilo  # manchete/prosa, não mais tudo monoespaçado
    assert "Libre Franklin" in estilo
    assert ".mc-prosa" in estilo and "IBM Plex Mono" in estilo  # mono continua reservada (indicador/ticker)


def test_card_indicador_estruturado_cotacao_e_macro():
    cot = {"nome": "Ibovespa", "preco": 148320.5, "variacao_pct": 0.54, "barra_fmt": "22/10 09:43 (horário de Brasília)", "erro": None}
    card = mc._card_indicador_estruturado(cot)
    assert "Ibovespa" in card and "alta" in card
    cot_erro = {"nome": "Ouro", "preco": None, "variacao_pct": None, "barra_fmt": None, "erro": "sem dado"}
    assert "indisponível" in mc._card_indicador_estruturado(cot_erro)
    macro = {"indicador": "Selic meta", "valor": 15.0, "unidade": "% a.a.", "referencia": "vigente desde 30/10/2025", "detalhe": None, "erro": None}
    card_macro = mc._card_indicador_estruturado(macro)
    assert "Selic meta" in card_macro and "15,00% a.a." in card_macro


def test_card_noticia_estruturada_com_imagem_e_traducao():
    fato = {
        "titulo": "Inflação do Reino Unido sobe", "titulo_original": "UK inflation jumps",
        "link": "https://www.cnbc.com/a", "veiculo": "CNBC", "corpo": ["Primeiro parágrafo.", "Segundo."],
        "imagem": "https://www.cnbc.com/foto.jpg",
    }
    card = mc._card_noticia_estruturada(fato)
    assert "href='https://www.cnbc.com/a'" in card and "Inflação do Reino Unido sobe" in card
    assert "TRADUZIDO" in card and "UK inflation jumps" in card
    assert "src='https://www.cnbc.com/foto.jpg'" in card
    assert "Primeiro parágrafo." in card and "Segundo." in card
    # sem imagem: nunca inventa uma genérica no lugar
    fato_sem_imagem = {**fato, "imagem": None, "titulo_original": None, "sem_traducao": True}
    card2 = mc._card_noticia_estruturada(fato_sem_imagem)
    assert "mc-noticia-img" not in card2 and "EN · SEM TRADUÇÃO" in card2


def test_linha_agenda_estruturada_nao_inventa_horario():
    from datetime import date
    evento = {"empresa": "Petrobras", "ticker": "PETR4", "tipo_evento": "ITR", "periodo": "3T25",
              "data": date(2026, 10, 28), "horario": None, "status_rotulo": "CONFIRMADO",
              "status_nota": "data CONFIRMADA pela própria empresa/fonte oficial."}
    linha = mc._linha_agenda_estruturada(evento)
    assert "28/10" in linha and "PETR4" in linha and "3T25" in linha
    assert "sem horário divulgado" in linha  # nunca inventa um horário que a fonte não deu
    assert "CONFIRMADO" in linha


def test_render_edicao_estruturada_html_monta_secoes_principais():
    edicao = {
        "agora": datetime(2026, 10, 22, 9, 0, tzinfo=TZ),
        "capa": {"indicadores": [], "destaques": [], "manchete": None, "chamadas": []},
        "brasil": {"indicadores": [{"nome": "Ibovespa", "preco": 148320.5, "variacao_pct": 0.54,
                                     "barra_fmt": "22/10 09:00", "erro": None}],
                   "noticias": [{"titulo": "Fato relevante da Vale", "link": "https://exemplo.com/vale",
                                 "veiculo": "Valor", "corpo": [], "imagem": None}],
                   "noticias_erro": None},
        "exterior": {"indicadores": [], "noticias": None, "noticias_erro": "coleta do Google News falhou nesta execução"},
        "empresas": {"cards": [], "agenda": [], "agenda_proximos": None, "noticias_erro": None},
        "radar": None,
        "mercados_nota": None,
        "limitacoes": ("Conteúdo informativo, não constitui recomendação de investimento.",),
        "fontes": ("Cotações: Yahoo Finance.",),
    }
    out = mc.render_edicao_estruturada_html(edicao)
    assert "BRASIL" in out and "EXTERIOR" in out and "EMPRESAS E SETORES" in out
    assert "Fato relevante da Vale" in out and "href='https://exemplo.com/vale'" in out
    assert "coleta do Google News falhou nesta execução" in out
    assert "LIMITAÇÕES" in out and "FONTES" in out
    # agenda_hoje=[] (calendário rodou, sem evento) é diferente de None
    # (calendário falhou) - a seção aparece com a mensagem certa, não some
    assert "AGENDA" in out and "Nenhum evento relevante identificado para hoje" in out
    assert "Próximos dias" not in out  # agenda_proximos=None: calendário não rodou pra essa parte


# --- Reformulação Morning Call (24/10/2026): teses de research numa seção
# própria, separada de catalisador/risco - antes tudo misturado numa única
# seção rotulada "MARKET MAKERS" (rótulo que ficou órfão depois da remoção
# da aba MARKET MAKERS; data/market_makers.py continua existindo, é a
# fachada compartilhada com o RADAR, só a apresentação no Morning Call
# mudou). None (fonte falhou) nunca é tratado como "sem conteúdo" (lista
# vazia, fonte respondeu) - mensagens diferentes pro leitor nos dois casos.

from datetime import date as _date  # noqa: E402 (import local ao bloco, mesmo padrão já usado acima)

_MM_BASE_EDICAO = {
    "agora": datetime(2026, 10, 24, 9, 0, tzinfo=TZ),
    "capa": {"indicadores": [], "destaques": [], "manchete": None, "chamadas": []},
    "brasil": {"indicadores": [], "noticias": None, "noticias_erro": None},
    "exterior": {"indicadores": [], "noticias": None, "noticias_erro": None},
    "empresas": {"cards": [], "agenda": None, "agenda_proximos": None, "noticias_erro": None},
    "radar": None, "mercados_nota": None, "limitacoes": (), "fontes": (),
}


def test_card_tese_research_com_fonte_e_sem_fonte():
    mudanca = {"ticker": "PETR4", "categoria": "Research — recomendação/preço-alvo",
               "descricao": "Genial revisou PETR4 de NEUTRO para COMPRA",
               "data_evento": _date(2026, 10, 20), "fonte_label": "Genial", "fonte_url": "https://genial.com/x"}
    card = mc._card_tese_research(mudanca)
    assert "PETR4" in card and "20/10/2026" in card
    assert "Genial revisou PETR4 de NEUTRO para COMPRA" in card
    assert "href='https://genial.com/x'" in card and ">Genial ↗</a>" in card
    # sem fonte_label/fonte_url: nunca inventa casa nem link quebrado
    sem_fonte = {**mudanca, "fonte_label": None, "fonte_url": None}
    card2 = mc._card_tese_research(sem_fonte)
    assert "CASA NÃO IDENTIFICADA" in card2 and "fonte não identificada nesta execução" in card2
    assert "<a href=" not in card2.split("mc-tese-fonte")[1]


def test_teses_research_falha_de_coleta_distinta_de_ausencia_legitima():
    # None: a própria consulta de inteligência de mercado falhou (RuntimeError
    # em data/market_makers.py:inteligencia_mercado) - FALHA, não "sem dado"
    falhou = mc.render_edicao_estruturada_html({**_MM_BASE_EDICAO, "market_makers": None})
    assert "TESES E RECOMENDAÇÕES DE RESEARCH" in falhou
    assert "Indisponível nesta execução" in falhou
    assert "CATALISADORES E ALERTAS" not in falhou  # sem dado nenhum pra mostrar, bloco nem aparece

    # dict vazio: a consulta respondeu, só não achou nada pros tickers do dia
    # - estado vazio informativo, nunca a mesma frase de falha
    vazio = mc.render_edicao_estruturada_html(
        {**_MM_BASE_EDICAO, "market_makers": {"mudancas": [], "catalisadores": [], "riscos": {}}})
    assert "Nenhuma mudança de tese ou recomendação de research verificada" in vazio
    assert "Indisponível nesta execução" not in vazio
    assert "CATALISADORES E ALERTAS" not in vazio  # catalisadores e riscos também vazios


def test_teses_research_com_dado_real_separadas_de_catalisador_e_risco():
    mm = {
        "mudancas": [{"ticker": "VALE3", "categoria": "Research — recomendação/preço-alvo",
                       "descricao": "XP elevou VALE3 para COMPRA", "data_evento": _date(2026, 10, 22),
                       "fonte_label": "XP Investimentos", "fonte_url": "https://xpi.com.br/y"}],
        "catalisadores": [{"ticker": "VALE3", "categoria": "Resultado corporativo",
                            "data": _date(2026, 11, 10), "status_label": "PRAZO CVM", "confirmado": False}],
        "riscos": {"VALE3": ["dívida líquida/EBITDA elevada (4.2x)"]},
    }
    out = mc.render_edicao_estruturada_html({**_MM_BASE_EDICAO, "market_makers": mm})
    teses_bloco = out.split("TESES E RECOMENDAÇÕES DE RESEARCH", 1)[1].split("CATALISADORES E ALERTAS", 1)[0]
    assert "XP Investimentos" in teses_bloco and "VALE3" in teses_bloco and "XP elevou VALE3 para COMPRA" in teses_bloco
    catalisador_bloco = out.split("CATALISADORES E ALERTAS", 1)[1]
    assert "Resultado corporativo" in catalisador_bloco and "10/11/2026" in catalisador_bloco
    assert "PRAZO CVM" in catalisador_bloco  # confirmado=False cai no status_label, não vira "CONFIRMADO"
    assert "dívida líquida/EBITDA elevada" in catalisador_bloco
    # a tese (XP/VALE3) não aparece de novo dentro do bloco de catalisador/risco
    assert "XP elevou VALE3" not in catalisador_bloco


# --- Revisão pré-merge do PR #135 (achados corrigidos nesta revisão) ------

def test_url_http_segura_rejeita_esquema_perigoso():
    assert mc._url_http_segura("https://exemplo.com/a") == "https://exemplo.com/a"
    assert mc._url_http_segura("http://exemplo.com/a") == "http://exemplo.com/a"
    assert mc._url_http_segura("javascript:alert(1)") is None
    assert mc._url_http_segura("data:text/html,<script>alert(1)</script>") is None
    assert mc._url_http_segura("/caminho/relativo") is None
    assert mc._url_http_segura(None) is None
    assert mc._url_http_segura("") is None


def test_card_noticia_estruturada_nunca_vira_href_com_esquema_perigoso():
    fato = {"titulo": "Manchete suspeita", "link": "javascript:alert(document.cookie)",
            "veiculo": "Fonte", "corpo": [], "imagem": "javascript:alert(1)"}
    card = mc._card_noticia_estruturada(fato)
    assert "javascript:" not in card
    # sem link seguro, o título vira texto simples (não <a href>) em vez de omitir a notícia
    assert "<span class='mc-noticia-titulo'>Manchete suspeita</span>" in card
    assert "mc-noticia-img" not in card  # imagem com esquema perigoso não vira <img src>


def test_render_edicao_estruturada_html_agenda_distingue_falha_de_vazio():
    base = {
        "agora": datetime(2026, 10, 22, 9, 0, tzinfo=TZ),
        "capa": {"indicadores": [], "destaques": [], "manchete": None, "chamadas": []},
        "brasil": {"indicadores": [], "noticias": None, "noticias_erro": None},
        "exterior": {"indicadores": [], "noticias": None, "noticias_erro": None},
        "radar": None, "mercados_nota": None, "limitacoes": (), "fontes": (),
    }
    # as duas falharam (None): a seção inteira não aparece (nada a dizer)
    sem_agenda = mc.render_edicao_estruturada_html(
        {**base, "empresas": {"cards": [], "agenda": None, "agenda_proximos": None, "noticias_erro": None}})
    assert "AGENDA" not in sem_agenda
    # próximos dias rodou e achou eventos, hoje não rodou: só "Próximos dias" aparece
    from datetime import date
    so_proximos = mc.render_edicao_estruturada_html({**base, "empresas": {
        "cards": [], "agenda": None,
        "agenda_proximos": [{"empresa": "Vale", "ticker": "VALE3", "tipo_evento": "ITR", "periodo": "3T26",
                             "data": date(2026, 10, 30), "horario": None,
                             "status_rotulo": "ESTIMADO", "status_nota": ""}],
        "noticias_erro": None}})
    assert "AGENDA" in so_proximos and "Próximos dias" in so_proximos and "VALE3" in so_proximos
    assert "<div class='mc-agenda-grupo-titulo'>Hoje</div>" not in so_proximos


def test_atualizar_previa_limpa_cache_do_pdf_junto():
    """Achado da revisão: .clear() do st.cache_data limpa TODA a função, não
    só a hora atual (confirmado direto na API do streamlit.runtime.caching -
    f.clear() refaz a chamada pra QUALQUER argumento já visto). _pdf_bytes
    (hora_ref) tem cache PRÓPRIO e chama _edicao_estruturada(hora_ref) por
    dentro - sem limpar os dois juntos, clicar ATUALIZAR PRÉVIA invalidava
    o dict mas deixava o PDF e o "ver conteúdo na tela" de RELATÓRIO
    COMPLETO com os bytes antigos pra mesma hora_ref: exatamente a
    inconsistência aba/PDF que este PR promete resolver. Guarda estática
    (não depende de simular sessão/cache real do Streamlit, que AppTest não
    isola de forma confiável entre chamadas de .clear()): o branch do botão
    ATUALIZAR PRÉVIA precisa limpar as DUAS funções."""
    import inspect

    fonte = inspect.getsource(mc.render_edicao_atual)
    bloco_atualizar = fonte.split("if tem_previa:", 1)[1].split("st.session_state.pop(\"mc_previa\"", 1)[0]
    assert "_edicao_estruturada.clear()" in bloco_atualizar
    assert "_pdf_bytes.clear()" in bloco_atualizar
