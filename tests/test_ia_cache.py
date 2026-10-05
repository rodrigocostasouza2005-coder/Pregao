# -*- coding: utf-8 -*-
"""Testes do cache GLOBAL de resumos de IA (data/ia_cache.py, tabela
resumos_ia_cache) - usado por Research (data/research/resumir.py) e
News (data/news.py:obter_resumo_grupo). Mocka o cliente Supabase (uma
fake simples que simula a tabela em memoria, incluindo a falha de
INSERT por chave duplicada que o Postgres daria de verdade) - nunca faz
chamada de rede nem de IA.

Uso: python tests/test_ia_cache.py (python do .venv do projeto)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.ia_cache as ia_cache_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)


# ============================================================
# Fake de cliente Supabase - simula resumos_ia_cache em memoria,
# incluindo a falha de INSERT por PRIMARY KEY duplicada (mesmo
# comportamento que o Postgres real daria numa corrida verdadeira).
# ============================================================

class _TabelaFake:
    def __init__(self, cliente):
        self.cliente = cliente
        self._filtro_chave = None
        self._op = None
        self._payload = None

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, campo, valor):
        if campo == "chave_documento":
            self._filtro_chave = valor
        return self

    def limit(self, _n):
        return self

    def execute(self):
        c = self.cliente
        chave = self._filtro_chave
        if self._op == "select":
            linha = c.linhas.get(chave)
            resp = MagicMock()
            resp.data = [linha] if linha else []
            return resp
        if self._op == "insert":
            chave_ins = self._payload["chave_documento"]
            if chave_ins in c.linhas or chave_ins in c.falhar_insert_chaves:
                raise Exception("duplicate key value violates unique constraint")
            c.linhas[chave_ins] = dict(self._payload)
            c.inserts.append(dict(self._payload))
            resp = MagicMock()
            resp.data = [dict(self._payload)]
            return resp
        if self._op == "update":
            if chave in c.linhas:
                c.linhas[chave].update(self._payload)
            c.updates.append((chave, dict(self._payload)))
            resp = MagicMock()
            resp.data = []
            return resp
        if self._op == "delete":
            c.linhas.pop(chave, None)
            c.deletes.append(chave)
            resp = MagicMock()
            resp.data = []
            return resp
        raise AssertionError(f"operacao nao mockada: {self._op}")


class _ClienteFake:
    def __init__(self):
        self.linhas = {}
        self.inserts = []
        self.updates = []
        self.deletes = []
        self.falhar_insert_chaves = set()

    def table(self, nome):
        assert nome == "resumos_ia_cache"
        return _TabelaFake(self)


# ============================================================
# 1. cache hit -> zero chamada a IA
# ============================================================

def test_1_cache_hit_zero_chamada_ia():
    cliente = _ClienteFake()
    cliente.linhas["chaveA"] = {
        "chave_documento": "chaveA", "status": "concluido",
        "resultado": {"resumo": "ja pronto"}, "criado_em": ia_cache_mod._agora_iso(),
    }
    chamadas = []
    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache(
            "chaveA", "https://x.com", "research", lambda: chamadas.append(1) or {"resumo": "novo"},
        )
    _checar("1a cache hit retorna o resultado cacheado", resultado == {"resumo": "ja pronto"})
    _checar("1b zero chamada a IA (gerar_fn nunca executado)", chamadas == [])


# ============================================================
# 2. cache miss -> gera e persiste
# ============================================================

def test_2_cache_miss_gera_e_persiste():
    cliente = _ClienteFake()
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "resumo novo", "motivo_indisponivel": None}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveB", "https://y.com", "research", gerar)
    _checar("2a cache miss chama gerar_fn exatamente 1 vez", chamadas == [1])
    _checar("2b resultado da geracao e' retornado", resultado["resumo"] == "resumo novo")
    _checar("2c resultado persistido no cache com status concluido", cliente.linhas["chaveB"]["status"] == "concluido")
    _checar("2d resultado completo gravado na linha", cliente.linhas["chaveB"]["resultado"] == resultado)


# ============================================================
# 3. dois pedidos simultaneos nao geram duplicado
# ============================================================

def test_3_pedido_que_perde_a_corrida_espera_e_reusa_sem_gerar():
    cliente = _ClienteFake()
    # simula outra requisicao que JA reservou a geracao (linha existe, 'gerando')
    cliente.linhas["chaveD"] = {
        "chave_documento": "chaveD", "status": "gerando",
        "resultado": None, "criado_em": ia_cache_mod._agora_iso(),
    }

    contador = {"n": 0}

    def _completar_apos_2_polls(*_a, **_k):
        contador["n"] += 1
        if contador["n"] >= 2:
            cliente.linhas["chaveD"]["status"] = "concluido"
            cliente.linhas["chaveD"]["resultado"] = {"resumo": "resumo da geracao concorrente"}

    chamadas = []

    def gerar_perdedor():
        chamadas.append(1)
        return {"resumo": "NUNCA deveria gerar isso"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente), \
         patch.object(ia_cache_mod.time, "sleep", side_effect=_completar_apos_2_polls):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveD", "https://w.com", "research", gerar_perdedor)

    _checar("3a quem perde a corrida espera a geracao concorrente em vez de gerar de novo", chamadas == [])
    _checar("3b retorna o resultado da geracao concorrente (nao um novo)",
             resultado == {"resumo": "resumo da geracao concorrente"})


# ============================================================
# 4. Supabase indisponivel -> fallback gracioso
# ============================================================

def test_4a_supabase_indisponivel_fallback_gracioso():
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "gerado sem cache"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=None):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveE", "https://v.com", "research", gerar)
    _checar("4a Supabase indisponivel (obter_cliente=None) -> gera direto sem erro", chamadas == [1])
    _checar("4a resultado da geracao e' retornado normalmente", resultado["resumo"] == "gerado sem cache")


def test_4b_tabela_ausente_nao_quebra_nem_bloqueia():
    cliente = MagicMock()
    cliente.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = Exception("PGRST205")
    cliente.table.return_value.insert.return_value.execute.side_effect = Exception("PGRST205")
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "gerado sem tabela"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveF", "https://u.com", "research", gerar)
    _checar("4b tabela ausente (erro de schema) -> gera direto, sem travar nem levantar excecao", chamadas == [1])
    _checar("4b resultado retornado normalmente mesmo com banco quebrado", resultado["resumo"] == "gerado sem tabela")


def test_4c_insert_falha_por_erro_de_infra_nao_espera_a_toa():
    """Insert pode falhar por 2 motivos bem diferentes: corrida real
    (outra reserva ja existe - vale esperar) ou erro de infra (banco/
    tabela com problema - esperar 10s a toa so' atrasaria o usuario sem
    chance de dar certo). So' o 1o caso deve acionar a espera."""
    cliente = _ClienteFake()
    cliente.falhar_insert_chaves.add("chaveI")  # insert falha mas NENHUMA linha concorrente existe de verdade
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "gerado sem cache por erro de infra"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente), \
         patch.object(ia_cache_mod.time, "sleep", side_effect=AssertionError("nao deveria esperar - nao e' corrida real")):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveI", "https://r.com", "research", gerar)
    _checar("4c insert falha por erro de infra (nao corrida real) -> gera direto, sem esperar 10s a toa", chamadas == [1])
    _checar("4c resultado retornado normalmente", resultado["resumo"] == "gerado sem cache por erro de infra")


# ============================================================
# 5. usuarios diferentes recebem o mesmo resumo
# ============================================================

def test_5_usuarios_diferentes_recebem_o_mesmo_resumo():
    cliente = _ClienteFake()
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "resumo compartilhado"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado_usuario1 = ia_cache_mod.obter_resumo_com_cache("chaveG", "https://t.com", "news", gerar)
        resultado_usuario2 = ia_cache_mod.obter_resumo_com_cache("chaveG", "https://t.com", "news", gerar)

    _checar("5a IA chamada so' 1 vez (usuario2 reusa o cache do usuario1)", chamadas == [1])
    _checar("5b usuario2 recebe o MESMO resumo que o usuario1 gerou", resultado_usuario1 == resultado_usuario2)


# ============================================================
# 6. documento diferente gera cache separado
# ============================================================

def test_6a_chaves_de_documentos_diferentes_sao_diferentes():
    _checar("6a chave_research de links diferentes e' diferente",
             ia_cache_mod.chave_research("https://a.com/1") != ia_cache_mod.chave_research("https://a.com/2"))
    _checar("6b chave_news de titulos diferentes e' diferente",
             ia_cache_mod.chave_news("Fato A", ("https://x.com",)) != ia_cache_mod.chave_news("Fato B", ("https://x.com",)))
    _checar("6c chave_news muda se o CONJUNTO de links do grupo mudar (fonte nova entrou no grupo)",
             ia_cache_mod.chave_news("Fato A", ("https://x.com",))
             != ia_cache_mod.chave_news("Fato A", ("https://x.com", "https://y.com")))
    _checar("6d chave_news e' estavel independente da ORDEM dos links (mesmo conjunto de fontes)",
             ia_cache_mod.chave_news("Fato A", ("https://x.com", "https://y.com"))
             == ia_cache_mod.chave_news("Fato A", ("https://y.com", "https://x.com")))


def test_6e_documentos_diferentes_geram_cache_separado_de_verdade():
    cliente = _ClienteFake()
    chamadas = []

    def _gerar(nome):
        chamadas.append(nome)
        return {"resumo": f"resumo de {nome}"}

    chave1 = ia_cache_mod.chave_research("https://doc1.com")
    chave2 = ia_cache_mod.chave_research("https://doc2.com")
    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        r1 = ia_cache_mod.obter_resumo_com_cache(chave1, "https://doc1.com", "research", lambda: _gerar("doc1"))
        r2 = ia_cache_mod.obter_resumo_com_cache(chave2, "https://doc2.com", "research", lambda: _gerar("doc2"))
    _checar("6e documentos diferentes GERAM cada um (nenhum reaproveita do outro)", chamadas == ["doc1", "doc2"])
    _checar("6f cada documento guarda o PROPRIO resultado, sem vazar pro outro",
             r1["resumo"] == "resumo de doc1" and r2["resumo"] == "resumo de doc2")


# ============================================================
# extra: reserva abandonada (processo morreu no meio da geracao) e'
# liberada em vez de bloquear pra sempre
# ============================================================

def test_7_reserva_abandonada_e_liberada_e_regerada():
    cliente = _ClienteFake()
    antigo = datetime.now(timezone.utc) - timedelta(seconds=ia_cache_mod._ABANDONO_SEGUNDOS + 30)
    cliente.linhas["chaveH"] = {
        "chave_documento": "chaveH", "status": "gerando",
        "resultado": None, "criado_em": antigo.isoformat(),
    }
    chamadas = []

    def gerar():
        chamadas.append(1)
        return {"resumo": "resumo apos reserva abandonada"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveH", "https://s.com", "research", gerar)
    _checar("7a reserva 'gerando' antiga (processo morto) e' liberada e regerada", chamadas == [1])
    _checar("7b novo resultado persistido com sucesso", cliente.linhas["chaveH"]["status"] == "concluido")


def test_8_geracao_sem_sucesso_libera_a_reserva_em_vez_de_travar():
    cliente = _ClienteFake()
    chamadas = []

    def gerar_falha():
        chamadas.append(1)
        return {"resumo": None, "motivo_indisponivel": "cota"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado = ia_cache_mod.obter_resumo_com_cache("chaveJ", "https://q.com", "research", gerar_falha)
    _checar("8a geracao sem resumo (falha de IA) nao fica marcada como cache valido", resultado["resumo"] is None)
    _checar("8b reserva e' liberada (linha removida) em vez de travar 'gerando' pra sempre", "chaveJ" not in cliente.linhas)

    # uma 2a tentativa (ex: usuario clica de novo) deve poder gerar normalmente de novo
    chamadas2 = []

    def gerar_sucesso():
        chamadas2.append(1)
        return {"resumo": "funcionou na 2a tentativa"}

    with patch.object(ia_cache_mod, "obter_cliente", return_value=cliente):
        resultado2 = ia_cache_mod.obter_resumo_com_cache("chaveJ", "https://q.com", "research", gerar_sucesso)
    _checar("8c nova tentativa gera normalmente (reserva anterior nao bloqueou)", chamadas2 == [1])
    _checar("8d resultado da 2a tentativa persistido", resultado2["resumo"] == "funcionou na 2a tentativa")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO CACHE GLOBAL DE RESUMOS DE IA PASSARAM")
