# -*- coding: utf-8 -*-
"""Edição atrasada do Morning Call: o GitHub entregou o disparo das 08h às
12:55 em 21/10 e não entregou nenhum em 22/10. Edição fora do horário sai
marcada no assunto, no texto e no HTML; disparo AGENDADO depois do
fechamento não envia; disparo manual envia sempre."""
from datetime import datetime
from zoneinfo import ZoneInfo

import jobs.morning_call as mc

TZ_SP = ZoneInfo("America/Sao_Paulo")
_TEXTO = (
    "MORNING CALL — 22/10/2026\n"
    "Pregão | Briefing informativo\n"
    "\n"
    "Gerado em 22/10/2026 13:05 (horário de Brasília)\n"
    "\n"
    "1. RESUMO EXECUTIVO\n"
    "- Ibovespa: alta de 0,50%\n"
)


def test_edicao_no_horario_nao_tem_aviso():
    agora = datetime(2026, 10, 22, 8, 3, tzinfo=TZ_SP)
    assert mc._assunto(agora) == "[PREGÃO] Morning Call — 22/10/2026"
    assert mc._com_aviso_atraso(_TEXTO, agora) == _TEXTO
    assert "ATRASADA" not in mc.montar_morning_call_html(_TEXTO)


def test_edicao_atrasada_marca_assunto_texto_e_html():
    agora = datetime(2026, 10, 22, 13, 5, tzinfo=TZ_SP)
    assert mc._assunto(agora) == "[PREGÃO] Morning Call — 22/10/2026 (enviado às 13:05, com atraso)"
    texto = mc._com_aviso_atraso(_TEXTO, agora)
    linhas = texto.split("\n")
    # logo abaixo do "Gerado em", cabeçalho intacto
    assert linhas[0] == "MORNING CALL — 22/10/2026"
    assert linhas[3].startswith("Gerado em ")
    assert linhas[4].startswith("[AVISO] Edição gerada às 13:05")
    html = mc.montar_morning_call_html(texto)
    assert "ATRASADA" in html and "Edição gerada às 13:05" in html


def _executar_com(monkeypatch, agora, evento):
    registros, envios = [], []
    monkeypatch.setenv("GITHUB_EVENT_NAME", evento)
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["a@exemplo.com"])
    monkeypatch.setattr(mc, "_ja_enviado_hoje", lambda *_a, **_k: False)
    monkeypatch.setattr(mc, "_montar_anexo_pdf", lambda *_a, **_k: None)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: _TEXTO)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: registros.append(k))

    def _enviar(assunto, texto, html=None, destinatario=None, anexos=None):
        envios.append(assunto)
        return {"ok": True, "erro": None}

    monkeypatch.setattr(mc, "enviar_email", _enviar)
    return mc.executar(agora), registros, envios


def test_disparo_agendado_depois_do_fechamento_nao_envia(monkeypatch):
    codigo, registros, envios = _executar_com(monkeypatch, datetime(2026, 10, 22, 21, 32, tzinfo=TZ_SP), "schedule")
    assert envios == []
    assert codigo == 1
    assert registros[0]["execucao_ok"] is False
    assert "21:32" in registros[0]["erro"]


def test_disparo_manual_tardio_envia_marcado_como_atrasado(monkeypatch):
    codigo, _registros, envios = _executar_com(monkeypatch, datetime(2026, 10, 22, 21, 32, tzinfo=TZ_SP),
                                               "workflow_dispatch")
    assert codigo == 0
    assert envios == ["[PREGÃO] Morning Call — 22/10/2026 (enviado às 21:32, com atraso)"]


def test_disparo_agendado_atrasado_antes_do_corte_envia(monkeypatch):
    codigo, _registros, envios = _executar_com(monkeypatch, datetime(2026, 10, 22, 12, 55, tzinfo=TZ_SP), "schedule")
    assert codigo == 0
    assert envios == ["[PREGÃO] Morning Call — 22/10/2026 (enviado às 12:55, com atraso)"]


def test_edicao_sem_ia_fica_parcial_no_painel(monkeypatch):
    """Sem GROQ_API_KEY a edição sai só com manchetes - não pode aparecer
    como sucesso pleno no painel SAÚDE DOS DADOS."""
    monkeypatch.setattr(mc, "_montar_anexo_pdf", lambda *_a, **_k: {
        "nome": "x.pdf", "conteudo": b"%PDF", "tipo_mime": "application/pdf",
        "radar_setores": [], "sem_ia": "GROQ_API_KEY ausente"})
    registros = []
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["a@exemplo.com"])
    monkeypatch.setattr(mc, "_ja_enviado_hoje", lambda *_a, **_k: False)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: _TEXTO)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: registros.append(k))
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: {"ok": True, "erro": None})

    assert mc.executar(datetime(2026, 10, 22, 8, 3, tzinfo=TZ_SP)) == 0
    assert registros[-1]["parcial"] is True
    assert "GROQ_API_KEY" in registros[-1]["erro"]
