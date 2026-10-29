import type { Resultado } from "@/lib/tipos";

const ROTULO: Record<string, string> = {
  vazio: "Sem dados",
  erro: "Fonte indisponível",
  nao_configurado: "Não configurado",
};

/** Estado de uma leitura quando não há o que mostrar - nunca esconde a
 * diferença entre "a fonte falhou", "não há registros" e "integração
 * ainda não configurada". Devolve null quando o estado é "ok". */
export function EstadoDados({ r, vazio }: { r: Pick<Resultado<unknown>, "estado" | "mensagem" | "fonte">; vazio?: string }) {
  if (r.estado === "ok") return null;
  const tom = r.estado === "erro" ? "border-baixa/50 text-baixa" : r.estado === "nao_configurado" ? "border-ambar/50 text-ambar" : "border-filete text-suave";
  return (
    <div className={`border-l-2 ${tom} bg-painel-alto px-3 py-2 text-[12px]`}>
      <span className="mr-2 font-mono text-[10px] uppercase tracking-wider">{ROTULO[r.estado]}</span>
      <span className="text-suave">{r.estado === "vazio" ? vazio || r.mensagem || "Nenhum registro." : r.mensagem}</span>
      <span className="ml-2 text-[10px] text-apagado">({r.fonte})</span>
    </div>
  );
}

/** Aviso parcial (ex.: alguns feeds falharam) junto de dados válidos. */
export function AvisoParcial({ mensagem }: { mensagem?: string }) {
  if (!mensagem) return null;
  return <p className="mb-2 text-[11px] text-ambar">{mensagem}</p>;
}
