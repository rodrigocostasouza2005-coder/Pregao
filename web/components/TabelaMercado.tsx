import { ATIVOS, type Cotacao } from "@/lib/mercado";

function formatar(valor: number, casas = 2) {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Tabela densa de ativos. Sem cotação conectada mostra "—" (nunca um
 * número estimado). */
export function TabelaMercado({ cotacoes }: { cotacoes: Record<string, Cotacao | null> }) {
  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-filete text-[10px] uppercase tracking-wider text-apagado">
          <th className="py-1.5 text-left font-medium">Ativo</th>
          <th className="py-1.5 text-right font-medium">Último</th>
          <th className="py-1.5 text-right font-medium">Var.</th>
          <th className="hidden py-1.5 text-right font-medium sm:table-cell">Referência</th>
        </tr>
      </thead>
      <tbody>
        {ATIVOS.map((ativo) => {
          const c = cotacoes[ativo.ticker];
          const cor = !c ? "text-apagado" : c.variacaoPct >= 0 ? "text-alta" : "text-baixa";
          return (
            <tr key={ativo.ticker} className="border-b border-filete/60 last:border-0">
              <td className="py-1.5">
                <div className="text-texto">{ativo.nome}</div>
                <div className="font-mono text-[10px] text-apagado">{ativo.ticker}</div>
              </td>
              <td className="py-1.5 text-right font-mono">{c ? formatar(c.preco) : "—"}</td>
              <td className={`py-1.5 text-right font-mono ${cor}`}>
                {c ? `${c.variacaoPct >= 0 ? "+" : ""}${formatar(c.variacaoPct)}%` : "—"}
              </td>
              <td className="hidden py-1.5 text-right font-mono text-[11px] text-apagado sm:table-cell">
                {c ? c.referencia : "sem fonte"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
