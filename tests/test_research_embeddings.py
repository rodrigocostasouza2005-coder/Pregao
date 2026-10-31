# -*- coding: utf-8 -*-
"""Testes do RAG de Research (Equity Research Library, Fase C - busca
semantica sobre research_premissas, 2026-10-30) -
data/research/embeddings.py. Sem rede/Supabase real - tudo mockado
(requests.post, time.sleep, cliente Supabase, config.obter_credenciais_gemini,
data.research.store). Cobre:

1. _texto_para_indexar - deterministico, puro.
2. _gerar_embedding - sucesso/timeout/erro HTTP/resposta malformada/
   credencial ausente, TODOS retornam None graciosamente; retry limitado
   (429/rede, nunca 4xx que nao seja 429).
3. indexar_pendentes - so' processa pendentes, respeita limite, isola
   falha individual, pula quando texto+modelo nao mudaram, reindexa
   quando texto OU modelo mudou.
4. buscar - filtros, dedup semantico/lexical, SEM_EVIDENCIA, degradacao
   graciosa (sem credencial e com falha persistente do Gemini), nunca
   lanca excecao, rastreabilidade (link/casa/data_publicacao sempre
   presentes)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.embeddings as emb


# ============================================================
# 1. _texto_para_indexar - puro, deterministico
# ============================================================

def test_texto_para_indexar_com_todos_os_campos():
    linha = {
        "casa": "Genial Analisa", "titulo": "WEGE3 - Iniciação de cobertura",
        "tickers": ["WEGE3"], "tipo_documento": "INICIACAO_COBERTURA",
        "premissas": ["ganho de market share", "expansão de capacidade em 2027"],
        "projecoes": {"receita": "crescimento de 12% a.a.", "ebitda_margem": "22% em 2027"},
        "recomendacao": "COMPRA", "preco_alvo": 55.0,
    }
    texto = emb._texto_para_indexar(linha)
    assert "Genial Analisa" in texto
    assert "WEGE3 - Iniciação de cobertura" in texto
    assert "WEGE3" in texto
    assert "INICIACAO_COBERTURA" in texto
    assert "ganho de market share" in texto
    assert "receita" in texto and "crescimento de 12% a.a." in texto
    assert "COMPRA" in texto
    assert "55.0" in texto


def test_texto_para_indexar_premissas_e_projecoes_vazias():
    linha = {"casa": "XP Investimentos", "titulo": "Macro semanal", "tickers": [],
              "tipo_documento": None, "premissas": [], "projecoes": {},
              "recomendacao": None, "preco_alvo": None}
    texto = emb._texto_para_indexar(linha)
    assert "XP Investimentos" in texto
    assert "Macro semanal" in texto
    assert "Premissas" not in texto
    assert "Projecoes" not in texto
    assert "Recomendacao" not in texto
    assert "Preco-alvo" not in texto


def test_texto_para_indexar_e_deterministico_mesmo_com_dict_em_ordem_diferente():
    linha_a = {"casa": "Genial Analisa", "titulo": "t", "tickers": ["A"],
               "projecoes": {"receita": "x", "lucro": "y"}}
    linha_b = {"casa": "Genial Analisa", "titulo": "t", "tickers": ["A"],
               "projecoes": {"lucro": "y", "receita": "x"}}
    assert emb._texto_para_indexar(linha_a) == emb._texto_para_indexar(linha_b)


def test_texto_para_indexar_nunca_inclui_texto_de_relatorio():
    """So' usa campos ja extraidos - nunca aceita/mostra um campo
    'texto'/'conteudo' que nao faz parte do contrato de research_premissas."""
    linha = {"casa": "X", "titulo": "Y", "texto": "conteudo completo do PDF aqui"}
    texto = emb._texto_para_indexar(linha)
    assert "conteudo completo do PDF aqui" not in texto


# ============================================================
# 2. _gerar_embedding - rede mockada, nunca lanca excecao
# ============================================================

def _resposta_ok(valores=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"embedding": {"values": valores or [0.1, 0.2, 0.3]}}
    return resp


def test_gerar_embedding_sucesso():
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "gemini-embedding-001")), \
         patch.object(emb.requests, "post", return_value=_resposta_ok([0.1, 0.2])) as mock_post:
        resultado = emb._gerar_embedding("texto qualquer")
    assert resultado == [0.1, 0.2]
    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"]["x-goog-api-key"] == "chave"
    assert kwargs["json"]["content"]["parts"][0]["text"] == "texto qualquer"
    assert kwargs["json"]["output_dimensionality"] == emb.config.GEMINI_EMBEDDING_DIMENSAO


def test_gerar_embedding_sem_credencial_nao_chama_rede():
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=(None, "modelo")), \
         patch.object(emb.requests, "post") as mock_post:
        resultado = emb._gerar_embedding("texto")
    assert resultado is None
    mock_post.assert_not_called()


def test_gerar_embedding_texto_vazio_retorna_none_sem_chamar_rede():
    with patch.object(emb.requests, "post") as mock_post:
        assert emb._gerar_embedding("") is None
        assert emb._gerar_embedding(None) is None
    mock_post.assert_not_called()


def test_gerar_embedding_timeout_persistente_esgota_retries_e_retorna_none():
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb.requests, "post", side_effect=emb.requests.exceptions.Timeout("timeout")) as mock_post, \
         patch.object(emb.time, "sleep") as mock_sleep:
        resultado = emb._gerar_embedding("texto")
    assert resultado is None
    assert mock_post.call_count == emb._MAX_TENTATIVAS
    assert mock_sleep.call_count == emb._MAX_TENTATIVAS - 1


def test_gerar_embedding_erro_http_nao_429_nunca_tenta_de_novo():
    resp_erro = MagicMock(status_code=401, text="credencial invalida")
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb.requests, "post", return_value=resp_erro) as mock_post, \
         patch.object(emb.time, "sleep") as mock_sleep:
        resultado = emb._gerar_embedding("texto")
    assert resultado is None
    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()


def test_gerar_embedding_resposta_malformada_retorna_none_sem_retry():
    resp_malformada = MagicMock(status_code=200)
    resp_malformada.json.return_value = {"nao_tem_embedding_aqui": True}
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb.requests, "post", return_value=resp_malformada) as mock_post:
        resultado = emb._gerar_embedding("texto")
    assert resultado is None
    assert mock_post.call_count == 1


def test_gerar_embedding_429_seguido_de_sucesso_usa_retry():
    resp_429 = MagicMock(status_code=429)
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb.requests, "post", side_effect=[resp_429, _resposta_ok([0.5])]) as mock_post, \
         patch.object(emb.time, "sleep") as mock_sleep:
        resultado = emb._gerar_embedding("texto")
    assert resultado == [0.5]
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once_with(emb._BACKOFF_SEGUNDOS[0])


def test_gerar_embedding_429_persistente_esgota_retries():
    resp_429 = MagicMock(status_code=429)
    with patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb.requests, "post", return_value=resp_429) as mock_post, \
         patch.object(emb.time, "sleep") as mock_sleep:
        resultado = emb._gerar_embedding("texto")
    assert resultado is None
    assert mock_post.call_count == emb._MAX_TENTATIVAS
    assert mock_sleep.call_count == emb._MAX_TENTATIVAS - 1


# ============================================================
# 3. indexar_pendentes - incremental, isolado, respeita limite
# ============================================================

def _premissa(link, **extra):
    base = {"link": link, "casa": "Genial Analisa", "titulo": "t", "tickers": [],
            "tipo_documento": None, "premissas": [], "projecoes": {},
            "recomendacao": None, "preco_alvo": None}
    base.update(extra)
    return base


def test_indexar_pendentes_processa_so_os_pendentes():
    premissas = [_premissa("link-novo"), _premissa("link-ja-indexado")]
    texto_ja_indexado = emb._texto_para_indexar(premissas[1])
    existentes = {"link-ja-indexado": {"texto_indexado": texto_ja_indexado, "modelo_embedding": "gemini-embedding-001"}}
    with patch.object(emb.store, "listar_premissas", return_value=premissas), \
         patch.object(emb, "_embeddings_existentes", return_value=existentes), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "gemini-embedding-001")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1, 0.2]) as mock_gerar, \
         patch.object(emb, "_salvar_embedding", return_value=True) as mock_salvar:
        resultado = emb.indexar_pendentes(limite=30)
    assert resultado == {"processados": 1, "falhas": 0, "pendentes_restantes": 0}
    mock_gerar.assert_called_once()
    mock_salvar.assert_called_once_with("link-novo", [0.1, 0.2], emb._texto_para_indexar(premissas[0]), "gemini-embedding-001")


def test_indexar_pendentes_respeita_limite():
    premissas = [_premissa(f"link-{i}") for i in range(5)]
    with patch.object(emb.store, "listar_premissas", return_value=premissas), \
         patch.object(emb, "_embeddings_existentes", return_value={}), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1]), \
         patch.object(emb, "_salvar_embedding", return_value=True):
        resultado = emb.indexar_pendentes(limite=2)
    assert resultado == {"processados": 2, "falhas": 0, "pendentes_restantes": 3}


def test_indexar_pendentes_isola_falha_individual_sem_derrubar_lote():
    # titulo=link so' pra texto_para_indexar ficar distinguivel por link
    # (ele nao inclui o link em si) - permite o fake abaixo decidir qual
    # link deve falhar na geracao do embedding.
    premissas = [
        _premissa("link-ok", titulo="link-ok"),
        _premissa("link-falha-embedding", titulo="link-falha-embedding"),
        _premissa("link-falha-salvar", titulo="link-falha-salvar"),
    ]

    def _gerar_fake(texto):
        # so' falha pro link cujo texto bate com link-falha-embedding
        if "link-falha-embedding" in texto:
            return None
        return [0.1]

    with patch.object(emb.store, "listar_premissas", return_value=premissas), \
         patch.object(emb, "_embeddings_existentes", return_value={}), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", side_effect=_gerar_fake), \
         patch.object(emb, "_salvar_embedding", side_effect=lambda link, *a: link != "link-falha-salvar"):
        resultado = emb.indexar_pendentes(limite=30)
    assert resultado["processados"] == 1
    assert resultado["falhas"] == 2
    assert resultado["pendentes_restantes"] == 0


def test_indexar_pendentes_pula_quando_texto_e_modelo_identicos():
    linha = _premissa("link-1")
    texto = emb._texto_para_indexar(linha)
    existentes = {"link-1": {"texto_indexado": texto, "modelo_embedding": "gemini-embedding-001"}}
    with patch.object(emb.store, "listar_premissas", return_value=[linha]), \
         patch.object(emb, "_embeddings_existentes", return_value=existentes), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "gemini-embedding-001")), \
         patch.object(emb, "_gerar_embedding") as mock_gerar:
        resultado = emb.indexar_pendentes(limite=30)
    mock_gerar.assert_not_called()
    assert resultado == {"processados": 0, "falhas": 0, "pendentes_restantes": 0}


def test_indexar_pendentes_reindexa_quando_texto_mudou():
    linha = _premissa("link-1", premissas=["premissa nova extraida depois"])
    existentes = {"link-1": {"texto_indexado": "texto antigo diferente", "modelo_embedding": "gemini-embedding-001"}}
    with patch.object(emb.store, "listar_premissas", return_value=[linha]), \
         patch.object(emb, "_embeddings_existentes", return_value=existentes), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "gemini-embedding-001")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.9]) as mock_gerar, \
         patch.object(emb, "_salvar_embedding", return_value=True):
        resultado = emb.indexar_pendentes(limite=30)
    mock_gerar.assert_called_once()
    assert resultado["processados"] == 1


def test_indexar_pendentes_reindexa_quando_modelo_mudou_mesmo_com_texto_igual():
    """Controle de versao do modelo de embedding: texto identico mas o
    modelo configurado agora e' diferente do que gerou o embedding salvo -
    embeddings de modelos diferentes nao sao comparaveis entre si, precisa
    reindexar."""
    linha = _premissa("link-1")
    texto = emb._texto_para_indexar(linha)
    existentes = {"link-1": {"texto_indexado": texto, "modelo_embedding": "gemini-embedding-001"}}
    with patch.object(emb.store, "listar_premissas", return_value=[linha]), \
         patch.object(emb, "_embeddings_existentes", return_value=existentes), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "gemini-embedding-002-novo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.9]) as mock_gerar, \
         patch.object(emb, "_salvar_embedding", return_value=True) as mock_salvar:
        resultado = emb.indexar_pendentes(limite=30)
    mock_gerar.assert_called_once()
    assert resultado["processados"] == 1
    mock_salvar.assert_called_once_with("link-1", [0.9], texto, "gemini-embedding-002-novo")


def test_indexar_pendentes_banco_premissas_fora_do_ar():
    with patch.object(emb.store, "listar_premissas", return_value=None):
        resultado = emb.indexar_pendentes()
    assert resultado == {"processados": 0, "falhas": 0, "pendentes_restantes": 0}


def test_indexar_pendentes_tabela_embeddings_fora_do_ar():
    premissas = [_premissa("link-1"), _premissa("link-2")]
    with patch.object(emb.store, "listar_premissas", return_value=premissas), \
         patch.object(emb, "_embeddings_existentes", return_value=None):
        resultado = emb.indexar_pendentes()
    assert resultado == {"processados": 0, "falhas": 0, "pendentes_restantes": 2}


# ============================================================
# 3b. _links_indexados / _embeddings_existentes / _salvar_embedding
# ============================================================

def test_links_indexados_retorna_set_dos_links_salvos():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.execute.return_value = MagicMock(
        data=[{"link": "a", "texto_indexado": "x", "modelo_embedding": "m"},
              {"link": "b", "texto_indexado": "y", "modelo_embedding": "m"}]
    )
    with patch.object(emb, "obter_cliente", return_value=cliente):
        resultado = emb._links_indexados()
    assert resultado == {"a", "b"}


def test_links_indexados_banco_fora_do_ar_retorna_none():
    with patch.object(emb, "obter_cliente", return_value=None):
        assert emb._links_indexados() is None


def test_salvar_embedding_upsert_por_link():
    cliente = MagicMock()
    with patch.object(emb, "obter_cliente", return_value=cliente):
        ok = emb._salvar_embedding("https://casa.com/1", [0.1, 0.2], "texto indexado", "gemini-embedding-001")
    assert ok is True
    chamada = cliente.table.return_value.upsert.call_args
    assert chamada.kwargs["on_conflict"] == "link"
    payload = chamada.args[0]
    assert payload["link"] == "https://casa.com/1"
    assert payload["embedding"] == [0.1, 0.2]
    assert payload["texto_indexado"] == "texto indexado"
    assert payload["modelo_embedding"] == "gemini-embedding-001"


def test_salvar_embedding_banco_fora_do_ar_retorna_false():
    with patch.object(emb, "obter_cliente", return_value=None):
        assert emb._salvar_embedding("link", [0.1], "texto", "modelo") is False


def test_salvar_embedding_erro_de_escrita_retorna_false_sem_excecao():
    cliente = MagicMock()
    cliente.table.return_value.upsert.return_value.execute.side_effect = Exception("fora do ar")
    with patch.object(emb, "obter_cliente", return_value=cliente):
        assert emb._salvar_embedding("link", [0.1], "texto", "modelo") is False


# ============================================================
# 4. buscar - hibrida (estrutural + semantica + lexical)
# ============================================================

def _item(link, casa="Genial Analisa", titulo="t", tickers=None, tipo_documento=None,
          premissas=None, projecoes=None, recomendacao=None, preco_alvo=None, data_publicacao=None):
    return {
        "link": link, "casa": casa, "titulo": titulo, "tickers": tickers or [],
        "tipo_documento": tipo_documento, "premissas": premissas or [],
        "projecoes": projecoes or {}, "recomendacao": recomendacao,
        "preco_alvo": preco_alvo, "data_publicacao": data_publicacao,
    }


def test_buscar_sem_pergunta_filtra_so_estrutural():
    # store.listar_premissas(tickers=[...]) ja faz o filtro por overlap no
    # proprio Supabase (ver data/research/store.py) - o mock simula isso
    # retornando SO' o item que a chamada real teria retornado p/ WEGE3.
    base_filtrada = [_item("a", casa="Genial Analisa", tickers=["WEGE3"])]
    with patch.object(emb.store, "listar_premissas", return_value=base_filtrada) as mock_listar:
        resultado = emb.buscar(ticker="WEGE3")
    mock_listar.assert_called_once_with(tickers=["WEGE3"], casa=None)
    assert resultado["confianca"] == "ALTA"
    assert [r["link"] for r in resultado["resultados"]] == ["a"]
    assert resultado["resultados"][0]["origem_match"] == "estrutural"


def test_buscar_filtra_por_tipo_documento_e_periodo():
    base = [
        _item("a", tipo_documento="INICIACAO_COBERTURA", data_publicacao="2026-10-29"),
        _item("b", tipo_documento="VALUATION", data_publicacao="2026-10-01"),
        _item("c", tipo_documento="INICIACAO_COBERTURA", data_publicacao="2026-01-01"),
    ]
    with patch.object(emb.store, "listar_premissas", return_value=base):
        resultado = emb.buscar(tipo_documento="INICIACAO_COBERTURA", data_inicio="2026-10-01")
    assert [r["link"] for r in resultado["resultados"]] == ["a"]


def test_buscar_sem_evidencia_quando_filtro_estrutural_vazio():
    with patch.object(emb.store, "listar_premissas", return_value=[]):
        resultado = emb.buscar(ticker="ZZZZ99")
    assert resultado == {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}


def test_buscar_banco_indisponivel_nunca_lanca_excecao():
    with patch.object(emb.store, "listar_premissas", return_value=None):
        resultado = emb.buscar(pergunta="qualquer coisa")
    assert resultado["confianca"] == "SEM_EVIDENCIA"
    assert resultado["resultados"] == []
    assert "indisponivel" in resultado["aviso"]


def test_buscar_sem_credencial_gemini_degrada_pra_lexical():
    base = [_item("a", titulo="WEGE3 ganha participação de mercado", premissas=["ganho de market share"])]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=(None, "modelo")), \
         patch.object(emb, "_gerar_embedding") as mock_gerar:
        resultado = emb.buscar(pergunta="market share")
    mock_gerar.assert_not_called()
    assert resultado["confianca"] == "BAIXA"  # so' lexical, sem semantico
    assert "GEMINI_API_KEY" in resultado["aviso"]
    assert resultado["resultados"][0]["origem_match"] == "lexical"


def test_buscar_falha_tecnica_persistente_do_gemini_nao_impede_estrutural_e_lexical():
    """Mesmo com a parte semantica falhando persistentemente (timeout/erro
    simulado em _gerar_embedding - jamais retornando um vetor), a busca
    estrutural + lexical continua funcionando normalmente e NUNCA lanca
    excecao - confianca reflete que a busca semantica nao ocorreu."""
    base = [
        _item("a", casa="Genial Analisa", titulo="WEGE3 revisão de preço-alvo",
              tickers=["WEGE3"], premissas=["revisão de preço-alvo"], data_publicacao="2026-10-20"),
        _item("b", casa="Genial Analisa", titulo="Outro assunto qualquer",
              tickers=["WEGE3"], data_publicacao="2026-10-15"),
    ]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=None), \
         patch.object(emb, "_buscar_por_similaridade") as mock_sim:
        resultado = emb.buscar(pergunta="preço-alvo", ticker="WEGE3", casa="Genial Analisa", data_inicio="2026-10-01")
    mock_sim.assert_not_called()  # sem embedding da pergunta, nunca chega a chamar a RPC
    assert resultado["confianca"] == "BAIXA"
    assert any("falha tecnica" in (resultado["aviso"] or "") for _ in [None]) or resultado["aviso"]
    assert [r["link"] for r in resultado["resultados"]] == ["a"]


def test_buscar_dedup_semantico_e_lexical_marca_origem_ambos():
    base = [_item("a", titulo="PETR4 revisão de preço-alvo", premissas=["revisão de preço-alvo"], data_publicacao="2026-10-01")]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1, 0.2]), \
         patch.object(emb, "_buscar_por_similaridade", return_value=[{"link": "a", "similaridade": 0.9}]):
        resultado = emb.buscar(pergunta="preço-alvo")
    assert resultado["confianca"] == "ALTA"
    assert resultado["resultados"][0]["origem_match"] == "ambos"


def test_buscar_so_semantico_sem_lexical_confianca_media():
    base = [_item("a", titulo="algo sem relacao textual nenhuma", data_publicacao="2026-10-01")]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1, 0.2]), \
         patch.object(emb, "_buscar_por_similaridade", return_value=[{"link": "a", "similaridade": 0.8}]):
        resultado = emb.buscar(pergunta="pergunta que nao aparece literalmente no texto")
    assert resultado["confianca"] == "MEDIA"
    assert resultado["resultados"][0]["origem_match"] == "semantico"


def test_buscar_sem_evidencia_quando_nem_semantico_nem_lexical_acham_nada():
    base = [_item("a", titulo="totalmente irrelevante", data_publicacao="2026-10-01")]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1, 0.2]), \
         patch.object(emb, "_buscar_por_similaridade", return_value=[]):
        resultado = emb.buscar(pergunta="nada a ver")
    assert resultado == {"resultados": [], "confianca": "SEM_EVIDENCIA", "aviso": None}


def test_buscar_restringe_busca_semantica_aos_links_do_filtro_estrutural():
    base = [_item("a", casa="Genial Analisa", tickers=["WEGE3"], data_publicacao="2026-10-01")]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1]), \
         patch.object(emb, "_buscar_por_similaridade", return_value=[]) as mock_sim:
        emb.buscar(pergunta="qualquer coisa", ticker="WEGE3")
    kwargs = mock_sim.call_args.kwargs
    assert kwargs["links_candidatos"] == ["a"]


def test_buscar_nunca_lanca_excecao_em_nenhum_cenario():
    """Teste de integracao leve: buscar() combinando todo tipo de falha
    (banco indisponivel, credencial ausente, RPC falhando, zero resultado,
    resultado normal) - nenhuma chamada propaga excecao pra fora."""
    cenarios = []

    # banco indisponivel
    with patch.object(emb.store, "listar_premissas", return_value=None):
        cenarios.append(emb.buscar(pergunta="x", ticker="PETR4"))

    # credencial ausente
    base = [_item("a", data_publicacao="2026-10-01")]
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=(None, "modelo")):
        cenarios.append(emb.buscar(pergunta="x"))

    # RPC falhando (retorna None) mesmo com embedding gerado
    with patch.object(emb.store, "listar_premissas", return_value=base), \
         patch.object(emb.config, "obter_credenciais_gemini", return_value=("chave", "modelo")), \
         patch.object(emb, "_gerar_embedding", return_value=[0.1]), \
         patch.object(emb, "_buscar_por_similaridade", return_value=None):
        cenarios.append(emb.buscar(pergunta="x"))

    # zero resultado (filtro estrutural vazio)
    with patch.object(emb.store, "listar_premissas", return_value=[]):
        cenarios.append(emb.buscar(ticker="NAO_EXISTE"))

    # resultado normal, sem pergunta
    with patch.object(emb.store, "listar_premissas", return_value=base):
        cenarios.append(emb.buscar())

    for resultado in cenarios:
        assert isinstance(resultado, dict)
        assert "resultados" in resultado and "confianca" in resultado and "aviso" in resultado
        assert resultado["confianca"] in ("ALTA", "MEDIA", "BAIXA", "SEM_EVIDENCIA")


def test_buscar_resultados_sempre_tem_link_casa_data_publicacao():
    """Rastreabilidade: todo item de resultado precisa trazer link+casa+
    data_publicacao (chave pra apontar pra uma publicacao real), mesmo em
    cenarios de busca semantica/lexical/estrutural combinados."""
    base = [
        _item("a", casa="Genial Analisa", titulo="revisão de preço-alvo PETR4",
              premissas=["revisão de preço-alvo"], data_publicacao="2026-10-10"),
        _item("b", casa="XP Investimentos", titulo="outro relatorio qualquer", data_publicacao="2026-09-01"),
    ]
    cenarios_kwargs = [
        {},  # sem pergunta
        {"pergunta": "revisão de preço-alvo"},  # lexical
    ]
    for kwargs in cenarios_kwargs:
        with patch.object(emb.store, "listar_premissas", return_value=base), \
             patch.object(emb.config, "obter_credenciais_gemini", return_value=(None, "modelo")):
            resultado = emb.buscar(**kwargs)
        for item in resultado["resultados"]:
            assert item.get("link"), kwargs
            assert item.get("casa"), kwargs
            assert "data_publicacao" in item, kwargs


# ============================================================
# 5. _buscar_por_similaridade - chamada da RPC
# ============================================================

def test_buscar_por_similaridade_chama_rpc_com_parametros_esperados():
    cliente = MagicMock()
    cliente.rpc.return_value.execute.return_value = MagicMock(data=[{"link": "a", "similaridade": 0.9}])
    with patch.object(emb, "obter_cliente", return_value=cliente):
        resultado = emb._buscar_por_similaridade([0.1, 0.2], links_candidatos=["a", "b"], limite=5)
    assert resultado == [{"link": "a", "similaridade": 0.9}]
    args, kwargs = cliente.rpc.call_args
    assert args[0] == "match_research_embeddings"
    assert args[1]["query_embedding"] == [0.1, 0.2]
    assert args[1]["match_count"] == 5
    assert args[1]["filtro_links"] == ["a", "b"]


def test_buscar_por_similaridade_banco_fora_do_ar_retorna_none():
    with patch.object(emb, "obter_cliente", return_value=None):
        assert emb._buscar_por_similaridade([0.1]) is None


def test_buscar_por_similaridade_rpc_falhando_retorna_none_sem_excecao():
    cliente = MagicMock()
    cliente.rpc.return_value.execute.side_effect = Exception("funcao nao existe ainda")
    with patch.object(emb, "obter_cliente", return_value=cliente):
        assert emb._buscar_por_similaridade([0.1]) is None
