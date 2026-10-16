# -*- coding: utf-8 -*-
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch
import pandas as pd
import jobs.morning_call as mc

TZ_SP = ZoneInfo("America/Sao_Paulo")


def test_morning_call_independente_sem_news_e_macro():
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert "MORNING CALL" in texto
    assert "CENÁRIOS CONDICIONAIS" in texto
    assert "AGENDA DE HOJE" in texto
    assert "carteira" not in texto.lower()
    assert "alerta" not in texto.lower()


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
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=focus_ipca), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
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


# ---------------------------------------------------------------------
# AGENDA DE HOJE (data/eventos.py) - item 1 da missão.
# ---------------------------------------------------------------------

def _evento_exemplo(**overrides):
    base = {
        "ticker": "PETR4",
        "empresa": "Petrobras",
        "periodo": "3T26",
        "data": date(2026, 10, 14),
        "horario": None,
        "status": mc.STATUS_PRAZO_CVM,
        "fonte": "CVM — prazo regulatório (Instrução CVM 480/2009)",
        "origem_url": None,
        "tipo_evento": "RESULTADO",
        "coletado_em": datetime(2026, 10, 14, 6, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


def test_agenda_lista_evento_de_hoje_com_nota_de_prazo_cvm():
    """Evento PRAZO_CVM precisa deixar claro no texto que é um prazo
    MÁXIMO regulatório, não uma data confirmada pela empresa - exigência
    explícita da missão (não confundir o leitor)."""
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    evento_hoje = _evento_exemplo(data=agora.date())
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[evento_hoje]):
        texto = mc.montar_morning_call(agora)
    assert "3. AGENDA DE HOJE" in texto
    assert "Petrobras" in texto
    assert "PETR4" in texto
    assert "PRAZO CVM" in texto
    assert "NÃO é uma data anunciada pela empresa" in texto


def test_agenda_ignora_evento_de_outro_dia():
    """calcular_calendario_cacheado devolve o PRÓXIMO evento por ticker,
    não necessariamente hoje - a AGENDA DE HOJE só deve listar o que
    realmente cai na data de hoje."""
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    evento_futuro = _evento_exemplo(data=date(2026, 11, 20))
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[evento_futuro]):
        texto = mc.montar_morning_call(agora)
    assert "Nenhum evento relevante identificado para hoje." in texto
    assert "Petrobras" not in texto


def test_agenda_sem_nenhum_evento_diz_isso_explicitamente():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(agora)
    assert "3. AGENDA DE HOJE" in texto
    assert "Nenhum evento relevante identificado para hoje." in texto


def test_agenda_falha_de_leitura_cai_no_fallback_textual_sem_quebrar_email():
    """Mesmo padrão try/except + fallback textual já usado em NOTÍCIAS -
    uma falha no calendário nunca pode quebrar o e-mail inteiro."""
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", side_effect=RuntimeError("CVM fora do ar")):
        texto = mc.montar_morning_call(agora)
    assert "3. AGENDA DE HOJE" in texto
    assert "Agenda do dia indisponível nesta execução." in texto
    # a falha não pode ter derrubado as seções seguintes:
    assert "CENÁRIOS CONDICIONAIS" in texto
    assert "LIMITAÇÕES" in texto


# ---------------------------------------------------------------------
# MODO DE PREVIEW (sem envio real) - item 2 da missão.
# ---------------------------------------------------------------------

def test_gerar_preview_contem_todas_as_secoes_obrigatorias_sem_enviar_email():
    enviar_email_mock = MagicMock(side_effect=AssertionError("gerar_preview nunca deve enviar e-mail de verdade"))
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[{"titulo": "Manchete X", "link": "https://exemplo.com/x"}]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[_evento_exemplo(data=agora.date())]), \
         patch.object(mc, "enviar_email", enviar_email_mock):
        preview = mc.gerar_preview(agora)

    enviar_email_mock.assert_not_called()
    assert preview["valido"] is True
    assert preview["secoes_faltantes"] == []
    for secao in mc.SECOES_OBRIGATORIAS:
        assert secao in preview["texto"]
    assert preview["assunto"] == "[PREGÃO] Morning Call — 14/10/2026"
    assert "Manchete X" in preview["texto"]
    assert "https://exemplo.com/x" in preview["texto"]


def test_gerar_preview_marca_invalido_quando_falta_secao_obrigatoria():
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with patch.object(mc, "montar_morning_call", return_value="MORNING CALL — texto incompleto sem as seções"):
        preview = mc.gerar_preview(agora)
    assert preview["valido"] is False
    assert "1. MERCADOS" in preview["secoes_faltantes"]


# ---------------------------------------------------------------------
# IDEMPOTÊNCIA / DUPLICATA - item 3 da missão.
# ---------------------------------------------------------------------

def _cliente_fake_com_resultado(linhas):
    resp = MagicMock()
    resp.data = linhas
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value = resp
    return cliente


def test_ja_enviado_hoje_true_quando_ha_registro_enviado_no_dia():
    cliente = _cliente_fake_com_resultado([{"id": 1}])
    agora = datetime(2026, 10, 16, 9, tzinfo=TZ_SP)
    assert mc._ja_enviado_hoje(cliente, agora) is True
    cliente.table.assert_called_with("morning_call_execucoes")
    cliente.table.return_value.select.return_value.eq.assert_called_with("status", "ENVIADO")


def test_ja_enviado_hoje_false_quando_nao_ha_registro():
    cliente = _cliente_fake_com_resultado([])
    agora = datetime(2026, 10, 16, 9, tzinfo=TZ_SP)
    assert mc._ja_enviado_hoje(cliente, agora) is False


def test_ja_enviado_hoje_false_sem_cliente_supabase():
    assert mc._ja_enviado_hoje(None, datetime(2026, 10, 16, 9, tzinfo=TZ_SP)) is False


def test_ja_enviado_hoje_false_quando_consulta_lanca_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    assert mc._ja_enviado_hoje(cliente, datetime(2026, 10, 16, 9, tzinfo=TZ_SP)) is False


def test_executar_pula_envio_quando_ja_enviado_hoje_regressao_retry_duplicado(monkeypatch):
    """Regressão: um retry manual (ou "Re-run failed jobs" no GitHub
    Actions) rodando executar() de novo no MESMO dia depois de um
    ENVIADO com sucesso anterior NÃO pode mandar e-mail duplicado."""
    cliente = _cliente_fake_com_resultado([{"id": 1}])
    chamadas_envio = []
    chamadas_registro = []

    def _montar_nao_deveria_ser_chamado(*_a, **_k):
        raise AssertionError("não deveria montar o texto quando já foi enviado hoje")

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "montar_morning_call", _montar_nao_deveria_ser_chamado)
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas_registro.append((a, k)))

    codigo = mc.executar()

    assert codigo == 0
    assert chamadas_envio == []
    # o insert de uma NOVA linha ENVIADO nunca deve ter sido tentado:
    cliente.table.return_value.insert.assert_not_called()


def test_executar_envia_normalmente_quando_nao_enviado_ainda_hoje(monkeypatch):
    cliente = _cliente_fake_com_resultado([])
    chamadas_envio = []

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    codigo = mc.executar()

    assert codigo == 0
    assert len(chamadas_envio) == 1
    cliente.table.return_value.insert.assert_called_once()


def test_executar_envia_versao_html_junto_da_versao_texto(monkeypatch):
    """Mission: 'Produza HTML compatível com clientes de e-mail e uma
    alternativa em texto simples' - enviar_email precisa receber html=
    não vazio, nunca só o texto puro."""
    cliente = _cliente_fake_com_resultado([])
    chamadas_envio = []

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "1. MERCADOS\n- Ibovespa: 140.000")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    mc.executar()

    assert len(chamadas_envio) == 1
    _args, kwargs = chamadas_envio[0]
    assert kwargs.get("html"), "enviar_email foi chamado sem a versão HTML"
    assert "<h2" in kwargs["html"]


def test_montar_morning_call_html_contem_as_mesmas_secoes_do_texto():
    texto = (
        "MORNING CALL — 16/10/2026\n"
        "1. MERCADOS\n- Ibovespa: 140.000\n"
        "4. NOTÍCIAS\n- Manchete com link — https://exemplo.com/a?x=1&y=2\n"
        "LIMITAÇÕES\n- Conteúdo informativo."
    )
    html_gerado = mc.montar_morning_call_html(texto)
    assert "<h2" in html_gerado and "1. MERCADOS" in html_gerado
    assert "LIMITAÇÕES" in html_gerado
    # URL crua vira link clicável, preservando o destino real.
    assert '<a href="https://exemplo.com/a?x=1&amp;y=2">' in html_gerado


def test_montar_morning_call_html_escapa_conteudo_perigoso():
    """Título/manchete de notícia é texto de fonte externa - nunca pode
    injetar HTML/script no e-mail gerado."""
    texto = "4. NOTÍCIAS\n- <script>alert(1)</script> & \"aspas\""
    html_gerado = mc.montar_morning_call_html(texto)
    assert "<script>" not in html_gerado
    assert "&lt;script&gt;" in html_gerado


def test_montar_morning_call_nao_quebra_numa_segunda_feira_apos_fim_de_semana():
    """Mission: 'Determine corretamente o último pregão encerrado,
    inclusive às segundas-feiras e após feriados' - o conteúdo nunca
    assume 'ontem foi dia útil': cada seção já lê o que o provedor
    devolveu (última barra real/cache real), sem recalcular datas aqui."""
    segunda = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)  # 19/10/2026 é segunda-feira
    assert segunda.weekday() == 0
    with patch.object(mc, "_linha_cotacao", side_effect=lambda nome, ticker: f"- {nome}: indisponível"), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(segunda)
    assert "19/10/2026" in texto
    faltantes = [secao for secao in mc.SECOES_OBRIGATORIAS if secao not in texto]
    assert not faltantes
