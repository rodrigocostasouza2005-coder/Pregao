import { dataHora, num, pct } from "@/lib/formatos";
import type { NotaEarnings as Nota } from "@/lib/server/dominio/inteligencia";
import { LinkFonte } from "./LinkFonte";
import { Selo } from "./Selo";

/** Nota do agente de earnings (data/earnings/reviewer.py): números da
 * CVM/SEC como FATO; interpretações do agente como INFERÊNCIA. */
export function NotaEarnings({ nota }: { nota: Nota }) {
  const c = nota.conteudo || {};
  const metricas = Object.entries(c.metricas || {});
  return (
    <div className="border-b border-filete/60 py-2 last:border-0">
      <div className="flex flex-wrap items-baseline gap-2 text-[12.5px]">
        <a href={`/ativo/${nota.ticker}`} className="font-mono text-texto hover:text-ambar">{nota.ticker}</a>
        <span className="text-suave">{c.empresa}</span>
        <span className="font-mono text-[11px] text-ambar">{nota.periodo_label}</span>
        <span className="ml-auto font-mono text-[10.5px] text-apagado">{dataHora(nota.gerado_em)}</span>
      </div>
      {metricas.length ? (
        <table className="mt-1 w-full text-[11.5px]">
          <tbody>
            {metricas.slice(0, 6).map(([nome, m]) => {
              const yoy = Object.entries(m).find(([k]) => /yoy.*variacao|variacao.*yoy|variacao_pct$/.test(k))?.[1] ?? null;
              return (
                <tr key={nome} className="border-b border-filete/40 last:border-0">
                  <td className="py-0.5 text-suave">{nome}</td>
                  <td className="py-0.5 text-right font-mono">{num(m.atual ?? null, 0)}</td>
                  <td className="py-0.5 text-right font-mono text-apagado">{yoy !== null ? `${pct(yoy)} a/a` : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
      {(c.interpretacoes || []).length ? (
        <ul className="mt-1 space-y-0.5 text-[11.5px] text-suave">
          {c.interpretacoes!.slice(0, 3).map((t, i) => <li key={i}><Selo tipo="inferencia" /> {t}</li>)}
        </ul>
      ) : null}
      <div className="mt-1 text-[10.5px] text-apagado">
        <Selo tipo="fato" texto="Números" /> Fonte: {c.fontes?.map((f, i) => <LinkFonte key={i} href={f.url}>{f.nome || "documento"}</LinkFonte>) || "—"}
        {c.moeda ? ` · ${c.moeda}${c.escala_moeda ? ` (${c.escala_moeda})` : ""}` : ""}
      </div>
    </div>
  );
}
