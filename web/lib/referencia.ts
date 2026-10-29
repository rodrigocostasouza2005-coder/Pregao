import { data, dataHora, hojeSaoPaulo } from "@/lib/formatos";
import type { Cotacao } from "@/lib/server/yahoo";

/** "fech. 16/10" quando a última barra é de outra sessão; senão o
 * horário do último negócio em Brasília. Nunca inventa horário. */
export function referenciaCotacao(c: Cotacao | null): string {
  if (!c) return "—";
  if (c.sessao && c.sessao < hojeSaoPaulo()) return `fech. ${data(c.sessao).slice(0, 5)}`;
  return c.negocioEm ? dataHora(c.negocioEm) : c.sessao ? data(c.sessao) : "—";
}
