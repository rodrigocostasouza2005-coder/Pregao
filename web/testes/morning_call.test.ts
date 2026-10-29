import { describe, expect, it } from "vitest";

import { secoes } from "@/lib/server/dominio/morningCall";

describe("seções do Morning Call (texto do e-mail enviado)", () => {
  it("separa as seções numeradas e as linhas", () => {
    const texto = "MORNING CALL — 19/10/2026\n\n1. RESUMO EXECUTIVO\n- Ibovespa: alta de 0,54%\n\n2. BRASIL\n- Dólar: 5,07\nLIMITAÇÕES\n- Fontes gratuitas";
    const s = secoes(texto);
    expect(s.map((x) => x.titulo)).toEqual(["RESUMO EXECUTIVO", "BRASIL", "LIMITAÇÕES"]);
    expect(s[0].linhas).toEqual(["- Ibovespa: alta de 0,54%"]);
  });
});
