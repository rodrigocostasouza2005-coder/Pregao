import { SeloDemonstrativo } from "./SeloDemonstrativo";

export function Cabecalho() {
  return (
    <header className="flex h-12 items-center justify-between gap-4 border-b border-filete bg-painel px-4">
      <div className="flex items-baseline gap-3">
        <span className="text-[17px] font-bold tracking-[0.32em] text-texto">PREGÃO</span>
        <span className="hidden h-4 w-px self-center bg-filete sm:block" />
        <span className="hidden text-[11px] uppercase tracking-[0.18em] text-apagado sm:block">
          Terminal de mercado
        </span>
      </div>
      <div className="flex items-center gap-3">
        <SeloDemonstrativo texto="Versão de migração" />
      </div>
    </header>
  );
}
