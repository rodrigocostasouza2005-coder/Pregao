/** Esqueleto compartilhado pros loading.tsx de cada rota do terminal.
 * Next.js mostra isso via Suspense IMEDIATAMENTE ao navegar, antes do
 * fetch real da página (Promise.all de Supabase/Yahoo/BCB/RSS) resolver
 * - sem isso, a navegação ficava "congelada" até todo o Server Component
 * terminar, mesmo com os fetches já rápidos/cacheados. Puramente visual,
 * nunca mostra dado (fiel a "nunca inventar número"). */
export function CarregandoPagina({ paineis = 2 }: { paineis?: number }) {
  return (
    <div className="animate-pulse">
      <div className="mb-3 h-7 w-48 border-b border-filete bg-painel-alto/60 pb-2" />
      <div className="grid gap-3 xl:grid-cols-2">
        {Array.from({ length: paineis }, (_, i) => (
          <div key={i} className="border border-filete bg-painel">
            <div className="h-9 border-b border-filete bg-painel-alto/40" />
            <div className="space-y-2 p-3">
              {Array.from({ length: 5 }, (_, j) => (
                <div key={j} className="h-3 bg-painel-alto/40" style={{ width: `${70 - j * 8}%` }} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
