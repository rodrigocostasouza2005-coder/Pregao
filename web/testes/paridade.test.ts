import { describe, expect, it } from "vitest";

import casos from "@/contratos/casos_editoriais.json";
import { editoriaPorAssunto, eNoticiaDeEmpresa, eOpiniao, foraDePauta, temRelevanciaFinanceira } from "@/lib/regrasEditoriais";

type Caso = { titulo: string; regiao_coleta: "BR" | "INT"; editoria: string; opiniao: boolean; fora_de_pauta: boolean; empresa: boolean; relevante: boolean };

/** Resultados gerados pelo PRÓPRIO Python (scripts/exportar_contratos_web.py):
 * a interface web tem que classificar igual ao Morning Call. */
describe("paridade das regras editoriais TypeScript x Python", () => {
  for (const c of (casos as { casos: Caso[] }).casos) {
    it(c.titulo.slice(0, 70), () => {
      expect({
        editoria: editoriaPorAssunto(c.titulo, c.regiao_coleta),
        opiniao: eOpiniao(c.titulo),
        fora_de_pauta: foraDePauta(c.titulo),
        empresa: eNoticiaDeEmpresa(c.titulo),
        relevante: temRelevanciaFinanceira(c.titulo),
      }).toEqual({ editoria: c.editoria, opiniao: c.opiniao, fora_de_pauta: c.fora_de_pauta, empresa: c.empresa, relevante: c.relevante });
    });
  }
});
