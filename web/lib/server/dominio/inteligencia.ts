import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";
import { lerTabela } from "../supabase";
import { lerDocumentosCvm } from "./cvm";
import { mudancasRecomendacao } from "./research";

export type Natureza = "fato" | "analista" | "inferencia";

/** Um item de "O que mudou?": sempre com natureza, data, fonte e ativos. */
export type Mudanca = {
  tipo: "Research" | "CVM" | "Alerta de queda" | "Resultado";
  natureza: Natureza;
  titulo: string;
  detalhe?: string;
  tickers: string[];
  em: string;
  fonte: string;
  link?: string | null;
};

export type AlertaQueda = {
  id: number; ticker: string; empresa: string | null; pregao: string; preco_atual: number | null; fechamento_anterior: number | null;
  variacao_pct: number | null; cotacao_em: string | null; tipo_cotacao: string | null; casas: string[] | null; carteiras: string[] | null;
  fontes: string[] | null; alertado_em: string; status: string | null;
};

export function lerAlertasQueda(limite = 60) {
  return lerTabela<AlertaQueda>("radar_alertas_queda", {
    select: "id,ticker,empresa,pregao,preco_atual,fechamento_anterior,variacao_pct,cotacao_em,tipo_cotacao,casas,carteiras,fontes,alertado_em,status",
    ordem: "alertado_em.desc",
    limite,
  });
}

export type NotaEarnings = {
  id: number; ticker: string; pais: string; periodo_label: string; gerado_em: string;
  conteudo: {
    empresa?: string; metricas?: Record<string, Record<string, number | null>>; interpretacoes?: string[];
    limitacoes?: string[]; fontes?: Array<{ nome?: string; url?: string }>; moeda?: string; escala_moeda?: string;
  };
};

export function lerEarnings(limite = 40, ticker?: string) {
  return lerTabela<NotaEarnings>("earnings_reviews", {
    select: "id,ticker,pais,periodo_label,gerado_em,conteudo",
    ordem: "gerado_em.desc",
    limite,
    filtros: ticker ? { ticker: `eq.${ticker}` } : undefined,
  });
}

/** "O que mudou?" - consolida as mudanças registradas pelos coletores e
 * agentes, mais recente primeiro. Cada fonte degrada sozinha. */
export async function oQueMudou(limite = 80): Promise<{ r: Resultado<Mudanca[]>; parciais: string[] }> {
  const [rec, cvm, quedas, earnings] = await Promise.all([
    mudancasRecomendacao(40),
    lerDocumentosCvm(40, { destaque: "eq.true" }),
    lerAlertasQueda(30),
    lerEarnings(20),
  ]);
  const parciais = [rec, cvm, quedas, earnings].filter((x) => x.estado === "erro" || x.estado === "nao_configurado").map((x) => `${x.fonte}: ${x.mensagem}`);
  const itens: Mudanca[] = [];
  for (const m of rec.dados) {
    const depois = `${m.depois.recomendacao || "—"}${m.depois.preco_alvo ? ` · alvo R$ ${Number(m.depois.preco_alvo).toFixed(2)}` : ""}`;
    const antes = m.antes ? `${m.antes.recomendacao || "—"}${m.antes.preco_alvo ? ` · alvo R$ ${Number(m.antes.preco_alvo).toFixed(2)}` : ""}` : null;
    itens.push({
      tipo: "Research", natureza: "analista", tickers: [m.ticker], em: m.em, fonte: m.casa,
      titulo: antes ? `${m.casa} alterou ${m.ticker}: ${antes} → ${depois}` : `${m.casa} passou a cobrir ${m.ticker}: ${depois}`,
    });
  }
  for (const d of cvm.dados) {
    itens.push({ tipo: "CVM", natureza: "fato", tickers: [d.ticker], em: d.coletado_em, fonte: "CVM", link: d.link, titulo: `${d.ticker} · ${d.tipo}`, detalhe: d.assunto });
  }
  for (const q of quedas.dados) {
    itens.push({
      tipo: "Alerta de queda", natureza: "fato", tickers: [q.ticker], em: q.alertado_em, fonte: (q.fontes || []).join(", ") || "Radar de quedas",
      titulo: `${q.ticker} caiu ${q.variacao_pct !== null ? Number(q.variacao_pct).toFixed(2) : "?"}% no pregão de ${q.pregao}`,
      detalhe: q.casas?.length ? `Recomendado por: ${q.casas.join(", ")}` : undefined,
    });
  }
  for (const e of earnings.dados) {
    itens.push({
      tipo: "Resultado", natureza: "fato", tickers: [e.ticker], em: e.gerado_em, fonte: e.conteudo.fontes?.[0]?.nome || "CVM/SEC",
      link: e.conteudo.fontes?.[0]?.url, titulo: `${e.ticker} · resultado ${e.periodo_label} processado`, detalhe: e.conteudo.empresa,
    });
  }
  itens.sort((a, b) => b.em.localeCompare(a.em));
  const lista = itens.slice(0, limite);
  const fonte = "Coletores e agentes do Pregão (Supabase)";
  const fontes = [rec, cvm, quedas, earnings];
  // sem nenhuma fonte respondendo, "nenhuma mudança" seria falso: o
  // estado da leitura sobe (não configurado / indisponível)
  if (!lista.length && fontes.every((x) => x.estado === "nao_configurado")) {
    return { r: resultado("nao_configurado", [], fonte, fontes[0].mensagem), parciais: [] };
  }
  if (!lista.length && fontes.every((x) => x.estado === "erro" || x.estado === "nao_configurado")) {
    return { r: resultado("erro", [], fonte, "Nenhuma das fontes de mudanças respondeu."), parciais: [] };
  }
  return { r: resultado(lista.length ? "ok" : "vazio", lista, fonte), parciais };
}
