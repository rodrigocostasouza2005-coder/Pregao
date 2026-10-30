import { ESTADOS_OK, painelSaude } from "@/lib/server/dominio/saude";

const FALHA = new Set(["FALHA_EXECUCAO", "FALHA_PERSISTENCIA", "FONTE_INDISPONIVEL"]);
const ATENCAO = new Set(["DADOS_DESATUALIZADOS", "PARCIAL"]);

/** Resumo compacto da saúde dos coletores pro indicador do cabeçalho
 * (IndicadorSaude.tsx) - mesma classificação de data/saude_dados.py via
 * painelSaude(), só agregada. Nunca inventa estado: "falha" só conta
 * coletor com problema real, nunca ausência de dado novo. */
export async function GET() {
  const { r, linhas } = await painelSaude();
  const ok = linhas.filter((l) => ESTADOS_OK.has(l.estado.codigo)).length;
  const falhas = linhas.filter((l) => FALHA.has(l.estado.codigo)).length;
  const atencao = linhas.filter((l) => ATENCAO.has(l.estado.codigo)).length;
  const ultimaColetaEm = linhas.reduce<string | null>((max, l) => {
    const t = l.status?.ultimo_sucesso_em;
    return t && (!max || t > max) ? t : max;
  }, null);
  const nivel = r.estado === "erro" || r.estado === "nao_configurado" ? "indisponivel" : falhas > 0 ? "falha" : atencao > 0 ? "atencao" : "ok";
  return Response.json({ nivel, ok, falhas, atencao, total: linhas.length, ultimaColetaEm });
}
