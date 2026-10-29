import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { Tabela } from "@/components/Tabela";
import { TabelaIndicadores } from "@/components/TabelaIndicadores";
import { Variacao } from "@/components/Variacao";
import { dataHora, num } from "@/lib/formatos";
import { altasEBaixas, INDICADORES, lerIndicadores, painelIbovespa } from "@/lib/server/dominio/mercado";
import { obterNoticias } from "@/lib/server/noticias";

export const metadata = { title: "Mercado · Pregão" };

export default async function Mercado() {
  const [indicadores, painel, noticias] = await Promise.all([lerIndicadores(), painelIbovespa(), obterNoticias()]);
  const { altas, baixas } = altasEBaixas(painel.acoes);
  const grupos = ["Brasil", "Exterior", "Juros e moedas", "Commodities"] as const;
  const relevantes = noticias.dados.filter((n) => n.regiao === "BR").slice(0, 8);
  const tabelaAcoes = (lista: typeof altas) => (
    <Tabela
      linhas={lista}
      chave={(a) => a.ticker}
      vazio="Nenhuma ação nesta lista agora."
      colunas={[
        { titulo: "Ativo", celula: (a) => <a href={`/ativo/${a.ticker}`} className="font-mono hover:text-ambar">{a.ticker}</a> },
        { titulo: "Setor", celula: (a) => <span className="text-apagado">{a.setor}</span>, larga: true },
        { titulo: "Preço", celula: (a) => num(a.cotacao.preco), alinhar: "dir" },
        { titulo: "Var.", celula: (a) => <Variacao v={a.cotacao.variacaoPct} />, alinhar: "dir" },
      ]}
    />
  );
  return (
    <>
      <CabecalhoPagina titulo="Mercado" descricao="Cotações com a referência de cada uma · variação contra o fechamento anterior" />
      <div className="grid gap-3 xl:grid-cols-2">
        {grupos.map((g) => (
          <Painel key={g} titulo={g} rodape="Fonte: Yahoo Finance · cotações podem ter atraso">
            <TabelaIndicadores linhas={indicadores.filter((i) => i.grupo === g)} />
          </Painel>
        ))}
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Painel titulo="Maiores altas" sigla="IBOV" rodape={`Universo: ${painel.acoes.length} de ${painel.totalUniverso} ações do Ibovespa com cotação`}>
          {tabelaAcoes(altas)}
        </Painel>
        <Painel titulo="Maiores baixas" sigla="IBOV" rodape={
            painel.semCotacao.length
              ? painel.semCotacao.length > 10
                ? `${painel.semCotacao.length} ações sem cotação nesta leitura (fonte não respondeu)`
                : `Sem cotação nesta leitura: ${painel.semCotacao.join(", ")}`
              : "Fonte: Yahoo Finance"
          }>
          {tabelaAcoes(baixas)}
        </Painel>
        <Painel titulo="Desempenho setorial" rodape="Média simples da variação das ações de cada setor do Ibovespa">
          <Tabela
            linhas={painel.setores}
            chave={(s) => s.setor}
            vazio="Sem cotações para calcular os setores."
            colunas={[
              { titulo: "Setor", celula: (s) => s.setor },
              { titulo: "Ações", celula: (s) => s.n, alinhar: "dir" },
              { titulo: "Var. média", celula: (s) => <Variacao v={s.variacaoMedia} />, alinhar: "dir" },
            ]}
          />
        </Painel>
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
      <p className="mt-2 text-[10.5px] text-apagado">{INDICADORES.length} indicadores e {painel.totalUniverso} ações monitoradas.</p>
    </>
  );
}
