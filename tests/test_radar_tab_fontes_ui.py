# -*- coding: utf-8 -*-
"""Revisão do PR de auditoria do Radar de Carteiras Recomendadas: a aba
RADAR agora mostra, dentro do expander "RADAR DE QUEDAS", o estado por
casa (Itaú Investimentos/Genial Analisa/Safra Corretora) usando
data.radar_quedas.resumo_fontes_vigentes() - este arquivo confirma que
a UI:

1. distingue corretamente os 3 estados (atualizada/desatualizada/
   indisponível), e não só um binário "tem dado ou não tem";
2. nunca chama os coletores de rede (coletar_carteiras_genial/
   coletar_carteiras_safra) só para desenhar essa linha de status -
   resumo_fontes_vigentes() só lê o que já está persistido
   (listar_carteiras(), sem rede nova).

Chama as rotas REAIS de produção (render_radar_carteiras/render_radar_
alertas, as mesmas que app.py despacha pra RADAR › Carteiras
Recomendadas e RADAR › Alertas) em vez de uma composição própria de
teste - antes este arquivo chamava render_radar, uma função legada que
nenhuma rota de produção usa mais (auditoria 2026-11-05: ui/radar_tab.py
compõe a aba via render_radar_alertas/_carteiras/_oportunidades/
_acompanhamento desde o redesign "Bloomberg terminal" de 2026-10-30).
render_radar e seus blocos (_bloco_cobertura, _bloco_monitorados,
_bloco_alertas, _bloco_contexto_alertas) são os MESMOS chamados pelas
rotas reais, então trocar o ponto de entrada aqui não perde cobertura -
pelo contrário, passa a testar exatamente o que é servido.

Bare mode (sem ScriptRunContext real) - mesmo padrão de
tests/test_mercado_ranking_ui.py/test_calendario_ui.py deste projeto:
st.columns/st.pills/st.caption/st.markdown funcionam fora de uma sessão
Streamlit real, só avisam no log.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.radar_quedas as radar_quedas_mod
import ui.radar_tab as radar_tab_mod

_PREFS_SEM_WATCHLIST = {"formato_numerico": "BR", "watchlist": []}
_SEM_MOCK = object()  # sentinel: nao faz patch, deixa a chamada real acontecer


def _coletor_nao_deveria_ser_chamado(*_a, **_k):
    raise AssertionError("coletor de rede chamado só para exibir o Radar")


def _capturar_carteiras(resumo_fontes, linhas_carteiras=_SEM_MOCK, monitorados=_SEM_MOCK,
                        alertas_90d=_SEM_MOCK, selecao_detalhe=None):
    """Chama render_radar_carteiras de verdade (rota real de produção,
    RADAR › Carteiras Recomendadas) com resumo_fontes_vigentes mockado
    (sem rede) e os coletores reais substituídos por algo que FALHA o
    teste se forem chamados - prova que desenhar a tela não dispara
    coleta nova. Exercita _bloco_cobertura, o mesmo bloco que render_
    radar (removido) testava antes. Retorna todo o HTML passado a
    st.markdown, concatenado.

    `linhas_carteiras`/`monitorados`/`alertas_90d`: quando fornecidos,
    mockam respectivamente listar_carteiras()/painel_monitorados()/
    alertas_periodo(90) - usados pelos blocos novos (COMPARAR CARTEIRAS/
    COMPOSIÇÃO/EXPOSIÇÃO SETORIAL, reformulação 2026-11-06). Om
    `_SEM_MOCK` (padrão), a chamada real acontece (sem Supabase no
    ambiente de teste, cai no caminho "banco indisponível" - mesmo
    comportamento de antes desta reformulação, pros testes que não
    passam esses argumentos).

    `selecao_detalhe`: mocka st.selectbox (usado pelo seletor nativo de
    "ver composição da carteira") pra devolver uma opção específica."""
    blocos = []
    patches = [
        patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo_fontes),
        patch.object(radar_quedas_mod, "coletar_carteiras_genial", side_effect=_coletor_nao_deveria_ser_chamado),
        patch.object(radar_quedas_mod, "coletar_carteiras_safra", side_effect=_coletor_nao_deveria_ser_chamado),
        patch.object(radar_quedas_mod, "coletar_carteiras_itau", side_effect=_coletor_nao_deveria_ser_chamado),
        patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)),
    ]
    if linhas_carteiras is not _SEM_MOCK:
        patches.append(patch.object(radar_quedas_mod, "listar_carteiras", return_value=linhas_carteiras))
    if monitorados is not _SEM_MOCK:
        patches.append(patch.object(radar_quedas_mod, "painel_monitorados", return_value=monitorados))
    if alertas_90d is not _SEM_MOCK:
        patches.append(patch.object(radar_quedas_mod, "alertas_periodo", return_value=alertas_90d))
    if selecao_detalhe is not None:
        patches.append(patch.object(radar_tab_mod.st, "selectbox", return_value=selecao_detalhe))

    with _aplicar(patches):
        # render_radar_carteiras e' decorado com @st.fragment, que em bare
        # mode (sem ScriptRunContext real) NUNCA executa o corpo da funcao -
        # chamar render_radar_carteiras(...) direto aqui silenciosamente nao
        # faria nada e o teste passaria "por acidente" sem checar nada.
        # .__wrapped__ e' a funcao original (sem o decorador).
        radar_tab_mod.render_radar_carteiras.__wrapped__(_PREFS_SEM_WATCHLIST)

    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def _aplicar(patches):
    """contextlib.ExitStack minimalista pra uma lista dinamica de
    patches (numero varia conforme os mocks opcionais pedidos acima)."""
    from contextlib import ExitStack

    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


def _capturar_alertas(resumo_fontes, alertas=None, monitorados=None):
    """Mesma ideia de _capturar_carteiras, pra render_radar_alertas (rota
    real RADAR › Alertas: regra + alertas registrados + monitorados
    agora) - exercita _bloco_alertas/_bloco_monitorados/_bloco_
    contexto_alertas."""
    blocos = []
    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo_fontes), \
         patch.object(radar_quedas_mod, "painel_monitorados", return_value=monitorados if monitorados is not None else []), \
         patch.object(radar_quedas_mod, "alertas_periodo", return_value=alertas if alertas is not None else []), \
         patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)):
        radar_tab_mod.render_radar_alertas.__wrapped__(_PREFS_SEM_WATCHLIST)

    return "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))


def _linha_da_casa(html_render, casa):
    inicio = html_render.index(f"<td class='rq-esq'>{casa}</td>")
    return html_render[inicio:html_render.index("</tr>", inicio)]


def test_fonte_atualizada_e_fonte_indisponivel_sao_distinguidas():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                            "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"},
        # Genial Analisa ausente do resumo -> UI trata como indisponível
    }
    html_render = _capturar_carteiras(resumo)
    assert "rq-estado-ATUALIZADA" in _linha_da_casa(html_render, "Safra Corretora")
    assert "rq-estado-INDISPONIVEL" in _linha_da_casa(html_render, "Genial Analisa")
    assert "1 de 3 casas com carteira vigente" in html_render
    assert "rq-estado-DESATUALIZADA" not in html_render


def test_fonte_desatualizada_e_distinguida_de_atualizada_e_de_indisponivel():
    resumo = {
        "Safra Corretora": {"ativos": 10, "verificado_em": "2026-09-01T10:00:00+00:00", "desatualizada": True,
                            "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-09-01"},
        "Genial Analisa": {"ativos": 42, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                           "carteiras": ["Carteira Ações"], "data_publicacao": "2026-10-05"},
    }
    html_render = _capturar_carteiras(resumo)
    assert "rq-estado-DESATUALIZADA" in _linha_da_casa(html_render, "Safra Corretora")
    assert "rq-estado-ATUALIZADA" in _linha_da_casa(html_render, "Genial Analisa")
    assert "rq-estado-INDISPONIVEL" in _linha_da_casa(html_render, "Itaú Investimentos")
    assert "2 de 3 casas com carteira vigente" in html_render


def test_supabase_indisponivel_avisa_e_nao_quebra():
    """resumo_fontes_vigentes() devolve None quando o Supabase está fora do
    ar - a UI avisa, não desenha tabela nenhuma e nunca lança exceção."""
    html_render = _capturar_carteiras(resumo_fontes=None)
    assert "Banco indisponível" in html_render
    assert "rq-tabela" not in html_render


def test_alertas_e_monitorados_renderizados_com_numero_brasileiro_e_estado_do_email():
    import data.radar_quedas as rq
    resumo = {"Safra Corretora": {"ativos": 2, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                                  "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"}}
    monitorados = rq.linhas_monitorados(
        [{"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "PETR4", "empresa": "Petrobras"},
         {"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "VALE3", "empresa": "Vale"}],
        {"PETR4": {"preco": 36.10, "fechamento_anterior": 37.92, "erro": None}, "VALE3": {"erro": "timeout"}},
    )
    alertas = [{"ticker": "PETR4", "empresa": "Petrobras", "pregao": "2026-10-16", "variacao_pct": -4.7996,
                "preco_atual": 36.10, "fechamento_anterior": 37.92, "casas": ["Safra Corretora"],
                "carteiras": ["Top 10 Ações"], "fontes": ["https://www.safra.com.br/x"],
                "alertado_em": "2026-10-16T15:31:05+00:00", "status": "FALHA_ENVIO"}]
    html_render = _capturar_alertas(resumo, alertas=alertas, monitorados=monitorados)
    assert "-4,80%" in html_render and "37,92" in html_render  # formato BR, nunca 37.92
    assert "rq-estado-ALERTA" in html_render
    assert "rq-estado-SEM_COTACAO" in html_render  # VALE3 sem cotação não vira "0,00%"
    assert "rq-estado-FALHOU" in html_render and "FALHA_ENVIO" not in html_render
    assert "16/10 12:31" in html_render  # horário de Brasília, não ISO UTC


def test_alerta_com_evidencia_real_mostra_contexto_market_makers():
    """Bug real (achado 23/10/2026, alerta WEGE3 'E-MAIL: FALHOU'): o
    alerta de queda não contextualizava nada, mesmo quando havia
    mudança de tese real na mesma janela. MARKET MAKERS (data/
    market_makers.py) agora cruza o alerta com evidência real, quando
    ela existe."""
    import data.radar_quedas as rq

    resumo = {"Safra Corretora": {"ativos": 1, "verificado_em": "2026-10-23T10:00:00+00:00", "desatualizada": False,
                                  "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"}}
    alertas = [{"ticker": "WEGE3", "empresa": "WEG", "pregao": "2026-10-23", "variacao_pct": -4.5,
                "preco_atual": 40.0, "fechamento_anterior": 41.9, "casas": ["Safra Corretora"],
                "carteiras": ["Top 10 Ações"], "fontes": [], "alertado_em": "2026-10-23T15:31:05+00:00",
                "status": "FALHA_ENVIO"}]
    contexto = {
        "ticker": "WEGE3", "gerado_em": None, "catalisadores": [], "mudancas": [], "riscos": [],
        "interpretacao": {"texto": "Genial revisou WEGE3 de COMPRA para NEUTRO.",
                          "tipo_evidencia": "FATO", "fonte_url": "https://genial.com.br",
                          "fonte_label": "Genial Analisa"},
    }
    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo), \
         patch.object(radar_quedas_mod, "painel_monitorados", return_value=[]), \
         patch.object(radar_quedas_mod, "alertas_periodo", return_value=alertas), \
         patch("data.market_makers.contexto_ticker", return_value=contexto):
        blocos = []
        with patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)), \
             patch.object(radar_tab_mod.st, "expander") as expander_mock:
            expander_mock.return_value.__enter__ = lambda self: self
            expander_mock.return_value.__exit__ = lambda *a: False
            radar_tab_mod.render_radar_alertas.__wrapped__(_PREFS_SEM_WATCHLIST)
    html_render = "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))
    assert "Genial revisou WEGE3 de COMPRA para NEUTRO" in html_render
    assert "href='https://genial.com.br'" in html_render


def test_alerta_sem_nenhuma_evidencia_nao_mostra_contexto_inventado():
    import data.radar_quedas as rq

    resumo = {"Safra Corretora": {"ativos": 1, "verificado_em": "2026-10-23T10:00:00+00:00", "desatualizada": False,
                                  "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"}}
    alertas = [{"ticker": "WEGE3", "empresa": "WEG", "pregao": "2026-10-23", "variacao_pct": -4.5,
                "preco_atual": 40.0, "fechamento_anterior": 41.9, "casas": ["Safra Corretora"],
                "carteiras": ["Top 10 Ações"], "fontes": [], "alertado_em": "2026-10-23T15:31:05+00:00",
                "status": "FALHA_ENVIO"}]
    sem_evidencia = {"ticker": "WEGE3", "gerado_em": None, "catalisadores": [], "mudancas": [], "riscos": [],
                     "interpretacao": None}
    with patch.object(radar_quedas_mod, "resumo_fontes_vigentes", return_value=resumo), \
         patch.object(radar_quedas_mod, "painel_monitorados", return_value=[]), \
         patch.object(radar_quedas_mod, "alertas_periodo", return_value=alertas), \
         patch("data.market_makers.contexto_ticker", return_value=sem_evidencia):
        blocos = []
        with patch.object(radar_tab_mod.st, "markdown", side_effect=lambda texto, **_k: blocos.append(texto)):
            radar_tab_mod.render_radar_alertas.__wrapped__(_PREFS_SEM_WATCHLIST)
    html_render = "\n".join(b for b in blocos if not b.lstrip().startswith("<style>"))
    assert "CONTEXTO DO MOVIMENTO" not in html_render


def test_ticker_das_tabelas_densas_e_clicavel():
    """Achado P1 da auditoria 360 (docs/auditoria-redesign-360.md secao 4):
    .rq-ticker tinha a MESMA cor/peso visual de "isto e' clicavel" usada
    no ranking de MERCADO, mas era so' <span> sem destino nenhum - tanto
    em MONITORADOS AGORA quanto em ALERTAS REGISTRADOS. Agora precisa ser
    um link real (?ticker=X, lido por app.py via
    ui.navegacao.ticker_da_url) pros dois casos."""
    import data.radar_quedas as rq
    resumo = {"Safra Corretora": {"ativos": 1, "verificado_em": "2026-10-17T10:00:00+00:00", "desatualizada": False,
                                  "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-10-01"}}
    monitorados = rq.linhas_monitorados(
        [{"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "PETR4", "empresa": "Petrobras"}],
        {"PETR4": {"preco": 36.10, "fechamento_anterior": 37.92, "erro": None}},
    )
    alertas = [{"ticker": "VALE3", "empresa": "Vale", "pregao": "2026-10-16", "variacao_pct": -4.7996,
                "preco_atual": 60.0, "fechamento_anterior": 63.0, "casas": ["Safra Corretora"],
                "carteiras": ["Top 10 Ações"], "fontes": [], "alertado_em": "2026-10-16T15:31:05+00:00",
                "status": "ENVIADO"}]
    html_render = _capturar_alertas(resumo, alertas=alertas, monitorados=monitorados)
    assert "<a class='rq-ticker' href='?ticker=PETR4'>PETR4</a>" in html_render
    assert "<a class='rq-ticker' href='?ticker=VALE3'>VALE3</a>" in html_render
    # nenhum ticker sobrevive como <span> sem destino (regressao do achado original)
    assert "<span class='rq-ticker'>" not in html_render


# ============================================================
# COMPARAR CARTEIRAS / COMPOSIÇÃO / EXPOSIÇÃO SETORIAL
# (reformulação 2026-11-06 - render_radar_carteiras passa a comparar as
# carteiras vigentes entre si e mostrar a composição + exposição
# setorial (nº de posições por setor) de uma carteira por vez, sem
# nunca inventar peso/alocação por ativo - nenhuma fonte monitorada
# persiste esse dado hoje, ver nota em ui/radar_tab.py.)
# ============================================================

_RESUMO_DUAS_CASAS = {
    "Safra Corretora": {"ativos": 2, "verificado_em": "2026-11-05T10:00:00+00:00", "desatualizada": False,
                        "carteiras": ["Top 10 Ações"], "data_publicacao": "2026-11-01"},
    "Genial Analisa": {"ativos": 2, "verificado_em": "2026-11-05T10:00:00+00:00", "desatualizada": False,
                       "carteiras": ["Carteira Ibovespa 10+"], "data_publicacao": "2026-11-03"},
}

_LINHAS_DUAS_CARTEIRAS = [
    {"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "PETR4", "empresa": "Petrobras",
     "preco_alvo": None, "data_publicacao": "2026-11-01", "fonte_url": "https://www.safra.com.br/x"},
    {"casa": "Safra Corretora", "carteira": "Top 10 Ações", "ticker": "VALE3", "empresa": "Vale",
     "preco_alvo": None, "data_publicacao": "2026-11-01", "fonte_url": "https://www.safra.com.br/x"},
    {"casa": "Genial Analisa", "carteira": "Carteira Ibovespa 10+", "ticker": "WEGE3", "empresa": "WEG",
     "preco_alvo": None, "data_publicacao": "2026-11-03", "fonte_url": "https://genial.com.br/y"},
    {"casa": "Genial Analisa", "carteira": "Carteira Ibovespa 10+", "ticker": "ITUB4", "empresa": "Itaú Unibanco",
     "preco_alvo": 42.5, "data_publicacao": "2026-11-03", "fonte_url": "https://genial.com.br/y"},
]


def _monitorados_duas_carteiras():
    import data.radar_quedas as rq
    recomendacoes = [
        {"casa": l["casa"], "carteira": l["carteira"], "ticker": l["ticker"], "empresa": l["empresa"]}
        for l in _LINHAS_DUAS_CARTEIRAS
    ]
    cotacoes = {
        "PETR4": {"preco": 36.10, "fechamento_anterior": 37.92, "erro": None},  # queda forte -> ALERTA
        "VALE3": {"preco": 61.0, "fechamento_anterior": 60.0, "erro": None},    # alta leve
        "WEGE3": {"preco": 40.0, "fechamento_anterior": 41.0, "erro": None},    # queda leve -> NORMAL
        "ITUB4": {"erro": "timeout"},                                          # sem cotação
    }
    return rq.linhas_monitorados(recomendacoes, cotacoes)


def test_comparar_carteiras_mostra_cada_carteira_com_ativos_var_media_e_risco():
    html_render = _capturar_carteiras(
        _RESUMO_DUAS_CASAS, linhas_carteiras=_LINHAS_DUAS_CARTEIRAS,
        monitorados=_monitorados_duas_carteiras(), alertas_90d=[],
    )
    assert "COMPARAR CARTEIRAS" in html_render
    # as 2 carteiras aparecem, cada uma com o nº real de ativos (2)
    assert "Top 10 Ações" in html_render and "Carteira Ibovespa 10+" in html_render
    assert "<td>2</td>" in html_render
    # PETR4 caiu mais de 4% -> a carteira da Safra tem 1 ativo em alerta
    assert "1 em alerta" in html_render
    # a tela declara explicitamente que não inventa peso/alocação por ativo
    assert "Peso/alocação de cada posição não é divulgado" in html_render


def test_composicao_da_carteira_selecionada_mostra_ativos_reais_sem_inventar_peso():
    html_render = _capturar_carteiras(
        _RESUMO_DUAS_CASAS, linhas_carteiras=_LINHAS_DUAS_CARTEIRAS,
        monitorados=_monitorados_duas_carteiras(), alertas_90d=[],
        selecao_detalhe="Genial Analisa — Carteira Ibovespa 10+",
    )
    assert "COMPOSIÇÃO — Genial Analisa · Carteira Ibovespa 10+" in html_render
    assert "WEGE3" in html_render and "ITUB4" in html_render
    # preço-alvo real da fonte (ITUB4) aparece; WEGE3 (sem preço-alvo coletado) mostra "—"
    assert "42,50" in html_render
    # nota explícita: nunca inventa peso/alocação por posição
    assert "Peso/alocação de cada posição não é divulgado" in html_render
    assert "EXPOSIÇÃO SETORIAL" in html_render


def test_exposicao_setorial_conta_posicoes_por_setor_sem_fabricar_percentual_monetario():
    import config
    html_render = _capturar_carteiras(
        _RESUMO_DUAS_CASAS, linhas_carteiras=_LINHAS_DUAS_CARTEIRAS,
        monitorados=_monitorados_duas_carteiras(), alertas_90d=[],
        selecao_detalhe="Safra Corretora — Top 10 Ações",
    )
    setor_petr4 = config.IBOVESPA_SETORES.get("PETR4", "Outros")
    setor_vale3 = config.IBOVESPA_SETORES.get("VALE3", "Outros")
    assert "EXPOSIÇÃO SETORIAL" in html_render
    assert "Nº POSIÇÕES" in html_render
    if setor_petr4 == setor_vale3:
        assert f"<td class='rq-esq'>{setor_petr4}</td><td>2</td>" in html_render
    else:
        assert f"<td class='rq-esq'>{setor_petr4}</td><td>1</td>" in html_render
        assert f"<td class='rq-esq'>{setor_vale3}</td><td>1</td>" in html_render


def test_sem_carteira_vigente_para_comparar_nao_quebra_e_avisa():
    """listar_carteiras() vazio (nenhuma carteira vigente), mas resumo_fontes
    tem casas presentes (estado possível quando todas foram descobertas
    EXPIRADAS entre as duas leituras) - UI avisa, não lança excecao nem
    desenha tabela de comparação vazia."""
    html_render = _capturar_carteiras(_RESUMO_DUAS_CASAS, linhas_carteiras=[], monitorados=[], alertas_90d=[])
    assert "Nenhuma carteira vigente pra comparar ou detalhar agora" in html_render
    assert "COMPARAR CARTEIRAS" not in html_render


def test_banco_fora_do_ar_na_composicao_nao_quebra_mesmo_com_cobertura_mockada():
    """resumo_fontes_vigentes mockado (cobertura OK), mas listar_carteiras()
    real (sem Supabase no teste) retorna None - a composição avisa
    'banco fora do ar' em vez de lançar excecao ou fingir dado vazio."""
    html_render = _capturar_carteiras(_RESUMO_DUAS_CASAS)  # linhas_carteiras não mockado = chamada real
    assert "Composição indisponível: banco fora do ar" in html_render
    assert "COMPARAR CARTEIRAS" not in html_render
