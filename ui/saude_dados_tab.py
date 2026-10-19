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

from data import coletores_status, saude_dados

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

    # Diagnostico de infraestrutura (achado real, missao coletores
    # 2026-10-13): antes desta checagem, uma tabela `coletores_status`
    # ausente/inacessivel no Supabase de producao (mesma classe de bug ja'
    # confirmada em `eventos_resultados`, PGRST205, commit 4c17876) e um
    # coletor que genuinamente nunca rodou eram 100% indistinguiveis na
    # UI - os dois apareciam como "Nunca executado"/"Nao comprovado" sem
    # nenhum aviso de QUAL e' o caso. Mostrado so' quando o diagnostico
    # falha (nunca um "tudo OK" extra na tela comum).
    #
    # Continuacao 2026-10-13: `disponivel` deixou de ser um binario
    # False/None - agora distingue TABELA_AUSENTE (migração pendente,
    # vermelho) de CREDENCIAL_OU_CONEXAO (tabela pode já existir, erro
    # é outro - amarelo) de ERRO_DESCONHECIDO (amarelo, causa não
    # identificável só pelo texto do erro). Antes, os 2 últimos casos
    # acendiam o MESMO vermelho de "tabela ausente", levando a rodar
    # uma migração que não resolveria nada.
    disponivel = saude_dados.diagnostico_infraestrutura()
    if disponivel == coletores_status.TABELA_AUSENTE:
        st.error(
            "Tabela **coletores_status** não encontrada no Supabase de produção "
            "(erro real do Postgrest compatível com tabela/schema ausente, ex. "
            "`PGRST205: Could not find the table`). Os coletores abaixo marcados "
            "'Nunca executado'/'Não comprovado' podem estar rodando normalmente por "
            "baixo — este painel só não consegue LER nem GRAVAR o histórico de "
            "tentativas. Ação: copie o conteúdo de `sql/coletores_status.sql` e "
            "rode no **SQL Editor** do projeto Supabase de produção certo (migração "
            "idempotente — `create table if not exists`, não apaga nada existente)."
        )
    elif disponivel == coletores_status.TABELA_CREDENCIAL_OU_CONEXAO:
        st.warning(
            "A consulta à tabela **coletores_status** falhou com um erro de "
            "**credencial/autorização ou de conexão** (API key inválida/errada, JWT, "
            "RLS bloqueando por role errada, ou timeout/DNS/SSL) — **não** é tabela "
            "ausente; rodar a migração não resolve isto. Ação: em 'Manage app' → "
            "'Secrets' do Streamlit Cloud, confira se `supabase.url` e "
            "`supabase.secret_key` apontam para o projeto Supabase de produção "
            "correto e usam a **secret key** (nunca a anon/public key), e confirme "
            "que o projeto Supabase está no ar."
        )
    elif disponivel == coletores_status.TABELA_ERRO_DESCONHECIDO:
        st.warning(
            "A consulta à tabela **coletores_status** falhou por um motivo que não "
            "bate com 'tabela ausente' nem com 'credencial/conexão' — ainda é um "
            "erro real, só não identificável automaticamente pelo texto. Ação: veja "
            "o erro completo em 'Manage app' → 'Logs' do Streamlit Cloud, procurando "
            "por `[coletores_status] tabela_disponivel`."
        )
    elif disponivel is None:
        st.warning(
            "Supabase indisponível neste momento (sem credencial configurada ou "
            "banco fora do ar) — não foi possível checar o histórico real de "
            "tentativas de nenhum coletor."
        )

    painel = saude_dados.obter_painel_saude()

    # Resumo compacto (achado real da missao de redesign 2026-10-19,
    # secao 3.6: "resumo compacto com metricas reais disponiveis" -
    # antes a tela ia direto pras tabelas por categoria, sem nenhum
    # "estado geral" visivel sem rolar/ler tudo). Mesma classificacao
    # JA' usada por linha (_COR_POR_ESTADO), so' agregada - nunca uma
    # metrica nova/paralela.
    if painel:
        contagem = {"alta": 0, "alerta": 0, "baixa": 0, "cinza": 0}
        for item in painel:
            contagem[_COR_POR_ESTADO.get(item["codigo_estado"], "cinza")] += 1
        st.markdown(
            "<div style='display:flex; gap:1.2rem; flex-wrap:wrap; font-size:0.72rem; "
            "margin-bottom:0.7rem; padding-bottom:0.5rem; border-bottom:1px solid var(--borda);'>"
            f"<span class='alta'>● {contagem['alta']} SAUDÁVE{'L' if contagem['alta'] == 1 else 'IS'}</span>"
            f"<span class='alerta'>● {contagem['alerta']} EM ATENÇÃO</span>"
            f"<span class='baixa'>● {contagem['baixa']} EM FALHA</span>"
            f"<span class='cinza'>● {contagem['cinza']} NÃO COMPROVADO{'' if contagem['cinza'] == 1 else 'S'}</span>"
            f"<span class='cinza'>· {len(painel)} coletor{'' if len(painel) == 1 else 'es'} monitorado{'' if len(painel) == 1 else 's'}</span>"
            "</div>",
            unsafe_allow_html=True,
        )

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
