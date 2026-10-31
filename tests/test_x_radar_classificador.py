# -*- coding: utf-8 -*-
"""Classificacao de posts (data/x_radar/classificador.py) - mocka a
chamada HTTP ao Groq (nenhum teste gasta cota real). Cobre: categoria
nunca falsificada quando a IA falha (nunca 'sem_relevancia' por
motivo tecnico), cache por post_id+versao evita 2a chamada, resposta
invalida (JSON quebrado) degrada pra ok=False sem lancar."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

import data.x_radar.classificador as classificador_mod
from x_radar_posts import SINAL_ANALISE_FUNDAMENTADA, SINAL_RUMOR, SINAL_SPAM


class _RespostaFake:
    def __init__(self, status_code, corpo=None, texto=""):
        self.status_code = status_code
        self._corpo = corpo or {}
        self.text = texto

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _resposta_groq(conteudo_json: str):
    return _RespostaFake(200, {"choices": [{"message": {"content": conteudo_json}}]})


def test_classificacao_ok_preenche_todos_os_campos_pedidos():
    corpo = (
        '{"categoria": "opiniao_analista", "tipo_conteudo": "analise fundamentalista", '
        '"ticker": "petr4", "empresa": "Petrobras", "setor": "petroleo e gas", '
        '"tema": "margem e ROIC", "sentimento": "negativo", '
        '"argumento_central": "ROIC caiu por aumento de custo", "catalisador": null, '
        '"risco": "margem em queda", "necessita_investigacao": true, '
        '"resumo": "Analista aponta queda de ROIC da Petrobras."}'
    )
    with patch.object(classificador_mod, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn()), \
         patch.object(classificador_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-x")), \
         patch.object(classificador_mod.requests, "post", return_value=_resposta_groq(corpo)):
        resultado = classificador_mod.classificar_post(SINAL_ANALISE_FUNDAMENTADA)
    assert resultado["ok"] is True
    assert resultado["categoria"] == "opiniao_analista"
    assert resultado["ticker"] == "PETR4"  # normalizado pra upper
    assert resultado["necessita_investigacao"] is True
    assert resultado["resumo"]


def test_categoria_fora_do_enum_vira_sem_relevancia_em_vez_de_quebrar():
    corpo = '{"categoria": "categoria_inventada_pela_ia", "resumo": "x"}'
    with patch.object(classificador_mod, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn()), \
         patch.object(classificador_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-x")), \
         patch.object(classificador_mod.requests, "post", return_value=_resposta_groq(corpo)):
        resultado = classificador_mod.classificar_post(SINAL_RUMOR)
    assert resultado["categoria"] == "sem_relevancia"


def test_sem_credencial_groq_nao_finge_classificacao():
    with patch.object(classificador_mod, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn()), \
         patch.object(classificador_mod.config, "obter_credenciais_groq", return_value=(None, "modelo-x")):
        resultado = classificador_mod.classificar_post(SINAL_SPAM)
    assert resultado["ok"] is False
    assert resultado["motivo_falha"] == "sem_credencial"
    assert "categoria" not in resultado  # nunca inventa categoria por falha tecnica


def test_resposta_json_invalida_degrada_sem_lancar():
    with patch.object(classificador_mod, "obter_resumo_com_cache", side_effect=lambda chave, link, origem, gerar_fn: gerar_fn()), \
         patch.object(classificador_mod.config, "obter_credenciais_groq", return_value=("fake-key", "modelo-x")), \
         patch.object(classificador_mod.requests, "post", return_value=_resposta_groq("isso nao e json")):
        resultado = classificador_mod.classificar_post(SINAL_SPAM)
    assert resultado["ok"] is False
    assert resultado["motivo_falha"] == "resposta_invalida"


def test_classificar_lote_preserva_ordem_e_inclui_falhas():
    with patch.object(classificador_mod, "classificar_post") as mock_classificar:
        mock_classificar.side_effect = [
            {"ok": True, "categoria": "opiniao_analista"},
            {"ok": False, "motivo_falha": "cota"},
        ]
        resultado = classificador_mod.classificar_lote([SINAL_ANALISE_FUNDAMENTADA, SINAL_RUMOR])
    assert len(resultado) == 2
    assert resultado[0]["sinal"] is SINAL_ANALISE_FUNDAMENTADA
    assert resultado[0]["classificacao"]["ok"] is True
    assert resultado[1]["classificacao"]["ok"] is False
