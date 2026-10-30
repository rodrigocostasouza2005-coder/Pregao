"use client";

import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { usePolling } from "@/lib/usePolling";
import { MiniGrafico } from "./MiniGrafico";

const INTERVALO_MS = 60_000;

/** Grade de MiniGrafico que se atualiza sozinha (Fase 9) - recebe o mesmo
 * subconjunto/ordem de símbolos que a página já escolheu (`inicial`,
 * vindo do Server Component) e troca só os VALORES a cada leitura nova
 * de /api/mercado/indicadores (lista cheia, filtrada aqui pros símbolos
 * pedidos) - nunca muda quais indicadores aparecem, só os números. */
export function MiniGraficoGridAoVivo({ inicial, className = "", altura }: { inicial: LinhaIndicador[]; className?: string; altura?: number }) {
  const simbolos = inicial.map((l) => l.simbolo);
  const { dado } = usePolling<{ linhas: LinhaIndicador[] }>({ linhas: inicial }, "/api/mercado/indicadores", INTERVALO_MS);
  const porSimbolo = new Map(dado.linhas.map((l) => [l.simbolo, l]));
  const linhas = simbolos.map((s) => porSimbolo.get(s)).filter((l): l is LinhaIndicador => !!l);
  const efetivas = linhas.length === simbolos.length ? linhas : inicial;
  return (
    <div className={className}>
      {efetivas.map((l) => <MiniGrafico key={l.simbolo} linha={l} altura={altura} />)}
    </div>
  );
}
