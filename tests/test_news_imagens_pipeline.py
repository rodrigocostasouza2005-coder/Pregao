# -*- coding: utf-8 -*-
"""Fluxo de imagens das notícias ponta a ponta (2026-10-19): extração da
página -> validação/normalização -> associação ao grupo -> registro
próprio de imagem no cache (ia_cache.salvar_registro_imagem) -> política
de reavaliação -> leitura em lote (obter_resumos_prontos) -> HTML da UI.

Causa raiz coberta aqui: a foto só era persistida junto de um resumo de
IA bem-sucedido; sem GROQ_API_KEY no coletor, cota esgotada ou matéria
sem texto extraível, a og:image encontrada era descartada e o card nunca
ganhava foto. Tudo mockado - nenhuma chamada de rede real."""
import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch

import pytest
import requests

import data.ia_cache as ia_cache
import data.news as news
import ui.news_tab as news_tab


# ------------------------------------------------------------------ fakes

class _Resp:
    def __init__(self, status=200, headers=None, url=None):
        self.status_code = status
        self.headers = headers or {}
        self.url = url
        self.fechada = False

    def close(self):
        self.fechada = True


def _img_ok(url="https://cdn.veiculo.com/foto.jpg"):
    return _Resp(200, {"Content-Type": "image/jpeg", "Content-Length": "48000"}, url)


class _PaginaResp:
    """requests.get(...) usado como context manager por _extrair_texto_artigo."""

    def __init__(self, html_txt, url):
        self.text = html_txt
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _grupo(titulo, link, outras=()):
    fontes = [{"veiculo": "Veículo", "link": link}] + [{"veiculo": "Outro", "link": l} for l in outras]
    return {"titulo": titulo, "titulos": [titulo], "link": link, "fontes": fontes}


def _fontes(g):
    return news.ordenar_fontes_para_resumo(g["fontes"])


class _TabelaFake:
    def __init__(self, cli):
        self.cli = cli
        self.op = None

    def upsert(self, payload, on_conflict=None):
        self.op, self.payload = "upsert", payload
        return self

    def execute(self):
        if self.cli.falhar:
            raise RuntimeError("supabase fora do ar")
        if self.op == "upsert":
            self.cli.linhas[self.payload["chave_documento"]] = dict(self.payload)
            self.cli.upserts += 1


class _ClienteFake:
    def __init__(self, falhar=False):
        self.linhas, self.upserts, self.falhar = {}, 0, falhar

    def table(self, _nome):
        return _TabelaFake(self)


def _extrair_com_html(html_txt, url_materia="https://www.veiculo.com.br/mercado/vale-cobre"):
    with patch.object(news, "_resolver_link_real", return_value=url_materia), \
         patch.object(news.requests, "get", return_value=_PaginaResp(html_txt, url_materia)):
        return news._extrair_texto_artigo("https://news.google.com/rss/articles/x")


_TEXTO = "<p>" + ("A Vale anunciou expansão da produção de cobre no Pará, segundo a companhia. " * 4) + "</p>"


# ------------------------------------------- 1. imagem válida e confirmada

def test_01_imagem_valida_da_pagina_e_confirmada():
    html_txt = (
        "<html><head><meta property='og:image' content='https://s2.glbimg.com/vale-carajas-1200.jpg'>"
        "<meta property='og:image:width' content='1200'></head>"
        f"<body><article>{_TEXTO}</article></body></html>"
    )
    _t, imagem, link_real, _m = _extrair_com_html(html_txt)
    assert imagem == "https://s2.glbimg.com/vale-carajas-1200.jpg"

    g = _grupo("Vale amplia produção de cobre no Pará", "https://news.google.com/a")
    with patch.object(news, "_extrair_texto_artigo", return_value=("texto", imagem, link_real, None)), \
         patch.object(news.requests, "head", return_value=_img_ok(imagem)):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] == imagem
    assert reg["imagem_status"] == news.STATUS_IMAGEM_CONFIRMADA
    assert reg["imagem_fonte"] == "veiculo.com.br"
    assert reg["imagem_tentativas"] == 1


# ------------------------------------------------- 2. notícia sem imagem

def test_02_pagina_sem_imagem_vira_ausente_e_card_sem_foto():
    _t, imagem, link_real, _m = _extrair_com_html(f"<html><body><article>{_TEXTO}</article></body></html>")
    assert imagem is None
    g = _grupo("Copom mantém Selic", "https://news.google.com/b")
    with patch.object(news, "_extrair_texto_artigo", return_value=("texto", None, link_real, None)):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] is None and reg["imagem_status"] == news.STATUS_IMAGEM_AUSENTE

    chave = news._chave_grupo(g)
    with patch.object(news.ia_cache, "obter_varios", return_value={ia_cache.chave_imagem_news(chave): reg}):
        prontos = news.obter_resumos_prontos([g])
    assert prontos[g["link"]]["imagem"] is None
    assert prontos[g["link"]]["resumo"] is None
    assert prontos[g["link"]]["imagem_status"] == news.STATUS_IMAGEM_AUSENTE


# ------------------------------------------------- 3. URL quebrada

def test_03_url_quebrada_404_e_rejeitada_e_lembrada():
    g = _grupo("Petrobras anuncia dividendos", "https://news.google.com/c")
    with patch.object(news, "_extrair_texto_artigo",
                      return_value=("t", "https://cdn.x.com/sumiu.jpg", "https://x.com/m", None)), \
         patch.object(news.requests, "head", return_value=_Resp(404, {"Content-Type": "text/html"})), \
         patch.object(news.requests, "get", return_value=_Resp(404, {"Content-Type": "text/html"})):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] is None and reg["imagem_status"] == news.STATUS_IMAGEM_INVALIDA
    assert reg["imagens_rejeitadas"] == ["https://cdn.x.com/sumiu.jpg"]
    # reavaliação reprovou a URL que um resumo antigo trazia -> não exibe
    resumo_antigo = {"resumo": "R", "imagem": "https://cdn.x.com/sumiu.jpg", "imagem_status": "nao_verificada"}
    assert news._imagem_do_resultado(resumo_antigo, reg) == (None, news.STATUS_IMAGEM_INVALIDA)


# ------------------------------------------------- 4. timeout / erro HTTP

def test_04_timeout_e_5xx_sao_temporarios_404_e_permanente():
    with patch.object(news.requests, "head", side_effect=requests.Timeout("lento")):
        assert news._verificar_imagem_url("https://cdn.x.com/a.jpg") == news.IMAGEM_ERRO_TEMPORARIO
    with patch.object(news.requests, "head", return_value=_Resp(503, {})), \
         patch.object(news.requests, "get", return_value=_Resp(503, {})):
        assert news._verificar_imagem_url("https://cdn.x.com/a.jpg") == news.IMAGEM_ERRO_TEMPORARIO
    with patch.object(news.requests, "head", return_value=_Resp(429, {"Content-Type": "text/plain"})), \
         patch.object(news.requests, "get", return_value=_Resp(429, {})):
        assert news._verificar_imagem_url("https://cdn.x.com/a.jpg") == news.IMAGEM_ERRO_TEMPORARIO
    with patch.object(news.requests, "head", return_value=_Resp(410, {})), \
         patch.object(news.requests, "get", return_value=_Resp(410, {})):
        assert news._verificar_imagem_url("https://cdn.x.com/a.jpg") == news.IMAGEM_INVALIDA


def test_04b_timeout_na_validacao_nao_apaga_a_foto_do_resumo():
    texto = "Texto longo o suficiente extraído da matéria real, com conteúdo jornalístico de verdade."
    with patch.object(news, "_extrair_texto_artigo",
                      return_value=(texto, "https://cdn.v.com/foto.jpg", "https://v.com/m", None)), \
         patch.object(news, "_chamar_groq",
                      return_value=("RESUMO:\nA empresa Gama reportou receita de R$ 3 bilhões no trimestre.", None)), \
         patch.object(news.requests, "head", side_effect=requests.ConnectionError("reset")):
        r = news._gerar_resumo_grupo("Gama reporta receita", (("F", "https://news.google.com/g"),),
                                     ("Gama reporta receita",), validar_imagem=True)
    assert r["resumo"]
    assert r["imagem"] == "https://cdn.v.com/foto.jpg"
    assert r["imagem_status"] == news.STATUS_IMAGEM_NAO_VERIFICADA


def test_04c_pagina_inacessivel_vira_erro_temporario():
    g = _grupo("Ibovespa sobe", "https://news.google.com/d")
    with patch.object(news, "_extrair_texto_artigo",
                      return_value=(None, None, "https://x.com/m", "falha HTTP ao acessar a matéria (Timeout)")):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem_status"] == news.STATUS_IMAGEM_ERRO_TEMPORARIO


# ------------------------------------------------- 5. redirecionamento

def test_05_redirecionamento_para_placeholder_e_rejeitado_para_foto_e_aceito():
    url = "https://cdn.x.com/2026/10/foto-expirada.jpg"
    for_placeholder = _Resp(200, {"Content-Type": "image/png", "Content-Length": "9000"},
                            "https://cdn.x.com/static/placeholder.png")
    with patch.object(news.requests, "head", return_value=for_placeholder):
        assert news._verificar_imagem_url(url) == news.IMAGEM_INVALIDA
    for_foto = _Resp(200, {"Content-Type": "image/webp", "Content-Length": "90000"},
                     "https://img.cdn.x.com/2026/10/foto-expirada.webp")
    with patch.object(news.requests, "head", return_value=for_foto):
        assert news._verificar_imagem_url(url) == news.IMAGEM_OK


def test_05b_get_de_fallback_e_sempre_fechado():
    resp_get = _Resp(200, {"Content-Type": "image/jpeg", "Content-Length": "50000"})
    with patch.object(news.requests, "head", return_value=_Resp(405, {})), \
         patch.object(news.requests, "get", return_value=resp_get):
        assert news._verificar_imagem_url("https://cdn.x.com/a.jpg") == news.IMAGEM_OK
    assert resp_get.fechada


# ------------------------------------------------- 6. metadados ausentes/inválidos

def test_06_metadados_invalidos_nao_quebram_nem_viram_foto():
    url_materia = "https://www.veiculo.com.br/mercado/vale-cobre"
    html_txt = (
        "<html><head>"
        f"<meta property='og:image' content='{url_materia}'>"  # aponta pra própria página
        "<meta property='og:image:width' content='abc'>"
        "<meta name='twitter:image' content='data:image/gif;base64,R0lGOD'>"
        "<script type='application/ld+json'>{isto não é json</script>"
        f"</head><body><article>{_TEXTO}</article></body></html>"
    )
    texto, imagem, _l, _m = _extrair_com_html(html_txt, url_materia)
    assert texto  # notícia continua aproveitável
    assert imagem is None
    assert news._url_imagem_valida("/relativa.jpg") is None
    assert news._url_imagem_valida(None) is None
    assert news._verificar_imagem_url(None) == news.IMAGEM_INVALIDA


def test_06b_registro_com_data_corrompida_e_reavaliado():
    reg = {"imagem_status": news.STATUS_IMAGEM_AUSENTE, "imagem_verificada_em": "ontem", "imagem_tentativas": 1}
    assert news._imagem_precisa_reavaliar(None, reg) is True


# ------------------------------------------------- 7. imagem genérica

@pytest.mark.parametrize("url", [
    "https://www.veiculo.com.br/og-image.png",
    "https://www.veiculo.com.br/static/share.jpg",
    "https://www.veiculo.com.br/img/marca.svg",
    "https://cdn.veiculo.com.br/logo-veiculo.png",
    "https://cdn.veiculo.com.br/2026/10/pexels-photo-34021878.webp",
    "https://s.tradingview.com/static/images/illustrations/news-story.jpg",
])
def test_07_imagem_generica_nunca_e_editorial(url):
    assert news._imagem_parece_generica(url)


def test_07b_foto_real_com_palavra_parecida_continua_aceita():
    assert not news._imagem_parece_generica("https://s2.glbimg.com/share-de-mercado-da-vale-2026.jpg")
    assert not news._imagem_parece_generica("https://cdn.veiculo.com.br/2026/10/vale-carajas.jpg")


def test_07c_svg_respondido_como_imagem_e_rejeitado():
    with patch.object(news.requests, "head",
                      return_value=_Resp(200, {"Content-Type": "image/svg+xml", "Content-Length": "5000"})):
        assert news._verificar_imagem_url("https://cdn.x.com/grafico") == news.IMAGEM_INVALIDA


def test_07d_cache_legado_com_foto_de_banco_some_na_leitura():
    """Linha cacheada ANTES do filtro de banco de imagens existir deixa
    de ser exibida sem precisar de backfill no banco."""
    g = _grupo("Níquel no Canadá", "https://news.google.com/e")
    legado = {"resumo": "RESUMO:\nx", "imagem": "https://spacemoney.com.br/wp/pexels-photo-1.webp"}
    with patch.object(news.ia_cache, "obter_varios", return_value={news._chave_grupo(g): legado}):
        prontos = news.obter_resumos_prontos([g])
    assert prontos[g["link"]]["resumo"] == "RESUMO:\nx"
    assert prontos[g["link"]]["imagem"] is None


# ------------------------------------------------- 8. imagem que não corresponde

def test_08_mesma_foto_em_materias_diferentes_e_descartada():
    g1 = _grupo("Dólar fecha em alta de 0,8% com exterior", "https://news.google.com/f1")
    g2 = _grupo("Ibovespa fecha em queda puxado por Petrobras", "https://news.google.com/f2")
    g3 = _grupo("Vale amplia produção de cobre", "https://news.google.com/f3")
    foto_padrao = "https://conteudo.imguol.com.br/c/noticias/fechamento-mercado.jpg?w=1200"
    linhas = {
        news._chave_grupo(g1): {"resumo": "a", "imagem": foto_padrao},
        news._chave_grupo(g2): {"resumo": "b", "imagem": foto_padrao.replace("w=1200", "w=600")},
        news._chave_grupo(g3): {"resumo": "c", "imagem": "https://s2.glbimg.com/vale.jpg"},
    }
    with patch.object(news.ia_cache, "obter_varios", return_value=linhas):
        prontos = news.obter_resumos_prontos([g1, g2, g3])
    assert prontos[g1["link"]]["imagem"] is None
    assert prontos[g2["link"]]["imagem"] is None
    assert prontos[g1["link"]]["imagem_status"] == news.STATUS_IMAGEM_REPETIDA
    assert prontos[g3["link"]]["imagem"] == "https://s2.glbimg.com/vale.jpg"


def test_08b_mesma_foto_no_mesmo_fato_duplicado_continua():
    ids = news._descartar_imagens_repetidas([
        ("a", "Vale anuncia expansão de cobre no Pará", "https://x.com/vale.jpg"),
        ("b", "Vale anuncia expansão de cobre no Pará, diz empresa", "https://x.com/vale.jpg"),
    ])
    assert ids == set()


def test_08c_foto_da_materia_da_manchete_tem_prioridade():
    g = _grupo("Vale amplia cobre", "https://news.google.com/manchete", outras=("https://news.google.com/outra",))
    ordem = [link for _, link in news._fontes_para_imagem(g, (("Outro", "https://news.google.com/outra"),
                                                             ("Veículo", "https://news.google.com/manchete")))]
    assert ordem[0] == "https://news.google.com/manchete"


def test_08c2_terceira_fonte_e_tentada_quando_as_2_primeiras_nao_tem_foto():
    """Achado real (auditoria 2026-10-19, rede real): um grupo cujas 2
    fontes mais prioritárias calham de ser as mesmas bloqueadas sempre
    (ex: Reuters/FT) nunca chegava a tentar uma 3ª fonte do MESMO fato
    que podia ter imagem acessível - _MAX_FONTES_IMAGEM subiu de 2 pra
    3 por causa disso. Confirma que a 3ª fonte É tentada e seu resultado
    é usado."""
    g = _grupo("Fed sinaliza cautela com juros", "https://news.google.com/f1",
               outras=("https://news.google.com/f2", "https://news.google.com/f3"))
    respostas = {
        "https://news.google.com/f1": ("texto", None, "https://reuters.com/x", None),
        "https://news.google.com/f2": ("texto", None, "https://ft.com/x", None),
        "https://news.google.com/f3": ("texto", "https://cdn.terceira.com/fed.jpg", "https://terceira.com/x", None),
    }
    with patch.object(news, "_extrair_texto_artigo", side_effect=lambda link: respostas[link]), \
         patch.object(news.requests, "head", return_value=_img_ok("https://cdn.terceira.com/fed.jpg")):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] == "https://cdn.terceira.com/fed.jpg"
    assert reg["imagem_status"] == news.STATUS_IMAGEM_CONFIRMADA


def test_08c3_quarta_fonte_nao_e_tentada_limite_continua_existindo():
    """O aumento de 2 pra 3 não virou 'tenta todas' - ainda tem um teto
    (orçamento de rede por grupo, ver _ORCAMENTO_PREGERAR_IMAGENS_S)."""
    g = _grupo("Fed sinaliza cautela com juros", "https://news.google.com/g1",
               outras=("https://news.google.com/g2", "https://news.google.com/g3", "https://news.google.com/g4"))

    def _nunca_deveria_chegar_na_4a(link):
        if link == "https://news.google.com/g4":
            raise AssertionError("4ª fonte não deveria ser tentada - _MAX_FONTES_IMAGEM=3")
        return ("texto", None, link, None)

    with patch.object(news, "_extrair_texto_artigo", side_effect=_nunca_deveria_chegar_na_4a):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] is None


def test_08d_foto_de_relacionados_dentro_do_article_nao_e_roubada():
    html_txt = (
        f"<html><body><article>{_TEXTO}"
        "<article class='relacionada'><img src='https://cdn.x.com/outra-materia.jpg' width='800'></article>"
        "</article></body></html>"
    )
    _t, imagem, _l, _m = _extrair_com_html(html_txt)
    assert imagem is None


# ------------------------------------------------- 9. cache e expiração

def test_09_politica_de_reavaliacao():
    agora = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)

    def reg(status, horas, tentativas=1):
        return {"imagem_status": status, "imagem_tentativas": tentativas,
                "imagem_verificada_em": (agora - timedelta(hours=horas)).isoformat()}

    assert news._imagem_precisa_reavaliar(None, None, agora)  # nunca avaliado
    assert not news._imagem_precisa_reavaliar(None, reg("confirmada", 500), agora)
    assert not news._imagem_precisa_reavaliar(None, reg("erro_temporario", 1), agora)
    assert news._imagem_precisa_reavaliar(None, reg("erro_temporario", 3), agora)
    assert not news._imagem_precisa_reavaliar(None, reg("ausente", 10), agora)
    assert news._imagem_precisa_reavaliar(None, reg("ausente", 30), agora)
    assert not news._imagem_precisa_reavaliar(None, reg("ausente", 30, tentativas=news._MAX_TENTATIVAS_IMAGEM), agora)
    # resumo com foto (legado ou confirmada) não gasta rede de novo
    assert not news._imagem_precisa_reavaliar({"resumo": "x", "imagem": "https://x.com/f.jpg"}, None, agora)
    assert news._imagem_precisa_reavaliar(
        {"resumo": "x", "imagem": "https://x.com/f.jpg", "imagem_status": "nao_verificada"}, None, agora)


def _pregerar_imagens(grupos, linhas_cache, avaliar):
    salvos = {}

    def _salvar(chave_img, link, registro):
        salvos[chave_img] = registro
        return True

    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news, "obter_top_mercado_tudo", return_value=grupos), \
         patch.object(news, "obter_top_mercado", return_value=[]), \
         patch.object(news, "obter_top_mercado_internacional", return_value=[]), \
         patch.object(news.ia_cache, "obter_varios", return_value=linhas_cache), \
         patch.object(news.ia_cache, "salvar_registro_imagem", side_effect=_salvar), \
         patch.object(news, "avaliar_imagem_grupo", side_effect=avaliar) as mock_avaliar:
        stats = news.pregerar_imagens_news([])
    return stats, salvos, mock_avaliar


def test_09b_pregerar_imagens_so_avalia_quem_precisa_e_sem_groq():
    com_foto = _grupo("Fato com foto", "https://news.google.com/1")
    sem_foto = _grupo("Fato sem foto ainda", "https://news.google.com/2")
    linhas = {news._chave_grupo(com_foto): {"resumo": "r", "imagem": "https://x.com/a.jpg"}}

    def avaliar(g, fontes, tentativas=0):
        return {"tipo": "imagem", "imagem": "https://x.com/b.jpg", "imagem_status": "confirmada",
                "imagem_fonte": "x.com", "imagem_verificada_em": news._agora_iso_utc(),
                "imagem_tentativas": tentativas + 1, "imagens_rejeitadas": []}

    with patch.object(news.config, "obter_credenciais_groq", side_effect=AssertionError("não usa IA")):
        stats, salvos, mock_avaliar = _pregerar_imagens([com_foto, sem_foto], linhas, avaliar)
    assert mock_avaliar.call_count == 1
    assert stats["ja_com_imagem"] == 1 and stats["avaliados"] == 1 and stats["salvos"] == 1
    assert list(salvos.values())[0]["imagem"] == "https://x.com/b.jpg"


def test_09c_pregerar_imagens_respeita_limite_por_execucao():
    grupos = [_grupo(f"Fato número {i} distinto", f"https://news.google.com/n{i}")
              for i in range(news._MAX_IMAGENS_POR_EXECUCAO + 5)]
    stats, _s, mock_avaliar = _pregerar_imagens(
        grupos, {}, lambda g, f, tentativas=0: {"imagem": None, "imagem_status": "ausente"})
    assert mock_avaliar.call_count == news._MAX_IMAGENS_POR_EXECUCAO
    assert stats["tempo_esgotado"] is True


def test_09d_pregerar_imagens_marca_foto_repetida_de_outra_materia():
    a = _grupo("Dólar fecha em alta com exterior", "https://news.google.com/r1")
    b = _grupo("Ibovespa cai puxado por Petrobras", "https://news.google.com/r2")
    linhas = {news._chave_grupo(a): {"resumo": "r", "imagem": "https://imguol.com/fechamento.jpg"}}
    stats, salvos, _m = _pregerar_imagens(
        [a, b], linhas,
        lambda g, f, tentativas=0: {"imagem": "https://imguol.com/fechamento.jpg", "imagem_status": "confirmada",
                                    "imagens_rejeitadas": []})
    reg = list(salvos.values())[0]
    assert reg["imagem"] is None and reg["imagem_status"] == news.STATUS_IMAGEM_REPETIDA
    assert stats["por_status"] == {news.STATUS_IMAGEM_REPETIDA: 1}


# ------------------------------------------------- 10. falha sem perder a notícia

def test_10_falha_de_imagem_nao_derruba_coleta_nem_noticia():
    a = _grupo("Fato que quebra", "https://news.google.com/q1")
    b = _grupo("Fato que funciona normalmente", "https://news.google.com/q2")

    def avaliar(g, f, tentativas=0):
        if g is a:
            raise RuntimeError("parser explodiu")
        return {"imagem": None, "imagem_status": "ausente"}

    stats, salvos, _m = _pregerar_imagens([a, b], {}, avaliar)
    assert stats["falhas"] == 1 and len(salvos) == 1

    # cache indisponível: feed segue (sem foto), nunca exceção
    with patch.object(news.ia_cache, "obter_varios", return_value={}):
        assert news.obter_resumos_prontos([a, b]) == {}
    assert news.imagem_pronta_do_grupo({"titulo": "x"}) is None  # grupo malformado -> None

    # extração lançando exceção dentro da avaliação -> registro, nunca exceção
    with patch.object(news, "_extrair_texto_artigo", side_effect=RuntimeError("boom")):
        reg = news.avaliar_imagem_grupo(a, _fontes(a))
    assert reg["imagem"] is None and reg["imagem_status"] == news.STATUS_IMAGEM_ERRO_TEMPORARIO


def test_10b_supabase_fora_na_gravacao_retorna_false():
    with patch.object(ia_cache, "obter_cliente", return_value=_ClienteFake(falhar=True)):
        assert ia_cache.salvar_registro_imagem("k", "https://l", {"imagem": None}) is False
    with patch.object(ia_cache, "obter_cliente", return_value=None):
        assert ia_cache.salvar_registro_imagem("k", "https://l", {"imagem": None}) is False


def test_10c_resumo_falhou_mas_foto_achada_vai_pro_registro_de_imagem():
    """O caso da causa raiz: sem chave/cota do Groq o resumo volta None -
    a foto encontrada na página não pode se perder junto."""
    with patch.object(news, "_extrair_texto_artigo",
                      return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo de verdade.",
                                    "https://cdn.v.com/foto.jpg", "https://v.com/m", None)), \
         patch.object(news, "_chamar_groq", return_value=(None, "cota")):
        r = news._gerar_resumo_grupo("Gama reporta receita", (("F", "https://news.google.com/g"),), ("Gama",))
    assert r["resumo"] is None and r["imagem"] is None
    assert r["imagem_candidata"] == {"imagem": "https://cdn.v.com/foto.jpg", "fonte": "https://v.com/m"}

    g = _grupo("Gama reporta receita", "https://news.google.com/g")
    gravados = []
    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news.config, "obter_credenciais_groq", return_value=("chave-de-teste", "m")), \
         patch.object(news, "obter_top_mercado_tudo", return_value=[g]), \
         patch.object(news, "obter_top_mercado", return_value=[]), \
         patch.object(news, "obter_top_mercado_internacional", return_value=[]), \
         patch.object(news.ia_cache, "obter_varios", return_value={}), \
         patch.object(news, "obter_resumo_grupo", return_value=r), \
         patch.object(news.requests, "head", return_value=_img_ok()), \
         patch.object(news.ia_cache, "salvar_registro_imagem",
                      side_effect=lambda c, l, reg: gravados.append(reg) or True):
        stats = news.pregerar_resumos_news([])
    assert stats["indisponiveis"] == 1
    assert gravados and gravados[0]["imagem_status"] == news.STATUS_IMAGEM_CONFIRMADA


# ------------------------------------------------- 11. duplicação / idempotência

def test_11_gravacao_idempotente_e_dedup_de_grupos():
    cli = _ClienteFake()
    reg = {"imagem": "https://x.com/a.jpg", "imagem_status": "confirmada"}
    with patch.object(ia_cache, "obter_cliente", return_value=cli):
        assert ia_cache.salvar_registro_imagem("chave-img", "https://l", reg)
        assert ia_cache.salvar_registro_imagem("chave-img", "https://l", reg)
    assert len(cli.linhas) == 1 and cli.upserts == 2
    linha = cli.linhas["chave-img"]
    assert linha["origem"] == ia_cache.ORIGEM_IMAGEM_NEWS and linha["status"] == "concluido"

    # chave de imagem nunca colide com a do resumo do mesmo grupo
    chave = ia_cache.chave_news("t", ("https://l",))
    assert ia_cache.chave_imagem_news(chave) != chave
    assert ia_cache.chave_imagem_news(chave) == ia_cache.chave_imagem_news(chave)

    # o mesmo grupo vindo de 2 pools é avaliado uma vez só
    g = _grupo("Fato repetido nos pools", "https://news.google.com/dup")
    with patch.object(news.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news, "obter_top_mercado_tudo", return_value=[g]), \
         patch.object(news, "obter_top_mercado", return_value=[dict(g)]), \
         patch.object(news, "obter_top_mercado_internacional", return_value=[]), \
         patch.object(news.ia_cache, "obter_varios", return_value={}), \
         patch.object(news.ia_cache, "salvar_registro_imagem", return_value=True), \
         patch.object(news, "avaliar_imagem_grupo",
                      return_value={"imagem": None, "imagem_status": "ausente"}) as mock_avaliar:
        stats = news.pregerar_imagens_news([])
    assert stats["grupos_considerados"] == 1 and mock_avaliar.call_count == 1


def test_11b_foto_do_registro_aparece_sem_resumo_e_confirmada_tem_prioridade():
    g = _grupo("Fato só com foto", "https://news.google.com/s")
    chave = news._chave_grupo(g)
    reg = {"imagem": "https://x.com/confirmada.jpg", "imagem_status": "confirmada"}
    resumo = {"resumo": "r", "imagem": "https://x.com/antiga.jpg", "imagem_status": "nao_verificada"}
    with patch.object(news.ia_cache, "obter_varios", return_value={ia_cache.chave_imagem_news(chave): reg}) as m:
        prontos = news.obter_resumos_prontos([g])
    assert m.call_count == 1  # resumo + imagem na MESMA query em lote
    assert prontos[g["link"]] == {"resumo": None, "imagem": "https://x.com/confirmada.jpg",
                                  "imagem_status": "confirmada"}
    with patch.object(news.ia_cache, "obter_varios",
                      return_value={chave: resumo, ia_cache.chave_imagem_news(chave): reg}):
        prontos = news.obter_resumos_prontos([g])
    assert prontos[g["link"]]["imagem"] == "https://x.com/confirmada.jpg"
    assert prontos[g["link"]]["resumo"] == "r"


# ------------------------------------------------- 12. renderização e fallback

def _png_bytes(largura, altura):
    from PIL import Image
    saida = BytesIO()
    Image.new("RGB", (largura, altura), (40, 90, 160)).save(saida, format="PNG")
    return saida.getvalue()


def test_12_thumbs_com_e_sem_foto():
    com = news_tab._thumb_wire_html("https://x.com/a.jpg?x=1&y=2")
    assert "<img" in com and "referrerpolicy='no-referrer'" in com and "&amp;y=2" in com
    assert "w-thumb-fallback" in com and "display:none" in com
    sem = news_tab._thumb_wire_html(None)
    assert "<img" not in sem and "w-thumb-fallback" in sem
    assert "<img" not in news_tab._thumb_html(None, "InfoMoney")
    assert ".w-thumb" in news_tab._SCRIPT_FALLBACK_IMAGEM  # listener cobre a thumb wire


def test_12b_capa_do_modal_reduz_e_devolve_a_proporcao_real():
    """_capa_data_uri devolve (data_uri, largura/altura) - a proporção real
    decide, em _renderizar_capa, o modo cobrir/conter (ver _RATIO_MIN/MAX_
    COBRIR). Retrato (1800x2400, proporção 0,75) fica MUITO fora da faixa
    de "cobrir" - recortar isso nas laterais é exatamente o bug real
    auditado em 2026-10-22 ("imagem cortada, perdendo parte importante da
    foto"); o modal agora preserva a foto inteira (contido) nesse caso."""
    news_tab._capa_data_uri.clear()
    with patch.object(news_tab, "_baixar_imagem_capa", return_value=_png_bytes(1800, 2400)):
        resultado = news_tab._capa_data_uri("https://x.com/retrato.jpg")
    uri, proporcao = resultado
    assert uri.startswith("data:image/jpeg;base64,")
    assert proporcao == pytest.approx(1800 / 2400)
    from PIL import Image
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as img:
        assert img.width == news_tab._LARGURA_MAX_CAPA

    saidas = []
    with patch.object(news_tab, "_capa_data_uri", return_value=(uri, proporcao)), \
         patch.object(news_tab.st, "markdown", side_effect=lambda h, **k: saidas.append(h)), \
         patch.object(news_tab.st, "image", side_effect=AssertionError("st.image solto não respeita o recorte")):
        news_tab._renderizar_capa("https://x.com/retrato.jpg", "Valor")
    assert "news-capa--conter" in saidas[0] and uri in saidas[0]
    assert "news-capa-fundo" in saidas[0]  # fundo desfocado, nunca barra vazia lisa
    assert "object-fit" not in saidas[0]  # decidido só via classe CSS, não inline


def test_12b2_capa_paisagem_tipica_continua_em_cobrir():
    """Proporção típica de og:image editorial (1200x630 ≈ 1,9) fica dentro
    da faixa de "cobrir" - continua preenchendo a caixa, sem letterbox
    desnecessário (nem toda foto precisa de 'conter')."""
    news_tab._capa_data_uri.clear()
    with patch.object(news_tab, "_baixar_imagem_capa", return_value=_png_bytes(1200, 630)):
        uri, proporcao = news_tab._capa_data_uri("https://x.com/paisagem.jpg")
    assert proporcao == pytest.approx(1200 / 630)

    saidas = []
    with patch.object(news_tab, "_capa_data_uri", return_value=(uri, proporcao)), \
         patch.object(news_tab.st, "markdown", side_effect=lambda h, **k: saidas.append(h)):
        news_tab._renderizar_capa("https://x.com/paisagem.jpg", "Valor")
    assert "news-capa--cobrir" in saidas[0] and "news-capa-fundo" not in saidas[0]


def test_12b3_capa_panoramica_tambem_vira_conter():
    """Panorâmica muito larga (1600x400 = 4,0) cortaria as laterais em
    cobrir - mesmo tratamento do retrato, na outra direção."""
    news_tab._capa_data_uri.clear()
    with patch.object(news_tab, "_baixar_imagem_capa", return_value=_png_bytes(1600, 400)):
        uri, proporcao = news_tab._capa_data_uri("https://x.com/panoramica.jpg")
    assert proporcao == pytest.approx(4.0)

    saidas = []
    with patch.object(news_tab, "_capa_data_uri", return_value=(uri, proporcao)), \
         patch.object(news_tab.st, "markdown", side_effect=lambda h, **k: saidas.append(h)):
        news_tab._renderizar_capa("https://x.com/panoramica.jpg", "Valor")
    assert "news-capa--conter" in saidas[0] and "news-capa-fundo" in saidas[0]


def test_12c_capa_falha_no_servidor_vira_img_com_fallback_e_sem_foto_vira_marca():
    saidas = []
    with patch.object(news_tab, "_capa_data_uri", return_value=None), \
         patch.object(news_tab.st, "markdown", side_effect=lambda h, **k: saidas.append(h)):
        news_tab._renderizar_capa("https://x.com/bloqueada.jpg", "Valor")
        news_tab._renderizar_capa(None, "Valor")
    assert "src='https://x.com/bloqueada.jpg'" in saidas[0] and "news-capa-fallback" in saidas[0]
    assert "<img" not in saidas[1] and "VALOR" in saidas[1].upper()


def test_12d_regressoes_da_validacao_visual():
    fonte = open(news_tab.__file__, encoding="utf-8").read()
    # capa COM foto também carrega o fallback oculto - a regra de "capa sem
    # foto" (64px no celular) não pode casar com ela
    assert ".news-capa:has(.news-capa-fallback)" not in fonte
    assert ".news-capa:not(:has(img))" in fonte
    # imagem que falhou antes do listener existir também cai no fallback
    script = news_tab._SCRIPT_FALLBACK_IMAGEM
    assert "naturalWidth === 0" in script and "setInterval" in script
    # miniatura wire some no celular (colunas empilhadas)
    assert 'div[data-testid="stColumn"]:has(.w-thumb) { display: none !important; }' in fonte


def test_12e_modal_aplica_filtros_de_leitura_e_usa_registro():
    g = _grupo("Níquel no Canadá", "https://news.google.com/m")
    chave = news._chave_grupo(g)
    reg = {"imagem": "https://x.com/niquel.jpg", "imagem_status": "confirmada"}
    gerado_agora = {"resumo": "r", "imagem": "https://spacemoney.com.br/pexels-photo-9.webp"}
    with patch.object(news.ia_cache, "obter_varios", return_value={ia_cache.chave_imagem_news(chave): reg}):
        assert news.imagem_pronta_do_grupo(g, gerado_agora) == "https://x.com/niquel.jpg"
    with patch.object(news.ia_cache, "obter_varios", return_value={}):
        assert news.imagem_pronta_do_grupo(g, gerado_agora) is None  # banco de imagens nunca no modal
        assert news.imagem_pronta_do_grupo(g, {"resumo": "r", "imagem": "https://x.com/f.jpg"}) == "https://x.com/f.jpg"
    with patch.object(news.ia_cache, "obter_varios", side_effect=RuntimeError("fora")):
        assert news.imagem_pronta_do_grupo(g, gerado_agora) is None


def test_12f_leitura_em_lote_divide_chaves_grandes():
    class _Q:
        def __init__(self, cli):
            self.cli = cli

        def select(self, *_a):
            return self

        def in_(self, _c, valores):
            self.cli.lotes.append(list(valores))
            self.vals = valores
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            class R:
                pass
            r = R()
            r.data = [{"chave_documento": v, "resultado": {"resumo": v}, "status": "concluido"} for v in self.vals]
            return r

    class _C:
        lotes = []

        def table(self, _n):
            return _Q(self)

    cli = _C()
    chaves = [f"k{i}" for i in range(250)]
    with patch.object(ia_cache, "obter_cliente", return_value=cli):
        achados = ia_cache.obter_varios(chaves + chaves[:10])
    assert len(achados) == 250
    assert [len(l) for l in cli.lotes] == [100, 100, 50]


def test_12g_lista_wire_nao_consulta_o_banco_a_cada_rerun():
    news_tab._prontos_para_lista.clear()
    itens = [_grupo("Fato da visão geral", "https://news.google.com/vg")]
    with patch.object(news_tab, "obter_resumos_prontos", return_value={"x": {}}) as m:
        news_tab._prontos_para_lista(itens)
        news_tab._prontos_para_lista(itens)
    assert m.call_count == 1
    news_tab._prontos_para_lista.clear()
    with patch.object(news_tab, "obter_resumos_prontos", side_effect=RuntimeError("supabase fora")):
        assert news_tab._prontos_para_lista(itens) == {}


# ------------------- revisão de correspondência (2026-10-19, 2ª rodada)

def test_13a_formato_diario_recorrente_com_mesma_foto_e_descartado():
    """Bug achado na revisão: 'Ibovespa fecha em alta hoje' x 'Ibovespa
    fecha em queda hoje' (dias diferentes) tinham sobreposição 0,75 e
    passavam como o MESMO fato - a og:image reciclada era aceita."""
    foto = "https://conteudo.imguol.com.br/c/noticias/fechamento.jpg"
    ids = news._descartar_imagens_repetidas([
        ("seg", "Ibovespa fecha em alta hoje; dólar cai", foto, "2026-10-19T17:30:00-03:00"),
        ("ter", "Ibovespa fecha em queda hoje; dólar sobe", foto, "2026-10-20T17:30:00-03:00"),
    ])
    assert ids == {"seg", "ter"}
    # mesmo dia, direção oposta, títulos quase iguais -> fatos diferentes
    ids = news._descartar_imagens_repetidas([
        ("a", "Petrobras sobe 3% na abertura", foto, "2026-10-19T10:05:00-03:00"),
        ("b", "Petrobras cai 3% na abertura", foto, "2026-10-19T10:40:00-03:00"),
    ])
    assert ids == {"a", "b"}
    # mesmo fato em 2 veículos, horas próximas -> foto mantida
    ids = news._descartar_imagens_repetidas([
        ("x", "Vale anuncia expansão de cobre no Pará", foto, "2026-10-19T09:00:00-03:00"),
        ("y", "Vale anuncia expansão de cobre no Pará, diz empresa", foto, "2026-10-19T11:00:00-03:00"),
    ])
    assert ids == set()


def test_13b_obter_resumos_prontos_usa_a_data_do_grupo():
    foto = "https://conteudo.imguol.com.br/fechamento.jpg"
    g1 = dict(_grupo("Ibovespa fecha em alta hoje", "https://news.google.com/d1"), data="2026-10-19T17:30:00-03:00")
    g2 = dict(_grupo("Ibovespa fecha em alta hoje", "https://news.google.com/d2"), data="2026-10-20T17:30:00-03:00")
    linhas = {news._chave_grupo(g1): {"resumo": "a", "imagem": foto},
              news._chave_grupo(g2): {"resumo": "b", "imagem": foto}}
    with patch.object(news.ia_cache, "obter_varios", return_value=linhas):
        prontos = news.obter_resumos_prontos([g1, g2])
    assert prontos[g1["link"]]["imagem"] is None and prontos[g2["link"]]["imagem"] is None


@pytest.mark.parametrize("url_final", [
    "https://www.veiculo.com.br/",
    "https://www.veiculo.com.br/assine/?origem=paywall",
    "https://login.veiculo.com.br/entrar?next=/materia",
    "https://consent.google.com/ml?continue=https://x",
])
def test_13c_redirecionamento_pra_fora_da_materia_nao_vira_foto(url_final):
    html_txt = ("<html><head><meta property='og:image' content='https://cdn.veiculo.com.br/capa-do-site.jpg'>"
                f"</head><body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt, url_final)
    assert imagem is None


def test_13d_materia_com_slug_parecido_continua_aceita():
    assert not news._pagina_nao_e_materia("https://www.veiculo.com.br/economia/cadastro-positivo-2026/")
    assert not news._pagina_nao_e_materia("https://www.veiculo.com.br/mercado/vale-cobre")
    html_txt = ("<html><head><meta property='og:image' content='https://cdn.veiculo.com.br/2026/10/cadastro.jpg'>"
                f"</head><body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt, "https://www.veiculo.com.br/economia/cadastro-positivo-2026")
    assert imagem == "https://cdn.veiculo.com.br/2026/10/cadastro.jpg"


def test_13e_jsonld_nao_pega_foto_de_materia_relacionada():
    import json
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "url": "https://www.veiculo.com.br/mercado/vale-cobre",
         "hasPart": [{"@type": "NewsArticle", "headline": "Outra matéria",
                      "image": "https://cdn.veiculo.com.br/outra-materia.jpg"}],
         "relatedLink": {"@type": "NewsArticle", "image": "https://cdn.veiculo.com.br/relacionada.jpg"}},
        {"@type": "BreadcrumbList", "itemListElement": [{"item": {"image": "https://cdn.veiculo.com.br/secao.jpg"}}]},
    ]}
    html_txt = (f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head>"
                f"<body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt)
    assert imagem is None
    ld["@graph"].append({"@type": "NewsArticle", "image": {"@type": "ImageObject",
                                                             "url": "https://cdn.veiculo.com.br/vale-carajas.jpg"}})
    html_txt = (f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head>"
                f"<body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt)
    assert imagem == "https://cdn.veiculo.com.br/vale-carajas.jpg"


def test_13e2_jsonld_nao_pega_avatar_de_autor_pessoa_ou_organizacao():
    """Achado real (auditoria 2026-10-19, validação com rede de verdade -
    infomoney.com.br, matéria assinada "Reuters"): a exclusão de
    "author"/"publisher"/"logo" só protege contra recursar pra DENTRO
    dessas chaves quando aparecem como propriedade de outro node; não
    protege quando o Person/Organization é, ele mesmo, um item solto do
    array "@graph" (padrão Yoast SEO) - esse node bate direto na chave
    "image" genérica e o avatar do autor (aqui, o logo "reuters.png" que
    o veículo usa pra qualquer matéria da agência) virava a foto do card."""
    import json
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Person", "name": "Reuters",
         "image": {"@type": "ImageObject", "url": "https://cdn.veiculo.com.br/avatar-reuters.png"}},
        {"@type": "Organization", "name": "Veículo",
         "logo": {"@type": "ImageObject", "url": "https://cdn.veiculo.com.br/logo-veiculo.png"},
         "image": "https://cdn.veiculo.com.br/marca-veiculo.png"},
        {"@type": "NewsArticle", "headline": "Vale amplia produção de cobre no Pará"},
    ]}
    html_txt = (f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head>"
                f"<body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt)
    assert imagem is None

    ld["@graph"].append({"@type": "NewsArticle", "image": "https://cdn.veiculo.com.br/vale-carajas.jpg"})
    html_txt = (f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head>"
                f"<body><article>{_TEXTO}</article></body></html>")
    _t, imagem, _l, _m = _extrair_com_html(html_txt)
    assert imagem == "https://cdn.veiculo.com.br/vale-carajas.jpg"


def test_13f_403_e_bloqueio_temporario_e_foto_fica_nao_verificada():
    g = _grupo("Itaú reporta lucro", "https://news.google.com/403")
    with patch.object(news, "_extrair_texto_artigo",
                      return_value=("t", "https://img.cdn.com/itau.jpg", "https://cdn.com/m", None)), \
         patch.object(news.requests, "head", return_value=_Resp(403, {})), \
         patch.object(news.requests, "get", return_value=_Resp(403, {})):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] == "https://img.cdn.com/itau.jpg"
    assert reg["imagem_status"] == news.STATUS_IMAGEM_NAO_VERIFICADA


def test_13g_url_assinada_nunca_fica_confirmada_pra_sempre():
    assinada = "https://bucket.s3.amazonaws.com/foto.jpg?X-Amz-Expires=3600&X-Amz-Signature=abc"
    assert news._url_assinada(assinada)
    assert not news._url_assinada("https://cdn.x.com/foto.jpg?w=1200&base=2")
    g = _grupo("Fato com foto assinada", "https://news.google.com/sig")
    with patch.object(news, "_extrair_texto_artigo", return_value=("t", assinada, "https://x.com/m", None)), \
         patch.object(news.requests, "head", return_value=_img_ok(assinada)):
        reg = news.avaliar_imagem_grupo(g, _fontes(g))
    assert reg["imagem"] == assinada and reg["imagem_status"] == news.STATUS_IMAGEM_NAO_VERIFICADA
    agora = datetime.now(timezone.utc)
    assert not news._imagem_precisa_reavaliar(None, reg, agora + timedelta(hours=1))
    assert news._imagem_precisa_reavaliar(None, reg, agora + timedelta(hours=7))


def _carregar_script_amostra():
    import importlib.util
    from pathlib import Path
    caminho = Path(news.__file__).resolve().parents[1] / "docs/evidencias/imagens-news-20261019/validar_amostra_real.py"
    spec = importlib.util.spec_from_file_location("validar_amostra_real", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rodar_script_amostra(mod, tmp_path, grupos, respostas, head=None, head_exc=None):
    """Roda main() com o isolamento de produção ATIVO, mas restaurando os
    atributos globais na saída (patch.object devolve o original mesmo que o
    script os reatribua) - nunca contamina os outros testes."""
    import sys as _sys
    import data.coletores_status as cs
    import data.supabase_client as sc
    criados = []
    head_kw = {"side_effect": head_exc} if head_exc else {"return_value": head or _img_ok()}
    with patch.object(sc, "create_client", side_effect=lambda *a: criados.append(a)), \
         patch.object(news, "registrar_tentativa", side_effect=AssertionError("gravaria coletores_status")), \
         patch.object(cs, "registrar_tentativa", side_effect=AssertionError("gravaria coletores_status")), \
         patch.object(news, "_chamar_groq", side_effect=AssertionError("chamaria IA")), \
         patch.object(news, "obter_top_mercado", return_value=grupos), \
         patch.object(news, "obter_top_mercado_internacional", return_value=[]), \
         patch.object(news, "_extrair_texto_artigo", side_effect=lambda link: respostas[link]), \
         patch.object(news.requests, "head", **head_kw), \
         patch.object(news.requests, "get", **head_kw), \
         patch.object(_sys, "argv", ["x", "--n", "10", "--saida", str(tmp_path)]):
        mod.main()
        # depois do isolamento: nenhum cliente Supabase, status/IA neutralizados
        assert sc.create_client is None and sc.obter_cliente() is None
        assert news.registrar_tentativa("x", "y", execucao_ok=True) is None
        with pytest.raises(RuntimeError):
            news._chamar_groq("a", "b")
    assert criados == []  # nenhum cliente Supabase foi criado
    import csv as _csv
    with open(tmp_path / "amostra.csv", encoding="utf-8") as f:
        return list(_csv.DictReader(f))


def test_13h_script_de_amostra_real_e_somente_leitura_e_nunca_marca_correto(tmp_path):
    mod = _carregar_script_amostra()
    g = lambda t, k, v: dict(_grupo(t, f"https://news.google.com/{k}"), veiculos=[v])
    grupos = [g("Vale amplia cobre", "v1", "Valor"), g("Copom mantém Selic", "v2", "Folha"),
              g("Itaú lucra mais", "v3", "Estadão")]
    respostas = {
        "https://news.google.com/v1": ("t", "https://cdn.v.com/vale.jpg", "https://valor.com/vale", None),
        "https://news.google.com/v2": ("t", None, "https://folha.com/copom", None),
        "https://news.google.com/v3": (None, None, "https://estadao.com/itau",
                                       "falha HTTP ao acessar a matéria (HTTPError)"),  # 403 na página
    }
    linhas = _rodar_script_amostra(mod, tmp_path, grupos, respostas)
    por_veiculo = {l["veiculo"]: l for l in linhas}
    assert por_veiculo["Valor"]["status"] == "confirmada"
    assert por_veiculo["Valor"]["classificacao"] == "pendente_inspecao_visual"  # nunca "correto" automático
    assert por_veiculo["Folha"]["classificacao"] == "sem_imagem"
    assert por_veiculo["Estadão"]["classificacao"] == "bloqueado"
    assert all(l["classificacao"] != "correto" for l in linhas)
    html_txt = (tmp_path / "amostra.html").read_text(encoding="utf-8")
    assert "https://cdn.v.com/vale.jpg" in html_txt and "onerror" in html_txt


@pytest.mark.parametrize("head_kw,esperado", [
    ({"head_exc": requests.Timeout("lento")}, "bloqueado"),
    ({"head": _Resp(403, {})}, "bloqueado"),
    ({"head": _Resp(404, {})}, "sem_imagem"),
])
def test_13i_timeout_403_404_da_imagem_nunca_contam_como_correto(tmp_path, head_kw, esperado):
    mod = _carregar_script_amostra()
    grupos = [dict(_grupo("Petrobras sobe", "https://news.google.com/p"), veiculos=["InfoMoney"])]
    respostas = {"https://news.google.com/p": ("t", "https://cdn.im.com/petr.jpg", "https://infomoney.com/p", None)}
    linhas = _rodar_script_amostra(mod, tmp_path, grupos, respostas, **head_kw)
    assert linhas[0]["classificacao"] == esperado


def test_13j_apuracao_so_conta_casos_efetivamente_verificados(tmp_path):
    mod = _carregar_script_amostra()
    import csv as _csv
    caminho = tmp_path / "classificado.csv"
    classes = ["correto"] * 6 + ["incorreto"] + ["bloqueado", "sem_imagem", "inconclusivo"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["titulo", "classificacao"])
        w.writeheader()
        w.writerows({"titulo": f"t{i}", "classificacao": c} for i, c in enumerate(classes))
    r = mod.apurar(caminho)
    assert r["verificados"] == 7 and abs(r["taxa_correspondencia"] - 6 / 7) < 1e-9
    assert r["linhas_sem_classificacao_final"] == []
    # pendente de inspeção nunca entra como correto: apuração fica incompleta
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["titulo", "classificacao"])
        w.writeheader()
        w.writerows([{"titulo": "a", "classificacao": "pendente_inspecao_visual"},
                     {"titulo": "b", "classificacao": "bloqueado"}])
    r = mod.apurar(caminho)
    assert r["linhas_sem_classificacao_final"] == [1] and r["taxa_correspondencia"] is None
