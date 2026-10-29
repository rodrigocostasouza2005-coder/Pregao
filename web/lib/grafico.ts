/** Geometria dos gráficos do terminal (SVG desenhado no servidor). Funções
 * puras: recebem os pontos da fonte e devolvem caminhos e marcações em
 * coordenadas de 0 a 100, sem inventar pontos entre as leituras. */

export type PontoGrafico = { t: number; v: number };

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

/** Índices dos rótulos do eixo x: um a cada mudança de dia/mês/ano
 * (conforme o período), no máximo `maximo` rótulos. */
export function marcasX(pontos: PontoGrafico[], chave: (t: number) => string, maximo = 6): number[] {
  const trocas: number[] = [];
  for (let i = 0; i < pontos.length; i++) {
    if (i === 0 || chave(pontos[i].t) !== chave(pontos[i - 1].t)) trocas.push(i);
  }
  if (trocas.length <= maximo) return trocas;
  const passo = Math.ceil(trocas.length / maximo);
  return trocas.filter((_, n) => n % passo === 0);
}
