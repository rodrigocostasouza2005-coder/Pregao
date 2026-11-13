# Dado mockado COMPARTILHADO pelos harnesses "antes"/"depois" de CARTEIRA
# RECOMENDADA - mesmo shape documentado em data/carteira_recomendada.py
# (montar_carteira_recomendada), representativo de uma rodada real do
# Comitê (8 ativos, 5 setores, 1 aviso de universo + 1 de correlação).
from datetime import datetime, timedelta, timezone

import pandas as pd

_AGORA = datetime.now(timezone.utc)


def carteira_mock() -> dict:
    itens = [
        {
            "ticker": "PETR4", "setor": "Petróleo e Gás", "peso_pct": 15.0,
            "justificativa": "Sinal COMPRA do Comitê (score 8, confiança ALTA).",
            "preco_referencia": 36.52, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 44.10, "metodo_preco_alvo": "consenso dos especialistas do Comitê",
            "cenarios": {
                "conservador": {"preco": 40.31, "retorno_pct": 10.4},
                "base": {"preco": 44.10, "retorno_pct": 20.8},
                "otimista": {"preco": 46.80, "retorno_pct": 28.1},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Geração de caixa robusta com Brent acima de US$ 85 e disciplina de capex sustentam o "
                    "dividendo; valuation ainda descontado vs. pares globais.",
            "riscos": ["Risco cambial pode pressionar margem em reais", "Interferência política em preços domésticos"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou se a tese resumida na análise não se confirmar até a data de revisão.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 42_300_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "ALTA", "sinal_comite": "COMPRA", "score_comite": 8,
            "origem_analise_id": "a1b2c3", "origem_analise_em": (_AGORA - timedelta(hours=10)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "WEGE3", "setor": "Bens de Capital e Industrial", "peso_pct": 15.0,
            "justificativa": "Sinal COMPRA do Comitê (score 7, confiança ALTA).",
            "preco_referencia": 54.30, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 61.20, "metodo_preco_alvo": "modelo interno do Comitê (DCF)",
            "cenarios": {
                "conservador": {"preco": 57.75, "retorno_pct": 6.4},
                "base": {"preco": 61.20, "retorno_pct": 12.7},
                "otimista": {"preco": 63.50, "retorno_pct": 16.9},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Crescimento consistente de receita internacional e margens resilientes, múltiplo premium "
                    "justificado pelo histórico de execução.",
            "riscos": ["Múltiplo já elevado reduz margem de segurança"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou se a tese resumida na análise não se confirmar até a data de revisão.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 8_100_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "ALTA", "sinal_comite": "COMPRA", "score_comite": 7,
            "origem_analise_id": "d4e5f6", "origem_analise_em": (_AGORA - timedelta(hours=9)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "ITUB4", "setor": "Bancos e Serviços Financeiros", "peso_pct": 15.0,
            "justificativa": "Sinal COMPRA do Comitê (score 7, confiança ALTA).",
            "preco_referencia": 34.21, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 39.80, "metodo_preco_alvo": "consenso dos especialistas do Comitê",
            "cenarios": {
                "conservador": {"preco": 37.0, "retorno_pct": 8.2},
                "base": {"preco": 39.80, "retorno_pct": 16.3},
                "otimista": {"preco": 41.50, "retorno_pct": 21.3},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "ROE consistente acima de pares, inadimplência controlada e carteira de crédito diversificada.",
            "riscos": [],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou se a tese resumida na análise não se confirmar até a data de revisão.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 31_400_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "ALTA", "sinal_comite": "COMPRA", "score_comite": 7,
            "origem_analise_id": "g7h8i9", "origem_analise_em": (_AGORA - timedelta(hours=8)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "PRIO3", "setor": "Petróleo e Gás", "peso_pct": 13.0,
            "justificativa": "Sinal COMPRA do Comitê (score 6, confiança MEDIA).",
            "preco_referencia": 42.10, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 48.0, "metodo_preco_alvo": "modelo interno do Comitê (DCF)",
            "cenarios": {
                "conservador": {"preco": 45.05, "retorno_pct": 7.0},
                "base": {"preco": 48.0, "retorno_pct": 14.0},
                "otimista": {"preco": 50.20, "retorno_pct": 19.2},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Produção crescente via aquisições de campos maduros, custo de extração competitivo.",
            "riscos": ["Histórico curto de execução integrada dos ativos adquiridos"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou antes disso - a confiança atual já é MEDIA.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 5_600_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "MEDIA", "sinal_comite": "COMPRA", "score_comite": 6,
            "origem_analise_id": "j1k2l3", "origem_analise_em": (_AGORA - timedelta(hours=7)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "BBAS3", "setor": "Bancos e Serviços Financeiros", "peso_pct": 13.0,
            "justificativa": "Sinal COMPRA do Comitê (score 6, confiança MEDIA).",
            "preco_referencia": 28.40, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 32.50, "metodo_preco_alvo": "consenso dos especialistas do Comitê",
            "cenarios": {
                "conservador": {"preco": 30.45, "retorno_pct": 7.2},
                "base": {"preco": 32.50, "retorno_pct": 14.4},
                "otimista": {"preco": 34.0, "retorno_pct": 19.7},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Dividend yield elevado e carteira agro resiliente, mas rentabilidade ainda abaixo de bancos privados.",
            "riscos": ["Ingerência política histórica em bancos públicos", "ROE abaixo de ITUB4/BBDC4"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou antes disso - a confiança atual já é MEDIA.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 18_900_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "MEDIA", "sinal_comite": "COMPRA", "score_comite": 6,
            "origem_analise_id": "m4n5o6", "origem_analise_em": (_AGORA - timedelta(hours=6)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "ABEV3", "setor": "Bebidas", "peso_pct": 12.0,
            "justificativa": "Sinal COMPRA do Comitê (score 5, confiança MEDIA).",
            "preco_referencia": 12.80, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 14.30, "metodo_preco_alvo": "preço-alvo por P/L setorial",
            "cenarios": {
                "conservador": {"preco": 13.55, "retorno_pct": 5.9},
                "base": {"preco": 14.30, "retorno_pct": 11.7},
                "otimista": {"preco": 14.30, "retorno_pct": 11.7},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Geração de caixa defensiva e dividend yield consistente em cenário de juros ainda altos.",
            "riscos": ["Volume doméstico pressionado por concorrência de cervejarias regionais"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou antes disso - a confiança atual já é MEDIA.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 22_100_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "MEDIA", "sinal_comite": "COMPRA", "score_comite": 5,
            "origem_analise_id": "p7q8r9", "origem_analise_em": (_AGORA - timedelta(hours=5)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "SUZB3", "setor": "Papel e Celulose", "peso_pct": 9.0,
            "justificativa": "Sinal COMPRA do Comitê (score 5, confiança BAIXA).",
            "preco_referencia": 48.90, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": None, "metodo_preco_alvo": None,
            "cenarios": None,
            "tese": "Exposição a celulose de fibra curta com custo competitivo, mas sem preço-alvo confiável "
                    "do Comitê nesta rodada.",
            "riscos": ["Preço internacional de celulose em queda", "Câmbio pode reverter rapidamente a vantagem de custo"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou antes disso - a confiança atual já é BAIXA, revisão prioritária "
                               "na próxima rodada do Comitê.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 9_800_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "BAIXA", "sinal_comite": "COMPRA", "score_comite": 5,
            "origem_analise_id": "s1t2u3", "origem_analise_em": (_AGORA - timedelta(hours=4)).isoformat(),
            "historico_alteracao": [],
        },
        {
            "ticker": "B3SA3", "setor": "Bancos e Serviços Financeiros", "peso_pct": 8.0,
            "justificativa": "Sinal COMPRA do Comitê (score 4, confiança BAIXA).",
            "preco_referencia": 11.75, "preco_referencia_em": (_AGORA - timedelta(hours=2)).isoformat(),
            "preco_alvo": 13.0, "metodo_preco_alvo": "modelo interno do Comitê (DCF)",
            "cenarios": {
                "conservador": {"preco": 12.38, "retorno_pct": 5.3},
                "base": {"preco": 13.0, "retorno_pct": 10.6},
                "otimista": {"preco": 13.0, "retorno_pct": 10.6},
                "aviso": "Cenários condicionais sobre o preço-alvo já calculado pelo Comitê de Investimentos - "
                         "nunca é retorno garantido nem previsão de probabilidade.",
            },
            "tese": "Volume de negociação em recuperação, mas concorrência de novas plataformas é risco estrutural.",
            "riscos": ["Risco regulatório/concorrencial de novas plataformas de negociação"],
            "criterio_saida": "Reavaliar a posição se o Comitê rebaixar o sinal deste ativo para NEUTRO ou VENDA "
                               "na próxima rodada, ou antes disso - a confiança atual já é BAIXA, revisão prioritária "
                               "na próxima rodada do Comitê.",
            "data_revisao": (_AGORA + timedelta(days=30)).date().isoformat(),
            "liquidez": {"volume": 27_300_000, "consultado_em": (_AGORA - timedelta(hours=2)).isoformat()},
            "confianca_comite": "BAIXA", "sinal_comite": "COMPRA", "score_comite": 4,
            "origem_analise_id": "v4w5x6", "origem_analise_em": (_AGORA - timedelta(hours=3)).isoformat(),
            "historico_alteracao": [],
        },
    ]

    diversificacao = {}
    for item in itens:
        if item["setor"]:
            diversificacao[item["setor"]] = round(diversificacao.get(item["setor"], 0.0) + item["peso_pct"], 2)

    resumo = {
        "n_ativos": len(itens),
        "peso_total_pct": round(sum(i["peso_pct"] for i in itens), 2),
        "diversificacao_setorial": diversificacao,
        "setores_cobertos": len(diversificacao),
        "concentracao_maxima_pct": 15.0,
        "horizonte": "Suposição declarada, não um dado do Comitê: horizonte médio/longo prazo.",
        "correlacao": None,
        "cenario_macro": {
            "selic_meta": pd.DataFrame({"selic_meta_pct": [15.0, 15.0, 14.75, 14.75, 14.5]}),
            "cdi": pd.DataFrame({"cdi_anualizado_pct": [14.9, 14.9, 14.85, 14.85, 14.8]}),
            "focus_ipca": pd.DataFrame({"ano_referencia": [2026, 2027, 2028], "mediana_pct": [4.6, 4.1, 3.8], "media_pct": [4.6, 4.1, 3.8]}),
        },
    }

    return {
        "gerado_em": _AGORA.isoformat(),
        "criterios": {},
        "itens": itens,
        "resumo": resumo,
        "avisos": [
            "Carteira recomendada informativa - NÃO constitui recomendação de investimento personalizada "
            "nem garante rentabilidade; cenários são condicionais.",
            "Universo considerado: 37 tickers com análise CONCLUIDA mais recente dentre as últimas 500 "
            "análises do Comitê.",
            "GAP conhecido: não existe hoje no projeto um motor de correlação entre ativos. Não preenchido "
            "com número nesta missão para não inventar dado - aparece como None/ausente em todas as saídas.",
        ],
        "fonte_universo": "Comitê de Investimentos (jobs/comite_noturno.py) via coordenador_analises.",
        "universo_consultado": 37,
        "universo_elegivel": 14,
    }


def historico_mock() -> list:
    return [
        {"ticker": "PETR4", "campo": "peso_pct", "valor_anterior": "12.0", "valor_novo": "15.0",
         "motivo": "Score do Comitê subiu de 7 para 8 na rodada de 12/11.",
         "registrado_em": (_AGORA - timedelta(days=1)).isoformat()},
        {"ticker": "MGLU3", "campo": "itens", "valor_anterior": "incluído", "valor_novo": "removido",
         "motivo": "Comitê rebaixou o sinal para VENDA na rodada de 10/11.",
         "registrado_em": (_AGORA - timedelta(days=3)).isoformat()},
        {"ticker": "SUZB3", "campo": "itens", "valor_anterior": "—", "valor_novo": "incluído",
         "motivo": "Novo sinal COMPRA do Comitê (score 5) na rodada de 08/11.",
         "registrado_em": (_AGORA - timedelta(days=5)).isoformat()},
    ]
