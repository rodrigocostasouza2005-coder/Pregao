# -*- coding: utf-8 -*-
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch
import pandas as pd
import jobs.morning_call as mc

TZ_SP = ZoneInfo("America/Sao_Paulo")

_COT_INDISPONIVEL = lambda nome, ticker: ({"erro": "indisponível"}, f"- {nome}: indisponível")


# ---------------------------------------------------------------------
# ESTRUTURA EDITORIAL (reconciliação PR #38 x main pós-#40, 2026-10-17):
# RESUMO EXECUTIVO / BRASIL / EXTERIOR / AGENDA DE HOJE / EMPRESAS E
# SETORES / TENDÊNCIAS E RISCOS / LIMITAÇÕES / FONTES.
# ---------------------------------------------------------------------

def test_morning_call_independente_sem_news_e_macro():
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert "MORNING CALL" in texto
    for secao in mc.SECOES_OBRIGATORIAS:
        assert secao in texto
    assert "carteira" not in texto.lower()
    assert "alerta" not in texto.lower()


def test_resumo_executivo_reporta_direcao_sem_inventar_numero():
    """RESUMO EXECUTIVO só repete direção/magnitude já calculada - nunca
    um número novo nem uma interpretação (seção 6, marcada
    [INTERPRETAÇÃO], é o único lugar com leitura de cenário)."""
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
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert "Ibovespa: alta de 1,23%" in texto
    assert "Dólar (USD/BRL): queda de 0,55%" in texto


def test_noticias_classificadas_por_regiao_e_ticker_em_secoes_separadas():
    """Reaproveita regiao/tickers já calculados por data/news.py - BR com
    ticker vai pra EMPRESAS E SETORES, BR sem ticker fica em BRASIL, INT
    fica em EXTERIOR. Nenhuma reclassificação própria, nenhum link
    inventado - o link vem direto do item de data/news.py."""
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
         patch.object(mc, "obter_top_mercado_tudo", return_value=noticias), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))

    secao_brasil = texto.split("2. BRASIL")[1].split("3. EXTERIOR")[0]
    secao_exterior = texto.split("3. EXTERIOR")[1].split("4. AGENDA")[0]
    secao_empresas = texto.split("5. EMPRESAS E SETORES")[1].split("6. TENDÊNCIAS")[0]
    assert "PETR4 anuncia dividendo" in secao_empresas
    assert "https://x/1" in secao_empresas
    assert "PETR4 anuncia dividendo" not in secao_brasil
    assert "Governo anuncia pacote fiscal" in secao_brasil
    assert "Governo anuncia pacote fiscal" not in secao_exterior
    assert "Fed sinaliza postura sobre juros" in secao_exterior
    assert "Fed sinaliza postura sobre juros" not in secao_brasil


def test_empresas_e_setores_some_fatos_relevantes_quando_sem_noticia_com_ticker():
    """Mission: seção sem dado confiável precisa dizer isso
    explicitamente, nunca omitir em silêncio nem inventar conteúdo."""
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[
             {"titulo": "Governo anuncia pacote fiscal", "link": "https://x/2", "regiao": "BR", "tickers": []},
         ]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    secao_empresas = texto.split("5. EMPRESAS E SETORES")[1].split("6. TENDÊNCIAS")[0]
    assert "sem fatos relevantes confirmados" in secao_empresas


def test_noticia_duplicada_na_mesma_coleta_nao_repete_na_secao():
    """data/news.py já dedupe/mescla fatos equivalentes antes de devolver
    - montar_morning_call nunca deve reintroduzir duplicata ao
    particionar por seção (cada item aparece exatamente 1x no texto)."""
    noticias = [
        {"titulo": "Fed sinaliza postura sobre juros", "link": "https://x/3", "regiao": "INT", "tickers": []},
    ]
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=noticias), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert texto.count("Fed sinaliza postura sobre juros") == 1


def test_noticias_indisponiveis_cai_no_fallback_textual_em_todas_as_secoes():
    """Falha de data/news.py (fonte indisponível) precisa ser dita
    explicitamente em cada seção que dependeria dela, nunca quebrar o
    e-mail inteiro nem inventar manchete."""
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", side_effect=RuntimeError("Google News fora do ar")), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert texto.count("Notícias indisponíveis nesta execução") == 3
    for secao in mc.SECOES_OBRIGATORIAS:
        assert secao in texto


def test_html_preserva_links_e_estrutura_minima():
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[
             {"titulo": "Manchete X", "link": "https://exemplo.com/a", "regiao": "INT", "tickers": []},
         ]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    corpo_html = mc.montar_morning_call_html(texto)
    assert "<h1" in corpo_html
    assert '<a href="https://exemplo.com/a">https://exemplo.com/a</a>' in corpo_html
    assert "<script" not in corpo_html
    assert "<li>Manchete X" in corpo_html
    assert "<h2" in corpo_html and "FONTES" in corpo_html


def test_focus_usa_ano_referencia_como_rotulo_sem_formatar_como_dinheiro():
    """Regressao 2026-10-15: Focus IPCA/Selic nao tem coluna 'data' (so
    Selic/CDI tem) - o codigo so conhecia 'data', entao toda linha de
    Focus caia no fallback 'data não informada'[:10] = 'data não i', e
    ano_referencia/numero_respondentes apareciam formatados como
    dinheiro (ex: '2.026,00' em vez de '2026')."""
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
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(datetime(2026, 10, 14, 7, tzinfo=TZ_SP))
    assert "data não i" not in texto
    assert "Focus IPCA (2026):" in texto
    assert "Focus IPCA (2027):" in texto
    assert "2.026,00" not in texto
    assert "numero_respondentes=144" in texto
    assert "mediana_pct=5,22" in texto


# ---------------------------------------------------------------------
# AGENDA DE HOJE (data/eventos.py) - preservada tal como veio do PR #40,
# só renumerada de "3." pra "4." (RESUMO EXECUTIVO/BRASIL/EXTERIOR
# entraram na frente dela na reconciliação editorial).
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
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[evento_hoje]):
        texto = mc.montar_morning_call(agora)
    assert "4. AGENDA DE HOJE" in texto
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
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
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
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", return_value=[]):
        texto = mc.montar_morning_call(agora)
    assert "4. AGENDA DE HOJE" in texto
    assert "Nenhum evento relevante identificado para hoje." in texto


def test_agenda_falha_de_leitura_cai_no_fallback_textual_sem_quebrar_email():
    """Mesmo padrão try/except + fallback textual já usado em
    BRASIL/EXTERIOR/EMPRESAS E SETORES - uma falha no calendário nunca
    pode quebrar o e-mail inteiro."""
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[]), \
         patch.object(mc, "calcular_calendario_cacheado", side_effect=RuntimeError("CVM fora do ar")):
        texto = mc.montar_morning_call(agora)
    assert "4. AGENDA DE HOJE" in texto
    assert "Agenda do dia indisponível nesta execução." in texto
    # a falha não pode ter derrubado as seções seguintes:
    assert "TENDÊNCIAS E RISCOS" in texto
    assert "LIMITAÇÕES" in texto
    assert "FONTES" in texto


def test_montar_morning_call_nao_quebra_numa_segunda_feira_apos_fim_de_semana():
    """Mission: 'Determine corretamente o último pregão encerrado,
    inclusive às segundas-feiras e após feriados' - o conteúdo nunca
    assume 'ontem foi dia útil': cada seção já lê o que o provedor
    devolveu (última barra real/cache real), sem recalcular datas aqui."""
    segunda = datetime(2026, 10, 19, 7, tzinfo=TZ_SP)  # 19/10/2026 é segunda-feira
    assert segunda.weekday() == 0
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
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


# ---------------------------------------------------------------------
# MODO DE PREVIEW (sem envio real).
# ---------------------------------------------------------------------

def test_gerar_preview_contem_todas_as_secoes_obrigatorias_sem_enviar_email(monkeypatch):
    enviar_email_mock = MagicMock(side_effect=AssertionError("gerar_preview nunca deve enviar e-mail de verdade"))
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["assinante@exemplo.com"])
    with patch.object(mc, "_obter_cotacao_fmt", side_effect=_COT_INDISPONIVEL), \
         patch.object(mc, "obter_selic_meta", return_value=None), \
         patch.object(mc, "obter_cdi", return_value=None), \
         patch.object(mc, "obter_focus_ipca", return_value=None), \
         patch.object(mc, "obter_focus_selic", return_value=None), \
         patch.object(mc, "obter_top_mercado_tudo", return_value=[
             {"titulo": "Manchete X", "link": "https://exemplo.com/x", "regiao": "INT", "tickers": []},
         ]), \
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
    assert preview["total_assinantes_ativos"] == 1


def test_gerar_preview_marca_invalido_quando_falta_secao_obrigatoria(monkeypatch):
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: [])
    with patch.object(mc, "montar_morning_call", return_value="MORNING CALL — texto incompleto sem as seções"):
        preview = mc.gerar_preview(agora)
    assert preview["valido"] is False
    assert "1. RESUMO EXECUTIVO" in preview["secoes_faltantes"]


def test_gerar_preview_total_assinantes_ativos_zero_quando_supabase_indisponivel(monkeypatch):
    """0 assinantes também é o resultado quando o Supabase está fora do
    ar (listar_assinantes_morning_call devolve None) - gerar_preview não
    distingue os 2 casos (documentado), só não pode quebrar/lançar."""
    agora = datetime(2026, 10, 14, 7, tzinfo=TZ_SP)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: None)
    with patch.object(mc, "montar_morning_call", return_value="texto completo o bastante"):
        preview = mc.gerar_preview(agora)
    assert preview["total_assinantes_ativos"] == 0


# ---------------------------------------------------------------------
# IDEMPOTÊNCIA / DUPLICATA por assinante.
# ---------------------------------------------------------------------

def _cliente_fake_com_resultado(linhas):
    """Fake pra _ja_enviado_hoje: select(...).eq("status",...).eq("destinatario",...).gte(...).limit(...).execute()."""
    resp = MagicMock()
    resp.data = linhas
    cliente = MagicMock()
    (
        cliente.table.return_value.select.return_value.eq.return_value
        .eq.return_value.gte.return_value.limit.return_value.execute.return_value
    ) = resp
    return cliente


def test_ja_enviado_hoje_true_quando_ha_registro_enviado_no_dia_pro_mesmo_destinatario():
    cliente = _cliente_fake_com_resultado([{"id": 1}])
    agora = datetime(2026, 10, 16, 9, tzinfo=TZ_SP)
    assert mc._ja_enviado_hoje(cliente, agora, "assinante@exemplo.com") is True
    cliente.table.assert_called_with("morning_call_execucoes")
    cliente.table.return_value.select.return_value.eq.assert_called_with("status", "ENVIADO")
    cliente.table.return_value.select.return_value.eq.return_value.eq.assert_called_with(
        "destinatario", "assinante@exemplo.com",
    )


def test_ja_enviado_hoje_false_quando_nao_ha_registro():
    cliente = _cliente_fake_com_resultado([])
    agora = datetime(2026, 10, 16, 9, tzinfo=TZ_SP)
    assert mc._ja_enviado_hoje(cliente, agora, "assinante@exemplo.com") is False


def test_ja_enviado_hoje_false_sem_cliente_supabase():
    assert mc._ja_enviado_hoje(None, datetime(2026, 10, 16, 9, tzinfo=TZ_SP), "assinante@exemplo.com") is False


def test_ja_enviado_hoje_false_quando_consulta_lanca_excecao():
    cliente = MagicMock()
    cliente.table.side_effect = RuntimeError("Supabase fora do ar")
    assert mc._ja_enviado_hoje(cliente, datetime(2026, 10, 16, 9, tzinfo=TZ_SP), "assinante@exemplo.com") is False


def test_hash_destinatario_nunca_expoe_o_email_e_e_estavel():
    h1 = mc._hash_destinatario("Assinante@Exemplo.com")
    h2 = mc._hash_destinatario("assinante@exemplo.com")
    assert h1 == h2, "hash deveria ser case-insensitive (mesmo e-mail normalizado)"
    assert "assinante" not in h1 and "exemplo" not in h1
    assert len(h1) == 10


# ---------------------------------------------------------------------
# executar(): self-test de persistência, assinantes (None x [] x lista),
# múltiplos assinantes, falha parcial, dedupe, compatibilidade com
# agendamento/infra do PR #40.
# ---------------------------------------------------------------------

def test_executar_chama_self_test_de_persistencia_antes_de_tudo(monkeypatch):
    chamadas_diagnostico = []
    monkeypatch.setattr(
        mc, "diagnosticar_persistencia",
        lambda: chamadas_diagnostico.append(1) or {"ok": True, "etapa": "OK", "detalhe": ""},
    )
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["assinante@exemplo.com"])

    mc.executar()

    assert len(chamadas_diagnostico) == 1


def test_executar_sem_nenhum_assinante_ativo_nao_tenta_enviar(monkeypatch):
    """Lista vazia (não None) = "ninguém se inscreveu ainda" - estado
    normal, não erro: não deve montar texto nem chamar enviar_email."""
    chamadas_envio = []
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: object())
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: [])
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("não deveria montar texto sem assinante")))
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    chamadas_registro = []
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas_registro.append((a, k)))

    codigo = mc.executar()

    assert codigo == 0
    assert chamadas_envio == []
    assert chamadas_registro[0][1]["execucao_ok"] is True


def test_executar_com_supabase_indisponivel_nao_mascara_falha_como_sucesso(monkeypatch):
    """None (distinto de []) = não foi possível consultar os assinantes
    (Supabase fora do ar) - precisa ser reportado como FALHA real no
    painel SAÚDE DOS DADOS, nunca como "ninguém assinou" (mascarar uma
    falha de infra como sucesso é o problema identificado na comparação
    com o PR concorrente #42 durante a consolidação, 2026-10-17)."""
    chamadas_envio = []
    chamadas_registro = []
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: None)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: None)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("não deveria montar texto com Supabase indisponível")))
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas_registro.append((a, k)))

    codigo = mc.executar()

    assert codigo == 1
    assert chamadas_envio == []
    assert chamadas_registro[0][1]["execucao_ok"] is False
    assert chamadas_registro[0][1]["persistencia_ok"] is False
    assert chamadas_registro[0][1]["erro"]


def test_executar_pula_envio_quando_todos_ja_enviados_hoje_regressao_retry_duplicado(monkeypatch):
    """Regressão: um retry manual (ou "Re-run failed jobs" no GitHub
    Actions) rodando executar() de novo no MESMO dia depois de um
    ENVIADO com sucesso anterior NÃO pode mandar e-mail duplicado pro
    MESMO assinante."""
    cliente = _cliente_fake_com_resultado([{"id": 1}])
    chamadas_envio = []
    chamadas_registro = []

    def _montar_nao_deveria_ser_chamado(*_a, **_k):
        raise AssertionError("não deveria montar o texto quando já foi enviado hoje pra todos")

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["assinante@exemplo.com"])
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
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["assinante@exemplo.com"])
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    codigo = mc.executar()

    assert codigo == 0
    assert len(chamadas_envio) == 1
    assert chamadas_envio[0][1].get("destinatario") == "assinante@exemplo.com"
    cliente.table.return_value.insert.assert_called_once()


def test_executar_envia_versao_html_junto_da_versao_texto(monkeypatch):
    """Mission: 'Produza HTML compatível com clientes de e-mail e uma
    alternativa em texto simples' - enviar_email precisa receber html=
    não vazio, nunca só o texto puro."""
    cliente = _cliente_fake_com_resultado([])
    chamadas_envio = []

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(mc, "listar_assinantes_morning_call", lambda *_a, **_k: ["assinante@exemplo.com"])
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "1. RESUMO EXECUTIVO\n- Ibovespa: alta de 1%")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    mc.executar()

    assert len(chamadas_envio) == 1
    _args, kwargs = chamadas_envio[0]
    assert kwargs.get("html"), "enviar_email foi chamado sem a versão HTML"
    assert "<h1" in kwargs["html"]


def test_executar_envia_pra_varios_assinantes_e_dedupe_ja_vem_da_listagem(monkeypatch):
    """listar_assinantes_morning_call já devolve e-mails deduplicados -
    executar() precisa enviar exatamente 1 vez por e-mail distinto da
    lista, nunca reenviar pro mesmo endereço na mesma execução."""
    cliente = _cliente_fake_com_resultado([])
    chamadas_envio = []

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(
        mc, "listar_assinantes_morning_call",
        lambda *_a, **_k: ["a@exemplo.com", "b@exemplo.com"],
    )
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    codigo = mc.executar()

    assert codigo == 0
    destinatarios = sorted(k.get("destinatario") for _a, k in chamadas_envio)
    assert destinatarios == ["a@exemplo.com", "b@exemplo.com"]


def test_executar_falha_pra_um_assinante_nao_impede_envio_aos_demais(monkeypatch):
    """Falha de envio pra UM assinante (ex: Resend rejeitou aquele
    endereço) não pode interromper o laço nem impedir que os demais
    recebam - e a execução não pode ser relatada como sucesso total
    (registrar_tentativa precisa ver execucao_ok=False)."""
    cliente = _cliente_fake_com_resultado([])
    chamadas_envio = []
    chamadas_registro = []

    def _enviar(_assunto, _texto, html=None, destinatario=None):
        chamadas_envio.append(destinatario)
        if destinatario == "falha@exemplo.com":
            return {"ok": False, "erro": "Resend HTTP 422"}
        return {"ok": True, "erro": None}

    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(
        mc, "listar_assinantes_morning_call",
        lambda *_a, **_k: ["falha@exemplo.com", "ok@exemplo.com"],
    )
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", _enviar)
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: chamadas_registro.append((a, k)))

    codigo = mc.executar()

    # os DOIS devem ter sido tentados (a falha de um não cancela o outro):
    assert sorted(chamadas_envio) == ["falha@exemplo.com", "ok@exemplo.com"]
    # falha parcial não pode ser sucesso total nem no retorno nem no painel:
    assert codigo == 1
    assert chamadas_registro[0][1]["execucao_ok"] is False
    assert chamadas_registro[0][1]["parcial"] is True


def test_executar_nunca_loga_email_completo_em_texto_puro(monkeypatch, capsys):
    """Exigência explícita da missão: nunca logar e-mail completo de
    destinatário - só o hash curto/irreversível (_hash_destinatario).
    Esse foi um ponto em que o PR concorrente #42 regredia (logava
    e-mail puro em 3 lugares) e o #41/consolidado não."""
    cliente = _cliente_fake_com_resultado([])
    monkeypatch.setattr(mc, "diagnosticar_persistencia", lambda: {"ok": True, "etapa": "OK", "detalhe": ""})
    monkeypatch.setattr(mc, "obter_cliente", lambda: cliente)
    monkeypatch.setattr(
        mc, "listar_assinantes_morning_call",
        lambda *_a, **_k: ["segredo-pessoal@exemplo.com"],
    )
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "registrar_tentativa", lambda *a, **k: None)

    mc.executar()

    saida = capsys.readouterr().out
    assert "segredo-pessoal@exemplo.com" not in saida
    assert mc._hash_destinatario("segredo-pessoal@exemplo.com") in saida


def test_enviar_teste_usa_destinatario_fixo_e_nunca_consulta_assinantes(monkeypatch):
    """Envio administrativo/manual (enviar_teste) é inteiramente
    separado do automático: nunca chama listar_assinantes_morning_call
    nem grava em morning_call_execucoes (não pode contaminar a
    idempotência diária de nenhum assinante real nem contar como envio
    de assinante). Assunto marcado [TESTE]."""
    chamadas_envio = []

    def _assinantes_nao_deveria_ser_chamado(*_a, **_k):
        raise AssertionError("enviar_teste nunca deve consultar a lista de assinantes")

    monkeypatch.setattr(mc, "listar_assinantes_morning_call", _assinantes_nao_deveria_ser_chamado)
    monkeypatch.setattr(mc, "montar_morning_call", lambda *_a, **_k: "texto")
    monkeypatch.setattr(mc, "enviar_email", lambda *a, **k: chamadas_envio.append((a, k)) or {"ok": True, "erro": None})

    resultado = mc.enviar_teste("admin-teste@exemplo.com")

    assert resultado == {"ok": True, "erro": None}
    assert len(chamadas_envio) == 1
    args, kwargs = chamadas_envio[0]
    assert kwargs.get("destinatario") == "admin-teste@exemplo.com"
    assert "[TESTE]" in args[0]


def test_enviar_teste_sem_destinatario_retorna_erro_sem_enviar(monkeypatch):
    monkeypatch.setattr(mc, "enviar_email", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("não deveria enviar sem destinatário")))
    resultado = mc.enviar_teste("")
    assert resultado["ok"] is False
    assert "obrigat" in resultado["erro"].lower()


def test_main_com_env_de_teste_chama_enviar_teste_nunca_executar(monkeypatch):
    """Compatibilidade com o workflow_dispatch do PR #40
    (.github/workflows/radar-morning-call.yml, input teste_destinatario
    -> env MORNING_CALL_TESTE_PARA): presente, só dispara enviar_teste
    (nunca o envio AGENDADO real aos assinantes)."""
    chamadas = {"teste": [], "executar": []}
    monkeypatch.setattr(mc, "enviar_teste", lambda destinatario: chamadas["teste"].append(destinatario) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "executar", lambda: chamadas["executar"].append(1) or 0)
    monkeypatch.setenv("MORNING_CALL_TESTE_PARA", "ops-teste@exemplo.com")

    codigo = mc._main()

    assert codigo == 0
    assert chamadas["teste"] == ["ops-teste@exemplo.com"]
    assert chamadas["executar"] == []


def test_main_sem_env_de_teste_chama_executar_normal(monkeypatch):
    chamadas = {"teste": [], "executar": []}
    monkeypatch.setattr(mc, "enviar_teste", lambda destinatario: chamadas["teste"].append(destinatario) or {"ok": True, "erro": None})
    monkeypatch.setattr(mc, "executar", lambda: chamadas["executar"].append(1) or 0)
    monkeypatch.delenv("MORNING_CALL_TESTE_PARA", raising=False)

    codigo = mc._main()

    assert codigo == 0
    assert chamadas["executar"] == [1]
    assert chamadas["teste"] == []


def test_montar_morning_call_html_escapa_conteudo_perigoso():
    """Título/manchete de notícia é texto de fonte externa - nunca pode
    injetar HTML/script no e-mail gerado."""
    texto = "MORNING CALL — 16/10/2026\nPregão\n\n5. EMPRESAS E SETORES\n- <script>alert(1)</script> & \"aspas\""
    html_gerado = mc.montar_morning_call_html(texto)
    assert "<script>" not in html_gerado
    assert "&lt;script&gt;" in html_gerado
