import { lerIndicadoresCompactos } from "@/lib/server/dominio/mercado";

/** Indicadores compactos (Ibovespa, dólar, DI, + Brent opcional) pro
 * polling do cliente (IndicadoresCompactos.tsx) - tiles de número, nunca
 * mini-gráfico (brief: Visão Geral e Mercado). */
export async function GET(req: Request) {
  const comBrent = new URL(req.url).searchParams.get("brent") === "1";
  const linhas = await lerIndicadoresCompactos({ comBrent });
  return Response.json({ linhas });
}
