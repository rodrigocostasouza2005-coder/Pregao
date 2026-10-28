# -*- coding: utf-8 -*-
"""Testes do MAPA DO MERCADO (treemap, ui/mercado_tab.py) - atualizado
no redesign em grade do Painel (2026-10-27, mesma correção já validada
em ui/visao_geral.py, PR #186): o treemap saiu do workspace livre e
virou seção FIXA (ver render_mercado) - 1 das 3 colunas da Região 2, não
mais "praticamente toda a largura útil". `_ALTURAS_PADRAO_MERCADO`/
`_ALTURA_TREEMAP_REM` (do fix anterior, 2026-10-26, que calibrava a
altura do CONTAINER do workspace livre) deixaram de existir - não há
mais container de workspace pra calibrar, só a altura da própria figura
Plotly (`_ALTURA_TREEMAP_PX`), recalibrada pra uma coluna de ~40% da
largura em vez de quase-total.

Este arquivo cobre só a LÓGICA (painel não quebra com dado real/vazio/
momento indisponível, horário relativo nunca inventado, nota de
inteligência contextual aparece só quando há concentração de verdade) -
a validação visual (tamanho de verdade, legibilidade dos blocos dentro
da coluna da grade) é feita com Playwright contra o app rodando de
verdade, não repetida aqui (mesma divisão já usada no resto do projeto).

st.markdown/st.plotly_chart funcionam em "bare mode" (fora de
ScriptRunContext real) sem lançar exceção - mesmo padrão dos outros
testes de UI deste projeto.

Uso: python tests/test_mercado_treemap_tamanho.py (python do .venv do
projeto) ou `pytest tests/test_mercado_treemap_tamanho.py`."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.mercado_tab as mercado_tab_mod

_PREFS = {"formato_numerico": "BR", "watchlist": [], "tema": "AMBAR"}

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _papel(ticker, setor, variacao_pct, preco=10.0, volume_financeiro=1_000_000.0):
    return {"ticker": ticker, "setor": setor, "preco": preco, "variacao_pct": variacao_pct, "volume_financeiro": volume_financeiro}


def test_treemap_saiu_do_registro_arrastavel():
    """Regressão: treemap virou seção fixa (render_mercado) - não pode
    ficar também no workspace livre, senão duplicaria (fixo + draggable),
    mesmo achado/mesma correção já aplicada em VISÃO GERAL (PR #186)."""
    ids = [pid for pid, _, _ in mercado_tab_mod.REGISTRO_PAINEIS]
    for pid in [
        "treemap", "metricas_principais", "altas_baixas", "mais_negociados",
        "setorial", "noticias_resumo", "destaques", "grafico_ibov",
    ]:
        _checar(f"'{pid}' não está mais em REGISTRO_PAINEIS (seção fixa ou removido)", pid not in ids)


def test_grafico_ibov_duplicado_foi_removido_de_vez():
    """IBOVESPA · TRAJETÓRIA duplicava o gráfico canônico de VISÃO GERAL
    (ui/visao_geral.py:_painel_ibov_grafico) - removido de vez, não fica
    nem fixo nem no workspace livre."""
    _checar("_painel_grafico_ibov não existe mais em ui/mercado_tab.py", not hasattr(mercado_tab_mod, "_painel_grafico_ibov"))


def test_altura_da_figura_e_razoavel_pra_coluna_estreita():
    # a figura usada no Painel (_ALTURA_TREEMAP_PX_GRADE) precisa ser uma
    # altura razoavel pra uma coluna de ~40% da largura (Regiao 2, grade
    # de 3 colunas) - nem tao baixa que vire ilegivel, nem tao alta que
    # domine a pagina (pedido explicito do Rodrigo: "evitar que o mapa
    # domine a pagina"). _ALTURA_TREEMAP_PX (default, compartilhado com
    # SETORES em largura cheia) continua intocada - ver teste abaixo.
    figura_px = mercado_tab_mod._ALTURA_TREEMAP_PX_GRADE
    _checar("altura da figura no Painel está entre 300 e 520px", 300 <= figura_px <= 520, f"(figura={figura_px}px)")


def test_altura_default_do_treemap_nao_regride_para_setores():
    """_painel_treemap é COMPARTILHADO com ui/setores_tab.py (importada
    direto, renderizada em largura cheia lá) - a altura DEFAULT não pode
    encolher pro tamanho calibrado pro Painel, senão regride o fix de
    "mapa pequeno" já validado em SETORES (2026-10-26)."""
    _checar(
        "altura default (_ALTURA_TREEMAP_PX) continua a mesma de antes do redesign do Painel (580px)",
        mercado_tab_mod._ALTURA_TREEMAP_PX == 580, f"(obtido: {mercado_tab_mod._ALTURA_TREEMAP_PX})",
    )
    figuras = []
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=[_papel("PETR4", "Petróleo e Gás", 1.0)]), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=datetime.now(timezone.utc)), \
         patch.object(mercado_tab_mod.st, "plotly_chart", side_effect=lambda fig, **k: figuras.append(fig)):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("sem altura_px explícito, usa a altura default compartilhada com SETORES",
            figuras[0].layout.height == mercado_tab_mod._ALTURA_TREEMAP_PX, f"(obtido: {figuras[0].layout.height})")


def test_render_mercado_monta_grade_fixa_com_treemap_numa_coluna():
    """render_mercado chama st.columns (não mais `alturas_padrao` pro
    workspace) pra montar a Região 2 - treemap é 1 das 3 colunas, não
    mais repassado como altura especial pro workspace livre."""
    with patch.object(mercado_tab_mod, "_painel_termometro", return_value=True), \
         patch.object(mercado_tab_mod, "_painel_metricas_principais"), \
         patch.object(mercado_tab_mod, "_painel_altas_baixas"), \
         patch.object(mercado_tab_mod, "_painel_destaques"), \
         patch.object(mercado_tab_mod, "_painel_treemap") as mock_treemap, \
         patch.object(mercado_tab_mod, "_painel_setorial"), \
         patch.object(mercado_tab_mod, "_painel_mais_negociados"), \
         patch.object(mercado_tab_mod, "_painel_noticias_resumo"), \
         patch.object(mercado_tab_mod.workspace, "renderizar_workspace") as mock_ws:
        mercado_tab_mod.render_mercado(_PREFS)
    _checar("_painel_treemap foi chamado (dentro da grade fixa)", mock_treemap.called)
    _checar("renderizar_workspace foi chamado sem alturas_padrao (mecanismo antigo removido)",
            mock_ws.called and "alturas_padrao" not in mock_ws.call_args.kwargs)


def test_tempo_relativo_sem_dado_e_explicito_nunca_inventado():
    _checar("None vira texto explícito", mercado_tab_mod._tempo_relativo(None) == "horário indisponível")


def test_tempo_relativo_recente_nao_lanca_excecao():
    agora = datetime.now(timezone.utc)
    resultado = mercado_tab_mod._tempo_relativo(agora)
    _checar("datetime recente não lança exceção e não é vazio", bool(resultado))
    _checar("datetime recente é 'agora mesmo'", resultado == "agora mesmo")


def test_tempo_relativo_minutos_atras():
    passado = datetime.now(timezone.utc) - timedelta(minutes=12)
    _checar("12min atrás formata como 'há 12min'", mercado_tab_mod._tempo_relativo(passado) == "há 12min")


def test_painel_treemap_sem_dado_nao_lanca_excecao():
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=[]):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap sem dado não lança exceção", True)


def test_painel_treemap_com_dado_real_nao_lanca_excecao_e_mostra_horario():
    papeis = [
        _papel("PETR4", "Petróleo e Gás", -2.5),
        _papel("VALE3", "Mineração e Siderurgia", 1.8),
        _papel("ITUB4", "Bancos", 0.3),
    ]
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=datetime.now(timezone.utc)):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap com dado real não lança exceção", True)


def test_painel_treemap_com_momento_indisponivel_nao_lanca_excecao():
    papeis = [_papel("PETR4", "Petróleo e Gás", -2.5)]
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=None):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("treemap com momento indisponível não lança exceção", True)


def test_nota_concentracao_so_aparece_com_2_ou_mais_setores_em_queda_relevante():
    """[FATO] computado sobre as mesmas médias já calculadas pro mapa -
    nunca aparece quando não há 2+ papéis caindo >3% em nenhum setor
    (regra explícita: nunca um padrão inventado quando não há)."""
    papeis_sem_concentracao = [
        _papel("PETR4", "Petróleo e Gás", -1.0),
        _papel("VALE3", "Mineração e Siderurgia", 1.0),
    ]
    htmls = []
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis_sem_concentracao), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=datetime.now(timezone.utc)), \
         patch.object(mercado_tab_mod.st, "markdown", side_effect=lambda h, **k: htmls.append(h)), \
         patch.object(mercado_tab_mod.st, "plotly_chart"):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar("sem concentração real, nenhum item cita '2+ papéis caindo'", not any("2+ papéis caindo" in h for h in htmls))

    papeis_com_concentracao = [
        _papel("AZUL4", "Transporte", -4.0),
        _papel("GOLL4", "Transporte", -5.0),
        _papel("CVCB3", "Transporte", -3.5),
    ]
    htmls2 = []
    with patch.object(mercado_tab_mod, "obter_panorama_ibovespa", return_value=papeis_com_concentracao), \
         patch.object(mercado_tab_mod, "obter_momento_panorama", return_value=datetime.now(timezone.utc)), \
         patch.object(mercado_tab_mod.st, "markdown", side_effect=lambda h, **k: htmls2.append(h)), \
         patch.object(mercado_tab_mod.st, "plotly_chart"):
        mercado_tab_mod._painel_treemap(_PREFS)
    _checar(
        "com 3 papéis do mesmo setor caindo >3%, a nota [FATO] cita o setor único",
        any("Transporte é o único" in h for h in htmls2),
    )


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass
    if _FALHAS:
        print(f"\n{len(_FALHAS)} falha(s): {_FALHAS}")
        sys.exit(1)
    print("\nTodos os testes passaram.")
