# -*- coding: utf-8 -*-
"""Testes da busca/autocomplete de ativo (ui/busca.py) - achado real
(2026-10-05): CVCB3 (e mais 7 tickers - ECOR3/EZTC3/JBSS32/LWSA3/PCAR3/
POSI3/SMTO3) saiu da composicao OFICIAL do Ibovespa num rebalanceamento
da B3, mas o projeto ainda os rastreia manualmente em
config.IBOVESPA_SETORES - o universo da busca usava "composicao oficial
OU fallback estatico" (exclusivo, nunca os dois), escondendo esses
tickers da busca sempre que a B3 respondia (quase sempre). Corrigido
pra UNIAO (ver ui/busca.py:_universo_ativos). Mocka
obter_composicao_oficial - nao faz chamada de rede."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import ui.busca as busca_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def test_1_ticker_fora_da_composicao_oficial_mas_no_dict_curado_aparece():
    """CVCB3 nao esta na composicao oficial (simulada aqui sem ele,
    reproduzindo o cenario real) mas esta em config.IBOVESPA_SETORES -
    tem que aparecer na busca mesmo assim."""
    composicao_sem_cvcb3 = {t: {"nome": t} for t in config.IBOVESPA_SETORES if t != "CVCB3"}
    with patch.object(busca_mod, "obter_composicao_oficial", return_value=composicao_sem_cvcb3):
        opcoes = busca_mod._universo_ativos(())
    _checar("1a CVCB3 nao esta na composicao oficial simulada (pre-condicao do teste)",
             "CVCB3" not in composicao_sem_cvcb3)
    _checar("1b CVCB3 ainda assim aparece no universo da busca (uniao com o dict curado)",
             "CVCB3" in opcoes)
    _checar("1c CVCB3 aparece com o nome curado (NOMES_ATIVOS_BUSCA), nao so' o ticker cru",
             opcoes.get("CVCB3") == "CVCB3 — CVC")


def test_2_ticker_so_na_composicao_oficial_tambem_aparece():
    """Uniao funciona nos dois sentidos - um ticker que a B3 retorna mas
    que (hipoteticamente) ainda nao foi adicionado ao dict curado
    tambem precisa aparecer (nunca perde cobertura em relacao a hoje)."""
    composicao = {t: {"nome": t, "peso_pct": 0.1} for t in config.IBOVESPA_SETORES if t != "CVCB3"}
    composicao["TICKERX9"] = {"nome": "Empresa Hipotetica", "peso_pct": 0.1}
    with patch.object(busca_mod, "obter_composicao_oficial", return_value=composicao):
        opcoes = busca_mod._universo_ativos(())
    _checar("2 ticker so' na composicao oficial (nao no dict curado) tambem aparece",
             "TICKERX9" in opcoes)


def test_3_b3_fora_do_ar_cai_pro_fallback_estatico_como_antes():
    """Comportamento ja existente preservado: composicao oficial vazia
    (B3 fora do ar) -> universo = so' o dict curado, nunca fica sem
    nenhuma opcao."""
    with patch.object(busca_mod, "obter_composicao_oficial", return_value={}):
        opcoes = busca_mod._universo_ativos(())
    _checar("3a B3 fora do ar: universo nao fica vazio", len(opcoes) > 0)
    _checar("3b B3 fora do ar: todo o dict curado continua disponivel",
             set(config.IBOVESPA_SETORES.keys()) <= set(opcoes.keys()))
    _checar("3c CVCB3 presente mesmo com B3 totalmente fora do ar", "CVCB3" in opcoes)


def test_4_extras_e_aliases_continuam_funcionando():
    composicao_sem_cvcb3 = {t: {"nome": t} for t in config.IBOVESPA_SETORES if t != "CVCB3"}
    with patch.object(busca_mod, "obter_composicao_oficial", return_value=composicao_sem_cvcb3):
        opcoes = busca_mod._universo_ativos(("ZZZZ99",))
    _checar("4a extras (watchlist) continuam aparecendo", "ZZZZ99" in opcoes)
    _checar("4b um alias de BDR conhecido continua aparecendo",
             next(iter(config.TICKER_ALIASES.keys()), None) in opcoes if config.TICKER_ALIASES else True)


def test_5b_roxo34_nubank_esta_cadastrado_como_bdr():
    """Achado real (2026-10-08, investigacao pontual pedida pelo Rodrigo):
    ROXO34 (BDR do Nubank/Nu Holdings) nao aparecia na busca/autocomplete
    nem tinha cobertura de noticia decente - nao e' limitacao da B3
    (Ibovespa nao inclui BDR por regra do indice, isso e' esperado), e'
    so' uma lacuna de cadastro: ao contrario de MELI34/NFLX34/etc, ROXO34
    nunca tinha sido adicionado em config.TICKER_ALIASES/NOMES_ATIVOS_BUSCA
    (os dicts GENERICOS que ja resolvem esse problema pra qualquer BDR -
    nenhuma logica nova, so' a entrada que faltava). Sem o alias "Nubank"
    (nome popular, nunca "Nu Holdings") a busca de noticia
    (data/news.py:obter_noticias) praticamente nao achava nada pro papel."""
    _checar("5b1 ROXO34 tem aliases cadastrados pra busca de noticia",
             bool(config.TICKER_ALIASES.get("ROXO34")))
    _checar("5b2 'Nubank' (nome popular, o que a imprensa usa de verdade) esta nos aliases",
             "Nubank" in config.TICKER_ALIASES.get("ROXO34", []))
    _checar("5b3 ROXO34 tem nome curado pra busca/autocomplete",
             bool(config.NOMES_ATIVOS_BUSCA.get("ROXO34")))
    with patch.object(busca_mod, "obter_composicao_oficial", return_value={}):
        opcoes = busca_mod._universo_ativos(())
    _checar("5b4 ROXO34 aparece no universo da busca/autocomplete (EQUITY/NEWS)",
             "ROXO34" in opcoes)


def test_5_cvcb3_esta_no_universo_do_coletor_de_eventos():
    """O coletor (coletor_local.py -> data.eventos_coleta.coletar_eventos_universo)
    usa list(config.IBOVESPA_SETORES.keys()) direto como universo (nao
    passa pela composicao oficial da B3) - CVCB3 so' precisa estar
    nessa fonte, que e' a mesma fonte central corrigida acima. Nao
    reexecuta a coleta completa (cara/lenta) - so' confirma que a CHAVE
    existe na fonte que o coletor consome."""
    _checar("5a CVCB3 esta em config.IBOVESPA_SETORES (fonte do universo do coletor)",
             "CVCB3" in config.IBOVESPA_SETORES)
    _checar("5b CVCB3 tem setor mapeado (nao fica sem classificacao)",
             bool(config.IBOVESPA_SETORES.get("CVCB3")))


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE BUSCA/AUTOCOMPLETE PASSARAM")
