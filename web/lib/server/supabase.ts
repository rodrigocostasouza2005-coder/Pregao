import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";
import { env, supabaseConfigurado } from "./env";

const FONTE = "Supabase do Pregão";

type Consulta = {
  select: string;
  filtros?: Record<string, string>;
  ordem?: string;
  limite?: number;
  /** segundos de cache da resposta (as tabelas são alimentadas pelos coletores) */
  revalidar?: number;
};

/** Leitura somente-leitura de uma tabela via PostgREST, só no servidor e
 * com a chave secreta do mesmo projeto que os coletores usam. Nunca lança
 * exceção: devolve o estado. */
export async function lerTabela<T>(tabela: string, consulta: Consulta): Promise<Resultado<T[]>> {
  if (!supabaseConfigurado()) {
    return resultado("nao_configurado", [], FONTE, "Banco de dados não configurado neste ambiente.");
  }
  const params = new URLSearchParams({ select: consulta.select });
  for (const [coluna, filtro] of Object.entries(consulta.filtros || {})) params.append(coluna, filtro);
  if (consulta.ordem) params.set("order", consulta.ordem);
  if (consulta.limite) params.set("limit", String(consulta.limite));
  try {
    const resp = await fetch(`${env.supabaseUrl}/rest/v1/${tabela}?${params}`, {
      headers: { apikey: env.supabaseChave, Authorization: `Bearer ${env.supabaseChave}` },
      next: { revalidate: consulta.revalidar ?? 120 },
    });
    if (!resp.ok) {
      console.error(`[supabase] ${tabela}: HTTP ${resp.status} ${await resp.text().catch(() => "")}`);
      return resultado("erro", [], FONTE, "O banco de dados não respondeu a esta consulta.");
    }
    const dados = (await resp.json()) as T[];
    return resultado(dados.length ? "ok" : "vazio", dados, FONTE);
  } catch (erro) {
    console.error(`[supabase] ${tabela}:`, erro);
    return resultado("erro", [], FONTE, "O banco de dados não respondeu a esta consulta.");
  }
}
