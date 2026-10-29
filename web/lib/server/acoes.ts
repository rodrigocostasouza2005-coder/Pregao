"use server";

import { revalidatePath } from "next/cache";

import { usuarioAtual } from "./auth";
import { alternarWatchlist } from "./dominio/userPrefs";

/** Ação de servidor do botão de watchlist (BotaoWatchlist.tsx) - funciona
 * com <form action={...}> puro, sem JS no cliente. Silenciosa se não
 * houver login (nunca deveria acontecer, o middleware já bloqueia tudo
 * sem sessão) ou se a escrita falhar (usuário só não vê a mudança -
 * nunca uma mensagem de erro técnica numa ação tão pequena). */
export async function acaoAlternarWatchlist(formData: FormData) {
  const usuario = await usuarioAtual();
  if (!usuario?.sub) return;
  const ticker = String(formData.get("ticker") || "").toUpperCase();
  if (!ticker) return;
  await alternarWatchlist(usuario.sub, usuario.email, ticker);
  revalidatePath(`/ativo/${ticker}`);
  revalidatePath("/empresas");
  revalidatePath("/");
}
