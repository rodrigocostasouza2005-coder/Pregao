# -*- coding: utf-8 -*-
"""Regressões do PR A do Morning Call (editorial + PDF), cada uma tirada
de um defeito real da edição de teste de 18/10/2026 (14h59). Sem rede:
provedores mockados no nível de função, PDF gerado das amostras."""
import io
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data.morning_call_editorial as ed  # noqa: E402
import data.radar_setorial as rs  # noqa: E402
import jobs.morning_call_pdf as pdf_mod  # noqa: E402
import morning_call_amostras as amostras  # noqa: E402
from test_morning_call_editorial import _MultiPatch, _pools  # noqa: E402

TZ_SP = ZoneInfo("America/Sao_Paulo")
DOMINGO = datetime(2026, 10, 18, 14, 59, tzinfo=TZ_SP)
SEGUNDA = datetime(2026, 10, 19, 7, 0, tzinfo=TZ_SP)


# ------------------------------------------------------------------
# 1. Editoria pelo assunto da manchete, não pelo pool de coleta
# ------------------------------------------------------------------

def test_manchete_sobre_eua_coletada_no_pool_br_vai_para_mundo():
    for titulo in ("Déficit orçamentário dos EUA chega a US$ 1,8 trilhão",
                   "EUA pagam US$ 1 tri em juros da dívida pela primeira vez",
                   "Bitcoin recua após falas de Warsh, do Fed"):
        assert ed.editoria_por_assunto(titulo, "BR") == "INT", titulo


def test_manchete_sobre_brasil_coletada_no_pool_int_vai_para_brasil():
    assert ed.editoria_por_assunto("Brazil central bank holds Selic at 15%", "INT") == "BR"
    assert ed.editoria_por_assunto("Copom mantém juros; dólar cai", "INT") == "BR"
    assert ed.editoria_por_assunto("PETR4 jumps as oil rallies", "INT") == "BR"


def test_manchete_com_marcador_dos_dois_lados_fica_no_pool_de_origem():
    titulo = "Fed e Copom: o que esperar dos juros no Brasil e nos EUA"
    assert ed.editoria_por_assunto(titulo, "BR") == "BR"


def test_coletar_noticias_reparte_pelos_assuntos():
    noticias = [
        {"titulo": "Déficit orçamentário dos EUA chega a US$ 1,8 trilhão", "link": "https://x/1", "regiao": "BR",
         "tickers": [], "importancia": 9},
        {"titulo": "Brazil central bank holds Selic at 15%", "link": "https://x/2", "regiao": "INT",
         "tickers": [], "importancia": 8},
    ]
    with _MultiPatch(**_pools(noticias)):
        _erros, brasil, empresas, exterior = ed._coletar_noticias()
    assert [i["link"] for i in exterior] == ["https://x/1"]
    assert [i["link"] for i in brasil] == ["https://x/2"]
    assert empresas == []


# ------------------------------------------------------------------
# 2. Empresas: empresa no título, não ticker herdado do grupo
# ------------------------------------------------------------------

def test_ticker_herdado_do_grupo_nao_faz_noticia_virar_empresa():
    # "Plano econômico de Flávio..." trazia tickers somados de outros títulos do grupo
    noticias = [{"titulo": "Plano econômico de Flávio prevê corte de gastos e reforma tributária",
                 "link": "https://x/1", "regiao": "BR", "tickers": ["PETR4", "VALE3"], "importancia": 9}]
    with _MultiPatch(**_pools(noticias)):
        _erros, brasil, empresas, _exterior = ed._coletar_noticias()
    assert empresas == [] and [i["link"] for i in brasil] == ["https://x/1"]


def test_empresa_reconhecida_por_ticker_ou_nome_no_titulo():
    assert ed.e_noticia_de_empresa("PETR4 anuncia dividendo extraordinário")
    assert ed.e_noticia_de_empresa("Petrobras atinge R$ 820 bilhões em valor de mercado")
    assert ed.e_noticia_de_empresa("Vale eleva produção de minério no 3T")


def test_resumo_de_pregao_nao_e_noticia_de_empresa():
    assert not ed.e_noticia_de_empresa("Ibovespa sobe com Petrobras e Vale; dólar cai")
    assert not ed.e_noticia_de_empresa("Dólar recua 0,28% com Vale em alta")
    assert not ed.e_noticia_de_empresa("Vale a pena investir em CDB agora?")


# ------------------------------------------------------------------
# 3. Fora de pauta e piso de relevância financeira
# ------------------------------------------------------------------

def _item(titulo, veiculos=("Reuters",), horas=6):
    return {"titulo": titulo, "veiculos": list(veiculos), "importancia": 50,
            "data": (SEGUNDA - timedelta(hours=horas)).isoformat()}


def test_filtro_descarta_variedades_carta_e_servico_de_financas_pessoais():
    itens = [
        _item("Deep-fried and built to go viral: the summer of extreme fair foods"),
        _item("‘Some people did everything right’: I lost my home to a wildfire"),
        _item("Tesouro Selic, Tesouro Reserva ou CDB: qual rende mais?"),
        _item("Fed's Waller says more rate cuts may be needed"),
    ]
    titulos = [i["titulo"] for i in ed.filtrar_noticias(itens, SEGUNDA, exigir_relevancia=True)]
    assert titulos == ["Fed's Waller says more rate cuts may be needed"]


def test_fed_cpi_e_resultados_continuam_na_edicao():
    itens = [_item("US CPI rises 0.4% in September"),
             _item("Netflix earnings beat estimates as subscribers grow"),
             _item("Fed holds rates steady")]
    assert len(ed.filtrar_noticias(itens, SEGUNDA, exigir_relevancia=True)) == 3


def test_piso_de_relevancia_pelo_assunto_nunca_pela_quantidade_de_veiculos():
    sem_termo_um_veiculo = _item("Celebrity chef opens new restaurant in Manhattan")
    sem_termo_varios_veiculos = _item("Governo anuncia novo programa nacional", veiculos=("g1", "Folha", "CNN"))
    assert not ed.tem_relevancia_financeira(sem_termo_um_veiculo)
    assert not ed.tem_relevancia_financeira(sem_termo_varios_veiculos)
    assert ed.tem_relevancia_financeira(_item("VALE3 sobe na abertura"))
    # o e-mail de texto (jobs/morning_call.py) chama sem o piso: comportamento inalterado
    assert ed.filtrar_noticias([sem_termo_um_veiculo], SEGUNDA) == [sem_termo_um_veiculo]
    assert ed.filtrar_noticias([sem_termo_um_veiculo], SEGUNDA, exigir_relevancia=True) == []


_VEICULOS_REPLICADOS = ("Agência SP", "g1", "Folha de S.Paulo", "Estadão", "CNN Brasil")


def test_certidao_unica_de_debitos_sai_mesmo_replicada_por_varios_veiculos():
    """Caso real (validação de dom 18/10/2026, 22h27): serviço ao cidadão
    replicado por vários veículos entrava na editoria Brasil do PDF."""
    item = _item("Saiba como emitir a nova Certidão Única de Débitos do Estado de São Paulo",
                 veiculos=_VEICULOS_REPLICADOS)
    assert not ed.tem_relevancia_financeira(item)
    assert ed.filtrar_noticias([item], SEGUNDA, exigir_relevancia=True) == []


def test_servico_e_utilidade_publica_sem_impacto_financeiro_saem():
    for titulo in ("Como consultar a restituição do imposto de renda na Receita",
                   "Veja como tirar a segunda via do documento pelo aplicativo",
                   "Passo a passo para agendar atendimento no Poupatempo",
                   "How to renew your passport before the holidays"):
        assert not ed.tem_relevancia_financeira(_item(titulo, veiculos=_VEICULOS_REPLICADOS)), titulo


def test_titulo_com_saiba_como_nao_e_excluido_por_si_so():
    """Não há regra genérica contra "Saiba como": com tema de impacto de
    mercado, empresa ou ticker, a matéria explicativa continua entrando."""
    for titulo in ("Saiba como fica o IR com a reforma tributária",
                   "Saiba como a alta da Selic muda o cenário para os bancos",
                   "Entenda como a Vale pode ser afetada pela desaceleração da China",
                   "Veja como o Copom deve decidir os juros nesta semana",
                   "Saiba como a Petrobras (PETR4) vai pagar dividendos extraordinários"):
        assert ed.tem_relevancia_financeira(_item(titulo)), titulo


def test_noticias_legitimas_de_impacto_material_continuam_entrando():
    """Empresas, resultados, política monetária e fiscal, regulação,
    indicadores, crédito e tributação - com um único veículo."""
    for titulo in ("Itaú lucra R$ 11 bilhões no terceiro trimestre",
                   "Magazine Luiza anuncia nova rodada de reestruturação",
                   "Copom mantém Selic e sinaliza cautela",
                   "Governo revisa meta fiscal de 2027",
                   "Aneel aprova reajuste nas contas de luz",
                   "CVM abre processo contra gestora",
                   "Caged: país cria 180 mil vagas em setembro",
                   "Inadimplência das famílias atinge recorde",
                   "Senado aprova reforma tributária em segundo turno",
                   "ICMS sobre combustíveis volta a subir em janeiro",
                   "IMF/World Bank meetings leave developing countries with more questions than answers",
                   "ECB holds rates as inflation cools"):
        assert ed.tem_relevancia_financeira(_item(titulo, veiculos=("Valor Econômico",))), titulo


# ------------------------------------------------------------------
# 4. Título com "hoje" publicado em outro dia
# ------------------------------------------------------------------

def test_titulo_relativo_de_outro_dia_e_marcado():
    sexta = {"titulo": "Ibovespa fecha hoje em alta", "data": "2026-10-16T18:00:00-03:00"}
    hoje = {"titulo": "Ibovespa abre hoje em alta", "data": "2026-10-19T06:30:00-03:00"}
    sem_relativo = {"titulo": "Ibovespa fecha em alta", "data": "2026-10-16T18:00:00-03:00"}
    assert ed.titulo_relativo_de_outro_dia(sexta, SEGUNDA)
    assert not ed.titulo_relativo_de_outro_dia(hoje, SEGUNDA)
    assert not ed.titulo_relativo_de_outro_dia(sem_relativo, SEGUNDA)


def test_manchete_prefere_titulo_sem_hoje_de_outro_dia_com_importancia_comparavel():
    velha = {"titulo": "Bolsa fecha hoje em alta", "data": "2026-10-16T18:00:00-03:00", "importancia": 100}
    proxima = {"titulo": "Focus eleva IPCA de 2026", "data": "2026-10-19T08:30:00-03:00", "importancia": 85}
    distante = {"titulo": "Petróleo sobe", "data": "2026-10-19T06:00:00-03:00", "importancia": 50}
    manchete, _ = ed.selecionar_manchete([velha, proxima], agora=SEGUNDA)
    assert manchete is proxima
    # sem alternativa comparável (>= 80%), mantém a mais importante
    manchete, _ = ed.selecionar_manchete([velha, distante], agora=SEGUNDA)
    assert manchete is velha


def test_montar_edicao_marca_fato_publicado_em_outro_dia():
    noticias = [{"titulo": "Ibovespa fecha hoje em alta de 0,54%", "link": "https://x/1", "regiao": "BR",
                 "tickers": [], "importancia": 9}]
    with _MultiPatch(**_pools(noticias, data="2026-10-16T18:00:00-03:00")):
        edicao = ed.montar_edicao(SEGUNDA)
    assert edicao["brasil"]["noticias"][0]["publicado_outro_dia"] is True


def test_linha_fonte_diz_quando_titulo_relativo_e_de_outro_dia():
    estilos = pdf_mod._estilos()
    fato = {"veiculo": "InfoMoney", "data": "2026-10-16T18:00:00-03:00", "publicado_outro_dia": True}
    texto = pdf_mod._linha_fonte(fato, SEGUNDA, estilos).text
    assert "publicado sex 16/10, 18h00" in texto


# ------------------------------------------------------------------
# 5. Toda linha de fonte tem dia da semana e data
# ------------------------------------------------------------------

def test_momento_publicacao_sempre_com_dia_e_data():
    assert pdf_mod._momento_publicacao("2026-10-19T07:02:00-03:00", SEGUNDA) == "seg 19/10, 7h02"
    assert pdf_mod._momento_publicacao("2026-10-18T04:00:00-03:00", SEGUNDA) == "dom 18/10, 4h00"
    # UTC convertido para Brasília
    assert pdf_mod._momento_publicacao("2026-10-19T10:00:00+00:00", SEGUNDA) == "seg 19/10, 7h00"
    assert pdf_mod._momento_publicacao(None, SEGUNDA) == ""


def test_todas_as_linhas_de_fonte_do_pdf_tem_data():
    leitor = PdfReader(io.BytesIO(pdf_mod.gerar_pdf(amostras.edicao_tipica(), {})))
    texto = "\n".join(p.extract_text() for p in leitor.pages)
    linhas = [l for l in texto.splitlines() if "texto completo" in l]
    assert linhas
    for linha in linhas:
        assert re.search(r"\b(seg|ter|qua|qui|sex|sáb|dom) \d{2}/\d{2}, \d{1,2}h\d{2}", linha), linha


# ------------------------------------------------------------------
# 6. Masthead: sessão de mercado separada do horário de geração
# ------------------------------------------------------------------

def test_masthead_separa_sessao_de_mercado_e_geracao():
    linha = pdf_mod._linha_referencia_masthead(DOMINGO, date(2026, 10, 16))
    assert linha == "Mercados: fechamento de sex 16/10 · gerado dom 18/10, 14h59 (Brasília)"
    assert pdf_mod._linha_referencia_masthead(SEGUNDA, date(2026, 10, 19)).startswith("Mercados: sessão de seg 19/10")
    assert pdf_mod._linha_referencia_masthead(SEGUNDA, None).startswith("Mercados: cotações indisponíveis")


def test_pdf_nao_tem_mais_edicao_das_8h_fixa():
    leitor = PdfReader(io.BytesIO(pdf_mod.gerar_pdf(amostras.edicao_tipica(), {})))
    capa = leitor.pages[0].extract_text()
    assert "Edição das 8h" not in capa and "Dados até" not in capa
    assert "Mercados: fechamento de sex 16/10" in capa


def test_sessao_mercado_vem_do_primeiro_indicador_com_sessao():
    assert ed.sessao_mercado([{"sessao": None}, {"sessao": date(2026, 10, 16)}]) == date(2026, 10, 16)
    assert ed.sessao_mercado([{"erro": "sem dado", "sessao": None}]) is None


# ------------------------------------------------------------------
# 7. Tabela macro: vigente/observado separado de expectativa (Focus)
# ------------------------------------------------------------------

def test_tabela_macro_tem_subcabecalhos_e_referencia_em_cada_linha():
    estilos = pdf_mod._estilos()
    macro = [i for i in amostras.edicao_tipica()["brasil"]["indicadores"] if "indicador" in i]
    tabela = pdf_mod._tabela_macro(macro, estilos)
    textos = [getattr(c[0], "text", c[0]) for c in tabela._cellvalues]
    assert "VIGENTE / OBSERVADO" in textos and "EXPECTATIVAS (FOCUS)" in textos
    assert textos.index("VIGENTE / OBSERVADO") < textos.index("EXPECTATIVAS (FOCUS)")
    for linha in macro:
        if linha.get("valor") is not None:
            assert linha.get("referencia"), linha["indicador"]


# ------------------------------------------------------------------
# 8. Texto essencial >= 7,5 pt
# ------------------------------------------------------------------

def test_fonte_nota_e_colofao_com_pelo_menos_7_5pt():
    estilos = pdf_mod._estilos()
    for nome in ("fonte", "nota", "colofao"):
        assert estilos[nome].fontSize >= 7.5, nome


# ------------------------------------------------------------------
# 9. Radar não repete fato já publicado nas editorias
# ------------------------------------------------------------------

def _noticia_radar(titulo, veiculo, horas=10, link=None):
    return {"titulo": titulo, "veiculos": [veiculo], "importancia": 50, "tickers": [],
            "link": link or f"https://exemplo.invalid/{abs(hash(titulo))}",
            "data": (SEGUNDA - timedelta(hours=horas)).isoformat()}


def test_radar_descarta_evidencia_ja_publicada_e_explica():
    inicio = datetime(2026, 10, 16, 6, 0, tzinfo=TZ_SP)
    publicada = _noticia_radar("Petrobras eleva produção de petróleo no pré-sal", "Valor Econômico",
                               link="https://x/publicada")
    outra = _noticia_radar("Petróleo Brent sobe e puxa ações de petroleiras", "InfoMoney")
    terceira = _noticia_radar("Preço do petróleo avança com corte da Opep", "Reuters")
    # sem publicados: 3 evidências válidas
    fontes, motivo = rs.evidencias_do_setor("PETRÓLEO & GÁS", [publicada, outra, terceira], inicio, SEGUNDA)
    assert motivo is None and len(fontes) == 3
    # com a publicada: ela sai do radar
    fontes, motivo = rs.evidencias_do_setor("PETRÓLEO & GÁS", [publicada, outra, terceira], inicio, SEGUNDA,
                                            publicados=[{"titulo": "outro", "link": "https://x/publicada"}])
    assert motivo is None
    assert "https://x/publicada" not in {f["link"] for f in fontes}
    # quando o descarte deixa o setor sem evidência, o motivo diz isso
    fontes, motivo = rs.evidencias_do_setor("PETRÓLEO & GÁS", [publicada, outra], inicio, SEGUNDA,
                                            publicados=[{"titulo": publicada["titulo"], "link": None}])
    assert motivo and "já publicada(s) nas editorias" in motivo


def test_montar_edicao_passa_fatos_publicados_ao_radar():
    capturado = {}

    def falso_radar(agora, publicados=None):
        capturado["publicados"] = publicados
        return {"setores": [], "excluidos": [], "plano": [], "historico": []}

    noticias = [{"titulo": "Petrobras eleva produção de petróleo", "link": "https://x/1", "regiao": "BR",
                 "tickers": [], "importancia": 9}]
    with _MultiPatch(**_pools(noticias, data="2026-10-19T06:00:00-03:00"), _radar_setorial=falso_radar):
        ed.montar_edicao(SEGUNDA)
    assert [f["link"] for f in capturado["publicados"]] == ["https://x/1"]


def test_editoria_cuja_unica_materia_e_a_manchete_nao_diz_que_nao_ha_noticia():
    """Caso real (validação de 18/10, 22h24): a única notícia de Empresas
    (Petrobras) abriu a capa e a editoria dizia 'Nenhuma notícia...'."""
    estilos = pdf_mod._estilos()
    manchete = {"titulo": "Petrobras (PETR4) sobe mais de 6%", "importancia": 9}
    flows = pdf_mod._editoria("Empresas e setores", "empresas", [manchete], None, SEGUNDA, estilos, {},
                              excluir=manchete)
    textos = [getattr(f, "text", "") for kt in flows for f in getattr(kt, "_content", [])]
    assert any("manchete da capa" in t for t in textos)
    assert not any("Nenhuma notícia" in t for t in textos)
