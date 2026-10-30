import "server-only";

/** Variáveis de ambiente do servidor. Nenhuma delas pode ter prefixo
 * NEXT_PUBLIC_: são lidas só no servidor e nunca vão para o navegador. */
export const env = {
  supabaseUrl: (process.env.SUPABASE_URL || "").trim().replace(/\/+$/, ""),
  supabaseChave: (process.env.SUPABASE_SECRET_KEY || "").trim(),
  googleId: (process.env.GOOGLE_CLIENT_ID || "").trim(),
  googleSegredo: (process.env.GOOGLE_CLIENT_SECRET || "").trim(),
  authSegredo: (process.env.NEXTAUTH_SECRET || "").trim(),
  emailsAdmin: (process.env.ADMIN_EMAILS || "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean),
};

export const supabaseConfigurado = () => Boolean(env.supabaseUrl && env.supabaseChave);
export const loginConfigurado = () => Boolean(env.googleId && env.googleSegredo && env.authSegredo);
