"""Testes das funções puras do painel Research & Fatores."""
from ui.analises_tab import _FATORES_POR_TICKER, _UNIDADE_FATOR, _alvo_positivo, _numero_finito, _potencial_pct


def test_potencial_percentual_com_valores_validos():
    assert abs(_potencial_pct(120, 100) - 20) < 1e-9
    assert abs(_potencial_pct(80, 100) + 20) < 1e-9


def test_potencial_nao_calcula_com_preco_ausente_ou_invalido():
    assert _potencial_pct(None, 100) is None
    assert _potencial_pct("indisponível", 100) is None
    assert _potencial_pct(100, 0) is None
    assert _potencial_pct(-10, 100) is None


def test_numero_finito_rejeita_nan_e_infinito():
    assert _numero_finito("12.5") == 12.5
    assert _numero_finito(None) is None
    assert _numero_finito("NaN") is None
    assert _numero_finito("inf") is None


def test_fatores_nao_assumem_serie_de_minerio_nao_validada():
    for ticker in ("VALE3", "GGBR4", "CSNA3"):
        fatores = dict(_FATORES_POR_TICKER[ticker])
        assert fatores["Minério de ferro: série específica não validada"] == ""


def test_petroleiras_tem_brent_e_cambio():
    fatores = dict(_FATORES_POR_TICKER["PETR4"])
    assert fatores["Petróleo Brent"] == "BZ=F"
    assert fatores["USD/BRL"] == "USDBRL=X"


def test_alvo_atual_nao_reaproveita_snapshot_anterior():
    assert _alvo_positivo({"preco_alvo": 35.5}) == 35.5
    assert _alvo_positivo({"preco_alvo": None}) is None
    assert _alvo_positivo({"preco_alvo": 0}) is None
    assert _alvo_positivo({"preco_alvo": "NaN"}) is None
    assert _alvo_positivo(None) is None

 
def test_unidades_de_futuros_sao_explicitas():
    assert _UNIDADE_FATOR["BZ=F"] == "US$/barril"
    assert _UNIDADE_FATOR["USDBRL=X"] == "R$/US$"
    assert _UNIDADE_FATOR["ZC=F"] == "¢/bushel"
    assert _UNIDADE_FATOR["HG=F"] == "¢/lb"
