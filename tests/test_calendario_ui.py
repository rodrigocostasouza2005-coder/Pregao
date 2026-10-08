# -*- coding: utf-8 -*-
"""Testes da fase CALENDARIO V3 (2026-10-02): ui/calendario_tab.py -
separacao visual entre PROXIMOS RESULTADOS (CONFIRMADO/ESTIMADO) e
PRAZOS CVM (PRAZO_CVM) - regra explicita: PRAZO CVM != data de
divulgacao. Mocka data.eventos.calcular_calendario (mesma funcao que a
UI real usa) - nao faz chamada de rede nem de IA.

Uso: python tests/test_calendario_ui.py (python do .venv do projeto)."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.calendario_tab as calendario_tab_mod
from data.eventos import STATUS_CONFIRMADO, STATUS_ESTIMADO, STATUS_PRAZO_CVM

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


def _evento(ticker="PETR4", periodo="3T26", status=STATUS_PRAZO_CVM, data_evento=None, fonte="fonte teste"):
    return {
        "ticker": ticker, "empresa": "EMPRESA TESTE", "periodo": periodo,
        "data": data_evento or date(2026, 11, 14), "horario": None,
        "status": status, "fonte": fonte, "origem_url": None, "tipo_evento": "RESULTADO",
        "coletado_em": None,
    }


def _capturar_markdown(fn, *args, **kwargs):
    capturado = []
    with patch.object(calendario_tab_mod.st, "markdown", side_effect=lambda html, **k: capturado.append(html)):
        fn(*args, **kwargs)
    return capturado


def test_1_somente_prazo_cvm_mostra_mensagem_de_nenhum_resultado_confirmado():
    prefs = {"watchlist": ["PETR4"]}
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=[_evento(status=STATUS_PRAZO_CVM)]):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("1a mensagem 'Nenhuma data de divulgação confirmada.' aparece quando so' ha PRAZO_CVM",
             "Nenhuma data de divulgação confirmada." in texto)
    _checar("1b subheader PRAZOS CVM aparece listando o evento", "PRAZOS CVM" in texto and "PETR4" in texto)
    _checar("1c PRAZO CVM nunca aparece sob o rotulo PRÓXIMOS RESULTADOS",
             texto.index("PRÓXIMOS RESULTADOS") < texto.index("PRAZOS CVM"))


def test_2_confirmado_aparece_em_proximos_resultados_nao_em_prazos_cvm():
    prefs = {"watchlist": ["PETR4"]}
    eventos = [_evento(status=STATUS_CONFIRMADO, fonte="Petrobras RI", data_evento=date(2026, 10, 20))]
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("2a CONFIRMADO aparece na lista (nao esconde o evento)", "PETR4" in texto and "CONFIRMADO" in texto)
    _checar("2b mensagem de 'nenhuma data confirmada' NAO aparece quando ha' CONFIRMADO", "Nenhuma data de divulgação confirmada." not in texto)
    _checar("2c subheader PRAZOS CVM NAO aparece (nenhum evento PRAZO_CVM nesta lista)", "PRAZOS CVM" not in texto)


def test_3_estimado_tambem_vai_pra_proximos_resultados():
    prefs = {"watchlist": ["VALE3"]}
    eventos = [_evento(ticker="VALE3", status=STATUS_ESTIMADO, fonte="Consenso de mercado")]
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    _checar("3 ESTIMADO aparece em PRÓXIMOS RESULTADOS (nao em PRAZOS CVM)",
             "VALE3" in texto and "PRAZOS CVM" not in texto)


def test_4_mix_confirmado_e_prazo_cvm_fica_em_secoes_diferentes():
    prefs = {"watchlist": ["PETR4", "VALE3"]}
    eventos = [
        _evento(ticker="PETR4", status=STATUS_CONFIRMADO, fonte="Petrobras RI", data_evento=date(2026, 10, 20)),
        _evento(ticker="VALE3", status=STATUS_PRAZO_CVM, data_evento=date(2026, 11, 14)),
    ]
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=eventos):
        capturado = _capturar_markdown(calendario_tab_mod._painel_proximos_watchlist, prefs)
    texto = " ".join(capturado)
    idx_resultados = texto.index("PRÓXIMOS RESULTADOS")
    idx_prazos = texto.index("PRAZOS CVM")
    idx_petr4 = texto.index("PETR4")
    idx_vale3 = texto.index("VALE3")
    _checar("4 PETR4 (CONFIRMADO) aparece ANTES do subheader PRAZOS CVM",
             idx_resultados < idx_petr4 < idx_prazos)
    _checar("4b VALE3 (PRAZO_CVM) aparece DEPOIS do subheader PRAZOS CVM",
             idx_prazos < idx_vale3)


def test_5_mensagem_de_periodo_vazio_na_agenda():
    prefs = {"watchlist": ["PETR4"]}
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(calendario_tab_mod.st, "columns", return_value=(_FakeCol(), _FakeCol())), \
         patch.object(calendario_tab_mod.st, "pills", return_value=None), \
         patch.object(calendario_tab_mod.st, "spinner", return_value=_FakeCtx()):
        capturado = _capturar_markdown(calendario_tab_mod._painel_agenda, prefs)
    texto = " ".join(capturado)
    _checar("5 mensagem exata 'Nenhum evento no período.' (sem 'selecionado')",
             "Nenhum evento no período." in texto)


class _FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_6_detalhe_prazo_cvm_mostra_aviso_explicito():
    evento = _evento(status=STATUS_PRAZO_CVM)
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("6 detalhe de PRAZO_CVM mostra o aviso obrigatório",
             "Não representa necessariamente a data de divulgação do resultado" in texto)


def test_7_detalhe_confirmado_nao_mostra_aviso_de_prazo():
    evento = _evento(status=STATUS_CONFIRMADO, fonte="Petrobras RI")
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._detalhe_evento, evento)
    texto = " ".join(capturado)
    _checar("7 detalhe de CONFIRMADO NAO mostra o aviso de prazo regulatório",
             "Não representa necessariamente a data de divulgação do resultado" not in texto)


# ============================================================
# FASE "HUB DO EVENTO" (2026-10-02; redesign visual 2026-10-05):
# RESEARCH/NEWS/DOCUMENTOS(CVM)/HISTORICO do ticker - reaproveita
# obter_documentos_cvm/obter_noticias/listar_itens (mesmas funcoes
# cacheadas que EQUITY/CVM/NEWS/RESEARCH ja usam), zero chamada de IA,
# zero fonte nova. Ate 2026-10-05 as 4 secoes ficavam sempre visiveis
# dentro de _detalhe_evento (dump); agora _detalhe_evento so' mostra o
# metadado compacto do evento (ver testes 6/7, inalterados) e o
# conteudo de contexto virou abas em _painel_contexto/_dados_contexto,
# 1 secao visivel por vez, so' aparecendo quando ha' dado.
# ============================================================

_DOC_CVM_GENERICO = {
    "ticker": "PETR4", "tipo": "COMUNICADO", "tipo_label": "COMUNICADO",
    "categoria_original": "Comunicado ao Mercado", "assunto": "Aviso de fato relevante",
    "data": "2026-09-28", "data_referencia": None, "link": "https://cvm.example/doc1", "destaque": False,
}
_DOC_CVM_RESULTADO_ANTIGO = {
    "ticker": "PETR4", "tipo": "RESULTADOS", "tipo_label": "RESULTADOS",
    "categoria_original": "Dados Econômico-Financeiros", "assunto": "Press-release",
    "data": "2026-07-10", "data_referencia": "2026-06-30", "link": "https://cvm.example/doc2", "destaque": False,
}
_NOTICIA = {"ticker": "PETR4", "titulo": "Petrobras anuncia investimento", "data": "2026-09-29",
            "link": "https://news.example/n1", "selo": "MENÇÃO", "score": 1, "veiculos": ["Veículo Teste"], "tickers": ["PETR4"]}
_RELATORIO = {"casa": "Genial Analisa", "titulo": "PETR4: tese de investimento", "data": "2026-09-27",
              "autor": "", "tipo": "ACOES", "tickers": ["PETR4"], "link": "https://research.example/r1",
              "resumo": None, "modelo_resumo": None, "preco_alvo": None, "recomendacao": None}


def test_8_dados_contexto_busca_as_4_fontes_sem_n_mais_1():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO, _DOC_CVM_RESULTADO_ANTIGO]) as mock_cvm, \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]):
        dados = calendario_tab_mod._dados_contexto(evento["ticker"])
    _checar("8a RESEARCH tem o relatorio relacionado", len(dados["RESEARCH"]) == 1 and dados["RESEARCH"][0]["titulo"] == "PETR4: tese de investimento")
    _checar("8b NEWS tem a noticia relacionada", len(dados["NEWS"]) == 1 and dados["NEWS"][0]["titulo"] == "Petrobras anuncia investimento")
    _checar("8c DOCUMENTOS tem os 2 documentos CVM (generico + resultado antigo)", len(dados["DOCUMENTOS"]) == 2)
    _checar("8d HISTÓRICO so' tem o documento tipo RESULTADOS (filtra o generico)",
             len(dados["HISTÓRICO"]) == 1 and dados["HISTÓRICO"][0]["data_referencia"] == "2026-06-30")
    _checar("8e ordem das chaves do dict é RESEARCH, NEWS, DOCUMENTOS, HISTÓRICO (pedido explícito)",
             list(dados.keys()) == ["RESEARCH", "NEWS", "DOCUMENTOS", "HISTÓRICO"])
    _checar("8f obter_documentos_cvm chamado so' 1 VEZ (DOCUMENTOS + HISTÓRICO reaproveitam a mesma busca, sem N+1)",
             mock_cvm.call_count == 1, f"(call_count={mock_cvm.call_count})")


def test_9_dados_contexto_fonte_vazia_fica_lista_vazia_nao_erro():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        dados = calendario_tab_mod._dados_contexto(evento["ticker"])
    _checar("9a RESEARCH vazio (sem relatório relacionado)", dados["RESEARCH"] == [])
    _checar("9b NEWS vazio (sem notícia relacionada)", dados["NEWS"] == [])
    _checar("9c DOCUMENTOS tem o documento genérico", len(dados["DOCUMENTOS"]) == 1)
    _checar("9d HISTÓRICO vazio (documento genérico não é tipo RESULTADOS)", dados["HISTÓRICO"] == [])


def test_10_painel_contexto_nao_mostra_nada_quando_ticker_sem_dado_nenhum():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        capturado = _capturar_markdown(calendario_tab_mod._painel_contexto, evento)
    _checar("10a nenhum markdown (nem o titulo CONTEXTO) quando as 4 fontes estao vazias", capturado == [])

    # fonte CVM indisponivel (None, nao []) tambem precisa degradar pra
    # "sem dado" sem quebrar (achado real: obter_documentos_cvm pode
    # retornar None)
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=None), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[]):
        try:
            capturado2 = _capturar_markdown(calendario_tab_mod._painel_contexto, evento)
            ok = True
        except Exception as e:
            ok = False
            print("      excecao:", e)
    _checar("10b fonte CVM indisponível (None) não quebra o painel de contexto", ok)
    if ok:
        _checar("10c fonte CVM indisponível (None) também não mostra CONTEXTO (nunca secao vazia)", capturado2 == [])


def test_11_painel_contexto_mostra_abas_com_contagem_e_links_clicaveis():
    evento = _evento()
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO, _DOC_CVM_RESULTADO_ANTIGO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]), \
         patch.object(calendario_tab_mod.st, "pills", return_value="RESEARCH") as mock_pills:
        capturado = _capturar_markdown(calendario_tab_mod._painel_contexto, evento)
    texto = " ".join(capturado)
    _checar("11a titulo CONTEXTO aparece", "CONTEXTO" in texto)
    _checar("11b opcoes de aba oferecidas (so' as 4, com contagem) na ordem certa",
             mock_pills.call_args.args[1] == ["RESEARCH", "NEWS", "DOCUMENTOS", "HISTÓRICO"])
    _checar("11c aba selecionada (RESEARCH) renderiza seu conteudo com link pra URL original",
             "tese de investimento" in texto and "href='https://research.example/r1'" in texto)
    _checar("11d aba NAO selecionada (NEWS) nao renderiza conteudo nesta chamada (so' 1 aba por vez)",
             "Petrobras anuncia investimento" not in texto)
    _checar("11e link abre em nova aba (target='_blank', nunca navega pra fora do Pregão)",
             "target='_blank'" in texto)

    # troca de aba (NEWS) renderiza NEWS, nao RESEARCH - confirma que cada
    # renderizador individual (_render_contexto_*) funciona com link correto
    for chave, link_esperado, trecho_esperado in [
        ("NEWS", "https://news.example/n1", "Petrobras anuncia investimento"),
        ("DOCUMENTOS", "https://cvm.example/doc1", "Aviso de fato relevante"),
        ("HISTÓRICO", "https://cvm.example/doc2", "ref. 2026-06-30"),
    ]:
        with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO, _DOC_CVM_RESULTADO_ANTIGO]), \
             patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
             patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]), \
             patch.object(calendario_tab_mod.st, "pills", return_value=chave):
            capturado_aba = _capturar_markdown(calendario_tab_mod._painel_contexto, evento)
        texto_aba = " ".join(capturado_aba)
        _checar(f"11f aba {chave} selecionada renderiza seu conteudo", trecho_esperado in texto_aba)
        _checar(f"11g aba {chave} link aponta pra URL original", f"href='{link_esperado}'" in texto_aba)


def test_12_ausencia_de_chamadas_de_ia():
    evento = _evento()
    chamadas_ia = []
    # research_tab.obter_resumo e resumir_com_groq sao os unicos pontos de
    # IA do projeto relacionados a ticker/research - garantir que o hub do
    # calendario nunca os importa/chama, mesmo com RESEARCH relacionado
    import data.research.resumir as resumir_mod
    with patch.object(calendario_tab_mod, "obter_documentos_cvm", return_value=[_DOC_CVM_GENERICO]), \
         patch.object(calendario_tab_mod, "obter_noticias", return_value=[_NOTICIA]), \
         patch.object(calendario_tab_mod, "listar_itens", return_value=[_RELATORIO]), \
         patch.object(resumir_mod, "resumir_com_groq", side_effect=lambda *a, **k: chamadas_ia.append(1)), \
         patch.object(resumir_mod, "obter_resumo", side_effect=lambda *a, **k: chamadas_ia.append(1)):
        _capturar_markdown(calendario_tab_mod._painel_contexto, evento)
    _checar("12 nenhuma chamada de IA (resumir_com_groq/obter_resumo) acontece ao montar o hub do evento",
             chamadas_ia == [], f"(chamadas_ia={chamadas_ia})")


# ============================================================
# REDESIGN VISUAL (2026-10-05): grade mensal/semanal (calendar.py,
# stdlib - sem dependencia nova) + auto-seleção do dia/evento mais
# relevante. Funções puras, sem Streamlit - testáveis direto.
# ============================================================

def test_13_semanas_do_mes_cobre_o_mes_inteiro_em_semanas_de_7_dias_seg_a_dom():
    semanas = calendario_tab_mod._semanas_do_mes(2026, 10)
    _checar("13a cada semana tem exatamente 7 dias", all(len(s) == 7 for s in semanas))
    _checar("13b primeiro dia de cada semana é segunda-feira (weekday()==0)",
             all(s[0].weekday() == 0 for s in semanas))
    _checar("13c todos os dias de outubro/2026 estão cobertos por alguma semana",
             all(any(d.year == 2026 and d.month == 10 and d.day == dia for s in semanas for d in s) for dia in range(1, 32)))


def test_14_semana_atual_e_1_semana_seg_a_dom_contendo_hoje():
    hoje = date(2026, 10, 5)  # segunda-feira
    semanas = calendario_tab_mod._semana_atual(hoje)
    _checar("14a retorna exatamente 1 semana", len(semanas) == 1)
    _checar("14b a semana contém 'hoje'", hoje in semanas[0])
    _checar("14c a semana começa numa segunda-feira", semanas[0][0].weekday() == 0)


def test_15_dia_mais_relevante_prioriza_o_primeiro_futuro_a_partir_de_hoje():
    hoje = date(2026, 10, 5)
    datas = [date(2026, 10, 1), date(2026, 10, 29), date(2026, 11, 5)]
    _checar("15a primeiro dia >= hoje é escolhido (29/10, nao 01/10 que já passou)",
             calendario_tab_mod._dia_mais_relevante(datas, hoje) == date(2026, 10, 29))
    _checar("15b sem nenhuma data, retorna None (nunca inventa um dia)",
             calendario_tab_mod._dia_mais_relevante([], hoje) is None)
    _checar("15c so' datas passadas -> cai pra mais recente delas (nunca fica sem selecao se ha' evento)",
             calendario_tab_mod._dia_mais_relevante([date(2026, 9, 1), date(2026, 9, 20)], hoje) == date(2026, 9, 20))


def test_16_abev3_suzb3_aparecem_confirmados_na_grade_quando_filtro_permite():
    """Integracao leve: confirma que os eventos reais ja' validados em
    sessoes anteriores (ABEV3 29/10/2026 e SUZB3 05/11/2026, ambos
    CONFIRMADO) continuam chegando corretos ate' a camada que alimenta
    a grade (agrupamento por data) - mocka so' calcular_calendario
    (fronteira UI<->dados), sem rede."""
    eventos = [
        _evento(ticker="ABEV3", status=STATUS_CONFIRMADO, fonte="Ambev RI", data_evento=date(2026, 10, 29)),
        _evento(ticker="SUZB3", status=STATUS_CONFIRMADO, fonte="Suzano RI", data_evento=date(2026, 11, 5)),
    ]
    eventos_por_data = {}
    for e in eventos:
        eventos_por_data.setdefault(e["data"], []).append(e)
    _checar("16a ABEV3 agrupado em 29/10/2026", eventos_por_data[date(2026, 10, 29)][0]["ticker"] == "ABEV3")
    _checar("16b SUZB3 agrupado em 05/11/2026", eventos_por_data[date(2026, 11, 5)][0]["ticker"] == "SUZB3")
    _checar("16c ambos continuam CONFIRMADO (nao regredem pra PRAZO_CVM na camada de UI)",
             all(e["status"] == STATUS_CONFIRMADO for data in eventos_por_data.values() for e in data))


# ============================================================
# DADOS STALE (2026-10-06): "atualizado há Xh" ganha sinalizacao
# (desatualizado=True) quando a idade do snapshot passa de
# _LIMIAR_SNAPSHOT_DESATUALIZADO_H - ainda discreto (so' muda a cor via
# classe CSS, pedido explicito do Rodrigo), nunca vira alarme grande.
# ============================================================

def _snapshot_com_idade(horas: float) -> dict:
    momento = datetime.now(timezone.utc) - timedelta(hours=horas)
    return {"eventos": [], "atualizado_em": momento.isoformat()}


def test_17_rotulo_atualizacao_recente_nao_sinaliza_desatualizado():
    with patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value=_snapshot_com_idade(2)):
        resultado = calendario_tab_mod._rotulo_atualizacao()
    _checar("17a snapshot de 2h -> nao desatualizado", resultado is not None and resultado[1] is False)
    _checar("17b texto mostra horas", "2h" in resultado[0], f"(texto={resultado[0]!r})")


def test_18_rotulo_atualizacao_velho_sinaliza_desatualizado():
    with patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value=_snapshot_com_idade(72)):
        resultado = calendario_tab_mod._rotulo_atualizacao()
    _checar("18a snapshot de 72h (> limiar de 48h) -> sinaliza desatualizado", resultado is not None and resultado[1] is True)
    _checar("18b texto mostra dias", "d" in resultado[0], f"(texto={resultado[0]!r})")


def test_19_rotulo_atualizacao_logo_abaixo_do_limiar_nao_sinaliza():
    # 47.9h (nao exatamente 48h - o tempo real que passa entre montar o
    # snapshot e _rotulo_atualizacao calcular "agora" tornaria um teste
    # "exatamente 48h" instavel/flaky por alguns milissegundos) - prova
    # que o limiar e' > (estrito), nao >=, com folga segura pro teste
    with patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value=_snapshot_com_idade(47.9)):
        resultado = calendario_tab_mod._rotulo_atualizacao()
    _checar("19 logo abaixo do limiar (47.9h de 48h) -> ainda NAO desatualizado",
             resultado is not None and resultado[1] is False)


def test_20_rotulo_atualizacao_sem_snapshot_retorna_none():
    with patch.object(calendario_tab_mod, "obter_snapshot_calendario", return_value=None):
        resultado = calendario_tab_mod._rotulo_atualizacao()
    _checar("20 sem snapshot nenhum -> None (nunca afirma uma 'ultima atualizacao' que nao existe)", resultado is None)


def test_21_painel_agenda_usa_classe_css_de_alerta_quando_desatualizado():
    with patch.object(calendario_tab_mod, "_rotulo_atualizacao", return_value=("atualizado há 3d", True)), \
         patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(calendario_tab_mod.st, "columns", return_value=(_FakeCol(), _FakeCol())), \
         patch.object(calendario_tab_mod.st, "pills", return_value=None), \
         patch.object(calendario_tab_mod.st, "spinner", return_value=_FakeCtx()):
        capturado = _capturar_markdown(calendario_tab_mod._painel_agenda, {"watchlist": ["PETR4"]})
    texto = " ".join(capturado)
    _checar("21 classe de alerta aplicada quando _rotulo_atualizacao sinaliza desatualizado",
             "cal-atualizado-alerta" in texto)


def test_22_legenda_de_escopo_aparece_no_filtro_padrao_watchlist():
    # achado da auditoria de cobertura (2026-10-08): o CALENDARIO "parecia"
    # mostrar so' 2-3 empresas porque o filtro padrao e' MINHA WATCHLIST e a
    # watchlist padrao (config.TICKERS_PADRAO) tem so' 3 tickers - nao e'
    # bug de coleta/parsing/dedup. Essa legenda deixa o escopo explicito.
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(calendario_tab_mod.st, "columns", return_value=(_FakeCol(), _FakeCol())), \
         patch.object(calendario_tab_mod.st, "pills", return_value=None), \
         patch.object(calendario_tab_mod.st, "spinner", return_value=_FakeCtx()):
        capturado = _capturar_markdown(calendario_tab_mod._painel_agenda, {"watchlist": ["PETR4", "VALE3"]})
    texto = " ".join(capturado)
    total_universo = len(calendario_tab_mod.config.IBOVESPA_SETORES)
    _checar("22a legenda menciona o tamanho real da watchlist (2 ativos)", "2 ativos" in texto, f"(texto={texto!r})")
    _checar("22b legenda aponta pro TODOS com o total real do universo",
             f"TODOS para ver as {total_universo} empresas" in texto)


def test_23_legenda_de_escopo_nao_aparece_fora_do_filtro_watchlist():
    with patch.object(calendario_tab_mod, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(calendario_tab_mod.st, "columns", return_value=(_FakeCol(), _FakeCol())), \
         patch.object(calendario_tab_mod.st, "pills", return_value="TODOS"), \
         patch.object(calendario_tab_mod.st, "spinner", return_value=_FakeCtx()):
        capturado = _capturar_markdown(calendario_tab_mod._painel_agenda, {"watchlist": ["PETR4"]})
    texto = " ".join(capturado)
    _checar("23 sem a legenda de escopo quando o filtro ja' e' TODOS (nao watchlist)",
             "mostrando sua watchlist" not in texto)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE UI DO CALENDARIO (V3) PASSARAM")
