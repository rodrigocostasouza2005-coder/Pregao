# -*- coding: utf-8 -*-
"""Testes do gate de fidelidade de resumo de research (data/research/
qualidade.py) - Fase 4 da missão RESEARCH institucional (2026-10-23).
100% determinístico, sem rede nem IA - usa pares (texto original,
resumo) representativos, tanto fiéis quanto quebrados de propósito.

Uso: pytest tests/test_research_qualidade.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.research import qualidade

_TEXTO_ORIGINAL_PETR4 = (
    "A Petrobras divulgou lucro líquido de R$ 12,50 bilhões no terceiro trimestre, "
    "alta de 8% frente ao mesmo período do ano anterior. A companhia elevou o "
    "preço-alvo de PETR4 para R$ 48,00, mantendo recomendação de compra. O resultado "
    "foi impulsionado por maior produção no pré-sal e preços do petróleo mais altos."
)


def test_resumo_fiel_passa_sem_nenhum_problema():
    resumo = (
        "A Petrobras reportou lucro líquido de R$ 12,50 bilhões no 3T, alta de 8% "
        "frente ao ano anterior, impulsionado por maior produção no pré-sal. "
        "O preço-alvo de PETR4 foi elevado para R$ 48,00."
    )
    assert qualidade.validar_fidelidade(resumo, _TEXTO_ORIGINAL_PETR4, "Petrobras eleva produção") is None


def test_numero_inventado_no_resumo_e_rejeitado():
    resumo = "A Petrobras reportou lucro recorde de R$ 99,90 bilhões no trimestre."
    motivo = qualidade.validar_fidelidade(resumo, _TEXTO_ORIGINAL_PETR4)
    assert motivo is not None
    assert "99,90" in motivo or "99.90" in motivo


def test_numero_com_formatacao_diferente_mas_mesmo_valor_nao_e_rejeitado():
    """48.00 (ponto) vs R$ 48,00 (vírgula) no original - mesmo valor,
    formatação diferente, nunca deveria disparar o gate."""
    resumo = "O preço-alvo de PETR4 foi elevado para R$ 48.00."
    assert qualidade.numeros_sem_base(resumo, _TEXTO_ORIGINAL_PETR4) == []


def test_percentual_inventado_e_rejeitado():
    resumo = "A Petrobras reportou crescimento de 45% na receita."
    nums = qualidade.numeros_sem_base(resumo, _TEXTO_ORIGINAL_PETR4)
    assert any("45" in n for n in nums)


def test_ticker_inventado_sem_base_e_rejeitado():
    resumo = "O resultado da Petrobras também beneficia VALE3, que deve subir."
    tickers = qualidade.tickers_sem_base(resumo, _TEXTO_ORIGINAL_PETR4, "Petrobras eleva produção")
    assert tickers == ["VALE3"]


def test_ticker_citado_no_titulo_mas_nao_no_corpo_nao_e_rejeitado():
    resumo = "WEGE3 reportou lucro em linha com o esperado."
    tickers = qualidade.tickers_sem_base(resumo, "texto sem o ticker", titulo="WEGE3: resultado do trimestre")
    assert tickers == []


def test_causalidade_sem_evidencia_e_rejeitada():
    resumo = (
        "A Petrobras reportou lucro de R$ 12,50 bilhões, impulsionado por uma "
        "reforma tributária aprovada no Congresso."
    )
    motivo = qualidade.causalidade_sem_evidencia(resumo, _TEXTO_ORIGINAL_PETR4)
    assert motivo is not None
    assert "reforma tributária" in motivo


def test_causalidade_com_evidencia_real_nao_e_rejeitada():
    resumo = "O lucro foi impulsionado por maior produção no pré-sal."
    assert qualidade.causalidade_sem_evidencia(resumo, _TEXTO_ORIGINAL_PETR4) is None


def test_causalidade_com_clausula_curta_demais_nao_bloqueia():
    """Clausula com so' 1 palavra de conteudo (depois de remover termos
    genericos) nao e' avaliavel com confianca - nunca bloqueia por isso
    (mesmo principio conservador de data/news.py)."""
    resumo = "O resultado veio em meio ao cenário."
    assert qualidade.causalidade_sem_evidencia(resumo, _TEXTO_ORIGINAL_PETR4) is None


def test_validar_fidelidade_prioriza_numero_sobre_ticker_sobre_causalidade():
    """Garante a ordem documentada: numero reprovado aparece primeiro,
    mesmo que o resumo tambem tenha ticker/causalidade sem base."""
    resumo = "A Petrobras reportou R$ 999,00 bilhões, beneficiando também VALE3."
    motivo = qualidade.validar_fidelidade(resumo, _TEXTO_ORIGINAL_PETR4, "Petrobras")
    assert "número" in motivo


def test_resumo_vazio_nao_quebra():
    assert qualidade.validar_fidelidade("", _TEXTO_ORIGINAL_PETR4) is None
    assert qualidade.validar_fidelidade(None, _TEXTO_ORIGINAL_PETR4) is None


def test_texto_original_vazio_reprova_qualquer_numero_do_resumo():
    """Sem texto original nenhum pra comparar, qualquer numero citado no
    resumo fica sem base por definicao - gate conservador, nunca aceita
    'confia em mim' sem evidencia."""
    resumo = "O preço-alvo foi fixado em R$ 48,00."
    motivo = qualidade.validar_fidelidade(resumo, "")
    assert motivo is not None


# ============================================================
# Separador de milhar (achado real, auditoria de integração
# 2026-10-23): "." e "," juntos no mesmo número seguem a convenção BR
# sem ambiguidade (ponto = milhar, vírgula = decimal) - antes deste
# fix, um resumo fiel que só reformatava "R$ 1.234,56" pra "R$ 1234,56"
# (mesmo valor, sem separador de milhar - reformatação plausível de um
# LLM) era reprovado e descartado inteiro.
# ============================================================

_TEXTO_ORIGINAL_COM_MILHAR = (
    "A empresa reportou receita de R$ 1.234,56 milhões no trimestre, dentro do esperado."
)


def test_numero_sem_separador_de_milhar_mas_mesmo_valor_nao_e_rejeitado():
    resumo = "A receita somou R$ 1234,56 milhões no trimestre."
    assert qualidade.numeros_sem_base(resumo, _TEXTO_ORIGINAL_COM_MILHAR) == []


def test_numero_com_separador_de_milhar_identico_ao_original_nao_e_rejeitado():
    resumo = "A receita somou R$ 1.234,56 milhões no trimestre."
    assert qualidade.numeros_sem_base(resumo, _TEXTO_ORIGINAL_COM_MILHAR) == []


def test_valor_realmente_diferente_com_separador_de_milhar_continua_rejeitado():
    """O fix não deve abrir brecha pra número genuinamente inventado só
    por ele também ter separador de milhar."""
    resumo = "A receita somou R$ 9.999,99 milhões no trimestre."
    nums = qualidade.numeros_sem_base(resumo, _TEXTO_ORIGINAL_COM_MILHAR)
    assert any("9.999,99" in n for n in nums)


def test_validar_fidelidade_completo_aceita_resumo_fiel_com_reformatacao_de_milhar():
    resumo = "A empresa reportou receita de R$ 1234,56 milhões no trimestre, dentro do esperado."
    assert qualidade.validar_fidelidade(resumo, _TEXTO_ORIGINAL_COM_MILHAR) is None


# ============================================================
# Limitação conhecida (achado real, auditoria de integração
# 2026-10-23, NÃO corrigida nesta mudança - registrada deliberadamente
# como teste de regressão do comportamento atual, não de requisito
# desejado): o gate verifica só se o número aparece EM ALGUM LUGAR do
# texto original, não se está associado à MESMA métrica/assunto. Um
# número real do texto, citado pelo resumo mas atribuído a uma métrica
# diferente da que ele realmente descreve, passa sem ser detectado.
# Resolver isso exigiria comparar proximidade número↔sujeito no texto
# original, mudança maior fora do escopo deste PR (só o bug do
# separador de milhar acima foi corrigido de verdade).
# ============================================================

def test_numero_real_mas_atribuido_a_metrica_errada_nao_e_pego_limitacao_conhecida():
    original = (
        "A Petrobras reportou margem bruta de 42% e crescimento de receita de 8% "
        "no trimestre. O lucro líquido cresceu 15% no ano."
    )
    # 8% e' um numero real do texto (crescimento de RECEITA), mas o
    # resumo abaixo o atribui ao LUCRO (que na verdade cresceu 15%) -
    # o gate hoje NAO pega isso, porque so' verifica presenca do numero
    # em algum lugar do original, nao a metrica a que ele se refere.
    resumo = "O lucro da Petrobras cresceu 8% no trimestre, superando as expectativas do mercado."
    assert qualidade.validar_fidelidade(resumo, original) is None
