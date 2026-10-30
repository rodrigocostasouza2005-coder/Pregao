import type { ReactNode } from "react";

export function CabecalhoPagina({ titulo, descricao, direita }: { titulo: ReactNode; descricao?: string; direita?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2 border-b border-filete pb-2">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-texto">{titulo}</h1>
        {descricao ? <p className="text-[12px] text-apagado">{descricao}</p> : null}
      </div>
      {direita}
    </div>
  );
}
