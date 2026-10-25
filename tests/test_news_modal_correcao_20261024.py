# -*- coding: utf-8 -*-
"""Correção cirúrgica do modal de NOTÍCIA (2026-10-24, ui/news_tab.py:
_abrir_card/_capa_html) - pedido do Rodrigo com captura de tela:
área de imagem grande e vazia, título que quebra em muitas linhas,
botão "ABRIR MATÉRIA" sem destaque. Cobre os 8 cenários pedidos:

1. Renderização do modal com imagem válida.
2. Fallback quando a imagem estiver ausente ou falhar.
3. Exibição correta de títulos longos.
4. Renderização do resumo e dos metadados.
5. Abertura da URL original válida.
6. Ausência de ação funcional quando a URL não for válida.
7. Fechamento do modal e comportamento da rolagem (CSS - o fechar em si
   é o X nativo do st.dialog, nunca um botão próprio; não há como
   exercitar scroll real em bare mode, então aqui só confirmamos que o
   mecanismo CSS existe e que nada no código desenha um "fechar" próprio
   que pudesse competir com o nativo).
8. Ausência de regressões - ver também
   tests/test_news_imagens_pipeline.py::test_12d_regressoes_da_validacao_visual
   (atualizado nesta mesma correção) e a suíte completa de
   tests/test_news_*.py, rodada sem alteração de comportamento fora do
   escopo descrito aqui.

Mesmo padrão bare-mode de tests/test_news_card_editorial_v5.py
(_abrir_card.__wrapped__, sem o decorador @st.dialog)."""
from unittest.mock import patch

import ui.news_tab as news_tab_mod

_ITEM_BASE = {
    "titulo": "Alfa revisa plano de investimentos",
    "titulos": ["Alfa revisa plano de investimentos"],
    "veiculos": ["InfoMoney"],
    "fontes": [{"veiculo": "InfoMoney", "link": "https://news.google.com/alfa"}],
    "fontes_count": 1,
    "data": "2026-10-19T10:00:00-03:00",
    "link": "https://news.google.com/alfa",
    "score": 70,
    "selo": "PROVÁVEL",
    "regras": [],
    "cvm_confirmacao": None,
    "tickers": [],
}

_RESUMO_SIMPLES = {
    "resumo": "RESUMO:\nA empresa Alfa anunciou revisão do plano de investimentos.",
    "qualidade_texto": "full_text",
    "motivo_indisponivel": None,
}


def _renderizar(item, resultado_resumo, imagem_pronta=None, tickers_watchlist=None):
    """Variante de _renderizar (ver test_news_card_editorial_v5.py) que
    NÃO mocka _renderizar_capa/st.link_button por fora - deixa a capa e
    o botão renderizarem de verdade, só com a camada de rede (download/
    reencode da imagem) mockada, pra inspecionar o HTML/chamada real."""
    capturado = []
    link_button_calls = []
    with patch.object(news_tab_mod, "obter_resumo_grupo", return_value=resultado_resumo), \
         patch.object(news_tab_mod, "imagem_pronta_do_grupo", return_value=imagem_pronta), \
         patch.object(news_tab_mod, "obter_recomendacoes", return_value=[]), \
         patch.object(news_tab_mod, "_capa_data_uri", return_value=None), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda h, **k: capturado.append(h)), \
         patch.object(news_tab_mod.st, "caption", side_effect=lambda t, **k: capturado.append(str(t))), \
         patch.object(news_tab_mod.st, "link_button", side_effect=lambda *a, **k: link_button_calls.append((a, k))), \
         patch.object(news_tab_mod.st, "spinner") as mock_spinner:
        mock_spinner.return_value.__enter__ = lambda self: None
        mock_spinner.return_value.__exit__ = lambda self, *a: False
        news_tab_mod._abrir_card.__wrapped__(item, tickers_watchlist or [])
    return capturado, link_button_calls


# --- 1. imagem válida ---------------------------------------------------------

def test_1_imagem_valida_renderiza_img_com_fallback_oculto_pronto():
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta="https://cdn.example.com/foto.jpg")
    html_capa = next(h for h in capturado if "news-capa" in h)
    assert "<img src='https://cdn.example.com/foto.jpg'" in html_capa
    assert "object-fit" not in html_capa  # isso é CSS, não inline - a estrutura só precisa do <img>
    assert "news-capa-vazia" not in html_capa  # com imagem real, nunca a classe compacta
    # fallback continua no DOM (oculto) - cobre o caso de a imagem falhar em runtime (JS)
    assert "news-capa-fallback' style='display:none;'" in html_capa
    assert "InfoMoney" in html_capa


# --- 2. fallback (ausente ou falha) -------------------------------------------

def test_2a_sem_imagem_usa_fallback_compacto_com_classe_vazia():
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta=None)
    html_capa = next(h for h in capturado if "news-capa" in h)
    assert "<img" not in html_capa  # nunca desenha <img> sem candidata real
    assert "news-capa-vazia" in html_capa  # classe que zera a altura reservada
    assert "SEM IMAGEM" in html_capa
    assert "InfoMoney" in html_capa  # identificação da fonte preservada


def test_2b_sem_veiculo_identificado_mostra_rotulo_generico_nunca_vazio():
    item = dict(_ITEM_BASE, veiculos=[])
    capturado, _ = _renderizar(item, _RESUMO_SIMPLES, imagem_pronta=None)
    html_capa = next(h for h in capturado if "news-capa" in h)
    assert "fonte não identificada" in html_capa or "fonte nao identificada" in html_capa.lower() or "FONTE" in html_capa.upper()


def test_2c_falha_de_download_cai_pro_link_direto_com_fallback_pronto():
    """_capa_data_uri (download/reencode no servidor) falhando -> ainda
    assim usa a URL direta (2a via, já existente) com o fallback oculto
    no DOM pra cobrir a falha de carregamento no navegador."""
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta="https://bloqueada.example.com/x.jpg")
    html_capa = next(h for h in capturado if "news-capa" in h)
    assert "<img src='https://bloqueada.example.com/x.jpg'" in html_capa
    assert "display:none;" in html_capa


# --- 3. títulos longos ---------------------------------------------------------

def test_3_titulo_longo_nunca_e_truncado_no_modal():
    titulo_longo = (
        "Conselho de administração aprova revisão completa do plano estratégico "
        "de investimentos para os próximos cinco anos, com foco em eficiência "
        "operacional e redução de endividamento de longo prazo"
    )
    item = dict(_ITEM_BASE, titulo=titulo_longo, titulos=[titulo_longo])
    capturado, _ = _renderizar(item, _RESUMO_SIMPLES, imagem_pronta=None)
    html_titulo = next(h for h in capturado if "news-headline" in h)
    assert titulo_longo in html_titulo  # texto integral, nenhum "…" de corte
    assert "…" not in html_titulo


def test_3b_css_do_titulo_nao_limita_largura_artificialmente():
    """Achado real da captura: max-width:34ch forçava quebra mesmo com
    largura de sobra no dialog "large" - removido nesta correção."""
    fonte = open(news_tab_mod.__file__, encoding="utf-8").read()
    bloco_headline = fonte.split('div[data-testid="stDialog"] .news-headline {', 1)[1].split("}", 1)[0]
    assert "max-width: 34ch" not in bloco_headline
    assert "max-width: none" in bloco_headline


# --- 4. resumo e metadados ------------------------------------------------------

def test_4_resumo_e_metadados_aparecem_juntos():
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta=None)
    texto = "\n".join(capturado)
    assert "news-resumo-rotulo" in texto and "gerado por IA" in texto
    assert "A empresa Alfa anunciou revisão" in texto
    html_meta = next(h for h in capturado if "news-meta-line" in h)
    assert "InfoMoney" in html_meta  # fonte
    assert "10:00" in html_meta  # hora
    assert "PROV 70" in html_meta  # selo + score (só se o campo existir - aqui existe)
    assert "1 fonte" in html_meta  # contagem real de fontes


def test_4b_sem_cvm_confirmacao_nunca_inventa_link_de_documento_oficial():
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta=None)
    html_meta = next(h for h in capturado if "news-meta-line" in h)
    assert "documento oficial CVM" not in html_meta


# --- 5/6. botão ABRIR MATÉRIA — URL válida / inválida --------------------------

def test_5_url_valida_abre_com_link_button_no_destino_original():
    _, chamadas = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta=None)
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[1] == "https://news.google.com/alfa"  # destino original preservado
    assert kwargs.get("use_container_width") is True


def test_6a_url_vazia_nunca_mostra_botao_funcional():
    item = dict(_ITEM_BASE, link="")
    capturado, chamadas = _renderizar(item, _RESUMO_SIMPLES, imagem_pronta=None)
    assert chamadas == []  # st.link_button nunca chamado
    assert any("indisponível" in str(c).lower() for c in capturado)


def test_6b_url_relativa_ou_nao_http_nunca_mostra_botao_funcional():
    for link_invalido in ("/materia/123", "javascript:alert(1)", None):
        item = dict(_ITEM_BASE, link=link_invalido)
        _, chamadas = _renderizar(item, _RESUMO_SIMPLES, imagem_pronta=None)
        assert chamadas == [], f"link inválido {link_invalido!r} não deveria chamar link_button"


def test_6c_helper_de_validacao_isolado():
    assert news_tab_mod._link_valido("https://exemplo.com/x") is True
    assert news_tab_mod._link_valido("http://exemplo.com/x") is True
    assert news_tab_mod._link_valido("") is False
    assert news_tab_mod._link_valido(None) is False
    assert news_tab_mod._link_valido("/caminho/relativo") is False
    assert news_tab_mod._link_valido("javascript:alert(1)") is False


# --- 7. fechamento / rolagem (CSS) ---------------------------------------------

def test_7a_nenhum_botao_de_fechar_proprio_e_desenhado():
    """O X de fechar é sempre o nativo do st.dialog - nenhum código deste
    projeto pode desenhar um "fechar" próprio que compita/duplique com
    ele (ver ui/news_tab.py:_abrir_card)."""
    capturado, _ = _renderizar(_ITEM_BASE, _RESUMO_SIMPLES, imagem_pronta=None)
    texto = "\n".join(capturado).lower()
    assert "fechar" not in texto and "close" not in texto


def test_7b_dialog_tem_altura_maxima_com_corpo_rolavel_e_cabecalho_fixo():
    """Cabeçalho nativo (stDialogHeader) e corpo (stVerticalBlock) são
    containers DIFERENTES dentro do dialog - limitar a altura do corpo
    (com rolagem própria) nunca esconde o cabeçalho, que fica fora desse
    container. Validação só por CSS (sem navegador real disponível nesta
    sessão - ver limitação registrada na PR)."""
    fonte = open(news_tab_mod.__file__, encoding="utf-8").read()
    bloco_redesign = fonte.split("Redesign editorial do modal NOTÍCIA", 1)[1]
    assert 'div[data-testid="stDialog"] > div {' in bloco_redesign
    bloco_dialog = bloco_redesign.split('div[data-testid="stDialog"] > div {', 1)[1].split("}", 1)[0]
    assert "max-height" in bloco_dialog
    bloco_corpo = bloco_redesign.split('div[data-testid="stDialog"] [data-testid="stVerticalBlock"] {', 1)[1].split("}", 1)[0]
    assert "overflow-y: auto" in bloco_corpo
    bloco_header = bloco_redesign.split('div[data-testid="stDialog"] [data-testid="stDialogHeader"] {', 1)[1].split("}", 1)[0]
    assert "flex: 0 0 auto" in bloco_header  # cabecalho nunca encolhe/rola junto


def test_7c_sem_overflow_horizontal_no_corpo_do_modal():
    fonte = open(news_tab_mod.__file__, encoding="utf-8").read()
    bloco_redesign = fonte.split("Redesign editorial do modal NOTÍCIA", 1)[1]
    bloco_corpo = bloco_redesign.split('div[data-testid="stDialog"] [data-testid="stVerticalBlock"] {', 1)[1].split("}", 1)[0]
    assert "overflow-x: hidden" in bloco_corpo


# --- 8. botão com destaque visual (tema do Pregão) -----------------------------

def test_8_css_do_botao_usa_cor_de_destaque_do_tema_preenchida():
    fonte = open(news_tab_mod.__file__, encoding="utf-8").read()
    bloco = fonte.split('div[data-testid="stDialog"] div[data-testid="stLinkButton"] a {', 1)[1].split("}", 1)[0]
    assert "var(--destaque)" in bloco
    assert "background-color" in bloco  # preenchido, nao so' contornado
