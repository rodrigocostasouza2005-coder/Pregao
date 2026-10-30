import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";
import { lerTabela } from "../supabase";
import { type EventoResultado, lerResultadosFuturos } from "./agenda";
import { filaDeIncidentes, lerAchados, type IncidenteEnriquecido } from "./backoffice";
import { oQueMudou, type Mudanca } from "./inteligencia";
import { CASAS, coberturaPorTicker, divergencias, type Divergencia, lerCarteiras } from "./research";

/** Coordenador de Inteligência (Fase 2 do pedido) - NÃO recalcula nada:
 * só lê o que os especialistas já persistem (oQueMudou, divergências,
 * achados do Backoffice, catalisadores, síntese de IA) e consolida numa
 * visão única, priorizada, com a natureza de cada item sempre explícita.
 * Nenhuma ordem/venda, nenhuma inferência apresentada como fato. */

// --- Síntese executiva via IA (data/sintese_mercado.py) -------------------

export type Movimento = {
  evento: string; fonte: string; data_fonte?: string | null; por_que_importa?: string | null;
  impacto_possivel?: string | null; horizonte?: string | null; confianca: string; confianca_motivo?: string | null;
};
export type OportunidadeRisco = {
  ativo_ou_setor: string; catalisador?: string | null; argumento_favoravel?: string | null;
  argumento_contrario?: string | null; acompanhar?: string | null; fonte: string; data_fonte?: string | null;
};
export type Cenario = { tipo: "principal" | "alternativo"; cenario: string; condicao?: string | null; sinalizadores?: string | null };
export type ItemObservar = { item: string; motivo?: string | null; fonte?: string | null; data_fonte?: string | null };
export type SinteseDados = {
  resumo_executivo: { texto: string; ressalvas: string }; movimentos: Movimento[]; oportunidades_riscos: OportunidadeRisco[];
  cenarios: Cenario[]; observar_proximas_sessoes: ItemObservar[]; o_que_nao_sabemos: string[];
};
export type SinteseMercado = {
  dados: SinteseDados; modelo: string | null; geradoEm: string | null; criadoEm: string; desatualizada: boolean;
  fontesIndisponiveis: string[];
};

type LinhaCacheIa = { resultado: { dados?: SinteseDados; modelo?: string; fatos_gerado_em?: string; fontes_indisponiveis?: string[] } | null; criado_em: string };

/** Lê a última síntese CONCLUÍDA (resumos_ia_cache, origem='sintese_mercado')
 * - mesma tabela/mesmo formato que data/sintese_mercado.py já grava,
 * gerada pelo job agendado (jobs/coordenador.py) em vez de só sob
 * demanda no Streamlit. `desatualizada` sinaliza quando a última síntese
 * é mais velha que ~2 ciclos de agendamento (90min) - nunca apresentada
 * como "agora" nesse caso, mesma cautela de obter_sintese_mercado(). */
export async function lerSinteseMercado(): Promise<Resultado<SinteseMercado | null>> {
  const r = await lerTabela<LinhaCacheIa>("resumos_ia_cache", {
    select: "resultado,criado_em",
    filtros: { origem: "eq.sintese_mercado", status: "eq.concluido" },
    ordem: "criado_em.desc",
    limite: 1,
    revalidar: 300,
  });
  if (r.estado !== "ok" || !r.dados[0]?.resultado?.dados) {
    return { ...r, dados: null } as Resultado<SinteseMercado | null>;
  }
  const linha = r.dados[0];
  const criadoEm = linha.criado_em;
  const idadeMin = (Date.now() - Date.parse(criadoEm)) / 60000;
  const sintese: SinteseMercado = {
    dados: linha.resultado!.dados!, modelo: linha.resultado!.modelo ?? null,
    geradoEm: linha.resultado!.fatos_gerado_em ?? null, criadoEm, desatualizada: idadeMin > 90,
    fontesIndisponiveis: linha.resultado!.fontes_indisponiveis ?? [],
  };
  return resultado("ok", sintese, r.fonte);
}

// --- Consolidação ----------------------------------------------------------

export type Natureza = "fato" | "analista" | "inferencia" | "calculo" | "insuficiente";

export type ItemConsolidado = {
  categoria: "mudanca" | "incidente" | "divergencia" | "catalisador";
  natureza: Natureza;
  titulo: string;
  detalhe?: string | null;
  tickers: string[];
  em: string;
  fonte: string;
  link?: string | null;
  prioridade: number; // menor = mais urgente/relevante; usado só pra ordenar
};

function deChaveMudanca(m: Mudanca): string {
  return `mudanca|${m.tipo}|${m.tickers.join(",")}|${m.titulo}`;
}

/** Monta e ordena os itens consolidados a partir do que cada
 * especialista JÁ calculou (parâmetros, nunca busca nada aqui) - função
 * PURA, testável sem rede/Supabase (mesmo padrão de
 * dominio/research.ts:divergencias). Deduplica por chave estável:
 * - incidente: a própria `chave` do Backoffice (coletor|categoria|tipo);
 * - mudança: tipo+tickers+título (idêntico ao que oQueMudou já produziria
 *   de novo pra o mesmo evento);
 * - divergência: 1 por ticker;
 * - catalisador: 1 por ticker+data.
 * Prioridade (menor = mais urgente): incidente crítico (Backoffice) <
 * alerta de queda < resultado/earnings < CVM < divergência < mudança de
 * research < catalisador futuro. Nunca inventa prioridade pra um item
 * sem evidência real - todo item aqui veio de uma leitura que já
 * aconteceu. */
export function montarItensConsolidados(
  mudancas: Mudanca[], fila: IncidenteEnriquecido[], div: Divergencia[], catalisadores: EventoResultado[],
): ItemConsolidado[] {
  const vistos = new Set<string>();
  const itens: ItemConsolidado[] = [];

  for (const a of fila) {
    if (a.status === "RESOLVIDO") continue; // resolvido não é mais um achado ativo pra priorizar
    const chave = `incidente|${a.chave}`;
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    itens.push({
      categoria: "incidente", natureza: "fato", tickers: [], em: a.ultima_ocorrencia_em, fonte: a.coletor,
      titulo: `${a.coletor}: ${a.rotuloEstado}${a.ocorrencias > 1 ? ` (${a.ocorrencias}x desde ${a.primeira_ocorrencia_em.slice(0, 10)})` : ""}`,
      detalhe: a.causaProvavel ? `Causa provável: ${a.causaProvavel} · Próxima ação: ${a.proximaAcao}` : a.descricao,
      prioridade: a.rankPrioridade,
    });
  }

  for (const m of mudancas) {
    const chave = deChaveMudanca(m);
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    const prioridadeBase = m.tipo === "Alerta de queda" ? 10 : m.tipo === "Resultado" ? 20 : m.tipo === "CVM" ? 30 : 40;
    itens.push({
      categoria: "mudanca", natureza: m.natureza as Natureza, tickers: m.tickers, em: m.em, fonte: m.fonte,
      titulo: m.titulo, detalhe: m.detalhe, link: m.link, prioridade: prioridadeBase,
    });
  }

  for (const d of div) {
    const chave = `divergencia|${d.ticker}`;
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    itens.push({
      categoria: "divergencia", natureza: "fato", tickers: [d.ticker], em: new Date().toISOString(), fonte: "Comitê de research (casas monitoradas)",
      titulo: `Divergência em ${d.ticker}: ${d.porCasa.map((p) => `${p.casa} ${p.recomendacao}`).join(" × ")}`,
      prioridade: 35,
    });
  }

  for (const e of catalisadores) {
    const chave = `catalisador|${e.ticker}|${e.data_evento}`;
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    itens.push({
      categoria: "catalisador", natureza: "fato", tickers: [e.ticker], em: e.data_evento, fonte: e.fonte || "Calendário (CVM)",
      titulo: `${e.ticker}: resultado ${e.periodo} (${e.status})`, link: e.url_fonte, prioridade: 50,
    });
  }

  return itens.sort((x, y) => x.prioridade - y.prioridade || y.em.localeCompare(x.em));
}

/** Visão consolidada da Inteligência (Fase 2 do pedido): busca tudo que
 * os especialistas já persistem e delega a consolidação pra
 * montarItensConsolidados (pura, testada em separado). Nunca emite
 * ordem de compra/venda; nunca apresenta inferência como fato (ver
 * campo `natureza` de cada item). */
export async function consolidar(limite = 80) {
  const [mudou, carteiras, agenda, achados, sintese] = await Promise.all([
    oQueMudou(limite), lerCarteiras(), lerResultadosFuturos(), lerAchados(200), lerSinteseMercado(),
  ]);

  const div = divergencias(carteiras.dados);
  const cobertura = coberturaPorTicker(carteiras.dados);
  const cobertos = new Set(cobertura.map((c) => c.ticker));
  const limiteCatalisador = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
  const catalisadores = agenda.dados.filter((e) => e.data_evento <= limiteCatalisador && cobertos.has(e.ticker));
  const fila = filaDeIncidentes(achados.dados);

  const itens = montarItensConsolidados(mudou.r.dados, fila, div, catalisadores);

  const fontesIndisponiveis = [
    ...mudou.parciais,
    ...(carteiras.estado === "erro" ? ["Research/carteiras: " + (carteiras.mensagem || "indisponível")] : []),
    ...(agenda.estado === "erro" ? ["Agenda/catalisadores: " + (agenda.mensagem || "indisponível")] : []),
    ...(achados.estado === "erro" ? ["Backoffice: " + (achados.mensagem || "indisponível")] : []),
  ];

  return {
    itens, sintese, fontesIndisponiveis,
    casasSemCarteira: CASAS.filter((c) => c.ativa_por_padrao).map((c) => c.nome)
      .filter((nome) => !carteiras.dados.some((c) => c.casa === nome)),
    incidentesAbertos: fila.filter((a) => a.status !== "RESOLVIDO"),
  };
}
