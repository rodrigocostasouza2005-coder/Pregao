import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { data, dataHora, hojeSaoPaulo } from "@/lib/formatos";
import { lerResultadosFuturos, lerSnapshotsCalendario } from "@/lib/server/dominio/agenda";

export const metadata = { title: "Agenda · Pregão" };

type EventoSnapshot = { data?: string; ticker?: string; empresa?: string; tipo_evento?: string; periodo?: string; horario?: string; status?: string; fonte?: string; url_fonte?: string };

// Nomes reais em eventos_resultados/calendario_snapshot (ver coletor_local.py e
// data/eventos_coleta.py) - PRAZO_CVM é o status dominante (446 de 466 eventos
// reais hoje), "PRAZO_REGULATORIO" nunca existiu nos dados e deixava quase todo
// evento sem cor (cai no default text-apagado).
const STATUS: Record<string, string> = { CONFIRMADO: "text-alta", ESTIMADO: "text-ambar", PRAZO_CVM: "text-suave" };

export default async function Agenda() {
  const [snaps, resultados] = await Promise.all([lerSnapshotsCalendario(), lerResultadosFuturos()]);
  const snap = snaps.dados.find((s) => s.id === "latest") || snaps.dados[0];
  const hoje = hojeSaoPaulo();
  const eventosSnap: EventoSnapshot[] = Array.isArray(snap?.eventos) ? (snap!.eventos as EventoSnapshot[]) : [];
  const eventos = eventosSnap.length
    ? eventosSnap.filter((e) => (e.data || "") >= hoje).sort((a, b) => (a.data || "").localeCompare(b.data || "") || (a.horario || "").localeCompare(b.horario || ""))
    : resultados.dados.map((r) => ({ data: r.data_evento, ticker: r.ticker, periodo: r.periodo, status: r.status, fonte: r.fonte || undefined, url_fonte: r.url_fonte || undefined, tipo_evento: "RESULTADO" }));
  const porDia = new Map<string, EventoSnapshot[]>();
  for (const e of eventos.slice(0, 250)) porDia.set(e.data || "?", [...(porDia.get(e.data || "?") || []), e]);
  const origem = eventosSnap.length ? `calendario_snapshot (atualizado ${dataHora(snap?.atualizado_em)})` : "eventos_resultados";
  return (
    <>
      <CabecalhoPagina titulo="Agenda" descricao="Resultados e eventos corporativos por data · status indica a confiabilidade da data" />
      <EstadoDados r={eventosSnap.length ? snaps : resultados} vazio="Nenhum evento futuro no calendário." />
      <div className="grid gap-3 lg:grid-cols-2">
        {[...porDia.entries()].map(([dia, lista]) => (
          <Painel key={dia} titulo={dia === hoje ? `Hoje · ${data(dia)}` : data(dia)} rodape={`Fonte: ${origem}`}>
            <ul className="divide-y divide-filete/60 text-[12.5px]">
              {lista.map((e, i) => (
                <li key={i} className="flex flex-wrap items-baseline gap-x-2 py-1.5">
                  <span className="w-16 font-mono text-[11px] text-apagado">{e.horario || "—"}</span>
                  <a href={`/ativo/${e.ticker}`} className="font-mono hover:text-ambar">{e.ticker}</a>
                  <span className="text-suave">{e.tipo_evento || "Evento"}{e.periodo ? ` · ${e.periodo}` : ""}</span>
                  <span className={`ml-auto font-mono text-[10px] ${STATUS[e.status || ""] || "text-apagado"}`}>
                    <LinkFonte href={e.url_fonte}>{e.status || "—"}</LinkFonte>
                  </span>
                </li>
              ))}
            </ul>
          </Painel>
        ))}
      </div>
      <p className="mt-3 text-[10.5px] text-apagado">
        Indicadores econômicos (IPCA, Copom, payroll...) ainda não têm coletor de calendário no Pregão; esta agenda cobre os eventos corporativos coletados.
      </p>
    </>
  );
}
