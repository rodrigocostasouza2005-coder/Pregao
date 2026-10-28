import { describe, expect, it } from "vitest";
import { classeVariacao, formatarNumero, formatarPct } from "../format";

describe("formatarNumero", () => {
  it("usa vírgula decimal e ponto de milhar (pt-BR)", () => {
    expect(formatarNumero(136218.5, 0)).toBe("136.219");
    expect(formatarNumero(52.79, 2)).toBe("52,79");
  });
});

describe("formatarPct", () => {
  it("antepõe + pra valores positivos, nunca pra negativos", () => {
    expect(formatarPct(2.023)).toBe("+2,02%");
    expect(formatarPct(-2.023)).toBe("-2,02%");
  });
});

describe("classeVariacao", () => {
  it("zero conta como alta (mesmo critério do app Python: >= 0)", () => {
    expect(classeVariacao(0)).toBe("alta");
    expect(classeVariacao(-0.01)).toBe("baixa");
  });
});
