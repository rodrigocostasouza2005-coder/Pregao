"use client";

import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { usePolling } from "@/lib/usePolling";
import { TabelaIndicadores } from "./TabelaIndicadores";

const INTERVALO_MS = 60_000;

/** Mesma ideia de MiniGraficoGridAoVivo, pra TabelaIndicadores (grupos da
 * aba Mercado) - atualiza preço/variação/sparkline sozinha, sem trocar
 * quais ativos aparecem nem a ordem que a página pediu. */
export function TabelaIndicadoresAoVivo({ inicial, semSessao }: { inicial: LinhaIndicador[]; semSessao?: boolean }) {
  const simbolos = inicial.map((l) => l.simbolo);
  const { dado } = usePolling<{ linhas: LinhaIndicador[] }>({ linhas: inicial }, "/api/mercado/indicadores", INTERVALO_MS);
  const porSimbolo = new Map(dado.linhas.map((l) => [l.simbolo, l]));
  const linhas = simbolos.map((s) => porSimbolo.get(s)).filter((l): l is LinhaIndicador => !!l);
  return <TabelaIndicadores linhas={linhas.length === simbolos.length ? linhas : inicial} semSessao={semSessao} />;
}
