/** Marca explícita de conteúdo sem dado real conectado. */
export function SeloDemonstrativo({ texto = "Demonstrativo" }: { texto?: string }) {
  return (
    <span className="rounded-sm border border-ambar/40 bg-ambar-fundo px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ambar">
      {texto}
    </span>
  );
}
