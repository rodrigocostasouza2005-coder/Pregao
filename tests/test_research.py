# -*- coding: utf-8 -*-
"""Testes da fase RESEARCH (2026-10-01): extracao estruturada
(preco-alvo/recomendacao) + historico de mudancas. So' cobre a logica
DETERMINISTICA (parsing de resposta, comparacao de snapshot) com Groq e
Supabase mockados - nao faz chamada de API real nem precisa de
.streamlit/secrets.toml, pra poder rodar em qualquer maquina/CI sem
custo nem rate limit.

Os 9 cenarios de VALIDACAO DE CONTEUDO pedidos (documento curto/longo,
com/sem preco-alvo, Morning Call, multiplos tickers etc.) foram
validados com chamadas REAIS a Groq durante o desenvolvimento desta
fase - ver PROGRESSO.md ("FASE RESEARCH") pros resultados completos.
Esse tipo de teste (qualidade de texto gerado por LLM) nao e' o que
este arquivo cobre - aqui e' so' a parte 100% determinstica/sem rede.

Uso: python tests/test_research.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research import historico
from data.research.resumir import _extrair_dados_estruturados

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _cliente_mock(ultimo_snapshot_data):
    cliente = MagicMock()
    log_inserts = []
    resp = MagicMock()
    resp.data = ultimo_snapshot_data
    cliente.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = resp

    def _insert(payload):
        log_inserts.append(payload)
        m = MagicMock()
        m.execute.return_value = MagicMock()
        return m

    cliente.table.return_value.insert.side_effect = _insert
    return cliente, log_inserts


def test_historico_primeiro_snapshot_grava_mas_nao_reporta_mudanca():
    cliente, inserts = _cliente_mock([])
    with patch.object(historico, "obter_cliente", return_value=cliente):
        resultado = historico.registrar_se_mudou("Genial Analisa", "PETR4", "COMPRA", 48.0)
    _checar("primeiro snapshot grava no banco", len(inserts) == 1, f"(inserts={inserts})")
    _checar("primeiro snapshot retorna None (nada pra comparar)", resultado is None)


def test_historico_sem_mudanca_nao_grava():
    anterior = [{"recomendacao": "COMPRA", "preco_alvo": 48.0}]
    cliente, inserts = _cliente_mock(anterior)
    with patch.object(historico, "obter_cliente", return_value=cliente):
        resultado = historico.registrar_se_mudou("Genial Analisa", "PETR4", "COMPRA", 48.0)
    _checar("sem mudanca real nao grava", len(inserts) == 0, f"(inserts={inserts})")
    _checar("sem mudanca real retorna None", resultado is None)


def test_historico_mudanca_preco_alvo_grava_e_retorna_anterior():
    anterior = [{"recomendacao": "COMPRA", "preco_alvo": 48.0}]
    cliente, inserts = _cliente_mock(anterior)
    with patch.object(historico, "obter_cliente", return_value=cliente):
        resultado = historico.registrar_se_mudou("Genial Analisa", "PETR4", "COMPRA", 52.0)
    _checar("mudanca de preco-alvo grava", len(inserts) == 1 and inserts[0]["preco_alvo"] == 52.0, f"(inserts={inserts})")
    _checar("retorna o snapshot ANTERIOR real (48.0, nunca inventado)",
             resultado is not None and resultado["preco_alvo"] == 48.0, f"(resultado={resultado})")


def test_historico_mudanca_recomendacao_grava_e_retorna_anterior():
    anterior = [{"recomendacao": "COMPRA", "preco_alvo": 48.0}]
    cliente, inserts = _cliente_mock(anterior)
    with patch.object(historico, "obter_cliente", return_value=cliente):
        resultado = historico.registrar_se_mudou("Genial Analisa", "PETR4", "MANTER", 48.0)
    _checar("mudanca de recomendacao grava", len(inserts) == 1, f"(inserts={inserts})")
    _checar("retorna a recomendacao anterior (COMPRA)", resultado is not None and resultado["recomendacao"] == "COMPRA")


def test_historico_banco_fora_do_ar_nunca_quebra_nem_finge_mudanca():
    with patch.object(historico, "obter_cliente", return_value=None):
        resultado = historico.registrar_se_mudou("Genial Analisa", "PETR4", "COMPRA", 48.0)
    _checar("banco fora do ar retorna None sem excecao", resultado is None)


def test_historico_mudou_casos_extremos():
    _checar("_mudou: primeiro snapshot (None) = sempre True", historico._mudou(None, "COMPRA", 48.0) is True)
    _checar("_mudou: campos identicos = False",
             historico._mudou({"recomendacao": "COMPRA", "preco_alvo": 48.0}, "COMPRA", 48.0) is False)
    _checar("_mudou: preco None nos dois lados (doc sem preco-alvo) = False, sem falso-positivo",
             historico._mudou({"recomendacao": None, "preco_alvo": None}, None, None) is False)
    _checar("_mudou: None -> valor real = True (passou a ter recomendacao)",
             historico._mudou({"recomendacao": None, "preco_alvo": None}, "COMPRA", None) is True)


def _groq_mock(resposta: str):
    """Mock de resumir._chamar_groq pra testar SO' o parsing de
    _extrair_dados_estruturados, sem chamada de rede nenhuma."""
    return patch("data.research.resumir._chamar_groq", return_value=(resposta, None))


def test_extracao_estruturada_preco_e_recomendacao_explicitos():
    with _groq_mock("PRECO_ALVO: 48.50\nRECOMENDACAO: COMPRA"):
        preco, rec = _extrair_dados_estruturados("texto qualquer", "titulo", "chave-fake", "modelo-fake")
    _checar("preco-alvo explicito extraido corretamente", preco == 48.50, f"(preco={preco})")
    _checar("recomendacao explicita extraida corretamente", rec == "COMPRA", f"(rec={rec})")


def test_extracao_estruturada_nao_identificado_vira_none():
    with _groq_mock("PRECO_ALVO: NAO_IDENTIFICADO\nRECOMENDACAO: NAO_IDENTIFICADO"):
        preco, rec = _extrair_dados_estruturados("texto qualquer", "titulo", "chave-fake", "modelo-fake")
    _checar("NAO_IDENTIFICADO vira None pro preco (nunca inventa)", preco is None, f"(preco={preco})")
    _checar("NAO_IDENTIFICADO vira None pra recomendacao (nunca inventa)", rec is None, f"(rec={rec})")


def test_extracao_estruturada_falha_de_rede_retorna_none_none():
    with patch("data.research.resumir._chamar_groq", return_value=(None, "erro de rede")):
        preco, rec = _extrair_dados_estruturados("texto qualquer", "titulo", "chave-fake", "modelo-fake")
    _checar("falha na chamada nunca inventa dado - preco None", preco is None)
    _checar("falha na chamada nunca inventa dado - recomendacao None", rec is None)


def test_extracao_estruturada_preco_com_formatacao_brl():
    # modelo pode devolver "R$ 48,50" apesar do prompt pedir so' numero -
    # o parsing precisa lidar com isso sem quebrar nem descartar o valor
    with _groq_mock("PRECO_ALVO: R$ 48,50\nRECOMENDACAO: MANTER"):
        preco, rec = _extrair_dados_estruturados("texto", "titulo", "chave-fake", "modelo-fake")
    _checar("preco com formatacao BRL (R$/virgula) ainda e' parseado certo", preco == 48.50, f"(preco={preco})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE RESEARCH (deterministicos) PASSARAM")
