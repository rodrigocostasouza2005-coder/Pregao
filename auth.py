# -*- coding: utf-8 -*-
"""Login Google nativo do Streamlit (st.login/st.user) e tela de apresentação.

A tela de apresentação (sem login) é só isso: apresentação. Nenhuma
lógica de autenticação/sessão/OAuth mora aqui além da chamada nativa
`st.login()` já existente - o objetivo desta revisão foi só a
composição visual (ver PROGRESSO.md, "upgrade tela inicial")."""

import streamlit as st


def logado() -> bool:
    return bool(st.user.is_logged_in)


def dados_usuario() -> dict:
    """sub (ID estável do Google) e email (minúsculo) do usuário logado."""
    return {
        "sub": st.user.sub,
        "email": (st.user.email or "").lower(),
        "nome": getattr(st.user, "name", "") or "",
    }


# icone "G" oficial do Google (4 cores), embutido como data URI SVG pra
# nao depender de request externo/CDN na tela que roda ANTES de qualquer
# login - usado via CSS ::before no botao (st.button so' aceita texto
# simples, nao HTML arbitrario dentro do label)
_ICONE_GOOGLE = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCIgd2lkdGg9IjE4IiBoZWlnaHQ9IjE4Ij48cGF0aCBmaWxsPSIjRkZDMTA3IiBkPSJNNDMuNjExLDIwLjA4M0g0MlYyMEgyNHY4aDExLjMwM2MtMS42NDksNC42NTctNi4wOCw4LTExLjMwMyw4Yy02LjYyNywwLTEyLTUuMzczLTEyLTEyYzAtNi42MjcsNS4zNzMtMTIsMTItMTJjMy4wNTksMCw1Ljg0MiwxLjE1NCw3Ljk2MSwzLjAzOWw1LjY1Ny01LjY1N0MzNC4wNDYsNi4wNTMsMjkuMjY4LDQsMjQsNEMxMi45NTUsNCw0LDEyLjk1NSw0LDI0YzAsMTEuMDQ1LDguOTU1LDIwLDIwLDIwYzExLjA0NSwwLDIwLTguOTU1LDIwLTIwQzQ0LDIyLjY1OSw0My44NjIsMjEuMzUsNDMuNjExLDIwLjA4M3oiLz48cGF0aCBmaWxsPSIjRkYzRDAwIiBkPSJNNi4zMDYsMTQuNjkxbDYuNTcxLDQuODE5QzE0LjY1NSwxNS4xMDgsMTguOTYxLDEyLDI0LDEyYzMuMDU5LDAsNS44NDIsMS4xNTQsNy45NjEsMy4wMzlsNS42NTctNS42NTdDMzQuMDQ2LDYuMDUzLDI5LjI2OCw0LDI0LDRDMTYuMzE4LDQsOS42NTYsOC4zMzcsNi4zMDYsMTQuNjkxeiIvPjxwYXRoIGZpbGw9IiM0Q0FGNTAiIGQ9Ik0yNCw0NGM1LjE2NiwwLDkuODYtMS45NzcsMTMuNDA5LTUuMTkybC02LjE5LTUuMjM4QzI5LjIxMSwzNS4wOTEsMjYuNzE1LDM2LDI0LDM2Yy01LjIwMiwwLTkuNjE5LTMuMzE3LTExLjI4My03Ljk0NmwtNi41MjIsNS4wMjVDOS41MDUsMzkuNTU2LDE2LjIyNyw0NCwyNCw0NHoiLz48cGF0aCBmaWxsPSIjMTk3NkQyIiBkPSJNNDMuNjExLDIwLjA4M0g0MlYyMEgyNHY4aDExLjMwM2MtMC43OTIsMi4yMzctMi4yMzEsNC4xNjYtNC4wODcsNS41NzFjMC4wMDEtMC4wMDEsMC4wMDItMC4wMDEsMC4wMDMtMC4wMDJsNi4xOSw1LjIzOEMzNi45NzEsMzkuMjA1LDQ0LDM0LDQ0LDI0QzQ0LDIyLjY1OSw0My44NjIsMjEuMzUsNDMuNjExLDIwLjA4M3oiLz48L3N2Zz4="
)

_CSS_LOGIN = f"""
div[class*="st-key-login-panel"] {{ animation: login-fade-in 0.45s ease-out; }}
@keyframes login-fade-in {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; transform:translateY(0); }} }}

.login-divider {{ border-top:1px solid var(--borda); margin:0.9rem 0 1.6rem 0; }}

.login-hero {{ text-align:center; margin-bottom:1.5rem; }}
.login-titulo {{
    color:var(--neutro); font-weight:700; letter-spacing:0.03em;
    font-size:clamp(1.4rem, 3vw, 2.1rem); line-height:1.25; margin-bottom:0.6rem;
}}
.login-cursor {{ color:var(--destaque); animation:login-blink 1.1s step-end infinite; }}
@keyframes login-blink {{ 0%,49% {{ opacity:1; }} 50%,100% {{ opacity:0; }} }}
.login-subtitulo {{ color:var(--cinza); font-size:0.95rem; letter-spacing:0.01em; margin-bottom:0.5rem; }}
.login-micro {{ color:var(--cinza); font-size:0.72rem; letter-spacing:0.03em; opacity:0.8; }}

.login-tags {{
    display:flex; justify-content:center; flex-wrap:wrap; gap:0.35rem 1.1rem;
    margin:1.4rem 0 1.7rem 0;
}}
.login-tag {{ color:var(--cinza); font-size:0.68rem; letter-spacing:0.06em; white-space:nowrap; }}
.login-tag::before {{ content:"●"; color:var(--destaque); font-size:0.5rem; margin-right:0.45rem; vertical-align:middle; }}

.login-preview {{
    border:1px solid var(--borda); border-radius:2px; background:var(--painel-bg);
    padding:0.9rem 1.1rem 1rem 1.1rem; max-width:560px; margin:0 auto 1.7rem auto; position:relative;
}}
.login-preview-tag {{
    position:absolute; top:-0.55rem; left:50%; transform:translateX(-50%);
    background:var(--bg); color:var(--cinza); font-size:0.6rem; letter-spacing:0.08em;
    padding:0 0.5rem; white-space:nowrap;
}}
.login-preview-topo {{
    display:flex; justify-content:center; gap:1.8rem; padding-bottom:0.6rem;
    margin-bottom:0.6rem; border-bottom:1px solid var(--borda); font-size:0.78rem;
}}
.login-preview-topo b {{ color:var(--neutro); font-weight:600; margin-right:0.35rem; }}
.login-preview-grid {{
    display:grid; grid-template-columns:1fr 1fr; gap:0.4rem 1.5rem;
    margin-bottom:0.7rem; font-size:0.78rem;
}}
.login-preview-grid span {{ color:var(--neutro); font-weight:600; margin-right:0.4rem; }}
.login-preview-news-label {{
    color:var(--cinza); font-size:0.62rem; letter-spacing:0.06em; margin-bottom:0.25rem;
    border-top:1px solid var(--borda); padding-top:0.6rem;
}}
.login-preview-news div {{ color:var(--cinza); font-size:0.74rem; padding:0.12rem 0; opacity:0.85; }}

div[class*="st-key-login-google-btn"] {{ display:flex; justify-content:center; margin-bottom:0.6rem; }}
div[class*="st-key-login-google-btn"] button {{
    display:flex !important; align-items:center; justify-content:center; gap:0.6rem;
    width:100%; max-width:320px; min-height:48px;
    background-color:var(--painel-bg) !important; border:1px solid var(--borda) !important;
    color:var(--neutro) !important; font-weight:600 !important; font-size:0.85rem !important;
    letter-spacing:0.04em; border-radius:3px !important; box-shadow:none !important;
    transition:border-color 0.15s ease, background-color 0.15s ease;
}}
div[class*="st-key-login-google-btn"] button::before {{
    content:""; display:inline-block; width:18px; height:18px; flex:none;
    background-image:url("{_ICONE_GOOGLE}"); background-size:contain; background-repeat:no-repeat;
}}
div[class*="st-key-login-google-btn"] button:hover {{
    border-color:var(--destaque) !important; background-color:#111111 !important;
}}
.login-cta-micro {{ color:var(--cinza); font-size:0.7rem; text-align:center; }}
.login-cta-micro-sep {{ margin:0 0.4rem; opacity:0.5; }}

@media (max-width: 640px) {{
    .login-preview-topo {{ flex-wrap:wrap; gap:0.8rem 1.2rem; }}
    .login-preview-grid {{ grid-template-columns:1fr; }}
    .login-tags {{ gap:0.3rem 0.7rem; }}
}}
"""


def tela_apresentacao():
    """Tela exibida sem login: landing/apresentação do terminal, sem dados
    reais (a prévia do terminal é ilustrativa, rotulada como tal - ver
    PROGRESSO.md pra decisão de não buscar cotação real aqui: evita
    request de rede numa tela que qualquer visitante anônimo carrega)."""
    st.markdown(f"<style>{_CSS_LOGIN}</style>", unsafe_allow_html=True)
    st.markdown('<div class="pregao-logo">PREGÃO</div>', unsafe_allow_html=True)

    with st.container(border=True, key="login-panel"):
        st.markdown(
            """
            <div class="login-divider"></div>
            <div class="login-hero">
                <div class="login-titulo">SEU TERMINAL DE MERCADO.<span class="login-cursor">_</span></div>
                <div class="login-subtitulo">B3, macro, juros, notícias, research e CVM em um só lugar.</div>
                <div class="login-micro">DADOS PÚBLICOS · ATUALIZAÇÃO PERIÓDICA · 100% GRATUITO</div>
            </div>
            <div class="login-tags">
                <span class="login-tag">B3</span>
                <span class="login-tag">MACRO</span>
                <span class="login-tag">JUROS</span>
                <span class="login-tag">NEWS</span>
                <span class="login-tag">RESEARCH</span>
                <span class="login-tag">CVM</span>
            </div>
            <div class="login-preview">
                <div class="login-preview-tag">PRÉVIA ILUSTRATIVA</div>
                <div class="login-preview-topo">
                    <div><b>IBOVESPA</b><span class="cinza">183.399</span> <span class="baixa">-0,31%</span></div>
                    <div><b>DÓLAR</b><span class="cinza">5,20</span> <span class="alta">+0,66%</span></div>
                </div>
                <div class="login-preview-grid">
                    <div><span>PETR4</span><span class="baixa">-2,57%</span></div>
                    <div><span>VALE3</span><span class="baixa">-0,03%</span></div>
                    <div><span>ITUB4</span><span class="alta">+0,43%</span></div>
                    <div><span>JUROS (SELIC)</span><span class="neutro">14,75%</span></div>
                </div>
                <div class="login-preview-news-label">ÚLTIMAS NOTÍCIAS</div>
                <div class="login-preview-news">
                    <div>Petrobras divulga resultado do trimestre acima do esperado</div>
                    <div>Banco Central sinaliza manutenção da taxa de juros</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _, col, _ = st.columns([1, 1, 1])
        with col:
            if st.button("ENTRAR COM GOOGLE", width="stretch", key="login-google-btn"):
                st.login()

        st.markdown(
            """
            <div class="login-cta-micro">Acesso gratuito<span class="login-cta-micro-sep">·</span>
            Entre com sua conta Google para acessar o terminal.</div>
            """,
            unsafe_allow_html=True,
        )
