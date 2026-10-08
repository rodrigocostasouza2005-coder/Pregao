# -*- coding: utf-8 -*-
"""Testes da FASE 3 (2026-10-08) pro lado RESEARCH do feed editorial:

- data/research/genial_lives.py: publicado_em (timestamp completo, so'
  usado pra posicionar Morning Call/lives cronologicamente no feed do
  NEWS) extraído do MESMO feed RSS já usado pros metadados - nunca uma
  fonte nova; 'data' (so' o dia) continua intocado.
- data/research/store.py: publicado_em passa pelo upsert de forma
  aditiva/graciosa - nunca quebra a coleta de TODAS as casas so' porque
  a coluna nova ainda nao existe no banco de quem esta rodando.
- data/research/resumir.py: prompt do foco MORNING_CALL reescrito pra
  pedir estrutura real (O QUE IMPORTA HOJE/DESTAQUES) em vez de resumo
  generico, sem abrir mao da regra de nunca inventar.

Tudo mockado (feedparser, Supabase) - nenhuma chamada de rede. Uso:
python tests/test_research_fase3.py (python do .venv do projeto)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.research.genial_lives as lives_mod
import data.research.store as store_mod
from data.research.resumir import _FOCO_POR_TIPO, _detectar_foco

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


# ============================================================
# 1. genial_lives.py - publicado_em (hora real, mesmo feed de sempre)
# ============================================================

class _EntryFake(dict):
    """feedparser.FeedParserDict se comporta como dict com .get() -
    um dict puro serve igual pros campos que obter_relatorios usa."""


def test_1a_publicado_em_extraido_do_mesmo_feed():
    entry = _EntryFake({
        "title": "Morning Call - 08/10",
        "yt_videoid": "abc123",
        "published": "2026-10-08T08:30:00+00:00",
        "published_parsed": (2026, 10, 8, 8, 30, 0, 0, 0, 0),
    })
    feed_fake = MagicMock()
    feed_fake.bozo = False
    feed_fake.entries = [entry]
    with patch.object(lives_mod.feedparser, "parse", return_value=feed_fake):
        relatorios = lives_mod.obter_relatorios()
    _checar("1a exatamente 1 relatorio reconhecido", len(relatorios) == 1)
    _checar("1b 'data' continua so' o dia (campo antigo intocado)", relatorios[0]["data"] == "2026-10-08")
    _checar("1c 'publicado_em' tem o timestamp COMPLETO (ISO, com hora)", relatorios[0]["publicado_em"] == "2026-10-08T08:30:00+00:00")


def test_1a2_data_usa_fuso_de_sp_nunca_a_data_crua_em_utc():
    # bug real corrigido (2026-10-08): video publicado as 22:30 BRT (ex:
    # "Fechamento de Mercado") vira 01:30 UTC do dia SEGUINTE - o campo
    # 'published' (string crua do feed, em UTC) ja' mostra a data
    # errada. 'data' precisa vir da CONVERSAO pro fuso de Brasilia, nao
    # da string crua.
    entry = _EntryFake({
        "title": "Fechamento de Mercado - 08/10",
        "yt_videoid": "def456",
        "published": "2026-10-09T01:30:00+00:00",
        "published_parsed": (2026, 10, 9, 1, 30, 0, 0, 0, 0),
    })
    feed_fake = MagicMock()
    feed_fake.bozo = False
    feed_fake.entries = [entry]
    with patch.object(lives_mod.feedparser, "parse", return_value=feed_fake):
        relatorios = lives_mod.obter_relatorios()
    _checar("1a2 'data' e' 08/10 em BRT (nao 09/10, a data crua em UTC)",
             relatorios[0]["data"] == "2026-10-08", f"(data={relatorios[0]['data']!r})")
    _checar("1a2b 'publicado_em' continua em UTC (ISO completo, intocado - so' 'data' muda de fuso)",
             relatorios[0]["publicado_em"] == "2026-10-09T01:30:00+00:00")


def test_1c_item_malformado_nao_derruba_os_demais():
    # isolado por item (2026-10-08): entry sem 'title' (AttributeError/
    # TypeError dentro de _identificar_programa) nao pode descartar os
    # videos que ja parsearam certo.
    entry_boa = _EntryFake({
        "title": "Morning Call - 08/10", "yt_videoid": "abc123",
        "published": "2026-10-08T08:30:00+00:00",
        "published_parsed": (2026, 10, 8, 8, 30, 0, 0, 0, 0),
    })

    class _EntryQuebra(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("feed malformado")

    feed_fake = MagicMock()
    feed_fake.bozo = False
    feed_fake.entries = [_EntryQuebra(), entry_boa]
    with patch.object(lives_mod.feedparser, "parse", return_value=feed_fake):
        relatorios = lives_mod.obter_relatorios()
    _checar("1c item malformado e' ignorado, o item bom continua aparecendo",
             len(relatorios) == 1 and relatorios[0]["titulo"] == "Morning Call - 08/10",
             f"(relatorios={relatorios})")


def test_1b_sem_published_parsed_publicado_em_e_none():
    """Nunca inventa hora - se o feed nao trouxer o campo estruturado,
    publicado_em fica None (quem usa cai pro meio-dia so' pra ordenar,
    nunca EXIBE uma hora que nao existe - ver ui/news_tab.py)."""
    entry = _EntryFake({"title": "Resumo da Manhã", "yt_videoid": "xyz", "published": ""})
    feed_fake = MagicMock()
    feed_fake.bozo = False
    feed_fake.entries = [entry]
    with patch.object(lives_mod.feedparser, "parse", return_value=feed_fake):
        relatorios = lives_mod.obter_relatorios()
    _checar("1d sem published_parsed -> publicado_em None (nunca inventado)", relatorios[0]["publicado_em"] is None)
    _checar("1e 'data' vazia tambem (nenhum dado estruturado disponivel)", relatorios[0]["data"] == "")


# ============================================================
# 2. store.py - publicado_em aditivo, nunca quebra a coleta inteira
# ============================================================

def _cliente_upsert(efeitos):
    """efeitos: lista de (Exception|None) - 1 por chamada de upsert().execute(),
    na ordem. Permite simular '1a tentativa falha, 2a funciona'."""
    cliente = MagicMock()

    def _execute():
        efeito = efeitos.pop(0)
        if efeito is not None:
            raise efeito
        return MagicMock()

    cliente.table.return_value.upsert.return_value.execute.side_effect = _execute
    return cliente


def test_2a_item_com_publicado_em_inclui_a_coluna():
    cliente = _cliente_upsert([None])
    itens = [{"link": "https://yt/1", "casa": "Genial (Lives)", "titulo": "Morning Call", "data": "2026-10-08",
              "publicado_em": "2026-10-08T08:30:00+00:00", "autor": "Morning Call", "tipo": "LIVE", "tickers": []}]
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    payload = cliente.table.return_value.upsert.call_args_list[0].args[0]
    _checar("2a upsert bem-sucedido -> True", ok is True)
    _checar("2b payload inclui publicado_em quando o item tem o campo", payload[0].get("publicado_em") == "2026-10-08T08:30:00+00:00")
    _checar("2c so' 1 tentativa de upsert (sucesso de primeira)", cliente.table.return_value.upsert.call_count == 1)


def test_2b_sem_nenhum_item_com_publicado_em_coluna_nunca_vai_no_payload():
    """Casas que nao sao Genial Lives nao preenchem publicado_em - o
    payload nem deve mandar a chave (comportamento IDENTICO a antes
    desta fase pra essas casas)."""
    cliente = _cliente_upsert([None])
    itens = [{"link": "https://x.com/1", "casa": "XP Investimentos", "titulo": "Relatório X", "data": "2026-10-08",
              "autor": "", "tipo": "ACOES", "tickers": ["PETR4"]}]
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        store_mod.salvar_itens(itens)
    payload = cliente.table.return_value.upsert.call_args_list[0].args[0]
    _checar("2d sem publicado_em em NENHUM item -> chave nem aparece no payload", "publicado_em" not in payload[0])


def test_2c_coluna_ausente_no_banco_cai_pro_retry_sem_ela():
    """Simula Supabase do usuario ainda sem a migracao (coluna
    publicado_em nao existe) - 1a tentativa (com a coluna) falha, retry
    SEM a coluna deve funcionar - a coleta de TODAS as casas no lote nao
    pode quebrar so' por isso."""
    cliente = _cliente_upsert([Exception("column research_itens.publicado_em does not exist"), None])
    itens = [{"link": "https://yt/2", "casa": "Genial (Lives)", "titulo": "Fechamento", "data": "2026-10-08",
              "publicado_em": "2026-10-08T20:00:00+00:00", "autor": "Fechamento de Mercado", "tipo": "LIVE", "tickers": []}]
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    _checar("2e 1a falha (coluna ausente) nao derruba a coleta - retry funciona", ok is True)
    _checar("2f exatamente 2 tentativas de upsert (1a com a coluna, retry sem ela)", cliente.table.return_value.upsert.call_count == 2)
    payload_retry = cliente.table.return_value.upsert.call_args_list[1].args[0]
    _checar("2g payload do retry NAO tem mais publicado_em", "publicado_em" not in payload_retry[0])


def test_2d_erro_persistente_mesmo_sem_a_coluna_retorna_false():
    cliente = _cliente_upsert([Exception("qualquer erro"), Exception("Supabase fora do ar")])
    itens = [{"link": "https://yt/3", "casa": "Genial (Lives)", "titulo": "X", "data": "2026-10-08",
              "publicado_em": "2026-10-08T20:00:00+00:00", "autor": "", "tipo": "LIVE", "tickers": []}]
    with patch.object(store_mod, "obter_cliente", return_value=cliente):
        ok = store_mod.salvar_itens(itens)
    _checar("2h falha persistente (mesmo apos retry) -> False, nunca excecao propagada", ok is False)


def test_2e_linha_para_item_traz_publicado_em_com_get_seguro():
    linha_com = {"casa": "Genial (Lives)", "titulo": "X", "tipo": "LIVE", "link": "https://yt/4", "publicado_em": "2026-10-08T08:30:00+00:00"}
    linha_sem = {"casa": "XP", "titulo": "Y", "tipo": "ACOES", "link": "https://x.com/5"}
    _checar("2i linha com a coluna -> publicado_em presente", store_mod._linha_para_item(linha_com)["publicado_em"] == "2026-10-08T08:30:00+00:00")
    _checar("2j linha sem a coluna (banco nao migrado ainda) -> None, sem KeyError", store_mod._linha_para_item(linha_sem)["publicado_em"] is None)


# ============================================================
# 3. resumir.py - prompt do Morning Call reescrito (estrutura real)
# ============================================================

def test_3a_foco_morning_call_pede_estrutura_real():
    foco = _FOCO_POR_TIPO["MORNING_CALL"]
    _checar("3a pede o bloco O QUE IMPORTA HOJE", "O QUE IMPORTA HOJE" in foco)
    _checar("3b pede o bloco DESTAQUES", "DESTAQUES" in foco)
    _checar("3c probe explicitamente resumo generico", "generico" in foco.lower() or "genérico" in foco.lower())
    _checar("3d reforca FATO vs VISAO DA CASA mesmo no foco especifico", "VISAO DA CASA" in foco.upper() or "VISÃO DA CASA" in foco.upper())
    _checar("3e proibe inventar preco-alvo/recomendacao/consenso", "preco-alvo" in foco.lower() or "preço-alvo" in foco.lower())
    _checar("3f permite nao forcar a estrutura quando nao ha conteudo (nunca template vazio)", "formato narrativo generico" in foco.lower())


def test_3b_detectar_foco_ainda_aponta_genial_lives_pro_morning_call():
    _checar("3g casa Genial (Lives) continua mapeada pro foco MORNING_CALL (sistema reaproveitado, nao duplicado)",
             _detectar_foco("Genial (Lives)", "LIVE") == "MORNING_CALL")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DA FASE 3 (RESEARCH - LIVES/PUBLICADO_EM/PROMPT) PASSARAM")
