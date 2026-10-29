/** Área estruturada, ainda sem fonte conectada: diz o que vai aparecer ali
 * e de onde virá o dado - nunca conteúdo fictício com cara de real. */
export function AreaPendente({ itens, origem }: { itens: string[]; origem: string }) {
  return (
    <div className="flex h-full flex-col gap-3">
      <ul className="space-y-1.5">
        {itens.map((item) => (
          <li key={item} className="flex items-center gap-2 text-[13px] text-suave">
            <span className="h-1 w-1 shrink-0 bg-ambar" />
            {item}
          </li>
        ))}
      </ul>
      <p className="mt-auto border-t border-filete pt-2 font-mono text-[10px] uppercase tracking-wider text-apagado">
        Fonte a conectar: {origem}
      </p>
    </div>
  );
}
