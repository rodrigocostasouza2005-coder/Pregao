/** Formatação pt-BR (vírgula decimal, ponto de milhar) - mesmo padrão
 * do app Python (config.formatar_numero). */
export function formatarNumero(valor: number, casas = 2): string {
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

export function formatarPct(valor: number): string {
  const sinal = valor >= 0 ? "+" : "";
  return `${sinal}${formatarNumero(valor, 2)}%`;
}

export function classeVariacao(valor: number): "alta" | "baixa" {
  return valor >= 0 ? "alta" : "baixa";
}
