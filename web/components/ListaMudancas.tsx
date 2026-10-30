import { dataHora } from "@/lib/formatos";
import type { Mudanca } from "@/lib/server/dominio/inteligencia";
import { LinkFonte } from "./LinkFonte";
import { Selo } from "./Selo";

export function ListaMudancas({ itens }: { itens: Mudanca[] }) {
  return (
    <ul className="divide-y divide-filete/60">
      {itens.map((m, i) => (
        <li key={i} className="grid grid-cols-[6rem_1fr] gap-x-3 py-1.5 text-[12.5px]">
          <span className="font-mono text-[11px] text-apagado">{dataHora(m.em)}</span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Selo tipo={m.natureza} />
              <span className="font-mono text-[10px] uppercase text-apagado">{m.tipo}</span>
              <LinkFonte href={m.link}><span className="text-texto">{m.titulo}</span></LinkFonte>
            </div>
            <div className="mt-0.5 text-[11px] text-apagado">
              {m.detalhe ? <span className="mr-2 text-suave">{m.detalhe}</span> : null}
              Fonte: {m.fonte}
              {m.tickers.map((t) => <a key={t} href={`/ativo/${t}`} className="ml-2 font-mono text-suave hover:text-ambar">{t}</a>)}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
