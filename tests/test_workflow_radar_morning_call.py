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
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

_CAMINHO = Path(__file__).parent.parent / ".github" / "workflows" / "radar-morning-call.yml"
_TZ_SP = ZoneInfo("America/Sao_Paulo")


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


def test_morning_call_dispara_as_06h30_brasilia_com_reservas():
    """Missão explícita "Frente 1" (2026-11-12): envio às 06h30 de
    Brasília (UTC-3, sem horário de verão desde 2019) - primeiro disparo
    06:03 (= 09:03 UTC) e reservas até 07:47, pra chegar ANTES da
    abertura da B3 (antes vinha chegando à tarde por atraso do agendador
    do GitHub sob carga - ver MANUAL.md, "Disparo externo dos
    agendamentos"). Idempotência diária evita envio duplo."""
    texto = _conteudo()
    crons_mc = _crons_do_if(texto, "morning-call")
    assert crons_mc[0] == "3 9 * * 1-5"
    assert len(crons_mc) >= 2
    for cron in crons_mc:
        minuto, hora = cron.split()[:2]
        assert hora in ("9", "10"), f"{cron!r} fora da janela 06h-07h BRT"
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


def test_email_provider_fallback_bate_com_os_secrets_ja_configurados():
    """Bug real (achado 22-23/10/2026): com o secret EMAIL_PROVIDER nunca
    configurado, `${{ secrets.EMAIL_PROVIDER || 'resend' }}` sempre
    resolvia pra 'resend' - mesmo com SMTP_HOST/SMTP_USER/SMTP_PASSWORD já
    configurados e EMAIL_FROM apontando pra um domínio @gmail.com que o
    Resend nunca verifica (não é domínio do Pregão). Resultado: todo envio
    (Radar E Morning Call, mesmo jobs/email_utils.py) falhava com HTTP 403
    'domain not verified'. O fallback do workflow precisa bater com o
    default do próprio código (jobs/email_utils.py:enviar_email, 'smtp')."""
    texto = _conteudo()
    from jobs.email_utils import enviar_email  # noqa: F401 - default real do código
    import inspect
    fonte = inspect.getsource(enviar_email)
    assert 'os.getenv("EMAIL_PROVIDER") or "smtp"' in fonte, (
        "default do código mudou - revise o fallback do workflow junto"
    )
    ocorrencias = re.findall(r"EMAIL_PROVIDER: \$\{\{ secrets\.EMAIL_PROVIDER \|\| '([^']+)' \}\}", texto)
    assert len(ocorrencias) == 3, "esperado 1 fallback por step que envia e-mail (radar + validação + envio MC)"
    assert set(ocorrencias) == {"smtp"}, (
        f"fallback do workflow é {ocorrencias!r}, deveria ser 'smtp' (bate com SMTP_* já configurados nos secrets)"
    )


def test_cron_utc_converte_para_06h30_brasilia_o_ano_todo():
    """Teste REAL de conversão (não aritmética manual): cada cron
    `minuto hora * * 1-5` do job morning-call é interpretado como um
    horário UTC de um disparo do GitHub Actions e convertido com
    zoneinfo (America/Sao_Paulo, fonte oficial de regras de fuso - a
    mesma lib usada em produção por jobs/morning_call.py e
    data/morning_call_editorial.py) para horário de Brasília. Roda em 4
    datas do ano (incluindo janeiro e julho, verão/inverno no
    hemisfério sul) pra confirmar que o Brasil não tem horário de verão
    desde 2019 - BRT é UTC-3 fixo o ano todo, a conversão não pode
    variar por data."""
    texto = _conteudo()
    crons_mc = _crons_do_if(texto, "morning-call")
    datas_do_ano = [
        datetime(2026, 1, 14, tzinfo=timezone.utc),   # verão no Brasil
        datetime(2026, 7, 15, tzinfo=timezone.utc),   # inverno no Brasil
        datetime(2026, 11, 12, tzinfo=timezone.utc),  # data da missão
        datetime(2027, 3, 3, tzinfo=timezone.utc),    # outro ano, pra não depender de 2026
    ]
    esperado_brt = ["06:03", "06:17", "06:27", "06:38", "06:52", "07:07", "07:27", "07:47"]
    for base in datas_do_ano:
        obtido_brt = []
        for cron in crons_mc:
            minuto, hora = (int(x) for x in cron.split()[:2])
            momento_utc = base.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            momento_brt = momento_utc.astimezone(_TZ_SP)
            assert momento_brt.utcoffset().total_seconds() == -3 * 3600, (
                f"{base.date()}: offset BRT != UTC-3 (horário de verão inesperado)"
            )
            obtido_brt.append(momento_brt.strftime("%H:%M"))
        assert obtido_brt == esperado_brt, f"{base.date()}: {obtido_brt!r} != {esperado_brt!r}"


def test_primeiro_disparo_chega_antes_da_abertura_da_b3():
    """O propósito da Frente 1: o Morning Call pronto ANTES do pregão
    abrir (B3 abre 10h BRT). Confirma com conversão real (zoneinfo) que
    mesmo a ÚLTIMA reserva (07:47 BRT) ainda deixa margem robusta antes
    da abertura, e que o primeiro disparo (06:03 BRT) cumpre a meta
    explícita de 06:30 da missão."""
    texto = _conteudo()
    crons_mc = _crons_do_if(texto, "morning-call")
    base = datetime(2026, 11, 12, tzinfo=timezone.utc)
    minuto, hora = (int(x) for x in crons_mc[0].split()[:2])
    primeiro_brt = base.replace(hour=hora, minute=minuto).astimezone(_TZ_SP)
    assert primeiro_brt.strftime("%H:%M") <= "06:30", (
        f"primeiro disparo às {primeiro_brt:%H:%M} BRT, depois da meta de 06:30"
    )
    minuto, hora = (int(x) for x in crons_mc[-1].split()[:2])
    ultima_reserva_brt = base.replace(hour=hora, minute=minuto).astimezone(_TZ_SP)
    abertura_b3 = base.replace(hour=13, minute=0).astimezone(_TZ_SP)  # 10h BRT = 13h UTC
    assert ultima_reserva_brt < abertura_b3, (
        f"última reserva ({ultima_reserva_brt:%H:%M} BRT) não deixa margem antes da abertura da B3 (10h BRT)"
    )


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
