import { redirect } from "next/navigation";

import { BotaoLogin } from "@/components/BotaoLogin";
import { usuarioAtual } from "@/lib/server/auth";
import { loginConfigurado } from "@/lib/server/env";

export const dynamic = "force-dynamic";

export default async function Login() {
  if (await usuarioAtual()) redirect("/");
  const configurado = loginConfigurado();
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm border border-filete bg-painel p-6">
        <div className="text-[22px] font-bold tracking-[0.32em]">PREGÃO</div>
        <p className="mt-1 text-[12px] text-apagado">Terminal de inteligência de mercado</p>
        <div className="my-5 h-px bg-filete" />
        {configurado ? (
          <BotaoLogin />
        ) : (
          <p className="border-l-2 border-ambar bg-ambar-fundo/60 px-3 py-2 text-[12px] text-suave">
            O login ainda não está configurado neste ambiente. O acesso fica bloqueado até as variáveis
            GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e NEXTAUTH_SECRET serem cadastradas na Vercel.
          </p>
        )}
      </div>
    </div>
  );
}
