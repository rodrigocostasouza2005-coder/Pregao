import { usuarioAtual } from "@/lib/server/auth";
import { lerCotacoesTickers } from "@/lib/server/dominio/mercado";
import { lerWatchlist } from "@/lib/server/dominio/userPrefs";

/** Watchlist do usuário logado com cotação + variação, pro polling do
 * cliente (PainelWatchlist.tsx) - lê a lista de novo a cada chamada (não
 * só os preços), então um ticker adicionado/removido em outra aba
 * aparece sozinho na próxima leitura, sem precisar recarregar a página. */
export async function GET() {
  const usuario = await usuarioAtual();
  const watchlist = usuario?.sub ? await lerWatchlist(usuario.sub) : [];
  const linhas = await lerCotacoesTickers(watchlist);
  return Response.json({ linhas });
}
