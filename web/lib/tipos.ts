/** Resultado de toda leitura de dados da interface: o estado é explícito
 * para a tela nunca confundir "fonte fora do ar" com "não há dados" nem
 * com "integração ainda não configurada". */
export type EstadoDados = "ok" | "vazio" | "erro" | "nao_configurado";

export type Resultado<T> = {
  estado: EstadoDados;
  dados: T;
  /** mensagem para o usuário (nunca stack trace, host ou segredo) */
  mensagem?: string;
  /** de onde veio o dado, para exibir na tela */
  fonte: string;
  /** momento da leitura (ISO) */
  lidoEm: string;
};

export function resultado<T>(estado: EstadoDados, dados: T, fonte: string, mensagem?: string): Resultado<T> {
  return { estado, dados, fonte, mensagem, lidoEm: new Date().toISOString() };
}
