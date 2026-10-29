import "server-only";

import casasJson from "@/contratos/casas_research.json";
import { resultado, type Resultado } from "@/lib/tipos";
import { lerTabela } from "../supabase";

export type CasaResearch = { id: string; nome: string; fonte: string | null; ativa_por_padrao: boolean };
export const CASAS = (casasJson as { casas: CasaResearch[] }).casas;

export type ItemResearch = {
  link: string; casa: string; titulo: string; data: string | null; autor: string | null; tipo: string;
  tickers: string[]; resumo: string | null; recomendacao: string | null; preco_alvo: number | null;
  publicado_em: string | null; coletado_em: string;
};

export type Recomendacao = {
  id: number; casa: string; carteira: string; ticker: string; empresa: string | null; recomendacao: string | null;
  preco_alvo: number | null; data_publicacao: string | null; fonte_url: string | null; verificado_em: string | null;
  status_coleta: string | null; vigente: boolean;
};

export type MudancaRecomendacao = {
  casa: string; ticker: string; antes: { recomendacao: string | null; preco_alvo: number | null } | null;
  depois: { recomendacao: string | null; preco_alvo: number | null; potencial_pct: number | null }; em: string;
};

export function lerItens(limite = 120): Promise<Resultado<ItemResearch[]>> {
  return lerTabela<ItemResearch>("research_itens", {
    select: "link,casa,titulo,data,autor,tipo,tickers,resumo,recomendacao,preco_alvo,publicado_em,coletado_em",
    ordem: "data.desc.nullslast,coletado_em.desc",
    limite,
  });
}

export function lerCarteiras(): Promise<Resultado<Recomendacao[]>> {
  return lerTabela<Recomendacao>("radar_carteiras_recomendadas", {
    select: "id,casa,carteira,ticker,empresa,recomendacao,preco_alvo,data_publicacao,fonte_url,verificado_em,status_coleta,vigente",
    filtros: { vigente: "eq.true" },
    ordem: "casa.asc,ticker.asc",
    limite: 500,
  });
}

/** Mudanças reais de recomendação/preço-alvo a partir do histórico
 * capturado pelos coletores (research_recomendacoes_historico): compara
 * cada captura com a anterior da mesma casa+ticker. Primeira captura de
 * um par = "início de cobertura" (antes = null). */
export async function mudancasRecomendacao(limite = 60): Promise<Resultado<MudancaRecomendacao[]>> {
  const r = await lerTabela<{ casa: string; ticker: string; recomendacao: string | null; preco_alvo: number | null; potencial_pct: number | null; capturado_em: string }>(
    "research_recomendacoes_historico",
    { select: "casa,ticker,recomendacao,preco_alvo,potencial_pct,capturado_em", ordem: "capturado_em.asc", limite: 5000 },
  );
  if (r.estado !== "ok") return { ...r, dados: [] };
  const ultimo = new Map<string, (typeof r.dados)[number]>();
  const mudancas: MudancaRecomendacao[] = [];
  for (const h of r.dados) {
    const chave = `${h.casa}|${h.ticker}`;
    const ant = ultimo.get(chave);
    const mudou = !ant || ant.recomendacao !== h.recomendacao || Number(ant.preco_alvo) !== Number(h.preco_alvo);
    if (mudou) {
      mudancas.push({
        casa: h.casa, ticker: h.ticker,
        antes: ant ? { recomendacao: ant.recomendacao, preco_alvo: ant.preco_alvo } : null,
        depois: { recomendacao: h.recomendacao, preco_alvo: h.preco_alvo, potencial_pct: h.potencial_pct },
        em: h.capturado_em,
      });
    }
    ultimo.set(chave, h);
  }
  const lista = mudancas.reverse().slice(0, limite);
  return resultado(lista.length ? "ok" : "vazio", lista, r.fonte);
}

export type Divergencia = { ticker: string; porCasa: Array<{ casa: string; recomendacao: string; preco_alvo: number | null; fonte_url: string | null; data: string | null }> };

function normalizarRec(r: string | null) {
  const t = (r || "").toLowerCase();
  if (/compra|buy|outperform|overweight/.test(t)) return "COMPRA";
  if (/venda|sell|underperform|underweight/.test(t)) return "VENDA";
  if (/neutr|hold|manter|market ?perform|equal/.test(t)) return "NEUTRO";
  return t ? t.toUpperCase() : "";
}

/** Regra do Market Researcher (data/market_researcher.py:
 * cobertura_cruzada_casas): divergência só quando >= 2 casas têm
 * recomendação ESTRUTURADA diferente para o mesmo ticker - nunca inferida. */
export function divergencias(carteiras: Recomendacao[]): Divergencia[] {
  const porTicker = new Map<string, Recomendacao[]>();
  for (const c of carteiras) if (c.recomendacao) porTicker.set(c.ticker, [...(porTicker.get(c.ticker) || []), c]);
  const saida: Divergencia[] = [];
  for (const [ticker, lista] of porTicker) {
    const porCasa = new Map<string, Recomendacao>();
    for (const c of lista) if (!porCasa.has(c.casa)) porCasa.set(c.casa, c);
    const normais = new Set([...porCasa.values()].map((c) => normalizarRec(c.recomendacao)));
    if (porCasa.size >= 2 && normais.size > 1) {
      saida.push({
        ticker,
        porCasa: [...porCasa.values()].map((c) => ({ casa: c.casa, recomendacao: c.recomendacao as string, preco_alvo: c.preco_alvo, fonte_url: c.fonte_url, data: c.data_publicacao })),
      });
    }
  }
  return saida.sort((a, b) => a.ticker.localeCompare(b.ticker));
}

/** Consenso observado (só contagem do que as casas publicaram). */
export function coberturaPorTicker(carteiras: Recomendacao[]) {
  const mapa = new Map<string, Set<string>>();
  for (const c of carteiras) mapa.set(c.ticker, new Set([...(mapa.get(c.ticker) || []), c.casa]));
  return [...mapa.entries()].map(([ticker, casas]) => ({ ticker, casas: [...casas] })).sort((a, b) => b.casas.length - a.casas.length);
}

export function lerItensDoTicker(ticker: string, limite = 30) {
  return lerTabela<ItemResearch>("research_itens", {
    select: "link,casa,titulo,data,autor,tipo,tickers,resumo,recomendacao,preco_alvo,publicado_em,coletado_em",
    filtros: { tickers: `cs.{${ticker}}` },
    ordem: "data.desc.nullslast",
    limite,
  });
}

export function buscarItens(termo: string, limite = 20) {
  const t = termo.replace(/[%,()*]/g, " ").trim();
  return lerTabela<ItemResearch>("research_itens", {
    select: "link,casa,titulo,data,autor,tipo,tickers,resumo,recomendacao,preco_alvo,publicado_em,coletado_em",
    filtros: { titulo: `ilike.*${t}*` },
    ordem: "data.desc.nullslast",
    limite,
  });
}
