# -*- coding: utf-8 -*-
"""Interface do DCF operacional auditável - simulador manual de valuation
(terminal preto/âmbar, ver ui/design_system.py). Reformulado (2026-11-06,
onda VALUATION) pra reunir num só painel: premissas editáveis, projeção de
5 anos, preço justo, margem de segurança, 3 cenários (otimista/base/
pessimista) e sensibilidade (WACC x crescimento terminal) - tudo
apresentação sobre o motor já testado em data/coordenador_central/
dcf_operacional.py (calcular_dcf_operacional, inalterado, + duas funções
novas de composição: calcular_cenarios_dcf_operacional e
calcular_sensibilidade_dcf_operacional - nenhuma lógica de cálculo nova
vive aqui na UI).

Por que "100% premissa, sem fato/estimativa misturado": diferente do
parecer de Valuation do comitê (fundamentos coletados automaticamente,
rota COORDENADOR CENTRAL › ANALISAR, depois de digitar um ticker - fora do
escopo deste arquivo), este simulador não lê nenhum dado de mercado - zero
coleta própria, de propósito (ver doc original do módulo). Então a
distinção "fato vs. estimativa vs. premissa" que o resto do app faz com
selos (ver ui/radar_tab.py:_selo_evidencia) aqui colapsa pra uma única
categoria: TUDO é premissa digitada por quem está calculando. O rótulo
"PREMISSA" (chip âmbar discreto) aparece em cada bloco de entrada e em
cada número derivado dela, exatamente pra nunca deixar ambíguo que nada
aqui foi coletado nem inventado automaticamente."""
import html

import streamlit as st

import config
from data.coordenador_central.dcf_operacional import (
    calcular_cenarios_dcf_operacional,
    calcular_dcf_operacional,
    calcular_sensibilidade_dcf_operacional,
)

_CSS_DCF_OPERACIONAL = """
.dcfop-nota { color: var(--cinza); font-size: 0.7rem; margin: 0.1rem 0 0.7rem 0; line-height: 1.55; }
.dcfop-chip {
    display: inline-block; font-size: 0.58rem; letter-spacing: 0.04em; font-weight: 700;
    padding: 0.08rem 0.4rem; border: 1px dashed var(--destaque); color: var(--destaque);
    white-space: nowrap; vertical-align: middle; margin-right: 0.4rem;
}
.dcfop-chip-calc { border-style: solid; color: var(--neutro); border-color: var(--borda); }
.dcfop-legenda {
    border: 1px solid var(--borda); padding: 0.55rem 0.7rem; margin-bottom: 0.9rem;
    font-size: 0.7rem; color: var(--cinza); line-height: 1.6;
}
.dcfop-secao {
    font-size: 0.68rem; color: var(--cinza); letter-spacing: 0.06em; font-weight: 600;
    border-bottom: 1px solid var(--borda); padding-bottom: 0.25rem; margin: 1rem 0 0.5rem 0;
}
.dcfop-hero {
    display: flex; flex-wrap: wrap; align-items: baseline; gap: 1.4rem;
    border: 1px solid var(--destaque); padding: 0.9rem 1.1rem; margin: 0.6rem 0 0.9rem 0;
}
.dcfop-hero-preco { font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem; font-weight: 700; color: var(--destaque); }
.dcfop-hero-legenda { color: var(--cinza); font-size: 0.68rem; }
.dcfop-hero-item { font-family: 'IBM Plex Mono', monospace; font-size: 0.95rem; }
.dcfop-hero-item .dcfop-hero-rotulo { display: block; color: var(--cinza); font-size: 0.62rem; letter-spacing: 0.03em; font-weight: 400; }
.dcfop-cenarios { display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 0.8rem; }
.dcfop-cenario {
    flex: 1 1 200px; border: 1px solid var(--borda); padding: 0.55rem 0.7rem;
    font-family: 'IBM Plex Mono', monospace;
}
.dcfop-cenario-otimista { border-left: 3px solid var(--alta); }
.dcfop-cenario-base { border-left: 3px solid var(--destaque); }
.dcfop-cenario-pessimista { border-left: 3px solid var(--baixa); }
.dcfop-cenario-rotulo { font-size: 0.62rem; letter-spacing: 0.05em; color: var(--cinza); font-weight: 600; }
.dcfop-cenario-preco { font-size: 1.05rem; font-weight: 700; margin-top: 0.15rem; }
.dcfop-cenario-otimista .dcfop-cenario-preco { color: var(--alta); }
.dcfop-cenario-base .dcfop-cenario-preco { color: var(--destaque); }
.dcfop-cenario-pessimista .dcfop-cenario-preco { color: var(--baixa); }
.dcfop-cenario-detalhe { font-size: 0.66rem; color: var(--cinza); margin-top: 0.2rem; }
.dcfop-sens-tabela { width: 100%; border-collapse: collapse; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; }
.dcfop-sens-tabela th {
    color: var(--cinza); font-size: 0.6rem; font-weight: 600; letter-spacing: 0.03em;
    text-align: center; padding: 0.25rem 0.4rem; border-bottom: 1px solid var(--borda); white-space: nowrap;
}
.dcfop-sens-tabela td { text-align: center; padding: 0.3rem 0.4rem; border-bottom: 1px solid var(--borda); white-space: nowrap; }
.dcfop-sens-tabela td:first-child, .dcfop-sens-tabela th:first-child {
    text-align: right; color: var(--cinza); font-size: 0.64rem; border-right: 1px solid var(--borda);
}
.dcfop-sens-tabela td.dcfop-sens-base { outline: 1px solid var(--destaque); font-weight: 700; }
.dcfop-sens-indisponivel { color: var(--cinza); }
"""


def _injetar_css_dcf_operacional():
    st.markdown(f"<style>{_CSS_DCF_OPERACIONAL}</style>", unsafe_allow_html=True)


def _fmt(valor, casas=2, sufixo=""):
    if valor is None:
        return "—"
    return f"{config.formatar_numero(valor, casas, 'BR')}{sufixo}"


def _chip(texto: str, calculado: bool = False) -> str:
    classe = "dcfop-chip dcfop-chip-calc" if calculado else "dcfop-chip"
    return f"<span class='{classe}'>{html.escape(texto)}</span>"


def _bloco_cenarios_html(cenarios: dict) -> str:
    cartoes = []
    ordem = (("pessimista", "PESSIMISTA"), ("base", "BASE"), ("otimista", "OTIMISTA"))
    for chave, rotulo in ordem:
        c = cenarios.get(chave) or {}
        delta = c.get("delta_crescimento_pp", 0.0)
        delta_txt = "" if chave == "base" else f" (Δ {delta:+.1f} p.p./ano na receita)"
        if not c.get("disponivel"):
            corpo = f"<div class='dcfop-cenario-preco'>—</div><div class='dcfop-cenario-detalhe'>{html.escape(c.get('motivo') or 'indisponível')}</div>"
        else:
            margem = c.get("margem_seguranca_pct")
            margem_txt = f" · margem de segurança {_fmt(margem, 1, '%')}" if margem is not None else ""
            upside_txt = f" · upside {_fmt(c.get('upside_pct'), 1, '%')}" if c.get("upside_pct") is not None else ""
            corpo = (
                f"<div class='dcfop-cenario-preco'>R$ {_fmt(c['preco_alvo'], 2)}</div>"
                f"<div class='dcfop-cenario-detalhe'>{upside_txt}{margem_txt}</div>"
            )
        cartoes.append(
            f"<div class='dcfop-cenario dcfop-cenario-{chave}'>"
            f"<div class='dcfop-cenario-rotulo'>{rotulo}{html.escape(delta_txt)}</div>{corpo}</div>"
        )
    return f"<div class='dcfop-cenarios'>{''.join(cartoes)}</div>"


def _tabela_sensibilidade_html(sens: dict) -> str:
    cabecalho = "<tr><th>WACC \\ Δg</th>" + "".join(
        f"<th>{g*100:+.2f} p.p.</th>" for g in sens["passos_g"]
    ) + "</tr>"
    linhas_html = []
    for linha in sens["linhas"]:
        celulas_html = []
        for cel in linha["celulas"]:
            e_base = linha["delta_wacc"] == 0.0 and cel["delta_g"] == 0.0
            classe_td = "dcfop-sens-base" if e_base else ""
            if not cel["disponivel"] or cel["preco_alvo"] is None:
                celulas_html.append(f"<td class='{classe_td} dcfop-sens-indisponivel'>—</td>")
                continue
            upside = cel.get("upside_pct")
            estilo = f" style='color:{'var(--alta)' if upside >= 0 else 'var(--baixa)'};'" if upside is not None else ""
            celulas_html.append(
                f"<td class='{classe_td}'{estilo}>R$ {_fmt(cel['preco_alvo'], 2)}</td>"
            )
        linhas_html.append(f"<tr><td>{linha['wacc']*100:.2f}%</td>{''.join(celulas_html)}</tr>")
    return f"<table class='dcfop-sens-tabela'>{cabecalho}{''.join(linhas_html)}</table>"


def render_dcf_operacional():
    """Formulário explícito: nenhuma premissa operacional é preenchida por padrão."""
    _injetar_css_dcf_operacional()
    with st.expander("DCF OPERACIONAL — SIMULADOR MANUAL (5 ANOS)", expanded=False):
        st.markdown(
            "<div class='dcfop-legenda'>"
            + _chip("PREMISSA")
            + "toda entrada e todo número derivado deste painel é premissa que <b>você</b> digita - "
            "o modelo não copia crescimento histórico, não copia margem de nenhum período anterior "
            "e não estima nada por conta própria. Sem dado de mercado lido automaticamente aqui "
            "(zero coleta própria). Percentuais em pontos percentuais (ex.: 12,5 para 12,5%)."
            "<br><br>"
            "<div class='dcfop-nota'>Simulador manual independente: não alimenta nem é alimentado "
            "pelo DCF oficial do comitê (o parecer de Valuation, calculado a partir dos fundamentos "
            "coletados automaticamente - COORDENADOR CENTRAL › ANALISAR, depois de digitar um "
            "ticker). Os dois podem apontar preços-alvo diferentes para o mesmo papel - isso é "
            "esperado, não é um bug.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.form("coord_dcf_operacional_form"):
            st.markdown("<div class='dcfop-secao'>PREMISSAS ESCALARES</div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            receita = c1.number_input("Receita-base (milhões)", min_value=0.0, value=None, placeholder="Informe", key="op_receita")
            imposto = c2.number_input("Alíquota de impostos (%)", min_value=0.0, max_value=99.9, value=None, placeholder="Informe", key="op_imposto")
            wacc = c3.number_input("WACC (%)", min_value=0.01, value=None, placeholder="Informe", key="op_wacc")
            c1, c2, c3 = st.columns(3)
            g = c1.number_input("Crescimento perpétuo (%)", min_value=0.0, value=None, placeholder="Informe", key="op_g")
            divida = c2.number_input("Dívida líquida (milhões)", value=None, placeholder="Informe", key="op_divida")
            acoes = c3.number_input("Ações (milhões)", min_value=0.000001, value=None, placeholder="Informe", key="op_acoes")
            preco_atual = st.number_input(
                "Cotação atual (opcional - só pra comparar com o preço-alvo; não é lida automaticamente)",
                min_value=0.0, value=None, placeholder="Deixe vazio se não quiser comparar", key="op_preco_atual",
            )

            st.markdown(
                "<div class='dcfop-secao'>CENÁRIOS — variação opcional no crescimento de receita</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Some pontos percentuais ao crescimento de receita de TODOS os 5 anos pra construir "
                "otimista/pessimista. Deixe em 0 pra ver só o cenário base nos três cartões (margem, "
                "D&A, CAPEX, capital de giro, WACC e g terminal não mudam entre cenários)."
            )
            c1, c2 = st.columns(2)
            delta_otimista = c1.number_input("Δ otimista (p.p./ano na receita)", value=0.0, step=0.5, key="op_delta_otimista")
            delta_pessimista = c2.number_input("Δ pessimista (p.p./ano na receita)", value=0.0, step=0.5, key="op_delta_pessimista")

            st.markdown("<div class='dcfop-secao'>PREMISSAS ANUAIS (cenário base)</div>", unsafe_allow_html=True)
            anos = st.columns(5)
            vetores = {k: [] for k in (
                "crescimento_receita", "margem_ebit", "da_sobre_receita",
                "capex_sobre_receita", "capital_giro_sobre_receita_incremental"
            )}
            campos = [
                ("crescimento_receita", "Cresc. receita (%)"),
                ("margem_ebit", "Margem EBIT (%)"),
                ("da_sobre_receita", "D&A/receita (%)"),
                ("capex_sobre_receita", "CAPEX/receita (%)"),
                ("capital_giro_sobre_receita_incremental", "CG/receita incremental (%)"),
            ]
            for ano, coluna in enumerate(anos, start=1):
                with coluna:
                    st.caption(f"Ano {ano}")
                    for chave, rotulo in campos:
                        valor = st.number_input(rotulo, value=None, placeholder="—", key=f"op_{chave}_{ano}")
                        vetores[chave].append(valor)
            fonte = st.text_input("Fonte e data-base das premissas", placeholder="Ex.: relatório anual 2025, página 84")
            enviar = st.form_submit_button("Calcular DCF operacional")
        if enviar:
            valores = [receita, imposto, wacc, g, divida, acoes] + [x for xs in vetores.values() for x in xs]
            if any(x is None for x in valores):
                st.warning("Preencha todos os campos obrigatórios. O modelo não completa premissas ausentes.")
            else:
                p = {
                    "receita_base": receita * 1_000_000,
                    "aliquota_impostos": imposto / 100,
                    "wacc": wacc / 100,
                    "g_terminal": g / 100,
                    "divida_liquida": divida * 1_000_000,
                    "acoes": acoes * 1_000_000,
                    "moeda": "BRL",
                    "fonte_premissas": fonte.strip() or "Não informada pelo usuário",
                    "data_base": None,
                }
                p.update({k: [x / 100 for x in xs] for k, xs in vetores.items()})
                resultado = calcular_dcf_operacional(p, preco_atual=preco_atual)
                cenarios = calcular_cenarios_dcf_operacional(
                    p, delta_otimista_pp=delta_otimista, delta_pessimista_pp=delta_pessimista,
                    preco_atual=preco_atual,
                )
                sensibilidade = calcular_sensibilidade_dcf_operacional(p, preco_atual=preco_atual)
                st.session_state["coord_dcf_operacional_resultado"] = resultado
                st.session_state["coord_dcf_operacional_cenarios"] = cenarios
                st.session_state["coord_dcf_operacional_sensibilidade"] = sensibilidade

        resultado = st.session_state.get("coord_dcf_operacional_resultado")
        if resultado:
            if not resultado.get("disponivel"):
                st.warning(resultado.get("motivo") or "DCF indisponível.")
                return
            alvo = resultado["preco_alvo"]
            preco_atual_calc = resultado.get("upside_pct") is not None

            st.markdown("<div class='dcfop-secao'>PREÇO JUSTO — PREMISSA BASE</div>", unsafe_allow_html=True)
            itens_hero = (
                f"<div class='dcfop-hero-preco'>R$ {_fmt(alvo, 2)}</div>"
                f"<div class='dcfop-hero-legenda'>Preço-alvo do DCF operacional · BRL por ação</div>"
            )
            if preco_atual_calc:
                margem = resultado.get("margem_seguranca_pct")
                itens_hero += (
                    f"<div class='dcfop-hero-item'><span class='dcfop-hero-rotulo'>UPSIDE</span>"
                    f"{_fmt(resultado['upside_pct'], 1, '%')}</div>"
                    f"<div class='dcfop-hero-item'><span class='dcfop-hero-rotulo'>MARGEM DE SEGURANÇA</span>"
                    f"{_fmt(margem, 1, '%')}</div>"
                )
            st.markdown(f"<div class='dcfop-hero'>{itens_hero}</div>", unsafe_allow_html=True)
            if not preco_atual_calc:
                st.caption("Informe a cotação atual no formulário acima pra ver upside e margem de segurança.")

            c1, c2, c3 = st.columns(3)
            c1.metric("Valor da firma", f"R$ {resultado['valor_empresa']/1e6:,.1f} mi")
            c2.metric("Valor do patrimônio", f"R$ {resultado['valor_patrimonio']/1e6:,.1f} mi")
            c3.metric("Valor terminal / VP", f"{resultado['valor_presente_terminal']/1e6:,.1f} mi")

            cenarios = st.session_state.get("coord_dcf_operacional_cenarios")
            if cenarios and cenarios.get("disponivel"):
                st.markdown(
                    "<div class='dcfop-secao'>CENÁRIOS — OTIMISTA / BASE / PESSIMISTA</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(_bloco_cenarios_html(cenarios["cenarios"]), unsafe_allow_html=True)

            linhas = []
            for item in resultado["projecao"]:
                linhas.append({
                    "Ano": item["ano"],
                    "Receita (R$ mi)": item["receita"]/1e6,
                    "EBIT (R$ mi)": item["ebit"]/1e6,
                    "NOPAT (R$ mi)": item["nopat"]/1e6,
                    "D&A (R$ mi)": item["depreciacao_amortizacao"]/1e6,
                    "CAPEX (R$ mi)": item["capex"]/1e6,
                    "Δ Capital de giro (R$ mi)": item["variacao_capital_giro"]/1e6,
                    "FCF (R$ mi)": item["fcf"]/1e6,
                })
            st.markdown("<div class='dcfop-secao'>PROJEÇÃO — DERIVADA DAS PREMISSAS ACIMA</div>", unsafe_allow_html=True)
            st.dataframe(linhas, hide_index=True, use_container_width=True)

            sensibilidade = st.session_state.get("coord_dcf_operacional_sensibilidade")
            if sensibilidade and sensibilidade.get("disponivel"):
                st.markdown(
                    "<div class='dcfop-secao'>SENSIBILIDADE — WACC × CRESCIMENTO TERMINAL</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(_tabela_sensibilidade_html(sensibilidade), unsafe_allow_html=True)
                legenda_cor = (
                    " Verde/vermelho seguem o sinal do upside sobre a cotação informada."
                    if preco_atual_calc else
                    " Informe a cotação atual pra colorir a tabela por upside/downside."
                )
                st.caption("Célula contornada em âmbar = cenário base (sem variação)." + legenda_cor)

            st.caption(f"Premissas: {html.escape(str(resultado.get('fonte_premissas') or 'Fonte não informada'))}. Confira a moeda e a escala dos dados antes de usar o valuation.")
