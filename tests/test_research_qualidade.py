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


# ---------------------------------------------------------------------
# PROBLEMA 1 (revisão técnica, 2026-10-23): falso positivo de formatação
# numérica - "R$ 1.234,56 milhões" (original) x "R$ 1234,56 milhões"
# (resumo) eram tratados como números DIFERENTES (separador de milhar
# ausente no resumo). _normalizar_numero agora resolve ponto-de-milhar
# vs decimal pelo ÚLTIMO separador presente quando os DOIS tipos
# aparecem no mesmo número - ver docstring da função.
# ---------------------------------------------------------------------

def test_br_com_separador_de_milhar_bate_com_br_sem_separador():
    original = "A companhia reportou receita de R$ 1.234,56 milhões no trimestre."
    resumo = "A receita somou R$ 1234,56 milhões no trimestre."
    assert qualidade.numeros_sem_base(resumo, original) == []


def test_decimal_com_virgula_bate_com_decimal_com_ponto():
    assert qualidade.numeros_sem_base("margem de 15,5%", "margem de 15.5% no período") == []


def test_valor_monetario_milhoes_bate_independente_do_separador():
    original = "lucro líquido de R$ 2.500.000,75"
    resumo = "lucro líquido de R$ 2500000,75"
    assert qualidade.numeros_sem_base(resumo, original) == []


def test_percentual_negativo_bate_com_percentual_negativo_no_original():
    original = "o indicador recuou -3,2% no período"
    resumo = "o indicador caiu -3,2% no período"
    assert qualidade.numeros_sem_base(resumo, original) == []


def test_numero_negativo_nunca_bate_com_o_mesmo_numero_positivo():
    """Bug relacionado corrigido junto: a regex antiga nem capturava o
    sinal - um resumo que invertesse alta/queda mantendo a magnitude
    passava batido. Agora o sinal faz parte da chave de comparação."""
    original = "o indicador avançou 3,2% no período"
    resumo = "o indicador recuou -3,2% no período"
    assert qualidade.numeros_sem_base(resumo, original) != []


def test_valor_monetario_negativo_e_reconhecido_e_comparado():
    original = "a empresa registrou prejuízo de R$ -50,00 milhões"
    resumo_fiel = "o prejuízo foi de R$ -50,00 milhões"
    resumo_sinal_trocado = "o lucro foi de R$ 50,00 milhões"
    assert qualidade.numeros_sem_base(resumo_fiel, original) == []
    assert qualidade.numeros_sem_base(resumo_sinal_trocado, original) != []


def test_valores_genuinamente_diferentes_continuam_rejeitados():
    """Garante que a correção do separador de milhar NAO vira uma
    validação frouxa - 1.234,56 (original) e 1.235,56 (resumo) são
    valores DIFERENTES de verdade, tem que continuar reprovando."""
    original = "receita de R$ 1.234,56 milhões"
    resumo = "receita de R$ 1.235,56 milhões"
    assert qualidade.numeros_sem_base(resumo, original) != []


def test_caso_ambiguo_1_ponto_isolado_continua_conservador():
    """Numero com SO' 1 separador tipo '.' isolado (sem virgula em
    nenhum dos dois lados pra desambiguar) continua tratado como decimal
    (nao vira milhar por suposicao) - mesmo comportamento conservador de
    antes da correcao, nunca mudou pra esse caso."""
    original = "o indicador fechou em R$ 4.850 no período"
    resumo_mesmo_valor_decimal = "o indicador fechou em R$ 4.850 no período"
    resumo_outro_valor = "o indicador fechou em R$ 4850 no período"
    assert qualidade.numeros_sem_base(resumo_mesmo_valor_decimal, original) == []
    # "4850" (sem separador) normaliza como inteiro 4850, DIFERENTE da
    # leitura conservadora de "4.850" como decimal (4,85) - sem a 2a
    # pista (virgula) em nenhum lado, o gate nao arrisca equiparar.
    assert qualidade.numeros_sem_base(resumo_outro_valor, original) != []


# ---------------------------------------------------------------------
# PROBLEMA 2 (revisão técnica, 2026-10-23): falso negativo de atribuição
# - número existe no original, mas colado numa métrica ERRADA no resumo
# (numeros_com_metrica_trocada).
# ---------------------------------------------------------------------

_TEXTO_MULTI_METRICA = (
    "A companhia reportou margem bruta de 42%, com crescimento do lucro líquido "
    "de 15% frente ao trimestre anterior, enquanto a receita líquida cresceu 8% "
    "no período."
)


def test_atribuicao_errada_e_detectada_numero_do_indicador_errado():
    resumo = "A companhia reportou que o lucro cresceu 8% no período."
    motivo = qualidade.numeros_com_metrica_trocada(resumo, _TEXTO_MULTI_METRICA)
    assert motivo != []
    assert "lucro" in motivo[0] and "receita" in motivo[0]


def test_atribuicao_correta_dos_3_indicadores_nao_e_rejeitada():
    """Positivo: resumo reatribui os 3 números do original às métricas
    CORRETAS, com texto bem diferente do original - tem que passar."""
    resumo = (
        "Margem bruta ficou em 42%. O lucro líquido avançou 15% ante o trimestre "
        "anterior. A receita líquida subiu 8% no período."
    )
    assert qualidade.numeros_com_metrica_trocada(resumo, _TEXTO_MULTI_METRICA) == []


def test_mesmo_evento_fontes_diferentes_preserva_agrupamento_legitimo():
    """Positivo adicional: mesma notícia, reescrita com sinônimos e
    ordem diferente - não pode gerar falso positivo de atribuição."""
    original = "O EBITDA da companhia atingiu R$ 500 milhões, alta de 12% no trimestre."
    resumo = "A companhia reportou EBITDA de R$ 500 milhões, um avanço de 12% no período."
    assert qualidade.numeros_com_metrica_trocada(resumo, original) == []


def test_metrica_generica_no_resumo_casa_com_metrica_especifica_no_original():
    """'lucro' (resumo) tem que reconhecer 'lucro liquido' (original)
    como a MESMA familia de metrica - nunca falso positivo so' por
    generalizar o nome. Achado real ao escrever este teste: a 1a versao
    da correcao exigia igualdade EXATA de string e rejeitava isso."""
    resumo = "O lucro avançou 15% no trimestre."
    assert qualidade.numeros_com_metrica_trocada(resumo, _TEXTO_MULTI_METRICA) == []


def test_margem_bruta_nunca_casa_com_margem_ebitda_mesmo_sendo_prefixo_comum():
    original = "a margem ebitda avançou 42% no trimestre"
    resumo = "a margem bruta avançou 42% no trimestre"
    motivo = qualidade.numeros_com_metrica_trocada(resumo, original)
    assert motivo != []


def test_numero_sem_metrica_reconhecida_no_resumo_nao_e_avaliado():
    """Conservador: se o resumo nao tem metrica conhecida perto do
    numero, a checagem de atribuicao nao se aplica (nunca reprova por
    uma ausencia de vocabulario, so' numeros_sem_base continua valendo)."""
    resumo = "O indicador ficou em 8% no período."
    assert qualidade.numeros_com_metrica_trocada(resumo, _TEXTO_MULTI_METRICA) == []


def test_numero_sem_metrica_reconhecida_no_original_nao_e_avaliado():
    """Mesmo principio do outro lado: se o ORIGINAL nao tem nenhuma
    metrica conhecida perto desse numero (ex: numero isolado, so' data/
    contagem), a checagem fica inconclusiva - nunca reprova por isso."""
    original = "o indicador em questao ficou em 8% no periodo, sem mais detalhes"
    resumo = "o lucro cresceu 8% no periodo"
    assert qualidade.numeros_com_metrica_trocada(resumo, original) == []


def test_caso_ambiguo_com_mais_de_1_metrica_perto_do_mesmo_numero_e_conservador():
    """Caso ambiguo de verdade: o MESMO numero aparece perto de 2
    metricas diferentes no original (ex: numero citado 2x, uma vez por
    engano/repeticao editorial perto de cada uma) - qualquer uma das 2
    no resumo tem que ser aceita, nunca reprovada so' por nao ser 'a'
    metrica unica (nao ha' uma unica resposta certa aqui)."""
    original = "margem de 20% e também custo de 20% foram citados no release."
    resumo_margem = "a margem ficou em 20%."
    resumo_custo = "o custo ficou em 20%."
    assert qualidade.numeros_com_metrica_trocada(resumo_margem, original) == []
    assert qualidade.numeros_com_metrica_trocada(resumo_custo, original) == []


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


# ---------------------------------------------------------------------
# Recomendação de compra/venda sem evidência (auditoria Lives Genial,
# 2026-11-13, pedido explícito do Rodrigo: falsa atribuição de
# recomendação é bug crítico). Cenário real: tipo "LIVE" nunca passa pela
# extração estruturada de recomendação (só tipo "ACOES" passa, ver
# resumir.py:_TIPOS_COM_DADOS_ESTRUTURADOS) - o único lugar onde uma
# recomendação pode "escapar" pra um vídeo é dentro da prosa do resumo
# narrativo, sem nenhum gate determinístico até esta correção.
# ---------------------------------------------------------------------

_TRANSCRICAO_LIVE_SEM_RECOMENDACAO = (
    "[00:22] bom dia, hoje é quinta-feira. o mercado reage ao CPI americano que veio "
    "acima do esperado, pressionando as bolsas. [05:10] a Genial comenta que o "
    "petróleo subiu 1,2% no pregão de ontem, favorecendo as petroleiras."
)

_TRANSCRICAO_LIVE_COM_RECOMENDACAO_REAL = (
    "[00:22] bom dia. [10:40] sobre PETR4, a Genial recomenda compra do papel, "
    "destacando o potencial de valorização com o novo plano de investimentos."
)


def test_recomendacao_inventada_em_live_e_rejeitada():
    """Caso crítico: o resumo atribui 'a Genial recomenda compra de PETR4'
    mas a transcrição real do programa nunca mencionou nenhuma
    recomendação de compra/venda - falsa atribuição, tem que ser pega."""
    resumo = "Sobre PETR4, a Genial recomenda compra do papel após o resultado do CPI."
    motivo = qualidade.recomendacao_sem_evidencia(resumo, _TRANSCRICAO_LIVE_SEM_RECOMENDACAO)
    assert motivo is not None
    assert "recomenda compra" in motivo


def test_recomendacao_realmente_dita_na_live_nao_e_rejeitada():
    """Positivo: a recomendação citada no resumo tem base real na
    transcrição (a Genial de fato disse isso no programa) - nunca pode
    ser bloqueada."""
    resumo = "A Genial recomenda compra de PETR4, citando o novo plano de investimentos."
    assert qualidade.recomendacao_sem_evidencia(resumo, _TRANSCRICAO_LIVE_COM_RECOMENDACAO_REAL) is None


def test_resumo_sem_nenhuma_recomendacao_explicita_nao_e_avaliado():
    """Resumo que so' narra fatos/opiniões sem usar nenhuma das frases de
    recomendação explícita de compra/venda nunca é afetado por esta
    checagem (mesmo sem nenhuma base, porque simplesmente não há
    recomendação nenhuma pra confirmar ou desmentir)."""
    resumo = "O mercado reagiu ao CPI americano, pressionando as bolsas."
    assert qualidade.recomendacao_sem_evidencia(resumo, _TRANSCRICAO_LIVE_SEM_RECOMENDACAO) is None


def test_validar_fidelidade_tambem_pega_recomendacao_inventada_em_live():
    """Integração: validar_fidelidade (o gate de fato usado por
    resumir.py:_gerar_resumo antes de cachear) também reprova pela
    recomendação inventada, não só a função isolada (ticker PETR4
    presente nos dois lados de propósito, pra garantir que é a checagem
    de RECOMENDAÇÃO - não a de ticker - que reprova aqui)."""
    transcricao = _TRANSCRICAO_LIVE_SEM_RECOMENDACAO + " PETR4 também foi citada de passagem."
    resumo = "Sobre PETR4, a Genial recomenda venda do papel após o resultado do CPI."
    motivo = qualidade.validar_fidelidade(resumo, transcricao, "Morning Call Genial")
    assert motivo is not None
    assert "recomenda" in motivo.lower() or "recomendação" in motivo.lower()


# ---------------------------------------------------------------------
# Achado real (auditoria Lives Genial 2026-11-13, rodado contra as 13
# transcrições reais já coletadas no Supabase): uma transcrição real de
# ~25k caracteres de live financeira (Resumo da Manhã Genial, 13/11)
# menciona "vendas de casa [nos EUA]", "vender título público" e "compras
# que eu fiz ultimamente" - nenhum relacionado a uma recomendação de ação
# - mas a checagem antiga ("raiz em QUALQUER lugar do original") bastava
# pra validar "a Genial recomenda compra da ação XPTO3" como se tivesse
# base real, mesmo XPTO3 nunca aparecendo na transcrição. Os testes abaixo
# fixam esse comportamento com um recorte sintético equivalente (sem
# depender da transcrição real, que não é determinística/versionada).
# ---------------------------------------------------------------------

_TRANSCRICAO_LIVE_COMPRA_VENDA_SOLTOS_SEM_RELACAO = (
    "[00:19] bom dia, hoje a minha maior preocupação é o número de vendas "
    "de casa nos Estados Unidos, que despencou - e a gente voltou a ter "
    "dificuldade de vender título público por aqui também. [05:40] eu "
    "comprei em qualquer lugar do mundo e tô até arrependido das compras "
    "que eu fiz ultimamente, mas vamos ver como fecha o pregão."
)


def test_recomendacao_inventada_nao_e_validada_por_compra_venda_solto_sem_relacao():
    """Reprodução do achado real: 'compra'/'venda'/'vender'/'comprar'
    aparecem na transcrição, mas em contextos sem nenhuma relação com uma
    recomendação de ação (venda de casa nos EUA, título público, compras
    pessoais do apresentador) - e o ticker da recomendação inventada
    (XPTO3) nunca é citado. Tem que ser rejeitada mesmo com as raízes
    presentes em algum lugar do texto."""
    resumo = "A Genial recomenda compra da ação XPTO3 após a leitura do PPI americano."
    motivo = qualidade.recomendacao_sem_evidencia(
        resumo, _TRANSCRICAO_LIVE_COMPRA_VENDA_SOLTOS_SEM_RELACAO
    )
    assert motivo is not None
    assert "XPTO3" in motivo


def test_recomendacao_com_ticker_longe_da_raiz_no_original_e_rejeitada():
    """O ticker e uma raiz de recomendação podem os dois aparecer no
    original sem relação entre si (ex: ticker citado numa parte, 'compra'
    citado bem depois, sobre outro assunto) - distância maior que a
    janela de proximidade (_JANELA_EVIDENCIA_TICKER_CH) não conta como
    evidência real da recomendação citada no resumo."""
    enchimento = "o mercado ficou de lado durante toda a sessão de hoje. " * 15
    transcricao = f"PETR4 foi citada de passagem no começo do programa. {enchimento} depois falamos de compras no varejo, sem relação com nenhuma ação."
    resumo = "Sobre PETR4, a Genial recomenda compra do papel após o resultado do CPI."
    motivo = qualidade.recomendacao_sem_evidencia(resumo, transcricao)
    assert motivo is not None
    assert "PETR4" in motivo


def test_recomendacao_com_ticker_proximo_da_raiz_no_original_nao_e_rejeitada():
    """Positivo simétrico ao teste anterior: ticker e raiz de recomendação
    aparecem PRÓXIMOS no original (mesma frase/vizinhança) - evidência
    real, nunca bloqueada."""
    transcricao = "sobre PETR4, a Genial recomenda compra do papel, destacando o potencial de valorização."
    resumo = "A Genial recomenda compra de PETR4, citando o potencial de valorização."
    assert qualidade.recomendacao_sem_evidencia(resumo, transcricao) is None


def test_recomendacao_sem_ticker_na_frase_continua_na_checagem_antiga():
    """Quando a frase de recomendação não cita nenhum ticker (ex:
    recomendação só por nome/prosa, sem código do papel), a checagem
    continua a antiga (raiz em qualquer lugar do original) - limitação
    conhecida e documentada, não resolvida por este achado (não há como
    amarrar a evidência a um alvo específico sem extrair o nome da
    empresa da frase)."""
    resumo = "A Genial recomenda compra do papel, destacando o resultado do trimestre."
    assert qualidade.recomendacao_sem_evidencia(
        resumo, _TRANSCRICAO_LIVE_COMPRA_VENDA_SOLTOS_SEM_RELACAO
    ) is None
