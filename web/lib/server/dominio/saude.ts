import "server-only";

import saudeJson from "@/contratos/saude_coletores.json";
import { lerTabela } from "../supabase";

type RegistroColetor = { nome: string; fonte: string; categoria: string; frequencia_esperada: string; idade_maxima_horas: number | null; instrumentado: boolean };
const SAUDE = saudeJson as { estados: Record<string, string>; termos_indisponibilidade: string[]; coletores: RegistroColetor[] };

export type StatusColetor = {
  nome: string; fonte: string | null; categoria: string | null; execucao_ok: boolean | null; persistencia_ok: boolean | null;
  parcial: boolean | null; registros_novos: number | null; ultimo_erro: string | null; ultima_tentativa_em: string | null; ultimo_sucesso_em: string | null;
};

/** Port de data/saude_dados.py:classificar_estado (mesmos códigos). */
export function classificarEstado(s: StatusColetor | undefined, idadeMaxH: number | null): { codigo: string; rotulo: string } {
  const E = SAUDE.estados;
  if (!s) return { codigo: "NUNCA_EXECUTADO", rotulo: E.NUNCA_EXECUTADO };
  const erro = s.ultimo_erro || "";
  if (!s.ultimo_sucesso_em) return { codigo: "NAO_COMPROVADO", rotulo: E.NAO_COMPROVADO };
  const idadeH = (Date.now() - Date.parse(s.ultimo_sucesso_em)) / 3600000;
  if (s.execucao_ok === false) {
    const indisponivel = SAUDE.termos_indisponibilidade.some((t) => erro.toLowerCase().includes(t));
    return indisponivel ? { codigo: "FONTE_INDISPONIVEL", rotulo: E.FONTE_INDISPONIVEL } : { codigo: "FALHA_EXECUCAO", rotulo: E.FALHA_EXECUCAO };
  }
  if (s.persistencia_ok === false) return { codigo: "FALHA_PERSISTENCIA", rotulo: E.FALHA_PERSISTENCIA };
  if (idadeMaxH !== null && idadeH > idadeMaxH) return { codigo: "DADOS_DESATUALIZADOS", rotulo: E.DADOS_DESATUALIZADOS };
  if (s.parcial) return { codigo: "PARCIAL", rotulo: E.PARCIAL };
  if (s.registros_novos) return { codigo: "SUCESSO_COM_NOVIDADE", rotulo: E.SUCESSO_COM_NOVIDADE };
  return { codigo: "SUCESSO_SEM_NOVIDADE", rotulo: E.SUCESSO_SEM_NOVIDADE };
}

export async function painelSaude() {
  const r = await lerTabela<StatusColetor>("coletores_status", {
    select: "nome,fonte,categoria,execucao_ok,persistencia_ok,parcial,registros_novos,ultimo_erro,ultima_tentativa_em,ultimo_sucesso_em",
    limite: 500,
    revalidar: 60,
  });
  const porNome = new Map(r.dados.map((s) => [s.nome, s]));
  const linhas = SAUDE.coletores.map((c) => {
    const s = porNome.get(c.nome);
    return { ...c, status: s, estado: classificarEstado(s, c.idade_maxima_horas) };
  });
  return { r, linhas };
}

export const ESTADOS_OK = new Set(["SUCESSO_COM_NOVIDADE", "SUCESSO_SEM_NOVIDADE"]);
