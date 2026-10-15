# -*- coding: utf-8 -*-
"""Testes da reformulação editorial completa do Market News (2026-10-15):

1. gate de qualidade (_resumo_e_generico) - rejeita resumo que só repete a
   manchete com outras palavras ou usa frase de preenchimento genérica, e
   o caminho completo de _gerar_resumo_grupo descartando um resumo
   genérico da PRIMEIRA fonte e caindo pra próxima fonte do grupo (nunca
   cacheia o genérico).
2. imagens - filtro de logo/favicon/placeholder por nome de arquivo e por
   dimensão declarada (og:image:width), e o validador de rede
   (_url_imagem_utilizavel - sucesso, tipo errado, pequeno demais, erro
   HTTP, timeout) só exercido quando validar_imagem=True.
3. pré-geração em lote (pregerar_resumos_news) - dedup entre TOP MERCADO
   e busca por ticker, nunca re-gera o que já está cacheado, respeita
   orçamento de tempo e contagem máxima de resumos por execução.

Groq, extração de matéria, Supabase e rede são todos mockados - nenhuma
chamada real. Uso: python tests/test_news_qualidade_editorial.py (python
do .venv do projeto)."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


# ============================================================
# 1. _resumo_e_generico - gate de qualidade
# ============================================================

def test_1a_frase_proibida_e_detectada():
    resumo = "RESUMO:\nA empresa divulgou balanço, mas o mercado segue atento aos próximos passos."
    _checar("1a frase genérica proibida -> True", news_mod._resumo_e_generico(resumo, "Empresa divulga balanço"))


def test_1b_parafrase_pura_da_manchete_e_detectada():
    titulo = "Petrobras anuncia corte no plano de investimentos"
    resumo = "RESUMO:\nPetrobras anuncia corte no plano de investimentos da empresa."
    _checar("1b corpo é essencialmente a manchete reescrita -> True", news_mod._resumo_e_generico(resumo, titulo))


def test_1c_resumo_especifico_com_numeros_nao_e_generico():
    titulo = "Petrobras revisa plano de investimentos"
    resumo = (
        "RESUMO:\nA companhia reduziu o capex previsto de 2027 de R$ 12 bilhões "
        "para R$ 9,5 bilhões, citando queda no preço de referência do petróleo. "
        "O projeto Beta foi postergado em 8 meses, segundo o comunicado."
    )
    _checar("1c resumo com fatos/números específicos -> False", not news_mod._resumo_e_generico(resumo, titulo))


def test_1d_resumo_ou_titulo_vazio_nunca_e_generico():
    _checar("1d resumo vazio -> False (vazio é outro problema, não genérico)", not news_mod._resumo_e_generico("", "Título"))
    _checar("1e título vazio -> False", not news_mod._resumo_e_generico("RESUMO:\nTexto qualquer.", ""))


def test_1f_gerar_resumo_grupo_descarta_generico_da_1a_fonte_e_usa_a_2a():
    """Fonte 1 devolve texto extraído normalmente, mas o Groq (mockado)
    responde um resumo genérico pra ela - _gerar_resumo_grupo NUNCA pode
    aceitar isso: precisa descartar e tentar a 2ª fonte do grupo, que
    devolve um resumo específico de verdade."""
    resumo_generico = "RESUMO:\nA empresa Alfa é notícia e o mercado segue atento aos próximos movimentos."
    resumo_especifico = (
        "RESUMO:\nA Alfa reportou lucro líquido de R$ 500 milhões no trimestre, "
        "alta de 12% em relação ao ano anterior, segundo o balanço divulgado."
    )

    def _fake_extrair(link):
        return ("Texto longo o suficiente extraído da matéria real, com bastante conteúdo jornalístico de verdade.",
                "https://veiculo.com/foto.jpg", link.replace("news.google.com", "veiculo.com"), None)

    chamadas_groq = []

    def _fake_groq(prompt_sistema, prompt_usuario):
        chamadas_groq.append(prompt_usuario)
        if len(chamadas_groq) == 1:
            return resumo_generico, None
        return resumo_especifico, None

    with patch.object(news_mod, "_extrair_texto_artigo", side_effect=_fake_extrair), \
         patch.object(news_mod, "_chamar_groq", side_effect=_fake_groq):
        resultado = news_mod._gerar_resumo_grupo(
            "Alfa é notícia",
            (("Fonte1", "https://news.google.com/alfa1"), ("Fonte2", "https://news.google.com/alfa2")),
            ("Alfa é notícia",),
        )
    _checar("1g tentou as 2 fontes (não aceitou o genérico da 1a)", len(chamadas_groq) == 2)
    _checar("1h resultado final é o resumo específico (nunca o genérico)", resultado["resumo"] == resumo_especifico)


def test_1i_gerar_resumo_grupo_so_generico_em_todas_as_fontes_desiste_honestamente():
    resumo_generico = "RESUMO:\nVale a pena acompanhar de perto os desdobramentos desse caso."
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria, com conteúdo jornalístico real.",
                                     None, "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_generico, None)):
        resultado = news_mod._gerar_resumo_grupo(
            "Beta é notícia",
            (("Fonte1", "https://news.google.com/beta1"),),
            ("Beta é notícia",),
        )
    _checar("1j nenhum resumo genérico é devolvido como sucesso", resultado["resumo"] is None)
    _checar("1k motivo explica a rejeição por qualidade", "genérico" in (resultado["motivo_indisponivel"] or ""))


# ============================================================
# 2. imagens - filtro por nome de arquivo e dimensão declarada
# ============================================================

def test_2a_logo_e_favicon_sao_rejeitados_por_nome():
    _checar("2a logo.png rejeitado", news_mod._imagem_parece_generica("https://site.com/assets/logo.png"))
    _checar("2b favicon rejeitado", news_mod._imagem_parece_generica("https://site.com/favicon.ico"))
    _checar("2c og-default rejeitado", news_mod._imagem_parece_generica("https://site.com/img/og-default.jpg"))
    _checar("2d apple-touch-icon rejeitado", news_mod._imagem_parece_generica("https://site.com/apple-touch-icon.png"))
    _checar("2e foto editorial normal NÃO é rejeitada", not news_mod._imagem_parece_generica("https://site.com/materias/2026/foto-ceo-empresa.jpg"))


def test_2f_extracao_rejeita_og_image_que_e_logo_pelo_nome():
    html_com_logo = '<html><head><meta property="og:image" content="https://veiculo.com/assets/logo.png"></head></html>'
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia"), \
         patch.object(news_mod.requests, "get", return_value=_FakeResponseHtml(html_com_logo)), \
         patch.object(news_mod.trafilatura, "extract", return_value='{"text": "Texto bem longo o suficiente pra passar do limite minimo de extracao exigido pelo projeto todo."}'):
        texto, imagem, _, _ = news_mod._extrair_texto_artigo("https://news.google.com/x")
    _checar("2g og:image apontando pro logo nunca é aceito como capa", imagem is None)
    _checar("2h texto ainda extraído normalmente", bool(texto))


def test_2i_extracao_rejeita_imagem_com_dimensao_declarada_pequena():
    html_com_icone = (
        '<html><head>'
        '<meta property="og:image" content="https://veiculo.com/img/compartilhar.jpg">'
        '<meta property="og:image:width" content="96">'
        '<meta property="og:image:height" content="96">'
        '</head></html>'
    )
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia2"), \
         patch.object(news_mod.requests, "get", return_value=_FakeResponseHtml(html_com_icone)), \
         patch.object(news_mod.trafilatura, "extract", return_value='{"text": "Outro texto bem longo o suficiente pra passar do limite minimo exigido pelo projeto todo."}'):
        texto, imagem, _, _ = news_mod._extrair_texto_artigo("https://news.google.com/y")
    _checar("2j og:image:width=96 (ícone de compartilhamento) é rejeitado", imagem is None)


def test_2k_extracao_aceita_imagem_com_dimensao_declarada_grande():
    html_com_foto = (
        '<html><head>'
        '<meta property="og:image" content="https://veiculo.com/img/foto-materia.jpg">'
        '<meta property="og:image:width" content="1200">'
        '<meta property="og:image:height" content="630">'
        '</head></html>'
    )
    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia3"), \
         patch.object(news_mod.requests, "get", return_value=_FakeResponseHtml(html_com_foto)), \
         patch.object(news_mod.trafilatura, "extract", return_value='{"text": "Mais um texto bem longo o suficiente pra passar do limite minimo exigido pelo projeto todo."}'):
        texto, imagem, _, _ = news_mod._extrair_texto_artigo("https://news.google.com/z")
    _checar("2l foto editorial 1200x630 é aceita", imagem == "https://veiculo.com/img/foto-materia.jpg")


class _FakeResponseHtml:
    """Resposta fake de requests.get só com o necessário pra
    _extrair_texto_artigo: .raise_for_status(), .headers, .text, .url -
    e o protocolo de context manager (`with requests.get(...) as r:`,
    uso real em _extrair_texto_artigo)."""
    def __init__(self, html_texto, content_type="text/html; charset=utf-8"):
        self.text = html_texto
        self.headers = {"Content-Type": content_type}
        self.url = "https://veiculo.com/materia"
        self.status_code = 200

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


# ============================================================
# 2m. _url_imagem_utilizavel - validador de rede (só quando validar_imagem=True)
# ============================================================

class _FakeResp:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def test_2m_head_sucesso_imagem_valida():
    with patch.object(news_mod.requests, "head", return_value=_FakeResp(200, {"Content-Type": "image/jpeg", "Content-Length": "50000"})):
        _checar("2m HEAD 200 + image/jpeg + tamanho razoável -> True", news_mod._url_imagem_utilizavel("https://x.com/foto.jpg"))


def test_2n_content_type_errado_e_rejeitado():
    with patch.object(news_mod.requests, "head", return_value=_FakeResp(200, {"Content-Type": "text/html"})):
        _checar("2n Content-Type text/html -> False", not news_mod._url_imagem_utilizavel("https://x.com/pagina"))


def test_2o_imagem_pequena_demais_e_rejeitada():
    with patch.object(news_mod.requests, "head", return_value=_FakeResp(200, {"Content-Type": "image/png", "Content-Length": "300"})):
        _checar("2o imagem de 300 bytes (ícone/pixel) -> False", not news_mod._url_imagem_utilizavel("https://x.com/pixel.png"))


def test_2p_erro_http_e_rejeitado():
    with patch.object(news_mod.requests, "head", return_value=_FakeResp(404, {})), \
         patch.object(news_mod.requests, "get", return_value=_FakeResp(404, {})):
        _checar("2p HTTP 404 -> False", not news_mod._url_imagem_utilizavel("https://x.com/sumiu.jpg"))


def test_2q_timeout_e_rejeitado_sem_lancar_excecao():
    with patch.object(news_mod.requests, "head", side_effect=news_mod.requests.exceptions.Timeout("mock timeout")):
        _checar("2q timeout -> False, nunca lança exceção", not news_mod._url_imagem_utilizavel("https://x.com/lento.jpg"))


def test_2r_head_nao_suportado_cai_pro_get():
    with patch.object(news_mod.requests, "head", return_value=_FakeResp(405, {})), \
         patch.object(news_mod.requests, "get", return_value=_FakeResp(200, {"Content-Type": "image/webp", "Content-Length": "20000"})) as mock_get:
        _checar("2r HEAD 405 cai pro GET e aceita", news_mod._url_imagem_utilizavel("https://x.com/foto.webp"))
    _checar("2s GET foi chamado exatamente 1x (fallback do HEAD)", mock_get.call_count == 1)


def test_2t_url_vazia_ou_invalida_nunca_lanca():
    _checar("2t None -> False", not news_mod._url_imagem_utilizavel(None))
    _checar("2u string vazia -> False", not news_mod._url_imagem_utilizavel(""))


def test_2v_gerar_resumo_grupo_com_validar_imagem_descarta_imagem_invalida():
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo jornalístico de verdade.",
                                     "https://veiculo.com/foto-quebrada.jpg", "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=("RESUMO:\nA empresa Gama reportou receita de R$ 3 bilhões no trimestre.", None)), \
         patch.object(news_mod, "_url_imagem_utilizavel", return_value=False) as mock_validador:
        resultado = news_mod._gerar_resumo_grupo(
            "Gama reporta receita",
            (("Fonte", "https://news.google.com/gama"),),
            ("Gama reporta receita",),
            validar_imagem=True,
        )
    _checar("2w validador foi chamado (validar_imagem=True)", mock_validador.call_count == 1)
    _checar("2x imagem inválida é descartada (nunca cacheia link morto)", resultado["imagem"] is None)
    _checar("2y resumo continua presente (só a imagem foi descartada)", bool(resultado["resumo"]))


def test_2z_sem_validar_imagem_nunca_chama_o_validador_de_rede():
    """Default (validar_imagem=False, caminho sob-demanda/clique no card):
    ZERO chamada de rede extra só pra imagem - preserva a regra antiga."""
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria real, com conteúdo jornalístico de verdade.",
                                     "https://veiculo.com/foto.jpg", "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=("RESUMO:\nA empresa Delta reportou lucro de R$ 1 bilhão no trimestre.", None)), \
         patch.object(news_mod, "_url_imagem_utilizavel") as mock_validador:
        resultado = news_mod._gerar_resumo_grupo(
            "Delta reporta lucro",
            (("Fonte", "https://news.google.com/delta"),),
            ("Delta reporta lucro",),
        )
    _checar("2aa validador NUNCA chamado por padrão", mock_validador.call_count == 0)
    _checar("2ab imagem preservada (não há motivo pra descartar)", resultado["imagem"] == "https://veiculo.com/foto.jpg")


# ============================================================
# 3. pregerar_resumos_news - pré-processamento em lote
# ============================================================

def _grupo_fake(titulo, link, fontes=None):
    fontes = fontes or [{"veiculo": "Fonte", "link": link}]
    return {"titulo": titulo, "titulos": [titulo], "link": link, "fontes": fontes}


def test_3a_dedup_entre_top_mercado_e_busca_por_ticker():
    """O MESMO fato pode aparecer no TOP MERCADO e na busca por ticker -
    pregerar_resumos_news nunca pode gerar/chamar a IA 2x pro mesmo grupo
    (chave de cache idêntica)."""
    grupo = _grupo_fake("PETR4 anuncia dividendo extraordinário", "https://veiculo.com/petr4-dividendo")
    chamadas_resumo = []

    def _fake_obter_resumo_grupo(titulo, fontes_ordenadas, titulos=(), validar_imagem=False):
        chamadas_resumo.append(titulo)
        return {"resumo": "RESUMO:\nTexto qualquer.", "imagem": None, "motivo_indisponivel": None}

    with patch.object(news_mod, "obter_top_mercado_tudo", return_value=[grupo]), \
         patch.object(news_mod, "obter_noticias", return_value=[grupo]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_resumo_grupo", side_effect=_fake_obter_resumo_grupo):
        stats = news_mod.pregerar_resumos_news(["PETR4"])
    _checar("3a 1 grupo considerado (dedup pelo mesmo link/título)", stats["grupos_considerados"] == 1, f"({stats})")
    _checar("3b IA chamada exatamente 1x (nunca 2x pro mesmo fato)", len(chamadas_resumo) == 1, f"({chamadas_resumo})")
    _checar("3c stats['gerados'] == 1", stats["gerados"] == 1, f"({stats})")


def test_3d_grupo_ja_cacheado_nunca_chama_a_ia_de_novo():
    grupo = _grupo_fake("Vale anuncia novo projeto", "https://veiculo.com/vale-projeto")
    fontes_ordenadas = news_mod.ordenar_fontes_para_resumo(grupo["fontes"])
    links = tuple(l for _, l in fontes_ordenadas)
    chave = news_mod.ia_cache.chave_news(grupo["titulo"], links)

    with patch.object(news_mod, "obter_top_mercado_tudo", return_value=[grupo]), \
         patch.object(news_mod, "obter_noticias", return_value=[]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={chave: {"resumo": "já cacheado"}}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_resumo_grupo") as mock_gerar:
        stats = news_mod.pregerar_resumos_news([])
    _checar("3e grupo já cacheado -> 0 chamadas de IA", mock_gerar.call_count == 0)
    _checar("3f stats reflete 1 já cacheado, 0 gerados", stats["ja_cacheados"] == 1 and stats["gerados"] == 0, f"({stats})")


def test_3g_respeita_contagem_maxima_de_resumos_por_execucao():
    grupos = [_grupo_fake(f"Fato número {i} do dia", f"https://veiculo.com/fato-{i}") for i in range(news_mod._MAX_RESUMOS_POR_EXECUCAO + 10)]

    def _fake_obter_resumo_grupo(titulo, fontes_ordenadas, titulos=(), validar_imagem=False):
        return {"resumo": "RESUMO:\nTexto qualquer.", "imagem": None, "motivo_indisponivel": None}

    with patch.object(news_mod, "obter_top_mercado_tudo", return_value=grupos), \
         patch.object(news_mod, "obter_noticias", return_value=[]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_resumo_grupo", side_effect=_fake_obter_resumo_grupo) as mock_gerar:
        stats = news_mod.pregerar_resumos_news([])
    _checar("3h nunca gera mais que _MAX_RESUMOS_POR_EXECUCAO por execução",
            mock_gerar.call_count == news_mod._MAX_RESUMOS_POR_EXECUCAO, f"(chamadas={mock_gerar.call_count})")
    _checar("3i stats['tempo_esgotado']=True quando corta por limite de contagem", stats["tempo_esgotado"] is True)


def test_3j_respeita_orcamento_de_tempo():
    grupos = [_grupo_fake(f"Fato {i}", f"https://veiculo.com/f{i}") for i in range(5)]

    def _fake_obter_resumo_grupo(titulo, fontes_ordenadas, titulos=(), validar_imagem=False):
        return {"resumo": "RESUMO:\nTexto qualquer.", "imagem": None, "motivo_indisponivel": None}

    with patch.object(news_mod, "obter_top_mercado_tudo", return_value=grupos), \
         patch.object(news_mod, "obter_noticias", return_value=[]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_resumo_grupo", side_effect=_fake_obter_resumo_grupo) as mock_gerar, \
         patch.object(news_mod.time, "monotonic", side_effect=[0.0] + [10 ** 9] * 20):
        stats = news_mod.pregerar_resumos_news([])
    _checar("3k orçamento já esgotado antes do 1º resumo -> 0 gerados", mock_gerar.call_count == 0, f"(chamadas={mock_gerar.call_count})")
    _checar("3l tempo_esgotado=True", stats["tempo_esgotado"] is True)


def test_3m_falha_isolada_em_1_ticker_nao_aborta_os_demais():
    grupo_ok = _grupo_fake("Fato que funciona", "https://veiculo.com/ok")

    def _fake_obter_noticias(ticker):
        if ticker == "QUEBRA3":
            raise RuntimeError("fonte indisponível")
        return [grupo_ok]

    with patch.object(news_mod, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(news_mod, "obter_noticias", side_effect=_fake_obter_noticias), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_resumo_grupo", return_value={"resumo": "RESUMO:\nTexto.", "imagem": None, "motivo_indisponivel": None}):
        stats = news_mod.pregerar_resumos_news(["QUEBRA3", "OK4"])
    _checar("3n 1 falha registrada (ticker QUEBRA3)", stats["falhas"] == 1, f"({stats})")
    _checar("3o ticker seguinte (OK4) ainda processado normalmente", stats["gerados"] == 1, f"({stats})")


def test_3p_top_mercado_indisponivel_nao_quebra_o_pregen():
    with patch.object(news_mod, "obter_top_mercado_tudo", side_effect=RuntimeError("fonte fora do ar")), \
         patch.object(news_mod, "obter_noticias", return_value=[]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True):
        stats = news_mod.pregerar_resumos_news([])
    _checar("3q TOP MERCADO indisponível -> nunca lança exceção, 0 grupos", stats["grupos_considerados"] == 0, f"({stats})")


# ============================================================
# 4. ia_cache.tabela_disponivel() + abort antecipado do pregen
#    (achado real 2026-10-15: resumos_ia_cache nunca foi criada em
#    produção - sql/ia_cache.sql nunca rodou lá - e sem esta checagem
#    pregerar_resumos_news gastava cota REAL do Groq em toda execução do
#    coletor sem conseguir cachear nada, porque a escrita falhava depois
#    do gerar_fn() já ter rodado de verdade).
# ============================================================

def test_4a_tabela_disponivel_true_quando_consulta_responde():
    with patch.object(news_mod.ia_cache, "obter_cliente") as mock_obter_cliente:
        mock_cliente = mock_obter_cliente.return_value
        mock_cliente.table.return_value.select.return_value.limit.return_value.execute.return_value = None
        resultado = news_mod.ia_cache.tabela_disponivel()
    _checar("4a consulta trivial bem-sucedida -> True", resultado is True)


def test_4b_tabela_disponivel_classifica_tabela_ausente_pgrst205():
    class _ErroFake(Exception):
        code = "PGRST205"
        message = "Could not find the table 'public.resumos_ia_cache' in the schema cache"

    with patch.object(news_mod.ia_cache, "obter_cliente") as mock_obter_cliente:
        mock_obter_cliente.return_value.table.side_effect = _ErroFake()
        resultado = news_mod.ia_cache.tabela_disponivel()
    _checar("4b PGRST205/'could not find the table' -> TABELA_AUSENTE",
            resultado == news_mod.ia_cache.TABELA_AUSENTE, f"(resultado={resultado!r})")


def test_4c_tabela_disponivel_classifica_credencial_rls_42501():
    class _ErroFake(Exception):
        code = "42501"
        message = 'new row violates row-level security policy for table "resumos_ia_cache"'

    with patch.object(news_mod.ia_cache, "obter_cliente") as mock_obter_cliente:
        mock_obter_cliente.return_value.table.side_effect = _ErroFake()
        resultado = news_mod.ia_cache.tabela_disponivel()
    _checar("4c erro 42501 (RLS) -> TABELA_CREDENCIAL_OU_CONEXAO",
            resultado == news_mod.ia_cache.TABELA_CREDENCIAL_OU_CONEXAO, f"(resultado={resultado!r})")


def test_4d_tabela_disponivel_erro_desconhecido_quando_nao_bate_nenhum_sinal():
    class _ErroFake(Exception):
        code = "99999"
        message = "alguma falha sem sinal conhecido"

    with patch.object(news_mod.ia_cache, "obter_cliente") as mock_obter_cliente:
        mock_obter_cliente.return_value.table.side_effect = _ErroFake()
        resultado = news_mod.ia_cache.tabela_disponivel()
    _checar("4d erro sem sinal conhecido -> TABELA_ERRO_DESCONHECIDO",
            resultado == news_mod.ia_cache.TABELA_ERRO_DESCONHECIDO, f"(resultado={resultado!r})")


def test_4e_tabela_disponivel_none_quando_supabase_sem_cliente():
    with patch.object(news_mod.ia_cache, "obter_cliente", return_value=None):
        resultado = news_mod.ia_cache.tabela_disponivel()
    _checar("4e sem cliente configurado -> None (nunca lança exceção)", resultado is None)


def test_4f_pregen_aborta_sem_gastar_nenhuma_chamada_de_ia_quando_tabela_ausente():
    grupo = _grupo_fake("Fato qualquer", "https://veiculo.com/fato")
    with patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=news_mod.ia_cache.TABELA_AUSENTE), \
         patch.object(news_mod, "obter_top_mercado_tudo", return_value=[grupo]) as mock_top, \
         patch.object(news_mod, "obter_noticias") as mock_noticias, \
         patch.object(news_mod, "obter_resumo_grupo") as mock_gerar:
        stats = news_mod.pregerar_resumos_news(["PETR4"])
    _checar("4g pregen devolve a causa exata em stats['tabela_disponivel']",
            stats["tabela_disponivel"] == news_mod.ia_cache.TABELA_AUSENTE, f"({stats})")
    _checar("4h NUNCA busca TOP MERCADO (evita trabalho inútil)", mock_top.call_count == 0)
    _checar("4i NUNCA busca noticia por ticker", mock_noticias.call_count == 0)
    _checar("4j ZERO chamada de IA (o ponto inteiro desta checagem)", mock_gerar.call_count == 0)
    _checar("4k stats continua com os outros campos zerados, nunca None/ausente",
            stats["grupos_considerados"] == 0 and stats["gerados"] == 0, f"({stats})")


def test_4l_pregen_roda_normalmente_quando_tabela_disponivel():
    """Confirma que o guard so' bloqueia quando tabela_disponivel() NAO
    e' True - com a tabela disponivel, o fluxo de sempre continua
    (nenhuma regressao introduzida pelo guard)."""
    grupo = _grupo_fake("Fato normal", "https://veiculo.com/normal")
    with patch.object(news_mod.ia_cache, "tabela_disponivel", return_value=True), \
         patch.object(news_mod, "obter_top_mercado_tudo", return_value=[grupo]), \
         patch.object(news_mod, "obter_noticias", return_value=[]), \
         patch.object(news_mod.ia_cache, "obter_varios", return_value={}), \
         patch.object(news_mod, "obter_resumo_grupo",
                       return_value={"resumo": "RESUMO:\nTexto.", "imagem": None, "motivo_indisponivel": None}) as mock_gerar:
        stats = news_mod.pregerar_resumos_news([])
    _checar("4m tabela disponivel -> stats['tabela_disponivel'] is True", stats["tabela_disponivel"] is True)
    _checar("4n processamento normal continua (1 grupo gerado)", stats["gerados"] == 1, f"({stats})")
    _checar("4o IA foi chamada normalmente", mock_gerar.call_count == 1)


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
    print("TODOS OS TESTES DE QUALIDADE EDITORIAL DO NEWS PASSARAM")
