import { painelIbovespa } from "@/lib/server/dominio/mercado";

/** Universo Ibovespa (cotação + setor) pro polling do cliente (Fase 9:
 * ranking de altas/baixas e desempenho setorial ao vivo, ver
 * PainelMercadoAoVivo.tsx) - mesma leitura batch já usada pelo Server
 * Component original da página Mercado/Empresas, só serializada. Payload
 * maior (~85 ações) que a fita - quem consome isto deve usar um
 * intervalo mais longo (ver INTERVALO_PAINEL_MS). */
export async function GET() {
  const painel = await painelIbovespa();
  return Response.json(painel);
}
