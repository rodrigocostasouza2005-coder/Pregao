/** Geometria dos gráficos do terminal (SVG desenhado no servidor). Funções
 * puras: recebem os pontos da fonte e devolvem caminhos e marcações em
 * coordenadas de 0 a 100, sem inventar pontos entre as leituras. */

export type PontoGrafico = { t: number; v: number };

/** Períodos aceitos pelo gráfico principal (GraficoPrincipal.tsx) e seu
 * eixo x - cópia client-safe das chaves de PERIODOS em lib/server/
 * yahoo.ts ("server-only", não pode ser importado por Client Component).
 * Mudar um período ali exige espelhar aqui. */
export const PERIODOS_GRAFICO = ["1D", "1S", "1M", "3M", "6M", "1A", "5A"] as const;
export type PeriodoGrafico = (typeof PERIODOS_GRAFICO)[number];

export type EixoX = "hora" | "dia" | "mes" | "ano";

export const EIXO_POR_PERIODO: Record<PeriodoGrafico, EixoX> = { "1D": "hora", "1S": "dia", "1M": "dia", "3M": "dia", "6M": "mes", "1A": "mes", "5A": "ano" };

/** Marcações "redondas" do eixo vertical (1, 2 ou 5 × 10^n: sem 2,5,
 * que pediria uma casa a mais do que o eixo mostra). */
export function ticksBonitos(min: number, max: number, alvo = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) return [min];
  const bruto = (max - min) / alvo;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 5, 10].map((m) => m * mag).find((p) => p >= bruto * (1 - 1e-9)) ?? 10 * mag;
  const saida: number[] = [];
  for (let v = Math.ceil(min / passo) * passo; v <= max + passo * 1e-9; v += passo) saida.push(Number(v.toFixed(10)));
  return saida;
}

export type Geometria = {
  linha: string;
  area: string;
  min: number;
  max: number;
  ticksY: Array<{ v: number; y: number }>;
  /** y (0-100) da linha de referência, se houver */
  yReferencia: number | null;
  ultimo: PontoGrafico;
  primeiro: PontoGrafico;
};

/** Eixo x por ordem dos pontos (como nos terminais: noites e fins de
 * semana não abrem buracos); eixo y com folga de 6% e referência incluída. */
export function geometria(pontos: PontoGrafico[], opcoes: { referencia?: number | null; degrau?: boolean } = {}): Geometria | null {
  if (pontos.length < 2) return null;
  const valores = pontos.map((p) => p.v);
  const ref = opcoes.referencia ?? null;
  let min = Math.min(...valores, ...(ref !== null ? [ref] : []));
  let max = Math.max(...valores, ...(ref !== null ? [ref] : []));
  const folga = (max - min || Math.abs(max) || 1) * 0.06;
  min -= folga;
  max += folga;
  const x = (i: number) => (i / (pontos.length - 1)) * 100;
  const y = (v: number) => 100 - ((v - min) / (max - min)) * 100;
  const f = (n: number) => n.toFixed(2);
  let linha = `M${f(x(0))},${f(y(pontos[0].v))}`;
  for (let i = 1; i < pontos.length; i++) {
    if (opcoes.degrau) linha += `H${f(x(i))}`;
    linha += `${opcoes.degrau ? "V" : `L${f(x(i))},`}${f(y(pontos[i].v))}`;
  }
  return {
    linha,
    area: `${linha}V100H0Z`,
    min,
    max,
    ticksY: ticksBonitos(min, max).map((v) => ({ v, y: y(v) })).filter((t) => t.y >= 4 && t.y <= 96),
    yReferencia: ref !== null ? y(ref) : null,
    ultimo: pontos.at(-1) as PontoGrafico,
    primeiro: pontos[0],
  };
}

export type VelaGrafico = { t: number; open: number; high: number; low: number; close: number };

export type ItemVela = { x: number; largura: number; yAlta: number; yBaixa: number; yAbre: number; yFecha: number; alta: boolean };

export type GeometriaVelas = {
  min: number;
  max: number;
  ticksY: Array<{ v: number; y: number }>;
  yReferencia: number | null;
  itens: ItemVela[];
  ultimo: VelaGrafico;
  primeiro: VelaGrafico;
};

/** Mesma régua de `geometria` (escala com folga de 6%, referência incluída
 * na escala, nunca interpolada), mas pro candle: a faixa considera os
 * máximos/mínimos de CADA barra (high/low), não só o fechamento. */
export function geometriaVelas(velas: VelaGrafico[], opcoes: { referencia?: number | null } = {}): GeometriaVelas | null {
  if (velas.length < 2) return null;
  const ref = opcoes.referencia ?? null;
  let min = Math.min(...velas.map((v) => v.low), ...(ref !== null ? [ref] : []));
  let max = Math.max(...velas.map((v) => v.high), ...(ref !== null ? [ref] : []));
  const folga = (max - min || Math.abs(max) || 1) * 0.06;
  min -= folga;
  max += folga;
  const y = (v: number) => 100 - ((v - min) / (max - min)) * 100;
  const n = velas.length;
  const slot = 100 / n;
  const largura = Math.min(slot * 0.62, 3.2);
  const itens = velas.map((v, i) => ({
    x: i * slot + slot / 2,
    largura,
    yAlta: y(v.high),
    yBaixa: y(v.low),
    yAbre: y(v.open),
    yFecha: y(v.close),
    alta: v.close >= v.open,
  }));
  return {
    min,
    max,
    ticksY: ticksBonitos(min, max).map((v) => ({ v, y: y(v) })).filter((t) => t.y >= 4 && t.y <= 96),
    yReferencia: ref !== null ? y(ref) : null,
    itens,
    ultimo: velas.at(-1) as VelaGrafico,
    primeiro: velas[0],
  };
}

/** Índices dos rótulos do eixo x: um a cada mudança de dia/mês/ano
 * (conforme o período), no máximo `maximo` rótulos e nunca dois mais
 * próximos que 1/(maximo+1) da largura (rótulos não se sobrepõem). */
export function marcasX(pontos: PontoGrafico[], chave: (t: number) => string, maximo = 6): number[] {
  const trocas: number[] = [];
  for (let i = 1; i < pontos.length; i++) {
    if (chave(pontos[i].t) !== chave(pontos[i - 1].t)) trocas.push(i);
  }
  const passo = Math.max(1, Math.ceil(trocas.length / maximo));
  const distancia = (pontos.length - 1) / (maximo + 1);
  const saida: number[] = [];
  for (const i of trocas.filter((_, n) => n % passo === 0)) {
    if (i >= distancia / 2 && (!saida.length || i - (saida.at(-1) as number) >= distancia)) saida.push(i);
  }
  return saida;
}
