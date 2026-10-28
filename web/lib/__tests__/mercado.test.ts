import { describe, expect, it } from "vitest";
import {
  calcularAltasBaixas,
  calcularDesempenhoSetorial,
  calcularMaisNegociados,
  concentracaoSetorial,
  type PapelPanorama,
} from "../mercado";

function papel(partial: Partial<PapelPanorama> & { ticker: string }): PapelPanorama {
  return {
    preco: 10,
    variacaoPct: 0,
    volume: 1000,
    nome: null,
    setor: "Outros",
    volumeFinanceiro: 10000,
    ...partial,
  };
}

describe("calcularAltasBaixas", () => {
  it("separa altas e baixas, ordenadas pela variação mais extrema", () => {
    const papeis = [
      papel({ ticker: "A", variacaoPct: 5 }),
      papel({ ticker: "B", variacaoPct: 1 }),
      papel({ ticker: "C", variacaoPct: -8 }),
      papel({ ticker: "D", variacaoPct: -2 }),
    ];
    const { altas, baixas } = calcularAltasBaixas(papeis, 5);
    expect(altas.map((p) => p.ticker)).toEqual(["A", "B"]);
    expect(baixas.map((p) => p.ticker)).toEqual(["C", "D"]);
  });

  it("respeita o limite n por grupo", () => {
    const papeis = Array.from({ length: 10 }, (_, i) => papel({ ticker: `T${i}`, variacaoPct: i + 1 }));
    const { altas } = calcularAltasBaixas(papeis, 3);
    expect(altas).toHaveLength(3);
  });

  it("papel com variação exatamente 0 não entra em nenhum dos dois grupos", () => {
    const papeis = [papel({ ticker: "Z", variacaoPct: 0 })];
    const { altas, baixas } = calcularAltasBaixas(papeis, 5);
    expect(altas).toHaveLength(0);
    expect(baixas).toHaveLength(0);
  });
});

describe("calcularDesempenhoSetorial", () => {
  it("calcula a média de variação por setor, ordenado do melhor pro pior", () => {
    const papeis = [
      papel({ ticker: "A", setor: "Bancos", variacaoPct: 2 }),
      papel({ ticker: "B", setor: "Bancos", variacaoPct: 4 }),
      papel({ ticker: "C", setor: "Varejo", variacaoPct: -6 }),
    ];
    const resultado = calcularDesempenhoSetorial(papeis);
    expect(resultado[0]).toEqual({ setor: "Bancos", variacaoMediaPct: 3, nPapeis: 2 });
    expect(resultado[1]).toEqual({ setor: "Varejo", variacaoMediaPct: -6, nPapeis: 1 });
  });
});

describe("calcularMaisNegociados", () => {
  it("ordena por volume financeiro decrescente e corta em n", () => {
    const papeis = [
      papel({ ticker: "A", volumeFinanceiro: 100 }),
      papel({ ticker: "B", volumeFinanceiro: 500 }),
      papel({ ticker: "C", volumeFinanceiro: 300 }),
    ];
    const resultado = calcularMaisNegociados(papeis, 2);
    expect(resultado.map((p) => p.ticker)).toEqual(["B", "C"]);
  });
});

describe("concentracaoSetorial", () => {
  it("detecta setor com maioria clara (>=3) na amostra", () => {
    const amostra = [
      papel({ ticker: "A", setor: "Petróleo e Gás" }),
      papel({ ticker: "B", setor: "Petróleo e Gás" }),
      papel({ ticker: "C", setor: "Petróleo e Gás" }),
      papel({ ticker: "D", setor: "Bancos" }),
    ];
    const resultado = concentracaoSetorial([], amostra);
    expect(resultado).toEqual({ setor: "Petróleo e Gás", qtd: 3, total: 4 });
  });

  it("retorna null quando não há concentração clara (<3 do mesmo setor)", () => {
    const amostra = [
      papel({ ticker: "A", setor: "Petróleo e Gás" }),
      papel({ ticker: "B", setor: "Bancos" }),
    ];
    expect(concentracaoSetorial([], amostra)).toBeNull();
  });

  it("amostra vazia retorna null sem lançar exceção", () => {
    expect(concentracaoSetorial([], [])).toBeNull();
  });
});
