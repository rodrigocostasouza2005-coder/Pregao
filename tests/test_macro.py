# -*- coding: utf-8 -*-
"""Testes de data/macro.py: obter_curva_pre (curva pre/ETTJ, ANBIMA) e
_focus_multi_ano (expectativas Focus/Olinda) - 2 bugs da MESMA classe,
achados em auditorias diferentes:

- testes 1-3 (2026-10-10): uma resposta NAO-vazia mas malformada pra UM
  dos 7 dias tentados na ANBIMA (layout mudou, mensagem de erro/
  manutencao no lugar do CSV) lancava excecao (StopIteration/ValueError)
  de dentro do loop de fallback - como nao havia try/except por
  iteracao, isso escapava pro try/except EXTERNO e abortava a tentativa
  nos outros 6 dias, mesmo que algum deles tivesse publicacao valida.
- testes 4-5 (2026-10-13, auditoria missao coletores): mesmo padrao no
  loop de 3 anos do Focus - um erro pontual buscando UM ano abortava os
  outros 2 anos, mesmo com dado valido.

Mocka _buscar_ettj_anbima/_focus_anual - nunca faz chamada de rede.

Uso: python tests/test_macro.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.macro as macro_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


_CSV_VALIDO = "\n".join([
    "10/10/2026",
    "PREFIXADOS (CIRCULAR 3.361)",
    "header (ignorada)",
    "21;13,3917",
    "42;13,2000",
    "",  # linha vazia real (splitlines() so reconhece como item separado
    "fim do bloco",  # se houver conteudo depois - string.splitlines() nao
])  # gera elemento vazio final so por terminar em "\n"


def test_1_dia_malformado_nao_aborta_tentativa_dos_dias_anteriores():
    """volta=0 (hoje) vem com texto NAO-vazio mas sem o bloco PREFIXADOS
    (layout mudou/mensagem de erro) - antes da correcao isso abortava o
    loop inteiro; agora deve cair pro volta=1 (CSV valido) sem lancar."""
    from datetime import date

    macro_mod.obter_curva_pre.clear()

    def _fake_buscar(dt_ref_str):
        if dt_ref_str == date(2026, 10, 10).strftime("%d%m%Y"):
            return "pagina de manutencao, sem o bloco PREFIXADOS esperado"
        return _CSV_VALIDO

    with patch.object(macro_mod, "_buscar_ettj_anbima", side_effect=_fake_buscar), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("1a nao retorna None (achou um dia valido apos o malformado)", df is not None, f"(df={df})")
    _checar("1b DataFrame tem os 2 vertices do dia valido", df is not None and len(df) == 2, f"(df={df})")
    _checar("1c registra execucao_ok=True (achou publicacao valida)",
            mock_reg.call_args is not None and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")


def test_2_todos_os_dias_malformados_resulta_em_falha_registrada():
    from datetime import date

    macro_mod.obter_curva_pre.clear()
    with patch.object(macro_mod, "_buscar_ettj_anbima", return_value="sem bloco PREFIXADOS nenhum"), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("2a todos os 7 dias malformados -> None (nunca inventa curva)", df is None)
    _checar("2b registra execucao_ok=False", mock_reg.call_args.kwargs.get("execucao_ok") is False, f"({mock_reg.call_args})")


def test_3_dias_vazios_continuam_pulados_normalmente():
    """Garante que a correcao nao mudou o comportamento ja existente pra
    dia sem publicacao (texto vazio, ex: fim de semana) - continua so'
    pulando pro dia anterior, sem tentar parsear."""
    from datetime import date

    macro_mod.obter_curva_pre.clear()
    chamadas = []

    def _fake_buscar(dt_ref_str):
        chamadas.append(dt_ref_str)
        if len(chamadas) <= 2:
            return ""  # dias sem publicacao
        return _CSV_VALIDO

    with patch.object(macro_mod, "_buscar_ettj_anbima", side_effect=_fake_buscar), \
         patch.object(macro_mod, "registrar_tentativa"):
        df = macro_mod.obter_curva_pre(data_referencia=date(2026, 10, 10))

    _checar("3a acha o CSV valido apos pular os 2 dias vazios", df is not None and len(df) == 2, f"(df={df})")
    _checar("3b tentou exatamente 3 dias (2 vazios + 1 valido, nao os 7)", len(chamadas) == 3, f"(chamadas={chamadas})")


def test_4_focus_ano_malformado_nao_aborta_os_outros_anos():
    """_focus_multi_ano: bug real corrigido (auditoria missao coletores,
    2026-10-13) - mesma classe de bug do fix ANBIMA (e04b295), so' que no
    caminho Focus/Olinda. Um erro (HTTPError/KeyError/etc) ao buscar UM
    dos 3 anos nao pode abortar os outros 2 anos, que tinham dado valido.
    Mocka _focus_anual - nunca faz chamada de rede."""
    from datetime import datetime

    ano_atual = datetime.now(macro_mod.TZ).year

    def _fake_focus_anual(indicador, ano, base_calculo=0):
        if ano == ano_atual + 1:
            raise ValueError("resposta malformada da Olinda pra esse ano")
        return {
            "ano_referencia": ano, "mediana_pct": 4.5, "media_pct": 4.6,
            "numero_respondentes": 50, "data_calculo": "2026-10-10",
        }

    with patch.object(macro_mod, "_focus_anual", side_effect=_fake_focus_anual):
        df = macro_mod._focus_multi_ano("IPCA")

    _checar("4a nao retorna None (2 dos 3 anos tinham dado valido)", df is not None, f"(df={df})")
    _checar("4b DataFrame tem os 2 anos validos (nao 3, nao 0)", df is not None and len(df) == 2, f"(df={df})")
    _checar(
        "4c o ano malformado (ano_atual+1) nao aparece no resultado",
        df is not None and (ano_atual + 1) not in df["ano_referencia"].tolist(),
        f"(anos={df['ano_referencia'].tolist() if df is not None else None})",
    )


def test_5_focus_todos_os_anos_malformados_resulta_em_none():
    with patch.object(macro_mod, "_focus_anual", side_effect=ValueError("sempre falha")):
        df = macro_mod._focus_multi_ano("Selic")

    _checar("5a todos os 3 anos falhando -> None (nunca inventa expectativa)", df is None)


def test_6_cenario_global_lote_falho_registra_falha_em_saude_dos_dados():
    # bug real corrigido (auditoria missao coletores 2026-10-13,
    # continuacao): obter_cenario_global usa _baixar_lote_bruto (mesmo
    # helper de data/mercado.py:obter_mercados_globais) mas nunca
    # chamava registrar_tentativa - nenhum dos 2 call-sites chamava,
    # na verdade. Se o lote de ouro/Brent/WTI/minerio/Treasuries/VIX
    # falhar, a aba MACRO mostrava [] honestamente, mas SAUDE DOS DADOS
    # nunca sabia (nenhuma linha representava essa fonte).
    with patch.object(macro_mod, "_baixar_lote_bruto", return_value=None), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        resultado = macro_mod.obter_cenario_global()
    _checar("6a lote falho -> [] (nunca inventa cotacao)", resultado == [])
    _checar("6b registra MACRO (Cenário Global) execucao_ok=False",
            mock_reg.call_args.args[0] == "MACRO (Cenário Global)" and mock_reg.call_args.kwargs.get("execucao_ok") is False,
            f"(call={mock_reg.call_args})")


def test_7_cenario_global_sucesso_registra_ok_com_registros_reais():
    idx = pd.date_range("2026-10-01", periods=2, freq="D")
    df = pd.concat({
        "GC=F": pd.DataFrame({"Close": [1900.0, 1920.0], "Volume": [0, 0]}, index=idx),  # "Ouro" em config.CENARIO_GLOBAL
    }, axis=1)
    with patch.object(macro_mod, "_baixar_lote_bruto", return_value=df), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        resultado = macro_mod.obter_cenario_global()
    _checar("7a registra MACRO (Cenário Global) execucao_ok=True",
            mock_reg.call_args.args[0] == "MACRO (Cenário Global)" and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")
    _checar("7b registros_novos bate com a quantidade real retornada (nunca conta item vazio)",
            mock_reg.call_args.kwargs.get("registros_novos") == len(resultado), f"(resultado={resultado}, call={mock_reg.call_args})")


# ============================================================
# testes 8-11 (gap de escopo ja catalogado em BACKLOG.md, resolvido
# nesta sessao de continuacao 2026-10-13): Selic/CDI/Focus (IPCA e
# Selic) ganham linha PROPRIA em SAUDE DOS DADOS - antes, so' IPCA
# chamava registrar_tentativa (como "ponto representativo" da fonte
# BCB inteira) e uma falha isolada numa dessas series ficava invisivel
# enquanto IPCA continuasse OK.
# ============================================================

def _serie_fake(valor=5.0):
    return pd.DataFrame({"data": pd.date_range("2026-10-01", periods=2, freq="D"), "valor": [valor, valor]})


def test_8_selic_sucesso_registra_linha_propria():
    macro_mod.obter_selic_meta.clear()
    with patch.object(macro_mod, "_serie_sgs", return_value=_serie_fake()), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_selic_meta()
    _checar("8a Selic retorna dado real", df is not None and len(df) == 2, f"(df={df})")
    _checar("8b registra 'MACRO (BCB - Selic)' execucao_ok=True (linha propria, nao mais so' IPCA)",
            mock_reg.call_args.args[0] == "MACRO (BCB - Selic)" and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")


def test_9_selic_falha_isolada_fica_visivel_mesmo_sem_tocar_ipca():
    macro_mod.obter_selic_meta.clear()
    with patch.object(macro_mod, "_serie_sgs", side_effect=Exception("BC renomeou o codigo SGS 432")), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_selic_meta()
    _checar("9a Selic falho -> None (nunca inventa taxa)", df is None)
    _checar("9b registra 'MACRO (BCB - Selic)' execucao_ok=False com o erro real",
            mock_reg.call_args.args[0] == "MACRO (BCB - Selic)" and mock_reg.call_args.kwargs.get("execucao_ok") is False
            and "432" in mock_reg.call_args.kwargs.get("erro", ""), f"(call={mock_reg.call_args})")


def test_10_cdi_sucesso_registra_linha_propria():
    macro_mod.obter_cdi.clear()
    with patch.object(macro_mod, "_serie_sgs", return_value=_serie_fake()), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        df = macro_mod.obter_cdi()
    _checar("10a CDI retorna dado real", df is not None and len(df) == 2, f"(df={df})")
    _checar("10b registra 'MACRO (BCB - CDI)' execucao_ok=True",
            mock_reg.call_args.args[0] == "MACRO (BCB - CDI)" and mock_reg.call_args.kwargs.get("execucao_ok") is True,
            f"(call={mock_reg.call_args})")


def test_11_focus_ipca_e_focus_selic_registram_linhas_proprias_e_distintas():
    macro_mod.obter_focus_ipca.clear()
    macro_mod.obter_focus_selic.clear()
    with patch.object(macro_mod, "_focus_multi_ano", return_value=pd.DataFrame({"ano_referencia": [2026]})), \
         patch.object(macro_mod, "registrar_tentativa") as mock_reg:
        macro_mod.obter_focus_ipca()
        macro_mod.obter_focus_selic()
    nomes_registrados = [c.args[0] for c in mock_reg.call_args_list]
    _checar("11a Focus IPCA e Focus Selic registram nomes DIFERENTES (nunca o mesmo nome pros 2 indicadores)",
            nomes_registrados == ["MACRO (BCB - Focus IPCA)", "MACRO (BCB - Focus Selic)"],
            f"(nomes={nomes_registrados})")
    _checar("11b ambos execucao_ok=True (dado real presente)",
            all(c.kwargs.get("execucao_ok") is True for c in mock_reg.call_args_list))


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
    print("TODOS OS TESTES DE MACRO.PY (CURVA PRE/ANBIMA) PASSARAM")
