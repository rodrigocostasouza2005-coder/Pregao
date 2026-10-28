/**
 * Cliente mínimo do endpoint público "chart" do Yahoo Finance - mesma
 * fonte gratuita que o app Python original usa via yfinance (nenhuma
 * chave/serviço pago). Implementado aqui em vez de reaproveitado porque
 * o backend Python não expõe nenhuma API HTTP (é um processo Streamlit
 * autocontido) - este é um fetch NOVO e independente, não uma migração
 * do coletor Python (que continua intocado, servindo o Streamlit).
 *
 * Sempre roda só no servidor (Route Handlers / Server Components) -
 * nunca importar isto num Client Component.
 */

const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 PregaoWeb/1.0";

export type Cotacao = {
  ticker: string;
  preco: number;
  variacaoPct: number;
  volume: number | null;
  nome: string | null;
};

export type PontoHistorico = {
  data: string; // ISO date
  close: number;
};

type ChartResult = {
  meta: {
    regularMarketPrice?: number;
    previousClose?: number;
    chartPreviousClose?: number;
    symbol?: string;
    longName?: string;
    shortName?: string;
    regularMarketVolume?: number;
    regularMarketChangePercent?: number;
  };
  timestamp?: number[];
  indicators?: { quote?: { close?: (number | null)[]; volume?: (number | null)[] }[] };
};

async function fetchChart(
  symbol: string,
  range: string,
  interval: string
): Promise<ChartResult | null> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    symbol
  )}?range=${range}&interval=${interval}`;
  try {
    const resp = await fetch(url, {
      headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
      // dados de mercado mudam rápido - nunca cachear no nível do fetch,
      // cada rota decide seu próprio cache (ver app/api/mercado/*)
      cache: "no-store",
    });
    if (!resp.ok) return null;
    const json = await resp.json();
    const result = json?.chart?.result?.[0] as ChartResult | undefined;
    if (!result || !result.meta) return null;
    return result;
  } catch {
    return null;
  }
}

/** Cotação atual (preço + variação %) - None se a fonte falhar ou não
 * houver dado válido, nunca um número inventado.
 *
 * Achado real (validação visual, 2026-10-27): `meta.previousClose` quase
 * sempre vem AUSENTE nesta API, e o fallback `meta.chartPreviousClose`
 * NÃO é o fechamento do pregão anterior - é um ponto de referência que o
 * Yahoo usa só pra escala do gráfico, podia ser de vários dias atrás.
 * Calcular variação manualmente contra ele gerou number absurdos (ex:
 * -57% num dia normal). `meta.regularMarketChangePercent` é o campo que
 * o próprio Yahoo já calcula corretamente (confirmado batendo com os
 * valores reais vistos no app Python/yfinance) - usar direto, nunca
 * recalcular na mão.
 *
 * `meta.regularMarketVolume` também vem 0 com frequência (barra do dia
 * ainda não fechada/mercado fechado) - o volume real mais recente está
 * no ÚLTIMO valor não-nulo/não-zero da série `indicators.quote[0].volume`. */
export async function obterCotacao(ticker: string, symbolYahoo?: string): Promise<Cotacao | null> {
  const symbol = symbolYahoo ?? ticker;
  const result = await fetchChart(symbol, "5d", "1d");
  if (!result) return null;
  const preco = result.meta.regularMarketPrice;
  const variacaoPct = result.meta.regularMarketChangePercent;
  if (preco == null || variacaoPct == null || !Number.isFinite(preco) || !Number.isFinite(variacaoPct)) {
    return null;
  }
  const serieVolume = result.indicators?.quote?.[0]?.volume ?? [];
  let volume: number | null = null;
  for (let i = serieVolume.length - 1; i >= 0; i--) {
    const v = serieVolume[i];
    if (v != null && v > 0) {
      volume = v;
      break;
    }
  }
  return {
    ticker,
    preco,
    variacaoPct,
    volume,
    nome: result.meta.longName ?? result.meta.shortName ?? null,
  };
}

/** Várias cotações em paralelo - tickers sem dado válido simplesmente
 * ficam de fora do resultado (mesmo princípio do coletor Python:
 * degradar por item, nunca derrubar o lote inteiro nem inventar). */
export async function obterCotacoesLote(
  tickers: { ticker: string; symbolYahoo?: string }[]
): Promise<Map<string, Cotacao>> {
  const resultados = await Promise.allSettled(
    tickers.map((t) => obterCotacao(t.ticker, t.symbolYahoo))
  );
  const mapa = new Map<string, Cotacao>();
  resultados.forEach((r, i) => {
    if (r.status === "fulfilled" && r.value) {
      mapa.set(tickers[i].ticker, r.value);
    }
  });
  return mapa;
}

const RANGE_POR_PERIODO: Record<string, { range: string; interval: string }> = {
  "1D": { range: "1d", interval: "5m" },
  "1S": { range: "5d", interval: "30m" },
  "1M": { range: "1mo", interval: "1d" },
  "3M": { range: "3mo", interval: "1d" },
  "6M": { range: "6mo", interval: "1d" },
  "1A": { range: "1y", interval: "1d" },
  "5A": { range: "5y", interval: "1wk" },
};

/** Histórico de fechamentos pro período pedido - [] se a fonte falhar
 * (nunca inventa um ponto da série). */
export async function obterHistorico(symbol: string, periodo: string): Promise<PontoHistorico[]> {
  const cfg = RANGE_POR_PERIODO[periodo] ?? RANGE_POR_PERIODO["6M"];
  const result = await fetchChart(symbol, cfg.range, cfg.interval);
  if (!result || !result.timestamp || !result.indicators?.quote?.[0]?.close) return [];
  const timestamps = result.timestamp;
  const closes = result.indicators.quote[0].close!;
  const pontos: PontoHistorico[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const c = closes[i];
    if (c == null || !Number.isFinite(c)) continue;
    pontos.push({ data: new Date(timestamps[i] * 1000).toISOString(), close: c });
  }
  return pontos;
}
