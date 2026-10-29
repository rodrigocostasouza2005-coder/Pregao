import { num } from "@/lib/formatos";
import { referenciaCotacao } from "@/lib/referencia";
import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { Variacao } from "./Variacao";

/** Indicadores com valor, variação e referência temporal de cada um. */
export function TabelaIndicadores({ linhas }: { linhas: LinhaIndicador[] }) {
  return (
    <table className="w-full border-collapse text-[12.5px]">
      <thead>
        <tr className="border-b border-filete text-[10px] uppercase tracking-wider text-apagado">
          <th className="py-1.5 text-left font-medium">Ativo</th>
          <th className="py-1.5 text-right font-medium">Último</th>
          <th className="py-1.5 text-right font-medium">Var.</th>
          <th className="py-1.5 text-right font-medium">Referência</th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => {
          const c = l.r.dados;
          return (
            <tr key={l.simbolo} className="border-b border-filete/60 last:border-0">
              <td className="py-1.5">
                <span className="text-texto">{l.nome}</span>
                <span className="ml-2 font-mono text-[10px] text-apagado">{l.simbolo}</span>
              </td>
              <td className="py-1.5 text-right font-mono">{c ? num(c.preco, l.casas) : <span className="text-apagado">indisponível</span>}</td>
              <td className="py-1.5 text-right"><Variacao v={c?.variacaoPct} /></td>
              <td className="py-1.5 text-right font-mono text-[11px] text-apagado">{referenciaCotacao(c)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
