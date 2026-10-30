import { normalizarSimbolo } from "@/lib/server/dominio/mercado";
import { obterCotacao, obterSerie, PERIODOS, type Periodo } from "@/lib/server/yahoo";

/** Série (linha + candles OHLC + volume financeiro) e cotação de QUALQUER
 * símbolo/período, pro gráfico principal da Visão Geral e do Mercado
 * (GraficoPrincipal.tsx) - generaliza o mesmo par serie+cotacao que
 * app/api/ativo/[ticker]/serie/route.ts já serve, mas por querystring
 * (ticker/período trocam sem navegar) em vez de path fixo em "1D". */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const simboloBruto = url.searchParams.get("simbolo") || "^BVSP";
  const periodoBruto = url.searchParams.get("periodo") || "1D";
  const periodo: Periodo = periodoBruto in PERIODOS ? (periodoBruto as Periodo) : "1D";
  const simbolo = normalizarSimbolo(simboloBruto);
  const [serie, cotacao] = await Promise.all([obterSerie(simbolo, periodo), obterCotacao(simbolo)]);
  return Response.json({ serie, cotacao });
}
