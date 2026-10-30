"use server";

import { revalidatePath } from "next/cache";

import { usuarioAtual } from "../auth";
import { atualizarLinha } from "../supabase";
import { transicoesPermitidas, type EstadoIncidente } from "./backoffice";

/** Única escrita que a interface web faz hoje sobre inteligência/
 * backoffice: avançar o ESTADO de triagem de um achado já persistido
 * por data/market_researcher.py:registrar_achados_atuais() (ver
 * sql/market_researcher_achados.sql). Nunca cria achado, nunca altera
 * schema, nunca toca em coleta/cálculo - só o campo `status` (e
 * `resolvido_em` quando aplicável) de uma linha que já existe.
 *
 * Restrito a administrador (mesmo gate de web/app/(terminal)/
 * configuracoes/page.tsx) e a uma lista FIXA de transições (ver
 * transicoesPermitidas) - nunca aceita um valor de estado arbitrário. */
export async function definirEstadoIncidente(
  id: number, estadoAtual: EstadoIncidente, novoEstado: EstadoIncidente,
): Promise<{ ok: boolean; mensagem?: string }> {
  const usuario = await usuarioAtual();
  if (!usuario?.admin) return { ok: false, mensagem: "Só administradores podem alterar o estado de um incidente." };
  if (!transicoesPermitidas(estadoAtual).includes(novoEstado)) {
    return { ok: false, mensagem: `Transição ${estadoAtual} → ${novoEstado} não é permitida.` };
  }
  const campos: Record<string, unknown> = { status: novoEstado };
  campos.resolvido_em = novoEstado === "RESOLVIDO" ? new Date().toISOString() : null;
  const resultado = await atualizarLinha("market_researcher_achados", { id: `eq.${id}` }, campos);
  if (resultado.ok) revalidatePath("/inteligencia");
  return resultado;
}

/** Wrapper sem retorno - só pra satisfazer a tipagem de `action` do
 * <form> do React (`(formData: FormData) => void | Promise<void>`).
 * Mensagem de erro (ex.: transição não permitida) fica só no log do
 * servidor - a interface usa transicoesPermitidas() pra nunca oferecer
 * um botão de transição inválida em primeiro lugar. */
export async function definirEstadoIncidenteForm(id: number, estadoAtual: EstadoIncidente, novoEstado: EstadoIncidente): Promise<void> {
  const resultado = await definirEstadoIncidente(id, estadoAtual, novoEstado);
  if (!resultado.ok) console.error(`[backoffice] definirEstadoIncidente(${id}) falhou: ${resultado.mensagem}`);
}
