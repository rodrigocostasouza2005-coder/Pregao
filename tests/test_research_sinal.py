from data.research.sinal import calcular_sinal_comite


def _base():
    return {
        "fundamentos": {
            "preco": 20.0, "roe": 22.0, "margem_liquida": 18.0,
            "divida_liquida_ebitda": 0.5, "fluxo_caixa_livre": 100.0,
            "pl": 12.0, "desatualizado": False,
        },
        "fundamentos_historicos": {
            "disponivel": True,
            "receita_liquida": {"yoy_pct_serie": [4.0, 8.0, 12.0]},
        },
        "comparativo_setorial": {"pl_mediana": 18.0},
        "cobertura_research": {"cobertura": []},
    }


def test_sinal_compra_quando_fundamentos_fortes_e_valuation_descontado():
    resultado = calcular_sinal_comite(_base())
    assert resultado["sinal"] == "COMPRA"
    assert resultado["score"] >= 4
    assert resultado["confianca"] == "ALTA"
    assert resultado["criterios"]


def test_sinal_venda_quando_rentabilidade_alavancagem_e_caixa_sao_fracos():
    analise = _base()
    analise["fundamentos"].update({
        "roe": 2.0, "margem_liquida": -3.0,
        "divida_liquida_ebitda": 5.0, "fluxo_caixa_livre": -50.0,
        "pl": 30.0,
    })
    analise["fundamentos_historicos"]["receita_liquida"]["yoy_pct_serie"] = [-8.0, -10.0]
    analise["comparativo_setorial"]["pl_mediana"] = 12.0
    resultado = calcular_sinal_comite(analise)
    assert resultado["sinal"] == "VENDA"
    assert resultado["score"] <= -4


def test_sinal_neutro_na_faixa_sem_assimetria():
    analise = _base()
    analise["fundamentos"].update({"roe": 10.0, "margem_liquida": 8.0,
                                   "divida_liquida_ebitda": 2.0, "fluxo_caixa_livre": 0.0})
    analise["fundamentos_historicos"]["receita_liquida"]["yoy_pct_serie"] = [1.0]
    analise["comparativo_setorial"]["pl_mediana"] = 12.0
    resultado = calcular_sinal_comite(analise)
    assert resultado["sinal"] == "NEUTRO"


def test_sinal_insuficiente_sem_cotacao_ou_com_menos_de_tres_dimensoes():
    sem_preco = _base()
    sem_preco["fundamentos"]["preco"] = None
    assert calcular_sinal_comite(sem_preco)["sinal"] == "INSUFICIENTE"
    poucos_dados = {"fundamentos": {"preco": 20.0, "roe": 15.0}}
    assert calcular_sinal_comite(poucos_dados)["sinal"] == "INSUFICIENTE"


def test_fundamentos_desatualizados_bloqueiam_sinal_direcional():
    analise = _base()
    analise["fundamentos"]["desatualizado"] = True
    resultado = calcular_sinal_comite(analise)
    assert resultado["sinal"] == "NEUTRO"
    assert resultado["confianca"] == "BAIXA"
    assert "desatualizados" in resultado["justificativa"]


def test_research_genial_e_xp_nao_entra_no_comite():
    analise = _base()
    analise["cobertura_research"] = {"cobertura": [
        {"casa": "Genial Analisa", "recomendacao": "VENDA"},
        {"casa": "XP", "recomendacao": "VENDA"},
    ]}
    resultado = calcular_sinal_comite(analise)
    assert all(c["grupo"] != "Research independente" for c in resultado["criterios"])


def test_research_independente_so_pesa_com_duas_casas():
    analise = _base()
    analise["cobertura_research"] = {"cobertura": [
        {"casa": "BTG Pactual", "recomendacao": "COMPRA"},
        {"casa": "Monte Bravo", "recomendacao": "COMPRA"},
    ]}
    resultado = calcular_sinal_comite(analise)
    bloco = next(c for c in resultado["criterios"] if c["grupo"] == "Research independente")
    assert bloco["pontos"] == 2
