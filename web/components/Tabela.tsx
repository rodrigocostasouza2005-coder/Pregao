import type { ReactNode } from "react";

export type Coluna<T> = {
  titulo: string;
  celula: (linha: T) => ReactNode;
  alinhar?: "esq" | "dir";
  /** esconde a coluna em telas estreitas */
  larga?: boolean;
  classe?: string;
};

/** Tabela densa do terminal: números à direita em fonte mono. */
export function Tabela<T>({ linhas, colunas, chave, vazio }: { linhas: T[]; colunas: Coluna<T>[]; chave: (l: T, i: number) => string; vazio?: string }) {
  if (!linhas.length) return <p className="text-[12px] text-apagado">{vazio || "Nenhum registro."}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="border-b border-filete text-[10px] uppercase tracking-wider text-apagado">
            {colunas.map((c) => (
              <th key={c.titulo} className={`py-1.5 pr-3 font-medium last:pr-0 ${c.alinhar === "dir" ? "text-right" : "text-left"} ${c.larga ? "hidden md:table-cell" : ""}`}>
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((l, i) => (
            <tr key={chave(l, i)} className="border-b border-filete/60 align-top last:border-0 hover:bg-painel-alto/60">
              {colunas.map((c) => (
                <td key={c.titulo} className={`py-1.5 pr-3 last:pr-0 ${c.alinhar === "dir" ? "text-right font-mono" : ""} ${c.larga ? "hidden md:table-cell" : ""} ${c.classe || ""}`}>
                  {c.celula(l)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
