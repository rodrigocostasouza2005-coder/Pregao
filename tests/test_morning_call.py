# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pandas as pd
import jobs.morning_call as mc


_COT_INDISPONIVEL = lambda nome, ticker: ({"erro": "indisponível"}, f"- {nome}: indisponível")


def test_morning_call_independente_sem_news_e_macro():
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert "MORNING CALL" in texto
    assert "RESUMO EXECUTIVO" in texto
    assert "BRASIL" in texto
    assert "EXTERIOR" in texto
    assert "EMPRESAS E SETORES" in texto
    assert "TENDÊNCIAS E RISCOS" in texto
    assert "FONTES" in texto
    assert "carteira" not in texto.lower()
    assert "alerta" not in texto.lower()


def test_resumo_executivo_reporta_direcao_sem_inventar_numero():
    """RESUMO EXECUTIVO só repete direção/magnitude já calculada - nunca
    um número novo nem uma interpretação."""
    cot_alta = {"erro": None, "variacao_pct": 1.23}
    cot_queda = {"erro": None, "variacao_pct": -0.55}

    def fake(nome, ticker):
        cot = cot_alta if "Ibovespa" in nome else cot_queda
        return cot, f"- {nome}: linha"

    with patch.object(mc, "_obter_cotacao_fmt", side_effect=fake), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert "Ibovespa: alta de 1,23%" in texto
    assert "Dólar (USD/BRL): queda de 0,55%" in texto


def test_noticias_classificadas_por_regiao_e_ticker():
    """Reaproveita regiao/tickers já calculados por data/news.py - BR com
    ticker vai pra EMPRESAS E SETORES, BR sem ticker fica em BRASIL,
    INT fica em EXTERIOR. Nenhuma reclassificação própria."""
    noticias = [
        {"titulo": "PETR4 anuncia dividendo", "link": "https://x/1", "regiao": "BR", "tickers": ["PETR4"]},
        {"titulo": "Governo anuncia pacote fiscal", "link": "https://x/2", "regiao": "BR", "tickers": []},
        {"titulo": "Fed sinaliza postura sobre juros", "link": "https://x/3", "regiao": "INT", "tickers": []},
    ]
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=noticias):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))

    secao_empresas = texto.split("4. EMPRESAS E SETORES")[1].split("5. TENDÊNCIAS")[0]
    secao_brasil = texto.split("2. BRASIL")[1].split("3. EXTERIOR")[0]
    secao_exterior = texto.split("3. EXTERIOR")[1].split("4. EMPRESAS")[0]
    assert "PETR4 anuncia dividendo" in secao_empresas
    assert "PETR4 anuncia dividendo" not in secao_brasil
    assert "Governo anuncia pacote fiscal" in secao_brasil
    assert "Fed sinaliza postura sobre juros" in secao_exterior


def test_html_preserva_links_e_estrutura_minima():
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[
             {"titulo": "Manchete X", "link": "https://exemplo.com/a", "regiao": "INT", "tickers": []},
         ]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    corpo_html = mc.montar_morning_call_html(texto)
    assert "<h1" in corpo_html
    assert '<a href="https://exemplo.com/a">https://exemplo.com/a</a>' in corpo_html
    assert "<script" not in corpo_html
    assert "<li>Manchete X" in corpo_html


def test_focus_usa_ano_referencia_como_rotulo_sem_formatar_como_dinheiro():
    """Regressao 2026-10-15: Focus IPCA/Selic nao tem coluna 'data' (so
    Selic/CDI tem) - o codigo so conhecia 'data', entao toda linha de
    Focus caia no fallback 'data não informada'[:10] = 'data não i', e
    ano_referencia/numero_respondentes apareciam formatados como valor
    monetario (ex: '2.026,00' em vez de '2026')."""
    focus_ipca = pd.DataFrame({
        "ano_referencia": [2026, 2027],
        "mediana_pct": [5.22, 4.30],
        "media_pct": [5.21, 4.32],
        "numero_respondentes": [144, 144],
        "data_calculo": pd.to_datetime(["2026-10-09", "2026-10-09"]),
    })
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=focus_ipca), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert "data não i" not in texto
    assert "Focus IPCA (2026):" in texto
    assert "Focus IPCA (2027):" in texto
    assert "2.026,00" not in texto
    assert "numero_respondentes=144" in texto
    assert "mediana_pct=5,22" in texto


def test_executar_registra_tentativa_no_painel_saude(monkeypatch):
    """Regressao 2026-10-15: o job rodava no GitHub Actions e persistia em
    morning_call_execucoes, mas nunca aparecia no painel SAUDE DOS DADOS
    (nenhuma linha em coletores_status) - sem isso, uma falha de envio so'
    era visivel no log do Actions, nunca na UI do Pregao."""
    chamadas = []
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = mc.executar()

    assert codigo == 0
    assert len(chamadas) == 1
    args, kwargs = chamadas[0]
    assert args[0] == "MORNING CALL"
    assert kwargs["execucao_ok"] is True
    assert kwargs["erro"] is None


def test_executar_registra_falha_quando_envio_nao_funciona(monkeypatch):
    chamadas = []
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": False, "erro": "Resend HTTP 401"})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas.append((a, k)))

    codigo = mc.executar()

    assert codigo == 1
    assert chamadas[0][1]["execucao_ok"] is False
    assert chamadas[0][1]["erro"] == "Resend HTTP 401"


def test_executar_chama_self_test_de_persistencia_antes_de_tudo(monkeypatch):
    chamadas_diagnostico = []
    monkeypatch.setattr(
        mc, "diagnosticar_persistencia",
        lambda: chamadas_diagnostico.append(1) or {"ok": True, "etapa": "OK", "detalhe": ""},
    )
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)

    mc.executar()

    assert len(chamadas_diagnostico) == 1


class _ClientePregao:
    """Cliente falso só pra _ja_enviado_hoje: devolve `ja_enviado` pra
    qualquer combinação pregao+modo=AGENDADO+status=ENVIADO consultada."""

    def __init__(self, ja_enviado: bool):
        self._ja_enviado = ja_enviado
        self.inseriu = []

    def table(self, nome):
        return self

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        return type("R", (), {"data": [{"id": 1}] if self._ja_enviado else []})()

    def insert(self, payload):
        self.inseriu.append(payload)
        return self


def test_execucao_agendada_nao_duplica_envio_do_mesmo_pregao(monkeypatch):
    """Retry/reexecução da mesma execução AGENDADA no mesmo pregão não
    reenvia o e-mail - _ja_enviado_hoje já encontrou um ENVIADO anterior."""
    monkeypatch.delenv("MORNING_CALL_MODO", raising=False)
    cliente = _ClientePregao(ja_enviado=True)
    chamadas_envio = []
    chamadas_registro = []
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas_registro.append((a, k)))

    codigo = mc.executar()

    assert codigo == 0
    assert chamadas_envio == []  # nenhum e-mail novo foi enviado
    assert cliente.inseriu == []  # nenhuma linha nova de execução
    assert chamadas_registro[0][1]["execucao_ok"] is True


def test_modo_teste_ignora_deduplicacao_e_marca_assunto(monkeypatch):
    """Envio de TESTE (workflow_dispatch manual) nunca é bloqueado pela
    deduplicação do envio agendado, e o assunto diferencia os dois."""
    monkeypatch.setenv("MORNING_CALL_MODO", "TESTE")
    cliente = _ClientePregao(ja_enviado=True)  # já existe um AGENDADO hoje
    chamadas_envio = []
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    codigo = mc.executar()

    assert codigo == 0
    assert len(chamadas_envio) == 1
    assunto = chamadas_envio[0][0][0]
    assert "[TESTE]" in assunto
    assert cliente.inseriu[0]["modo"] == "TESTE"
    monkeypatch.delenv("MORNING_CALL_MODO", raising=False)
