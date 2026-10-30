import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";

const FONTE = "Yahoo Finance";
const UA = "Mozilla/5.0 (compatible; PregaoTerminal/1.0)";

export type Cotacao = {
  simbolo: string;
  preco: number;
  variacaoPct: number | null;
  fechamentoAnterior: number | null;
  /** horário do último negócio informado pela fonte (ISO) */
  negocioEm: string | null;
  /** data (AAAA-MM-DD, fuso da bolsa) da última barra diária */
  sessao: string | null;
  moeda: string | null;
  /** preço × quantidade negociada na última barra diária (R$, proxy de liquidez - mesma definição de data/mercado.py:volume_financeiro) */
  volumeFinanceiro: number | null;
};

type ChartResposta = {
  chart?: {
    result?: Array<{
      meta?: { regularMarketPrice?: number; regularMarketTime?: number; currency?: string; exchangeTimezoneName?: string };
      timestamp?: number[];
      indicators?: {
        quote?: Array<{
          close?: Array<number | null>;
          volume?: Array<number | null>;
          open?: Array<number | null>;
          high?: Array<number | null>;
          low?: Array<number | null>;
        }>;
      };
    }>;
  };
};

function dataNoFuso(epoch: number, fuso: string): { iso: string; diaSemana: number } {
  const d = new Date(epoch * 1000);
  const partes = new Intl.DateTimeFormat("en-CA", { timeZone: fuso, year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" })
    .formatToParts(d)
    .reduce<Record<string, string>>((acc, p) => ({ ...acc, [p.type]: p.value }), {});
  const dias: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  return { iso: `${partes.year}-${partes.month}-${partes.day}`, diaSemana: dias[partes.weekday] ?? 1 };
}

/** Mesma regra de data/prices.py (obter_cotacao_indice): barras diárias dos
 * últimos 5 dias SEM fim de semana; variação = último fechamento contra o
 * anterior. Nunca estima: sem duas barras válidas, variação = null. */
export async function obterCotacao(simbolo: string, revalidar = 300): Promise<Resultado<Cotacao | null>> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(simbolo)}?range=5d&interval=1d`;
  try {
    const resp = await fetch(url, { headers: { "User-Agent": UA }, next: { revalidate: revalidar } });
    if (!resp.ok) {
      console.error(`[yahoo] ${simbolo}: HTTP ${resp.status}`);
      return resultado("erro", null, FONTE, "Cotação indisponível na fonte.");
    }
    const corpo = (await resp.json()) as ChartResposta;
    const r = corpo.chart?.result?.[0];
    const fuso = r?.meta?.exchangeTimezoneName || "America/Sao_Paulo";
    const ts = r?.timestamp || [];
    const fech = r?.indicators?.quote?.[0]?.close || [];
    const vol = r?.indicators?.quote?.[0]?.volume || [];
    const barras = ts
      .map((t, i) => ({ ...dataNoFuso(t, fuso), close: fech[i], volume: vol[i] }))
      .filter((b) => typeof b.close === "number" && b.diaSemana !== 0 && b.diaSemana !== 6) as Array<{ iso: string; close: number; volume: number | null }>;
    const preco = r?.meta?.regularMarketPrice ?? barras.at(-1)?.close;
    if (typeof preco !== "number") return resultado("vazio", null, FONTE, "Sem cotação na fonte.");
    const anterior = barras.length >= 2 ? barras[barras.length - 2].close : null;
    const ultimoFech = barras.at(-1)?.close ?? null;
    const base = ultimoFech !== null && anterior !== null ? anterior : null;
    const variacaoPct = base ? ((preco - base) / base) * 100 : null;
    const ultimoVolume = barras.at(-1)?.volume ?? null;
    return resultado("ok", {
      simbolo,
      preco,
      variacaoPct,
      fechamentoAnterior: base,
      negocioEm: r?.meta?.regularMarketTime ? new Date(r.meta.regularMarketTime * 1000).toISOString() : null,
      sessao: barras.at(-1)?.iso ?? null,
      moeda: r?.meta?.currency ?? null,
      volumeFinanceiro: typeof ultimoVolume === "number" ? ultimoVolume * preco : null,
    }, FONTE);
  } catch (erro) {
    console.error(`[yahoo] ${simbolo}:`, erro);
    return resultado("erro", null, FONTE, "Cotação indisponível na fonte.");
  }
}

/** Várias cotações com concorrência limitada (a lista do Ibovespa tem ~85). */
export async function obterCotacoes(simbolos: string[], concorrencia = 12, revalidar = 300) {
  const saida: Record<string, Resultado<Cotacao | null>> = {};
  let i = 0;
  async function trabalhador() {
    while (i < simbolos.length) {
      const s = simbolos[i++];
      saida[s] = await obterCotacao(s, revalidar);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concorrencia, simbolos.length) }, trabalhador));
  return saida;
}

export type Ponto = { t: number; v: number };
/** Barra OHLC real da fonte (nunca um candle artificial feito só com o
 * fechamento): só entra em `velas` quando open/high/low/close vieram
 * todos presentes na mesma barra. */
export type Vela = { t: number; open: number; high: number; low: number; close: number; volume: number | null };
export type Serie = {
  simbolo: string;
  pontos: Ponto[];
  /** preço × quantidade de cada barra (mesma ordem/timestamps de `pontos`) - ausente quando a fonte não traz volume pro intervalo pedido */
  volumes: Ponto[];
  /** candles OHLC reais da fonte para o mesmo intervalo - vazio quando a fonte não trouxe open/high/low pro período (ver `pontos`, que cobre todo período com fechamento) */
  velas: Vela[];
  fechamentoAnterior: number | null;
  moeda: string | null;
  fuso: string;
};

/** Períodos de gráfico aceitos (range/interval do Yahoo). "1S" é a janela
 * de 5 dias de pregão (a API do Yahoo não tem um range nativo de
 * "1 semana"); "3M" usa barras diárias, como "6M"/"1A". */
export const PERIODOS = {
  "1D": { range: "1d", interval: "5m", revalidar: 300 },
  "1S": { range: "5d", interval: "30m", revalidar: 600 },
  "1M": { range: "1mo", interval: "1d", revalidar: 1800 },
  "3M": { range: "3mo", interval: "1d", revalidar: 3600 },
  "6M": { range: "6mo", interval: "1d", revalidar: 3600 },
  "1A": { range: "1y", interval: "1d", revalidar: 3600 },
  "5A": { range: "5y", interval: "1wk", revalidar: 21600 },
} as const;
export type Periodo = keyof typeof PERIODOS;

/** Série histórica de fechamentos como a fonte publica: pontos sem preço
 * são descartados (nunca interpolados). No intradiário, a referência é o
 * fechamento anterior informado pela própria fonte. */
export async function obterSerie(simbolo: string, periodo: Periodo = "1D"): Promise<Resultado<Serie | null>> {
  const p = PERIODOS[periodo];
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(simbolo)}?range=${p.range}&interval=${p.interval}`;
  try {
    const resp = await fetch(url, { headers: { "User-Agent": UA }, next: { revalidate: p.revalidar } });
    if (!resp.ok) {
      console.error(`[yahoo] série ${simbolo} ${periodo}: HTTP ${resp.status}`);
      return resultado("erro", null, FONTE, "Série indisponível na fonte.");
    }
    const corpo = (await resp.json()) as ChartResposta & {
      chart?: { result?: Array<{ meta?: { chartPreviousClose?: number; previousClose?: number } }> };
    };
    const r = corpo.chart?.result?.[0];
    const ts = r?.timestamp || [];
    const quote = r?.indicators?.quote?.[0];
    const fech = quote?.close || [];
    const vol = quote?.volume || [];
    const abre = quote?.open || [];
    const alta = quote?.high || [];
    const baixa = quote?.low || [];
    const pontos = ts.flatMap((t, i) => (typeof fech[i] === "number" ? [{ t: t * 1000, v: fech[i] as number }] : []));
    if (pontos.length < 2) return resultado("vazio", null, FONTE, "Sem negócios suficientes no período.");
    // volume financeiro por barra (preço × quantidade) - só entram barras
    // com os dois valores presentes, na mesma ordem de `pontos`
    const volumes = ts.flatMap((t, i) => (typeof fech[i] === "number" && typeof vol[i] === "number" ? [{ t: t * 1000, v: (vol[i] as number) * (fech[i] as number) }] : []));
    // candle OHLC real: só entra a barra com os 4 valores presentes (nunca
    // monta high/low artificiais a partir só do fechamento)
    const velas = ts.flatMap((t, i) =>
      typeof abre[i] === "number" && typeof alta[i] === "number" && typeof baixa[i] === "number" && typeof fech[i] === "number"
        ? [{ t: t * 1000, open: abre[i] as number, high: alta[i] as number, low: baixa[i] as number, close: fech[i] as number, volume: typeof vol[i] === "number" ? (vol[i] as number) : null }]
        : [],
    );
    const meta = r?.meta as { chartPreviousClose?: number; previousClose?: number; currency?: string; exchangeTimezoneName?: string } | undefined;
    return resultado("ok", {
      simbolo,
      pontos,
      volumes,
      velas,
      fechamentoAnterior: periodo === "1D" ? (meta?.previousClose ?? meta?.chartPreviousClose ?? null) : null,
      moeda: meta?.currency ?? null,
      fuso: meta?.exchangeTimezoneName || "America/Sao_Paulo",
    }, FONTE);
  } catch (erro) {
    console.error(`[yahoo] série ${simbolo}:`, erro);
    return resultado("erro", null, FONTE, "Série indisponível na fonte.");
  }
}
