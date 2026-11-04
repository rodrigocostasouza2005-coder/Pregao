# -*- coding: utf-8 -*-
"""Interface compacta para o DCF operacional auditável."""
import html

import streamlit as st

from data.coordenador_central.dcf_operacional import calcular_dcf_operacional


def render_dcf_operacional():
    """Formulário explícito: nenhuma premissa operacional é preenchida por padrão."""
    with st.expander("DCF operacional — projeção de 5 anos", expanded=False):
        st.caption(
            "Preencha os drivers anuais. O modelo não copia crescimento histórico nem "
            "inventa margens. Percentuais devem ser informados em pontos percentuais "
            "(ex.: 12,5 para 12,5%)."
        )
        with st.form("coord_dcf_operacional_form"):
            c1, c2, c3 = st.columns(3)
            receita = c1.number_input("Receita-base (milhões)", min_value=0.0, value=None, placeholder="Informe", key="op_receita")
            imposto = c2.number_input("Alíquota de impostos (%)", min_value=0.0, max_value=99.9, value=None, placeholder="Informe", key="op_imposto")
            wacc = c3.number_input("WACC (%)", min_value=0.01, value=None, placeholder="Informe", key="op_wacc")
            c1, c2, c3 = st.columns(3)
            g = c1.number_input("Crescimento perpétuo (%)", min_value=0.0, value=None, placeholder="Informe", key="op_g")
            divida = c2.number_input("Dívida líquida (milhões)", value=None, placeholder="Informe", key="op_divida")
            acoes = c3.number_input("Ações (milhões)", min_value=0.000001, value=None, placeholder="Informe", key="op_acoes")
            st.markdown("**Premissas anuais**")
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
                st.warning("Preencha todos os campos. O modelo não completa premissas ausentes.")
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
                resultado = calcular_dcf_operacional(p)
                st.session_state["coord_dcf_operacional_resultado"] = resultado
        resultado = st.session_state.get("coord_dcf_operacional_resultado")
        if resultado:
            if not resultado.get("disponivel"):
                st.warning(resultado.get("motivo") or "DCF indisponível.")
                return
            alvo = resultado["preco_alvo"]
            st.markdown(
                f"<div class='coord-valuation-destaque'><div class='coord-valuation-preco'>R$ {alvo:,.2f}</div>"
                "<div class='coord-valuation-legenda'>Preço-alvo do DCF operacional · BRL por ação</div></div>"
                .replace(",", "X").replace(".", ",").replace("X", "."),
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor da firma", f"R$ {resultado['valor_empresa']/1e6:,.1f} mi")
            c2.metric("Valor do patrimônio", f"R$ {resultado['valor_patrimonio']/1e6:,.1f} mi")
            c3.metric("Valor terminal / VP", f"{resultado['valor_presente_terminal']/1e6:,.1f} mi")
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
            st.dataframe(linhas, hide_index=True, use_container_width=True)
            st.caption(f"Premissas: {html.escape(str(resultado.get('fonte_premissas') or 'Fonte não informada'))}. Confira a moeda e a escala dos dados antes de usar o valuation.")
