# -*- coding: utf-8 -*-
"""ui/morning_call_tab.py: blocos novos do briefing (resumo executivo,
radar de ações, cenários, alertas) - ver missão "Morning Call: briefing
profissional". Cada função é pura (string in/out), sem sessão
Streamlit real."""
import ui.morning_call_tab as mc

_SINTESE_OK = {
    "ok": True, "atual": True, "modelo": "m",
    "dados": {
        "resumo_executivo": {"texto": "Ibovespa opera em alta.", "ressalvas": "Dólar sem fechamento ainda."},
        "movimentos": [
            {"evento": "Alta do Ibovespa", "fonte": "B3", "data_fonte": "27/10", "por_que_importa": "acompanha exterior",
             "impacto_possivel": "exportadoras", "confianca": "media"},
        ],
        "oportunidades_riscos": [
            {"ativo_ou_setor": "Petróleo", "catalisador": "alta do barril", "argumento_favoravel": "receita maior",
             "argumento_contrario": "custo de insumos", "acompanhar": "preço do Brent", "fonte": "Reuters", "data_fonte": "27/10"},
        ],
        "cenarios": [
            {"tipo": "principal", "cenario": "Alta segue no curto prazo", "condicao": "exterior positivo",
             "sinalizadores": "futuros dos EUA"},
            {"tipo": "alternativo", "cenario": "Correção técnica", "condicao": "realização de lucro", "sinalizadores": ""},
        ],
        "observar_proximas_sessoes": [
            {"item": "Decisão do Fed", "motivo": "pode mudar o humor global", "fonte": "Reuters", "data_fonte": "28/10"},
        ],
        "o_que_nao_sabemos": ["Sem dado recente do Focus Selic."],
    },
}
_SINTESE_INDISPONIVEL = {"ok": False, "motivo": "GROQ_API_KEY não configurada"}


def test_resumo_executivo_mostra_texto_e_ressalvas():
    out = mc._bloco_resumo_executivo_html(_SINTESE_OK)
    assert "Ibovespa opera em alta." in out
    assert "Dólar sem fechamento ainda." in out
    assert "Sem dado recente do Focus Selic." in out


def test_resumo_executivo_indisponivel_nao_quebra():
    out = mc._bloco_resumo_executivo_html(_SINTESE_INDISPONIVEL)
    assert "indisponível" in out.lower()


def test_resumo_executivo_marca_rodada_anterior():
    anterior = {**_SINTESE_OK, "atual": False, "motivo_atual_indisponivel": "cota"}
    out = mc._bloco_resumo_executivo_html(anterior)
    assert "ANÁLISE ANTERIOR" in out and "cota" in out


def test_radar_acoes_mostra_movimento_e_oportunidade_com_chip_interpretacao():
    out = mc._bloco_radar_acoes_html(_SINTESE_OK)
    assert "Alta do Ibovespa" in out and "Petróleo" in out
    assert out.count("INTERPRETAÇÃO") + out.count("PARA INVESTIGAR") >= 2
    assert "A favor:" in out and "Contra:" in out


def test_radar_acoes_vazio_quando_sintese_indisponivel():
    assert mc._bloco_radar_acoes_html(_SINTESE_INDISPONIVEL) == ""


def test_radar_acoes_vazio_quando_sem_movimentos_nem_oportunidades():
    vazio = {"ok": True, "atual": True, "dados": {"movimentos": [], "oportunidades_riscos": []}}
    assert mc._bloco_radar_acoes_html(vazio) == ""


def test_cenarios_preserva_principal_mesmo_fora_da_primeira_posicao():
    sintese = {
        "ok": True, "atual": True,
        "dados": {"cenarios": [
            {"tipo": "alternativo", "cenario": "B"},
            {"tipo": "principal", "cenario": "A"},
        ], "observar_proximas_sessoes": []},
    }
    out = mc._bloco_cenarios_html(sintese)
    assert out.index("CENÁRIO PRINCIPAL") < out.index("CENÁRIO ALTERNATIVO")
    assert "A" in out and "B" in out


def test_cenarios_mostra_o_que_observar():
    out = mc._bloco_cenarios_html(_SINTESE_OK)
    assert "Decisão do Fed" in out and "pode mudar o humor global" in out


def test_cenarios_vazio_quando_sem_cenario_nem_observar():
    vazio = {"ok": True, "atual": True, "dados": {"cenarios": [], "observar_proximas_sessoes": []}}
    assert mc._bloco_cenarios_html(vazio) == ""


def test_alertas_html_vazio_sem_alerta_nem_novidade():
    assert mc._bloco_alertas_html([], []) == ""


def test_alertas_html_mostra_alerta_de_saude_e_novidade():
    alertas = [{"nome": "NEWS (Brasil)", "rotulo_estado": "Fonte indisponível"}]
    out = mc._bloco_alertas_html(alertas, ["VALE3"])
    assert "NEWS (Brasil)" in out and "Fonte indisponível" in out
    assert "VALE3" in out and "Novos no radar" in out
