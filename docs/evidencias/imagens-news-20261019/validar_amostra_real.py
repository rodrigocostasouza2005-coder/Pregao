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
além da própria URL pública da imagem.

SOMENTE LEITURA, garantido no próprio script (_isolar_de_producao): o
cliente Supabase fica desligado (a coleta do TOP MERCADO chamaria
registrar_tentativa, que GRAVA em coletores_status), o registro de status
vira no-op e qualquer chamada de IA levanta erro. Nada de e-mail.

Classificação: nenhum status automático é "correto". Foto validada por
rede vira "pendente_inspecao_visual" - quem decide correto/incorreto é a
pessoa, comparando com a matéria original. Depois de preencher a coluna
"classificacao" do CSV (correto | incorreto | bloqueado | sem_imagem |
inconclusivo):
    python docs/evidencias/imagens-news-20261019/validar_amostra_real.py --apurar /tmp/amostra-fotos/amostra.csv
A taxa de correspondência é calculada SÓ sobre correto + incorreto."""
import argparse
import csv
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import data.coletores_status as coletores_status  # noqa: E402
import data.news as news  # noqa: E402
import data.supabase_client as supabase_client  # noqa: E402

CLASSES_VALIDAS = ("correto", "incorreto", "bloqueado", "sem_imagem", "inconclusivo")

# status automático -> classificação inicial (NUNCA "correto")
_CLASSIFICACAO_INICIAL = {
    "confirmada": "pendente_inspecao_visual",
    "nao_verificada(assinada)": "pendente_inspecao_visual",
    "nao_verificada(bloqueio/temporario)": "bloqueado",
    "pagina_inacessivel": "bloqueado",
    "sem_imagem": "sem_imagem",
    "invalida": "sem_imagem",
    "generica_repetida": "sem_imagem",
}


def _isolar_de_producao():
    """Garante leitura pura mesmo numa máquina com SUPABASE_* / GROQ_API_KEY
    configurados: sem cliente Supabase (obter_cliente devolve None em todos
    os módulos, que importam a MESMA função), sem registro de status e
    com a IA bloqueada."""
    supabase_client.create_client = None
    try:
        supabase_client.obter_cliente.clear()
    except Exception:
        pass

    def _sem_registro(*_a, **_k):
        return None

    def _sem_ia(*_a, **_k):
        raise RuntimeError("validar_amostra_real: chamada de IA bloqueada (script somente leitura)")

    news.registrar_tentativa = _sem_registro
    coletores_status.registrar_tentativa = _sem_registro
    news._chamar_groq = _sem_ia


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
            # página baixada sem foto confiável = sem_imagem; qualquer falha de
            # download (401/403, timeout, conexão, link do Google News não
            # resolvido) = pagina_inacessivel -> "bloqueado", nunca "correto"
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


def apurar(caminho_csv) -> dict:
    """Taxa de correspondência a partir do CSV PREENCHIDO à mão. Só
    correto + incorreto entram no denominador; pendências bloqueiam a
    apuração (nunca contam como correto)."""
    with open(caminho_csv, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    contagem = {c: 0 for c in CLASSES_VALIDAS}
    pendentes = []
    for i, l in enumerate(linhas, 1):
        c = (l.get("classificacao") or "").strip().lower()
        if c in contagem:
            contagem[c] += 1
        else:
            pendentes.append(i)
    verificados = contagem["correto"] + contagem["incorreto"]
    taxa = (contagem["correto"] / verificados) if verificados else None
    return {"total": len(linhas), "contagem": contagem, "verificados": verificados,
            "taxa_correspondencia": taxa, "linhas_sem_classificacao_final": pendentes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--saida", default="amostra-fotos")
    ap.add_argument("--apurar", metavar="CSV", help="calcula a taxa a partir do CSV já classificado à mão")
    args = ap.parse_args()
    if args.apurar:
        r = apurar(args.apurar)
        print(r)
        if r["linhas_sem_classificacao_final"]:
            print(f"linhas ainda sem classificação final: {r['linhas_sem_classificacao_final']} - apuração incompleta")
            sys.exit(3)
        if r["taxa_correspondencia"] is None:
            print("nenhum caso efetivamente verificado (correto/incorreto) - taxa indefinida")
        else:
            print(f"taxa de correspondência: {r['taxa_correspondencia']:.0%} "
                  f"({r['contagem']['correto']}/{r['verificados']} verificados)")
        return
    _isolar_de_producao()
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

    for l in linhas:
        l["classificacao"] = _CLASSIFICACAO_INICIAL.get(l["status"], "inconclusivo")
        l["observacao"] = ""

    with open(saida / "amostra.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    contagem = {}
    for l in linhas:
        contagem[l["classificacao"]] = contagem.get(l["classificacao"], 0) + 1
    print(f"\nclassificação inicial: {contagem}")
    print("Nenhum caso é 'correto' até a inspeção visual: troque cada 'pendente_inspecao_visual' do CSV por "
          "correto/incorreto/inconclusivo e rode --apurar.")

    cards = []
    for l in linhas:
        img = (f"<img src='{html.escape(l['url_imagem'])}' referrerpolicy='no-referrer' "
               "onerror=\"this.outerHTML='<div class=sem>não carregou no navegador (bloqueado?)</div>'\">"
               if l["url_imagem"] and l["status"] != "generica_repetida" else "<div class='sem'>sem foto</div>")
        cards.append(
            f"<div class='c'>{img}<div><b>{html.escape(l['titulo'])}</b><br>{html.escape(l['veiculo'])} · "
            f"<code>{html.escape(l['status'])}</code> → <b>{html.escape(l['classificacao'])}</b><br>"
            f"<a href='{html.escape(l['url_materia'])}' target='_blank'>"
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
