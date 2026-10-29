"use client";

import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/formatos";
import { SIGLAS } from "@/lib/siglas";
import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { Variacao } from "./Variacao";

const INTERVALO_MS = 60_000;

/** Faixa de cotações fixa no topo (mesma leitura/regra do painel de
 * Mercado), atualizada sozinha em segundo plano - sem precisar navegar
 * nem apertar F5. Client Component por causa do polling: o servidor já
 * cacheia a leitura real (lib/server/yahoo.ts), então bater aqui a cada
 * 60s só pega o cache quase sempre, sem sobrecarregar a fonte. Pausa
 * quando a aba não está visível (evita polling inútil em segundo plano)
 * e nunca troca um valor já exibido por "—" durante um refresh que
 * falhou - mantém o último dado bom até uma leitura nova funcionar. */
export function FitaCotacoes({ inicial }: { inicial: LinhaIndicador[] }) {
  const [linhas, setLinhas] = useState(inicial);
  const emVoo = useRef(false);

  useEffect(() => {
    async function atualizar() {
      if (emVoo.current || document.hidden) return;
      emVoo.current = true;
      try {
        const r = await fetch("/api/mercado/fita", { cache: "no-store" });
        if (r.ok) {
          const { linhas: novas } = (await r.json()) as { linhas: LinhaIndicador[] };
          if (Array.isArray(novas) && novas.length) setLinhas(novas);
        }
      } catch {
        // mantém o último dado bom - próximo tick tenta de novo
      } finally {
        emVoo.current = false;
      }
    }
    const id = setInterval(atualizar, INTERVALO_MS);
    document.addEventListener("visibilitychange", atualizar);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", atualizar);
    };
  }, []);

  return (
    <div className="sticky top-12 z-10 flex overflow-x-auto border-b border-filete bg-base text-[11px] [scrollbar-width:none]">
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
