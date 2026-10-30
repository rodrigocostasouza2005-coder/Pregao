import "server-only";

import ibovespa from "@/contratos/ibovespa.json";
import { resultado, type Resultado } from "@/lib/tipos";
import { historicoSgs, SERIES_SGS } from "../bcb";
import { obterCotacao, obterCotacoes, obterSerie, type Cotacao, type Serie } from "../yahoo";

export type Indicador = { nome: string; simbolo: string; grupo: "Brasil" | "Exterior" | "Commodities" | "Juros e moedas"; casas: number };

export const INDICADORES: Indicador[] = [
  { nome: "Ibovespa", simbolo: "^BVSP", grupo: "Brasil", casas: 0 },
  { nome: "Dólar (USD/BRL)", simbolo: "USDBRL=X", grupo: "Brasil", casas: 4 },
  { nome: "Euro (EUR/BRL)", simbolo: "EURBRL=X", grupo: "Brasil", casas: 4 },
  { nome: "S&P 500", simbolo: "^GSPC", grupo: "Exterior", casas: 2 },
  { nome: "Nasdaq", simbolo: "^IXIC", grupo: "Exterior", casas: 2 },
  { nome: "Dow Jones", simbolo: "^DJI", grupo: "Exterior", casas: 2 },
  { nome: "S&P 500 futuro", simbolo: "ES=F", grupo: "Exterior", casas: 2 },
  { nome: "Treasury 10 anos (%)", simbolo: "^TNX", grupo: "Juros e moedas", casas: 3 },
  { nome: "Índice dólar (DXY)", simbolo: "DX-Y.NYB", grupo: "Juros e moedas", casas: 2 },
  { nome: "Petróleo Brent", simbolo: "BZ=F", grupo: "Commodities", casas: 2 },
  { nome: "Petróleo WTI", simbolo: "CL=F", grupo: "Commodities", casas: 2 },
  { nome: "Ouro", simbolo: "GC=F", grupo: "Commodities", casas: 2 },
  { nome: "Bitcoin (USD)", simbolo: "BTC-USD", grupo: "Commodities", casas: 0 },
];

/** Re-exportado de lib/siglas.ts (ver lá o motivo: precisa ser
 * importável por um Client Component, que não pode tocar neste módulo
 * "server-only"). */
export { SIGLAS } from "@/lib/siglas";

/** `s` é a série intradiária da última sessão (para gráficos e linhas). */
export type LinhaIndicador = Indicador & { r: Resultado<Cotacao | null>; s?: Resultado<Serie | null> };

export async function lerIndicadores(lista = INDICADORES, comSerie = true): Promise<LinhaIndicador[]> {
  const [leituras, series] = await Promise.all([
    Promise.all(lista.map((i) => obterCotacao(i.simbolo))),
    comSerie ? Promise.all(lista.map((i) => obterSerie(i.simbolo, "1D"))) : Promise.resolve([]),
  ]);
  return lista.map((i, n) => ({ ...i, r: leituras[n], s: series[n] }));
}

export type Acao = { ticker: string; setor: string; cotacao: Cotacao };
export type Painel = {
  acoes: Acao[];
  semCotacao: string[];
  setores: Array<{ setor: string; variacaoMedia: number; n: number }>;
  totalUniverso: number;
};

const SETORES = (ibovespa as { setores: Record<string, string> }).setores;

/** Universo do Ibovespa (config.IBOVESPA_SETORES) com cotação; ações sem
 * cotação/variação ficam fora das listas e são contadas, nunca zeradas. */
export async function painelIbovespa(): Promise<Painel> {
  const tickers = Object.keys(SETORES);
  const leituras = await obterCotacoes(tickers.map((t) => `${t}.SA`));
  const acoes: Acao[] = [];
  const semCotacao: string[] = [];
  for (const t of tickers) {
    const c = leituras[`${t}.SA`]?.dados;
    if (c && c.variacaoPct !== null) acoes.push({ ticker: t, setor: SETORES[t], cotacao: c });
    else semCotacao.push(t);
  }
  const porSetor = new Map<string, number[]>();
  for (const a of acoes) porSetor.set(a.setor, [...(porSetor.get(a.setor) || []), a.cotacao.variacaoPct as number]);
  const setores = [...porSetor.entries()]
    .map(([setor, v]) => ({ setor, variacaoMedia: v.reduce((s, x) => s + x, 0) / v.length, n: v.length }))
    .sort((a, b) => b.variacaoMedia - a.variacaoMedia);
  return { acoes, semCotacao, setores, totalUniverso: tickers.length };
}

export function altasEBaixas(acoes: Acao[], n = 8) {
  const ord = [...acoes].sort((a, b) => (b.cotacao.variacaoPct as number) - (a.cotacao.variacaoPct as number));
  return { altas: ord.slice(0, n).filter((a) => (a.cotacao.variacaoPct as number) > 0), baixas: ord.slice(-n).reverse().filter((a) => (a.cotacao.variacaoPct as number) < 0) };
}

/** Ranking por liquidez EFETIVA (preço × volume de ações da última barra
 * diária, ver Cotacao.volumeFinanceiro em lib/server/yahoo.ts) - nunca
 * pela contagem de negócios nem pelo volume em ações puro, que é o que o
 * protótipo rotula de "proxy de liquidez". */
export function maisNegociados(acoes: Acao[], n = 8) {
  return [...acoes]
    .filter((a) => typeof a.cotacao.volumeFinanceiro === "number")
    .sort((a, b) => (b.cotacao.volumeFinanceiro as number) - (a.cotacao.volumeFinanceiro as number))
    .slice(0, n);
}

/** "PETR4" -> "PETR4.SA" (ticker da B3 pro sufixo do Yahoo); símbolos que
 * já não são um ticker de 4 letras + número (índices, FX, futuros) saem
 * inalterados. Mesma regra que estava duplicada em app/(terminal)/
 * ativo/[ticker]/page.tsx e app/api/ativo/[ticker]/serie/route.ts. */
export function normalizarSimbolo(tickerBruto: string): string {
  const ticker = tickerBruto.toUpperCase().replace(/[^A-Z0-9.\-^=]/g, "");
  return /^[A-Z]{4}\d{1,2}$/.test(ticker) ? `${ticker}.SA` : ticker;
}

/** Seleção padrão de ações da B3 pra fita de cotações (brief: PETR4,
 * VALE3, ITUB4, B3SA3, BBAS3, BBDC4, WEGE3, PRIO3, RENT3, ABEV3) - usada
 * quando o usuário não está logado ou não tem watchlist própria; sempre
 * complementada pela watchlist real de quem está logado. */
export const ATIVOS_FITA_PADRAO = ["PETR4", "VALE3", "ITUB4", "B3SA3", "BBAS3", "BBDC4", "WEGE3", "PRIO3", "RENT3", "ABEV3"];

export type ItemFita = { simbolo: string; nome: string; casas: number; unidade?: string; r: Resultado<Cotacao | null> };

/** DI (CDI anualizado, série SGS 4389 do Banco Central) com variação
 * contra a leitura anterior, em pontos percentuais - mesma fonte oficial
 * de lib/server/bcb.ts, nunca uma estimativa. */
async function lerDI(): Promise<Resultado<Cotacao | null>> {
  const r = await historicoSgs(SERIES_SGS.cdiAnualizado.codigo, 20, 3600);
  const serie = r.dados;
  if (r.estado !== "ok" || serie.length < 1) return resultado(r.estado === "ok" ? "vazio" : r.estado, null, r.fonte, r.mensagem);
  const ultima = serie.at(-1) as { valor: number; data: string };
  const anterior = serie.length >= 2 ? serie[serie.length - 2] : null;
  return resultado("ok", {
    simbolo: "DI",
    preco: ultima.valor,
    variacaoPct: anterior ? ultima.valor - anterior.valor : null,
    fechamentoAnterior: anterior?.valor ?? null,
    negocioEm: null,
    sessao: ultima.data,
    moeda: null,
    volumeFinanceiro: null,
  }, r.fonte);
}

/** Fita de cotações "viva": índices brasileiros (Ibovespa, dólar) + DI +
 * ações da B3 (watchlist do usuário, complementada pela seleção padrão
 * quando a lista é curta) - nunca índices americanos, que ficam fora da
 * fita principal (brief: "não quero SPX, Nasdaq, Dow Jones... na fita"). */
export async function lerFita(watchlist: string[] = []): Promise<ItemFita[]> {
  const indicadoresBr = INDICADORES.filter((i) => i.simbolo === "^BVSP" || i.simbolo === "USDBRL=X");
  const tickers = [...new Set([...watchlist.map((t) => t.toUpperCase()), ...ATIVOS_FITA_PADRAO])].slice(0, 20);
  const [leiturasIdx, leiturasAcoes, di] = await Promise.all([
    Promise.all(indicadoresBr.map((i) => obterCotacao(i.simbolo))),
    obterCotacoes(tickers.map((t) => normalizarSimbolo(t))),
    lerDI(),
  ]);
  const itensIdx: ItemFita[] = indicadoresBr.map((i, n) => ({ simbolo: i.simbolo, nome: i.nome, casas: i.casas, r: leiturasIdx[n] }));
  const itemDI: ItemFita[] = di.estado === "ok" ? [{ simbolo: "DI", nome: "DI (CDI anualizado)", casas: 2, unidade: "p.p.", r: di }] : [];
  const itensAcoes: ItemFita[] = tickers.map((t) => ({ simbolo: t, nome: t, casas: 2, r: leiturasAcoes[normalizarSimbolo(t)] }));
  return [...itensIdx, ...itemDI, ...itensAcoes];
}
