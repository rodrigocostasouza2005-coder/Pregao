import { num } from "@/lib/formatos";
import { INDICADORES, lerIndicadores, SIGLAS } from "@/lib/server/dominio/mercado";
import { Variacao } from "./Variacao";

/** Faixa de cotações do topo (mesma leitura e regra do painel de Mercado);
 * indicador sem cotação aparece como indisponível, nunca com número. */
export async function FitaCotacoes() {
  const linhas = await lerIndicadores(INDICADORES, false);
  return (
    <div className="flex overflow-x-auto border-b border-filete bg-base text-[11px] [scrollbar-width:none]">
      {linhas.map((l) => (
        <a
          key={l.simbolo}
          href={`/ativo/${encodeURIComponent(l.simbolo)}`}
          title={l.nome}
          className="flex shrink-0 items-baseline gap-1.5 border-r border-filete px-2.5 py-1 hover:bg-painel-alto"
        >
          <span className="font-mono font-semibold text-ambar">{SIGLAS[l.simbolo] || l.simbolo}</span>
          <span className="font-mono text-texto">{l.r.dados ? num(l.r.dados.preco, l.casas) : "—"}</span>
          <Variacao v={l.r.dados?.variacaoPct} />
        </a>
      ))}
    </div>
  );
}
