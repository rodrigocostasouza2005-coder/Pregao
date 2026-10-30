import { lerFita } from "@/lib/server/dominio/mercado";
import { usuarioAtual } from "@/lib/server/auth";
import { lerWatchlist } from "@/lib/server/dominio/userPrefs";

/** Dados da fita de cotações pro polling do cliente (FitaCotacoes.tsx) -
 * mesma leitura/cache do Server Component original (lerFita já respeita
 * o revalidate de lib/server/yahoo.ts e lib/server/bcb.ts); só serializa
 * pra JSON. Inclui a watchlist de quem está logado, igual ao layout. */
export async function GET() {
  const usuario = await usuarioAtual();
  const watchlist = usuario?.sub ? await lerWatchlist(usuario.sub) : [];
  const linhas = await lerFita(watchlist);
  return Response.json({ linhas });
}
