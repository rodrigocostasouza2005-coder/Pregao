import { BarraLateral } from "@/components/BarraLateral";
import { Cabecalho } from "@/components/Cabecalho";
import { usuarioAtual } from "@/lib/server/auth";

export const dynamic = "force-dynamic";

export default async function LayoutTerminal({ children }: { children: React.ReactNode }) {
  const usuario = await usuarioAtual();
  const urlStreamlit = process.env.NEXT_PUBLIC_STREAMLIT_URL || undefined;
  return (
    <div className="flex min-h-screen flex-col">
      <Cabecalho usuario={usuario} />
      <div className="flex flex-1 flex-col md:flex-row">
        <BarraLateral urlStreamlit={urlStreamlit} />
        <main className="min-w-0 flex-1 p-3 md:p-4">{children}</main>
      </div>
      <footer className="border-t border-filete px-4 py-2 text-[10.5px] text-apagado">
        Conteúdo informativo, não constitui recomendação de investimento. Cotações podem ter atraso conforme a fonte.
      </footer>
    </div>
  );
}
