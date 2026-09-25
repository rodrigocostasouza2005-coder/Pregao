# -*- coding: utf-8 -*-
"""Reset de zoom reutilizável pros gráficos Plotly do projeto (pedido no
redesign do terminal - ver PROGRESSO.md). Sem componente JS novo: cada
gráfico recebe uma `key=` que muda quando o usuário clica em RESET ou
quando os parâmetros que definem o gráfico mudam (ticker/período/
comparação/etc) - o Streamlit remonta o componente Plotly do zero nesses
casos, o que reseta qualquer zoom aplicado (estado é guardado no
client, atrelado à key do componente) automaticamente.

`displayModeBar` fica desligado de propósito em todo o projeto (barra
de ferramentas nativa do Plotly escondida, visual mais limpo) - o botão
de reset visível por isso é um `st.button` comum, não o ícone nativo do
Plotly. Duplo clique continua funcionando sozinho: é comportamento
padrão do Plotly (`doubleClick: 'reset+autosize'`), independente de
`displayModeBar`."""

import streamlit as st


def zoom_key(chave_base: str, *partes_estado) -> str:
    """Renderiza um botão pequeno "↺" alinhado à direita (chamar logo
    ANTES do st.plotly_chart correspondente) e retorna a `key=` pra
    passar pro gráfico. `partes_estado`: qualquer valor que, ao mudar
    (ticker, período, comparar_ibov, tipo de gráfico...), já deve por si
    só resetar o zoom - entram na key junto com o contador do botão,
    então tanto "trocar filtro" quanto "clicar em reset" produzem uma
    key nova, forçando o Streamlit a remontar o gráfico com o range
    original. Nenhuma coleta de dado nova acontece por causa disso - é
    só remontagem do componente com o `fig` já calculado no mesmo rerun."""
    contador_key = f"_zoom_reset_{chave_base}"
    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0
    _vazio, col_botao = st.columns([12, 1])
    with col_botao:
        if st.button("↺", key=f"{contador_key}_btn", help="Resetar zoom do gráfico"):
            st.session_state[contador_key] += 1
    sufixo_estado = "_".join(str(p) for p in partes_estado)
    return f"{chave_base}_{sufixo_estado}_{st.session_state[contador_key]}"
