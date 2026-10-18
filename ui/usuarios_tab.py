# -*- coding: utf-8 -*-
"""Interface da aba USUÁRIOS (só admin, ver config.obter_emails_admin):
métricas de cadastro/atividade/inscrição no Morning Call e tabela de
usuários, a partir de data/admin_usuarios.py.

Autorização em 3 camadas (nenhuma delas é "esconder o link na sidebar"):
1. app.py só adiciona "USUÁRIOS" na navegação pra quem é admin.
2. app.py reconfirma `_eh_admin` antes de chamar render_usuarios.
3. data/admin_usuarios.py reconfirma de novo, e é quem de fato bloqueia
   a CONSULTA (não só a renderização) - um e-mail não-admin chegando
   aqui por qualquer bug nas camadas 1/2 ainda recebe None, nunca dado
   real."""

import csv
import html
import io
from datetime import datetime, timedelta, timezone

import streamlit as st

import config
from data.admin_usuarios import obter_usuarios_admin

_ROTULO_STATUS = {
    "inscrito": "Inscrito",
    "recusou": "Recusou",
    "nao_respondeu": "Não respondeu",
}


def _parse_dt(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except Exception:
        return None


def calcular_metricas(usuarios: list[dict], dias_novos: int = 30, agora=None) -> dict:
    """Função pura (sem Streamlit/Supabase) - métricas honestas a partir
    da lista já carregada: nunca inventa linha nem data, só conta o que
    está presente (created_at/last_seen_at ausentes não entram em
    "novos"/"ativos", mas também não entram em nenhuma contagem negativa
    fabricada)."""
    agora = agora or datetime.now(timezone.utc)
    limite_novos = agora - timedelta(days=dias_novos)
    limite_7d = agora - timedelta(days=7)
    limite_30d = agora - timedelta(days=30)

    metricas = {
        "total": len(usuarios),
        "novos": 0,
        "ativos_7d": 0,
        "ativos_30d": 0,
        "inscritos": 0,
        "nao_responderam": 0,
    }
    for usuario in usuarios:
        criado_em = _parse_dt(usuario.get("created_at"))
        if criado_em and criado_em >= limite_novos:
            metricas["novos"] += 1
        ultimo_acesso = _parse_dt(usuario.get("last_seen_at"))
        if ultimo_acesso and ultimo_acesso >= limite_7d:
            metricas["ativos_7d"] += 1
        if ultimo_acesso and ultimo_acesso >= limite_30d:
            metricas["ativos_30d"] += 1
        if usuario.get("status_inscricao") == "inscrito":
            metricas["inscritos"] += 1
        elif usuario.get("status_inscricao") == "nao_respondeu":
            metricas["nao_responderam"] += 1
    return metricas


def _filtrar(usuarios: list[dict], busca: str, filtro_inscricao: str, filtro_atividade: str, agora) -> list[dict]:
    busca_norm = (busca or "").strip().lower()
    linhas = []
    for usuario in usuarios:
        if busca_norm and busca_norm not in (usuario.get("email") or ""):
            continue

        status = usuario.get("status_inscricao")
        if filtro_inscricao == "Inscrito" and status != "inscrito":
            continue
        if filtro_inscricao == "Recusou" and status != "recusou":
            continue
        if filtro_inscricao == "Não respondeu" and status != "nao_respondeu":
            continue

        ultimo_acesso = _parse_dt(usuario.get("last_seen_at"))
        ativo_7d = bool(ultimo_acesso and (agora - ultimo_acesso) <= timedelta(days=7))
        ativo_30d = bool(ultimo_acesso and (agora - ultimo_acesso) <= timedelta(days=30))
        if filtro_atividade == "Ativo últimos 7 dias" and not ativo_7d:
            continue
        if filtro_atividade == "Ativo últimos 30 dias" and not ativo_30d:
            continue
        if filtro_atividade == "Inativo / sem registro" and ativo_30d:
            continue

        linhas.append(
            {
                "email": usuario.get("email") or "—",
                "created_at": usuario.get("created_at"),
                "last_seen_at": usuario.get("last_seen_at"),
                "status_inscricao": status,
                "ativo_7d": ativo_7d,
                "ativo_30d": ativo_30d,
            }
        )
    return linhas


def _tabela_html(linhas: list[dict]) -> str:
    def _data_ou_sem_registro(valor):
        dt = _parse_dt(valor)
        return dt.strftime("%d/%m/%Y %H:%M") if dt else "<span class='cinza'>sem registro</span>"

    corpo = []
    for linha in linhas:
        status = linha["status_inscricao"]
        classe_status = "alta" if status == "inscrito" else ("baixa" if status == "recusou" else "cinza")
        corpo.append(
            "<tr>"
            f"<td style='text-align:left;' class='neutro'>{html.escape(linha['email'])}</td>"
            f"<td class='neutro'>{_data_ou_sem_registro(linha['created_at'])}</td>"
            f"<td class='neutro'>{_data_ou_sem_registro(linha['last_seen_at'])}</td>"
            f"<td class='{classe_status}'>{_ROTULO_STATUS.get(status, status)}</td>"
            f"<td class='{'alta' if linha['ativo_7d'] else 'cinza'}'>{'Sim' if linha['ativo_7d'] else 'Não'}</td>"
            f"<td class='{'alta' if linha['ativo_30d'] else 'cinza'}'>{'Sim' if linha['ativo_30d'] else 'Não'}</td>"
            "</tr>"
        )
    return (
        "<div style=\"overflow-x:auto; overflow-y:hidden;\">"
        "<table style=\"width:100%; border-collapse:collapse;\">"
        "<thead><tr>"
        "<th style=\"text-align:left; font-weight:400;\" class=\"cinza\">E-MAIL</th>"
        "<th class=\"cinza\">CADASTRO</th>"
        "<th class=\"cinza\">ÚLTIMO ACESSO</th>"
        "<th class=\"cinza\">MORNING CALL</th>"
        "<th class=\"cinza\">ATIVO (7D)</th>"
        "<th class=\"cinza\">ATIVO (30D)</th>"
        "</tr></thead>"
        f"<tbody>{''.join(corpo)}</tbody>"
        "</table></div>"
    )


def _csv_bytes(linhas: list[dict]) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["email", "cadastro", "ultimo_acesso", "morning_call", "ativo_7d", "ativo_30d"])
    for linha in linhas:
        escritor.writerow(
            [
                linha["email"],
                linha["created_at"] or "",
                linha["last_seen_at"] or "",
                _ROTULO_STATUS.get(linha["status_inscricao"], linha["status_inscricao"]),
                "sim" if linha["ativo_7d"] else "nao",
                "sim" if linha["ativo_30d"] else "nao",
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def render_usuarios(usuario: dict):
    """Ponto de entrada da aba USUÁRIOS, chamado pelo app.py - só deve
    ser chamado pra quem já passou pela checagem de admin em app.py, mas
    reconfirma aqui mesmo assim (ver docstring do módulo)."""
    st.markdown('<div class="painel-titulo">USUÁRIOS</div>', unsafe_allow_html=True)
    st.caption("Visível só para e-mails admin — métricas e lista vêm direto do Supabase (user_prefs).")

    if usuario.get("email") not in config.obter_emails_admin():
        st.error("Acesso restrito a administradores.")
        return

    usuarios = obter_usuarios_admin(usuario["email"])
    if usuarios is None:
        st.warning(
            "Não foi possível carregar os dados agora (Supabase indisponível). "
            "O resto do Pregão continua funcionando normalmente - tente de novo em instantes."
        )
        return
    if not usuarios:
        st.info("Nenhum usuário identificado ainda.")
        return

    st.markdown(
        "<div class='cinza' style='font-size:0.65rem; margin-bottom:0.6rem;'>"
        "\"Cadastro\" e \"último acesso\" só existem a partir desta versão (2026-10-18) — "
        "usuários de antes podem aparecer sem uma dessas datas até o próximo acesso deles; "
        "não é inatividade, é ausência de dado histórico."
        "</div>",
        unsafe_allow_html=True,
    )

    dias_novos = st.segmented_control(
        "NOVOS CADASTROS NOS ÚLTIMOS", [7, 30, 90], default=30, key="usuarios_periodo_novos",
    ) or 30
    metricas = calcular_metricas(usuarios, dias_novos=dias_novos)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("TOTAL", metricas["total"])
    c2.metric(f"NOVOS ({dias_novos}D)", metricas["novos"])
    c3.metric("ATIVOS 7D", metricas["ativos_7d"])
    c4.metric("ATIVOS 30D", metricas["ativos_30d"])
    c5.metric("INSCRITOS MC", metricas["inscritos"])
    c6.metric("NÃO RESPONDERAM", metricas["nao_responderam"])

    st.divider()

    busca = st.text_input("Buscar por e-mail", key="usuarios_busca", placeholder="parte do e-mail...")
    colf1, colf2 = st.columns(2)
    with colf1:
        filtro_inscricao = st.selectbox(
            "Inscrição no Morning Call",
            ["Todos", "Inscrito", "Recusou", "Não respondeu"],
            key="usuarios_filtro_inscricao",
        )
    with colf2:
        filtro_atividade = st.selectbox(
            "Atividade",
            ["Todos", "Ativo últimos 7 dias", "Ativo últimos 30 dias", "Inativo / sem registro"],
            key="usuarios_filtro_atividade",
        )

    agora = datetime.now(timezone.utc)
    linhas = _filtrar(usuarios, busca, filtro_inscricao, filtro_atividade, agora)

    st.caption(f"{len(linhas)} de {len(usuarios)} usuário(s)")
    if not linhas:
        st.info("Nenhum usuário encontrado com esses filtros.")
        return

    st.markdown(_tabela_html(linhas), unsafe_allow_html=True)

    st.download_button(
        "EXPORTAR CSV (filtro atual)",
        data=_csv_bytes(linhas),
        file_name="usuarios_pregao.csv",
        mime="text/csv",
        key="usuarios_export_csv",
    )
