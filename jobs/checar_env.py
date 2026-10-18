# -*- coding: utf-8 -*-
"""Falha cedo (com anotacao ::error:: no GitHub Actions) se algum secret
obrigatorio nao chegou no ambiente. Em Python (e nao bash/PowerShell) pra
rodar igual no runner Linux da nuvem e no runner self-hosted do PC de casa
(Windows usa PowerShell como shell padrao).

Uso: python -m jobs.checar_env SUPABASE_URL SUPABASE_SECRET_KEY"""
import os
import sys


def faltando(nomes):
    return [nome for nome in nomes if not os.environ.get(nome)]


def main(nomes):
    ausentes = faltando(nomes)
    for nome in ausentes:
        print(f"::error::Configure {nome} em Settings > Secrets and variables > Actions.")
    return 1 if ausentes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
