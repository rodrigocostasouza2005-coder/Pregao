import { describe, expect, it } from "vitest";

import { divergencias, type Recomendacao } from "@/lib/server/dominio/research";
import { classificarEstado, type StatusColetor } from "@/lib/server/dominio/saude";

const rec = (casa: string, ticker: string, recomendacao: string | null): Recomendacao => ({
  id: Math.random(), casa, carteira: "Top", ticker, empresa: null, recomendacao, preco_alvo: null,
  data_publicacao: "2026-10-01", fonte_url: null, verificado_em: null, status_coleta: null, vigente: true,
});

describe("divergências entre casas (regra do Market Researcher)", () => {
  it("só aponta com >= 2 casas e recomendações estruturadas diferentes", () => {
    const d = divergencias([rec("XP", "PETR4", "Compra"), rec("BTG", "PETR4", "Neutro"), rec("XP", "VALE3", "Compra")]);
    expect(d.map((x) => x.ticker)).toEqual(["PETR4"]);
  });
  it("sinônimos não são divergência (Compra x Buy)", () => {
    expect(divergencias([rec("XP", "ITUB4", "Compra"), rec("BTG", "ITUB4", "Buy")])).toEqual([]);
  });
  it("recomendação ausente nunca é inferida", () => {
    expect(divergencias([rec("XP", "WEGE3", "Compra"), rec("BTG", "WEGE3", null)])).toEqual([]);
  });
});

const status = (p: Partial<StatusColetor>): StatusColetor => ({
  nome: "X", fonte: null, categoria: null, execucao_ok: true, persistencia_ok: true, parcial: false,
  registros_novos: 0, ultimo_erro: null, ultima_tentativa_em: null, ultimo_sucesso_em: new Date().toISOString(), ...p,
});

describe("saúde dos coletores (port de data/saude_dados.py)", () => {
  it("sem registro = nunca executado; sem sucesso = não comprovado", () => {
    expect(classificarEstado(undefined, 6).codigo).toBe("NUNCA_EXECUTADO");
    expect(classificarEstado(status({ ultimo_sucesso_em: null }), 6).codigo).toBe("NAO_COMPROVADO");
  });
  it("erro de rede = fonte indisponível; outro erro = falha de execução", () => {
    expect(classificarEstado(status({ execucao_ok: false, ultimo_erro: "Read timed out" }), 6).codigo).toBe("FONTE_INDISPONIVEL");
    expect(classificarEstado(status({ execucao_ok: false, ultimo_erro: "KeyError" }), 6).codigo).toBe("FALHA_EXECUCAO");
  });
  it("sucesso antigo = desatualizado; novidade = sucesso com novidade", () => {
    const velho = new Date(Date.now() - 10 * 3600000).toISOString();
    expect(classificarEstado(status({ ultimo_sucesso_em: velho }), 6).codigo).toBe("DADOS_DESATUALIZADOS");
    expect(classificarEstado(status({ registros_novos: 3 }), 6).codigo).toBe("SUCESSO_COM_NOVIDADE");
  });
});
