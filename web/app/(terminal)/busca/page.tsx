import ibovespa from "@/contratos/ibovespa.json";
import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { data } from "@/lib/formatos";
import { NAVEGACAO } from "@/lib/navegacao";
import { buscarItens } from "@/lib/server/dominio/research";

const SETORES = (ibovespa as { setores: Record<string, string> }).setores;

export default async function Busca({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const q = ((await searchParams).q || "").trim();
  const Q = q.toUpperCase();
  const tickers = q ? Object.keys(SETORES).filter((t) => t.includes(Q) || SETORES[t].toUpperCase().includes(Q)).slice(0, 30) : [];
  const areas = q ? NAVEGACAO.filter((n) => `${n.rotulo} ${n.descricao}`.toLowerCase().includes(q.toLowerCase())) : [];
  const itens = q.length >= 3 ? await buscarItens(q) : null;
  const tickerLivre = /^[A-Z]{4}\d{1,2}$/.test(Q) && !tickers.includes(Q) ? Q : null;
  return (
    <>
      <CabecalhoPagina titulo="Busca" descricao={q ? `Resultados para "${q}"` : "Digite um ticker, setor, área ou título de research"} />
      <div className="grid gap-3 lg:grid-cols-2">
        <Painel titulo="Ativos">
          <div className="flex flex-wrap gap-1.5 text-[12px]">
            {tickerLivre ? <a href={`/ativo/${tickerLivre}`} className="rounded-sm border border-ambar px-2 py-0.5 font-mono">{tickerLivre}</a> : null}
            {tickers.map((t) => <a key={t} href={`/ativo/${t}`} className="rounded-sm border border-filete px-2 py-0.5 hover:border-ambar"><span className="font-mono">{t}</span> <span className="text-apagado">{SETORES[t]}</span></a>)}
            {!tickers.length && !tickerLivre ? <span className="text-apagado">Nenhum ativo do Ibovespa corresponde.</span> : null}
          </div>
          {areas.length ? <div className="mt-3 flex flex-wrap gap-2 text-[12px]">{areas.map((a) => <a key={a.rota} href={a.rota} className="text-ambar hover:underline">{a.rotulo}</a>)}</div> : null}
        </Painel>
        <Painel titulo="Research">
          {itens ? (
            <>
              <EstadoDados r={itens} vazio="Nenhuma publicação com esse termo no título." />
              <ul className="space-y-1 text-[12px]">
                {itens.dados.map((i) => <li key={i.link}><span className="font-mono text-[10.5px] text-apagado">{data(i.data)}</span> <span className="text-ambar">{i.casa}</span> <LinkFonte href={i.link}>{i.titulo}</LinkFonte></li>)}
              </ul>
            </>
          ) : <p className="text-[12px] text-apagado">Use pelo menos 3 caracteres.</p>}
        </Painel>
      </div>
    </>
  );
}
