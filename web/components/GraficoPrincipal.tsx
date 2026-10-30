"use client";

import { useEffect, useRef, useState } from "react";

import ibovespa from "@/contratos/ibovespa.json";
import { dataHora, num } from "@/lib/formatos";
import { EIXO_POR_PERIODO, PERIODOS_GRAFICO, type PeriodoGrafico } from "@/lib/grafico";
import { NOMES, SIGLAS } from "@/lib/siglas";
import type { Cotacao, Serie } from "@/lib/server/yahoo";
import type { Resultado } from "@/lib/tipos";
import { Grafico } from "./Grafico";
import { GraficoCandles } from "./GraficoCandles";
import { useAtivoSelecionado } from "./SelecaoAtivo";
import { Variacao } from "./Variacao";

const INTERVALO_VIVO_MS = 60_000;
const SETORES = (ibovespa as { setores: Record<string, string> }).setores;

type Resposta = { serie: Resultado<Serie | null>; cotacao: Resultado<Cotacao | null> };

function nomeDe(simbolo: string): string {
  if (NOMES[simbolo]) return NOMES[simbolo];
  const ticker = simbolo.replace(/\.SA$/, "");
  return SETORES[ticker] ? `${ticker} · ${SETORES[ticker]}` : "";
}

/** O ÚNICO gráfico principal da Visão Geral e do Mercado (brief: "um
 * gráfico grande e funcional", não seis mini-gráficos). Lê o ativo
 * selecionado do SelecaoAtivoProvider da página (clicar num ranking, na
 * watchlist ou na fita troca o gráfico sem navegar) e busca a série em
 * `/api/mercado/grafico` a cada troca de ativo/período/tipo - usa os
 * dados já lidos no servidor (`serieInicial`/`cotacaoInicial`) enquanto
 * o ativo/período não mudou, pra não duplicar a 1a leitura. */
export function GraficoPrincipal({
  simboloPadrao,
  nomePadrao,
  serieInicial,
  cotacaoInicial,
  periodoPadrao = "1D",
}: {
  simboloPadrao: string;
  nomePadrao?: string;
  serieInicial: Resultado<Serie | null>;
  cotacaoInicial: Resultado<Cotacao | null>;
  periodoPadrao?: PeriodoGrafico;
}) {
  const { simbolo } = useAtivoSelecionado();
  const [periodo, setPeriodo] = useState<PeriodoGrafico>(periodoPadrao);
  const [tipo, setTipo] = useState<"linha" | "candle">("linha");
  const [resposta, setResposta] = useState<Resposta>({ serie: serieInicial, cotacao: cotacaoInicial });
  const [carregando, setCarregando] = useState(false);
  const ultimaBusca = useRef<string>(`${simboloPadrao}|${periodoPadrao}`);

  useEffect(() => {
    const chave = `${simbolo}|${periodo}`;
    if (ultimaBusca.current === chave) return;
    let vivo = true;
    (async () => {
      setCarregando(true);
      try {
        const r = await fetch(`/api/mercado/grafico?simbolo=${encodeURIComponent(simbolo)}&periodo=${periodo}`, { cache: "no-store" });
        if (r.ok && vivo) setResposta(await r.json());
      } catch {
        // mantém o último dado bom - próxima troca tenta de novo
      } finally {
        if (vivo) setCarregando(false);
      }
    })();
    ultimaBusca.current = chave;
    return () => {
      vivo = false;
    };
  }, [simbolo, periodo]);

  // "ao vivo" só no 1D (mesma régua de GraficoIntradiarioAoVivo/usePolling: nunca gera ponto sozinho, só repete a busca)
  useEffect(() => {
    if (periodo !== "1D") return;
    const id = setInterval(async () => {
      if (document.hidden) return;
      try {
        const r = await fetch(`/api/mercado/grafico?simbolo=${encodeURIComponent(simbolo)}&periodo=1D`, { cache: "no-store" });
        if (r.ok) setResposta(await r.json());
      } catch {
        // mantém o último dado bom
      }
    }, INTERVALO_VIVO_MS);
    return () => clearInterval(id);
  }, [simbolo, periodo]);

  const serie = resposta.serie.dados;
  const cotacao = resposta.cotacao.dados;
  const rotulo = SIGLAS[simbolo] || simbolo.replace(/\.SA$/, "");
  const nome = simbolo === simboloPadrao && nomePadrao ? nomePadrao : nomeDe(simbolo);
  const eixoX = EIXO_POR_PERIODO[periodo];
  const candleDisponivel = (serie?.velas.length ?? 0) >= 2;
  const usarCandle = tipo === "candle" && candleDisponivel;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[16px] font-semibold text-ambar">{rotulo}</span>
            {nome ? <span className="text-[11px] text-apagado">{nome}</span> : null}
          </div>
          {cotacao ? (
            <div className="mt-0.5 flex items-baseline gap-2">
              <span className="font-mono text-[21px] leading-none">{num(cotacao.preco)}</span>
              <Variacao v={cotacao.variacaoPct} />
              {cotacao.negocioEm ? <span className="font-mono text-[10.5px] text-apagado">{dataHora(cotacao.negocioEm)}</span> : null}
            </div>
          ) : (
            <p className="mt-0.5 text-[12px] text-apagado">cotação indisponível</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-px font-mono text-[11px]">
            {(["linha", "candle"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTipo(t)}
                className={`px-2 py-0.5 ${tipo === t ? "bg-ambar text-base" : "bg-painel-alto text-suave hover:text-ambar"}`}
              >
                {t === "linha" ? "LINHA" : "CANDLE"}
              </button>
            ))}
          </div>
          <div className="flex gap-px font-mono text-[11px]">
            {PERIODOS_GRAFICO.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriodo(p)}
                className={`px-2 py-0.5 ${periodo === p ? "bg-ambar text-base" : "bg-painel-alto text-suave hover:text-ambar"}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>
      {resposta.serie.estado !== "ok" ? (
        <p className="text-[12px] text-apagado">{resposta.serie.mensagem || "Sem negócios no período."}</p>
      ) : usarCandle ? (
        <GraficoCandles
          velas={serie!.velas}
          volumes={serie!.volumes}
          referencia={serie!.fechamentoAnterior}
          rotuloReferencia="fech. ant."
          eixoX={eixoX}
          fuso={serie!.fuso}
          altura={320}
          titulo={`${rotulo} ${periodo}`}
        />
      ) : serie ? (
        <Grafico
          pontos={serie.pontos}
          volumes={serie.volumes}
          referencia={serie.fechamentoAnterior}
          rotuloReferencia="fech. ant."
          eixoX={eixoX}
          fuso={serie.fuso}
          altura={320}
          titulo={`${rotulo} ${periodo}`}
        />
      ) : null}
      {tipo === "candle" && !candleDisponivel && resposta.serie.estado === "ok" ? (
        <p className="mt-1 text-[10.5px] text-ambar">Candlestick indisponível para este ativo/período na fonte (sem OHLC completo nesta leitura) · exibindo linha.</p>
      ) : null}
      <p className="mt-1 text-[10px] text-apagado">
        Fonte: {resposta.serie.fonte} · {carregando ? "atualizando…" : periodo === "1D" ? "intradiário, atualiza sozinho" : "fechamentos do período"} · pontos sem negócio não são preenchidos
      </p>
    </div>
  );
}
