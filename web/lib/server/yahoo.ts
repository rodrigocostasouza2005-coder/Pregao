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
};

type ChartResposta = {
  chart?: {
    result?: Array<{
      meta?: { regularMarketPrice?: number; regularMarketTime?: number; currency?: string; exchangeTimezoneName?: string };
      timestamp?: number[];
      indicators?: { quote?: Array<{ close?: Array<number | null> }> };
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
    const barras = ts
      .map((t, i) => ({ ...dataNoFuso(t, fuso), close: fech[i] }))
      .filter((b) => typeof b.close === "number" && b.diaSemana !== 0 && b.diaSemana !== 6) as Array<{ iso: string; close: number }>;
    const preco = r?.meta?.regularMarketPrice ?? barras.at(-1)?.close;
    if (typeof preco !== "number") return resultado("vazio", null, FONTE, "Sem cotação na fonte.");
    const anterior = barras.length >= 2 ? barras[barras.length - 2].close : null;
    const ultimoFech = barras.at(-1)?.close ?? null;
    const base = ultimoFech !== null && anterior !== null ? anterior : null;
    const variacaoPct = base ? ((preco - base) / base) * 100 : null;
    return resultado("ok", {
      simbolo,
      preco,
      variacaoPct,
      fechamentoAnterior: base,
      negocioEm: r?.meta?.regularMarketTime ? new Date(r.meta.regularMarketTime * 1000).toISOString() : null,
      sessao: barras.at(-1)?.iso ?? null,
      moeda: r?.meta?.currency ?? null,
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
