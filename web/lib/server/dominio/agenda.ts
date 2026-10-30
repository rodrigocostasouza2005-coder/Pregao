import "server-only";

import { hojeSaoPaulo } from "@/lib/formatos";
import { lerTabela } from "../supabase";

export type EventoResultado = { ticker: string; periodo: string; data_evento: string; status: string; fonte: string | null; url_fonte: string | null; coletado_em: string };

/** Agenda de resultados (eventos_resultados, coletor CALENDÁRIO/CVM):
 * de ontem em diante, em ordem de data. */
export function lerResultadosFuturos(limite = 300) {
  const ontem = new Date(Date.parse(`${hojeSaoPaulo()}T12:00:00Z`) - 86400000).toISOString().slice(0, 10);
  return lerTabela<EventoResultado>("eventos_resultados", {
    select: "ticker,periodo,data_evento,status,fonte,url_fonte,coletado_em",
    filtros: { data_evento: `gte.${ontem}` },
    ordem: "data_evento.asc,ticker.asc",
    limite,
  });
}

export type Snapshot = { id: string; eventos: unknown; atualizado_em: string };

export function lerSnapshotsCalendario() {
  return lerTabela<Snapshot>("calendario_snapshot", { select: "id,eventos,atualizado_em", ordem: "atualizado_em.desc", limite: 5 });
}

export function lerEventosDoTicker(ticker: string) {
  return lerTabela<EventoResultado>("eventos_resultados", {
    select: "ticker,periodo,data_evento,status,fonte,url_fonte,coletado_em",
    filtros: { ticker: `eq.${ticker}` },
    ordem: "data_evento.desc",
    limite: 12,
  });
}
