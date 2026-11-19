# -*- coding: utf-8 -*-
"""Testes de config.sintese_ia_comite_ativa() / config.
limite_sinteses_ia_comite_por_noite() - missão "PREGÃO 2.3-B — fiação
real da síntese de IA no Comitê", 2026-11-13.

A auditoria anterior (docs/auditoria-comite-20261113.md) confirmou que a
camada híbrida de IA (Groq) do Comitê funciona de verdade, mas nenhum
caminho de produção (jobs/comite_noturno.py, ui/coordenador_tab.py)
acionava - esta missão fia o caminho real, mas MANTÉM a ativação
DESLIGADA por padrão. Estes testes garantem que o default real é False
(nunca presumido "ativo" por engano) e que a variável de ambiente tem
prioridade sobre st.secrets, mesmo padrão de config.obter_credenciais_groq()
(ver tests/test_config_groq.py)."""
import os
from unittest.mock import patch

import config


def test_sintese_ia_comite_ativa_default_e_false_sem_nenhuma_config():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SINTESE_IA_COMITE_ATIVA", None)
        with patch("streamlit.secrets", {}):
            assert config.sintese_ia_comite_ativa() is False


def test_sintese_ia_comite_ativa_variavel_de_ambiente_liga():
    with patch.dict(os.environ, {"SINTESE_IA_COMITE_ATIVA": "true"}, clear=False):
        assert config.sintese_ia_comite_ativa() is True


def test_sintese_ia_comite_ativa_variavel_de_ambiente_false_explicito():
    with patch.dict(os.environ, {"SINTESE_IA_COMITE_ATIVA": "false"}, clear=False):
        assert config.sintese_ia_comite_ativa() is False


def test_sintese_ia_comite_ativa_cai_pro_secrets_quando_sem_env():
    class _SecretsFake(dict):
        def get(self, chave, default=None):
            if chave == "comite":
                return {"sintese_ia_ativa": True}
            return super().get(chave, default)

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SINTESE_IA_COMITE_ATIVA", None)
        with patch("streamlit.secrets", _SecretsFake()):
            assert config.sintese_ia_comite_ativa() is True


def test_limite_sinteses_ia_comite_por_noite_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MAX_SINTESES_IA_COMITE_POR_NOITE", None)
        with patch("streamlit.secrets", {}):
            assert config.limite_sinteses_ia_comite_por_noite() == config.MAX_SINTESES_IA_COMITE_POR_NOITE_PADRAO


def test_limite_sinteses_ia_comite_por_noite_variavel_de_ambiente():
    with patch.dict(os.environ, {"MAX_SINTESES_IA_COMITE_POR_NOITE": "5"}, clear=False):
        assert config.limite_sinteses_ia_comite_por_noite() == 5


def test_limite_sinteses_ia_comite_por_noite_valor_invalido_cai_pro_default():
    with patch.dict(os.environ, {"MAX_SINTESES_IA_COMITE_POR_NOITE": "nao-e-numero"}, clear=False):
        with patch("streamlit.secrets", {}):
            assert config.limite_sinteses_ia_comite_por_noite() == config.MAX_SINTESES_IA_COMITE_POR_NOITE_PADRAO
