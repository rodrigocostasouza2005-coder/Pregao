# -*- coding: utf-8 -*-
"""Testes de .github/workflows/radar-morning-call.yml - texto puro (sem
PyYAML, não é dependência do projeto), pra pegar justamente a classe de
bug que já aconteceu aqui: o cron em `on.schedule` e a string comparada
no `if:` do job precisam ser IDÊNTICAS (o GitHub Actions compara
`github.event.schedule` por igualdade de string literal - um cron
"corrigido" só no `schedule` e esquecido no `if:` deixa o job silenciosamente
sem rodar nunca, sem erro nenhum)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_CAMINHO = Path(__file__).parent.parent / ".github" / "workflows" / "radar-morning-call.yml"


def _conteudo():
    return _CAMINHO.read_text(encoding="utf-8")


def test_cron_do_morning_call_e_08h_brasilia():
    """Missão explícita: envio às 08h00 de Brasília (America/Sao_Paulo,
    UTC-3, sem horário de verão desde 2019) = 11:00 UTC."""
    texto = _conteudo()
    assert '- cron: "0 11 * * 1-5"' in texto, (
        "cron do Morning Call não está em '0 11 * * 1-5' (08h BRT) - "
        "conferir .github/workflows/radar-morning-call.yml"
    )
    # Regressão de documentação: não pode sobrar um comentário/cron
    # antigo dizendo 07:00 (bug real encontrado e corrigido nesta sessão).
    assert "07:00 BRT" not in texto


def test_cron_do_schedule_bate_com_a_condicao_if_do_job_morning_call():
    """O `if:` do job morning-call compara github.event.schedule por
    string literal - precisa citar EXATAMENTE o mesmo cron declarado em
    `on.schedule`, senão o job nunca dispara via schedule (só via
    workflow_dispatch manual), sem nenhum erro visível."""
    texto = _conteudo()
    crons_declarados = re.findall(r'- cron:\s*"([^"]+)"', texto)
    assert "0 11 * * 1-5" in crons_declarados

    bloco_job = texto.split("morning-call:", 1)[1]
    condicao_if = bloco_job.split("steps:", 1)[0]
    m = re.search(r"github\.event\.schedule == '([^']+)'", condicao_if)
    assert m is not None, "job morning-call não tem comparação de github.event.schedule no if:"
    assert m.group(1) in crons_declarados, (
        f"o if: do job morning-call compara contra {m.group(1)!r}, que não está "
        f"em on.schedule ({crons_declarados!r}) - job nunca dispara sozinho"
    )


def test_input_teste_destinatario_declarado_e_fiado_na_env_do_job():
    """O modo de teste remoto (jobs.morning_call.enviar_teste) só é
    alcançável via GitHub Actions se o input existir em
    workflow_dispatch.inputs E o job morning-call passar ele adiante
    pro processo Python via env - um dos dois faltando deixa o recurso
    "existir" só no código, inacessível de fora sem rodar localmente."""
    texto = _conteudo()
    assert "teste_destinatario:" in texto.split("workflow_dispatch:", 1)[1].split("permissions:", 1)[0]
    bloco_job = texto.split("morning-call:", 1)[1]
    assert "MORNING_CALL_TESTE_PARA: ${{ inputs.teste_destinatario }}" in bloco_job
