"use client";

import { useEffect, useState } from "react";

import { num } from "@/lib/formatos";
import { SIGLAS } from "@/lib/siglas";
import { usePolling } from "@/lib/usePolling";
import type { LinhaIndicador } from "@/lib/server/dominio/mercado";
import { Variacao } from "./Variacao";

const INTERVALO_MS = 60_000;

/** Segunda-a-sexta, 10h-17h (Brasília) - mesma regra de app.py:
 * _pregao_esta_aberto (B3). Só pra rótulo informativo no cabeçalho, não
 * trava nenhuma leitura de dado - fora desse horário os preços mostrados
 * continuam sendo o último fechamento real, nunca um valor inventado. */
function pregaoAbertoAgora(): boolean {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date());
  const mapa = Object.fromEntries(partes.map((p) => [p.type, p.value]));
  if (["Sat", "Sun"].includes(mapa.weekday)) return false;
  const hm = Number(mapa.hour) * 60 + Number(mapa.minute);
  return hm >= 10 * 60 && hm <= 17 * 60;
}

function StatusPregao() {
  // calculado só no cliente (useEffect) pra nunca divergir do fuso do
  // servidor na 1a pintura (hydration mismatch) - mesmo motivo de
  // qualquer relógio em Client Component
  const [aberto, setAberto] = useState<boolean | null>(null);
  useEffect(() => {
    const atualizar = () => setAberto(pregaoAbertoAgora());
    atualizar();
    const id = setInterval(atualizar, 30_000);
    return () => clearInterval(id);
  }, []);
  if (aberto === null) return null;
  return (
    <span className={`ml-auto flex shrink-0 items-center gap-1 border-l border-filete px-2.5 font-mono text-[10px] ${aberto ? "text-alta" : "text-apagado"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${aberto ? "bg-alta" : "bg-apagado"}`} />
      {aberto ? "PREGÃO ABERTO" : "PREGÃO FECHADO"}
    </span>
  );
}

/** Faixa de cotações fixa no topo (mesma leitura/regra do painel de
 * Mercado), atualizada sozinha em segundo plano via usePolling - sem
 * precisar navegar nem apertar F5. O servidor já cacheia a leitura real
 * (lib/server/yahoo.ts), então bater aqui a cada 60s só pega o cache
 * quase sempre, sem sobrecarregar a fonte. */
export function FitaCotacoes({ inicial }: { inicial: LinhaIndicador[] }) {
  const { dado } = usePolling<{ linhas: LinhaIndicador[] }>({ linhas: inicial }, "/api/mercado/fita", INTERVALO_MS);
  const linhas = dado.linhas?.length ? dado.linhas : inicial;

  return (
    <div className="sticky top-12 z-10 flex h-8 items-center overflow-x-auto border-b border-filete bg-base text-[11px] [scrollbar-width:none]">
      {linhas.map((l) => (
        <a
          key={l.simbolo}
          href={`/ativo/${encodeURIComponent(l.simbolo)}`}
          title={l.nome}
          className="flex shrink-0 items-baseline gap-1.5 border-r border-filete px-2.5 py-1 hover:bg-painel-alto"
        >
          <span className="font-mono font-semibold text-ambar">{SIGLAS[l.simbolo] || l.simbolo}</span>
          <span className="font-mono text-texto">{l.r.dados ? num(l.r.dados.preco, l.casas) : "—"}</span>
          <Variacao v={l.r.dados?.variacaoPct} />
        </a>
      ))}
      <StatusPregao />
    </div>
  );
}
