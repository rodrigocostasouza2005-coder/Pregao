import { Indicadores } from "@/components/Indicadores";
import { GraficoIbovespa } from "@/components/GraficoIbovespa";
import { LeituraPregao } from "@/components/LeituraPregao";
import { AltasBaixas } from "@/components/AltasBaixas";
import { MapaSetorial } from "@/components/MapaSetorial";
import { DesempenhoTabela } from "@/components/DesempenhoTabela";
import { Painel, Pendente } from "@/components/Painel";
import {
  obterPanoramaIbovespa,
  obterHistoricoIbovespa,
  calcularAltasBaixas,
  calcularDesempenhoSetorial,
  calcularMaisNegociados,
  concentracaoSetorial,
} from "@/lib/mercado";

// Pagina 100% dinamica de proposito: dados de mercado nunca podem ser
// pre-renderizados/cacheados estaticamente (ver Next.js "Cache
// Components", habilitado por padrao nesta versao).
export const instant = false;

export default async function VisaoGeralPage() {
  const [panorama, historico] = await Promise.all([
    obterPanoramaIbovespa(),
    obterHistoricoIbovespa("6M"),
  ]);

  const { altas, baixas } = calcularAltasBaixas(panorama, 4);
  const setores = calcularDesempenhoSetorial(panorama);
  const maisNegociados = calcularMaisNegociados(panorama, 6);
  const amostraConcentracao = calcularAltasBaixas(panorama, 6);
  const concentracao = concentracaoSetorial(panorama, [...amostraConcentracao.altas, ...amostraConcentracao.baixas]);
  const maisNegociado = maisNegociados[0] ?? null;

  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-accent font-bold text-lg tracking-wide">PREGÃO</span>
          <span className="text-text-faint text-[0.62rem] border border-border rounded-[2px] px-1.5 py-0.5">
            migração Next.js · preview
          </span>
        </div>
        <span className="text-text-faint text-[0.64rem]">Mercado › Visão Geral</span>
      </header>

      <main className="p-4 flex flex-col gap-4 max-w-[1440px] mx-auto">
        <LeituraPregao concentracao={concentracao} maisNegociado={maisNegociado} />

        <Indicadores />

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
          <GraficoIbovespa pontosIniciais={historico} />
          <Painel titulo="PARA INVESTIGAR">
            <Pendente motivo="depende da síntese por IA (data/sintese_mercado.py), ainda não portada" />
          </Painel>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1.2fr_1fr] gap-4">
          <Painel titulo="PRINCIPAIS ALTAS E BAIXAS">
            <AltasBaixas altas={altas} baixas={baixas} />
          </Painel>
          <Painel titulo="DESTAQUES DO DIA" sub="ÚLTIMAS 4">
            <Pendente motivo="feed de notícias (RSS, data/news.py) ainda não portado" />
          </Painel>
          <Painel titulo="MAPA SETORIAL">
            <MapaSetorial setores={setores} />
          </Painel>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4">
          <Painel titulo="DESEMPENHO DO IBOVESPA">
            <DesempenhoTabela papeis={maisNegociados} />
          </Painel>
          <Painel titulo="AGENDA · WATCHLIST">
            <Pendente motivo="depende de login e preferências do usuário (watchlist), autenticação ainda não portada" />
          </Painel>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Painel titulo="MERCADOS GLOBAIS">
            <Pendente motivo="será a mesma fonte Yahoo Finance (lib/yahoo.ts) — só falta ligar os índices internacionais" />
          </Painel>
          <Painel titulo="MINHA WATCHLIST">
            <Pendente motivo="depende de login e preferências do usuário, autenticação ainda não portada" />
          </Painel>
        </div>

        <footer className="text-text-faint text-[0.6rem] pb-6 pt-2">
          Dados de mercado: Yahoo Finance (cotações/histórico) e Banco Central (SGS, CDI) — mesmas fontes públicas e
          gratuitas do app Python original. Nenhum dado simulado é apresentado como real; módulos ainda não
          integrados mostram essa mensagem explicitamente em vez de inventar conteúdo.
        </footer>
      </main>
    </div>
  );
}
