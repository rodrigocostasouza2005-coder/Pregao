# -*- coding: utf-8 -*-
"""Testes do modulo isolado/desligado de sinais do X (data/x_signals.py,
FASE 4 da auditoria 2026-10-09). Confirma que o modulo fica
explicitamente desligado (nunca finge uma integracao funcional) e que
nao e' importado por nenhuma UI/app - ver decisao em BACKLOG.md.

Uso: python tests/test_x_signals.py (python do .venv do projeto)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.x_signals as x_signals_mod

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


def test_1_modulo_desligado_por_padrao():
    _checar("1 DISPONIVEL == False", x_signals_mod.DISPONIVEL is False)


def test_2_status_modulo_reporta_motivo_nao_vazio():
    status = x_signals_mod.status_modulo()
    _checar("2a disponivel False", status["disponivel"] is False)
    _checar("2b motivo preenchido (nunca vazio)", bool(status["motivo"]) and len(status["motivo"]) > 20)


def test_3_buscar_sinais_lanca_em_vez_de_fingir():
    try:
        x_signals_mod.buscar_sinais()
        _checar("3 buscar_sinais() lanca NotImplementedError", False)
    except NotImplementedError:
        _checar("3 buscar_sinais() lanca NotImplementedError (nunca retorna [] nem dado inventado)", True)


def test_4_sinal_preserva_todos_os_campos_de_proveniencia():
    sinal = x_signals_mod.Sinal(
        autor="@exemplo", link_original="https://x.com/exemplo/status/1",
        horario_publicacao=datetime(2026, 1, 1, tzinfo=timezone.utc),
        horario_captura=datetime.now(timezone.utc),
        contexto="teste", chave_acontecimento="evento-x",
        nivel_evidencia=x_signals_mod.NivelEvidencia.NAO_CONFIRMADO,
        estado=x_signals_mod.EstadoSinal.DETECTADO,
    )
    _checar("4a autor preservado", sinal.autor == "@exemplo")
    _checar("4b mesma_origem default False", sinal.mesma_origem is False)
    _checar("4c conta_verificada default False", sinal.conta_verificada is False)
    _checar("4d evidencias_confirmacao default lista vazia (nunca None)", sinal.evidencias_confirmacao == [])


def test_5_niveis_de_evidencia_sao_3_e_distintos():
    niveis = {x_signals_mod.NivelEvidencia.NAO_CONFIRMADO, x_signals_mod.NivelEvidencia.EM_VERIFICACAO,
              x_signals_mod.NivelEvidencia.CONFIRMADO}
    _checar("5 3 niveis distintos (Sinal Social/Em Verificacao/Confirmado)", len(niveis) == 3)


def test_6_estados_do_ciclo_de_vida_cobrem_detectado_a_expirado():
    esperados = {"detectado", "em_verificacao", "confirmado", "refutado", "expirado"}
    valores = {e.value for e in x_signals_mod.EstadoSinal}
    _checar("6 ciclo de vida tem os 5 estados pedidos", valores == esperados)


def test_7_modulo_nao_e_importado_por_nenhum_arquivo_de_ui_nem_app():
    raiz = Path(__file__).parent.parent
    arquivos_com_import = []
    for pasta in ("ui", "."):
        for caminho in (raiz / pasta).glob("*.py" if pasta == "." else "*.py"):
            if caminho.name == "test_x_signals.py":
                continue
            texto = caminho.read_text(encoding="utf-8")
            if "x_signals" in texto:
                arquivos_com_import.append(str(caminho.relative_to(raiz)))
    _checar("7 nenhum arquivo de ui/ ou raiz (app.py etc) referencia x_signals",
             arquivos_com_import == [], f"(achados={arquivos_com_import})")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO MODULO X (DESLIGADO) PASSARAM")
