# -*- coding: utf-8 -*-
"""Worker independente: monitoramento de quedas e entrega resiliente de e-mails."""
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from data.coletores_status import diagnosticar_persistencia, registrar_tentativa
from data.macro import obter_cenario_global
from data.radar_quedas import processar_monitoramento
from data.supabase_client import obter_cliente
from data.user_prefs import listar_assinantes_radar_quedas
from jobs.email_utils import enviar_email

TZ_SP = ZoneInfo("America/Sao_Paulo")

# Nome no painel de SAUDE DOS DADOS por casa de carteira recomendada -
# NUNCA o mesmo nome da casa de RESEARCH (ex: "Genial Analisa" já é usado
# por data/research/genial.py via coletar_casa - mesmo motivo de "NEWS
# (watchlist)" vs "NEWS (ticker único)" em data/saude_dados.py: registrar_
# tentativa faz upsert por `nome`, nome igual faria uma fonte sobrescrever
# o status da outra, mesmo sendo coletores DIFERENTES (endpoint, formato,
# disponibilidade diferentes - ver data/research/genial_carteiras.py x
# data/research/genial.py).
_NOME_PAINEL_POR_CASA = {
    "Genial Analisa": "Genial Analisa (carteiras)",
    "Safra Corretora": "Safra Corretora (carteiras)",
}
_FONTE_POR_CASA = {
    "Genial Analisa (carteiras)": "analisa.genialinvestimentos.com.br (carteiras recomendadas)",
    "Safra Corretora (carteiras)": "safra.com.br (carteiras recomendadas, HTML + PDF mensal)",
}


def _registrar_tentativas_por_casa(status_fontes: dict) -> None:
    """Granularidade por casa (achado real, auditoria 2026-10-22):
    `resultado["fontes"]` de processar_monitoramento() já tem o status
    de CADA casa separado, mas só o AGREGADO "RADAR DE QUEDAS" chegava
    ao painel - uma falha isolada de 1 casa (ex: Genial carteiras fora
    do ar, Safra OK) ficava indistinguível de "tudo OK" ou "tudo falhou"
    pra quem olha o painel, mesmo com a avaliação de recomendações já
    sendo resiliente por casa (ver processar_monitoramento). Nunca
    lança excecao - status desconhecido (string nova/inesperada) vira
    FALHA_EXECUCAO com o texto bruto, nunca falso sucesso."""
    for casa, status in (status_fontes or {}).items():
        nome_painel = _NOME_PAINEL_POR_CASA.get(casa)
        if nome_painel is None:
            continue
        fonte = _FONTE_POR_CASA.get(nome_painel, nome_painel)
        if status.startswith("ok ("):
            try:
                n = int(status.split("(")[1].split(" ")[0])
            except (IndexError, ValueError):
                n = None
            # Achado real (revisão independente 2026-10-27): salvar_carteiras
            # pode persistir os itens novos com sucesso e, ainda assim, falhar
            # SÓ ao desativar recomendações que saíram da carteira deste mês
            # (ver data/radar_quedas.py:salvar_carteiras, aviso_desativacao) -
            # "; aviso: ..." no status marca esse caso. Nunca sucesso pleno
            # silencioso nem falha de persistência (os dados novos estão
            # corretos) - PARCIAL, com o texto real do aviso.
            aviso = status.split("; aviso: ", 1)[1] if "; aviso: " in status else None
            registrar_tentativa(nome_painel, fonte, execucao_ok=True, persistencia_ok=True,
                                 registros_novos=n, categoria="Radar",
                                 parcial=bool(aviso), erro=aviso)
        elif status == "fonte indisponível":
            registrar_tentativa(nome_painel, fonte, execucao_ok=False, erro=status, categoria="Radar")
        elif status.startswith("snapshot vazio"):
            registrar_tentativa(nome_painel, fonte, execucao_ok=True, persistencia_ok=True,
                                 registros_novos=0, parcial=True, erro=status, categoria="Radar")
        elif status.startswith("falha ao persistir"):
            registrar_tentativa(nome_painel, fonte, execucao_ok=True, persistencia_ok=False,
                                 erro=status, categoria="Radar")
        else:
            registrar_tentativa(nome_painel, fonte, execucao_ok=False,
                                 erro=f"status inesperado: {status}", categoria="Radar")
STATUS_REPROCESSAVEIS = ("PENDENTE_ENVIO", "FALHA_ENVIO")
# Só reenvia alerta de pregão recente: 3 dias corridos cobrem fim de semana
# e feriado. Sem esse limite, um alerta que nunca saiu (ex.: EMAIL_TO vazio,
# visto nos logs de 21/10/2026 - hoje substituído pelo opt-in de
# data/user_prefs.py:listar_assinantes_radar_quedas, mas o mesmo risco
# existe se ninguém tiver autorizado ainda) ficava pendente pra sempre e,
# quando o envio voltasse, chegaria dias depois como se a queda fosse de
# hoje; e, com mais de 200 pendentes antigos (ordem do mais velho +
# limit), os NOVOS nunca entravam no lote. Alerta mais velho continua no
# banco e na tela (RADAR > Alertas, coluna E-MAIL), só não é mais
# reenviado.
JANELA_REENVIO_DIAS = 3


def _alertas_pendentes(cliente, hoje=None):
    """Busca alertas persistidos ainda não entregues, inclusive de execuções
    anteriores, de pregões dentro de JANELA_REENVIO_DIAS."""
    hoje = hoje or datetime.now(TZ_SP).date()
    desde = (hoje - timedelta(days=JANELA_REENVIO_DIAS)).isoformat()
    try:
        resposta = (
            cliente.table("radar_alertas_queda")
            .select("*")
            .in_("status", list(STATUS_REPROCESSAVEIS))
            .gte("pregao", desde)
            .order("alertado_em")
            .limit(200)
            .execute()
        )
        return resposta.data or []
    except Exception as exc:
        print(f"[radar_quedas] falha ao recuperar alertas pendentes: {exc!r}")
        return None


def _data_pregao(alerta):
    """'dd/mm/aaaa' do pregão do alerta, ou None se ausente/inválida."""
    pregao = alerta.get("pregao")
    try:
        return datetime.fromisoformat(str(pregao)).strftime("%d/%m/%Y") if pregao else None
    except ValueError:
        return None


def _texto_alerta(alerta):
    return (
        f"RADAR DE QUEDAS — {alerta['ticker']}\n\n"
        f"Pregão: {_data_pregao(alerta) or 'não informado'}\n"
        f"Variação diária: {float(alerta['variacao_pct']):.2f}%\n"
        f"Preço: {float(alerta['preco_atual']):.2f}\n"
        f"Fechamento anterior: {float(alerta['fechamento_anterior']):.2f}\n"
        f"Cotação: {alerta.get('cotacao_em', 'indisponível')} "
        f"({alerta.get('tipo_cotacao', 'provedor não informado')})\n"
        f"Casas: {', '.join(alerta.get('casas') or [])}\n"
        f"Carteiras: {', '.join(alerta.get('carteiras') or [])}\n"
        f"Fontes: {' | '.join(alerta.get('fontes') or [])}\n\n"
        "Alerta informativo, não constitui recomendação de investimento."
    )


def _hash_destinatario(email: str) -> str:
    """Identificador curto e irreversível (sha256[:10]) de um e-mail, só
    pra correlacionar linhas de log da MESMA execução sem nunca expor o
    e-mail completo em stdout/log do GitHub Actions - mesmo padrão de
    jobs/morning_call.py:_hash_destinatario."""
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()[:10]


def _enviar_alerta(cliente, alerta, destinatarios):
    """Envia (1 e-mail por destinatário autorizado) e persiste o
    resultado agregado do alerta. `destinatarios` vem de
    data/user_prefs.py:listar_assinantes_radar_quedas, resolvido 1x por
    execução em executar() - enviar_email nunca recebe um destinatario
    implícito (sem fallback de EMAIL_TO, ver jobs/email_utils.py).

    Sem NENHUM destinatário autorizado, o alerta não é enviado e seu
    status não é alterado (continua PENDENTE_ENVIO/FALHA_ENVIO, elegível
    pra reenvio se alguém autorizar dentro de JANELA_REENVIO_DIAS) -
    isso é o caso normal "ninguém quer receber ainda", nunca uma falha
    (ver missão "Radar/Morning Call: consentimento").

    Retorna "ENVIADO"/"FALHA_ENVIO"/"SEM_DESTINATARIO"/"IGNORADO" (em
    vez de bool) pra executar() poder contar os 4 desfechos
    separadamente - "SEM_DESTINATARIO" nunca deve contar como falha."""
    alerta_id = alerta.get("id")
    if alerta_id is None:
        print(f"[radar_quedas] alerta sem id persistido; envio ignorado: {alerta.get('ticker')}")
        return "IGNORADO"

    if not destinatarios:
        print(
            f"[radar_quedas] ticker={alerta['ticker']} sem destinatário autorizado - alerta não "
            "enviado (nenhum usuário optou por receber alertas do Radar de Quedas)."
        )
        return "SEM_DESTINATARIO"

    # data do pregão no assunto: um alerta reenviado depois (retry) nunca
    # parece ser uma queda de hoje
    data_pregao = _data_pregao(alerta)
    sufixo = f" (pregão {data_pregao[:5]})" if data_pregao else ""
    assunto = f"[PREGÃO] Queda >4% — {alerta['ticker']}{sufixo}"
    texto = _texto_alerta(alerta)

    # "ENVIADO" se ao menos 1 destinatário recebeu - uma falha parcial
    # nunca reenvia pra quem já recebeu com sucesso (o retry do alerta
    # inteiro, via STATUS_REPROCESSAVEIS, dispararia um e-mail
    # DUPLICADO pro destinatário que já tinha sido entregue). O
    # trade-off é quem falhou num envio parcial não ganha retry
    # automático nesse alerta específico - aceitável dado que, na
    # prática, o Radar tem poucos assinantes (ver PR).
    algum_sucesso = False
    erros = []
    for email in destinatarios:
        envio = enviar_email(assunto, texto, destinatario=email)
        print(
            f"[radar_quedas] ticker={alerta['ticker']} destinatario={_hash_destinatario(email)} "
            f"envio_ok={envio['ok']} erro={envio['erro']}"
        )
        if envio["ok"]:
            algum_sucesso = True
        else:
            erros.append(envio["erro"])

    status = "ENVIADO" if algum_sucesso else "FALHA_ENVIO"
    erro_envio = None
    if erros:
        erro_envio = (
            f"falha para {len(erros)}/{len(destinatarios)} destinatário(s) - ex: {erros[0]}"
            if algum_sucesso else erros[0]
        )
    atualizacao = {
        "status": status,
        "email_enviado_em": datetime.now(TZ_SP).isoformat() if algum_sucesso else None,
        "erro_envio": erro_envio,
    }
    try:
        cliente.table("radar_alertas_queda").update(atualizacao).eq("id", alerta_id).execute()
    except Exception as exc:
        # O email pode já ter saído. Log explícito porque um retry posterior
        # pode duplicá-lo se a gravação do status falhar após a entrega.
        print(
            f"[radar_quedas] envio_ok={algum_sucesso} mas falhou ao salvar "
            f"status do alerta id={alerta_id}: {exc!r}"
        )
        return "FALHA_ENVIO"

    return status


def executar():
    # Self-test de escrita+leitura ANTES de tentar persistir qualquer
    # coisa (mesmo motivo de coletor_local.py: 1 diagnostico claro na
    # raiz em vez de N excecoes "42501" repetidas, uma por tabela).
    diagnostico = diagnosticar_persistencia()
    if diagnostico["ok"]:
        print("[radar_quedas] persistencia (self-test escrita+leitura): OK")
    else:
        print(
            f"[radar_quedas] persistencia (self-test escrita+leitura): FALHOU "
            f"na etapa {diagnostico['etapa']} - {diagnostico['detalhe']}"
        )

    # Mantém "MACRO (Cenário Global)" fiel ao comportamento real (auditoria
    # SAÚDE DOS DADOS 2026-10-26): esse coletor só era chamado a partir de
    # ui/macro_tab.py e data/sintese_mercado.py (sob demanda) -
    # idade_maxima_horas=2 (mesmo TTL curto do resto de cotações globais,
    # ver data/saude_dados.py) nunca fica coberta só por visita na UI. Este
    # job já roda a cada 15min em dia de pregão (.github/workflows/radar-
    # morning-call.yml) - reaproveita essa cadência pra manter a fonte
    # dentro da janela esperada, sem cron novo nem chamada fora do horário
    # de pregão. obter_cenario_global() já trata a própria falha e registra
    # a tentativa internamente; nunca lança excecao pra aqui.
    obter_cenario_global()

    resultado = processar_monitoramento()
    cliente = obter_cliente()
    if cliente is None:
        print("[radar_quedas] Supabase indisponível; não é possível recuperar alertas pendentes.")
        return 1

    # Destinatarios dinamicos: todo usuario com a preferencia
    # 'radar_quedas_email_ativo'=True em user_prefs E e-mail valido (ver
    # data/user_prefs.py:listar_assinantes_radar_quedas) - resolvido 1x
    # por execucao (nao por alerta), mesmo padrao de
    # jobs/morning_call.py:executar. NUNCA usa EMAIL_TO como destinatario
    # fixo (ver jobs/email_utils.py - o fallback foi removido).
    #
    # None (nao []) diferencia "Supabase indisponivel pra ESSA consulta"
    # (falha real de infra - nunca reportar como sucesso silencioso) de
    # "ninguem autorizou ainda" (estado normal, ver _enviar_alerta) -
    # mesma distincao de listar_assinantes_morning_call.
    destinatarios = listar_assinantes_radar_quedas(cliente)
    if destinatarios is None:
        print(
            "[radar_quedas] não foi possível consultar os destinatários opt-in do Radar "
            "(Supabase indisponível) - nenhum e-mail de alerta enviado nesta execução."
        )
    elif not destinatarios:
        print(
            "[radar_quedas] nenhum usuário autorizou receber alertas do Radar de Quedas "
            "ainda - nenhum e-mail enviado nesta execução (não é uma falha)."
        )

    # Não depender apenas de alertas_novos: eles deixam de aparecer nessa lista
    # após a primeira inserção, mesmo se o envio falhar. Reconsultar o banco
    # recupera pendências após timeout, falha SMTP ou interrupção do runner.
    pendentes = _alertas_pendentes(cliente)
    if pendentes is None:
        # Ainda tenta os alertas recém-criados, caso a consulta de recuperação falhe.
        pendentes = resultado.get("alertas_novos", [])

    ids_vistos = set()
    entregues = 0
    falhas = 0
    sem_destinatario = 0
    for alerta in pendentes:
        alerta_id = alerta.get("id")
        if alerta_id is None or alerta_id in ids_vistos:
            continue
        ids_vistos.add(alerta_id)
        desfecho = _enviar_alerta(cliente, alerta, destinatarios)
        if desfecho == "ENVIADO":
            entregues += 1
        elif desfecho == "SEM_DESTINATARIO":
            sem_destinatario += 1
        elif desfecho == "FALHA_ENVIO":
            falhas += 1
        # "IGNORADO" (alerta sem id) não entra em nenhum contador - nunca
        # existiu uma tentativa de envio de verdade.

    print(
        f"[radar_quedas] coleta_ok={resultado.get('coleta_ok')} "
        f"novos={len(resultado.get('alertas_novos', []))} "
        f"pendentes_processados={len(ids_vistos)} entregues={entregues} "
        f"sem_destinatario={sem_destinatario} falhas={falhas} "
        f"erro_coleta={resultado.get('erro', '')}"
    )
    # "não deu pra saber quem pode receber" é uma falha de execução
    # visível no painel (mesmo espírito do Morning Call) - diferente de
    # "sem_destinatario" (confirmado que ninguém autorizou), que nunca é.
    erro_destinatarios = (
        "não foi possível consultar destinatários opt-in do Radar (Supabase indisponível)"
        if destinatarios is None else None
    )
    execucao_ok = bool(resultado.get("coleta_ok")) and destinatarios is not None
    # Visibilidade no painel SAÚDE DOS DADOS: sem isto, o Radar podia parar
    # de rodar (ou falhar silenciosamente) sem nenhuma linha refletindo
    # isso - a tabela radar_alertas_queda só registra ALERTAS, não a
    # tentativa de execução em si (uma rodada sem nenhuma queda >4% é
    # sucesso legítimo e não deixaria rastro nenhum sem isto).
    registrar_tentativa(
        "RADAR DE QUEDAS",
        "Carteiras recomendadas (Genial + Safra) + cotações (variação diária)",
        execucao_ok=execucao_ok,
        persistencia_ok=(falhas == 0),
        registros_novos=len(resultado.get("alertas_novos", [])),
        erro=(
            resultado.get("erro") or erro_destinatarios
            or (f"{falhas} alerta(s) sem envio confirmado" if falhas else None)
        ),
        categoria="Radar",
        # Parcial tanto por falha de ENVIO (falhas>0) quanto por falha de
        # COLETA numa fonte só (resultado["erro"] setado mesmo com
        # coleta_ok=True - ver processar_monitoramento: "Execução parcial: ...").
        parcial=bool(resultado.get("coleta_ok")) and bool(falhas or resultado.get("erro")),
    )
    _registrar_tentativas_por_casa(resultado.get("fontes"))
    # Falha de fonte (ou não conseguir saber quem pode receber) também
    # deve ser visível como execução falha, mesmo que uma pendência
    # antiga tenha sido entregue nesta rodada. "sem_destinatario" nunca
    # entra nessa conta - ver docstring de _enviar_alerta.
    return 0 if execucao_ok and falhas == 0 else 1


if __name__ == "__main__":
    raise SystemExit(executar())
