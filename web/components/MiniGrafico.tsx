import { num } from "@/lib/formatos";
import { referenciaCotacao } from "@/lib/referencia";
import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { Grafico } from "./Grafico";
import { Variacao } from "./Variacao";

/** Quadro compacto de um indicador: cotação, variação (regra do Pregão)
 * e o intradiário da última sessão contra o fechamento anterior. */
export function MiniGrafico({ linha, altura = 92 }: { linha: LinhaIndicador; altura?: number }) {
  const c = linha.r.dados;
  const s = linha.s?.dados;
  return (
    <div className="min-w-0 border border-filete bg-painel px-2.5 pb-1.5 pt-2">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="truncate text-[11px] font-semibold uppercase tracking-wider text-suave">{linha.nome}</span>
        <Variacao v={c?.variacaoPct} />
      </div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="font-mono text-[15px] text-texto">{c ? num(c.preco, linha.casas) : "—"}</span>
        <span className="font-mono text-[9.5px] text-apagado">{referenciaCotacao(c)}</span>
      </div>
      {s ? (
        <Grafico pontos={s.pontos} referencia={c?.fechamentoAnterior ?? null} eixoX="hora" fuso={s.fuso} casas={linha.casas} altura={altura} titulo={linha.nome} rotulosX={3} />
      ) : (
        <p className="flex items-center text-[11px] text-apagado" style={{ height: altura + 16 }}>
          {linha.s?.mensagem || "Gráfico indisponível na fonte."}
        </p>
      )}
    </div>
  );
}
