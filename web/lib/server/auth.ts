import "server-only";

import type { NextAuthOptions } from "next-auth";
import { getServerSession } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

import { env, loginConfigurado } from "./env";

/** Login Google, o mesmo provedor do Streamlit (st.login). O `sub` do
 * Google vira o id do usuário - o mesmo usado em user_prefs/teses/posições. */
export const authOptions: NextAuthOptions = {
  secret: env.authSegredo || undefined,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: loginConfigurado()
    ? [GoogleProvider({ clientId: env.googleId, clientSecret: env.googleSegredo })]
    : [],
  callbacks: {
    async jwt({ token, profile }) {
      if (profile?.sub) token.sub = profile.sub;
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as { sub?: string }).sub = token.sub;
        session.user.email = (session.user.email || "").toLowerCase();
      }
      return session;
    },
  },
};

export type Usuario = { sub: string | null; email: string; nome: string; admin: boolean };

export async function usuarioAtual(): Promise<Usuario | null> {
  if (!loginConfigurado()) return null;
  const sessao = await getServerSession(authOptions);
  if (!sessao?.user?.email) return null;
  const email = sessao.user.email.toLowerCase();
  return {
    sub: (sessao.user as { sub?: string }).sub ?? null,
    email,
    nome: sessao.user.name || email,
    admin: env.emailsAdmin.includes(email),
  };
}
