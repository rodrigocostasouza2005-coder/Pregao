import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";
import { lerTabela } from "../supabase";

export type Edicao = { dia: string; executadoEm: string; conteudo: string; envios: number };

/** Edições do Morning Call registradas pelo job (morning_call_execucoes):
 * uma linha por destinatário, agrupada por dia. A coluna `destinatario`
 * (e-mail) NUNCA é lida pela interface. */
export async function lerEdicoes(limite = 30): Promise<Resultado<Edicao[]>> {
  const r = await lerTabela<{ executado_em: string; status: string; conteudo: string | null }>("morning_call_execucoes", {
    select: "executado_em,status,conteudo",
    filtros: { status: "eq.ENVIADO" },
    ordem: "executado_em.desc",
    limite: 400,
  });
  if (r.estado !== "ok") return { ...r, dados: [] };
  const porDia = new Map<string, Edicao>();
  for (const l of r.dados) {
    const dia = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date(l.executado_em));
    const e = porDia.get(dia);
    if (e) e.envios += 1;
    else if (l.conteudo) porDia.set(dia, { dia, executadoEm: l.executado_em, conteudo: l.conteudo, envios: 1 });
  }
  const lista = [...porDia.values()].slice(0, limite);
  return resultado(lista.length ? "ok" : "vazio", lista, r.fonte);
}

export type SecaoMorningCall = { titulo: string; linhas: string[] };

/** Separa o texto do e-mail nas seções numeradas que o job já produz
 * ("1. RESUMO EXECUTIVO", "2. BRASIL", ...). */
export function secoes(conteudo: string): SecaoMorningCall[] {
  const saida: SecaoMorningCall[] = [];
  let atual: SecaoMorningCall | null = null;
  for (const bruta of conteudo.split("\n")) {
    const linha = bruta.trimEnd();
    if (/^(\d+\.\s+[A-ZÀ-Ý ]{4,}|LIMITAÇÕES|FONTES)$/.test(linha.trim())) {
      atual = { titulo: linha.trim().replace(/^\d+\.\s+/, ""), linhas: [] };
      saida.push(atual);
    } else if (atual && linha.trim()) {
      atual.linhas.push(linha.trim());
    }
  }
  return saida;
}
