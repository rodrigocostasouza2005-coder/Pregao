# -*- coding: utf-8 -*-
"""Testes da FASE 3 (evolução NEWS + RESEARCH pra feed editorial,
2026-10-08) - cobre so' a parte determinística/sem rede:

- data/news.py: extração de imagem (mesmo download do resumo, nunca uma
  requisição de rede extra) + obter_resumos_prontos (leitura em lote);
- ui/news_tab.py: funções puras do feed unificado (merge cronológico
  NOTICIA+LIVE, teaser de resumo, hora de exibição honesta - nunca
  inventa horário quando não existe).

Groq, Supabase e trafilatura.fetch_url são todos mockados - nenhuma
chamada de rede nem custo de API. Uso: python tests/test_news_fase3.py
(python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod
import ui.news_tab as news_tab_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


# ============================================================
# 1. extração de imagem - MESMO download do resumo, nunca rede extra
# ============================================================

def test_1a_extrai_texto_e_imagem_do_mesmo_download():
    chamadas_fetch = []

    def _fetch(url):
        chamadas_fetch.append(url)
        return "<html>conteudo</html>"

    json_extraido = (
        '{"text": "Texto longo o suficiente pra passar do limite minimo de caracteres exigido pela extracao de artigo usada no projeto.", '
        '"image": "https://veiculo.com/foto.jpg"}'
    )
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia"), \
         patch.object(news_mod.trafilatura, "fetch_url", side_effect=_fetch), \
         patch.object(news_mod.trafilatura, "extract", return_value=json_extraido):
        texto, imagem, link_real, motivo = news_mod._extrair_texto_artigo("https://news.google.com/x")

    _checar("1a texto extraido corretamente", texto and texto.startswith("Texto longo"))
    _checar("1b imagem extraida do MESMO download (zero fetch extra)", imagem == "https://veiculo.com/foto.jpg")
    _checar("1c exatamente 1 download de pagina (texto+imagem juntos)", len(chamadas_fetch) == 1)
    _checar("1d motivo None (sucesso)", motivo is None)
    _checar("1e link_real correto", link_real == "https://veiculo.com/materia")


def test_1b_sem_og_image_no_image_none():
    json_extraido = '{"text": "Outro texto de teste bem longo pra passar do limite minimo exigido pela funcao de extracao de artigo do projeto.", "image": null}'
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia2"), \
         patch.object(news_mod.trafilatura, "fetch_url", return_value="<html></html>"), \
         patch.object(news_mod.trafilatura, "extract", return_value=json_extraido):
        texto, imagem, _, _ = news_mod._extrair_texto_artigo("https://news.google.com/y")
    _checar("1f sem og:image -> imagem=None (nunca inventada)", imagem is None)
    _checar("1g texto ainda extraido normalmente", bool(texto))


def test_1c_imagem_relativa_ou_invalida_e_descartada():
    _checar("1h caminho relativo nunca e' aceito como imagem", news_mod._url_imagem_valida("/img/foto.jpg") is None)
    _checar("1i data: URI nunca e' aceita como imagem", news_mod._url_imagem_valida("data:image/png;base64,abc") is None)
    _checar("1j None passa direto", news_mod._url_imagem_valida(None) is None)
    _checar("1k URL https valida e' aceita", news_mod._url_imagem_valida("https://x.com/a.jpg") == "https://x.com/a.jpg")


def test_1d_json_malformado_do_extract_nao_quebra():
    """trafilatura.extract pode devolver None ou um JSON invalido (ex:
    versao incompativel) - nunca pode derrubar a extracao do texto."""
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia3"), \
         patch.object(news_mod.trafilatura, "fetch_url", return_value="<html></html>"), \
         patch.object(news_mod.trafilatura, "extract", return_value="{nao e json valido"):
        texto, imagem, link_real, motivo = news_mod._extrair_texto_artigo("https://news.google.com/z")
    _checar("1l JSON malformado -> texto None (nunca excecao propagada)", texto is None)
    _checar("1m imagem None junto", imagem is None)
    _checar("1n motivo explica conteudo curto/indisponivel", motivo is not None)


def test_1e_falha_ao_baixar_pagina():
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia4"), \
         patch.object(news_mod.trafilatura, "fetch_url", side_effect=Exception("timeout")):
        texto, imagem, link_real, motivo = news_mod._extrair_texto_artigo("https://news.google.com/w")
    _checar("1o erro ao baixar -> texto None", texto is None)
    _checar("1p imagem None", imagem is None)
    _checar("1q link_real preservado mesmo com falha de download", link_real == "https://veiculo.com/materia4")
    _checar("1r motivo cita o erro de download", "erro ao baixar" in (motivo or ""))


def test_1f_link_nao_resolvido():
    with patch.object(news_mod, "_resolver_link_real", return_value=None):
        texto, imagem, link_real, motivo = news_mod._extrair_texto_artigo("https://news.google.com/v")
    _checar("1s decoder falhou -> texto None, link_real None, imagem None", (texto, imagem, link_real) == (None, None, None))
    _checar("1t motivo explica falha de decode", "resolver o link" in (motivo or ""))


# ============================================================
# 2. obter_resumos_prontos - leitura em LOTE (nunca gera)
# ============================================================

def test_2a_obter_resumos_prontos_mapeia_por_link_do_grupo():
    grupo1 = {"titulo": "Fato A", "link": "https://link-a.com", "fontes": [{"veiculo": "InfoMoney", "link": "https://link-a.com"}]}
    grupo2 = {"titulo": "Fato B", "link": "https://link-b.com", "fontes": [{"veiculo": "Valor", "link": "https://link-b.com"}]}

    chave1 = news_mod.ia_cache.chave_news("Fato A", ("https://link-a.com",))

    with patch.object(news_mod.ia_cache, "obter_varios", return_value={chave1: {"resumo": "resumo A", "imagem": "https://img-a.jpg"}}) as mock_varios:
        resultado = news_mod.obter_resumos_prontos([grupo1, grupo2])

    _checar("2a so' 1 chamada em lote (nunca 1 por grupo)", mock_varios.call_count == 1)
    _checar("2b grupo1 (cacheado) aparece mapeado pelo SEU link", resultado.get("https://link-a.com") == {"resumo": "resumo A", "imagem": "https://img-a.jpg"})
    _checar("2c grupo2 (nao cacheado) nao aparece (nunca inventa resumo)", "https://link-b.com" not in resultado)


def test_2b_lista_vazia_nao_bate_no_cache():
    with patch.object(news_mod.ia_cache, "obter_varios") as mock_varios:
        resultado = news_mod.obter_resumos_prontos([])
    _checar("2d lista vazia -> {} sem chamar obter_varios", resultado == {} and mock_varios.call_count == 0)


# ============================================================
# 3. feed unificado (ui/news_tab.py) - merge cronologico puro
# ============================================================

def test_3a_montar_feed_ordena_cronologicamente():
    noticias = [
        {"data": "2026-10-08T09:18:00-03:00", "titulo": "Petróleo sobe"},
        {"data": "2026-10-08T08:12:00-03:00", "titulo": "Dólar opera"},
        {"data": "2026-10-08T09:42:00-03:00", "titulo": "SmartFit anuncia"},
    ]
    lives = [{"casa": "Genial (Lives)", "autor": "Morning Call", "data": "2026-10-08", "publicado_em": "2026-10-08T11:30:00+00:00", "link": "https://yt/1", "titulo": "Morning Call"}]
    feed = news_tab_mod._montar_feed(noticias, lives)
    ordem = [it["dado"]["titulo"] for it in feed]
    _checar("3a ordem cronologica correta (mais recente primeiro)", ordem == ["SmartFit anuncia", "Petróleo sobe", "Morning Call", "Dólar opera"])
    _checar("3b tipo_feed correto pro item LIVE", feed[2]["tipo_feed"] == "LIVE")
    _checar("3c tipo_feed correto pros itens de noticia", all(it["tipo_feed"] == "NOTICIA" for it in feed if it["dado"]["titulo"] != "Morning Call"))


def test_3b_hora_exibicao_nunca_inventa():
    com_hora = {"publicado_em": "2026-10-08T11:30:00+00:00"}
    sem_hora = {"publicado_em": None, "data": "2026-10-08"}
    _checar("3d publicado_em real -> mostra HH:MM convertido pro fuso de SP", news_tab_mod._hora_exibicao_live(com_hora) == "08:30")
    _checar("3e sem publicado_em -> string vazia (NUNCA um horario inventado)", news_tab_mod._hora_exibicao_live(sem_hora) == "")


def test_3c_chave_ordenacao_cai_pro_meio_dia_so_pra_ordenar():
    sem_hora = {"publicado_em": None, "data": "2026-10-08"}
    chave = news_tab_mod._chave_ordenacao_live(sem_hora)
    _checar("3f sem publicado_em, chave de ordenacao usa a data real (meio-dia, so' interno)", chave.startswith("2026-10-08"))
    _checar("3g hora exibida continua vazia mesmo com chave de ordenacao preenchida", news_tab_mod._hora_exibicao_live(sem_hora) == "")


def test_3d_feed_vazio():
    _checar("3h sem noticias nem lives -> feed vazio, sem erro", news_tab_mod._montar_feed([], []) == [])


# ============================================================
# 4. teaser de resumo (card do feed) - nunca o bloco inteiro
# ============================================================

def test_4a_teaser_news_extrai_so_o_que_aconteceu_e_impacto():
    resumo_completo = (
        "O QUE ACONTECEU: Petrobras anunciou revisão do plano de investimentos.\n"
        "NÚMEROS: não informado\n"
        "IMPACTO: ações podem reagir na abertura.\n"
        "PRÓXIMOS PASSOS: não informado"
    )
    teaser = news_tab_mod._resumo_teaser(resumo_completo, limite=500)
    _checar("4a teaser inclui O QUE ACONTECEU", "Petrobras anunciou" in teaser)
    _checar("4b teaser inclui IMPACTO", "ações podem reagir" in teaser)
    _checar("4c teaser NAO inclui 'não informado'", "não informado" not in teaser)
    _checar("4d teaser nao e' o bloco completo (bem mais curto)", len(teaser) < len(resumo_completo))


def test_4b_teaser_cai_pro_texto_cru_se_formato_nao_bater():
    texto_livre = "Resumo baseado nas manchetes, sem o formato de campos."
    _checar("4e formato nao-estruturado cai pro texto cru truncado", news_tab_mod._resumo_teaser(texto_livre, limite=500) == texto_livre)


def test_4c_teaser_live_remove_titulo_do_bloco_e_tags():
    resumo_live = (
        "O QUE IMPORTA HOJE\n\n"
        "O Copom manteve a Selic em <b>15%</b>, segundo o comunicado oficial.\n\n"
        "DESTAQUES\n\n"
        "<b>PETR4</b>: Genial cita possível revisão de guidance."
    )
    teaser = news_tab_mod._teaser_live(resumo_live, limite=500)
    _checar("4f teaser live pula a linha de titulo em maiusculas", "O QUE IMPORTA HOJE" not in teaser)
    _checar("4g teaser live remove tags <b>", "<b>" not in teaser and "</b>" not in teaser)
    _checar("4h teaser live preserva o conteudo real", "Selic em 15%" in teaser)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DA FASE 3 (FEED EDITORIAL NEWS+RESEARCH) PASSARAM")
