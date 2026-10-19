# -*- coding: utf-8 -*-
"""Testes de data/morning_call_editorial.py:sintese_pagina2 e das funções
auxiliares da página 2 analítica (PR "página 2 analítica", 2026-10-19).

Cobertura exigida pela missão: ausência de fonte, dados insuficientes,
duplicação entre blocos, falha/validação da IA, datas nunca inventadas e
afirmações sem suporte (número novo vindo do Groq). Testes de link
clicável/veículo aparecendo no PDF real vivem em tests/test_morning_call_pdf.py
(camada de apresentação) - aqui é só a camada de dados, sem ReportLab.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import data.morning_call_editorial as ed

TZ = timezone.utc


def _item(titulo, veiculo="Veículo Exemplo", importancia=0.5, corpo=None, link="https://x.invalid/a",
          tickers=None):
    return {
        "titulo": titulo, "veiculo": veiculo, "importancia": importancia, "corpo": corpo or [],
        "link": link, "tickers": tickers or [], "data": None, "publicado_outro_dia": False,
    }


# ---------------------------------------------------------------------
# Tema e cláusula - mapeamento determinístico, nunca inventa tema
# ---------------------------------------------------------------------

def test_tema_do_item_detecta_juros_por_copom_e_selic():
    assert ed._tema_do_item(_item("Copom mantém Selic em 15% ao ano")) == "juros"


def test_tema_do_item_detecta_commodities_por_petroleo():
    assert ed._tema_do_item(_item("Petróleo Brent sobe 2% com tensão na Opep")) == "commodities"


def test_tema_do_item_sem_termo_conhecido_retorna_none():
    assert ed._tema_do_item(_item("Prefeitura inaugura nova ciclovia no bairro")) is None


def test_clausula_tema_vazia_quando_item_sem_tema():
    assert ed._clausula_tema(_item("Prefeitura inaugura nova ciclovia no bairro")) == ""


def test_clausula_tema_presente_quando_tema_detectado():
    clausula = ed._clausula_tema(_item("IPCA acelera para 0,5% em setembro"))
    assert clausula.strip().startswith("É um")


# ---------------------------------------------------------------------
# Frase-fato - ausência de fonte nunca vira veículo inventado
# ---------------------------------------------------------------------

def test_frase_fato_sem_veiculo_usa_rotulo_honesto():
    item = _item("Alguma manchete", veiculo=None)
    frase = ed._frase_fato(item)
    assert "fonte não identificada" in frase
    assert "None" not in frase


def test_frase_fato_cita_veiculo_real():
    assert "Reuters" in ed._frase_fato(_item("Fed sinaliza pausa nos juros", veiculo="Reuters"))


# ---------------------------------------------------------------------
# Seção A (mercados) - conecta Brasil+exterior só quando o tema bate,
# nunca afirma causalidade, degrada honesto sem nenhuma notícia
# ---------------------------------------------------------------------

def test_mercados_conecta_brasil_exterior_quando_tema_coincide():
    brasil = [_item("Copom mantém Selic em 15% ao ano", veiculo="Valor")]
    exterior = [_item("Fed sinaliza mais um corte de juros", veiculo="Reuters")]
    paragrafos, citados = ed._paragrafos_mercados_determinista(brasil, exterior, [])
    texto = " ".join(paragrafos)
    assert "dois lados" in texto
    assert "não estabelecem relação causal" in texto
    assert len(citados) == 2


def test_mercados_nao_conecta_temas_diferentes():
    brasil = [_item("Copom mantém Selic em 15% ao ano")]
    exterior = [_item("Bitcoin se estabiliza perto de US$ 80 mil")]
    paragrafos, citados = ed._paragrafos_mercados_determinista(brasil, exterior, [])
    texto = " ".join(paragrafos)
    assert "dois lados" not in texto
    assert len(paragrafos) == 2  # 1 frase por editoria, sem forçar conexão


def test_mercados_sem_nenhuma_noticia_e_honesto_sem_inventar_fato():
    paragrafos, citados = ed._paragrafos_mercados_determinista([], [], [])
    assert citados == []
    assert "Sem notícias" in paragrafos[0]


# ---------------------------------------------------------------------
# Exclusão da manchete da capa - página 2 não repete o que já foi
# mostrado na capa
# ---------------------------------------------------------------------

def test_sem_manchete_remove_item_identico_da_lista():
    manchete = _item("Manchete que abriu a capa")
    outro = _item("Outra notícia qualquer")
    resultado = ed._sem_manchete([manchete, outro], manchete)
    assert resultado == [outro]


def test_sem_manchete_com_manchete_none_preserva_lista():
    itens = [_item("A"), _item("B")]
    assert ed._sem_manchete(itens, None) == itens


# ---------------------------------------------------------------------
# Duplicação entre blocos - mesma frase de corpo nunca sai 2x na edição
# ---------------------------------------------------------------------

def test_segunda_frase_real_nao_repete_entre_chamadas():
    item = _item("Notícia com corpo", corpo=["Primeira frase real.", "Segunda frase real."])
    usadas = set()
    primeira = ed._segunda_frase_real(item, usadas)
    segunda_chamada_mesmo_item = ed._segunda_frase_real(item, usadas)
    assert primeira == "Primeira frase real."
    assert segunda_chamada_mesmo_item == "Segunda frase real."  # próxima frase ainda não usada
    assert ed._segunda_frase_real(item, usadas) is None  # as 2 frases já saíram


def test_segunda_frase_real_sem_corpo_retorna_none():
    assert ed._segunda_frase_real(_item("Sem corpo", corpo=[]), set()) is None


def test_cenario_internacional_pula_item_ja_citado_sem_informacao_nova():
    """Item já citado em A (sem corpo pra acrescentar) não repete em D -
    'aprofundar é aceitável, repetir sem nada novo não'."""
    ja_citado = _item("Fed mantém juros", corpo=[])
    outro = _item("Déficit dos EUA cresce", corpo=[])
    blocos = ed._bloco_cenario_internacional([ja_citado, outro], [ja_citado], set())
    titulos = [b["item"]["titulo"] for b in blocos]
    assert ja_citado["titulo"] not in titulos
    assert outro["titulo"] in titulos


def test_cenario_internacional_mantem_item_ja_citado_se_tiver_frase_nova():
    ja_citado = _item("Fed mantém juros", corpo=["Frase adicional real do corpo."])
    blocos = ed._bloco_cenario_internacional([ja_citado], [ja_citado], set())
    assert len(blocos) == 1
    assert "Frase adicional real do corpo." in blocos[0]["texto"]


# ---------------------------------------------------------------------
# "O que acompanhar" - nunca inventa data, só usa o que a agenda real tem
# ---------------------------------------------------------------------

def test_acompanhar_nunca_inventa_data_so_usa_horario_e_status():
    agenda = [{"empresa": "Usiminas", "ticker": "USIM5", "tipo_evento": "RESULTADO", "periodo": "3T26",
              "horario": "após o fechamento", "status_rotulo": "CONFIRMADO"}]
    linhas = ed._bloco_acompanhar(agenda)
    assert len(linhas) == 1
    assert "após o fechamento" in linhas[0]
    assert "confirmado" in linhas[0]
    # nenhuma data numérica (dd/mm) foi adicionada - só o que já veio no evento
    import re
    assert not re.search(r"\b\d{1,2}/\d{1,2}\b", linhas[0])


def test_acompanhar_evento_sem_horario_e_honesto():
    agenda = [{"empresa": "WEG", "tipo_evento": "RESULTADO", "periodo": "3T26", "status_rotulo": "ESTIMADO"}]
    linhas = ed._bloco_acompanhar(agenda)
    assert "sem horário divulgado" in linhas[0]


def test_acompanhar_prioriza_confirmado_antes_de_estimado():
    agenda = [
        {"empresa": "Estimada", "tipo_evento": "RESULTADO", "periodo": "3T26", "status_rotulo": "ESTIMADO"},
        {"empresa": "Confirmada", "tipo_evento": "RESULTADO", "periodo": "3T26", "status_rotulo": "CONFIRMADO"},
    ]
    linhas = ed._bloco_acompanhar(agenda)
    assert linhas[0].startswith("Confirmada")


def test_acompanhar_limita_tamanho_mesmo_com_agenda_grande():
    agenda = [{"empresa": f"Empresa {i}", "tipo_evento": "RESULTADO", "periodo": "3T26",
              "status_rotulo": "CONFIRMADO"} for i in range(20)]
    assert len(ed._bloco_acompanhar(agenda, limite=5)) == 5


def test_acompanhar_deduplica_evento_repetido_na_agenda():
    """Achado na inspeção visual real (fixture 'cheia', 2026-10-19): a
    mesma linha de agenda repetida na fonte (ex.: agenda multiplicada por
    engano) não pode virar 5 bullets idênticos - cada evento único entra
    só 1 vez, mesmo que apareça várias vezes na lista de entrada."""
    evento = {"empresa": "Usiminas", "tipo_evento": "RESULTADO", "periodo": "3T26",
              "horario": "após o fechamento", "status_rotulo": "CONFIRMADO"}
    linhas = ed._bloco_acompanhar([evento] * 6)
    assert linhas == [
        "Usiminas: resultado (3T26), após o fechamento — data confirmado.",
    ]


def test_acompanhar_vazio_quando_sem_agenda():
    assert ed._bloco_acompanhar(None) == []
    assert ed._bloco_acompanhar([]) == []


# ---------------------------------------------------------------------
# IA (Groq) - sempre opcional, nunca a fonte dos fatos; falha/ausência
# de credencial cai no texto determinístico sem quebrar a edição
# ---------------------------------------------------------------------

def _sem_groq():
    return patch.object(ed.config, "obter_credenciais_groq", return_value=(None, "modelo"))


def _com_groq():
    return patch.object(ed.config, "obter_credenciais_groq", return_value=("chave-ficticia", "modelo"))


def test_sintese_ia_sem_credencial_usa_fallback_determinista():
    with _sem_groq():
        paragrafos, modo = ed._sintese_mercados_ia(["Parágrafo base real."])
    assert modo == "fallback"
    assert paragrafos == ["Parágrafo base real."]


def test_sintese_ia_erro_de_rede_usa_fallback(monkeypatch):
    with _com_groq(), patch("requests.post", side_effect=ConnectionError("fora do ar")):
        paragrafos, modo = ed._sintese_mercados_ia(["Parágrafo base real."])
    assert modo == "fallback"
    assert paragrafos == ["Parágrafo base real."]


def test_sintese_ia_status_http_diferente_de_200_usa_fallback():
    resposta_fake = MagicMock(status_code=500)
    with _com_groq(), patch("requests.post", return_value=resposta_fake):
        paragrafos, modo = ed._sintese_mercados_ia(["Parágrafo base real."])
    assert modo == "fallback"


def _resposta_groq(conteudo):
    resposta = MagicMock(status_code=200)
    resposta.json.return_value = {"choices": [{"message": {"content": conteudo}}]}
    return resposta


def test_sintese_ia_aceita_texto_valido_e_marca_modo_ia():
    base = ["O Ibovespa subiu 0,54% nesta sessão, segundo InfoMoney."]
    with _com_groq(), patch("requests.post", return_value=_resposta_groq(
        "O Ibovespa avançou 0,54% na sessão, puxado por ações ligadas ao petróleo, segundo a InfoMoney.")):
        paragrafos, modo = ed._sintese_mercados_ia(base)
    assert modo == "ia"
    assert paragrafos != base


def test_ia_rejeita_numero_novo_nao_presente_na_base_e_usa_fallback():
    """Afirmação sem suporte: o Groq "inventou" um percentual que não
    estava no texto determinístico - nunca pode ir pro PDF."""
    base = ["O Ibovespa subiu 0,54% nesta sessão, segundo InfoMoney."]
    with _com_groq(), patch("requests.post", return_value=_resposta_groq(
        "O Ibovespa subiu 0,54%, puxado por uma alta de 12% nas ações da Vale, segundo a InfoMoney.")):
        paragrafos, modo = ed._sintese_mercados_ia(base)
    assert modo == "fallback"
    assert paragrafos == base


def test_ia_rejeita_frase_de_recomendacao_de_compra():
    base = ["A Petrobras renovou máxima histórica de valor de mercado, segundo InfoMoney."]
    with _com_groq(), patch("requests.post", return_value=_resposta_groq(
        "A Petrobras renovou máxima histórica de valor de mercado - é hora de comprar, segundo a InfoMoney.")):
        paragrafos, modo = ed._sintese_mercados_ia(base)
    assert modo == "fallback"


def test_ia_rejeita_texto_vazio():
    base = ["Texto base real."]
    with _com_groq(), patch("requests.post", return_value=_resposta_groq("   ")):
        paragrafos, modo = ed._sintese_mercados_ia(base)
    assert modo == "fallback"


def test_ia_rejeita_texto_desproporcionalmente_maior_que_a_base():
    base = ["Texto base curto."]
    texto_longo = "Explicação detalhada. " * 80
    with _com_groq(), patch("requests.post", return_value=_resposta_groq(texto_longo)):
        paragrafos, modo = ed._sintese_mercados_ia(base)
    assert modo == "fallback"


@pytest.mark.parametrize("numero_base,numero_ia,esperado", [
    ("0,54%", "0,54%", True),
    ("R$ 820 bilhões", "R$ 820 bilhões", True),
    ("0,54%", "0,55%", False),
])
def test_ia_sintese_segura_compara_numeros_com_a_base(numero_base, numero_ia, esperado):
    base = f"O índice variou {numero_base} na sessão."
    texto_ia = f"O índice variou {numero_ia} na sessão, segundo a fonte."
    assert ed._ia_sintese_segura(texto_ia, base) is esperado


# ---------------------------------------------------------------------
# sintese_pagina2 - integração, nunca lança exceção mesmo com edição
# incompleta/antiga (sem as chaves novas)
# ---------------------------------------------------------------------

def test_sintese_pagina2_com_edicao_minima_nao_lanca_excecao():
    edicao_minima = {"agora": datetime(2026, 10, 19, 8, tzinfo=TZ), "capa": {}, "brasil": {}, "exterior": {},
                     "empresas": {}}
    resultado = ed.sintese_pagina2(edicao_minima, edicao_minima["agora"])
    assert resultado["brasil_foco"] is None
    assert resultado["empresas_foco"] == []
    assert resultado["cenario_internacional"] == []
    assert resultado["acompanhar"] == []


def test_sintese_pagina2_com_dict_totalmente_vazio_nao_lanca_excecao():
    resultado = ed.sintese_pagina2({}, datetime(2026, 10, 19, 8, tzinfo=TZ))
    assert resultado["mercados"]["modo"] == "fallback"
