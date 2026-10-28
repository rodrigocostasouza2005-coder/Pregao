"use client";

import { useState, useTransition } from "react";
import { formatarNumero, formatarPct } from "@/lib/format";
import type { PontoHistorico } from "@/lib/yahoo";

const PERIODOS = ["1D", "1S", "1M", "3M", "6M", "1A", "5A"];

function Sparkline({ pontos }: { pontos: PontoHistorico[] }) {
  if (pontos.length < 2) {
    return <div className="text-text-faint text-[0.78rem] py-16 text-center">Sem histórico disponível.</div>;
  }
  const w = 980;
  const h = 230;
  const closes = pontos.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const pathPoints = pontos.map((p, i) => {
    const x = (i / (pontos.length - 1)) * w;
    const y = h - ((p.close - min) / span) * (h - 20) - 10;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const linha = pathPoints.join(" ");
  const area = `M0,${h} L${pathPoints.join(" L")} L${w},${h} Z`;
  const ultimo = pathPoints[pathPoints.length - 1].split(",");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={220} preserveAspectRatio="none">
      <defs>
        <linearGradient id="fillGrafico" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffa028" stopOpacity={0.32} />
          <stop offset="100%" stopColor="#ffa028" stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#fillGrafico)" />
      <polyline fill="none" stroke="#ffa028" strokeWidth={1.8} points={linha} />
      <circle cx={ultimo[0]} cy={ultimo[1]} r={3.2} fill="#ffa028" />
    </svg>
  );
}

export function GraficoIbovespa({ pontosIniciais }: { pontosIniciais: PontoHistorico[] }) {
  const [periodo, setPeriodo] = useState("6M");
  const [pontos, setPontos] = useState(pontosIniciais);
  const [pending, startTransition] = useTransition();

  function selecionar(p: string) {
    setPeriodo(p);
    startTransition(async () => {
      const resp = await fetch(`/api/mercado/historico?periodo=${p}`, { cache: "no-store" });
      if (resp.ok) {
        const json = await resp.json();
        setPontos(json.pontos ?? []);
      }
    });
  }

  const inicio = pontos[0]?.close;
  const fim = pontos[pontos.length - 1]?.close;
  const maxima = pontos.length ? Math.max(...pontos.map((p) => p.close)) : null;
  const minima = pontos.length ? Math.min(...pontos.map((p) => p.close)) : null;
  const variacaoPeriodo = inicio && fim ? ((fim - inicio) / inicio) * 100 : null;

  return (
    <div className="border border-border bg-bg">
      <div className="flex items-baseline justify-between px-3 py-2 border-b border-border">
        <span className="text-[0.68rem] tracking-wide font-bold text-text">IBOVESPA</span>
        <div className="flex gap-1">
          {PERIODOS.map((p) => (
            <button
              key={p}
              onClick={() => selecionar(p)}
              className={`text-[0.6rem] px-1.5 py-0.5 border rounded-[2px] ${
                p === periodo
                  ? "bg-accent text-bg border-accent font-bold"
                  : "border-border text-text-faint"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className={`px-3 py-2.5 ${pending ? "opacity-60" : ""}`}>
        <Sparkline pontos={pontos} />
        <div className="flex flex-wrap gap-5 mt-2 pt-2 border-t border-border">
          <div>
            <div className="text-[0.6rem] text-text-faint">INÍCIO DO PERÍODO</div>
            <div className="text-[0.76rem] font-bold mt-0.5">{inicio != null ? formatarNumero(inicio, 0) : "—"}</div>
          </div>
          <div>
            <div className="text-[0.6rem] text-text-faint">MÁXIMA</div>
            <div className="text-[0.76rem] font-bold mt-0.5">{maxima != null ? formatarNumero(maxima, 0) : "—"}</div>
          </div>
          <div>
            <div className="text-[0.6rem] text-text-faint">MÍNIMA</div>
            <div className="text-[0.76rem] font-bold mt-0.5">{minima != null ? formatarNumero(minima, 0) : "—"}</div>
          </div>
          {variacaoPeriodo != null && (
            <div>
              <div className="text-[0.6rem] text-text-faint">VARIAÇÃO NO PERÍODO</div>
              <div className={`text-[0.76rem] font-bold mt-0.5 ${variacaoPeriodo >= 0 ? "text-up" : "text-down"}`}>
                {formatarPct(variacaoPeriodo)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
