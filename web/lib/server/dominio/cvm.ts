import "server-only";

import { lerTabela } from "../supabase";

export type DocumentoCvm = { link: string; ticker: string; tipo: string; assunto: string; data: string | null; destaque: boolean; coletado_em: string };

export function lerDocumentosCvm(limite = 150, filtros?: Record<string, string>) {
  return lerTabela<DocumentoCvm>("cvm_documentos", {
    select: "link,ticker,tipo,assunto,data,destaque,coletado_em",
    ordem: "coletado_em.desc",
    limite,
    filtros,
  });
}
