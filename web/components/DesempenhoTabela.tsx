import { Badge, SemDado } from "./Painel";
import { formatarNumero, formatarPct } from "@/lib/format";
import type { PapelPanorama } from "@/lib/mercado";

export function DesempenhoTabela({ papeis }: { papeis: PapelPanorama[] }) {
  if (papeis.length === 0) return <SemDado>—</SemDado>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[0.76rem]">
        <thead>
          <tr className="text-[0.62rem] text-text-faint">
            <th className="text-left font-normal pb-1 pr-2">ATIVO</th>
            <th className="text-left font-normal pb-1 pr-2">SETOR</th>
            <th className="text-right font-normal pb-1 pr-2">PREÇO</th>
            <th className="text-right font-normal pb-1 pr-2">VAR. %</th>
            <th className="text-right font-normal pb-1">VOL. (R$ MI)</th>
          </tr>
        </thead>
        <tbody>
          {papeis.map((p) => (
            <tr key={p.ticker} className="border-t border-border/60">
              <td className="py-1 pr-2 whitespace-nowrap">
                <Badge ticker={p.ticker} />
                <b>{p.ticker}</b>{" "}
                <span className="text-text-dim text-[0.64rem]">{p.nome ?? ""}</span>
              </td>
              <td className="py-1 pr-2 text-text-dim">{p.setor}</td>
              <td className="py-1 pr-2 text-right">{formatarNumero(p.preco, 2)}</td>
              <td className={`py-1 pr-2 text-right ${p.variacaoPct >= 0 ? "text-up" : "text-down"}`}>
                {formatarPct(p.variacaoPct)}
              </td>
              <td className="py-1 text-right">{formatarNumero(p.volumeFinanceiro / 1_000_000, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
