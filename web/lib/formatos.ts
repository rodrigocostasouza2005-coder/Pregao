const FUSO = "America/Sao_Paulo";

export function num(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** "1,2 mi" / "340,0 mil" - mesma escala de ui/mercado_tab.py (volume financeiro em R$). */
export function numCompacto(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—";
  const abs = Math.abs(valor);
  if (abs >= 1_000_000_000) return `${num(valor / 1_000_000_000, 1)} bi`;
  if (abs >= 1_000_000) return `${num(valor / 1_000_000, 1)} mi`;
  if (abs >= 1_000) return `${num(valor / 1_000, 0)} mil`;
  return num(valor, 0);
}

export function pct(valor: number | null | undefined, casas = 2, sinal = true): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—";
  // -0,001 arredondado vira "0,00" (nunca "-0,00%")
  if (Math.abs(valor) < 0.5 / 10 ** casas) valor = 0;
  return `${sinal && valor > 0 ? "+" : ""}${num(valor, casas)}%`;
}

/** "29/10 10:35" no horário de Brasília. */
export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(d);
}

/** "29/10/2026" a partir de "2026-10-29" (data sem fuso) ou ISO completo. */
export function data(valor: string | null | undefined): string {
  if (!valor) return "—";
  const so = /^\d{4}-\d{2}-\d{2}$/.test(valor);
  if (so) {
    const [a, m, d] = valor.split("-");
    return `${d}/${m}/${a}`;
  }
  const d = new Date(valor);
  if (Number.isNaN(d.getTime())) return valor;
  return new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

/** "há 12 min", "há 3 h", "há 2 dias". */
export function idade(iso: string | null | undefined, agora = Date.now()): string {
  if (!iso) return "—";
  const ms = agora - Date.parse(iso);
  if (!Number.isFinite(ms)) return "—";
  const min = Math.round(ms / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} h`;
  return `há ${Math.round(h / 24)} dias`;
}

export function hojeSaoPaulo(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function corVariacao(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v) || v === 0) return "text-suave";
  return v > 0 ? "text-alta" : "text-baixa";
}
