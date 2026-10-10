# -*- coding: utf-8 -*-
"""Guarda de regressao: todo arquivo .py do projeto precisa compilar
limpo (sem SyntaxError) na versao de Python realmente usada em produção/
dev (ver .devcontainer/devcontainer.json e BACKLOG.md - Python 3.11).

Existe porque um bug real passou batido por 2 commits consecutivos
(2026-10-09/10, `ui/mercado_tab.py` e `app.py`): f-string com aspas
duplas REPETIDAS dentro de uma expressao `{...}` que ja estava dentro de
uma f-string delimitada por aspas duplas (`f"...class='{"alta" if ...
else "baixa"}'..."`) - sintaxe so' valida a partir do Python 3.12 (PEP
701); em 3.11 e' SyntaxError na importacao do modulo, o que quebraria
TODO o app (MERCADO, VISAO GERAL e a tabela de destaques do dia em
app.py importam esses modulos). BACKLOG.md ja documentava "compileall"
como parte da validacao visual, mas isso nunca foi automatizado na
suite - rodava so' manualmente, quando alguem lembrava. Esta checagem
fecha essa lacuna: roda sempre, em toda execucao da suite (pytest ou
standalone).

Uso: python tests/test_sintaxe_modulos.py (python do .venv do projeto)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_RAIZ = Path(__file__).parent.parent
_IGNORAR_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _arquivos_py():
    for p in sorted(_RAIZ.rglob("*.py")):
        if any(parte in _IGNORAR_DIRS for parte in p.parts):
            continue
        yield p


def test_todo_arquivo_py_do_projeto_compila_sem_syntaxerror():
    erros = []
    total = 0
    for caminho in _arquivos_py():
        total += 1
        src = caminho.read_text(encoding="utf-8")
        try:
            compile(src, str(caminho), "exec")
        except SyntaxError as e:
            erros.append(f"{caminho.relative_to(_RAIZ)}:{e.lineno}: {e.msg}")
    _checar(
        f"todos os {total} arquivo(s) .py compilam limpo (sem SyntaxError)",
        not erros, f"erros={erros}" if erros else "",
    )


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
    print("TODOS OS ARQUIVOS .PY COMPILAM LIMPO")
