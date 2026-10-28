import { NextRequest, NextResponse } from "next/server";
import { obterHistoricoIbovespa } from "@/lib/mercado";

/** Usada pelo seletor de período (client component) pra reconsultar o
 * histórico do Ibovespa sem recarregar a página inteira. Mesma fonte
 * (Yahoo Finance, lib/yahoo.ts) do resto do app. */
export async function GET(req: NextRequest) {
  const periodo = req.nextUrl.searchParams.get("periodo") ?? "6M";
  const pontos = await obterHistoricoIbovespa(periodo);
  return NextResponse.json({ periodo, pontos }, { headers: { "Cache-Control": "no-store" } });
}
