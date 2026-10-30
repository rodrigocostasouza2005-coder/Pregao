"use client";

import { num } from "@/lib/formatos";
import { usePolling } from "@/lib/usePolling";
import type { ItemFita } from "@/lib/server/dominio/mercado";
import { NOMES } from "@/lib/siglas";
import { Variacao } from "./Variacao";

const INTERVALO_MS = 60_000;

/** Tiles de número (rótulo + valor + variação) pros indicadores
 * principais - Ibovespa, dólar, DI e, na aba Mercado, Petróleo Brent.
 * Deliberadamente NÃO é um mini-gráfico: o brief pede "não transforme
 * cada indicador em um mini-gráfico" e "não quero seis mini-gráficos" -
 * o lugar do gráfico é só o GraficoPrincipal, grande, abaixo. */
export function IndicadoresCompactos({ inicial, comBrent }: { inicial: ItemFita[]; comBrent?: boolean }) {
  const url = `/api/mercado/indicadores-compactos${comBrent ? "?brent=1" : ""}`;
  const simbolos = inicial.map((l) => l.simbolo);
  const { dado } = usePolling<{ linhas: ItemFita[] }>({ linhas: inicial }, url, INTERVALO_MS);
  const porSimbolo = new Map(dado.linhas.map((l) => [l.simbolo, l]));
  const linhas = simbolos.map((s) => porSimbolo.get(s)).filter((l): l is ItemFita => !!l);
  const efetivas = linhas.length === simbolos.length ? linhas : inicial;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
      {efetivas.map((item) => (
        <div key={item.simbolo} className="border border-t-2 border-filete border-t-ambar bg-painel px-3 py-2">
          <div className="truncate text-[10px] uppercase tracking-wider text-apagado">{NOMES[item.simbolo] || item.nome}</div>
          <div className="mt-1 font-mono text-[18px] font-semibold leading-none">
            {item.r.dados ? num(item.r.dados.preco, item.casas) : "—"}
            {item.unidade ? <span className="ml-1 text-[11px] text-apagado">{item.unidade}</span> : null}
          </div>
          <div className="mt-1 text-[11px]">
            <Variacao v={item.r.dados?.variacaoPct} />
          </div>
        </div>
      ))}
    </div>
  );
}
