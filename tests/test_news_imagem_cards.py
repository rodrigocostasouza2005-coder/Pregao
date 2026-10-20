# -*- coding: utf-8 -*-
"""Testes da investigação do bug real "imagens dos cards de notícias não
exibem corretamente" (auditoria 2026-10-17).

Causa raiz confirmada rastreando o fluxo completo (coleta -> cache ->
backend -> frontend):

1. `data/news.py:_url_imagem_utilizavel` (usada pelo PRÉ-PROCESSAMENTO em
   lote, `pregerar_resumos_news`, que é quem popula o cache Supabase lido
   pelo feed via `obter_resumos_prontos` SEM request por card) validava a
   og:image com um User-Agent educado/autoidentificado como bot
   ("PregaoApp/0.1 ..."), igual ao usado pro RSS do Google News. Vários
   CDNs de imagem de veículo BR (ex: glbimg, imguol) bloqueiam/degradam
   esse tipo de UA só nas imagens, mesmo quando o download do ARTIGO
   (`_extrair_texto_artigo`, que já usa UA de navegador real) funciona -
   fazendo esta validação descartar (`imagem=None`) uma og:image
   perfeitamente válida ANTES de chegar no cache que o feed lê.
2. `ui/news_tab.py:_baixar_imagem_capa` (download da capa do modal) tinha
   o mesmo problema com outro UA de bot ("PregaoNews/1.0").
3. `ui/news_tab.py:_thumb_html` (thumbnail do card da LISTA do feed -
   nunca passa pelo proxy server-side, por design: zero request de rede
   por card) faz hotlink direto do navegador pro CDN do veículo sem
   `referrerpolicy`, ficando exposto a bloqueio de hotlink por Referer
   (comum nesses CDNs) que o download server-side da capa do modal nunca
   enfrenta.

Este arquivo cobre as 3 correções: UA de navegador real nas 2 chamadas de
rede relacionadas a imagem, e `referrerpolicy='no-referrer'` nos 2 <img>
que o navegador busca direto (thumb do feed e segunda via da capa).

Tudo mockado (requests.head/get, PIL) - nenhuma chamada de rede real.
Uso: python tests/test_news_imagem_cards.py (venv do projeto) ou pytest.

LIMITAÇÃO EXPLÍCITA: sem acesso a browser real neste ambiente - estes
testes confirmam o HTML/headers gerados pelo backend (prova real do que
o código faz), não que um CDN específico em produção de fato aceita o UA
novo ou libera sem referer (isso só se confirma abrindo o app publicado
e observando a aba Network do navegador contra uma notícia real)."""
import html
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod
import ui.news_tab as news_tab_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


class _RespostaFake:
    """Simula uma requests.Response o suficiente pra passar pelos dois
    caminhos exercitados (_url_imagem_utilizavel HEAD/GET e
    _baixar_imagem_capa GET streaming, que usa `with ... as response:` -
    __enter__/__exit__ precisam estar na CLASSE, nao so' na instancia,
    pra o protocolo de context manager do `with` encontrar)."""

    def __init__(self, status_code=200, headers=None, chunks=(b"fake-image-bytes",)):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=0):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _resposta_fake(status_code=200, headers=None, chunks=(b"fake-image-bytes",)):
    return _RespostaFake(status_code, headers, chunks)


# ============================================================
# 1. data/news.py:_url_imagem_utilizavel - UA de navegador real (causa
#    raiz: UA de bot fazia o CDN bloquear so' a VALIDACAO da imagem, que
#    e' quem decide se a foto entra no cache usado pelo feed)
# ============================================================

def test_1a_validacao_de_imagem_usa_user_agent_de_navegador_real():
    chamadas = []

    def _head_fake(url, headers=None, timeout=None, allow_redirects=None):
        chamadas.append(headers or {})
        return _resposta_fake(200, {"Content-Type": "image/jpeg", "Content-Length": "5000"})

    with patch.object(news_mod.requests, "head", side_effect=_head_fake):
        ok = news_mod._url_imagem_utilizavel("https://cdn.g1.globo.com/foto-real.jpg")

    _checar("1a imagem validada com sucesso", ok is True)
    ua = chamadas[0].get("User-Agent", "")
    _checar("1b UA e' de navegador real (Chrome/Mozilla), nao mais 'PregaoApp'",
            "PregaoApp" not in ua and "Chrome" in ua, f"(UA={ua!r})")


def test_1b_validacao_cai_pra_get_com_mesmo_ua_quando_head_nao_suportado():
    chamadas_get = []

    def _head_405(url, headers=None, timeout=None, allow_redirects=None):
        return _resposta_fake(405, {})

    def _get_fake(url, headers=None, timeout=None, stream=None):
        chamadas_get.append(headers or {})
        return _resposta_fake(200, {"Content-Type": "image/png", "Content-Length": "9000"})

    with patch.object(news_mod.requests, "head", side_effect=_head_405), \
         patch.object(news_mod.requests, "get", side_effect=_get_fake):
        ok = news_mod._url_imagem_utilizavel("https://cdn.estadao.com.br/foto.png")

    _checar("1c GET de fallback tambem valida (HEAD 405 nao e' tratado como falha definitiva)", ok is True)
    _checar("1d GET de fallback usa o MESMO UA de navegador (consistencia)",
            "Chrome" in chamadas_get[0].get("User-Agent", ""))


def test_1e_imagem_pixel_de_rastreio_continua_rejeitada():
    """Regressao: a troca de UA nao afrouxa o filtro de tamanho minimo
    (pixel de rastreio/icone disfarcado de foto editorial)."""
    with patch.object(news_mod.requests, "head",
                       return_value=_resposta_fake(200, {"Content-Type": "image/gif", "Content-Length": "40"})):
        ok = news_mod._url_imagem_utilizavel("https://cdn.exemplo.com/pixel.gif")
    _checar("1e pixel de rastreio (40 bytes) continua reprovado", ok is False)


def test_1f_url_invalida_ou_inacessivel_nunca_lanca_excecao():
    """URL inacessivel (erro de rede real) -> False, nunca propaga excecao
    pra quem chama (_gerar_resumo_grupo)."""
    import requests as requests_lib

    with patch.object(news_mod.requests, "head", side_effect=requests_lib.ConnectionError("fora do ar")):
        ok = news_mod._url_imagem_utilizavel("https://host-inexistente.invalido/foto.jpg")
    _checar("1f falha de rede na validacao -> False, sem excecao", ok is False)


# ============================================================
# 2. ui/news_tab.py:_baixar_imagem_capa - mesmo UA de navegador real
#    (causa raiz: UA de bot fazia o CDN bloquear o download da CAPA)
# ============================================================

def test_2a_download_da_capa_usa_user_agent_de_navegador_real():
    news_tab_mod._baixar_imagem_capa.clear()
    chamadas = []

    class _FakeImg:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def verify(self):
            return None

    def _get_fake(url, headers=None, timeout=None, stream=None, allow_redirects=None):
        chamadas.append(headers or {})
        return _resposta_fake(200, {"Content-Type": "image/jpeg"}, chunks=(b"foto-de-verdade",))

    with patch.object(news_tab_mod.requests, "get", side_effect=_get_fake), \
         patch("PIL.Image.open", return_value=_FakeImg()):
        dados = news_tab_mod._baixar_imagem_capa("https://cdn.uol.com.br/foto.jpg")

    _checar("2a download da capa funciona com a imagem mockada", dados == b"foto-de-verdade")
    ua = chamadas[0].get("User-Agent", "")
    _checar("2b UA e' de navegador real, nao mais 'PregaoNews/1.0'",
            "PregaoNews" not in ua and "Chrome" in ua, f"(UA={ua!r})")
    news_tab_mod._baixar_imagem_capa.clear()


def test_2c_download_da_capa_com_http_erro_vira_none_sem_excecao():
    news_tab_mod._baixar_imagem_capa.clear()

    def _get_erro(url, headers=None, timeout=None, stream=None, allow_redirects=None):
        return _resposta_fake(403, {})

    with patch.object(news_tab_mod.requests, "get", side_effect=_get_erro):
        dados = news_tab_mod._baixar_imagem_capa("https://cdn.bloqueado.com/foto.jpg")
    _checar("2c HTTP 403 (bloqueio real) -> None, nunca excecao", dados is None)
    news_tab_mod._baixar_imagem_capa.clear()


def test_2d_url_vazia_ou_nao_http_nunca_tenta_rede():
    news_tab_mod._baixar_imagem_capa.clear()
    with patch.object(news_tab_mod.requests, "get") as get_mock:
        _checar("2d None -> None sem chamar rede", news_tab_mod._baixar_imagem_capa(None) is None)
        _checar("2e data: URI -> None sem chamar rede (nunca aceita URL relativa/embutida)",
                news_tab_mod._baixar_imagem_capa("data:image/png;base64,Zm9v") is None)
        _checar("2f zero chamadas de rede pras duas acima", get_mock.call_count == 0)
    news_tab_mod._baixar_imagem_capa.clear()


# ============================================================
# 3. ui/news_tab.py:_thumb_html / _capa_html - referrerpolicy e
#    fallback visual (thumb do feed NUNCA passa pelo proxy - hotlink
#    direto do navegador, por isso precisa do referrerpolicy)
# ============================================================

def test_3a_thumb_com_imagem_valida_inclui_referrerpolicy_no_referrer():
    html_saida = news_tab_mod._thumb_html("https://cdn.g1.globo.com/foto.jpg", "G1")
    _checar("3a <img> presente com a URL real (nunca inventa outra)",
            "https://cdn.g1.globo.com/foto.jpg" in html_saida)
    _checar("3b referrerpolicy='no-referrer' presente no thumb", "referrerpolicy='no-referrer'" in html_saida)
    _checar("3c fallback (iniciais) presente mas OCULTO por padrao (display:none)",
            "display:none" in html_saida and "G1"[:2].upper() in html_saida.upper())


def test_3d_thumb_sem_imagem_mostra_so_fallback_sem_img_quebrado():
    html_saida = news_tab_mod._thumb_html(None, "InfoMoney")
    _checar("3d sem imagem -> nenhuma tag <img> (nunca icone de imagem quebrada)", "<img" not in html_saida)
    _checar("3e fallback com iniciais do veiculo aparece visivel", "IN" in html_saida)


def test_3f_capa_com_imagem_valida_inclui_referrerpolicy_no_referrer():
    html_saida = news_tab_mod._capa_html("https://cdn.valor.globo.com/foto.jpg", "Valor Econômico")
    _checar("3f <img> da capa presente com a URL real", "https://cdn.valor.globo.com/foto.jpg" in html_saida)
    _checar("3g referrerpolicy='no-referrer' presente na capa (2a via, navegador busca direto)",
            "referrerpolicy='no-referrer'" in html_saida)


def test_3h_capa_sem_imagem_mostra_so_fallback_do_veiculo():
    html_saida = news_tab_mod._capa_html(None, "Reuters")
    _checar("3h sem imagem -> nenhuma tag <img> na capa", "<img" not in html_saida)
    _checar("3i fallback mostra nome do veiculo", "Reuters" in html_saida)


def test_3j_url_com_aspas_ou_html_e_escapada_nunca_injeta_markup():
    """Nunca confiar na URL (vinda de og:image de terceiros) sem escapar -
    regressao de seguranca que tambem garante que a imagem renderiza
    como atributo valido (imagem 'incorreta' no DOM quebraria o layout)."""
    maliciosa = "https://x.com/a.jpg'><script>alert(1)</script>"
    html_saida = news_tab_mod._thumb_html(maliciosa, "X")
    _checar("3j aspas/HTML da URL vem escapados (sem <script> cru no DOM)", "<script>" not in html_saida)


# ============================================================
# 4. integracao data -> ui: o MESMO campo "imagem" (nunca outro nome)
#    atravessa gerar_resumo -> card da lista -> capa do modal, com
#    formatos de URL diferentes entre "coletores" (fontes) distintos
# ============================================================

def _grupo_fake(imagem_fonte):
    """_extrair_texto_artigo fake devolvendo (texto, imagem, link_real,
    motivo) - simula o formato real de UMA fonte do grupo."""
    return ("Texto completo da matéria com informação suficiente para resumir de verdade, "
            "contendo mais de sessenta caracteres de corpo real.", imagem_fonte,
            "https://veiculo.com/materia-real", None)


def test_4a_imagem_do_resumo_chega_identica_no_thumb_e_na_capa():
    """URLs vindas de 2 'coletores' (hosts) distintos - confirma que o
    pipeline nao perde nem troca a URL entre as camadas, mesmo quando o
    formato da URL muda (com/sem query string, extensao diferente)."""
    for imagem_fonte in (
        "https://s2.glbimg.com/abc/materia-capa.jpg",
        "https://conteudo.imguol.com.br/fotos/2026/foto.png?w=800&h=450",
    ):
        with patch.object(news_mod, "_extrair_texto_artigo", return_value=_grupo_fake(imagem_fonte)), \
             patch.object(news_mod, "_resumir_com_groq", return_value=("RESUMO:\nResumo de teste válido.", None)):
            resultado = news_mod._gerar_resumo_grupo("Título do grupo", (("Veículo", "https://veiculo.com/materia"),))

        _checar(f"4a imagem preservada sem alteração ({imagem_fonte})", resultado["imagem"] == imagem_fonte)

        # compara com a URL ESCAPADA (html.escape) - a comparação com a
        # URL crua falha de propósito quando a URL tem '&' (ex: query
        # string com múltiplos parâmetros), que o escape HTML converte
        # pra '&amp;' - isso é escaping correto, não perda/troca de URL.
        esperado = html.escape(imagem_fonte)

        thumb = news_tab_mod._thumb_html(resultado["imagem"], "Veículo")
        _checar(f"4b thumb do feed usa a MESMA URL ({imagem_fonte})", esperado in thumb)

        capa = news_tab_mod._capa_html(resultado["imagem"], "Veículo")
        _checar(f"4c capa do modal usa a MESMA URL ({imagem_fonte})", esperado in capa)


def test_4d_imagem_ausente_na_fonte_nunca_inventa_url_no_card_nem_na_capa():
    with patch.object(news_mod, "_extrair_texto_artigo", return_value=_grupo_fake(None)), \
         patch.object(news_mod, "_resumir_com_groq", return_value=("RESUMO:\nResumo sem foto.", None)):
        resultado = news_mod._gerar_resumo_grupo("Título sem foto", (("Veículo", "https://veiculo.com/materia"),))

    _checar("4d sem og:image na fonte -> imagem None (nunca inventa)", resultado["imagem"] is None)
    thumb = news_tab_mod._thumb_html(resultado["imagem"], "Veículo")
    capa = news_tab_mod._capa_html(resultado["imagem"], "Veículo")
    _checar("4e thumb sem imagem -> sem <img>", "<img" not in thumb)
    _checar("4f capa sem imagem -> sem <img>", "<img" not in capa)


# ============================================================
# 5. regressão de layout (sem browser real - inspeção de CSS/estrutura,
#    limitação documentada no BACKLOG e reconfirmada aqui)
# ============================================================

def test_5a_css_de_corte_e_dimensao_do_thumb_e_da_capa_continua_presente():
    css = news_tab_mod._CSS_WIRE
    _checar("5a CSS do thumb do feed ainda define object-fit:cover (sem distorcer a foto)",
            ".news-item-thumb-wrap img" in css and "object-fit: cover" in css)
    _checar("5b CSS da capa do modal ainda define object-fit:cover", ".news-capa img" in css and "object-fit: cover" in css)


def test_5c_listener_global_de_fallback_cobre_tanto_thumb_quanto_capa():
    """O script injetado por injetar_fallback_imagem() precisa continuar
    escutando falha de carregamento tanto no thumb do feed quanto na
    capa do modal - se o seletor mudar sem querer, imagem quebrada volta
    a aparecer sem fallback."""
    script = news_tab_mod._SCRIPT_FALLBACK_IMAGEM
    _checar("5d listener cobre '.news-item-thumb-wrap'", ".news-item-thumb-wrap" in script)
    _checar("5e listener cobre '.news-capa'", ".news-capa" in script)


# ============================================================
# 6. Vinculo notícia <-> imagem no FEED real (2+ cards na mesma tela) -
# achado da investigacao 2026-10-19: os testes acima (secao 4) chamam
# _thumb_html diretamente com a imagem ja' escolhida a mao - nenhum
# cobria o CAMINHO completo (resumos_prontos.get(n["link"]) dentro do
# loop de _renderizar_feed_editorial) com 2+ noticias cacheadas ao MESMO
# tempo, onde um bug de chave trocada so' apareceria com 2 itens
# distintos (1 item so' sempre "acerta" por coincidencia).
# ============================================================

def test_6a_feed_com_2_noticias_cada_uma_mostra_so_a_PROPRIA_imagem():
    n1 = {"link": "https://link-a.com", "titulo": "Fato A", "data": "2026-10-19T10:00:00+00:00",
          "veiculos": ["InfoMoney"], "fontes_count": 1, "score": 50, "selo": "", "regras": [], "tickers": []}
    n2 = {"link": "https://link-b.com", "titulo": "Fato B", "data": "2026-10-19T09:00:00+00:00",
          "veiculos": ["Valor"], "fontes_count": 1, "score": 50, "selo": "", "regras": [], "tickers": []}
    resumos_prontos = {
        "https://link-a.com": {"resumo": "resumo A", "imagem": "https://img-a.jpg"},
        "https://link-b.com": {"resumo": "resumo B", "imagem": "https://img-b.jpg"},
    }
    itens_feed = [{"tipo_feed": "NOTICIA", "chave_data": n1["data"], "dado": n1},
                  {"tipo_feed": "NOTICIA", "chave_data": n2["data"], "dado": n2}]
    blocos = []
    with patch.object(news_tab_mod.st, "columns", return_value=[MagicMock(), MagicMock()]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(news_tab_mod.st, "button", return_value=False):
        news_tab_mod._renderizar_feed_editorial.__wrapped__(itens_feed, [], resumos_prontos, "teste")
    html_completo = "\n".join(blocos)
    _checar("6a-1 imagem A aparece no HTML renderizado", "img-a.jpg" in html_completo)
    _checar("6a-2 imagem B aparece no HTML renderizado", "img-b.jpg" in html_completo)
    # garante que nao e' so' "as duas aparecem em algum lugar" - cada
    # thumb individual (<img src=...>) tem a URL CERTA, nunca trocada
    thumbs = [b for b in blocos if "news-item-thumb-wrap" in b]
    _checar("6a-3 exatamente 2 thumbs renderizados (1 por noticia)", len(thumbs) == 2)
    _checar("6a-4 thumb de A tem SO' a imagem de A (nunca a de B)",
            "img-a.jpg" in thumbs[0] and "img-b.jpg" not in thumbs[0], f"(thumb={thumbs[0]!r})")
    _checar("6a-5 thumb de B tem SO' a imagem de B (nunca a de A)",
            "img-b.jpg" in thumbs[1] and "img-a.jpg" not in thumbs[1], f"(thumb={thumbs[1]!r})")


def test_6b_noticia_sem_resumo_cacheado_usa_fallback_nunca_imagem_de_outra():
    """Confirma o caso real do pipeline: 30 grupos avaliados, nem todos
    confirmados (2 'sem imagem' no ultimo run real) - uma noticia SEM
    entrada em resumos_prontos nunca deve herdar a foto da vizinha."""
    n1 = {"link": "https://link-a.com", "titulo": "Fato A", "data": "2026-10-19T10:00:00+00:00",
          "veiculos": ["InfoMoney"], "fontes_count": 1, "score": 50, "selo": "", "regras": [], "tickers": []}
    n2 = {"link": "https://link-sem-foto.com", "titulo": "Fato Sem Foto", "data": "2026-10-19T09:00:00+00:00",
          "veiculos": ["Valor"], "fontes_count": 1, "score": 50, "selo": "", "regras": [], "tickers": []}
    resumos_prontos = {"https://link-a.com": {"resumo": "resumo A", "imagem": "https://img-a.jpg"}}
    itens_feed = [{"tipo_feed": "NOTICIA", "chave_data": n1["data"], "dado": n1},
                  {"tipo_feed": "NOTICIA", "chave_data": n2["data"], "dado": n2}]
    blocos = []
    with patch.object(news_tab_mod.st, "columns", return_value=[MagicMock(), MagicMock()]), \
         patch.object(news_tab_mod.st, "markdown", side_effect=lambda t, **_k: blocos.append(t)), \
         patch.object(news_tab_mod.st, "button", return_value=False):
        news_tab_mod._renderizar_feed_editorial.__wrapped__(itens_feed, [], resumos_prontos, "teste")
    thumbs = [b for b in blocos if "news-item-thumb-wrap" in b]
    _checar("6b-1 noticia sem resumo cacheado mostra fallback (iniciais), nunca <img>",
            "<img" not in thumbs[1] and "news-item-thumb-fallback" in thumbs[1], f"(thumb={thumbs[1]!r})")
    _checar("6b-2 a noticia SEM foto nunca herda a imagem da outra",
            "img-a.jpg" not in thumbs[1])


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE IMAGEM DOS CARDS DE NOTICIA PASSARAM")
