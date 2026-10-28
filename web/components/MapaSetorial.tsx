import { SemDado } from "./Painel";
import { formatarPct } from "@/lib/format";
import type { DesempenhoSetor } from "@/lib/mercado";

export function MapaSetorial({ setores }: { setores: DesempenhoSetor[] }) {
  if (setores.length === 0) return <SemDado>—</SemDado>;
  const exibidos = setores.slice(0, 6);
  const maiorDispersao = [...setores].sort(
    (a, b) => Math.abs(b.variacaoMediaPct) - Math.abs(a.variacaoMediaPct)
  )[0];
  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {exibidos.map((s) => {
          const alta = s.variacaoMediaPct >= 0;
          return (
            <div
              key={s.setor}
              className={`flex-1 min-w-24 rounded-[3px] px-2 py-1.5 border ${
                alta ? "border-up/35 bg-up/10" : "border-down/35 bg-down/10"
              }`}
            >
              <div className="text-[0.62rem] font-semibold whitespace-nowrap overflow-hidden text-ellipsis">
                {s.setor}
              </div>
              <div className={`text-[0.76rem] font-bold mt-0.5 ${alta ? "text-up" : "text-down"}`}>
                {formatarPct(s.variacaoMediaPct)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="text-[0.6rem] text-text-faint mt-2.5 pt-2 border-t border-border">
        Maior dispersão: <b className="text-accent">{maiorDispersao.setor}</b> ({maiorDispersao.nPapeis} papel(éis),{" "}
        {formatarPct(maiorDispersao.variacaoMediaPct)} méd.)
      </div>
    </div>
  );
}
