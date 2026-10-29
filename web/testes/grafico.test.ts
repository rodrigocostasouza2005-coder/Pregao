import { describe, expect, it } from "vitest";

import { geometria, marcasX, ticksBonitos } from "@/lib/grafico";

describe("ticksBonitos", () => {
  it("usa passos redondos dentro do intervalo", () => {
    expect(ticksBonitos(170120, 171980)).toEqual([170500, 171000, 171500]);
    expect(ticksBonitos(5.31, 5.39)).toEqual([5.32, 5.34, 5.36, 5.38]);
  });
  it("não quebra com intervalo nulo ou inválido", () => {
    expect(ticksBonitos(2, 2)).toEqual([2]);
    expect(ticksBonitos(NaN, 1)).toEqual([]);
  });
});

describe("geometria", () => {
  const pts = [10, 12, 11, 15].map((v, i) => ({ t: i, v }));

  it("exige ao menos dois pontos (não desenha com um só)", () => {
    expect(geometria([{ t: 0, v: 1 }])).toBeNull();
  });

  it("um vértice por leitura, sem pontos inventados", () => {
    const g = geometria(pts)!;
    expect(g.linha.match(/[ML]/g)).toHaveLength(pts.length);
    expect(g.ultimo.v).toBe(15);
    expect(g.primeiro.v).toBe(10);
  });

  it("inclui a referência na escala, mesmo fora da faixa dos preços", () => {
    const g = geometria(pts, { referencia: 20 })!;
    expect(g.max).toBeGreaterThan(20);
    expect(g.yReferencia).toBeGreaterThan(0);
    expect(g.yReferencia).toBeLessThan(10);
  });

  it("em degraus, cada mudança é horizontal e depois vertical", () => {
    const g = geometria(pts, { degrau: true })!;
    expect(g.linha).not.toContain("L");
    expect(g.linha.match(/H/g)).toHaveLength(pts.length - 1);
  });
});

describe("marcasX", () => {
  it("marca cada troca de chave e respeita o máximo", () => {
    const pontos = Array.from({ length: 30 }, (_, i) => ({ t: i, v: 1 }));
    expect(marcasX(pontos, (t) => String(Math.floor(t / 10)))).toEqual([0, 10, 20]);
    expect(marcasX(pontos, (t) => String(t), 5).length).toBeLessThanOrEqual(5);
  });
});
