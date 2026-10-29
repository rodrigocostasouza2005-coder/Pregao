# -*- coding: utf-8 -*-
"""Exporta para web/contratos/*.json as definições do Pregão em Python que
a interface Next.js (web/) precisa conhecer - sem duplicar à mão: lista do
Ibovespa por setor (config.IBOVESPA_SETORES), casas de research
(data/research.CASAS) e o registro/estados de saúde dos coletores
(data/saude_dados). Nenhum dado de mercado: só configuração.

Uso: python scripts/exportar_contratos_web.py
tests/test_contratos_web.py falha se os JSONs ficarem desatualizados."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DESTINO = RAIZ / "web" / "contratos"


def contratos() -> dict:
    import config
    from data import saude_dados
    from data.research import CASAS

    return {
        "ibovespa.json": {"setores": dict(config.IBOVESPA_SETORES)},
        "casas_research.json": {
            "casas": [{"id": c["id"], "nome": c["nome"], "fonte": c.get("fonte"),
                       "ativa_por_padrao": bool(c.get("ativa_por_padrao"))} for c in CASAS],
        },
        "saude_coletores.json": {
            "estados": dict(saude_dados.ESTADOS),
            "termos_indisponibilidade": list(saude_dados._TERMOS_INDISPONIBILIDADE),
            "coletores": [{k: c.get(k) for k in ("nome", "fonte", "categoria", "frequencia_esperada",
                                                   "idade_maxima_horas", "instrumentado")}
                          for c in saude_dados.REGISTRO_COLETORES],
        },
    }


def serializar(conteudo) -> str:
    return json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in contratos().items():
        (DESTINO / nome).write_text(serializar(conteudo), encoding="utf-8")
        print(f"web/contratos/{nome}")


if __name__ == "__main__":
    main()
