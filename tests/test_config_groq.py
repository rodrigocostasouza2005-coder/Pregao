# -*- coding: utf-8 -*-
"""Testes de config.obter_credenciais_groq() - achado real 2026-10-15
(auditoria de persistência): a função só lia st.secrets, nunca
os.getenv("GROQ_API_KEY") - diferente de data/supabase_client.py, que já
tinha o fallback de variável de ambiente pras tarefas externas (GitHub
Actions) desde o PR #31. Sem isso, mesmo configurando o secret
GROQ_API_KEY no GitHub e passando via env: no workflow,
pregerar_resumos_news nunca conseguia uma api_key de verdade -
confirmado em produção: 24 de 25 resumos "gerados" na run real
retornavam 'GROQ_API_KEY não configurada em st.secrets' (ver
coletores-nuvem.yml, run 38803968174).

Uso: python tests/test_config_groq.py (python do .venv do projeto)."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def test_1a_variavel_de_ambiente_tem_prioridade():
    with patch.dict(os.environ, {"GROQ_API_KEY": "chave-do-ambiente"}, clear=False):
        api_key, _modelo = config.obter_credenciais_groq()
    _checar("1a GROQ_API_KEY do ambiente é usada", api_key == "chave-do-ambiente", f"(api_key={api_key!r})")


def test_1b_sem_variavel_de_ambiente_cai_pro_st_secrets():
    class _SecretsFake(dict):
        def get(self, chave, default=None):
            if chave == "groq":
                return {"api_key": "chave-do-secrets-toml"}
            return super().get(chave, default)

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("GROQ_API_KEY", None)
        with patch("streamlit.secrets", _SecretsFake()):
            api_key, _modelo = config.obter_credenciais_groq()
    _checar("1b sem variável de ambiente, usa st.secrets", api_key == "chave-do-secrets-toml", f"(api_key={api_key!r})")


def test_1c_sem_nenhuma_credencial_devolve_none_sem_lancar():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("GROQ_API_KEY", None)
        with patch("streamlit.secrets", {}):
            api_key, modelo = config.obter_credenciais_groq()
    _checar("1d sem credencial nenhuma -> api_key None", api_key is None, f"(api_key={api_key!r})")
    _checar("1e modelo cai pro padrão mesmo sem credencial", modelo == config.GROQ_MODELO_PADRAO, f"(modelo={modelo!r})")


def test_1f_variavel_de_ambiente_vazia_nao_conta_como_configurada():
    """string vazia (secret configurado só com env: mas sem valor real,
    ex: repo sem o secret definido) nunca deve ser tratada como chave
    válida - precisa continuar None pra quem chama mostrar o motivo certo."""
    with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
        with patch("streamlit.secrets", {}):
            api_key, _modelo = config.obter_credenciais_groq()
    _checar("1g string vazia -> None (nunca uma chave 'vazia' válida)", api_key is None, f"(api_key={api_key!r})")


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
    print("TODOS OS TESTES DE CREDENCIAL GROQ PASSARAM")
