# -*- coding: utf-8 -*-
"""Script DIAGNOSTICO TEMPORARIO (nao faz parte do app) - roda SO dentro do
workflow .github/workflows/_diag-btg-playwright.yml, em runner real do
GitHub Actions (ubuntu-latest, mesmo tipo de rede/IP que a producao usa),
pra responder com evidencia real (nao suposicao) se um Chromium headless
via Playwright consegue passar do desafio JS da Akamai que protege a API
de research do BTG Pactual, de forma ESTAVEL (varias tentativas).

NAO faz nenhuma evasao alem de rodar um navegador real headless (mesma
tecnica que o resto do projeto ja aceita via curl_cffi impersonate, s'o
que aqui com o navegador de verdade em vez de so' o fingerprint de TLS) -
nao usa proxy residencial, nao resolve captcha por servico terceiro, nao
falsifica nada alem do User-Agent padrao de um Chrome real.

Endpoints testados (identificados em sessao anterior, ver BACKLOG.md
secao Research):
- pagina publica que (acredita-se) consome a API via JS client-side:
  https://www.btgpactual.com/acoes/ultimos-relatorios
- API publica que respondeu (fora deste sandbox) quando testada
  isoladamente: .../media-research/.../medias/lives (lives)
- API que deu 404 na tentativa anterior (pode ser so' o endpoint errado,
  nao necessariamente bot-detection): .../ALL?pageNumber=1&pageSize=9

Saida: imprime 1 linha JSON por tentativa em stdout (visivel nos Logs do
Actions) - nunca inventa sucesso; se der excecao, registra a excecao."""

import json
import sys
import time

import requests
from playwright.sync_api import sync_playwright

PAGINA_RESEARCH = "https://www.btgpactual.com/acoes/ultimos-relatorios"
API_LIVES = (
    "https://content.btgpactual.com/api/research/public-router/media-research"
    "/api/media-research/public/v1/medias/lives?status=LIVE&pageNumber=1&pageSize=1"
)
API_ALL = (
    "https://content.btgpactual.com/api/research/public-router/media-research"
    "/api/media-research/public/v1/medias/ALL?pageNumber=1&pageSize=9"
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _tentativa(n: int, *, forcar_http1: bool, so_api: bool) -> dict:
    """`forcar_http1`: lanca o Chromium com --disable-http2 (1a rodada real
    deu net::ERR_HTTP2_PROTOCOL_ERROR - mesma familia de sintoma que
    genial.py ja documentou pro WAF da Genial; testa se forcar HTTP/1.1,
    que resolveu pra Genial, tambem resolve aqui). `so_api`: pula a
    navegacao na pagina www.btgpactual.com e chama as APIs (dominio
    content.btgpactual.com, separado) direto, sem passar por cookies/
    sensor nenhum - testa se o host da API reage diferente do host do
    site principal."""
    t0 = time.monotonic()
    chamadas_rede = []

    def _on_response(resp):
        if "public-router" in resp.url or "media-research" in resp.url:
            try:
                chamadas_rede.append({"url": resp.url, "status": resp.status})
            except Exception:
                pass

    resultado = {"tentativa": n, "forcar_http1": forcar_http1, "so_api": so_api}
    args = ["--disable-http2"] if forcar_http1 else []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=args)
            try:
                contexto = browser.new_context(user_agent=UA, locale="pt-BR")
                pagina = contexto.new_page()
                pagina.on("response", _on_response)

                if not so_api:
                    try:
                        pagina.goto(PAGINA_RESEARCH, wait_until="networkidle", timeout=30000)
                        resultado["pagina_status"] = "carregou"
                    except Exception as e:
                        resultado["pagina_erro"] = f"{type(e).__name__}: {e}"
                    resultado["chamadas_rede_observadas"] = chamadas_rede

                # tenta as 2 APIs diretamente DENTRO do mesmo contexto do
                # browser (mesmas cookies se a navegacao acima rodou, mesmo
                # TLS/HTTP de Chrome real - nao e' um client HTTP separado)
                for rotulo, url in (("lives", API_LIVES), ("all", API_ALL)):
                    try:
                        r = contexto.request.get(url, timeout=15000)
                        resultado[f"api_{rotulo}_status"] = r.status
                        resultado[f"api_{rotulo}_corpo_preview"] = r.text()[:200]
                    except Exception as e:
                        resultado[f"api_{rotulo}_erro"] = f"{type(e).__name__}: {e}"
            finally:
                browser.close()
    except Exception as e:
        resultado["erro_geral"] = f"{type(e).__name__}: {e}"

    resultado["duracao_s"] = round(time.monotonic() - t0, 1)
    return resultado


def _teste_plain_requests() -> dict:
    """2a rodada real confirmou api_lives_status=200 mesmo SEM navegador
    (so_api=True) - ou seja, essa API especifica pode nao ter bot-detection
    NENHUM. Testa aqui com `requests` puro (sem curl_cffi, sem Playwright -
    fingerprint de TLS padrao do Python) pra confirmar isso de vez: se
    passar, a conclusao e' que e' uma API publica comum, sem Akamai na
    frente, e Playwright/curl_cffi nem seriam necessarios pra ela. Tambem
    tenta 3 variacoes de path/params pra procurar um endpoint de LISTAGEM
    DE RELATORIOS ESCRITOS (nao lives) - a sessao anterior so' tinha
    adivinhado 'ALL' sem confirmar se e' o nome certo do recurso."""
    resultado = {}
    tentativas = {
        "lives_plain_requests": API_LIVES,
        "all_plain_requests": API_ALL,
        "medias_sem_segmento": (
            "https://content.btgpactual.com/api/research/public-router/media-research"
            "/api/media-research/public/v1/medias?pageNumber=1&pageSize=5"
        ),
        "medias_type_report": (
            "https://content.btgpactual.com/api/research/public-router/media-research"
            "/api/media-research/public/v1/medias?type=REPORT&pageNumber=1&pageSize=5"
        ),
        "medias_report_segmento": (
            "https://content.btgpactual.com/api/research/public-router/media-research"
            "/api/media-research/public/v1/medias/REPORT?pageNumber=1&pageSize=5"
        ),
    }
    for rotulo, url in tentativas.items():
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=15)
            resultado[rotulo] = {"status": r.status_code, "corpo_preview": r.text[:200]}
        except Exception as e:
            resultado[rotulo] = {"erro": f"{type(e).__name__}: {e}"}
    return resultado


if __name__ == "__main__":
    # bateria de hipoteses, nao so repeticao da mesma tentativa: (1) igual
    # a 1a rodada (controle), (2) forcando HTTP/1.1 (testa se o sintoma e'
    # igual ao da Genial, contornavel), (3)+(4) direto na API sem passar
    # pela home (testa se o host da API reage diferente do www).
    plano = [
        {"forcar_http1": False, "so_api": False},
        {"forcar_http1": True, "so_api": False},
        {"forcar_http1": False, "so_api": True},
        {"forcar_http1": True, "so_api": True},
    ]
    resultados = [_tentativa(i + 1, **cfg) for i, cfg in enumerate(plano)]
    for r in resultados:
        print("[diag-btg]", json.dumps(r, ensure_ascii=False))
    sucesso = any(r.get("api_lives_status") == 200 or r.get("api_all_status") == 200 for r in resultados)
    print(f"[diag-btg] RESUMO (playwright): sucesso_em_pelo_menos_1_tentativa={sucesso}")

    print("[diag-btg] (plain requests, sem Playwright/curl_cffi, procurando endpoint de relatorios)")
    print("[diag-btg]", json.dumps(_teste_plain_requests(), ensure_ascii=False))
    sys.exit(0)
