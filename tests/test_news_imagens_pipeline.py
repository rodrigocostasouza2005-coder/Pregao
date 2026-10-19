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


def test_12b_capa_do_modal_recorta_dentro_do_container_e_reduz():
    news_tab._capa_data_uri.clear()
    with patch.object(news_tab, "_baixar_imagem_capa", return_value=_png_bytes(1800, 2400)):
        uri = news_tab._capa_data_uri("https://x.com/retrato.jpg")
    assert uri.startswith("data:image/jpeg;base64,")
    from PIL import Image
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as img:
        assert img.width == news_tab._LARGURA_MAX_CAPA

    saidas = []
    with patch.object(news_tab, "_capa_data_uri", return_value=uri), \
         patch.object(news_tab.st, "markdown", side_effect=lambda h, **k: saidas.append(h)), \
         patch.object(news_tab.st, "image", side_effect=AssertionError("st.image solto não respeita o recorte")):
        news_tab._renderizar_capa("https://x.com/retrato.jpg", "Valor")
    assert saidas[0].startswith("<div class='news-capa'>") and uri in saidas[0]


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
