"use client";

import { num, numCompacto } from "@/lib/formatos";
import type { Acao, Painel as PainelDados } from "@/lib/server/dominio/mercado";
import { usePolling } from "@/lib/usePolling";
import { BarrasVariacao } from "./Grafico";
import { Painel } from "./Painel";
import { useAtivoSelecionadoOpcional } from "./SelecaoAtivo";
import { Tabela } from "./Tabela";
import { Variacao } from "./Variacao";

// Payload maior que a fita/indicadores (~85 ações do Ibovespa) -
// intervalo mais longo de propósito, mesmo espírito de não sobrecarregar
// a fonte que já guiou lib/server/yahoo.ts (revalidate) e FitaCotacoes.
const INTERVALO_MS = 90_000;

/** Mesma lógica pura de lib/server/dominio/mercado.ts:altasEBaixas /
 * maisNegociados - duplicada aqui (poucas linhas, sem I/O nenhum) porque
 * aquele módulo importa "server-only" lá no topo, o que barra o arquivo
 * inteiro (até funções puras) de entrar num Client Component. Qualquer
 * mudança no critério de ranking precisa espelhar as duas. */
function altasEBaixas(acoes: Acao[], n = 8) {
  const ord = [...acoes].sort((a, b) => (b.cotacao.variacaoPct as number) - (a.cotacao.variacaoPct as number));
  return { altas: ord.slice(0, n).filter((a) => (a.cotacao.variacaoPct as number) > 0), baixas: ord.slice(-n).reverse().filter((a) => (a.cotacao.variacaoPct as number) < 0) };
}

function maisNegociados(acoes: Acao[], n = 8) {
  return [...acoes]
    .filter((a) => typeof a.cotacao.volumeFinanceiro === "number")
    .sort((a, b) => (b.cotacao.volumeFinanceiro as number) - (a.cotacao.volumeFinanceiro as number))
    .slice(0, n);
}

function TickerClicavel({ ticker }: { ticker: string }) {
  const ctx = useAtivoSelecionadoOpcional();
  if (ctx) return <button type="button" onClick={() => ctx.selecionar(ticker)} className="font-mono hover:text-ambar">{ticker}</button>;
  return <a href={`/ativo/${ticker}`} className="font-mono hover:text-ambar">{ticker}</a>;
}

function TabelaAcoes({ lista }: { lista: Acao[] }) {
  return (
    <Tabela
      linhas={lista}
      chave={(a) => a.ticker}
      vazio="Nenhuma ação nesta lista agora."
      colunas={[
        { titulo: "Ativo", celula: (a) => <TickerClicavel ticker={a.ticker} /> },
        { titulo: "Setor", celula: (a) => <span className="text-apagado">{a.setor}</span>, larga: true },
        { titulo: "Preço", celula: (a) => num(a.cotacao.preco), alinhar: "dir" },
        { titulo: "Var.", celula: (a) => <Variacao v={a.cotacao.variacaoPct} />, alinhar: "dir" },
      ]}
    />
  );
}

function TabelaVolume({ lista }: { lista: Acao[] }) {
  return (
    <Tabela
      linhas={lista}
      chave={(a) => a.ticker}
      vazio="Sem leitura de volume financeiro agora."
      colunas={[
        { titulo: "Ativo", celula: (a) => <TickerClicavel ticker={a.ticker} /> },
        { titulo: "Setor", celula: (a) => <span className="text-apagado">{a.setor}</span>, larga: true },
        { titulo: "Preço", celula: (a) => num(a.cotacao.preco), alinhar: "dir" },
        { titulo: "Var.", celula: (a) => <Variacao v={a.cotacao.variacaoPct} />, alinhar: "dir" },
        { titulo: "Vol. fin.", celula: (a) => `R$ ${numCompacto(a.cotacao.volumeFinanceiro)}`, alinhar: "dir" },
      ]}
    />
  );
}

/** Ranking de altas/baixas, mais negociados (por volume financeiro real)
 * e desempenho setorial ao vivo - 3 listas sempre separadas (brief: "não
 * misturar essas três classificações"). Server Components não podem
 * passar função (render prop) pra Client Component (precisa ser
 * serializável), então este componente já desenha os painéis ele mesmo,
 * em vez de receber um `render` da página. */
export function PainelMercadoAoVivo({ inicial }: { inicial: PainelDados }) {
  const { dado } = usePolling<PainelDados>(inicial, "/api/mercado/painel", INTERVALO_MS);
  const p = dado.acoes?.length ? dado : inicial;
  const { altas, baixas } = altasEBaixas(p.acoes);
  const negociados = maisNegociados(p.acoes);
  return (
    <div className="mt-3 grid gap-3 lg:grid-cols-3">
      <Painel titulo="Maiores altas" sigla="IBOV" rodape={`Universo: ${p.acoes.length} de ${p.totalUniverso} ações do Ibovespa com cotação`}>
        <TabelaAcoes lista={altas} />
      </Painel>
      <Painel titulo="Maiores baixas" sigla="IBOV" rodape={
          p.semCotacao.length
            ? p.semCotacao.length > 10
              ? `${p.semCotacao.length} ações sem cotação nesta leitura (fonte não respondeu)`
              : `Sem cotação nesta leitura: ${p.semCotacao.join(", ")}`
            : "Fonte: Yahoo Finance"
        }>
        <TabelaAcoes lista={baixas} />
      </Painel>
      <Painel titulo="Mais negociados" sigla="IBOV" rodape="Volume financeiro real (preço × quantidade da última barra diária) - não é contagem de negócios">
        <TabelaVolume lista={negociados} />
      </Painel>
      <Painel titulo="Desempenho setorial" className="lg:col-span-3" rodape="Média simples da variação das ações de cada setor do Ibovespa (número de ações ao passar o mouse)">
        <BarrasVariacao itens={p.setores.map((s) => ({ rotulo: s.setor, valor: s.variacaoMedia, detalhe: `${s.n} ações` }))} />
      </Painel>
    </div>
  );
}
