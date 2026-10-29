import { beforeEach, describe, expect, it, vi } from "vitest";

const usuarioAtualMock = vi.fn();
const atualizarLinhaMock = vi.fn();
const revalidatePathMock = vi.fn();

vi.mock("@/lib/server/auth", () => ({ usuarioAtual: usuarioAtualMock }));
vi.mock("next/cache", () => ({ revalidatePath: revalidatePathMock }));
vi.mock("@/lib/server/supabase", () => ({ atualizarLinha: atualizarLinhaMock }));

const { definirEstadoIncidente } = await import("@/lib/server/dominio/backofficeAcoes");

beforeEach(() => {
  usuarioAtualMock.mockReset();
  atualizarLinhaMock.mockReset();
  revalidatePathMock.mockReset();
});

describe("definirEstadoIncidente - permissões e isolamento (Fase 7, item 10)", () => {
  it("usuário não-admin nunca consegue alterar o estado de um incidente", async () => {
    usuarioAtualMock.mockResolvedValue({ sub: "1", email: "quem@x.com", nome: "Quem", admin: false });
    const r = await definirEstadoIncidente(1, "ABERTO", "INVESTIGANDO");
    expect(r.ok).toBe(false);
    expect(atualizarLinhaMock).not.toHaveBeenCalled();
  });

  it("sem sessão (deslogado) também não consegue alterar", async () => {
    usuarioAtualMock.mockResolvedValue(null);
    const r = await definirEstadoIncidente(1, "ABERTO", "RESOLVIDO");
    expect(r.ok).toBe(false);
    expect(atualizarLinhaMock).not.toHaveBeenCalled();
  });

  it("admin não pode forçar uma transição fora da whitelist (ex.: ABERTO -> ABERTO não listado como novidade, RESOLVIDO -> INCONCLUSIVO direto)", async () => {
    usuarioAtualMock.mockResolvedValue({ sub: "1", email: "admin@x.com", nome: "Admin", admin: true });
    const r = await definirEstadoIncidente(1, "RESOLVIDO", "INCONCLUSIVO");
    expect(r.ok).toBe(false);
    expect(r.mensagem).toMatch(/não é permitida/);
    expect(atualizarLinhaMock).not.toHaveBeenCalled();
  });

  it("admin com transição permitida grava só status/resolvido_em - nunca outro campo - e revalida a página", async () => {
    usuarioAtualMock.mockResolvedValue({ sub: "1", email: "admin@x.com", nome: "Admin", admin: true });
    atualizarLinhaMock.mockResolvedValue({ ok: true });
    const r = await definirEstadoIncidente(42, "ABERTO", "INVESTIGANDO");
    expect(r.ok).toBe(true);
    expect(atualizarLinhaMock).toHaveBeenCalledWith(
      "market_researcher_achados", { id: "eq.42" }, { status: "INVESTIGANDO", resolvido_em: null },
    );
    expect(revalidatePathMock).toHaveBeenCalledWith("/inteligencia");
  });

  it("transição para RESOLVIDO grava resolvido_em com timestamp, nunca null", async () => {
    usuarioAtualMock.mockResolvedValue({ sub: "1", email: "admin@x.com", nome: "Admin", admin: true });
    atualizarLinhaMock.mockResolvedValue({ ok: true });
    await definirEstadoIncidente(42, "ABERTO", "RESOLVIDO");
    const [, , campos] = atualizarLinhaMock.mock.calls[0];
    expect(campos.status).toBe("RESOLVIDO");
    expect(typeof campos.resolvido_em).toBe("string");
  });

  it("falha de escrita no banco não revalida a página (evita mostrar sucesso falso)", async () => {
    usuarioAtualMock.mockResolvedValue({ sub: "1", email: "admin@x.com", nome: "Admin", admin: true });
    atualizarLinhaMock.mockResolvedValue({ ok: false, mensagem: "indisponível" });
    const r = await definirEstadoIncidente(42, "ABERTO", "INVESTIGANDO");
    expect(r.ok).toBe(false);
    expect(revalidatePathMock).not.toHaveBeenCalled();
  });
});
