import { Badge, SemDado } from "./Painel";
import { formatarPct } from "@/lib/format";
import type { PapelPanorama } from "@/lib/mercado";

function Coluna({ titulo, papeis, tipo }: { titulo: string; papeis: PapelPanorama[]; tipo: "alta" | "baixa" }) {
  if (papeis.length === 0) return <SemDado>—</SemDado>;
  const maior = Math.max(...papeis.map((p) => Math.abs(p.variacaoPct))) || 1;
  const corTexto = tipo === "alta" ? "text-up" : "text-down";
  const corBarra = tipo === "alta" ? "bg-up" : "bg-down";
  return (
    <div>
      <div className={`text-[0.68rem] font-bold mb-1 ${corTexto}`}>{titulo}</div>
      {papeis.map((p) => {
        const largura = Math.max(8, Math.round((Math.abs(p.variacaoPct) / maior) * 100));
        return (
          <div key={p.ticker} className="py-1">
            <div className="whitespace-nowrap">
              <Badge ticker={p.ticker} />
              <span className="font-semibold text-[0.72rem]">{p.ticker}</span>
              <span className={`float-right text-[0.72rem] ${corTexto}`}>{formatarPct(p.variacaoPct)}</span>
            </div>
            <div className="h-0.5 bg-border mt-1">
              <div className={`h-full ${corBarra}`} style={{ width: `${largura}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AltasBaixas({ altas, baixas }: { altas: PapelPanorama[]; baixas: PapelPanorama[] }) {
  return (
    <div className="grid grid-cols-2 gap-x-3">
      <Coluna titulo="ALTAS" papeis={altas} tipo="alta" />
      <Coluna titulo="BAIXAS" papeis={baixas} tipo="baixa" />
    </div>
  );
}
