import "server-only";

import ibovespa from "@/contratos/ibovespa.json";
import type { Resultado } from "@/lib/tipos";
import { obterCotacao, obterCotacoes, type Cotacao } from "../yahoo";

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

export type LinhaIndicador = Indicador & { r: Resultado<Cotacao | null> };

export async function lerIndicadores(lista = INDICADORES): Promise<LinhaIndicador[]> {
  const leituras = await Promise.all(lista.map((i) => obterCotacao(i.simbolo)));
  return lista.map((i, n) => ({ ...i, r: leituras[n] }));
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
