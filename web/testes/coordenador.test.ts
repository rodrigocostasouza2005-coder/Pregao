import { describe, expect, it } from "vitest";

import type { EventoResultado } from "@/lib/server/dominio/agenda";
import type { IncidenteEnriquecido } from "@/lib/server/dominio/backoffice";
import { consolidar, montarItensConsolidados } from "@/lib/server/dominio/coordenador";
import type { Mudanca } from "@/lib/server/dominio/inteligencia";
import type { Divergencia } from "@/lib/server/dominio/research";

const mudanca = (p: Partial<Mudanca>): Mudanca => ({
  tipo: "Research", natureza: "analista", titulo: "XP alterou PETR4: Compra → Neutro", tickers: ["PETR4"],
  em: "2026-10-29T10:00:00Z", fonte: "XP", ...p,
});

const incidente = (p: Partial<IncidenteEnriquecido>): IncidenteEnriquecido => ({
  id: 1, chave: "NEWS|Noticias|FALHA_EXECUCAO", coletor: "NEWS (Brasil)", categoria: "Noticias", tipo: "FALHA_EXECUCAO",
  descricao: "Falha de execucao", severidade: "ATENCAO", status: "ABERTO",
  primeira_ocorrencia_em: "2026-10-20T10:00:00Z", ultima_ocorrencia_em: "2026-10-29T10:00:00Z",
  ocorrencias: 1, causa_raiz: null, commit_correcao: null, resolvido_em: null,
  rotuloEstado: "Novo", causaProvavel: "Execução falhou", proximaAcao: "Ver log", critico: true, rankPrioridade: 1,
  ...p,
});

const divergencia = (ticker: string): Divergencia => ({
  ticker, porCasa: [{ casa: "XP", recomendacao: "COMPRA", preco_alvo: null, fonte_url: null, data: null },
    { casa: "BTG", recomendacao: "VENDA", preco_alvo: null, fonte_url: null, data: null }],
});

const catalisador = (ticker: string, data: string): EventoResultado => ({
  ticker, periodo: "3T26", data_evento: data, status: "ESTIMADO", fonte: "CVM", url_fonte: null, coletado_em: "2026-10-01T00:00:00Z",
});

describe("montarItensConsolidados (Coordenador) - consolidação pura", () => {
  it("incidente crítico vem antes de uma mudança de research comum", () => {
    const itens = montarItensConsolidados([mudanca({})], [incidente({})], [], []);
    expect(itens[0].categoria).toBe("incidente");
    expect(itens[1].categoria).toBe("mudanca");
  });

  it("alerta de queda (FATO) tem prioridade maior que mudança de research (ANALISTA)", () => {
    const itens = montarItensConsolidados(
      [mudanca({ tipo: "Research", natureza: "analista" }), mudanca({ tipo: "Alerta de queda", natureza: "fato", titulo: "PETR4 caiu 5%" })],
      [], [], [],
    );
    expect(itens[0].titulo).toBe("PETR4 caiu 5%");
  });

  it("nunca apresenta a natureza de uma mudança como 'fato' quando ela é 'analista'", () => {
    const [item] = montarItensConsolidados([mudanca({ natureza: "analista" })], [], [], []);
    expect(item.natureza).toBe("analista");
  });

  it("incidente RESOLVIDO não entra na fila consolidada", () => {
    const itens = montarItensConsolidados([], [incidente({ status: "RESOLVIDO" })], [], []);
    expect(itens).toHaveLength(0);
  });

  it("deduplica incidente repetido pela mesma chave estável", () => {
    const itens = montarItensConsolidados([], [incidente({ chave: "A|B|C" }), incidente({ chave: "A|B|C" })], [], []);
    expect(itens).toHaveLength(1);
  });

  it("deduplica divergência repetida do mesmo ticker", () => {
    const itens = montarItensConsolidados([], [], [divergencia("VALE3"), divergencia("VALE3")], []);
    expect(itens).toHaveLength(1);
  });

  it("deduplica catalisador repetido do mesmo ticker+data", () => {
    const itens = montarItensConsolidados([], [], [], [catalisador("ITUB4", "2026-11-05"), catalisador("ITUB4", "2026-11-05")]);
    expect(itens).toHaveLength(1);
  });

  it("catalisadores diferentes (tickers distintos) não são deduplicados entre si", () => {
    const itens = montarItensConsolidados([], [], [], [catalisador("ITUB4", "2026-11-05"), catalisador("BBAS3", "2026-11-06")]);
    expect(itens).toHaveLength(2);
  });

  it("sem nenhuma entrada em nenhuma fonte, devolve lista vazia sem lançar", () => {
    expect(montarItensConsolidados([], [], [], [])).toEqual([]);
  });
});

describe("consolidar() - degradação graciosa sem Supabase configurado", () => {
  it("nunca lança excecao e devolve listas vazias quando nenhuma fonte está configurada", async () => {
    const saida = await consolidar();
    expect(saida.itens).toEqual([]);
    expect(saida.sintese.dados).toBeNull();
    expect(saida.incidentesAbertos).toEqual([]);
  });
});
