# -*- coding: utf-8 -*-
"""Testes da LEITURA DO PREGÃO + PARA INVESTIGAR (ui/visao_geral.py,
redesign terminal 2026-10-27) - substituem os antigos 4 painéis ANALISTA
DE MERCADO separados (resumo executivo/movimentos/oportunidades/
cenários), agora condensados: _painel_leitura_pregao (chips DADO/
NOTÍCIA/AGENDA + headline) e _painel_para_investigar (top 2 oportunidades
+ cenário principal). Mocka data.sintese_mercado.obter_sintese_mercado
(única função de IA que estes painéis chamam) - nenhuma chamada de
rede/IA real. Cobre os 3 estados honestos: sem síntese (ok=False),
síntese ANTERIOR usada como fallback (atual=False, rotulada), síntese
atual (atual=True) - e que os chips baseados em DADO (concentração
setorial, agenda) funcionam mesmo com a síntese por IA indisponível,
sem degradar silenciosamente.

st.markdown/st.columns funcionam em "bare mode" (fora de ScriptRunContext
real) sem lançar exceção - mesmo padrão dos outros testes de UI deste
projeto."""
from unittest.mock import patch

import ui.visao_geral as vg

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_SEM_SINTESE = {"ok": False, "motivo": "GROQ_API_KEY não configurada"}

_ATUAL = {
    "ok": True, "atual": True, "gerado_em": "2026-10-26T12:00:00+00:00", "modelo": "openai/gpt-oss-20b",
    "fontes_indisponiveis": ["calendário: timeout"],
    "dados": {
        "resumo_executivo": {"texto": "Ibovespa opera em alta.", "ressalvas": "Calendário indisponível no momento."},
        "movimentos": [
            {"evento": "Ibovespa sobe 1,2%", "fonte": "B3 (cotação)", "data_fonte": "2026-10-26",
             "por_que_importa": "acompanha alta global", "impacto_possivel": "setores exportadores",
             "horizonte": "curto prazo", "confianca": "media", "confianca_motivo": "1 fonte"},
        ],
        "oportunidades_riscos": [
            {"ativo_ou_setor": "Petróleo", "catalisador": "alta do barril", "argumento_favoravel": "receita maior",
             "argumento_contrario": "custo de insumos", "acompanhar": "preço do Brent", "fonte": "Reuters",
             "data_fonte": "2026-10-26"},
        ],
        "cenarios": [
            {"tipo": "principal", "cenario": "Alta se sustenta", "condicao": "exterior seguir positivo",
             "sinalizadores": "futuros dos EUA"},
            {"tipo": "alternativo", "cenario": "Reversão", "condicao": "exterior perder força",
             "sinalizadores": "abertura americana"},
        ],
        "observar_proximas_sessoes": [
            {"item": "Preço do Brent", "motivo": "catalisador do dia", "fonte": "Reuters", "data_fonte": "2026-10-26"},
        ],
        "o_que_nao_sabemos": ["Sem dado recente sobre o Focus Selic."],
    },
}

_ANTERIOR = {
    "ok": True, "atual": False, "gerado_em": "2026-10-25T08:00:00+00:00", "modelo": "openai/gpt-oss-20b",
    "fontes_indisponiveis": [], "motivo_atual_indisponivel": "cota",
    "dados": {
        "resumo_executivo": {"texto": "Síntese de ontem.", "ressalvas": ""},
        "movimentos": [], "oportunidades_riscos": [], "o_que_nao_sabemos": [],
    },
}

_ALTAS_CONCENTRADAS = [
    {"ticker": "PETR4", "variacao_pct": 3.1, "setor": "Petróleo e Gás"},
    {"ticker": "PRIO3", "variacao_pct": 2.4, "setor": "Petróleo e Gás"},
]
_BAIXAS_CONCENTRADAS = [
    {"ticker": "CSAN3", "variacao_pct": -2.0, "setor": "Petróleo e Gás"},
]


def test_tempo_relativo_sem_iso_nao_inventa_horario():
    assert vg._tempo_relativo(None) == "horário indisponível"
    assert vg._tempo_relativo("não é uma data") == "horário indisponível"


def test_tempo_relativo_com_iso_recente_nao_lanca_excecao():
    from datetime import datetime, timezone
    resultado = vg._tempo_relativo(datetime.now(timezone.utc).isoformat())
    assert resultado


def test_concentracao_setorial_detecta_maioria():
    with patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS_CONCENTRADAS, _BAIXAS_CONCENTRADAS)):
        resultado = vg._concentracao_setorial()
    assert resultado is not None
    setor, qtd, total = resultado
    assert setor == "Petróleo e Gás"
    assert qtd == 3
    assert total == 3


def test_concentracao_setorial_sem_maioria_retorna_none():
    dispersos = [
        {"ticker": "PETR4", "variacao_pct": 3.1, "setor": "Petróleo e Gás"},
        {"ticker": "ITUB4", "variacao_pct": 2.0, "setor": "Bancos"},
    ]
    with patch.object(vg, "obter_altas_baixas", return_value=(dispersos, [])):
        assert vg._concentracao_setorial() is None


def test_proximo_evento_watchlist_vazia_retorna_none():
    assert vg._proximo_evento_watchlist({"watchlist": []}) is None


def test_proximo_evento_watchlist_escolhe_o_mais_proximo():
    from datetime import date
    eventos = [
        {"ticker": "VALE3", "data": date(2026, 12, 1), "status": "CONFIRMADO"},
        {"ticker": "PETR4", "data": date(2026, 11, 5), "status": "CONFIRMADO"},
    ]
    with patch.object(vg, "calcular_calendario_cacheado", return_value=eventos):
        resultado = vg._proximo_evento_watchlist({"watchlist": ["VALE3", "PETR4"]})
    assert resultado["ticker"] == "PETR4"


def test_leitura_pregao_sem_sintese_usa_so_dados_sem_quebrar():
    with patch.object(vg, "obter_sintese_mercado", return_value=_SEM_SINTESE), \
         patch.object(vg, "obter_altas_baixas", return_value=([], [])), \
         patch.object(vg, "obter_mais_negociados", return_value=[]), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None):
        vg._painel_leitura_pregao(_PREFS)  # não deve lançar exceção


def test_leitura_pregao_atual_renderiza_chips_e_headline():
    with patch.object(vg, "obter_sintese_mercado", return_value=_ATUAL), \
         patch.object(vg, "obter_altas_baixas", return_value=(_ALTAS_CONCENTRADAS, _BAIXAS_CONCENTRADAS)), \
         patch.object(vg, "obter_mais_negociados", return_value=[
             {"ticker": "PETR4", "volume_financeiro": 4.2e9},
         ]), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None):
        vg._painel_leitura_pregao(_PREFS)


def test_leitura_pregao_anterior_nao_lanca_excecao():
    with patch.object(vg, "obter_sintese_mercado", return_value=_ANTERIOR), \
         patch.object(vg, "obter_altas_baixas", return_value=([], [])), \
         patch.object(vg, "obter_mais_negociados", return_value=[]), \
         patch.object(vg, "_proximo_evento_watchlist", return_value=None):
        vg._painel_leitura_pregao(_PREFS)


def test_para_investigar_sem_sintese_nao_lanca_excecao():
    with patch.object(vg, "obter_sintese_mercado", return_value=_SEM_SINTESE):
        vg._painel_para_investigar(_PREFS)


def test_para_investigar_com_item_renderiza_sem_excecao():
    with patch.object(vg, "obter_sintese_mercado", return_value=_ATUAL):
        vg._painel_para_investigar(_PREFS)


def test_para_investigar_vazio_nao_lanca_excecao():
    vazio = {**_ATUAL, "dados": {**_ATUAL["dados"], "oportunidades_riscos": [], "cenarios": []}}
    with patch.object(vg, "obter_sintese_mercado", return_value=vazio):
        vg._painel_para_investigar(_PREFS)


def test_registro_paineis_vazio_sem_drag_nesta_aba():
    # redesign terminal (2026-10-27): VISAO GERAL virou cockpit fixo,
    # sem workspace modular - REGISTRO_PAINEIS fica vazio de proposito
    # (nao removido, pra nao quebrar o import em app.py/CONFIG).
    assert vg.REGISTRO_PAINEIS == []
