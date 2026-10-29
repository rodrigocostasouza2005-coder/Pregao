"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAVEGACAO } from "@/lib/navegacao";

/** Navegação lateral compacta; vira faixa rolável no celular. */
export function BarraLateral({ urlStreamlit }: { urlStreamlit?: string }) {
  const caminho = usePathname();
  return (
    <nav
      aria-label="Áreas do Pregão"
      className="flex shrink-0 gap-1 overflow-x-auto border-b border-filete bg-painel p-2 md:sticky md:top-12 md:h-[calc(100vh-3rem)] md:w-48 md:flex-col md:overflow-y-auto md:border-r md:border-b-0"
    >
      {NAVEGACAO.map((item) => {
        const atual = item.rota === "/" ? caminho === "/" : caminho.startsWith(item.rota);
        return (
          <Link
            key={item.rota}
            href={item.rota}
            aria-current={atual ? "page" : undefined}
            title={item.descricao}
            className={`flex items-center gap-2 whitespace-nowrap rounded-sm px-2 py-1.5 text-[13px] transition-colors ${
              atual ? "bg-ambar-fundo text-texto shadow-[inset_2px_0_0_var(--color-ambar)]" : "text-suave hover:bg-painel-alto hover:text-texto"
            }`}
          >
            <span className={`w-7 font-mono text-[10px] ${atual ? "text-ambar" : "text-apagado"}`}>{item.sigla}</span>
            {item.rotulo}
          </Link>
        );
      })}
      <div className="hidden flex-1 md:block" />
      {urlStreamlit ? (
        <a href={urlStreamlit} className="hidden rounded-sm border border-filete px-2 py-1.5 text-[11px] text-suave hover:border-ambar hover:text-texto md:block">
          Pregão (Streamlit) ↗
        </a>
      ) : null}
    </nav>
  );
}
