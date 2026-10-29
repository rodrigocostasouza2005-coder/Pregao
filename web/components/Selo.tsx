const TONS = {
  fato: "border-alta/40 text-alta",
  analista: "border-[#6aa7ff]/40 text-[#8fbcff]",
  inferencia: "border-ambar/50 text-ambar",
  neutro: "border-filete text-suave",
  alerta: "border-baixa/50 text-baixa",
} as const;

const TEXTOS = { fato: "Fato", analista: "Visão de analista", inferencia: "Inferência" } as const;

/** Marca a natureza de uma informação (regra da Inteligência do Pregão):
 * FATO (dado publicado), VISÃO DE ANALISTA (casa de research) ou
 * INFERÊNCIA (derivado pelo Pregão a partir dos dados). */
export function Selo({ tipo, texto }: { tipo: keyof typeof TONS; texto?: string }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-sm border px-1.5 py-px font-mono text-[9.5px] uppercase tracking-wider ${TONS[tipo]}`}>
      {texto || (tipo in TEXTOS ? TEXTOS[tipo as keyof typeof TEXTOS] : tipo)}
    </span>
  );
}
