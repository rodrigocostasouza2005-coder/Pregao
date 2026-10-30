"use client";

import { useState } from "react";

import { num } from "@/lib/formatos";
import { usePolling } from "@/lib/usePolling";
import type { CotacaoTicker } from "@/lib/server/dominio/mercado";
import { useAtivoSelecionadoOpcional } from "./SelecaoAtivo";
import { Variacao } from "./Variacao";

const INTERVALO_MS = 60_000;
type Ordem = "ticker" | "variacao";

/** Watchlist persistente (user_prefs, mesma tabela/coluna do Python) com
 * preço e variação ao vivo. Clicar num ticker seleciona o ativo no
 * SelecaoAtivoProvider da página (troca o GraficoPrincipal) quando
 * houver um; sem Provider, navega pra página do ativo. */
export function PainelWatchlist({ inicial }: { inicial: CotacaoTicker[] }) {
  const { dado } = usePolling<{ linhas: CotacaoTicker[] }>({ linhas: inicial }, "/api/mercado/watchlist", INTERVALO_MS);
  const [ordem, setOrdem] = useState<Ordem>("ticker");
  const ctx = useAtivoSelecionadoOpcional();
  const linhas = dado.linhas ?? inicial;

  if (!linhas.length) {
    return <p className="text-[12px] text-apagado">Sua watchlist está vazia · adicione ativos na página de cada ativo (★ adicionar).</p>;
  }

  const ordenadas = [...linhas].sort((a, b) =>
    ordem === "variacao" ? (b.cotacao.variacaoPct ?? -Infinity) - (a.cotacao.variacaoPct ?? -Infinity) : a.ticker.localeCompare(b.ticker),
  );

  return (
    <div>
      <div className="mb-1.5 flex justify-end gap-1 text-[10px] text-apagado">
        <span className="self-center">Ordenar:</span>
        {(["ticker", "variacao"] as Ordem[]).map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => setOrdem(o)}
            className={`rounded-sm border px-1.5 py-0.5 ${ordem === o ? "border-ambar text-ambar" : "border-filete text-suave"}`}
          >
            {o === "ticker" ? "Ticker" : "Variação"}
          </button>
        ))}
      </div>
      <ul className="divide-y divide-filete/60">
        {ordenadas.map((i) => (
          <li key={i.ticker} className="flex items-center gap-2 py-1.5 text-[12px]">
            {ctx ? (
              <button type="button" onClick={() => ctx.selecionar(i.ticker)} className="font-mono text-texto hover:text-ambar">
                {i.ticker}
              </button>
            ) : (
              <a href={`/ativo/${i.ticker}`} className="font-mono text-texto hover:text-ambar">
                {i.ticker}
              </a>
            )}
            <span className="ml-auto font-mono">{num(i.cotacao.preco)}</span>
            <Variacao v={i.cotacao.variacaoPct} />
          </li>
        ))}
      </ul>
    </div>
  );
}
