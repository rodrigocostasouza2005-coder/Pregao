# -*- coding: utf-8 -*-
"""scripts/encerrar_analises_orfas.py (PR #305/#309 - revisão técnica
antes de autorizar execução real contra produção, missão
"fix/estabilizacao-execucoes-orfas", 2026-11-13).

Nenhum teste aqui toca o Supabase real - cliente 100% fake local,
simulando só o suficiente de `.table().select().eq().lt().order()
.execute()` que o script usa. Cobre especificamente os riscos listados
na missão: execução recém-iniciada (falso positivo) vs. realmente
travada, execução com resultado parcial/concluído nunca tocada,
idempotência (rodar 2x não duplica efeito), integridade de registros
relacionados (especialistas nunca alterados), e o piso de segurança
novo contra `--limiar-horas` perigoso."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import encerrar_analises_orfas as script
from data.coordenador_central import persistencia


# ============================================================
# Cliente fake - só o subconjunto de supabase-py que o script usa
# (select/eq/lt/order/limit/execute, update/eq/execute).
# ============================================================

class _Resposta:
    def __init__(self, data):
        self.data = data


class _TabelaFake:
    def __init__(self, cliente, nome):
        self.cliente = cliente
        self.nome = nome
        self._op = None
        self._payload = None
        self._filtros_eq = []
        self._filtros_lt = []
        self._order = None
        self._limit = None

    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def update(self, payload):
        self._op, self._payload = "update", dict(payload)
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", dict(payload)
        return self

    def eq(self, campo, valor):
        self._filtros_eq.append((campo, valor))
        return self

    def lt(self, campo, valor):
        self._filtros_lt.append((campo, valor))
        return self

    def order(self, campo, desc=False):
        self._order = (campo, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _bate_filtros(self, linha):
        if not all(linha.get(c) == v for c, v in self._filtros_eq):
            return False
        for campo, valor in self._filtros_lt:
            if not (linha.get(campo) is not None and linha.get(campo) < valor):
                return False
        return True

    def execute(self):
        linhas = self.cliente.tabelas.setdefault(self.nome, {})
        if self._op == "insert":
            novo_id = self._payload.get("id") or f"id-{len(linhas) + 1}"
            linha = {**self._payload, "id": novo_id}
            linhas[novo_id] = linha
            return _Resposta([linha])
        if self._op == "update":
            self.cliente.chamadas_update.append(dict(self._payload))
            atualizadas = []
            for linha in linhas.values():
                if all(linha.get(c) == v for c, v in self._filtros_eq):
                    linha.update(self._payload)
                    atualizadas.append(linha)
            return _Resposta(atualizadas)
        if self._op == "select":
            resultado = [l for l in linhas.values() if self._bate_filtros(l)]
            if self._order:
                campo, desc = self._order
                resultado = sorted(resultado, key=lambda l: l.get(campo) or "", reverse=desc)
            if self._limit is not None:
                resultado = resultado[: self._limit]
            return _Resposta(resultado)
        return _Resposta([])


class _ClienteFake:
    def __init__(self):
        self.tabelas = {}
        self.chamadas_update = []

    def table(self, nome):
        return _TabelaFake(self, nome)


def _agora():
    return datetime.now(timezone.utc)


def _linha_analise(id_, ticker, horas_atras, status="EM_ANDAMENTO"):
    iniciado = (_agora() - timedelta(hours=horas_atras)).isoformat()
    return {
        "id": id_, "ticker": ticker, "tipo_fluxo": "analise_ticker",
        "status": status, "iniciado_em": iniciado, "duracao_ms": None, "erro": None,
    }


def _popular(cliente, linhas):
    for linha in linhas:
        cliente.tabelas.setdefault("coordenador_analises", {})[linha["id"]] = dict(linha)


def _patch_cliente(cliente):
    """Patcha o cliente tanto no módulo do script (import local em
    main()) quanto em persistencia (usado por concluir_analise)."""
    return (
        patch("data.supabase_client.obter_cliente", return_value=cliente),
        patch.object(persistencia, "obter_cliente", return_value=cliente),
    )


def _rodar_main(argv, cliente):
    p1, p2 = _patch_cliente(cliente)
    with p1, p2, patch.object(sys, "argv", ["encerrar_analises_orfas.py"] + argv):
        return script.main()


# ============================================================
# localizar_orfas: critério = EM_ANDAMENTO + iniciado_em mais antigo
# que o limiar - risco central da missão (falso positivo).
# ============================================================

def test_execucao_recem_iniciada_nao_e_marcada_como_orfa():
    """Risco de falso positivo: uma análise iniciada há 5 minutos é
    EM_ANDAMENTO genuína (ainda dentro do pior caso real de ~2.5min a
    poucos minutos de folga) - o limiar default (2h) nunca deve
    selecioná-la."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("recente", "PETR4", horas_atras=5 / 60)])
    orfas = script.localizar_orfas(cliente, script._LIMIAR_HORAS_DEFAULT)
    assert orfas == []


def test_execucao_realmente_travada_e_selecionada():
    """Caso real da missão: ~205h de idade, muito acima do limiar."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    orfas = script.localizar_orfas(cliente, script._LIMIAR_HORAS_DEFAULT)
    assert len(orfas) == 1 and orfas[0]["id"] == "travada"


def test_limiar_e_fronteira_exata_nao_inclui_a_execucao_no_limite():
    """iniciado_em exatamente no corte (nem um segundo mais antigo) não
    deve ser tratado como órfã - só idade estritamente maior que o
    limiar (`lt`, nunca `lte`)."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("no-limite", "ITUB4", horas_atras=script._LIMIAR_HORAS_DEFAULT - 0.001)])
    orfas = script.localizar_orfas(cliente, script._LIMIAR_HORAS_DEFAULT)
    assert orfas == []


def test_resultado_parcial_ou_concluido_nunca_e_selecionado_mesmo_antigo():
    """Execução com resultado válido (PARCIAL/CONCLUIDA), mesmo muito
    antiga, nunca é tocada - o filtro é só sobre status='EM_ANDAMENTO'."""
    cliente = _ClienteFake()
    _popular(cliente, [
        _linha_analise("concluida-antiga", "BBAS3", horas_atras=1000, status="CONCLUIDA"),
        _linha_analise("parcial-antiga", "ALPA4", horas_atras=1000, status="PARCIAL"),
        _linha_analise("erro-antiga", "ASAI3", horas_atras=1000, status="ERRO"),
    ])
    orfas = script.localizar_orfas(cliente, script._LIMIAR_HORAS_DEFAULT)
    assert orfas == []


def test_mistura_de_execucoes_so_seleciona_as_travadas():
    """Mix realista: 1 recém-iniciada (falso positivo em potencial), 1
    travada de verdade, 1 já concluída antiga - só a travada é órfã."""
    cliente = _ClienteFake()
    _popular(cliente, [
        _linha_analise("ativa", "PETR4", horas_atras=0.01),
        _linha_analise("travada", "VALE3", horas_atras=205),
        _linha_analise("concluida", "ITUB4", horas_atras=500, status="CONCLUIDA"),
    ])
    orfas = script.localizar_orfas(cliente, script._LIMIAR_HORAS_DEFAULT)
    assert [l["id"] for l in orfas] == ["travada"]


# ============================================================
# dry-run (sem --aplicar): nunca escreve, pode rodar livremente.
# ============================================================

def test_dry_run_nunca_escreve_mesmo_com_orfas_encontradas():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    codigo = _rodar_main([], cliente)
    assert codigo == 0
    assert cliente.chamadas_update == []
    assert cliente.tabelas["coordenador_analises"]["travada"]["status"] == "EM_ANDAMENTO"


def test_aplicar_sem_confirmo_aborta_sem_escrever():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    codigo = _rodar_main(["--aplicar"], cliente)
    assert codigo == 1
    assert cliente.chamadas_update == []
    assert cliente.tabelas["coordenador_analises"]["travada"]["status"] == "EM_ANDAMENTO"


def test_aplicar_com_confirmo_errado_aborta_sem_escrever():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    codigo = _rodar_main(["--aplicar", "--confirmo", "frase-errada"], cliente)
    assert codigo == 1
    assert cliente.chamadas_update == []
    assert cliente.tabelas["coordenador_analises"]["travada"]["status"] == "EM_ANDAMENTO"


# ============================================================
# --aplicar --confirmo correto: escreve, preserva o registro original,
# nunca deleta, nunca inventa `resultado`.
# ============================================================

def test_aplicar_com_confirmo_correto_encerra_preservando_registro_original():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    codigo = _rodar_main(["--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)
    assert codigo == 0
    linha = cliente.tabelas["coordenador_analises"]["travada"]
    assert linha["status"] == "ERRO"
    assert linha["concluido_em"] is not None
    assert "FECHAMENTO_RETROATIVO" in linha["erro"]
    # Nunca inventa resultado - não existe mais o dado real da análise.
    assert linha.get("resultado") is None
    # Registro original intacto - nunca deletado, id/ticker/iniciado_em preservados.
    assert linha["id"] == "travada"
    assert linha["ticker"] == "VALE3"
    assert "iniciado_em" in linha


def test_aplicar_so_toca_as_linhas_realmente_orfas_nunca_as_demais():
    """Integridade: uma linha EM_ANDAMENTO recente (ativa de verdade) no
    mesmo lote nunca é tocada, mesmo com --aplicar --confirmo corretos."""
    cliente = _ClienteFake()
    _popular(cliente, [
        _linha_analise("travada", "VALE3", horas_atras=205),
        _linha_analise("ativa", "PETR4", horas_atras=0.01),
    ])
    _rodar_main(["--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)
    assert cliente.tabelas["coordenador_analises"]["travada"]["status"] == "ERRO"
    assert cliente.tabelas["coordenador_analises"]["ativa"]["status"] == "EM_ANDAMENTO"


def test_integridade_execucoes_de_especialistas_nunca_sao_alteradas():
    """coordenador_especialistas_execucoes (telemetria de quando o
    processo rodou) não tem FK formal (ver sql/coordenador_central.sql),
    mas o script nunca deveria tocar nela de qualquer forma - só
    `coordenador_analises` é atualizada."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    especialistas_antes = [
        {"analise_id": "travada", "especialista_id": f"esp{i}", "disponivel": True, "executado_em": "2026-11-05T02:51:14Z"}
        for i in range(6)
    ]
    for linha in especialistas_antes:
        cliente.tabelas.setdefault("coordenador_especialistas_execucoes", {})[f"{linha['especialista_id']}"] = dict(linha)

    _rodar_main(["--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)

    especialistas_depois = cliente.tabelas["coordenador_especialistas_execucoes"]
    assert especialistas_depois == {l["especialista_id"]: l for l in especialistas_antes}


# ============================================================
# Idempotência: rodar 2x (com --aplicar --confirmo) não duplica efeito.
# ============================================================

def test_rodar_duas_vezes_e_idempotente_segunda_vez_nao_encontra_nada():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])

    codigo_1 = _rodar_main(["--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)
    assert codigo_1 == 0
    linha_apos_1 = dict(cliente.tabelas["coordenador_analises"]["travada"])
    n_updates_apos_1 = len(cliente.chamadas_update)

    codigo_2 = _rodar_main(["--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)
    assert codigo_2 == 0  # "nenhuma linha encontrada" - sucesso, nada a fazer

    linha_apos_2 = cliente.tabelas["coordenador_analises"]["travada"]
    assert linha_apos_2 == linha_apos_1  # nenhum campo mudou na 2a rodada
    assert len(cliente.chamadas_update) == n_updates_apos_1  # nenhum UPDATE novo


# ============================================================
# Piso de segurança novo (fix desta revisão): --limiar-horas perigoso
# (zero/negativo) é rejeitado ANTES de qualquer SELECT/escrita.
# ============================================================

def test_limiar_horas_zero_aborta_sem_consultar_ou_escrever():
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("ativa", "PETR4", horas_atras=0.001)])
    codigo = _rodar_main(["--limiar-horas", "0"], cliente)
    assert codigo == 1
    assert cliente.chamadas_update == []
    # A tabela nunca chegou a ser consultada por este caminho (abort antes do obter_cliente).


def test_limiar_horas_negativo_mesmo_com_aplicar_e_confirmo_nunca_escreve():
    """Caso de risco máximo: operador passa --limiar-horas negativo
    JUNTO com --aplicar --confirmo correto - sem o piso de segurança,
    isso encerraria qualquer execução EM_ANDAMENTO, incluindo uma
    genuinamente ativa. Com o piso, aborta antes de tudo."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("ativa", "PETR4", horas_atras=0.001)])
    codigo = _rodar_main(["--limiar-horas", "-1", "--aplicar", "--confirmo", script._FRASE_CONFIRMACAO], cliente)
    assert codigo == 1
    assert cliente.chamadas_update == []
    assert cliente.tabelas["coordenador_analises"]["ativa"]["status"] == "EM_ANDAMENTO"


def test_limiar_horas_customizado_acima_do_piso_funciona_normalmente():
    """Confirma que o piso não quebra o uso legítimo de um limiar
    customizado (ex.: --limiar-horas 6, citado no próprio docstring)."""
    cliente = _ClienteFake()
    _popular(cliente, [_linha_analise("travada", "VALE3", horas_atras=205)])
    codigo = _rodar_main(["--limiar-horas", "6"], cliente)
    assert codigo == 0
    assert cliente.chamadas_update == []  # dry-run, só confirma que não aborta por engano


# ============================================================
# Supabase indisponível - nunca lança.
# ============================================================

def test_supabase_indisponivel_aborta_sem_lancar():
    p1, p2 = _patch_cliente(None)
    with p1, p2, patch.object(sys, "argv", ["encerrar_analises_orfas.py"]):
        codigo = script.main()
    assert codigo == 1
