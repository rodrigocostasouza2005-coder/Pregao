import type { ReactNode } from "react";

type PainelProps = {
  titulo: string;
  sigla?: string;
  acao?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Bloco padrão do terminal: cabeçalho compacto em caixa alta, conteúdo denso. */
export function Painel({ titulo, sigla, acao, children, className = "" }: PainelProps) {
  return (
    <section className={`flex min-w-0 flex-col border border-filete bg-painel ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-filete px-3 py-2">
        <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-suave">
          {sigla ? <span className="font-mono text-ambar">{sigla}</span> : null}
          {titulo}
        </h2>
        {acao}
      </header>
      <div className="flex-1 p-3">{children}</div>
    </section>
  );
}
