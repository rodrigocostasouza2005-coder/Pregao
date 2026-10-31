# -*- coding: utf-8 -*-
"""Testes do modulo de contrato/conector de sinais do X (data/x_signals.py,
FASE 4 da auditoria 2026-10-09, ligado explicitamente em 2026-10-30 via
data/x_radar/). Confirma que o modulo nunca finge uma integracao
funcional sem credencial valida (status_credencial/buscar_sinais) e que
so' data/x_radar/* pode importa-lo direto - ver decisao em BACKLOG.md.

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
        x_signals_mod.buscar_sinais("PETR4 OR VALE3")
        _checar("3 buscar_sinais(query) lanca NotImplementedError", False)
    except NotImplementedError:
        _checar("3 buscar_sinais(query) lanca NotImplementedError (nunca retorna [] nem dado inventado)", True)


def test_4_sinal_preserva_todos_os_campos_de_proveniencia():
    sinal = x_signals_mod.Sinal(
        post_id="1", autor="@exemplo", link_original="https://x.com/exemplo/status/1",
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


def test_7_modulo_so_e_importado_pela_camada_data_x_radar():
    """Invariante atualizada 2026-10-30 (decisao explicita do Rodrigo de
    ligar a integracao, ver docs/x-radar-inteligencia-social-20261030.md):
    data.x_signals deixou de ser 'nunca importado' e passou a ser
    importado SO por data/x_radar/* (camada que classifica/cruza antes
    de qualquer UI ler algo) - ui/*.py e app.py continuam proibidos de
    importar o conector bruto direto, mesma disciplina de antes, só que
    com um ponto de entrada explícito em vez de zero."""
    import re
    _PADRAO_IMPORT = re.compile(r"^\s*(import\s+data\.x_signals|from\s+data\.x_signals\s+import|from\s+data\s+import\s+.*\bx_signals\b)", re.MULTILINE)

    raiz = Path(__file__).parent.parent
    arquivos_proibidos_com_import = []
    for pasta in ("ui", "."):
        for caminho in (raiz / pasta).glob("*.py"):
            if caminho.name == "test_x_signals.py":
                continue
            texto = caminho.read_text(encoding="utf-8")
            if _PADRAO_IMPORT.search(texto):
                arquivos_proibidos_com_import.append(str(caminho.relative_to(raiz)))
    _checar("7a nenhum arquivo de ui/ ou raiz (app.py etc) importa x_signals direto",
             arquivos_proibidos_com_import == [], f"(achados={arquivos_proibidos_com_import})")

    pasta_x_radar = raiz / "data" / "x_radar"
    algum_arquivo_importa = any(
        _PADRAO_IMPORT.search(caminho.read_text(encoding="utf-8"))
        for caminho in pasta_x_radar.glob("*.py")
    ) if pasta_x_radar.is_dir() else False
    _checar("7b data/x_radar/ e' o unico ponto de entrada (algum arquivo la' importa x_signals)",
             algum_arquivo_importa)


def test_8_status_credencial_sem_token_nunca_faz_rede():
    """Sem X_BEARER_TOKEN no ambiente de teste, status_credencial() deve
    reportar 'sem_credencial' SEM tentar nenhuma chamada HTTP - mockamos
    requests.get pra garantir isso (se chamar, o teste falha)."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("X_BEARER_TOKEN", None)
        with patch.object(x_signals_mod.requests, "get", side_effect=AssertionError("nao deveria chamar rede sem token")):
            status = x_signals_mod.status_credencial()
    _checar("8a estado sem_credencial quando token ausente", status["estado"] == "sem_credencial")
    _checar("8b token_presente False", status["token_presente"] is False)


def test_9_buscar_sinais_usa_estado_real_da_credencial_na_mensagem():
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("X_BEARER_TOKEN", None)
        try:
            x_signals_mod.buscar_sinais("PETR4")
            _checar("9 buscar_sinais propaga estado real no erro", False)
        except NotImplementedError as exc:
            _checar("9 buscar_sinais propaga estado real no erro", "sem_credencial" in str(exc))


class _RespostaFake:
    def __init__(self, status_code, corpo=None, headers=None, texto=""):
        self.status_code = status_code
        self._corpo = corpo or {}
        self.headers = headers or {}
        self.text = texto
        self.ok = status_code < 400

    def json(self):
        return self._corpo


def test_10_buscar_sinais_pagina_e_dedupla_entre_paginas():
    """2 paginas via meta.next_token, 1 post repetido na 2a pagina
    (mesmo id) - so' 1 Sinal pro post repetido (dedup real, nao so'
    teorico)."""
    from unittest.mock import patch
    pagina_1 = _RespostaFake(200, {
        "data": [{"id": "1", "text": "post 1", "author_id": "u1", "created_at": "2026-10-30T10:00:00Z"}],
        "includes": {"users": [{"id": "u1", "username": "autor1", "verified": False}]},
        "meta": {"next_token": "tok2"},
    }, headers={"x-rate-limit-remaining": "299"})
    pagina_2 = _RespostaFake(200, {
        "data": [
            {"id": "1", "text": "post 1 de novo", "author_id": "u1", "created_at": "2026-10-30T10:00:00Z"},  # duplicado
            {"id": "2", "text": "post 2", "author_id": "u2", "created_at": "2026-10-30T10:05:00Z"},
        ],
        "includes": {"users": [{"id": "u1", "username": "autor1"}, {"id": "u2", "username": "autor2", "verified": True}]},
        "meta": {},
    }, headers={"x-rate-limit-remaining": "298"})

    with patch.object(x_signals_mod, "status_credencial", return_value={"estado": "ok", "motivo": None, "token_presente": True}), \
         patch.object(x_signals_mod.config, "obter_credencial_x", return_value="fake-token"), \
         patch.object(x_signals_mod.requests, "get", side_effect=[pagina_1, pagina_2]):
        sinais, info_consumo = x_signals_mod.buscar_sinais("PETR4", max_resultados=10)

    _checar("10a so 2 sinais unicos (dedup por post_id entre paginas)", len(sinais) == 2)
    _checar("10b segundo sinal preserva conta_verificada=True", sinais[1].conta_verificada is True)
    _checar("10c info_consumo conta as 2 leituras (1 por pagina)", info_consumo["leituras"] == 2)
    _checar("10d limite_restante reflete a ULTIMA chamada (298)", info_consumo["limite_restante"] == 298)


def test_11_buscar_sinais_sem_estado_ok_lanca_antes_de_qualquer_requisicao():
    from unittest.mock import patch
    with patch.object(x_signals_mod, "status_credencial", return_value={"estado": "sem_permissao_busca", "motivo": "sem busca", "token_presente": True}), \
         patch.object(x_signals_mod.requests, "get", side_effect=AssertionError("nao deveria chamar rede")):
        try:
            x_signals_mod.buscar_sinais("PETR4")
            _checar("11 lanca antes de chamar rede quando credencial sem permissao de busca", False)
        except NotImplementedError as exc:
            _checar("11 lanca antes de chamar rede quando credencial sem permissao de busca", "sem_permissao_busca" in str(exc))


def test_12_buscar_sinais_respeita_max_resultados_entre_paginas():
    from unittest.mock import patch
    pagina_1 = _RespostaFake(200, {
        "data": [{"id": str(i), "text": f"post {i}", "author_id": "u1", "created_at": "2026-10-30T10:00:00Z"} for i in range(5)],
        "includes": {"users": [{"id": "u1", "username": "autor1"}]},
        "meta": {"next_token": "tok2"},
    })
    with patch.object(x_signals_mod, "status_credencial", return_value={"estado": "ok", "motivo": None, "token_presente": True}), \
         patch.object(x_signals_mod.config, "obter_credencial_x", return_value="fake-token"), \
         patch.object(x_signals_mod.requests, "get", return_value=pagina_1):
        sinais, _info = x_signals_mod.buscar_sinais("PETR4", max_resultados=3)
    _checar("12 para no max_resultados mesmo com mais paginas disponiveis", len(sinais) == 3)


def test_13_toda_chamada_requests_tem_timeout_explicito():
    """Regressao (revisao final PR RADAR X, 2026-10-30, ponto A -
    isolamento do coordenador): nenhuma chamada de rede deste modulo
    pode ficar pendurada indefinidamente - inspecao estatica do
    codigo-fonte, nao so' dos mocks (mock aceita qualquer kwarg, nao
    pegaria um timeout removido por acidente numa edicao futura)."""
    import inspect
    import re
    fonte = inspect.getsource(x_signals_mod)
    chamadas = re.findall(r"requests\.(?:get|post)\([^)]*\)", fonte, re.DOTALL)
    _checar("13a pelo menos 1 chamada de rede encontrada no modulo", len(chamadas) >= 2, f"(achadas={len(chamadas)})")
    sem_timeout = [c for c in chamadas if "timeout=" not in c]
    _checar("13b todas as chamadas requests.get/post tem timeout= explicito",
             sem_timeout == [], f"(sem timeout={sem_timeout})")


def test_14_buscar_sinais_paginas_sao_limitadas_mesmo_sem_next_token_parar():
    """max_paginas limita o numero de requisicoes mesmo se a API
    devolver next_token indefinidamente (nunca um loop sem fim)."""
    from unittest.mock import patch
    pagina_com_proximo_token_sempre = _RespostaFake(200, {
        "data": [{"id": "x", "text": "post", "author_id": "u1", "created_at": "2026-10-30T10:00:00Z"}],
        "includes": {"users": [{"id": "u1", "username": "autor1"}]},
        "meta": {"next_token": "sempre_tem_mais"},
    })
    chamadas = {"n": 0}

    def _contar(*_a, **_k):
        chamadas["n"] += 1
        return pagina_com_proximo_token_sempre

    with patch.object(x_signals_mod, "status_credencial", return_value={"estado": "ok", "motivo": None, "token_presente": True}), \
         patch.object(x_signals_mod.config, "obter_credencial_x", return_value="fake-token"), \
         patch.object(x_signals_mod.requests, "get", side_effect=_contar):
        x_signals_mod.buscar_sinais("PETR4", max_resultados=1000, max_paginas=4)
    _checar("14 numero de chamadas limitado por max_paginas mesmo com next_token infinito", chamadas["n"] == 4, f"(chamadas={chamadas['n']})")


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
