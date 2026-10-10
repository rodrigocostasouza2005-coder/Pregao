# -*- coding: utf-8 -*-
"""Aba SAUDE DOS DADOS - monitoramento real dos coletores do PREGAO
(FASE 2 da auditoria 2026-10-09, ver PROGRESSO.md/BACKLOG.md). Isolada
de proposito (so' le data/saude_dados.py) - nao compartilha estado nem
import de UI com nenhuma outra aba, pra nao conflitar com sessoes que
estejam tocando RESEARCH/CALENDARIO/NEWS ao mesmo tempo.

Diferente do painel DIAGNOSTICO DE FONTES (app.py, dentro de CONFIG):
aquele testa reachability AO VIVO sob clique, sem persistir nada; este
mostra o HISTORICO real de tentativas (quando rodou, deu certo,
persistiu, quantos registros novos) - complementares, nao substitutos."""

import streamlit as st

from data import saude_dados

_COR_POR_ESTADO = {
    "SUCESSO_COM_NOVIDADE": "alta",
    "SUCESSO_SEM_NOVIDADE": "alta",
    "PARCIAL": "alerta",
    "DADOS_DESATUALIZADOS": "alerta",
    "FALHA_EXECUCAO": "baixa",
    "FALHA_PERSISTENCIA": "baixa",
    "FONTE_INDISPONIVEL": "baixa",
    "NAO_COMPROVADO": "cinza",
    "NUNCA_EXECUTADO": "cinza",
}


def _idade_formatada(iso_ts: str | None) -> str:
    if not iso_ts:
        return "—"
    from datetime import datetime, timezone
    ts = datetime.fromisoformat(iso_ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    horas = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if horas < 1:
        return f"há {int(horas * 60)}min"
    if horas < 48:
        return f"há {horas:.0f}h"
    return f"há {horas / 24:.0f}d"


def render_saude_dados():
    st.markdown('<div class="painel-titulo">SAÚDE DOS DADOS</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='cinza' style='font-size:0.7rem; margin-bottom:0.6rem;'>"
        "Estado real de cada coletor — última tentativa, último sucesso "
        "confirmado e registros novos. Nunca mostra dado antigo como se "
        "fosse atual; coletor sem evidência suficiente aparece como tal, "
        "nunca como 'OK' por omissão.</div>",
        unsafe_allow_html=True,
    )

    if st.button("ATUALIZAR", key="saude_dados_atualizar"):
        st.cache_data.clear()

    painel = saude_dados.obter_painel_saude()

    categorias = {}
    for item in painel:
        categorias.setdefault(item["categoria"], []).append(item)

    for categoria, itens in categorias.items():
        with st.container(border=True):
            st.markdown(
                f"<div class='alerta' style='font-weight:600; letter-spacing:0.05em; "
                f"font-size:0.72rem; margin-bottom:0.3rem;'>{categoria.upper()}</div>",
                unsafe_allow_html=True,
            )
            linhas_html = ""
            for item in itens:
                cor = _COR_POR_ESTADO.get(item["codigo_estado"], "neutro")
                status_bruto = item.get("status_bruto") or {}
                ultimo_sucesso = _idade_formatada(status_bruto.get("ultimo_sucesso_em"))
                ultima_tentativa = (
                    _idade_formatada(status_bruto.get("ultima_tentativa_em"))
                    if item["instrumentado"] else "não instrumentado"
                )
                registros = status_bruto.get("registros_novos")
                registros_fmt = "—" if registros is None else str(registros)
                linhas_html += (
                    "<tr>"
                    f"<td style='text-align:left;' class='neutro'>{item['nome']}</td>"
                    f"<td style='text-align:left;' class='cinza'>{item['fonte']}</td>"
                    f"<td class='{cor}'>{item['rotulo_estado']}</td>"
                    f"<td class='cinza'>{ultima_tentativa}</td>"
                    f"<td class='cinza'>{ultimo_sucesso}</td>"
                    f"<td class='cinza'>{registros_fmt}</td>"
                    "</tr>"
                )
            st.markdown(
                f"""
                <div style="overflow-x:auto; overflow-y:hidden;">
                <table style="width:100%; border-collapse:collapse;">
                <thead><tr>
                    <th style="text-align:left; font-weight:400;" class="cinza">COLETOR</th>
                    <th style="text-align:left; font-weight:400;" class="cinza">FONTE</th>
                    <th class="cinza">ESTADO</th>
                    <th class="cinza">ÚLTIMA TENTATIVA</th>
                    <th class="cinza">ÚLTIMO SUCESSO</th>
                    <th class="cinza">REGISTROS NOVOS</th>
                </tr></thead>
                <tbody>{linhas_html}</tbody>
                </table>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # 1 st.markdown SO' pra todas as legendas da categoria (nao 1
            # por item): bug real corrigido, 2026-10-10 (confirmado por
            # screenshot real do Playwright) - varias chamadas separadas
            # de st.markdown, uma por item, renderizavam cada uma com
            # ALTURA EFETIVA ZERO entre si (o gap de 0.4rem do bloco
            # vertical do Streamlit nao se aplicava aqui, causa exata nao
            # isolada) e as linhas ficavam sobrepostas/ilegiveis quando
            # havia mais de 1 coletor na mesma categoria (MACRO, RESEARCH).
            # Combinar num unico bloco HTML com margin-top proprio entre
            # linhas resolve de forma determinista, sem depender do
            # espacamento entre elementos do Streamlit.
            legendas_html = "".join(
                f"<div style='margin-top:0.25rem;'>{item['nome']}: frequência esperada — "
                f"{item['frequencia_esperada']}"
                f"{'' if item['instrumentado'] else ' · status derivado só do último dado persistido (coletor ainda não registra tentativas)'}"
                "</div>"
                for item in itens
            )
            st.markdown(
                f"<div class='cinza' style='font-size:0.65rem;'>{legendas_html}</div>",
                unsafe_allow_html=True,
            )
