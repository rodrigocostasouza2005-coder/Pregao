import Link from "next/link";

import type { Usuario } from "@/lib/server/auth";
import { IndicadorSaude } from "./IndicadorSaude";

export function Cabecalho({ usuario }: { usuario: Usuario | null }) {
  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-filete bg-painel px-3 md:px-4">
      <Link href="/" className="text-[16px] font-bold tracking-[0.3em] text-texto">
        PREGÃO
      </Link>
      <form action="/busca" className="ml-2 flex max-w-md flex-1">
        <input
          name="q"
          type="search"
          placeholder="Buscar ticker, empresa, casa…"
          aria-label="Busca global"
          className="w-full rounded-sm border border-filete bg-base px-2.5 py-1 text-[12.5px] text-texto placeholder:text-apagado focus:border-ambar focus:outline-none"
        />
      </form>
      <div className="ml-auto flex items-center gap-3 text-[11px] text-apagado">
        <IndicadorSaude />
        {usuario ? (
          <>
            <span className="hidden max-w-40 truncate sm:inline" title={usuario.email}>{usuario.nome}</span>
            <Link href="/api/auth/signout" className="rounded-sm border border-filete px-2 py-1 text-suave hover:border-ambar hover:text-texto">
              Sair
            </Link>
          </>
        ) : (
          <span className="font-mono uppercase tracking-wider text-ambar">modo de validação</span>
        )}
      </div>
    </header>
  );
}
