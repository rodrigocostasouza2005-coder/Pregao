# -*- coding: utf-8 -*-
"""Cobertura de ui/news_tab.py:_truncar - usada pra cortar manchete
(wire, limite 92) e teaser/resumo (limite 320) em varios pontos do feed
de NEWS. Achado real da auditoria 360 (2026-10-18,
docs/auditoria-redesign-360.md): o corte era por CONTAGEM DE CARACTERES
pura (texto[:limite-1]), sem respeitar fronteira de palavra - uma
manchete real cortava no meio de uma palavra (ex: "...aprovacao
unanime..." virava "...aprovacao u…"), ilegivel. O proprio docstring de
_teaser_card (mesmo arquivo) ja documentava a intencao de nunca cortar
no meio de uma frase "se nem a 1a frase sozinha couber" - cortar no meio
de uma PALAVRA e' pior ainda e nao era intencional."""
import ui.news_tab as news_tab_mod


def test_truncar_nao_corta_no_meio_de_uma_palavra():
    texto = (
        "Petrobras anuncia dividendo extraordinario de R$ 2 bilhoes para "
        "acionistas apos aprovacao unanime do conselho administrativo em reuniao"
    )
    resultado = news_tab_mod._truncar(texto, limite=92)
    assert resultado.endswith("…")
    sem_reticencias = resultado[:-1]
    assert not sem_reticencias.endswith(" ")
    ultima_palavra = sem_reticencias.rsplit(" ", 1)[-1]
    # a ultima palavra do resultado tem que ser uma palavra REAL do texto
    # original (nao um prefixo cortado no meio, ex: "u" de "unanime")
    assert ultima_palavra in texto.split(), f"corte no meio de palavra: {resultado!r}"


def test_truncar_texto_curto_nao_e_alterado():
    texto = "Manchete curta"
    assert news_tab_mod._truncar(texto, limite=92) == texto


def test_truncar_sem_nenhum_espaco_faz_corte_duro_sem_quebrar():
    """Token unico sem espaco (URL/hashtag longo) - nao ha' fronteira de
    palavra pra recuar, o corte duro continua sendo o unico jeito
    (melhor que devolver string vazia)."""
    texto = "x" * 150
    resultado = news_tab_mod._truncar(texto, limite=92)
    assert resultado.endswith("…")
    assert len(resultado) <= 92


def test_truncar_respeita_limite_customizado_do_teaser():
    texto = "Primeira frase bem completa aqui. " * 15
    resultado = news_tab_mod._truncar(texto, limite=320)
    assert len(resultado) <= 320
    assert resultado.endswith("…")
