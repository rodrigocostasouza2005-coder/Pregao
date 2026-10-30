"use client";

import { Grafico } from "./Grafico";
import { usePolling } from "@/lib/usePolling";
import type { Cotacao, Serie } from "@/lib/server/yahoo";
import type { Resultado } from "@/lib/tipos";

const INTERVALO_MS = 60_000;

type Resposta = { serie: Resultado<Serie | null>; cotacao: Resultado<Cotacao | null> };

/** Gráfico intradiário (período "1D") que se atualiza sozinho (Fase 9) -
 * só usado pra "1D": gráficos de períodos históricos (1S em diante) são
 * sempre o Server Component estático (ver app/(terminal)/ativo/[ticker]/
 * page.tsx) pra nunca sobrescrever uma série histórica com uma leitura
 * parcial do dia. O ritmo real continua limitado pelo revalidate de
 * lib/server/yahoo.ts (hoje 300s pro "1D") - isto só garante que a tela
 * busca de novo sem precisar de F5, nunca inventa ponto. */
export function GraficoIntradiarioAoVivo({ ticker, inicial, titulo }: { ticker: string; inicial: Resposta; titulo: string }) {
  const { dado } = usePolling<Resposta>(inicial, `/api/ativo/${encodeURIComponent(ticker)}/serie`, INTERVALO_MS);
  const serie = dado.serie.dados ?? inicial.serie.dados;
  const cotacao = dado.cotacao.dados ?? inicial.cotacao.dados;
  if (!serie) return <p className="text-[12px] text-apagado">Sem negócios no período.</p>;
  return (
    <Grafico
      pontos={serie.pontos}
      volumes={serie.volumes}
      referencia={cotacao?.fechamentoAnterior ?? null}
      rotuloReferencia="fech. ant."
      eixoX="hora"
      fuso={serie.fuso}
      altura={260}
      titulo={titulo}
    />
  );
}
