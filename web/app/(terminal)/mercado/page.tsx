import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { GraficoPrincipal } from "@/components/GraficoPrincipal";
import { IndicadoresCompactos } from "@/components/IndicadoresCompactos";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { PainelMercadoAoVivo } from "@/components/PainelMercadoAoVivo";
import { PainelWatchlist } from "@/components/PainelWatchlist";
import { SelecaoAtivoProvider } from "@/components/SelecaoAtivo";
import { TabelaIndicadoresAoVivo } from "@/components/TabelaIndicadoresAoVivo";
import { Variacao } from "@/components/Variacao";
import { dataHora, num } from "@/lib/formatos";
import { usuarioAtual } from "@/lib/server/auth";
import { INDICADORES, lerCotacoesTickers, lerIndicadores, lerIndicadoresCompactos, painelIbovespa } from "@/lib/server/dominio/mercado";
import { lerWatchlist } from "@/lib/server/dominio/userPrefs";
import { obterCotacao, obterSerie } from "@/lib/server/yahoo";
import { obterNoticias } from "@/lib/server/noticias";

export const metadata = { title: "Mercado · Pregão" };

const ATIVO_PADRAO = "^BVSP";

export default async function Mercado() {
  const usuario = await usuarioAtual();
  const [compactos, serie, cotacao, indicadores, painel, noticias, watchlist] = await Promise.all([
    lerIndicadoresCompactos({ comBrent: true }),
    obterSerie(ATIVO_PADRAO, "1D"),
    obterCotacao(ATIVO_PADRAO),
    lerIndicadores(),
    painelIbovespa(),
    obterNoticias(),
    usuario?.sub ? lerWatchlist(usuario.sub) : Promise.resolve<string[]>([]),
  ]);
  const watchlistCotacoes = await lerCotacoesTickers(watchlist);
  // grupos primários = B3 e o que move o real; "Exterior" (índices
  // americanos) fica numa seção secundária/opcional mais abaixo (brief:
  // "não quero uma interface dominada por índices americanos")
  const gruposPrimarios = ["Brasil", "Juros e moedas", "Commodities"] as const;
  const globais = indicadores.filter((i) => i.grupo === "Exterior");
  const relevantes = noticias.dados.filter((n) => n.regiao === "BR").slice(0, 8);
  return (
    <>
      <CabecalhoPagina titulo="Mercado" descricao="Amplitude do Ibovespa · ranking de ações · desempenho setorial - atualiza sozinho" />
      <IndicadoresCompactos inicial={compactos} comBrent />

      <SelecaoAtivoProvider padrao={ATIVO_PADRAO}>
        <div className="mt-3 grid gap-3 xl:grid-cols-3">
          <Painel titulo="Gráfico" sigla="GP" className="xl:col-span-2">
            <GraficoPrincipal simboloPadrao={ATIVO_PADRAO} nomePadrao="Ibovespa" serieInicial={serie} cotacaoInicial={cotacao} />
          </Painel>
          <Painel titulo="Minha watchlist" sigla="WL" rodape="Clique num ticker pra ver no gráfico · a mesma watchlist da fita superior">
            <PainelWatchlist inicial={watchlistCotacoes} />
          </Painel>
        </div>

        <PainelMercadoAoVivo inicial={painel} />
      </SelecaoAtivoProvider>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        {gruposPrimarios.map((g) => (
          <Painel key={g} titulo={g} rodape="Fonte: Yahoo Finance / Banco Central · cotações podem ter atraso">
            <TabelaIndicadoresAoVivo inicial={indicadores.filter((i) => i.grupo === g)} />
          </Painel>
        ))}
      </div>

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

      <Painel titulo="Mercados globais" className="mt-3" rodape="Referência secundária - o foco do Pregão é a B3">
        <div className="grid grid-cols-2 gap-px bg-filete sm:grid-cols-3 md:grid-cols-6">
          {globais.map((g) => (
            <div key={g.simbolo} className="bg-painel px-2.5 py-2">
              <div className="truncate text-[10px] text-apagado">{g.nome}</div>
              <div className="mt-0.5 flex items-baseline gap-1.5 font-mono text-[12.5px]">
                {g.r.dados ? num(g.r.dados.preco, g.casas) : "—"}
                <Variacao v={g.r.dados?.variacaoPct} casas={2} />
              </div>
            </div>
          ))}
        </div>
      </Painel>

      <p className="mt-2 text-[10.5px] text-apagado">{INDICADORES.length} indicadores e {painel.totalUniverso} ações monitoradas.</p>
    </>
  );
}
