import { acaoAlternarWatchlist } from "@/lib/server/acoes";

/** Alterna 1 ticker na watchlist do usuário logado - form Server Action
 * puro (sem JS no cliente), mesma tabela/coluna do app Python
 * (user_prefs.preferencias.watchlist). */
export function BotaoWatchlist({ ticker, naWatchlist }: { ticker: string; naWatchlist: boolean }) {
  return (
    <form action={acaoAlternarWatchlist}>
      <input type="hidden" name="ticker" value={ticker} />
      <button
        type="submit"
        title={naWatchlist ? "Remover da watchlist" : "Adicionar à watchlist"}
        className={`rounded-sm border px-1.5 py-0.5 font-mono text-[11px] ${naWatchlist ? "border-ambar text-ambar" : "border-filete text-apagado hover:border-ambar hover:text-ambar"}`}
      >
        {naWatchlist ? "★ na watchlist" : "☆ adicionar"}
      </button>
    </form>
  );
}
