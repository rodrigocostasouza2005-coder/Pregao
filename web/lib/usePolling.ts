"use client";

import { useEffect, useRef, useState } from "react";

/** Hook de atualização "quase em tempo real" do terminal (Fase 9): busca
 * `url` a cada `intervaloMs`, pausa quando a aba não está visível, e
 * NUNCA troca um dado já exibido por vazio/erro quando um poll falha -
 * mantém o último dado bom até uma leitura nova funcionar. Mesma lógica
 * que FitaCotacoes/IndicadorSaude já usavam cada um por conta própria;
 * extraído aqui pra não triplicar o mesmo mecanismo nos componentes
 * novos desta fase (MiniGraficoGridAoVivo, TabelaIndicadoresAoVivo,
 * PainelMercadoAoVivo, GraficoIntradiarioAoVivo).
 *
 * O ritmo real dos dados continua limitado pelo cache do servidor
 * (`revalidate` em lib/server/yahoo.ts, hoje 300s pro intradiário) - this
 * hook só repete a busca do lado do cliente, nunca gera ponto novo
 * sozinho nem promete mais frequência do que a fonte realmente entrega
 * (ver PREGÃO.md Fase 9 item 3: "não simular movimentação de preços"). */
export function usePolling<T>(inicial: T, url: string, intervaloMs: number) {
  const [dado, setDado] = useState(inicial);
  const [atualizadoEm, setAtualizadoEm] = useState<number | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const emVoo = useRef(false);

  useEffect(() => {
    let vivo = true;
    async function atualizar() {
      if (emVoo.current || document.hidden) return;
      emVoo.current = true;
      setAtualizando(true);
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (r.ok && vivo) {
          setDado(await r.json());
          setAtualizadoEm(Date.now());
        }
      } catch {
        // mantém o último dado bom - próximo tick tenta de novo
      } finally {
        emVoo.current = false;
        if (vivo) setAtualizando(false);
      }
    }
    // 1a busca imediata (não espera o 1o intervalo inteiro) só quando não
    // há dado inicial de SSR pra mostrar enquanto isso (ver FitaCotacoes,
    // que passa `inicial` real e não precisa de uma 2a busca imediata
    // redundante) - achado real do refactor desta fase: sem isso,
    // componentes como IndicadorSaude (que começam com null) ficavam
    // mostrando "verificando…" pelo intervalo inteiro antes da 1a leitura.
    if (inicial === null || inicial === undefined) atualizar();
    const id = setInterval(atualizar, intervaloMs);
    document.addEventListener("visibilitychange", atualizar);
    return () => {
      vivo = false;
      clearInterval(id);
      document.removeEventListener("visibilitychange", atualizar);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- url/intervaloMs são constantes por instância do componente que chama o hook
  }, [url, intervaloMs]);

  return { dado, atualizando, atualizadoEm };
}
