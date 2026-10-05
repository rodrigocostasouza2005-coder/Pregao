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

import data.research.resumir as resumir_mod
from data.research import historico
from data.research.resumir import _chamar_groq_com_fallback, _extrair_dados_estruturados, obter_resumo

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


# --- resiliencia do pipeline de resumo (2026-10-01): fallback de modelo
# quando o principal esgota cota/rate-limit ou falha por erro tecnico ---

_MSGS = [{"role": "user", "content": "teste"}]


def test_fallback_1_modelo_principal_funciona_sem_tentar_fallback():
    chamadas = []

    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        chamadas.append(modelo)
        return "resumo do principal", None

    with patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            "chave", "modelo-principal", "modelo-fallback", _MSGS, 100,
        )
    _checar("1 principal funciona: retorna o conteudo do principal", conteudo == "resumo do principal")
    _checar("1 principal funciona: motivo None", motivo is None)
    _checar("1 principal funciona: NAO tenta o fallback (so' 1 chamada, ao principal)",
             chamadas == ["modelo-principal"], f"(chamadas={chamadas})")


def test_fallback_2_principal_cota_fallback_funciona():
    chamadas = []

    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        chamadas.append(modelo)
        if modelo == "modelo-principal":
            return None, "cota"
        return "resumo do fallback", None

    with patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            "chave", "modelo-principal", "modelo-fallback", _MSGS, 100,
        )
    _checar("2 principal com cota: tenta os DOIS modelos, nessa ordem",
             chamadas == ["modelo-principal", "modelo-fallback"], f"(chamadas={chamadas})")
    _checar("2 principal com cota: fallback resolve - retorna o conteudo dele", conteudo == "resumo do fallback")
    _checar("2 principal com cota: motivo None (sucesso, nao precisa avisar nada)", motivo is None)
    _checar("2 principal com cota: usou_fallback=True", usou_fallback is True)


def test_fallback_3_erro_nao_recuperavel_tenta_fallback_mesmo_assim():
    # erro tecnico (nao-429) no principal - fluxo pedido diferencia
    # quota/rate-limit/indisponibilidade (todos tentam fallback), nunca
    # repete INDEFINIDAMENTE (so' 1 tentativa por modelo)
    chamadas = []

    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        chamadas.append(modelo)
        if modelo == "modelo-principal":
            return None, "500 Server Error: Internal Server Error"
        return "resumo do fallback", None

    with patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            "chave", "modelo-principal", "modelo-fallback", _MSGS, 100,
        )
    _checar("3 erro tecnico (nao-cota) no principal tambem aciona o fallback", conteudo == "resumo do fallback")
    _checar("3 cada modelo e' tentado so' 1 vez (sem retry em loop)",
             chamadas == ["modelo-principal", "modelo-fallback"], f"(chamadas={chamadas})")


def test_fallback_4_ambos_falham_mensagem_segura_sem_detalhe_tecnico():
    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        if modelo == "modelo-principal":
            return None, "cota"
        return None, "ConnectionError: HTTPSConnectionPool(host='api.groq.com', port=443): stack trace interno aqui"

    with patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            "chave", "modelo-principal", "modelo-fallback", _MSGS, 100,
        )
    _checar("4 ambos falham: conteudo None", conteudo is None)
    _checar("4 ambos falham: motivo e' um valor SEGURO (cota/indisponivel), nunca o texto cru da excecao",
             motivo in ("cota", "indisponivel"), f"(motivo={motivo!r})")
    _checar("4 ambos falham: motivo NAO contem detalhe tecnico (stack trace/host/porta)",
             "stack trace" not in str(motivo) and "ConnectionError" not in str(motivo) and "HTTPSConnectionPool" not in str(motivo),
             f"(motivo={motivo!r})")


def test_fallback_5_pular_principal_nao_tenta_modelo_ja_sabido_esgotado():
    chamadas = []

    def _fake_chamar_groq(chave, modelo, mensagens, max_tokens):
        chamadas.append(modelo)
        return "resumo do fallback", None

    with patch.object(resumir_mod, "_chamar_groq", side_effect=_fake_chamar_groq):
        conteudo, motivo, usou_fallback = _chamar_groq_com_fallback(
            "chave", "modelo-principal", "modelo-fallback", _MSGS, 100, pular_principal=True,
        )
    _checar("5 pular_principal=True nunca tenta o modelo principal",
             chamadas == ["modelo-fallback"], f"(chamadas={chamadas})")
    _checar("5 pular_principal=True ainda retorna o resultado do fallback normalmente", conteudo == "resumo do fallback")


def test_fallback_6_resumo_ja_existente_nao_chama_ia_de_novo():
    """Cache (ja' existente no projeto - esse teste so' confirma, nao
    reimplementa): chama ui.research_tab._linha_relatorio DE VERDADE
    (a funcao real da UI, nao uma reimplementacao da condicao) com um
    item que ja' tem resumo salvo - o link (PK de research_itens) ja' e'
    chave suficiente, nao precisa de identificador novo nenhum."""
    import ui.research_tab as research_tab_mod

    rel = {
        "link": "https://exemplo.com/1", "resumo": "resumo ja salvo", "titulo": "Titulo teste",
        "casa": "X", "tipo": "ACOES", "tickers": [], "data": "2026-10-01", "autor": "",
    }
    chamadas_ia = []
    with patch.object(research_tab_mod, "obter_resumo", side_effect=lambda *a, **k: chamadas_ia.append(1)):
        research_tab_mod._linha_relatorio(rel, permitir_resumo_auto=True)
    _checar("6 resumo ja existente: _linha_relatorio (funcao real da UI) nao chama obter_resumo",
             chamadas_ia == [], f"(chamadas_ia={chamadas_ia})")


def test_fallback_7_erro_de_transcript_e_erro_de_ia_tem_motivos_diferentes():
    """Erro de EXTRACAO de texto (obter_texto_relatorio - link bloqueado,
    PDF ilegivel, exige login) precisa continuar DISTINGUIVEL de erro de
    IA (cota/indisponivel) - nunca os dois virarem o mesmo motivo
    generico. obter_resumo nem chega a chamar resumir_com_groq se a
    extracao falhar primeiro."""
    chamadas_ia = []
    with patch.object(resumir_mod, "obter_texto_relatorio", return_value=(None, "conteúdo muito curto (provavelmente exige login)")), \
         patch.object(resumir_mod, "resumir_com_groq", side_effect=lambda *a, **k: chamadas_ia.append(1)), \
         patch.object(resumir_mod.ia_cache, "obter_cliente", return_value=None):
        resultado = obter_resumo("https://exemplo.com/1", "titulo", casa="X", tipo="ACOES")
    _checar("7 erro de extracao NAO chama a IA (nem chega la')", chamadas_ia == [], f"(chamadas_ia={chamadas_ia})")
    _checar("7 motivo de extracao e' distinto dos motivos de IA (cota/indisponivel)",
             resultado["motivo_indisponivel"] not in ("cota", "indisponivel"), f"(motivo={resultado['motivo_indisponivel']!r})")
    _checar("7 motivo de extracao preservado (nao substituido por generico)",
             resultado["motivo_indisponivel"] == "conteúdo muito curto (provavelmente exige login)")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE RESEARCH (deterministicos) PASSARAM")
