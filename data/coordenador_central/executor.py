# -*- coding: utf-8 -*-
"""Executor do Coordenador Central - roda especialistas (ver registro.py)
de forma ISOLADA (erro de qualquer um nunca propaga pro chamador) e com
TIMEOUT REAL (concurrent.futures, biblioteca padrão, sem dependência
nova) - um especialista que nunca retorna nunca trava quem chamou.

executar_especialista: 1 especialista, isolado.
executar_varios: N especialistas EM PARALELO (ThreadPoolExecutor com N
workers + as_completed) - uma falha/timeout de um nunca impede os
demais de terminar.

Importante sobre o timeout: o worker interno que roda a função real é
um thread "solto" (nunca aguardamos seu término via shutdown(wait=True))
- se a função nunca retornar, o thread fica rodando em segundo plano
indefinidamente (vaza 1 thread), mas a CHAMADA a executar_especialista
sempre retorna no máximo ~timeout_seg depois. É a troca deliberada:
nunca travar o chamador é mais importante do que nunca vazar uma thread
de uma função mal-comportada (que não deveria existir de qualquer forma -
todos os especialistas reais aqui são rápidos e já têm seus próprios
timeouts de rede)."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FuturesTimeoutError, as_completed

from data.coordenador_central.registro import obter_especialista

_TIMEOUT_PADRAO_SEG = 30


def _resultado_base(especialista_id: str, execucao_id: str) -> dict:
    return {
        "id": especialista_id, "execucao_id": execucao_id,
        "disponivel": False, "resumo": None, "evidencias": [],
        "motivo_indisponivel": None, "duracao_ms": 0, "erro_tecnico": None, "dados": None,
    }


def executar_especialista(especialista_id: str, timeout_seg: int = _TIMEOUT_PADRAO_SEG, **kwargs) -> dict:
    """Chama o especialista `especialista_id` com `kwargs`, isolado (try/
    except amplo) e com timeout real. Retorno SEMPRE no mesmo formato
    (id, execucao_id, disponivel, resumo, evidencias, motivo_indisponivel,
    duracao_ms, erro_tecnico, dados) - erro_tecnico nunca é exposto na UI
    (ui/coordenador_tab.py), só logado/persistido pra diagnóstico."""
    execucao_id = uuid.uuid4().hex
    inicio = time.monotonic()
    resultado = _resultado_base(especialista_id, execucao_id)

    especialista = obter_especialista(especialista_id)
    if especialista is None:
        resultado["motivo_indisponivel"] = f"especialista '{especialista_id}' não está registrado"
        resultado["duracao_ms"] = int((time.monotonic() - inicio) * 1000)
        return resultado

    def _rodar():
        bruto = especialista.funcao(**kwargs)
        return especialista.extrator_saida(bruto)

    # Sem "with": __exit__ de ThreadPoolExecutor chama shutdown(wait=True),
    # que bloquearia até a thread interna terminar mesmo em caso de
    # timeout - exatamente o travamento que este módulo existe pra evitar.
    pool = ThreadPoolExecutor(max_workers=1)
    futuro = pool.submit(_rodar)
    try:
        padronizado = futuro.result(timeout=timeout_seg)
        resultado.update({
            "disponivel": bool(padronizado.get("disponivel")),
            "resumo": padronizado.get("resumo"),
            "evidencias": padronizado.get("evidencias") or [],
            "motivo_indisponivel": padronizado.get("motivo_indisponivel"),
            "dados": padronizado.get("dados"),
        })
    except _FuturesTimeoutError:
        resultado["motivo_indisponivel"] = "timeout"
        resultado["erro_tecnico"] = f"TimeoutError: especialista não respondeu em {timeout_seg}s"
    except Exception as exc:
        resultado["motivo_indisponivel"] = "falha técnica ao executar especialista"
        resultado["erro_tecnico"] = repr(exc)
    finally:
        pool.shutdown(wait=False)
        resultado["duracao_ms"] = int((time.monotonic() - inicio) * 1000)
    return resultado


def executar_varios(ids: list, timeout_seg: int = _TIMEOUT_PADRAO_SEG, **kwargs_comuns) -> dict:
    """Roda todos os `ids` EM PARALELO - cada um com seu próprio
    execucao_id/isolamento/timeout (ver executar_especialista). Uma
    falha/timeout de um nunca impede os demais de terminar."""
    if not ids:
        return {}
    resultados = {}
    with ThreadPoolExecutor(max_workers=len(ids)) as pool:
        futuros = {
            pool.submit(executar_especialista, especialista_id, timeout_seg, **kwargs_comuns): especialista_id
            for especialista_id in ids
        }
        for futuro in as_completed(futuros):
            especialista_id = futuros[futuro]
            try:
                resultados[especialista_id] = futuro.result()
            except Exception as exc:
                resultado = _resultado_base(especialista_id, uuid.uuid4().hex)
                resultado["motivo_indisponivel"] = "falha técnica inesperada no executor paralelo"
                resultado["erro_tecnico"] = repr(exc)
                resultados[especialista_id] = resultado
    return resultados
