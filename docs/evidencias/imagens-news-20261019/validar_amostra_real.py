# -*- coding: utf-8 -*-
"""Validação de uma AMOSTRA REAL de fotos de notícias - somente leitura.

Roda o mesmo extrator e a mesma validação do coletor (data/news.py) contra
matérias reais do TOP MERCADO (Brasil + internacional), sem gravar nada no
Supabase e sem chamar IA. Gera:
  - amostra.csv  : título, veículo, URL da matéria, URL da imagem, status
  - amostra.html : título e foto lado a lado, pra conferência MANUAL
                   ("a foto é da matéria?") - HTTP 200 não basta.

Uso (de uma máquina com acesso à internet, a partir da raiz do repo):
    python docs/evidencias/imagens-news-20261019/validar_amostra_real.py --n 10 --saida /tmp/amostra-fotos

Educado com as fontes: 1 matéria por vez, no máximo 1 por veículo até
completar a amostra, os mesmos timeouts do coletor. Não contorna
bloqueios: página ou imagem bloqueada aparece como tal no relatório.
Não registra cookies, tokens nem query strings de imagem no CSV/HTML
além da própria URL pública da imagem."""
import argparse
import csv
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import data.news as news  # noqa: E402


def _amostra(n: int) -> list:
    grupos = []
    for coletar in (news.obter_top_mercado, news.obter_top_mercado_internacional):
        try:
            grupos.extend(coletar("TODOS") or [])
        except Exception as exc:
            print(f"coleta falhou: {type(exc).__name__}")
    escolhidos, vistos = [], set()
    for g in grupos:  # 1 por veículo primeiro (diversidade de fontes)
        veiculo = (g.get("veiculos") or ["?"])[0]
        if veiculo not in vistos:
            vistos.add(veiculo)
            escolhidos.append(g)
    for g in grupos:  # completa se faltar
        if len(escolhidos) >= n:
            break
        if g not in escolhidos:
            escolhidos.append(g)
    return escolhidos[:n]


def _avaliar(g: dict) -> dict:
    fontes = news._fontes_para_imagem(g, news.ordenar_fontes_para_resumo(g["fontes"]))
    linha = {"titulo": g["titulo"], "veiculo": (g.get("veiculos") or [""])[0], "url_materia": "",
             "url_imagem": "", "status": "", "motivo": ""}
    for _veiculo, link in fontes:
        _texto, imagem, link_real, motivo = news._extrair_texto_artigo(link)
        linha["url_materia"] = link_real or link
        linha["motivo"] = motivo or ""
        if not imagem:
            linha["status"] = "sem_imagem" if (motivo is None or "sem texto" in (motivo or "")) else "pagina_inacessivel"
            continue
        verificacao = news._verificar_imagem_url(imagem)
        linha["url_imagem"] = imagem
        linha["status"] = {news.IMAGEM_OK: "confirmada" if not news._url_assinada(imagem) else "nao_verificada(assinada)",
                           news.IMAGEM_ERRO_TEMPORARIO: "nao_verificada(bloqueio/temporario)",
                           news.IMAGEM_INVALIDA: "invalida"}[verificacao]
        if verificacao != news.IMAGEM_INVALIDA:
            break
    return linha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--saida", default="amostra-fotos")
    args = ap.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    grupos = _amostra(args.n)
    if not grupos:
        print("nenhuma notícia coletada - sem acesso ao Google News/fontes neste ambiente? Nada foi validado.")
        sys.exit(2)
    linhas = []
    for i, g in enumerate(grupos, 1):
        linha = _avaliar(g)
        linhas.append(linha)
        print(f"[{i}/{len(grupos)}] {linha['status']:<34} {linha['veiculo'][:20]:<20} {linha['titulo'][:60]}")

    repetidas = news._descartar_imagens_repetidas(
        [(i, l["titulo"], l["url_imagem"] or None, g.get("data")) for i, (l, g) in enumerate(zip(linhas, grupos))])
    for i in repetidas:
        linhas[i]["status"] = "generica_repetida"

    with open(saida / "amostra.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()) + ["foto_e_da_materia(preencher)"]) if linhas else None
        if w:
            w.writeheader()
            for l in linhas:
                w.writerow({**l, "foto_e_da_materia(preencher)": ""})

    cards = []
    for l in linhas:
        img = (f"<img src='{html.escape(l['url_imagem'])}' referrerpolicy='no-referrer'>"
               if l["url_imagem"] and l["status"] != "generica_repetida" else "<div class='sem'>sem foto</div>")
        cards.append(
            f"<div class='c'>{img}<div><b>{html.escape(l['titulo'])}</b><br>{html.escape(l['veiculo'])} · "
            f"<code>{html.escape(l['status'])}</code><br><a href='{html.escape(l['url_materia'])}' target='_blank'>"
            f"abrir matéria original</a></div></div>")
    (saida / "amostra.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Amostra de fotos</title><style>"
        "body{font-family:sans-serif;max-width:900px;margin:16px auto;padding:0 16px}"
        ".c{display:flex;gap:12px;border-bottom:1px solid #ccc;padding:10px 0}"
        ".c img,.sem{width:200px;height:112px;object-fit:cover;flex:0 0 200px;background:#eee}"
        ".sem{display:flex;align-items:center;justify-content:center;color:#888}</style>"
        "<h1>Amostra real — compare cada foto com a matéria original</h1>" + "".join(cards),
        encoding="utf-8")
    print(f"\nrelatório: {saida / 'amostra.csv'} e {saida / 'amostra.html'}")


if __name__ == "__main__":
    main()
