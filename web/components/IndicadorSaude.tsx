"use client";

import { useEffect, useRef, useState } from "react";

type Resumo = { nivel: "ok" | "atencao" | "falha" | "indisponivel"; ok: number; falhas: number; atencao: number; total: number; ultimaColetaEm: string | null };

const INTERVALO_MS = 120_000;

const ROTULO: Record<Resumo["nivel"], string> = { ok: "Atualizado", atencao: "Dados atrasados", falha: "Fonte indisponível", indisponivel: "Sem conexão com o banco" };
const COR: Record<Resumo["nivel"], string> = { ok: "bg-alta", atencao: "bg-ambar", falha: "bg-baixa", indisponivel: "bg-apagado" };

function horaBR(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  } catch {
    return "—";
  }
}

/** Indicador discreto de saúde no cabeçalho - resume painelSaude() (ver
 * /api/saude/resumo) sem duplicar a classificação. "Carregando" só
 * aparece na primeira leitura; depois disso o último estado bom nunca é
 * substituído por "indisponível" só porque UM poll falhou (rede do
 * navegador, não dos coletores) - só atualiza quando uma leitura nova
 * de verdade chega. Nunca mostra um ponto verde genérico: a cor e o
 * texto vêm do estado real agregado dos coletores. */
export function IndicadorSaude() {
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const emVoo = useRef(false);

  useEffect(() => {
    async function atualizar() {
      if (emVoo.current || document.hidden) return;
      emVoo.current = true;
      setAtualizando(true);
      try {
        const r = await fetch("/api/saude/resumo", { cache: "no-store" });
        if (r.ok) setResumo(await r.json());
      } catch {
        // mantém o último estado bom - próximo tick tenta de novo
      } finally {
        emVoo.current = false;
        setAtualizando(false);
      }
    }
    atualizar();
    const id = setInterval(atualizar, INTERVALO_MS);
    document.addEventListener("visibilitychange", atualizar);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", atualizar);
    };
  }, []);

  if (!resumo) return <span className="hidden font-mono text-[10px] text-apagado sm:inline">verificando…</span>;
  return (
    <a
      href="/configuracoes"
      title={`${ROTULO[resumo.nivel]} · ${resumo.ok}/${resumo.total} coletores OK · última coleta às ${horaBR(resumo.ultimaColetaEm)}`}
      className="hidden items-center gap-1.5 font-mono text-[10px] text-apagado hover:text-suave sm:flex"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${COR[resumo.nivel]} ${atualizando ? "animate-pulse" : ""}`} />
      {ROTULO[resumo.nivel]} · {horaBR(resumo.ultimaColetaEm)}
    </a>
  );
}
