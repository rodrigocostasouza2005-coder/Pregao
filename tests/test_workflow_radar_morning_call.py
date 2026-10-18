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


def _crons_declarados(texto):
    return re.findall(r'- cron:\s*"([^"]+)"', texto)


def _crons_do_if(texto, job):
    """Lista de crons que o `if:` do job aceita (contains(fromJSON([...]),
    github.event.schedule))."""
    bloco_job = texto.split(f"\n  {job}:", 1)[1]
    condicao_if = bloco_job.split("runs-on:", 1)[0]
    m = re.search(r"contains\(fromJSON\('(\[[^']+\])'\), github\.event\.schedule\)", condicao_if)
    assert m is not None, f"job {job} sem contains(fromJSON([...]), github.event.schedule) no if:"
    return re.findall(r'"([^"]+)"', m.group(1))


def test_morning_call_dispara_as_08h_brasilia_com_reservas():
    """Missão explícita: envio às 08h de Brasília (UTC-3, sem horário de
    verão desde 2019) - primeiro disparo 08:03 (= 11:03 UTC) e reservas
    até 09:07, porque o GitHub descarta schedule sob carga (medido:
    nenhum disparo em 17/10). Idempotência diária evita envio duplo."""
    texto = _conteudo()
    crons_mc = _crons_do_if(texto, "morning-call")
    assert crons_mc[0] == "3 11 * * 1-5"
    assert len(crons_mc) >= 2
    for cron in crons_mc:
        minuto, hora = cron.split()[:2]
        assert hora in ("11", "12"), f"{cron!r} fora da janela 08h-09h BRT"
    assert "07:00 BRT" not in texto


def test_cron_do_schedule_bate_com_a_condicao_if_dos_jobs():
    """O `if:` de cada job compara github.event.schedule por string
    literal - todo cron que o job aceita precisa existir em on.schedule
    (senão nunca dispara), e todo cron declarado precisa pertencer a
    exatamente UM job (senão dispara um run vazio, ou os dois)."""
    texto = _conteudo()
    declarados = _crons_declarados(texto)
    crons_radar = _crons_do_if(texto, "radar")
    crons_mc = _crons_do_if(texto, "morning-call")
    for cron in crons_radar + crons_mc:
        assert cron in declarados, f"{cron!r} está no if: mas não em on.schedule - job nunca dispara"
    assert not set(crons_radar) & set(crons_mc), "cron compartilhado entre radar e morning-call"
    assert set(declarados) == set(crons_radar) | set(crons_mc), "cron declarado sem job correspondente"


def test_agendamentos_evitam_minutos_redondos():
    """O GitHub descarta disparos de schedule sob carga e :00/:15/:30/:45
    são os mais congestionados - nenhum cron dos workflows agendados pode
    cair nesses minutos."""
    for nome in ("radar-morning-call.yml", "coletores-nuvem.yml"):
        texto = (_CAMINHO.parent / nome).read_text(encoding="utf-8")
        for cron in _crons_declarados(texto):
            minutos = cron.split()[0]
            for minuto in minutos.replace("*/", "").split(","):
                assert minuto.isdigit() and int(minuto) % 15 != 0, f"{nome}: cron {cron!r} usa minuto redondo"


def test_concurrency_por_job_nao_por_workflow():
    """Com um grupo único no workflow, o GitHub mantém só 1 pendente e
    cancela o anterior - um Radar enfileirado podia derrubar o Morning
    Call pendente."""
    texto = _conteudo()
    topo = texto.split("\njobs:", 1)[0]
    assert "concurrency:" not in topo
    for job in ("radar", "morning-call"):
        bloco = texto.split(f"\n  {job}:", 1)[1].split("steps:", 1)[0]
        assert "concurrency:" in bloco, f"job {job} sem concurrency própria"
