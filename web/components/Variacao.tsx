import { corVariacao, pct } from "@/lib/formatos";

export function Variacao({ v, casas = 2 }: { v: number | null | undefined; casas?: number }) {
  return <span className={`font-mono ${corVariacao(v)}`}>{pct(v, casas)}</span>;
}
