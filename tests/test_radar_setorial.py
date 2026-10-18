# -*- coding: utf-8 -*-
"""Radar setorial do Morning Call (data/radar_setorial.py) - seleção,
reprodutibilidade, rodízio, dados ausentes, validação de fontes e
renderização no PDF. Sem rede: as notícias vêm de amostras."""
import io
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data.radar_setorial as rs  # noqa: E402
import jobs.morning_call_pdf as pdf_mod  # noqa: E402
import morning_call_amostras as amostras  # noqa: E402

TZ_SP = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 10, 19, 8, 0, tzinfo=TZ_SP)
INICIO = datetime(2026, 10, 16, 6, 0, tzinfo=TZ_SP)


def _noticia(titulo, veiculo="Valor Econômico", horas=10, link=None, data=None, importancia=50, tickers=None):
    return {"titulo": titulo, "veiculos": [veiculo], "importancia": importancia, "tickers": tickers or [],
            "link": link if link is not None else f"https://exemplo.invalid/{abs(hash(titulo))}",
            "data": data if data is not None else (AGORA - timedelta(hours=horas)).isoformat()}


# ------------------------------------------------------------------
# Seleção
# ------------------------------------------------------------------

def test_plano_tem_quatro_setores_distintos_do_catalogo():
    plano = rs.plano_do_dia(date(2026, 10, 19))[:rs.QTD_SETORES]
    assert len(plano) == 4 and len(set(plano)) == 4
    assert set(plano) <= set(rs.CATALOGO)


def test_mesma_edicao_mesma_selecao():
    assert rs.plano_do_dia(date(2026, 10, 19)) == rs.plano_do_dia(date(2026, 10, 19))
    rs._planos.cache_clear()
    assert rs.plano_do_dia(date(2026, 10, 19))[:4] == ["PETRÓLEO & GÁS", "IMOBILIÁRIO", "BANCOS", "VAREJO"]


def test_dias_seguidos_variam_e_todo_setor_aparece_em_tres_dias_uteis():
    dias = [d for d, _ in rs.historico_planos(date(2026, 10, 30), dias=10)]
    planos = [set(p) for _, p in rs.historico_planos(date(2026, 10, 30), dias=10)]
    for anterior, atual in zip(planos, planos[1:]):
        assert anterior != atual
    for i in range(len(planos) - 2):
        assert planos[i] | planos[i + 1] | planos[i + 2] == set(rs.CATALOGO), dias[i]


def test_historico_bate_com_o_plano_de_cada_dia_e_pula_fim_de_semana():
    historico = rs.historico_planos(date(2026, 10, 19), dias=4)
    assert [d.weekday() < 5 for d, _ in historico] == [True] * 4
    for dia, setores in historico:
        assert setores == rs.plano_do_dia(dia)[:4]
    assert rs.plano_do_dia(date(2026, 10, 18)) == rs.plano_do_dia(date(2026, 10, 16))


def test_catalogo_configuravel():
    catalogo = {k: rs.CATALOGO[k] for k in ("BANCOS", "VAREJO", "SAÚDE", "SANEAMENTO", "IMOBILIÁRIO")}
    plano = rs.plano_do_dia(date(2026, 10, 19), catalogo=catalogo)
    assert set(plano) == set(catalogo)


def test_textos_do_catalogo_sem_numeros_e_sem_recomendacao():
    for setor, cfg in rs.CATALOGO.items():
        texto = cfg["importa"] + " " + cfg["acompanhar"]
        assert not re.search(r"\d", texto), setor
        assert not re.search(r"\b(compre|venda|comprar|vender|recomend\w*)\b", texto.lower()), setor


# ------------------------------------------------------------------
# Evidência e fontes
# ------------------------------------------------------------------

def test_validar_fonte_exige_titulo_veiculo_link_e_data_na_janela():
    ok = _noticia("Bancos ampliam crédito")
    assert rs.validar_fonte(ok, INICIO, AGORA) == (True, None)
    assert rs.validar_fonte({**ok, "titulo": ""}, INICIO, AGORA)[1] == "sem título"
    assert rs.validar_fonte({**ok, "veiculos": []}, INICIO, AGORA)[1] == "sem veículo"
    assert rs.validar_fonte({**ok, "link": "javascript:alert(1)"}, INICIO, AGORA)[1] == "link inválido"
    assert rs.validar_fonte({**ok, "link": ""}, INICIO, AGORA)[1] == "link inválido"
    assert rs.validar_fonte({**ok, "data": None}, INICIO, AGORA)[1] == "sem data"
    assert rs.validar_fonte({**ok, "data": "2026-10-13T09:00:00-03:00"}, INICIO, AGORA)[1] == "fora da janela da edição"
    assert rs.validar_fonte({**ok, "data": "2026-10-20T09:00:00-03:00"}, INICIO, AGORA)[1] == "data no futuro"


def test_setor_com_uma_fonte_so_e_excluido_com_motivo():
    fontes, motivo = rs.evidencias_do_setor("BANCOS", [_noticia("Bancos ampliam crédito")], INICIO, AGORA)
    assert len(fontes) == 1
    assert "evidência insuficiente" in motivo


def test_duas_noticias_do_mesmo_veiculo_nao_bastam():
    itens = [_noticia("Bancos ampliam crédito", "Exame"), _noticia("Inadimplência de bancos sobe", "Exame")]
    _fontes, motivo = rs.evidencias_do_setor("BANCOS", itens, INICIO, AGORA)
    assert "1 veículo" in motivo


def test_sem_veiculo_confiavel_e_excluido():
    itens = [_noticia("Bancos ampliam crédito", "Blog A"), _noticia("Inadimplência de bancos sobe", "Blog B")]
    _f, motivo = rs.evidencias_do_setor("BANCOS", itens, INICIO, AGORA,
                                        confiavel=lambda v: v in ("Valor Econômico",))
    assert "fontes confiáveis" in motivo


def test_classificacao_estrita_por_palavra_inteira():
    """O classificador do app casa por substring ('gas' em 'gastos'); o
    radar exige a palavra inteira ou o ticker do setor."""
    assert not rs._menciona_setor("Governo corta gastos e acordo fiscal avança no mercado", "PETRÓLEO & GÁS")
    assert not rs._menciona_setor("Governo fecha acordo com estados sobre dívida", "MINERAÇÃO & SIDERURGIA")
    assert rs._menciona_setor("Preço do aço sobe na China", "MINERAÇÃO & SIDERURGIA")
    assert rs._menciona_setor("Ações sobem com resultado de PRIO3", "PETRÓLEO & GÁS")


def test_citar_o_setor_sem_contexto_de_mercado_nao_basta():
    """Casos reais do exemplo de 18/10/2026 que entraram só por palavra-chave."""
    assert not rs._menciona_setor("Tecnologia detecta mais de 80 tiros em Niterói e auxilia ação policial",
                                  "TECNOLOGIA & TELECOM")
    assert not rs._menciona_setor("Papa Leão 14 reza o Angelus após deixar hospital e agradece orações", "SAÚDE")
    assert not rs._menciona_setor("Edital Mãos Dadas, do Banco do Brasil, tem inscrições abertas para projetos "
                                  "de impacto social", "BANCOS")
    assert not rs._menciona_setor("Plano econômico de Flávio pode garantir equilíbrio fiscal", "PETRÓLEO & GÁS",
                                  tickers=["PETR4", "VALE3"])
    assert rs._menciona_setor("Petrobras supera R$ 800 bilhões e lidera ranking das maiores empresas",
                              "PETRÓLEO & GÁS")
    assert rs._menciona_setor("CNI: indústria depende mais de bancos tradicionais para obter crédito", "BANCOS")


def test_nome_de_empresa_ambiguo_exige_maiuscula():
    assert rs._menciona_setor("Vale eleva produção de minério no trimestre", "MINERAÇÃO & SIDERURGIA")
    assert not rs._menciona_setor("Tesouro Selic ou CDB: onde vale a pena investir?", "MINERAÇÃO & SIDERURGIA")
    assert not rs._menciona_setor("Vale a pena investir em CDB com a Selic alta?", "MINERAÇÃO & SIDERURGIA")
    assert rs._menciona_setor("Gol e Azul reajustam preços de passagens", "TRANSPORTE & LOGÍSTICA")
    assert not rs._menciona_setor("TIMES do Brasil mantêm vendas", "TECNOLOGIA & TELECOM")


def test_bancos_centrais_nao_sao_o_setor_bancario():
    """Caso real de 18/10/2026."""
    assert not rs._menciona_setor("Bancos centrais preveem juros mais altos com corrida por capital", "BANCOS")
    assert not rs._menciona_setor("Banco Central mantém juros", "BANCOS")
    assert rs._menciona_setor("Banco Central aperta regra e bancos elevam provisões", "BANCOS")


def test_empresas_citadas_vem_so_das_manchetes_publicadas():
    publicadas = [rs._fonte(_noticia("Bancos ampliam crédito; ITUB4 sobe", "Valor")),
                  rs._fonte(_noticia("Inadimplência de bancos cai", "Folha"))]
    nao_publicada = rs._fonte(_noticia("Spread de bancos sobe; BBDC4 cai " + "x " * 60, "Estadão"))
    bloco = rs.redigir_bloco("BANCOS", publicadas + [nao_publicada])
    assert [f["veiculo"] for f in bloco["fontes"]] == ["Valor", "Folha"]
    assert "Citadas nas notícias: ITUB4." in bloco["empresas"]
    assert "BBDC4" in bloco["empresas"]  # só como principal do setor, não como citada
    assert "Citadas nas notícias: BBDC4" not in bloco["empresas"]


def test_empresas_citadas_so_tickers_de_acao_escritos_no_titulo():
    assert rs._tickers_do_titulo("Mini-índice WINZ26 e PETR4 sobem; VALE3 cai") == ["PETR4", "VALE3"]


def test_noticia_fora_da_janela_ou_sem_link_nao_conta_como_evidencia():
    itens = [_noticia("Bancos ampliam crédito", "Valor Econômico"),
             _noticia("Inadimplência de bancos sobe", "Folha", data="2026-10-13T09:00:00-03:00"),
             _noticia("Spread dos bancos cai", "Estadão", link="")]
    fontes, motivo = rs.evidencias_do_setor("BANCOS", itens, INICIO, AGORA)
    assert [f["veiculo"] for f in fontes] == ["Valor Econômico"]
    assert motivo


def test_edital_publicado_nao_conta_como_noticia():
    """Caso real de 18/10/2026."""
    itens = [_noticia("Edital de Leilão ITAÚ UNIBANCO S/A", "Folha Capital"),
             _noticia("Bancos ampliam crédito", "Valor Econômico")]
    fontes, motivo = rs.evidencias_do_setor("BANCOS", itens, INICIO, AGORA)
    assert [f["veiculo"] for f in fontes] == ["Valor Econômico"] and motivo


def test_duplicata_do_mesmo_fato_conta_uma_vez():
    itens = [_noticia("Bancos ampliam crédito", "Valor Econômico"), _noticia("Bancos ampliam crédito", "Folha")]
    fontes, motivo = rs.evidencias_do_setor("BANCOS", itens, INICIO, AGORA)
    assert len(fontes) == 1 and motivo


# ------------------------------------------------------------------
# Redação
# ------------------------------------------------------------------

def test_blocos_da_amostra_tem_quatro_partes_e_tamanho_alvo():
    radar = amostras.radar_amostra()
    assert len(radar["setores"]) == 4
    for bloco in radar["setores"]:
        assert bloco["o_que_aconteceu"] and bloco["por_que_importa"] and bloco["empresas"] and bloco["acompanhar"]
        assert rs.PALAVRAS_MIN <= bloco["palavras"] <= rs.PALAVRAS_MAX, (bloco["nome"], bloco["palavras"])
        assert len(bloco["fontes"]) >= rs.MIN_FONTES


def test_nenhum_numero_que_nao_esteja_na_fonte():
    """Todo número de 'O que aconteceu' vem do título ou da data da fonte;
    'Empresas' só cita tickers (das fontes ou do catálogo)."""
    for bloco in amostras.radar_amostra()["setores"]:
        origem = " ".join(f["titulo"] + " " + f["data"].strftime("%d/%m") for f in bloco["fontes"])
        for fato in bloco["o_que_aconteceu"]:
            for numero in re.findall(r"\d+(?:[.,/]\d+)*", fato):
                assert numero in origem, (numero, fato)
        tickers_validos = set(rs.CATALOGO[bloco["setor"]]["empresas"]) | {
            t for f in bloco["fontes"] for t in rs._tickers_do_titulo(f["titulo"])}
        assert set(re.findall(r"\b[A-Z]{4}\d{1,2}\b", bloco["empresas"])) <= tickers_validos


def test_fatos_citam_veiculo_e_data_de_cada_fonte():
    bloco = amostras.radar_amostra()["setores"][0]
    for fato, fonte in zip(bloco["o_que_aconteceu"], bloco["fontes"]):
        assert fato.startswith(f"{fonte['veiculo']} ({fonte['data'].strftime('%d/%m')}):")
        assert fonte["titulo"].rstrip(" .") in fato


def test_texto_longo_demais_corta_manchetes_mas_nao_abaixo_do_minimo_de_fontes():
    longa = " ".join(["palavra"] * 30)
    fontes = [rs._fonte(_noticia(f"Bancos {longa} {i}", v)) for i, v in enumerate(("Valor", "Folha", "Estadão"))]
    bloco = rs.redigir_bloco("BANCOS", fontes)
    assert len(bloco["fontes"]) == rs.MIN_FONTES


# ------------------------------------------------------------------
# Dados ausentes
# ------------------------------------------------------------------

def test_setor_sem_evidencia_e_substituido_pelo_proximo_da_ordem():
    noticias = dict(amostras.NOTICIAS_SETOR_AMOSTRA)
    noticias["BANCOS"] = noticias["BANCOS"][:1]  # bancos fica com uma fonte só
    noticias.pop("ENERGIA ELÉTRICA")  # o substituto recebe as notícias genéricas abaixo
    ordem = rs.plano_do_dia(AGORA.date())
    radar = rs.montar_radar(AGORA, buscar=lambda s: noticias.get(s, []) or [
        _noticia(f"{rs.CATALOGO[s]['termos'][0]}: ações sobem após resultado", "Valor Econômico"),
        _noticia(f"{rs.CATALOGO[s]['termos'][0]}: receita cresce no trimestre", "Folha")], inicio=INICIO)
    nomes = [b["setor"] for b in radar["setores"]]
    assert "BANCOS" not in nomes and len(nomes) == 4
    assert nomes[3] == ordem[4]
    assert radar["excluidos"][0]["setor"] == "BANCOS"
    assert "evidência insuficiente" in radar["excluidos"][0]["motivo"]


def test_coleta_que_falha_registra_motivo_e_nao_derruba_o_radar():
    def buscar(setor):
        if setor == "PETRÓLEO & GÁS":
            raise TimeoutError("google news")
        if setor == "IMOBILIÁRIO":
            return None
        return amostras.NOTICIAS_SETOR_AMOSTRA.get(setor, [])
    radar = rs.montar_radar(AGORA, buscar=buscar, inicio=INICIO)
    motivos = {e["setor"]: e["motivo"] for e in radar["excluidos"]}
    assert motivos["PETRÓLEO & GÁS"] == "coleta falhou: TimeoutError"
    assert motivos["IMOBILIÁRIO"] == "coleta falhou"


def test_sem_nenhuma_noticia_radar_vazio_sem_inventar():
    radar = rs.montar_radar(AGORA, buscar=lambda _s: [], inicio=INICIO)
    assert radar["setores"] == []
    assert len(radar["excluidos"]) == rs.MAX_TENTATIVAS


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------

def _texto_pdf(edicao):
    leitor = PdfReader(io.BytesIO(pdf_mod.gerar_pdf(edicao)))
    return leitor, " ".join(" ".join(p.extract_text() for p in leitor.pages).split())


def test_pdf_publica_os_quatro_setores_com_rotulos_e_links():
    edicao = amostras.edicao_tipica()
    edicao["radar"] = amostras.radar_amostra()
    leitor, texto = _texto_pdf(edicao)
    assert "R A D A R" in texto or "RADAR SETORIAL" in texto.upper()
    for bloco in edicao["radar"]["setores"]:
        assert bloco["nome"] in texto
    for rotulo in ("O QUE ACONTECEU", "POR QUE IMPORTA", "EMPRESAS E ATIVOS RELACIONADOS", "O QUE ACOMPANHAR"):
        assert texto.count(rotulo) == 4
    assert "Não é recomendação de compra ou venda" in texto
    assert "Radar setorial" in texto  # índice da capa
    links = {a["/A"]["/URI"] for p in leitor.pages for a in (p.get("/Annots") or [])
             if a.get_object().get("/A", {}).get("/URI")}
    for bloco in edicao["radar"]["setores"]:
        for fonte in bloco["fontes"]:
            assert fonte["link"] in links


def test_pdf_sem_radar_diz_que_nao_saiu():
    edicao = amostras.edicao_tipica()
    edicao["radar"] = None
    _l, texto = _texto_pdf(edicao)
    assert "Radar setorial indisponível nesta edição." in texto
    edicao["radar"] = {"setores": [], "excluidos": [], "plano": [], "historico": []}
    _l, texto = _texto_pdf(edicao)
    assert "Nenhum setor do rodízio teve notícias suficientes" in texto
