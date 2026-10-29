# -*- coding: utf-8 -*-
"""Exporta para web/contratos/*.json as definições do Pregão em Python que
a interface Next.js (web/) precisa conhecer - sem duplicar à mão: lista do
Ibovespa por setor (config.IBOVESPA_SETORES), casas de research
(data/research.CASAS) e o registro/estados de saúde dos coletores
(data/saude_dados). Nenhum dado de mercado: só configuração.

Uso: python scripts/exportar_contratos_web.py
tests/test_contratos_web.py falha se os JSONs ficarem desatualizados."""
import json
import re
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
        # Só casas com fonte coletável de verdade (disponivel=True, ver
        # data/research/__init__.py) - casas sem nenhum canal público
        # (ex: Itaú BBA/Santander/Bradesco BBI, investigadas 2026-10-29)
        # não entram aqui: não faz sentido um filtro na UI do Research
        # pra uma casa que nunca vai ter item, ela já fica registrada na
        # limitação via motivo_indisponivel no app Python.
        "casas_research.json": {
            "casas": [{"id": c["id"], "nome": c["nome"], "fonte": c.get("fonte"),
                       "ativa_por_padrao": bool(c.get("ativa_por_padrao"))}
                      for c in CASAS if c.get("disponivel")],
        },
        "regras_editoriais.json": _regras_editoriais(),
        "casos_editoriais.json": _casos_editoriais(),
        "saude_coletores.json": {
            "estados": dict(saude_dados.ESTADOS),
            "termos_indisponibilidade": list(saude_dados._TERMOS_INDISPONIBILIDADE),
            "coletores": [{k: c.get(k) for k in ("nome", "fonte", "categoria", "frequencia_esperada",
                                                   "idade_maxima_horas", "instrumentado")}
                          for c in saude_dados.REGISTRO_COLETORES],
        },
    }


def _regras_editoriais() -> dict:
    """Regras editoriais do Morning Call (data/morning_call_editorial.py)
    que o feed de notícias da web aplica igual: editoria pelo assunto,
    opinião/serviço fora e piso de relevância financeira. Regex são
    exportadas pelo padrão (sintaxe compatível com JavaScript)."""
    from data import morning_call_editorial as ed

    return {
        "marcadores_exterior": list(ed._MARCADORES_EXTERIOR),
        "marcadores_brasil": list(ed._MARCADORES_BRASIL),
        "termos_opiniao": list(ed._TERMOS_OPINIAO),
        "termos_financeiros": list(ed._TERMOS_FINANCEIROS),
        "termos_impacto_mercado": list(ed._TERMOS_IMPACTO_MERCADO),
        "servico_financas_pessoais": list(ed._SERVICO_FINANCAS_PESSOAIS),
        "termos_fora_de_pauta": list(ed._TERMOS_FORA_DE_PAUTA),
        "nomes_empresas": sorted(ed._NOMES_EMPRESAS),  # vem de um set: ordem estável
        "regex": {
            nome: {"padrao": rx.pattern, "flags": "i" if rx.flags & re.IGNORECASE else ""}
            for nome, rx in (
                ("rotulo_opiniao", ed._ROTULO_OPINIAO),
                ("carta_de_leitor", ed._CARTA_DE_LEITOR),
                ("carta_com_citacao", ed._CARTA_COM_CITACAO),
                ("formato_servico", ed._FORMATO_SERVICO),
                ("sem_sentido_economico", ed._SEM_SENTIDO_ECONOMICO),
                ("inicio_resumo_de_pregao", ed._INICIO_RESUMO_DE_PREGAO),
                ("ticker_no_titulo", ed._TICKER_NO_TITULO),
            )
        },
    }


# Manchetes reais (edições de 18 e 19/10/2026 e validação de 29/10) para o
# teste de paridade TypeScript x Python (web/testes/paridade.test.ts).
_TITULOS_PARIDADE = [
    ("O Estelionato Eleitoral e a Irresponsabilidade Fiscal do Governo Lula", "BR"),
    ("Lula desafia Flávio Bolsonaro a abrir sigilos bancário, telefônico e fiscal em debate", "BR"),
    ("Saiba como emitir a nova Certidão Única de Débitos do Estado de São Paulo", "BR"),
    ("Saiba como fica o IR com a reforma tributária", "BR"),
    ("Déficit orçamentário dos EUA se aproxima de US$ 2 trilhões no ano fiscal de 2026", "BR"),
    ("Bitcoin se mantém acima de US$ 80 mil enquanto os mercados reduzem apostas em alta de juros pelo Fed", "BR"),
    ("Brazil central bank holds Selic at 15%", "INT"),
    ("Petrobras (PETR4) sobe mais de 6% e escapa do tombo do Ibovespa", "BR"),
    ("Vale a pena investir em CDB?", "BR"),
    ("Ibovespa sobe com Petrobras e Vale; dólar cai", "BR"),
    ("Tesouro Selic, Tesouro Reserva ou CDB: qual rende mais", "BR"),
    ("\u2018My husband suffered a massive stroke at 53\u2019: I\u2019m 64 and will rent for the rest of my life", "INT"),
    ("I'm 63 and diagnosed with lymphoma. Should I take my Social Security next year?", "INT"),
    ("OpenAI bugging suspect WhatsApp'ed Saudi royal days before arrest, feds reveal", "INT"),
    ("Celebrity chef opens new restaurant in Manhattan", "INT"),
    ("Governo central tem superávit primário de R$ 4,839 bilhões em setembro", "BR"),
    ("Resultado da Quina concurso 6900", "BR"),
    ("Magazine Luiza anuncia nova rodada de reestruturação", "BR"),
    ("Tech stocks stumbled. Now comes a crucial week for Wall Street.", "INT"),
    ("Opinião: o Copom errou ao manter os juros", "BR"),
]


def _casos_editoriais() -> dict:
    from data import morning_call_editorial as ed

    return {"casos": [
        {"titulo": t, "regiao_coleta": r, "editoria": ed.editoria_por_assunto(t, r), "opiniao": ed.e_opiniao(t),
         "fora_de_pauta": ed._fora_de_pauta(t), "empresa": ed.e_noticia_de_empresa(t),
         "relevante": ed.tem_relevancia_financeira({"titulo": t})}
        for t, r in _TITULOS_PARIDADE
    ]}


def serializar(conteudo) -> str:
    return json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in contratos().items():
        (DESTINO / nome).write_text(serializar(conteudo), encoding="utf-8")
        print(f"web/contratos/{nome}")


if __name__ == "__main__":
    main()
