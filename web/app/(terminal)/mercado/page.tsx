import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { MiniGraficoGridAoVivo } from "@/components/MiniGraficoGridAoVivo";
import { Painel } from "@/components/Painel";
import { PainelMercadoAoVivo } from "@/components/PainelMercadoAoVivo";
import { TabelaIndicadoresAoVivo } from "@/components/TabelaIndicadoresAoVivo";
import { dataHora } from "@/lib/formatos";
import { INDICADORES, lerIndicadores, painelIbovespa } from "@/lib/server/dominio/mercado";
import { obterNoticias } from "@/lib/server/noticias";

export const metadata = { title: "Mercado · Pregão" };

export default async function Mercado() {
  const [indicadores, painel, noticias] = await Promise.all([lerIndicadores(), painelIbovespa(), obterNoticias()]);
  const grupos = ["Brasil", "Exterior", "Juros e moedas", "Commodities"] as const;
  const DESTAQUES = ["^BVSP", "USDBRL=X", "ES=F", "^IXIC", "BZ=F", "GC=F"];
  const destaques = DESTAQUES.flatMap((d) => indicadores.filter((i) => i.simbolo === d));
  const relevantes = noticias.dados.filter((n) => n.regiao === "BR").slice(0, 8);
  return (
    <>
      <CabecalhoPagina titulo="Mercado" descricao="Cotações com a referência de cada uma · variação contra o fechamento anterior - atualiza sozinho" />
      <MiniGraficoGridAoVivo inicial={destaques} className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6" />
      <div className="grid gap-3 xl:grid-cols-2">
        {grupos.map((g) => (
          <Painel key={g} titulo={g} rodape="Fonte: Yahoo Finance · cotações podem ter atraso">
            <TabelaIndicadoresAoVivo inicial={indicadores.filter((i) => i.grupo === g)} />
          </Painel>
        ))}
      </div>
      <PainelMercadoAoVivo inicial={painel} />
      <Painel titulo="Notícias relevantes · Brasil" sigla="NWS" className="mt-3" acao={<a href="/noticias" className="text-[11px] text-ambar hover:underline">Ver todas →</a>}>
        <EstadoDados r={noticias} />
        <ul className="divide-y divide-filete/60">
          {relevantes.map((n) => (
            <li key={n.link} className="flex gap-3 py-1.5 text-[12.5px]">
              <span className="w-24 shrink-0 font-mono text-[11px] text-apagado">{dataHora(n.publicadaEm)}</span>
              <LinkFonte href={n.link}>{n.titulo}</LinkFonte>
              <span className="ml-auto hidden shrink-0 text-[11px] text-apagado sm:inline">{n.veiculo}</span>
            </li>
          ))}
        </ul>
      </Painel>
      <p className="mt-2 text-[10.5px] text-apagado">{INDICADORES.length} indicadores e {painel.totalUniverso} ações monitoradas.</p>
    </>
  );
}
