# Harness "ANTES" - reproduz literalmente o render MINIMO que existia em
# app.py antes desta missao (ver git log de app.py, commit 1a7547e/#304 -
# codigo copiado aqui so' pra evidencia visual, nao executa mais em
# producao). Mesmo dado mockado de _dados_carteira.py usado no "DEPOIS",
# pra comparacao justa.
from _dados_carteira import carteira_mock, historico_mock
from _tema import preparar_pagina

import streamlit as st

preparar_pagina("harness carteira ANTES")

ABA = __import__("sys").argv[1] if len(__import__("sys").argv) > 1 else "visao-geral"

with st.container():
    if ABA == "visao-geral":
        st.title("Carteira Recomendada")
        st.caption("Construída a partir do Comitê de Investimentos (coordenador_analises) - "
                   "informativa, não é recomendação personalizada nem garante rentabilidade.")
        carteira = carteira_mock()
        for aviso in carteira.get("avisos") or []:
            st.warning(aviso)
        itens = carteira.get("itens") or []
        if not itens:
            st.info("Nenhum ativo elegível no momento (ver avisos acima).")
        for item in itens:
            with st.expander(f"{item['ticker']} · {item.get('peso_pct')}% · sinal {item.get('sinal_comite')}"):
                st.write(f"Setor: {item.get('setor') or 'não classificado'}")
                st.write(f"Preço de referência: {item.get('preco_referencia')} · Preço-alvo: {item.get('preco_alvo')} ({item.get('metodo_preco_alvo')})")
                st.write(f"Tese: {item.get('tese') or 'sem resumo disponível'}")
                if item.get("riscos"):
                    st.write("Riscos: " + "; ".join(item["riscos"]))
                st.write(f"Critério de saída: {item.get('criterio_saida')}")
                st.write(f"Próxima revisão: {item.get('data_revisao')}")
    else:
        st.title("Carteira Recomendada — Histórico")
        historico = historico_mock()
        if historico is None:
            st.info("Histórico ainda não disponível (persistência proposta em "
                     "sql/carteira_recomendada.sql, não aplicada em produção).")
        elif not historico:
            st.info("Nenhuma alteração registrada ainda.")
        else:
            for linha in historico:
                st.write(linha)
