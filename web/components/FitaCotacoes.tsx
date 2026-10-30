"use client";

import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/formatos";
import { SIGLAS } from "@/lib/siglas";
import { usePolling } from "@/lib/usePolling";
import type { ItemFita } from "@/lib/server/dominio/mercado";
import { useAtivoSelecionadoOpcional } from "./SelecaoAtivo";
import { Variacao } from "./Variacao";

const INTERVALO_MS = 60_000;
const DURACAO_POR_ITEM_S = 2.6;

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
    <span className={`flex h-full shrink-0 items-center gap-1 border-l border-filete bg-base px-3 font-mono text-[10px] ${aberto ? "text-alta" : "text-apagado"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${aberto ? "bg-alta" : "bg-apagado"}`} />
      {aberto ? "PREGÃO ABERTO" : "PREGÃO FECHADO"}
    </span>
  );
}

function ItemFitaView({ item, piscar }: { item: ItemFita; piscar: boolean }) {
  const ctx = useAtivoSelecionadoOpcional();
  const rotulo = SIGLAS[item.simbolo] || item.simbolo;
  const preco = item.r.dados ? num(item.r.dados.preco, item.casas) : "—";
  const conteudo = (
    <>
      <span className="font-mono font-semibold text-ambar">{rotulo}</span>
      <span className="font-mono text-texto">{preco}{item.unidade ? ` ${item.unidade}` : ""}</span>
      <Variacao v={item.r.dados?.variacaoPct} />
    </>
  );
  const classe = `flex shrink-0 items-baseline gap-1.5 border-r border-filete px-3 py-1.5 transition-colors duration-700 hover:bg-painel-alto ${piscar ? "bg-ambar-fundo" : ""}`;
  if (ctx) {
    return (
      <button type="button" title={item.nome} onClick={() => ctx.selecionar(item.simbolo)} className={classe}>
        {conteudo}
      </button>
    );
  }
  return (
    <a href={`/ativo/${encodeURIComponent(item.simbolo)}`} title={item.nome} className={classe}>
      {conteudo}
    </a>
  );
}

/** Hook: compara o preço de cada item contra a leitura anterior e devolve
 * o conjunto de símbolos cujo preço mudou nesta leitura - usado só pro
 * destaque visual momentâneo, nunca pra decidir o que renderizar. */
function useDestaques(linhas: ItemFita[]) {
  const anteriores = useRef<Map<string, number>>(new Map());
  const [piscando, setPiscando] = useState<Set<string>>(new Set());
  useEffect(() => {
    const mudou = new Set<string>();
    for (const l of linhas) {
      const preco = l.r.dados?.preco;
      if (typeof preco !== "number") continue;
      const anterior = anteriores.current.get(l.simbolo);
      if (anterior !== undefined && anterior !== preco) mudou.add(l.simbolo);
      anteriores.current.set(l.simbolo, preco);
    }
    if (mudou.size) {
      setPiscando(mudou);
      const id = setTimeout(() => setPiscando(new Set()), 900);
      return () => clearTimeout(id);
    }
  }, [linhas]);
  return piscando;
}

/** Faixa de cotações fixa no topo: watchlist viva (ações da B3 + IBOV +
 * dólar + DI, nunca índices americanos - ver lib/server/dominio/
 * mercado.ts:lerFita), em movimento horizontal contínuo (duas cópias da
 * mesma lista lado a lado, deslocadas por CSS - ver globals.css
 * @keyframes fita-rolagem), atualizada sozinha em segundo plano via
 * usePolling - sem precisar navegar nem apertar F5. O servidor já
 * cacheia a leitura real (lib/server/yahoo.ts e lib/server/bcb.ts),
 * então bater aqui a cada 60s só pega o cache quase sempre. */
export function FitaCotacoes({ inicial }: { inicial: ItemFita[] }) {
  const { dado } = usePolling<{ linhas: ItemFita[] }>({ linhas: inicial }, "/api/mercado/fita", INTERVALO_MS);
  const linhas = dado.linhas?.length ? dado.linhas : inicial;
  const piscando = useDestaques(linhas);
  const [pausado, setPausado] = useState(false);
  const duracao = Math.max(linhas.length * DURACAO_POR_ITEM_S, 18);

  return (
    <div
      className="sticky top-12 z-10 h-11 overflow-hidden border-b border-filete bg-base text-[11.5px]"
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
    >
      <div
        className="flex h-full items-stretch motion-reduce:!animate-none"
        style={{ animation: `fita-rolagem ${duracao}s linear infinite`, animationPlayState: pausado ? "paused" : "running" }}
      >
        {[0, 1].map((copia) => (
          <div key={copia} className="flex h-full shrink-0 items-stretch" aria-hidden={copia === 1}>
            {linhas.map((l, i) => (
              <ItemFitaView key={`${copia}-${l.simbolo}-${i}`} item={l} piscar={copia === 0 && piscando.has(l.simbolo)} />
            ))}
          </div>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-stretch">
        <div className="pointer-events-auto flex items-stretch">
          <StatusPregao />
        </div>
      </div>
    </div>
  );
}
