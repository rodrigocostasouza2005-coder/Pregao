import { INDICADORES, lerIndicadores } from "@/lib/server/dominio/mercado";

/** Mesma leitura de /api/mercado/fita, mas COM série intradiária (Fase 9:
 * gráficos ao vivo) - pro polling do cliente dos minigráficos
 * (MiniGraficoGridAoVivo.tsx) e das tabelas de indicadores
 * (TabelaIndicadoresAoVivo.tsx). Lista completa (INDICADORES) sempre;
 * cada componente filtra o subconjunto que mostra - 1 formato de
 * resposta só, sem endpoint por página. */
export async function GET() {
  const linhas = await lerIndicadores(INDICADORES, true);
  return Response.json({ linhas });
}
