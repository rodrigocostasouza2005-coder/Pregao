/** Ativos acompanhados no painel de Mercado. Sem fonte conectada ainda:
 * a interface mostra "—" e o aviso de conteúdo demonstrativo - nunca um
 * número inventado. Os tickers são os mesmos do Morning Call (Yahoo). */
export type Ativo = {
  nome: string;
  ticker: string;
  grupo: "Brasil" | "Exterior" | "Commodities";
};

export const ATIVOS: Ativo[] = [
  { nome: "Ibovespa", ticker: "^BVSP", grupo: "Brasil" },
  { nome: "Dólar (USD/BRL)", ticker: "USDBRL=X", grupo: "Brasil" },
  { nome: "S&P 500 futuro", ticker: "ES=F", grupo: "Exterior" },
  { nome: "Nasdaq futuro", ticker: "NQ=F", grupo: "Exterior" },
  { nome: "Ouro", ticker: "GC=F", grupo: "Commodities" },
  { nome: "Petróleo Brent", ticker: "BZ=F", grupo: "Commodities" },
];

export type Cotacao = {
  preco: number;
  variacaoPct: number;
  referencia: string;
};

/** Ponto único de integração futura (API do backend Python / Supabase).
 * Enquanto não houver fonte, devolve null para todos. */
export async function obterCotacoes(): Promise<Record<string, Cotacao | null>> {
  return Object.fromEntries(ATIVOS.map((a) => [a.ticker, null]));
}
