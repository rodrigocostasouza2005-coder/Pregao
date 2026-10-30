import { normalizarSimbolo } from "@/lib/server/dominio/mercado";
import { obterCotacao, obterSerie, PERIODOS, type Periodo } from "@/lib/server/yahoo";

/** Série (preço + volume financeiro) e cotação de um ativo pro polling
 * do cliente (Fase 9: gráfico intradiário ao vivo, ver
 * GraficoIntradiarioAoVivo.tsx). Só o período "1D" faz sentido "ao vivo"
 * - períodos históricos (1S/1M/.../5A) são servidos direto pelo Server
 * Component da página, sem polling, pra nunca sobrescrever um gráfico
 * histórico com uma leitura parcial do dia. Mesmo `ticker`/mapeamento
 * pra `.SA` da página de ativo (ver app/(terminal)/ativo/[ticker]/page.tsx). */
export async function GET(_req: Request, { params }: { params: Promise<{ ticker: string }> }) {
  const tickerBruto = decodeURIComponent((await params).ticker);
  const simbolo = normalizarSimbolo(tickerBruto);
  const periodo: Periodo = "1D" in PERIODOS ? "1D" : (Object.keys(PERIODOS)[0] as Periodo);
  const [serie, cotacao] = await Promise.all([obterSerie(simbolo, periodo), obterCotacao(simbolo)]);
  return Response.json({ serie, cotacao });
}
