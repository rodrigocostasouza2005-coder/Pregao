# -*- coding: utf-8 -*-
"""Testes de integração do motor de DEDUP de data/news.py: _agrupar e
_mesmo_grupo (orquestração completa - várias notícias reais, várias
fontes, decidindo quais são o MESMO fato e quais são distintas). Até
2026-10-08 esse nível (FASE 8 da auditoria) não tinha teste nenhum -
tests/test_news_relevancia.py cobre só as peças puras isoladas
(_relevante/_similaridade/_calcular_score); este arquivo cobre a
ORQUESTRAÇÃO (_agrupar chamando _mesmo_grupo pra cada item, decidindo
se funde ou abre grupo novo).

Cenários cobertos, nas palavras do pedido: notícias EQUIVALENTES (mesmo
fato, fontes/manchetes diferentes), notícias do MESMO EVENTO reportado
por fontes diferentes, e notícias REALMENTE DISTINTAS que não podem ser
agrupadas. Não altera nenhuma regra - só prova o comportamento atual
com casos realistas.

Puro (sem rede/IA) - usa as MESMAS funções internas (_tokens_similaridade/
_extrair_entidades) que o pipeline real usa pra montar os itens, não
dados inventados à mão. Uso: python tests/test_news_dedup.py (venv)."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.news import _agrupar, _tokens_similaridade

_FALHAS = []
_TZ_SP = ZoneInfo("America/Sao_Paulo")
_AGORA = datetime(2026, 10, 8, 12, 0, 0, tzinfo=_TZ_SP)


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # 2026-10-10: faz a checagem REALMENTE falhar sob pytest (antes so'
        # imprimia e guardava em _FALHAS, lido so' pelo runner `__main__` -
        # sob pytest toda funcao test_* passava mesmo com condicao=False,
        # a menos que outra linha lancasse excecao por acidente; ver
        # investigacao registrada no relatorio da auditoria 2026-10-10)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _item(titulo, veiculo, data=None, relevante=True, ticker="PETR4", ao_vivo=False, link=None):
    """Mesma forma de data/news.py:_montar_item - usa as funções reais de
    tokenização, não um fixture desconectado da implementação."""
    return {
        "titulo": titulo,
        "veiculo": veiculo,
        "link": link or f"https://{veiculo.lower().replace(' ', '')}.com/{abs(hash(titulo))}",
        "data": data or _AGORA,
        "relevante": relevante,
        "ao_vivo": ao_vivo,
        "_tokens_sim": _tokens_similaridade(titulo, ticker),
    }


# ============================================================
# 1. Notícias EQUIVALENTES (mesmo fato, veículos/manchetes diferentes)
#    -> 1 grupo só, com as 2 fontes preservadas.
# ============================================================

def test_1_mesmo_fato_fontes_diferentes_vira_1_grupo():
    itens = [
        _item("Petrobras anuncia dividendos extraordinários de R$ 5 bilhões", "Valor Econômico",
              data=_AGORA),
        _item("Petrobras distribui dividendos extraordinários de R$ 5 bilhões aos acionistas", "InfoMoney",
              data=_AGORA - timedelta(hours=1)),
    ]
    grupos = _agrupar(itens)
    _checar("1a mesmo fato reportado por 2 veículos -> 1 grupo só (não 2)", len(grupos) == 1, f"(qtd={len(grupos)})")
    _checar("1b as 2 fontes aparecem preservadas no grupo (nunca escondida)",
            len(grupos[0]["fontes"]) == 2, f"(fontes={grupos[0]['fontes']})")
    veiculos = {f["veiculo"] for f in grupos[0]["fontes"]}
    _checar("1c ambos os veículos (Valor e InfoMoney) estão no grupo", veiculos == {"Valor Econômico", "InfoMoney"})


def test_2_titulo_do_grupo_e_do_item_mais_recente():
    # itens fora de ordem na entrada - _agrupar ordena por data desc antes
    # de processar, entao o titulo/link do grupo tem que ser do item MAIS
    # RECENTE (o que "abriu" o grupo), nunca do mais antigo.
    antigo = _item("Petrobras eleva previsão de produção para 2027", "Exame",
                    data=_AGORA - timedelta(hours=5))
    recente = _item("Petrobras revisa previsão de produção para 2027 para cima", "Reuters",
                     data=_AGORA)
    grupos = _agrupar([antigo, recente])
    _checar("2a ainda 1 grupo so' (mesmo fato)", len(grupos) == 1)
    _checar("2b titulo do grupo e' o do item MAIS RECENTE (Reuters), nao o mais antigo",
            grupos[0]["titulo"] == recente["titulo"], f"(titulo={grupos[0]['titulo']!r})")
    _checar("2c link do grupo tambem e' o do item mais recente",
            grupos[0]["link"] == recente["link"])


# ============================================================
# 2. Notícias REALMENTE DISTINTAS -> nunca podem ser agrupadas.
# ============================================================

def test_3_fatos_diferentes_mesma_empresa_ficam_em_grupos_separados():
    # fora da janela de entidade (_JANELA_HORAS_ENTIDADE=24h) de proposito:
    # "Petrobras" sozinho (nome proprio capitalizado, 5+ letras) conta
    # como entidade em comum (ver nota em test_3b abaixo) - dentro de 24h
    # isso fundiria os 2, mesmo sendo fatos diferentes. Passado 24h, so'
    # sobra a similaridade de texto (bem baixa aqui: so' "petrobras" em
    # comum) pra decidir - por isso ficam separados.
    itens = [
        _item("Petrobras anuncia novo investimento em refino no Nordeste", "Valor Econômico",
              data=_AGORA),
        _item("Petrobras reduz preço da gasolina nas refinarias em 3%", "InfoMoney",
              data=_AGORA - timedelta(hours=30)),
    ]
    grupos = _agrupar(itens)
    _checar("3 fatos DIFERENTES (mesma empresa, >24h de diferença) ficam em 2 grupos separados - NUNCA fundidos",
            len(grupos) == 2, f"(qtd={len(grupos)})")


def test_3b_nome_da_propria_empresa_sozinho_conta_como_entidade_em_comum():
    # comportamento ATUAL documentado (nao e' bug reportado, so' uma
    # caracteristica real da heuristica sem IA): uma palavra capitalizada
    # isolada com 5+ letras (ex: "Petrobras") conta como "entidade em
    # comum" em _extrair_entidades - _ENTIDADE_IGNORAR so' lista termos
    # genericos (brasil/governo/dias da semana/meses), nao nomes de
    # empresa. Por isso, 2 fatos DIFERENTES da MESMA empresa DENTRO de
    # 24h fundem pela regra de entidade, mesmo com baixa similaridade de
    # texto - mesmo cenario do test_3, so' que dentro da janela de 24h.
    itens = [
        _item("Petrobras anuncia novo investimento em refino no Nordeste", "Valor Econômico",
              data=_AGORA),
        _item("Petrobras reduz preço da gasolina nas refinarias em 3%", "InfoMoney",
              data=_AGORA - timedelta(hours=5)),
    ]
    grupos = _agrupar(itens)
    _checar("3b dentro de 24h, o nome da empresa sozinho ja' basta pra' fundir (comportamento atual, nao alterado)",
            len(grupos) == 1, f"(qtd={len(grupos)})")


def test_4_mesmo_fato_fora_da_janela_de_dias_nao_funde_por_similaridade_generica():
    # similaridade de tokens so' funde dentro de _JANELA_DIAS_GRUPO (4
    # dias) - passado isso, SO' titulo identico ou entidade em comum (24h)
    # ainda fundem; um titulo PARECIDO (nao identico) sobre algo
    # relativamente antigo nao deveria se fundir com algo novo e' um
    # fato realmente novo (ex: resultado trimestral != resultado anterior).
    antigo = _item("Petrobras divulga resultado do 2º trimestre acima do esperado", "Valor Econômico",
                    data=_AGORA - timedelta(days=10))
    novo = _item("Petrobras divulga resultado do 3º trimestre acima do esperado", "InfoMoney",
                 data=_AGORA)
    grupos = _agrupar([antigo, novo])
    _checar("4 titulos parecidos mas fora da janela de dias (10 dias) E sem entidade em comum -> NAO funde",
            len(grupos) == 2, f"(qtd={len(grupos)})")


def test_5_entidades_diferentes_titulos_parecidos_nao_fundem_erroneamente():
    # entidades de 2+ palavras (ex: "Banco Genial" vs "Banco Master") sao
    # distintas (nao ha' overlap so' por compartilhar "Banco") - e o
    # CONTEUDO das manchetes aqui e' propositalmente diferente (resultado
    # trimestral vs reestruturacao pos-fusao), pra similaridade de texto
    # tambem ficar baixa - prova que 2 bancos diferentes nao se fundem
    # nem pela entidade nem pelo texto.
    itens = [
        _item("Banco Genial anuncia resultado trimestral acima do esperado", "Valor Econômico", data=_AGORA),
        _item("Banco Master reduz quadro de funcionários após fusão com concorrente", "InfoMoney", data=_AGORA),
    ]
    grupos = _agrupar(itens)
    _checar("5 bancos DIFERENTES (Genial vs Master), entidades e conteúdo distintos -> grupos separados",
            len(grupos) == 2, f"(qtd={len(grupos)})")


# ============================================================
# 3. Entidade em comum (nome próprio) funde mesmo com baixa
#    similaridade de palavras - dentro da janela de 24h.
# ============================================================

def test_6_entidade_em_comum_funde_mesmo_com_titulos_bem_diferentes():
    itens = [
        _item("Banco Genial é alvo de investigação da CVM por fraude em fundos", "Valor Econômico",
              data=_AGORA),
        _item("Caso Carbono Oculto: Banco Genial nega irregularidades em nota oficial", "InfoMoney",
              data=_AGORA - timedelta(hours=5)),
    ]
    grupos = _agrupar(itens)
    _checar("6 titulos com poucas palavras em comum, mas MESMA entidade (Banco Genial) dentro de 24h -> funde",
            len(grupos) == 1, f"(qtd={len(grupos)})")


def test_7_entidade_em_comum_mas_fora_da_janela_de_24h_nao_funde():
    itens = [
        _item("Banco Genial é alvo de investigação da CVM por fraude em fundos", "Valor Econômico",
              data=_AGORA),
        _item("Caso Carbono Oculto: Banco Genial nega irregularidades em nota oficial", "InfoMoney",
              data=_AGORA - timedelta(hours=30)),  # > _JANELA_HORAS_ENTIDADE (24h)
    ]
    grupos = _agrupar(itens)
    _checar("7 mesma entidade, mas fora da janela de 24h E sem similaridade de tokens suficiente -> NAO funde",
            len(grupos) == 2, f"(qtd={len(grupos)})")


# ============================================================
# 4. Título idêntico sempre funde, mesmo fora de qualquer janela
#    (a mesma manchete republicada semanas depois ainda é a mesma matéria).
# ============================================================

def test_8_titulo_identico_funde_mesmo_fora_de_qualquer_janela():
    itens = [
        _item("Petrobras aprova novo plano de investimentos", "Valor Econômico", data=_AGORA),
        _item("Petrobras aprova novo plano de investimentos", "Agência Brasil",
              data=_AGORA - timedelta(days=60)),  # bem fora de _JANELA_DIAS_GRUPO
    ]
    grupos = _agrupar(itens)
    _checar("8 titulo IDENTICO funde mesmo com 60 dias de diferenca (republicacao da mesma materia)",
            len(grupos) == 1, f"(qtd={len(grupos)})")


# ============================================================
# 5. Grupo compara contra TODOS os membros (nao so' o que abriu o
#    grupo) - evita fragmentar quando o titulo vai mudando ao longo
#    do dia (corrente de 3+ itens, cada um parecido só com o vizinho).
# ============================================================

def test_9_cadeia_de_titulos_mudando_gradualmente_nao_fragmenta():
    # A (mais antigo) <-> B <-> C (mais recente): A e C sozinhos podem nao
    # bater o limiar de similaridade, mas cada um bate com B - a regra
    # "compara contra TODOS os tokens ja' no grupo" deve manter os 3 juntos.
    a = _item("Petrobras eleva investimento em exploração no pré-sal este ano", "Valor Econômico",
              data=_AGORA - timedelta(hours=10))
    b = _item("Petrobras aumenta investimento em exploração e produção no pré-sal", "InfoMoney",
              data=_AGORA - timedelta(hours=5))
    c = _item("Petrobras amplia investimento em produção e logística no pré-sal", "Exame",
              data=_AGORA)
    grupos = _agrupar([a, b, c])
    _checar("9 cadeia de titulos mudando gradualmente (A~B~C) permanece em 1 grupo so', nao fragmenta",
            len(grupos) == 1, f"(qtd={len(grupos)}, titulos={[g['titulo'] for g in grupos]})")
    if len(grupos) == 1:
        _checar("9b as 3 fontes estao todas no mesmo grupo", len(grupos[0]["fontes"]) == 3)


# ============================================================
# 6. relevante/ao_vivo do grupo refletem QUALQUER item membro.
# ============================================================

def test_10_relevante_do_grupo_e_true_se_qualquer_item_for_relevante():
    # o item que ABRE o grupo (mais recente) NAO e' relevante, mas um
    # item fundido depois e' - o grupo inteiro deve virar relevante.
    abre_grupo = _item("Mercado repercute resultados de bancos no trimestre", "Valor Econômico",
                        data=_AGORA, relevante=False)
    membro_relevante = _item("Mercado repercute resultados do Itaú no trimestre", "InfoMoney",
                              data=_AGORA - timedelta(hours=1), relevante=True)
    grupos = _agrupar([abre_grupo, membro_relevante])
    if len(grupos) == 1:
        _checar("10 grupo e' relevante porque PELO MENOS 1 membro e' (mesmo que o que abriu nao seja)",
                grupos[0]["relevante"] is True)
    else:
        _checar("10 pre-condicao do teste (items deveriam se fundir por similaridade) nao bateu - revisar fixture",
                False, f"(qtd grupos={len(grupos)})")


def test_11_ao_vivo_do_grupo_e_true_se_qualquer_item_for():
    abre_grupo = _item("Petrobras divulga balanço do terceiro trimestre de 2026", "Valor Econômico",
                        data=_AGORA, ao_vivo=False)
    membro_ao_vivo = _item("Petrobras divulga balanço do 3º trimestre de 2026 em teleconferência",
                           "InfoMoney", data=_AGORA - timedelta(hours=1), ao_vivo=True)
    grupos = _agrupar([abre_grupo, membro_ao_vivo])
    if len(grupos) == 1:
        _checar("11 ao_vivo do grupo e' True porque pelo menos 1 membro e'", grupos[0]["ao_vivo"] is True)
    else:
        _checar("11 pre-condicao do teste (items deveriam se fundir) nao bateu - revisar fixture",
                False, f"(qtd grupos={len(grupos)})")


# ============================================================
# 7. Casos vazios/triviais nunca quebram.
# ============================================================

def test_12_lista_vazia_retorna_lista_vazia():
    _checar("12 lista vazia -> [] sem excecao", _agrupar([]) == [])


def test_13_item_unico_vira_1_grupo_com_1_fonte():
    grupos = _agrupar([_item("Petrobras anuncia novo CEO", "Valor Econômico", data=_AGORA)])
    _checar("13a 1 item -> 1 grupo", len(grupos) == 1)
    _checar("13b grupo tem exatamente 1 fonte", len(grupos[0]["fontes"]) == 1)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DE DEDUP (_agrupar/_mesmo_grupo) DE NEWS PASSARAM")
