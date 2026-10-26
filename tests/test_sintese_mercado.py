# -*- coding: utf-8 -*-
"""data/sintese_mercado.py (ANALISTA DE MERCADO): síntese executiva via
IA sobre fatos já coletados pelo Pregão. Cobre: geração com sucesso,
validação/limpeza de resposta malformada da IA, fallback de modelo
(mesmo padrão de resumir.py), fallback pra última síntese válida quando
a geração atual falha, indisponibilidade total quando nunca houve
síntese válida, e que a falha de UMA fonte de fatos não derruba as
demais (sempre aparece em fontes_indisponiveis, nunca propaga
exceção)."""
import json
from unittest.mock import patch

from data import sintese_mercado as sm

_JSON_VALIDO = json.dumps({
    "resumo_executivo": {"texto": "O Ibovespa opera em alta, acompanhando o exterior.", "ressalvas": ""},
    "movimentos": [
        {"evento": "Ibovespa sobe 1,2%", "fonte": "B3 (cotação)", "data_fonte": "2026-10-26",
         "por_que_importa": "acompanha alta global", "impacto_possivel": "setores exportadores",
         "horizonte": "curto prazo", "confianca": "media", "confianca_motivo": "1 fonte"},
    ],
    "oportunidades_riscos": [
        {"ativo_ou_setor": "Petróleo", "catalisador": "alta do barril", "argumento_favoravel": "receita maior",
         "argumento_contrario": "custo de insumos", "acompanhar": "preço do Brent", "fonte": "Reuters",
         "data_fonte": "2026-10-26"},
    ],
    "o_que_nao_sabemos": ["Não há dado recente sobre o Focus Selic nesta rodada."],
})


def _fatos_minimos():
    return {"gerado_em": "2026-10-26T12:00:00+00:00", "fontes_indisponiveis": []}


def test_gerar_sintese_com_sucesso_preenche_resumo_e_dados():
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=(_JSON_VALIDO, None)):
        resultado = sm._gerar_sintese()
    assert resultado["resumo"] == "O Ibovespa opera em alta, acompanhando o exterior."
    assert resultado["modelo"] == "modelo-principal"
    assert len(resultado["dados"]["movimentos"]) == 1
    assert resultado["dados"]["movimentos"][0]["confianca"] == "media"


def test_sem_groq_api_key_nao_chama_rede_e_devolve_motivo_claro():
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=(None, "modelo-principal")), \
         patch.object(sm, "_chamar_groq") as groq_mock:
        resultado = sm._gerar_sintese()
    groq_mock.assert_not_called()
    assert resultado["resumo"] is None
    assert "GROQ_API_KEY" in resultado["motivo"]


def test_modelo_principal_falha_usa_fallback_uma_unica_vez():
    chamadas = []

    def _fake(chave, modelo, mensagens, max_tokens):
        chamadas.append(modelo)
        if modelo == "modelo-principal":
            return None, "timeout"
        return _JSON_VALIDO, None

    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", side_effect=_fake):
        resultado = sm._gerar_sintese()
    assert chamadas == ["modelo-principal", "modelo-fallback"]
    assert resultado["modelo"] == "modelo-fallback"
    assert resultado["resumo"]


def test_resposta_json_malformada_nao_quebra_e_devolve_motivo():
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=("isto não é json", None)):
        resultado = sm._gerar_sintese()
    assert resultado["resumo"] is None
    assert "formato inesperado" in resultado["motivo"]


def test_resposta_sem_resumo_executivo_e_invalidada():
    sem_resumo = json.dumps({"movimentos": [], "oportunidades_riscos": [], "o_que_nao_sabemos": []})
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=(sem_resumo, None)):
        resultado = sm._gerar_sintese()
    assert resultado["resumo"] is None


def test_item_de_movimento_sem_fonte_e_descartado_sem_invalidar_o_resto():
    payload = json.dumps({
        "resumo_executivo": {"texto": "Texto válido.", "ressalvas": ""},
        "movimentos": [
            {"evento": "sem fonte nenhuma"},
            {"evento": "com fonte", "fonte": "B3", "confianca": "alta"},
        ],
        "oportunidades_riscos": [],
        "o_que_nao_sabemos": [],
    })
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=(payload, None)):
        resultado = sm._gerar_sintese()
    assert len(resultado["dados"]["movimentos"]) == 1
    assert resultado["dados"]["movimentos"][0]["evento"] == "com fonte"


def test_confianca_ausente_vira_baixa_nunca_numero_inventado():
    payload = json.dumps({
        "resumo_executivo": {"texto": "Texto válido.", "ressalvas": ""},
        "movimentos": [{"evento": "evento", "fonte": "B3"}],
        "oportunidades_riscos": [], "o_que_nao_sabemos": [],
    })
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=(payload, None)):
        resultado = sm._gerar_sintese()
    assert resultado["dados"]["movimentos"][0]["confianca"] == "baixa"


def test_json_envolvido_em_markdown_e_extraido_mesmo_assim():
    envolvido = "```json\n" + _JSON_VALIDO + "\n```"
    with patch.object(sm, "_coletar_fatos", return_value=_fatos_minimos()), \
         patch.object(sm.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-principal")), \
         patch.object(sm.config, "obter_modelo_groq_fallback", return_value="modelo-fallback"), \
         patch.object(sm, "_chamar_groq", return_value=(envolvido, None)):
        resultado = sm._gerar_sintese()
    assert resultado["resumo"]


def test_uma_fonte_de_fatos_falhando_nao_derruba_as_demais():
    """_snapshot_indice tem seu proprio try/except (degradacao por
    INSTRUMENTO, mais granular que por BLOCO): quando so' uma cotacao
    falha (ex: IBOVESPA), as demais (PETR4/VALE3, que usam
    prices.obter_cotacao em vez de obter_cotacao_indice) continuam
    aparecendo com dado real em mercado_agora - a falha fica visivel
    so' no item ('erro' setado, preco/variacao None), nunca propagada
    pra fontes_indisponiveis nem pra fora do bloco inteiro. Isso e'
    estritamente melhor do que zerar mercado_agora inteiro por causa de
    1 instrumento fora do ar."""
    with patch.object(sm.prices, "obter_cotacao_indice", side_effect=RuntimeError("fora do ar")), \
         patch.object(sm.mercado, "obter_mercados_globais", return_value=[{"nome": "S&P 500", "preco": 1, "variacao_pct": 0.1}]), \
         patch.object(sm.prices, "obter_cotacao", return_value={"preco": 10, "variacao_pct": 1.0}):
        fatos = sm._coletar_fatos()
    por_nome = {item["nome"]: item for item in fatos["mercado_agora"]}
    assert por_nome["IBOVESPA"]["erro"] == "RuntimeError('fora do ar')"
    assert por_nome["IBOVESPA"]["preco"] is None
    assert por_nome["PETR4"]["preco"] == 10
    assert por_nome["VALE3"]["variacao_pct"] == 1.0
    assert fatos["mercados_globais"] == [{"nome": "S&P 500", "preco": 1, "variacao_pct": 0.1}]


def test_obter_sintese_mercado_sem_cache_e_sem_fallback_devolve_ok_false():
    with patch.object(sm.ia_cache, "obter_resumo_com_cache", return_value={"resumo": None, "motivo": "indisponivel"}), \
         patch.object(sm.ia_cache, "obter_mais_recente_concluido", return_value=None):
        resultado = sm.obter_sintese_mercado()
    assert resultado["ok"] is False


def test_obter_sintese_mercado_usa_anterior_quando_atual_falha_e_marca_nao_atual():
    anterior = {
        "criado_em": "2026-10-25T08:00:00+00:00",
        "resultado": {
            "dados": {"resumo_executivo": {"texto": "Síntese de ontem.", "ressalvas": ""},
                      "movimentos": [], "oportunidades_riscos": [], "o_que_nao_sabemos": []},
            "modelo": "modelo-principal", "fatos_gerado_em": "2026-10-25T08:00:00+00:00",
            "fontes_indisponiveis": [],
        },
    }
    with patch.object(sm.ia_cache, "obter_resumo_com_cache", return_value={"resumo": None, "motivo": "indisponivel"}), \
         patch.object(sm.ia_cache, "obter_mais_recente_concluido", return_value=anterior):
        resultado = sm.obter_sintese_mercado()
    assert resultado["ok"] is True
    assert resultado["atual"] is False
    assert resultado["gerado_em"] == "2026-10-25T08:00:00+00:00"
    assert resultado["dados"]["resumo_executivo"]["texto"] == "Síntese de ontem."


def test_obter_sintese_mercado_atual_quando_cache_tem_sucesso():
    sucesso = {
        "resumo": "Texto atual.",
        "dados": {"resumo_executivo": {"texto": "Texto atual.", "ressalvas": ""},
                  "movimentos": [], "oportunidades_riscos": [], "o_que_nao_sabemos": []},
        "modelo": "modelo-principal", "fatos_gerado_em": "2026-10-26T12:00:00+00:00",
        "fontes_indisponiveis": [],
    }
    with patch.object(sm.ia_cache, "obter_resumo_com_cache", return_value=sucesso):
        resultado = sm.obter_sintese_mercado()
    assert resultado["ok"] is True
    assert resultado["atual"] is True
    assert resultado["gerado_em"] == "2026-10-26T12:00:00+00:00"
