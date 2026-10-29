import { num } from "@/lib/formatos";
import { INDICADORES, lerIndicadores } from "@/lib/server/dominio/mercado";
import { Variacao } from "./Variacao";

const SIGLA: Record<string, string> = {
  "^BVSP": "IBOV", "USDBRL=X": "USDBRL", "EURBRL=X": "EURBRL", "^GSPC": "SPX", "^IXIC": "CCMP", "^DJI": "INDU",
  "ES=F": "ES1", "^TNX": "UST10", "DX-Y.NYB": "DXY", "BZ=F": "CO1", "CL=F": "CL1", "GC=F": "GC1", "BTC-USD": "BTC",
};

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
          <span className="font-mono font-semibold text-ambar">{SIGLA[l.simbolo] || l.simbolo}</span>
          <span className="font-mono text-texto">{l.r.dados ? num(l.r.dados.preco, l.casas) : "—"}</span>
          <Variacao v={l.r.dados?.variacaoPct} />
        </a>
      ))}
    </div>
  );
}
