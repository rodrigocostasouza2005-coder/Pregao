import type { ReactNode } from "react";

type PainelProps = {
  titulo: string;
  sigla?: string;
  acao?: ReactNode;
  rodape?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Bloco padrão do terminal: cabeçalho compacto em caixa alta, conteúdo
 * denso e um rodapé opcional com a fonte/horário do dado. */
export function Painel({ titulo, sigla, acao, rodape, children, className = "" }: PainelProps) {
  return (
    <section className={`flex min-w-0 flex-col border border-filete bg-painel ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-filete px-3 py-2">
        <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-suave">
          {sigla ? <span className="font-mono text-ambar">{sigla}</span> : null}
          {titulo}
        </h2>
        {acao}
      </header>
      <div className="min-w-0 flex-1 p-3">{children}</div>
      {rodape ? <footer className="border-t border-filete px-3 py-1.5 text-[10px] text-apagado">{rodape}</footer> : null}
    </section>
  );
}
