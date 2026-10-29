import { INDICADORES, lerIndicadores } from "@/lib/server/dominio/mercado";

/** Dados da fita de cotações pro polling do cliente (FitaCotacoes.tsx) -
 * mesma leitura/cache do Server Component original (lerIndicadores já
 * respeita o revalidate de lib/server/yahoo.ts); só serializa pra JSON. */
export async function GET() {
  const linhas = await lerIndicadores(INDICADORES, false);
  return Response.json({ linhas });
}
