import "server-only";

import { lerTabela } from "../supabase";

/** Documentos da CVM são persistidos em research_itens (casa="CVM"),
 * NUNCA numa tabela "cvm_documentos" própria - são o mesmo mecanismo de
 * upsert por link que as casas de research usam (ver data/cvm.py:
 * salvar_documentos, que converte pro formato de data/research/
 * store.salvar_itens de propósito, pra reaproveitar a limpeza/retenção
 * que já existe lá). A versão anterior deste arquivo consultava uma
 * tabela "cvm_documentos" que nunca existiu no Supabase - a aba CVM e a
 * seção CVM da página de ativo sempre voltavam erro/vazio na Vercel. */
const CASA_CVM = "CVM";

export type DocumentoCvm = { link: string; tickers: string[]; tipo: string; titulo: string; data: string | null; destaque: boolean; coletado_em: string };

type LinhaResearchItens = { link: string; tickers: string[] | null; tipo: string | null; titulo: string | null; data: string | null; coletado_em: string };

async function lerCvm(limite: number, filtrosExtra: Record<string, string> = {}) {
  const r = await lerTabela<LinhaResearchItens>("research_itens", {
    select: "link,tickers,tipo,titulo,data,coletado_em",
    ordem: "data.desc,coletado_em.desc",
    limite,
    filtros: { casa: `eq.${CASA_CVM}`, ...filtrosExtra },
  });
  return { ...r, dados: r.dados.map((d): DocumentoCvm => ({
    link: d.link, tickers: d.tickers || [], tipo: d.tipo || "", titulo: d.titulo || "",
    data: d.data, coletado_em: d.coletado_em, destaque: d.tipo === "FATO_RELEVANTE",
  })) };
}

export function lerDocumentosCvm(limite = 150, opcoes?: { ticker?: string; destaque?: boolean }) {
  const filtros: Record<string, string> = {};
  if (opcoes?.ticker) filtros.tickers = `cs.{${opcoes.ticker}}`;
  if (opcoes?.destaque) filtros.tipo = "eq.FATO_RELEVANTE";
  return lerCvm(limite, filtros);
}
