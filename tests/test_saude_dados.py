# -*- coding: utf-8 -*-
"""Testes da classificacao de SAUDE DOS DADOS (data/saude_dados.py) -
os estados diferenciados pedidos na FASE 2 (sucesso com/sem novidade,
parcial, falha de execucao, falha de persistencia, desatualizado,
fonte indisponivel, nao comprovado/nunca executado). `classificar_estado`
e' funcao pura (sem rede/banco) - testada so' com dicts de entrada.
`obter_painel_saude` e' testado mockando `coletores_status.obter_status`
e os leitores somente-leitura.

Uso: python tests/test_saude_dados.py (python do .venv do projeto)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.saude_dados as saude_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _ha(horas):
    return (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()


def test_1_sem_status_e_nunca_executado():
    codigo, _ = saude_mod.classificar_estado(None)
    _checar("1 status None -> NUNCA_EXECUTADO", codigo == "NUNCA_EXECUTADO")


def test_2_execucao_ok_sem_sucesso_nunca_e_nao_comprovado():
    status = {
        "execucao_ok": False,
        "persistencia_ok": True,
        "ultimo_erro": "x",
        "ultimo_sucesso_em": None,
    }
    codigo, rotulo = saude_mod.classificar_estado(status)
    _checar("2 nunca teve sucesso -> NAO_COMPROVADO", codigo == "NAO_COMPROVADO")
    _checar("2b rotulo menciona o erro mais recente", "x" in rotulo)


def test_3_sucesso_com_novidade():
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 5,
        "ultimo_sucesso_em": _ha(0.1),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar(
        "3 execucao+persistencia OK e registros_novos>0 -> SUCESSO_COM_NOVIDADE",
        codigo == "SUCESSO_COM_NOVIDADE",
    )


def test_4_sucesso_sem_novidade():
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "ultimo_sucesso_em": _ha(0.1),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar(
        "4 registros_novos==0 -> SUCESSO_SEM_NOVIDADE",
        codigo == "SUCESSO_SEM_NOVIDADE",
    )


def test_5_parcial():
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "parcial": True,
        "ultimo_sucesso_em": _ha(0.1),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("5 parcial=True -> PARCIAL", codigo == "PARCIAL")


def test_5b_parcial_com_erro_mostra_o_detalhe_real():
    """Achado real (2026-10-19, Radar de quedas): sem o detalhe, uma
    falha grave (ex: cotacao indisponivel pra 10/10 tickers monitorados)
    e uma fonte de carteira so' 1h desatualizada caem na MESMA frase
    generica "algumas fontes/itens nao confirmados" - o painel deixa de
    refletir a gravidade real da execucao. Ver data/radar_quedas.py:
    processar_monitoramento, que agora preenche `erro` com o detalhe
    mesmo quando coleta_ok=True."""
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "parcial": True,
        "ultimo_erro": "Cotação indisponível para 10/10 ticker(s) monitorado(s)",
        "ultimo_sucesso_em": _ha(0.1),
    }
    codigo, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("5b parcial com erro -> ainda PARCIAL", codigo == "PARCIAL")
    _checar("5b rotulo menciona o detalhe real do erro", "10/10" in rotulo, rotulo)


def test_5c_parcial_sem_erro_mantem_frase_generica():
    """Sem `ultimo_erro`, mantem a frase antiga - nao regride o caso ja'
    coberto pelo teste 5."""
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "parcial": True,
        "ultimo_sucesso_em": _ha(0.1),
    }
    _, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("5c sem erro -> frase generica", "algumas fontes/itens nao confirmados" in rotulo, rotulo)


def test_6_falha_execucao_generica():
    status = {
        "execucao_ok": False,
        "persistencia_ok": True,
        "ultimo_erro": "KeyError inesperado",
        "ultimo_sucesso_em": _ha(1),
    }
    codigo, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("6 erro sem termo de indisponibilidade -> FALHA_EXECUCAO", codigo == "FALHA_EXECUCAO")
    _checar("6b rotulo cita o erro real", "KeyError" in rotulo)


def test_7_fonte_indisponivel():
    status = {
        "execucao_ok": False,
        "persistencia_ok": True,
        "ultimo_erro": "timeout ao conectar",
        "ultimo_sucesso_em": _ha(1),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("7 erro com 'timeout' -> FONTE_INDISPONIVEL", codigo == "FONTE_INDISPONIVEL")


def test_8_falha_persistencia():
    status = {
        "execucao_ok": True,
        "persistencia_ok": False,
        "ultimo_sucesso_em": _ha(1),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar(
        "8 execucao OK mas persistencia_ok=False -> FALHA_PERSISTENCIA",
        codigo == "FALHA_PERSISTENCIA",
    )


def test_9_dados_desatualizados():
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "ultimo_sucesso_em": _ha(48),
    }
    codigo, rotulo = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar("9 ultimo sucesso ha 48h com limite 6h -> DADOS_DESATUALIZADOS", codigo == "DADOS_DESATUALIZADOS")
    _checar("9b rotulo cita a idade aproximada", "48" in rotulo)


def test_10_sem_limite_de_idade_nao_marca_desatualizado():
    status = {
        "execucao_ok": True,
        "persistencia_ok": True,
        "registros_novos": 0,
        "ultimo_sucesso_em": _ha(1000),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=None)
    _checar(
        "10 idade_maxima_horas=None nunca marca desatualizado",
        codigo == "SUCESSO_SEM_NOVIDADE",
    )


def test_11_falha_execucao_tem_prioridade_sobre_desatualizado():
    status = {
        "execucao_ok": False,
        "persistencia_ok": True,
        "ultimo_erro": "erro generico",
        "ultimo_sucesso_em": _ha(100),
    }
    codigo, _ = saude_mod.classificar_estado(status, idade_maxima_horas=6)
    _checar(
        "11 tentativa mais recente falhou -> reporta a falha, nao so' 'desatualizado'",
        codigo == "FALHA_EXECUCAO",
    )


def test_12_status_somente_leitura_sem_dado_e_none():
    _checar(
        "12 _status_somente_leitura(None) -> None",
        saude_mod._status_somente_leitura(None) is None,
    )


def test_13_status_somente_leitura_aceita_datetime_e_string():
    agora = datetime.now(timezone.utc)
    s1 = saude_mod._status_somente_leitura(agora)
    s2 = saude_mod._status_somente_leitura(agora.isoformat())
    _checar("13a datetime normalizado pra iso", s1["ultimo_sucesso_em"] == agora.isoformat())
    _checar("13b string aceita direto", s2["ultimo_sucesso_em"] == agora.isoformat())
    _checar("13c execucao_ok=None (desconhecido, nunca inventado)", s1["execucao_ok"] is None)


def test_14_painel_completo_cobre_todos_os_coletores_registrados():
    # Substitui o leitor de TODOS os coletores para impedir acesso a dados reais.
    registro_sem_dados = [
        {**c, "leitor": (lambda: None)}
        for c in saude_mod.REGISTRO_COLETORES
    ]

    with patch.object(saude_mod.coletores_status, "obter_status", return_value=None):
        with patch.object(saude_mod, "REGISTRO_COLETORES", registro_sem_dados):
            painel = saude_mod.obter_painel_saude()

    nomes_painel = {item["nome"] for item in painel}
    nomes_registro = {c["nome"] for c in registro_sem_dados}

    _checar(
        "14a painel tem 1 entrada por coletor registrado",
        nomes_painel == nomes_registro,
    )
    _checar(
        "14b sem nenhum dado disponivel, tudo cai em NUNCA_EXECUTADO",
        all(item["codigo_estado"] == "NUNCA_EXECUTADO" for item in painel),
    )
    _checar(
        "14c todos marcados como desconhecido (nao falso-verde)",
        all(item["desconhecido"] for item in painel),
    )


# ============================================================
# N+1 real (auditoria de performance 2026-10-24): coletores SEM leitor
# dedicado (24 de 30 em REGISTRO_COLETORES) chamavam
# coletores_status.obter_status(nome) individualmente - 24 round-trips
# sequenciais ao Supabase por carregamento de SAUDE DOS DADOS.
# obter_todos_status() (1 unica consulta, mesmo schema de linha) ja
# existia e nao era usada aqui.
# ============================================================

def test_14b_painel_usa_consulta_em_lote_nunca_uma_por_coletor():
    linhas = {c["nome"]: {"nome": c["nome"], "execucao_ok": True, "persistencia_ok": True,
                          "parcial": False, "registros_novos": 1, "ultimo_erro": None,
                          "ultimo_sucesso_em": _ha(1)}
              for c in saude_mod.REGISTRO_COLETORES if "leitor" not in c}

    with patch.object(saude_mod.coletores_status, "obter_todos_status", return_value=linhas) as m_lote, \
         patch.object(saude_mod.coletores_status, "obter_status",
                      side_effect=AssertionError("N+1: obter_status chamado por coletor, deveria usar obter_todos_status")):
        painel = saude_mod.obter_painel_saude()

    _checar("14b1 obter_todos_status chamado exatamente 1 vez (nao 1 por coletor)", m_lote.call_count == 1)
    sem_leitor = [c["nome"] for c in saude_mod.REGISTRO_COLETORES if "leitor" not in c]
    _checar(
        "14b2 coletores sem leitor dedicado recebem o status_bruto exato do lote (comportamento preservado)",
        all(next(p for p in painel if p["nome"] == nome)["status_bruto"] == linhas[nome] for nome in sem_leitor),
    )


def test_15_painel_excecao_num_leitor_nao_derruba_o_painel():
    def _leitor_que_falha():
        raise RuntimeError("Supabase fora do ar")

    registro_modificado = [dict(c) for c in saude_mod.REGISTRO_COLETORES]
    for c in registro_modificado:
        if not c["instrumentado"]:
            c["leitor"] = _leitor_que_falha

    with patch.object(
        saude_mod.coletores_status,
        "obter_status",
        side_effect=RuntimeError("banco fora do ar"),
    ):
        with patch.object(saude_mod, "REGISTRO_COLETORES", registro_modificado):
            painel = saude_mod.obter_painel_saude()

    _checar(
        "15 painel completo mesmo com todo leitor/obter_status lancando excecao",
        len(painel) == len(registro_modificado),
    )
    _checar(
        "15b todas as entradas ficam NUNCA_EXECUTADO (nao quebra, nao finge sucesso)",
        all(item["codigo_estado"] == "NUNCA_EXECUTADO" for item in painel),
    )


def test_16_diagnostico_infraestrutura_repassa_tabela_disponivel():
    with patch.object(saude_mod.coletores_status, "tabela_disponivel", return_value=False):
        resultado = saude_mod.diagnostico_infraestrutura()
    _checar(
        "16 diagnostico_infraestrutura repassa False (tabela ausente/erro) pra UI reagir",
        resultado is False,
    )


def test_17_toda_casa_de_research_ativa_aparece_no_painel():
    """Achado real (auditoria 2026-10-22): 'BTG Pactual Research' e 'Monte
    Bravo' sao casas ativa_por_padrao=True em data/research/__init__.py:
    CASAS (coletam de verdade, gravam research_itens com esse 'casa' - ver
    btg.py/montebravo.py:_NOME_CASA) mas nao constavam em REGISTRO_COLETORES -
    ficavam sem NENHUMA representacao neste painel (nem OK, nem falha). Este
    teste trava a lista: toda casa ativa em CASAS tem que ter uma entrada
    com o MESMO nome aqui, pra nao repetir o gap com a proxima casa nova."""
    from data.research import CASAS

    nomes_painel = {c["nome"] for c in saude_mod.REGISTRO_COLETORES}
    nomes_casas_ativas = {c["nome"] for c in CASAS if c.get("ativa_por_padrao")}
    faltando = nomes_casas_ativas - nomes_painel
    _checar(
        "17 nenhuma casa ativa de research falta no painel de saude",
        not faltando,
        f"faltando: {faltando}",
    )


def test_18_btg_e_montebravo_usam_leitor_hibrido_pela_mesma_casa():
    por_nome = {c["nome"]: c for c in saude_mod.REGISTRO_COLETORES}
    for nome in ("BTG Pactual Research", "Monte Bravo"):
        _checar(f"18 {nome} esta registrado", nome in por_nome, nome)
        _checar(f"18 {nome} tem leitor hibrido proprio", "leitor" in por_nome[nome], nome)


def test_19_consumo_sem_edicao_fica_desconhecido_nao_falso_verde():
    painel = saude_mod.obter_painel_consumo(edicao=None)
    _checar(
        "19 sem edicao (banco indisponivel ou nenhuma publicada) -> CONSUMO_DESCONHECIDO pra todas as fontes",
        all(item["codigo_estado"] == "CONSUMO_DESCONHECIDO" for item in painel),
    )


def test_20_consumo_com_itens_na_secao():
    edicao = {
        "data": "2026-10-22",
        "conteudo": "\n".join([
            "2. BRASIL",
            "- Manchete A — https://a.com",
            "3. EXTERIOR",
            "- Nenhuma manchete internacional nesta coleta.",
        ]),
    }
    painel = saude_mod.obter_painel_consumo(edicao=edicao)
    por_fonte = {item["fonte"]: item for item in painel}
    _checar(
        "20a NEWS (Brasil) com 1 item -> CONSUMO_COM_ITENS",
        por_fonte["NEWS (Brasil)"]["codigo_estado"] == "CONSUMO_COM_ITENS",
    )
    _checar(
        "20b NEWS (Internacional) sem item -> CONSUMO_SEM_ITENS (nao declara coletor quebrado)",
        por_fonte["NEWS (Internacional)"]["codigo_estado"] == "CONSUMO_SEM_ITENS",
    )


def test_21_consumo_falha_na_contagem_nao_derruba_o_painel():
    edicao = {"data": "2026-10-22", "conteudo": "qualquer texto"}
    with patch("jobs.morning_call.contar_itens_por_secao", side_effect=RuntimeError("boom")):
        painel = saude_mod.obter_painel_consumo(edicao=edicao)
    _checar(
        "21 excecao na contagem -> todas as fontes com itens=0, sem lancar",
        all(item["itens"] == 0 for item in painel),
    )


def test_22_carteiras_recomendadas_tem_nome_proprio_nunca_colide_com_research():
    """Achado real (auditoria 2026-10-22): registrar_tentativa faz upsert
    por `nome` - "Genial Analisa (carteiras)"/"Safra Corretora
    (carteiras)" (jobs/radar_quedas.py) tem que ser nomes DIFERENTES de
    "Genial Analisa" (data/research/genial.py, research de verdade) e
    de "Safra Corretora" (se existir alguma outra entrada) - senao' o
    upsert de uma fonte sobrescreveria o status da outra."""
    nomes = {c["nome"] for c in saude_mod.REGISTRO_COLETORES}
    _checar(
        "22a Genial Analisa (carteiras) presente",
        "Genial Analisa (carteiras)" in nomes,
    )
    _checar(
        "22b Safra Corretora (carteiras) presente",
        "Safra Corretora (carteiras)" in nomes,
    )
    _checar(
        "22c nunca existe uma entrada 'Safra Corretora' sem o sufixo (nome ambiguo)",
        "Safra Corretora" not in nomes,
    )


def test_23_mercado_cotacao_individual_presente_e_nome_diferente_do_lote():
    """Achado real (auditoria 2026-10-22): data/prices.py:obter_cotacao
    (1 ticker por vez) nunca tinha representacao no painel, so' "MERCADO"
    (data/mercado.py, cotacao EM LOTE) - caminhos de codigo diferentes,
    podem falhar isolado."""
    nomes = {c["nome"] for c in saude_mod.REGISTRO_COLETORES}
    _checar("23a MERCADO (cotação individual) presente", "MERCADO (cotação individual)" in nomes)
    _checar("23b nome diferente de MERCADO (lote)", "MERCADO (cotação individual)" != "MERCADO")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE SAUDE DOS DADOS PASSARAM")