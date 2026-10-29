"use client";

import { signIn } from "next-auth/react";

export function BotaoLogin() {
  return (
    <button
      onClick={() => signIn("google", { callbackUrl: "/" })}
      className="w-full rounded-sm border border-ambar bg-ambar-fundo px-3 py-2 text-[13px] font-medium text-texto hover:bg-ambar hover:text-base"
    >
      Entrar com Google
    </button>
  );
}
