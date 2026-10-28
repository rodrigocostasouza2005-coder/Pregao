export function Painel({
  titulo,
  sub,
  children,
  className = "",
}: {
  titulo: string;
  sub?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-border bg-bg ${className}`}>
      <div className="flex items-baseline justify-between px-3 py-2 border-b border-border">
        <span className="text-[0.68rem] tracking-wide font-bold text-text">{titulo}</span>
        {sub && <span className="text-[0.6rem] text-text-faint">{sub}</span>}
      </div>
      <div className="px-3 py-2.5">{children}</div>
    </div>
  );
}

export function SemDado({ children }: { children: React.ReactNode }) {
  return <div className="text-text-faint text-[0.76rem]">{children}</div>;
}

export function Pendente({ motivo }: { motivo: string }) {
  return (
    <div className="text-text-faint text-[0.74rem] italic">
      Não disponível nesta versão — {motivo}
    </div>
  );
}

export function Badge({ ticker }: { ticker: string }) {
  const iniciais = (ticker.replace(/[^A-Za-z]/g, "").slice(0, 2) || ticker.slice(0, 2)).toUpperCase();
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 min-w-5 rounded-[3px] bg-accent-dim text-accent text-[0.56rem] font-bold mr-1.5 align-middle">
      {iniciais}
    </span>
  );
}
