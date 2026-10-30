import { describe, expect, it } from "vitest";

import { type Achado, filaDeIncidentes, transicoesPermitidas } from "@/lib/server/dominio/backoffice";

const achado = (p: Partial<Achado>): Achado => ({
  id: 1, chave: "X|Y|Z", coletor: "NEWS (Brasil)", categoria: "Noticias", tipo: "FALHA_EXECUCAO",
  descricao: "Falha de execucao", severidade: "ATENCAO", status: "ABERTO",
  primeira_ocorrencia_em: "2026-10-20T10:00:00Z", ultima_ocorrencia_em: "2026-10-29T10:00:00Z",
  ocorrencias: 1, causa_raiz: null, commit_correcao: null, resolvido_em: null, ...p,
});

describe("fila de incidentes (Backoffice) - priorização", () => {
  it("categoria crítica vem antes de uma não-crítica mesmo com o mesmo tipo de estado", () => {
    const naoCritico = achado({ id: 1, categoria: "Calendario", severidade: "ATENCAO" });
    const critico = achado({ id: 2, categoria: "Noticias", severidade: "ATENCAO" }); // Noticias é categoria crítica
    const fila = filaDeIncidentes([naoCritico, critico]);
    expect(fila[0].id).toBe(2);
  });

  it("FALHA_PERSISTENCIA é mais grave que DADOS_DESATUALIZADOS dentro da mesma criticidade", () => {
    const desatualizado = achado({ id: 1, tipo: "DADOS_DESATUALIZADOS" });
    const falhaPersist = achado({ id: 2, tipo: "FALHA_PERSISTENCIA" });
    const fila = filaDeIncidentes([desatualizado, falhaPersist]);
    expect(fila[0].id).toBe(2);
  });

  it("empate de prioridade desempata por mais ocorrências, depois mais recente", () => {
    const poucasOcorrencias = achado({ id: 1, tipo: "PARCIAL", ocorrencias: 1, ultima_ocorrencia_em: "2026-10-29T08:00:00Z" });
    const muitasOcorrencias = achado({ id: 2, tipo: "PARCIAL", ocorrencias: 5, ultima_ocorrencia_em: "2026-10-29T08:00:00Z" });
    const fila = filaDeIncidentes([poucasOcorrencias, muitasOcorrencias]);
    expect(fila[0].id).toBe(2);
  });

  it("nunca inventa causa/ação pra um tipo de estado desconhecido", () => {
    const [item] = filaDeIncidentes([achado({ tipo: "ALGO_NOVO_NAO_MAPEADO" })]);
    expect(item.causaProvavel).toBeNull();
    expect(item.proximaAcao).toBeNull();
  });

  it("achado real (FALHA_EXECUCAO) sempre tem causa provável e próxima ação, nunca vazio", () => {
    const [item] = filaDeIncidentes([achado({ tipo: "FALHA_EXECUCAO" })]);
    expect(item.causaProvavel).toBeTruthy();
    expect(item.proximaAcao).toBeTruthy();
  });
});

describe("transições de estado do incidente (triagem manual)", () => {
  it("ABERTO pode ir para qualquer estado de triagem", () => {
    expect(transicoesPermitidas("ABERTO")).toContain("INVESTIGANDO");
    expect(transicoesPermitidas("ABERTO")).toContain("RESOLVIDO");
  });
  it("RESOLVIDO só pode ser reaberto manualmente, nunca ir direto para INCONCLUSIVO", () => {
    expect(transicoesPermitidas("RESOLVIDO")).toEqual(["ABERTO"]);
  });
  it("estado desconhecido não permite transição nenhuma (nunca quebra, nunca libera tudo)", () => {
    // @ts-expect-error - testando entrada inválida de propósito
    expect(transicoesPermitidas("NAO_EXISTE")).toEqual([]);
  });
});
