import "server-only";

import { lerTabela, upsertLinha } from "../supabase";

type LinhaPrefs = { sub: string; email: string; preferencias: Record<string, unknown> | null };

/** Mesma tabela/coluna do app Python (data/user_prefs.py) - nenhum
 * schema novo. Sem linha ainda (usuário nunca salvou nada): watchlist
 * vazia (nunca a lista padrão do Python, que é só o valor inicial do
 * ONBOARDING no Streamlit - aqui não temos como saber se o usuário já
 * decidiu uma watchlist vazia de propósito). */
export async function lerWatchlist(sub: string): Promise<string[]> {
  const r = await lerTabela<LinhaPrefs>("user_prefs", { select: "preferencias", filtros: { sub: `eq.${sub}` }, limite: 1, revalidar: 60 });
  const lista = r.dados[0]?.preferencias?.watchlist;
  return Array.isArray(lista) ? lista.filter((t): t is string => typeof t === "string") : [];
}

/** Adiciona/remove 1 ticker (upsert por sub) - lê a linha atual primeiro
 * pra preservar as outras preferências (ver upsertLinha: upsert aqui é
 * do objeto preferencias inteiro, igual ao Python). Nunca lança
 * exceção; quem chama (ação de servidor) decide o que fazer com false. */
export async function alternarWatchlist(sub: string, email: string, ticker: string): Promise<boolean> {
  const r = await lerTabela<LinhaPrefs>("user_prefs", { select: "preferencias", filtros: { sub: `eq.${sub}` }, limite: 1, revalidar: 0 });
  const prefsAtuais = r.dados[0]?.preferencias || {};
  const atual = Array.isArray(prefsAtuais.watchlist) ? (prefsAtuais.watchlist as string[]) : [];
  const watchlist = atual.includes(ticker) ? atual.filter((t) => t !== ticker) : [...atual, ticker];
  return upsertLinha("user_prefs", "sub", { sub, email: email.toLowerCase(), preferencias: { ...prefsAtuais, watchlist } });
}
