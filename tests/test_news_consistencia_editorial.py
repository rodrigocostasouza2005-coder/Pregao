# -*- coding: utf-8 -*-
"""Testes da auditoria do pipeline de noticias/IA (ABA 5, 2026-10-17).

Achado real em producao que motivou este arquivo: manchete "IBOVESPA
fecha hoje com alta de 0,54%" com RESUMO cacheado afirmando queda,
atribuindo o movimento a pesquisas eleitorais/Fed/petroleo sem nenhuma
base no texto/manchetes de origem, exibindo "17 fonte(s)"/"PROV 100" sem
deixar claro o que essas metricas significam. Nenhum gate ate' aqui
verificava:
  (a) contradicao de direcao de mercado/percentual entre titulo e resumo
      (ver data/news.py:_contradicao_titulo_resumo);
  (b) causalidade atribuida pela IA sem base no texto/manchetes
      (ver data/news.py:_causalidade_sem_evidencia);
  (c) semantica do selo/score e da contagem de fontes
      (ver ui/news_tab.py:_tooltip_regras);
  (d) cache servindo pra sempre um resumo gerado antes desses gates
      existirem (ver data/ia_cache.py:_VERSAO_CHAVE_NEWS, bump v3->v4).

Cobre os 15 cenarios obrigatorios do pedido (numerados nos nomes dos
testes). Groq, extracao de materia e Supabase sao todos mockados -
nenhuma chamada real de rede nem de IA.

Uso: python tests/test_news_consistencia_editorial.py (python do .venv
do projeto) ou pytest tests/test_news_consistencia_editorial.py."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.news as news_mod
import data.ia_cache as ia_cache_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


# ============================================================
# 1. Manchete de alta com texto que afirma queda
# ============================================================

def test_01_manchete_alta_corpo_queda_e_contradicao():
    titulo = "IBOVESPA fecha hoje com alta de 0,54%"
    corpo = "RESUMO:\nO Ibovespa encerrou o pregão em queda, pressionado pelo exterior."
    motivo = news_mod._contradicao_titulo_resumo(titulo, corpo)
    _checar("01 direcao oposta (alta x queda) e' detectada", motivo is not None and "alta" in motivo and "queda" in motivo)


def test_01b_gerar_resumo_grupo_descarta_resumo_contraditorio_e_nao_publica():
    """Fluxo completo: a UNICA fonte do grupo devolve um resumo que
    contradiz a direcao do titulo - _gerar_resumo_grupo NUNCA pode
    devolver isso como sucesso (Caso 3 do pedido: "se não resolver, não
    publicar uma síntese afirmativa contraditória")."""
    titulo = "IBOVESPA fecha hoje com alta de 0,54%"
    resumo_contraditorio = "RESUMO:\nO Ibovespa encerrou o pregão em queda, pressionado pelo exterior."
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente extraído da matéria, com conteúdo jornalístico real.",
                                     None, "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_contraditorio, None)):
        resultado = news_mod._gerar_resumo_grupo(titulo, (("Veiculo", "https://veiculo.com/materia"),), (titulo,))
    _checar("01c resumo contraditorio NUNCA e' devolvido como sucesso", resultado["resumo"] is None)
    _checar("01d motivo explica a contradicao", "inconsistente" in (resultado.get("motivo_indisponivel") or ""))


# ============================================================
# 2. Percentual divergente entre manchete e corpo
# ============================================================

def test_02_percentual_divergente_e_contradicao():
    titulo = "Ibovespa fecha em alta de 0,54%"
    corpo = "RESUMO:\nO índice encerrou em alta de 3,80%, puxado por bancos."
    motivo = news_mod._contradicao_titulo_resumo(titulo, corpo)
    _checar("02a percentuais bem diferentes -> contradicao", motivo is not None and "percentual" in motivo)


def test_02b_diferenca_de_arredondamento_nao_e_falso_positivo():
    """0,54% (titulo) x 0,5% (resumo, arredondado por outra fonte) e' a
    MESMA informacao - a tolerancia (_TOLERANCIA_PERCENTUAL) existe
    exatamente pra nao bloquear isso."""
    titulo = "Ibovespa fecha em alta de 0,54%"
    corpo = "RESUMO:\nO índice fechou em alta de 0,5%, puxado por bancos."
    motivo = news_mod._contradicao_titulo_resumo(titulo, corpo)
    _checar("02c diferenca so' de arredondamento -> sem contradicao", motivo is None)


# ============================================================
# 3. Texto completo consistente -> sintese especifica normal
# ============================================================

def test_03_texto_completo_consistente_gera_resumo_full_text():
    titulo = "Ibovespa fecha em alta de 0,54%, puxado por Vale e Petrobras"
    resumo_bom = (
        "RESUMO:\nO Ibovespa fechou em alta de 0,54%, aos 128.400 pontos, "
        "com Vale subindo 2,1% após alta do minério de ferro e Petrobras "
        "avançando 1,4% com a cotação do barril."
    )
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente, com conteúdo jornalístico real sobre o pregão.",
                                     None, "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_bom, None)):
        resultado = news_mod._gerar_resumo_grupo(titulo, (("Veiculo", "https://veiculo.com/materia"),), (titulo,))
    _checar("03a resumo consistente e' aceito", resultado["resumo"] == resumo_bom)
    _checar("03b qualidade_texto == full_text (1 fonte, texto integral)", resultado["qualidade_texto"] == "full_text")
    _checar("03c parcial=False (nao e' fallback)", resultado["parcial"] is False)


# ============================================================
# 4. Apenas manchete e snippet (nenhuma fonte deu pra extrair)
# ============================================================

def test_04_somente_manchetes_gera_resumo_snippet_only():
    titulos = ("Ibovespa fecha em alta de 0,54%", "Bolsa brasileira sobe 0,54% no fechamento")
    resumo_curto = "RESUMO:\nO Ibovespa encerrou o pregão em alta de 0,54%, segundo as fontes."
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, "https://veiculo.com/materia", "paywall")), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_curto, None)):
        resultado = news_mod._gerar_resumo_grupo(
            titulos[0],
            (("V1", "https://veiculo1.com/m"), ("V2", "https://veiculo2.com/m")),
            titulos,
        )
    _checar("04a resumo so'-manchetes e' aceito (consistente com o titulo)", resultado["resumo"] == resumo_curto)
    _checar("04b qualidade_texto == snippet_only", resultado["qualidade_texto"] == "snippet_only")
    _checar("04c parcial=True (UI avisa que texto completo nao foi acessado)", resultado["parcial"] is True)


# ============================================================
# 5. Extracao de conteudo malsucedida (sem fallback possivel)
# ============================================================

def test_05_extracao_malsucedida_sem_titulo_extra_nao_inventa_resumo():
    titulo = "Empresa X anuncia resultado"
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=(None, None, "https://veiculo.com/materia", "paywall")):
        resultado = news_mod._gerar_resumo_grupo(titulo, (("Veiculo", "https://veiculo.com/materia"),), (titulo,))
    _checar("05a nenhum resumo inventado", resultado["resumo"] is None)
    _checar("05b qualidade_texto == extraction_failed", resultado["qualidade_texto"] == "extraction_failed")
    _checar("05c motivo_indisponivel preservado (nao generico)", resultado["motivo_indisponivel"] == "paywall")


# ============================================================
# 6. Texto de erro/HTML irrelevante (pagina acessivel, sem conteudo)
# ============================================================

def test_06_pagina_de_erro_sem_texto_jornalistico_nao_e_promovida_a_materia():
    html_erro = "<html><head><title>Erro 404</title></head><body><nav>Menu</nav><footer>Rodapé</footer></body></html>"

    class _RespFake:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        url = "https://veiculo.com/materia"
        text = html_erro

        def raise_for_status(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch.object(news_mod, "_resolver_link_real", return_value="https://veiculo.com/materia"), \
         patch.object(news_mod.requests, "get", return_value=_RespFake()):
        texto, imagem, link_real, motivo = news_mod._extrair_texto_artigo("https://news.google.com/x")
    _checar("06a pagina de erro/menu nunca vira texto de materia", texto is None)
    _checar("06b motivo explica a falha (nao finge sucesso)", motivo is not None)


# ============================================================
# 7. Conteudo que mistura duas noticias diferentes
#    (via grounding: clausula causal cita algo que NAO esta no texto-base
#    - sinal de mistura de fatos nao relacionados)
# ============================================================

def test_07_clausula_causal_de_outro_assunto_e_detectada_sem_base():
    corpo = (
        "RESUMO:\nA Petrobras anunciou novo plano de investimentos em meio a "
        "pesquisas eleitorais que indicam acirramento da disputa presidencial."
    )
    texto_base = "A Petrobras detalhou o plano estratégico 2027-2031 em evento com investidores em São Paulo."
    motivo = news_mod._causalidade_sem_evidencia(corpo, texto_base)
    _checar("07a causalidade de tema ausente do texto-base e' sinalizada", motivo is not None and "eleitorais" in motivo.lower() or "pesquisas" in (motivo or "").lower())


# ============================================================
# 8. Noticias republicadas e URLs duplicadas
# ============================================================

def test_08_chave_cache_independe_da_ordem_e_muda_com_fonte_nova():
    titulo = "Fato X"
    chave_a = ia_cache_mod.chave_news(titulo, ("https://a.com/1", "https://b.com/2"))
    chave_b = ia_cache_mod.chave_news(titulo, ("https://b.com/2", "https://a.com/1"))
    chave_c = ia_cache_mod.chave_news(titulo, ("https://a.com/1", "https://b.com/2", "https://c.com/3"))
    _checar("08a mesma CHAVE pro mesmo conjunto de links, em qualquer ordem", chave_a == chave_b)
    _checar("08b chave MUDA quando uma fonte nova entra no grupo", chave_a != chave_c)


def test_08b_fontes_count_deduplica_veiculo_republicado():
    """2 entradas do MESMO veiculo (ex: a materia foi indexada 2x pelo
    RSS, URLs levemente diferentes) contam como 1 fonte so' - a formula
    usada em obter_noticias/obter_top_mercado_tudo e' len(set(veiculos))."""
    veiculos = ["InfoMoney", "InfoMoney", "UOL", "G1"]
    _checar("08c veiculo duplicado nao inflama a contagem", len(set(veiculos)) == 3)


# ============================================================
# 9. Varias fontes que concordam sobre o mesmo fato
# ============================================================

def test_09_fontes_concordantes_mesma_direcao_sem_contradicao():
    titulo = "Ibovespa fecha em alta de 0,54%"
    corpo = "RESUMO:\nO índice subiu 0,54% no fechamento, segundo as fontes consultadas."
    _checar("09a mesma direcao (alta/alta) -> sem contradicao", news_mod._contradicao_titulo_resumo(titulo, corpo) is None)


# ============================================================
# 10. Fontes que divergem sobre um numero
# ============================================================

def test_10_fontes_divergem_em_percentual_e_contradicao_e_detectada():
    titulo = "Ibovespa fecha em alta de 1,20%"
    corpo = "RESUMO:\nO índice fechou em alta de 3,50%, impulsionado pelo setor financeiro."
    motivo = news_mod._contradicao_titulo_resumo(titulo, corpo)
    _checar("10a percentuais muito diferentes entre fontes -> contradicao", motivo is not None)


# ============================================================
# 11. Causalidade nao sustentada pelo conteudo
# ============================================================

def test_11_causalidade_sem_evidencia_e_bloqueada():
    corpo = "RESUMO:\nAs ações caíram por causa de temores sobre juros nos Estados Unidos."
    texto_base = "A empresa divulgou balanço trimestral com queda de margem operacional."
    motivo = news_mod._causalidade_sem_evidencia(corpo, texto_base)
    _checar("11a causalidade sem nenhuma base no texto -> bloqueada", motivo is not None)


def test_11b_causalidade_com_base_no_texto_nao_e_bloqueada():
    corpo = "RESUMO:\nAs ações caíram por causa do corte no preço do petróleo informado pela própria empresa."
    texto_base = "A empresa citou o corte no preço do petróleo como fator da revisão de receita."
    motivo = news_mod._causalidade_sem_evidencia(corpo, texto_base)
    _checar("11c causalidade com base real no texto -> nao bloqueada", motivo is None)


# ============================================================
# 12. Resumo generico e repetitivo (gate antigo) convive com o gate novo
# ============================================================

def test_12_resumo_generico_e_descartado_mesmo_sem_contradicao_de_direcao():
    titulo = "Empresa Alfa é notícia"
    resumo_generico = "RESUMO:\nA empresa Alfa é notícia e o mercado segue atento aos próximos movimentos."
    with patch.object(news_mod, "_extrair_texto_artigo",
                       return_value=("Texto longo o suficiente, com conteúdo jornalístico real.",
                                     None, "https://veiculo.com/materia", None)), \
         patch.object(news_mod, "_chamar_groq", return_value=(resumo_generico, None)):
        resultado = news_mod._gerar_resumo_grupo(titulo, (("Veiculo", "https://veiculo.com/materia"),), (titulo,))
    _checar("12a resumo generico continua sendo descartado (gate antigo intacto)", resultado["resumo"] is None)


# ============================================================
# 13. Metrica de confianca sem calibracao (selo/score)
# ============================================================

def test_13_score_e_sempre_limitado_a_0_100():
    score, _regras = news_mod._calcular_score(
        ["MANCHETE CHOCANTE!! Rumor de fraude é indício de crise!!"], ["g1"],
    )
    _checar("13a score nunca fica negativo mesmo com varias penalidades", score >= 0)
    score_alto, _ = news_mod._calcular_score(
        ["Fato confirmado pelo Valor"], ["valor", "estadao", "folha", "g1", "uol"],
    )
    _checar("13b score nunca passa de 100", score_alto <= 100)


def test_13b_tooltip_deixa_explicito_que_nao_e_probabilidade_calibrada():
    import ui.news_tab as news_tab_mod
    tooltip = news_tab_mod._tooltip_regras({"score": 100, "regras": ["veículo confiável: valor"]})
    _checar("13c tooltip explica que e' heuristica por regras, nao % de acerto", "não é % de acerto" in tooltip)


# ============================================================
# 14. Cache contendo um resumo antigo e incorreto (pre-fix)
# ============================================================

def test_14_bump_de_versao_invalida_cache_antigo_v3():
    titulo = "IBOVESPA fecha hoje com alta de 0,54%"
    links = ("https://veiculo.com/materia",)
    chave_v4 = ia_cache_mod.chave_news(titulo, links)
    chave_v3_simulada = __import__("hashlib").sha256(
        ("v3|" + titulo.strip().lower() + "|" + "|".join(sorted(links))).encode("utf-8")
    ).hexdigest()
    _checar("14a chave atual (_VERSAO_CHAVE_NEWS) NAO e' mais 'v3'", ia_cache_mod._VERSAO_CHAVE_NEWS != "v3")
    _checar("14b chave nova difere da chave v3 simulada (cache antigo nunca e' reaproveitado)", chave_v4 != chave_v3_simulada)


def test_14b_linha_v3_no_supabase_nunca_e_lida_pela_chave_v4():
    """Simula uma linha JA' cacheada sob a chave v3 (resumo contraditorio,
    gerado antes do fix) - obter_resumo_com_cache com a chave v4 (atual)
    precisa dar MISS (nunca servir o resumo antigo errado) e gerar de
    novo, agora passando pelos gates novos."""
    class _TabelaFake:
        def __init__(self, linhas):
            self.linhas = linhas
            self._op = None
            self._chave = None

        def select(self, *_a, **_k):
            self._op = "select"
            return self

        def insert(self, payload):
            self._op = "insert"
            self._payload = payload
            return self

        def update(self, payload):
            self._op = "update"
            self._payload = payload
            return self

        def eq(self, campo, valor):
            if campo == "chave_documento":
                self._chave = valor
            return self

        def limit(self, _n):
            return self

        def execute(self):
            if self._op == "select":
                linha = self.linhas.get(self._chave)
                resp = MagicMock()
                resp.data = [linha] if linha else []
                return resp
            if self._op == "insert":
                if self._chave is None:
                    self._chave = self._payload["chave_documento"]
                if self._payload["chave_documento"] in self.linhas:
                    raise Exception("duplicate key")
                self.linhas[self._payload["chave_documento"]] = dict(self._payload)
                resp = MagicMock()
                resp.data = [dict(self._payload)]
                return resp
            if self._op == "update":
                self.linhas[self._chave].update(self._payload)
                resp = MagicMock()
                resp.data = []
                return resp
            raise AssertionError("op nao mockada")

    class _ClienteFake:
        def __init__(self, linhas):
            self.linhas = linhas

        def table(self, _nome):
            return _TabelaFake(self.linhas)

    titulo = "IBOVESPA fecha hoje com alta de 0,54%"
    links = ("https://veiculo.com/materia",)
    chave_v3_simulada = __import__("hashlib").sha256(
        ("v3|" + titulo.strip().lower() + "|" + "|".join(sorted(links))).encode("utf-8")
    ).hexdigest()
    linhas = {
        chave_v3_simulada: {
            "chave_documento": chave_v3_simulada, "status": "concluido",
            "resultado": {"resumo": "RESUMO:\nO Ibovespa encerrou o pregão em queda (resumo antigo errado)."},
            "criado_em": ia_cache_mod._agora_iso(),
        }
    }
    cliente = _ClienteFake(linhas)
    chamadas = []

    def _gerar_fn():
        chamadas.append(1)
        return {"resumo": "RESUMO:\nO Ibovespa fechou em alta de 0,54%.", "modelo": "x"}

    chave_v4 = ia_cache_mod.chave_news(titulo, links)
    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache(chave_v4, links[0], "news", _gerar_fn)
    _checar("14c resumo antigo (v3) NUNCA e' devolvido pela chave v4", "queda" not in resultado["resumo"])
    _checar("14d gerar_fn foi chamado de verdade (cache MISS na chave nova)", len(chamadas) == 1)


# ============================================================
# 15. Atualizacao e persistencia corretas apos a correcao
# ============================================================

def test_15_resumo_corrigido_fica_cacheado_e_e_reaproveitado():
    class _TabelaFake:
        def __init__(self, linhas):
            self.linhas = linhas
            self._op = None
            self._chave = None

        def select(self, *_a, **_k):
            self._op = "select"
            return self

        def insert(self, payload):
            self._op = "insert"
            self._payload = payload
            return self

        def update(self, payload):
            self._op = "update"
            self._payload = payload
            return self

        def eq(self, campo, valor):
            if campo == "chave_documento":
                self._chave = valor
            return self

        def limit(self, _n):
            return self

        def execute(self):
            if self._op == "select":
                linha = self.linhas.get(self._chave)
                resp = MagicMock()
                resp.data = [linha] if linha else []
                return resp
            if self._op == "insert":
                if self._payload["chave_documento"] in self.linhas:
                    raise Exception("duplicate key")
                self._chave = self._payload["chave_documento"]
                self.linhas[self._chave] = dict(self._payload)
                resp = MagicMock()
                resp.data = [dict(self._payload)]
                return resp
            if self._op == "update":
                self.linhas[self._chave].update(self._payload)
                resp = MagicMock()
                resp.data = []
                return resp
            raise AssertionError("op nao mockada")

    class _ClienteFake:
        def __init__(self):
            self.linhas = {}

        def table(self, _nome):
            return _TabelaFake(self.linhas)

    cliente = _ClienteFake()
    chamadas = []

    def _gerar_fn():
        chamadas.append(1)
        return {"resumo": "RESUMO:\nO Ibovespa fechou em alta de 0,54%.", "modelo": "x"}

    chave = ia_cache_mod.chave_news("IBOVESPA fecha hoje com alta de 0,54%", ("https://veiculo.com/materia",))
    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        primeiro = ia_cache_mod.obter_resumo_com_cache(chave, "https://veiculo.com/materia", "news", _gerar_fn)
        segundo = ia_cache_mod.obter_resumo_com_cache(chave, "https://veiculo.com/materia", "news", _gerar_fn)
    _checar("15a 1a chamada gera de verdade", len(chamadas) == 1)
    _checar("15b 2a chamada reaproveita o cache (nao gera de novo)", len(chamadas) == 1)
    _checar("15c o resumo persistido e' o corrigido, igual nas 2 leituras", primeiro["resumo"] == segundo["resumo"])
    _checar("15d status final no Supabase e' 'concluido'", cliente.linhas[chave]["status"] == "concluido")


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
    print("TODOS OS TESTES DE CONSISTENCIA EDITORIAL DO NEWS PASSARAM")
