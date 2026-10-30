import { describe, expect, it } from "vitest";

import { altasEBaixas, ATIVOS_FITA_PADRAO, maisNegociados, normalizarSimbolo, type Acao } from "@/lib/server/dominio/mercado";
import type { Cotacao } from "@/lib/server/yahoo";

function cotacao(parcial: Partial<Cotacao>): Cotacao {
  return { simbolo: "X", preco: 10, variacaoPct: 0, fechamentoAnterior: 10, negocioEm: null, sessao: null, moeda: "BRL", volumeFinanceiro: null, ...parcial };
}

function acao(ticker: string, variacaoPct: number, volumeFinanceiro: number | null): Acao {
  return { ticker, setor: "Setor", cotacao: cotacao({ variacaoPct, volumeFinanceiro }) };
}

describe("normalizarSimbolo", () => {
  it("adiciona .SA em ticker da B3 (4 letras + 1-2 dígitos)", () => {
    expect(normalizarSimbolo("petr4")).toBe("PETR4.SA");
    expect(normalizarSimbolo("WEGE3")).toBe("WEGE3.SA");
    expect(normalizarSimbolo("brap4")).toBe("BRAP4.SA");
  });
  it("não toca em índices, FX e futuros (já vêm no formato da fonte)", () => {
    expect(normalizarSimbolo("^BVSP")).toBe("^BVSP");
    expect(normalizarSimbolo("USDBRL=X")).toBe("USDBRL=X");
    expect(normalizarSimbolo("BTC-USD")).toBe("BTC-USD");
  });
});

describe("maisNegociados", () => {
  it("ordena por volume financeiro (preço × quantidade), não por variação", () => {
    const acoes = [acao("A", 10, 100), acao("B", -5, 900), acao("C", 2, 500)];
    const top = maisNegociados(acoes, 2);
    expect(top.map((a) => a.ticker)).toEqual(["B", "C"]);
  });
  it("nunca inclui ação sem volume financeiro na leitura (nunca mostra zero inventado)", () => {
    const acoes = [acao("A", 1, null), acao("B", 2, 300)];
    expect(maisNegociados(acoes).map((a) => a.ticker)).toEqual(["B"]);
  });
});

describe("altasEBaixas", () => {
  it("separa altas e baixas sem misturar as duas listas", () => {
    const acoes = [acao("UP1", 5, 1), acao("UP2", 2, 1), acao("DOWN1", -3, 1), acao("FLAT", 0, 1)];
    const { altas, baixas } = altasEBaixas(acoes);
    expect(altas.map((a) => a.ticker)).toEqual(["UP1", "UP2"]);
    expect(baixas.map((a) => a.ticker)).toEqual(["DOWN1"]);
  });
});

describe("ATIVOS_FITA_PADRAO", () => {
  it("são todos tickers reais do universo Ibovespa (contratos/ibovespa.json)", async () => {
    const ibovespa = (await import("@/contratos/ibovespa.json")).default as { setores: Record<string, string> };
    for (const t of ATIVOS_FITA_PADRAO) expect(ibovespa.setores[t]).toBeDefined();
  });
});
