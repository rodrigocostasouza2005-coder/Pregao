# -*- coding: utf-8 -*-
"""DIAG TEMPORARIO (somente leitura, NAO MERGEAR): agrupamento e setor
antes x depois com o noticiario real. Sem secrets."""
import os, sys, copy
sys.path.insert(0, os.getcwd())
import data.news as n
import data.news_setores as ns

def itens_do_pool(entries):
    return [i for i in (n._montar_item_mercado(e, vf) for e, vf in entries.values()) if i]

def antigo():
    salvo = (n._TOKENS_MOVIMENTO, n._mesmo_numero_mesmo_assunto)
    # sem termos de movimento a exigencia de "conteudo em comum" vira
    # "qualquer token em comum" (sempre verdade quando a similaridade passa)
    n._TOKENS_MOVIMENTO = set(); n._mesmo_numero_mesmo_assunto = lambda g, i: False
    return salvo

for nome, fn in (("BR", n._coletar_pool_brasil), ("INT", n._coletar_pool_internacional)):
    entries, ok = fn("TODOS")
    itens = itens_do_pool(entries)
    novos = n._agrupar(copy.deepcopy(itens))
    salvo = antigo(); velhos = n._agrupar(copy.deepcopy(itens)); n._TOKENS_MOVIMENTO, n._mesmo_numero_mesmo_assunto = salvo
    print(f"\n===== {nome}: {len(itens)} itens | grupos antes {len(velhos)} depois {len(novos)}")
    chave = lambda g: tuple(sorted(g["titulos"]))
    sv, sn = {chave(g) for g in velhos}, {chave(g) for g in novos}
    print("-- grupos que so existem DEPOIS (juncoes novas ou separacoes):")
    for g in novos:
        if chave(g) not in sv and len(g["titulos"]) > 1:
            print("   +", " || ".join(t[:80] for t in g["titulos"][:5]))
    print("-- grupos multiplos que existiam ANTES e mudaram:")
    for g in velhos:
        if chave(g) not in sn and len(g["titulos"]) > 1:
            print("   -", " || ".join(t[:80] for t in g["titulos"][:5]))
    mudou = 0
    for g in novos:
        texto = " ".join(g["titulos"])
        tick = sorted({t for ti in g["titulos"] for t in n._tickers_no_titulo(ti)})
        novo = ns.classificar_setores(texto, tick)
        t = ns._sem_acento(texto)
        velho = [s for s, c in ns.SETORES.items() if any(ns._sem_acento(p) in t for p in c["palavras"]) or set(tick) & set(c["tickers"])]
        if novo != velho:
            mudou += 1
            if mudou <= 40:
                print(f"   setor {velho} -> {novo} | {g['titulo'][:90]}")
    print(f"-- grupos com setor diferente: {mudou}")
