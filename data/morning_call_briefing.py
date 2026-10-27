# -*- coding: utf-8 -*-
"""Camada de dados do BRIEFING do Morning Call (ui/morning_call_tab.py).

Preenche só o que faltava pra aba virar um briefing acionável - sem
coletor novo, sem chamada de IA nova, sem sistema de monitoramento
novo. O briefing já reusa diretamente (sem passar por aqui):
data/sintese_mercado.py:obter_sintese_mercado() (resumo executivo,
movimentos, oportunidades/riscos, cenários, o que observar - mesmo
motor de IA já usado pela VISÃO GERAL) e
data/morning_call_editorial.py:montar_edicao() (agenda, teses de
research, notícias, radar setorial).

Este módulo só cobre o que nenhum dos dois acima já fazia:
- alertas_confiabilidade(): leitura filtrada do painel SAÚDE DOS DADOS
  já existente (data/saude_dados.py:obter_painel_saude) - nunca
  reimplementa classificação de estado nem persiste nada novo.
- tickers_novos(): comparação textual simples (sem rede, sem IA) entre
  os tickers já coletados pela edição de hoje e o texto da última
  edição publicada por e-mail.

Sem import de streamlit de propósito (mesmo padrão de
data/morning_call_editorial.py) - testável com pytest puro; decisões
de cache ficam na camada de UI."""
import re

# Categorias do painel SAÚDE DOS DADOS (data/saude_dados.py:
# REGISTRO_COLETORES) que alimentam o Morning Call. "Cotacoes" fica de
# fora de propósito: uma cotação indisponível já tem aviso próprio por
# indicador (data/morning_call_editorial.py:_indicador, campo "erro") -
# listar a mesma falha aqui duplicaria o sinal em 2 lugares da mesma
# edição. "Fundamentos"/"Earnings" também ficam de fora - não são
# consumidos pelo Morning Call (Equity/Earnings Reviewer são áreas
# próprias, nunca absorvidas aqui, ver missão).
_CATEGORIAS_RELEVANTES = {"Noticias", "Macro", "CVM", "Research", "Calendario", "Radar", "Morning Call"}


def alertas_confiabilidade() -> list:
    """Linhas do painel SAÚDE DOS DADOS (obter_painel_saude, já
    existente) com alerta=True nas categorias que alimentam o Morning
    Call - leitura pura, nunca uma classificação nova (ver
    data/saude_dados.py:classificar_estado/_ESTADOS_ALERTA, única fonte
    de verdade sobre o que é "alerta"). [] se nada estiver em alerta ou
    o painel/banco estiver indisponível (obter_painel_saude já degrada
    pra NAO_COMPROVADO/erro sem lançar excecao - este wrapper nunca
    propaga exceção de volta pro Morning Call)."""
    from data.saude_dados import obter_painel_saude

    try:
        painel = obter_painel_saude()
    except Exception as exc:
        print(f"[morning_call_briefing] painel de saúde indisponível: {exc!r}")
        return []
    return [
        item for item in (painel or [])
        if item.get("alerta") and item.get("categoria") in _CATEGORIAS_RELEVANTES
    ]


def tickers_novos(edicao: dict, ultima_publicada: dict | None) -> list:
    """Tickers citados HOJE (edicao['market_makers']['tickers'], já
    coletados por montar_edicao - nenhuma consulta nova) que não
    apareciam no TEXTO da última edição publicada por e-mail
    (comparação textual simples, \\b-delimitada - nunca reconsulta
    nenhuma fonte nem tenta inferir "o que mudou" na tese em si, só
    presença/ausência do ticker no texto anterior). [] quando não há
    base de comparação (sem mm.tickers nesta edição, ou nenhuma edição
    anterior publicada ainda) - nunca inventa uma novidade."""
    mm = (edicao or {}).get("market_makers") or {}
    tickers_hoje = mm.get("tickers") or ()
    texto_anterior = (ultima_publicada or {}).get("conteudo") or ""
    if not tickers_hoje or not texto_anterior:
        return []
    return [t for t in tickers_hoje if not re.search(rf"\b{re.escape(t)}\b", texto_anterior)]
