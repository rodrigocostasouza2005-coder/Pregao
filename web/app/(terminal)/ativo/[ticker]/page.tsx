import ibovespa from "@/contratos/ibovespa.json";
import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { NotaEarnings } from "@/components/NotaEarnings";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { Variacao } from "@/components/Variacao";
import { data, dataHora, num } from "@/lib/formatos";
import { referenciaCotacao } from "@/lib/referencia";
import { lerEventosDoTicker } from "@/lib/server/dominio/agenda";
import { lerDocumentosCvm } from "@/lib/server/dominio/cvm";
import { lerEarnings } from "@/lib/server/dominio/inteligencia";
import { lerCarteiras, lerItensDoTicker } from "@/lib/server/dominio/research";
import { buscarNoticias } from "@/lib/server/noticias";
import { obterCotacao } from "@/lib/server/yahoo";

const SETORES = (ibovespa as { setores: Record<string, string> }).setores;

/** Cadeia EVENTO → ATIVO → NÚMEROS → FONTE → RESEARCH → REAÇÃO de um ativo,
 * só com o que os coletores e agentes já registraram. */
export default async function Ativo({ params }: { params: Promise<{ ticker: string }> }) {
  const ticker = decodeURIComponent((await params).ticker).toUpperCase().replace(/[^A-Z0-9.\-^=]/g, "");
  const simbolo = /^[A-Z]{4}\d{1,2}$/.test(ticker) ? `${ticker}.SA` : ticker;
  const [cotacao, eventos, cvm, earnings, itens, carteiras, noticias] = await Promise.all([
    obterCotacao(simbolo),
    lerEventosDoTicker(ticker),
    lerDocumentosCvm(20, { ticker: `eq.${ticker}` }),
    lerEarnings(4, ticker),
    lerItensDoTicker(ticker),
    lerCarteiras(),
    buscarNoticias(ticker),
  ]);
  const c = cotacao.dados;
  const recs = carteiras.dados.filter((x) => x.ticker === ticker);
  return (
    <>
      <CabecalhoPagina
        titulo={ticker}
        descricao={SETORES[ticker] ? `Setor: ${SETORES[ticker]} · Ibovespa` : "Ativo"}
        direita={
          c ? (
            <div className="text-right">
              <div className="font-mono text-[20px]">{num(c.preco)}</div>
              <div className="text-[12px]"><Variacao v={c.variacaoPct} /> <span className="ml-1 font-mono text-[10.5px] text-apagado">{referenciaCotacao(c)}</span></div>
            </div>
          ) : <span className="text-[12px] text-apagado">cotação indisponível</span>
        }
      />
      <div className="grid gap-3 xl:grid-cols-3">
        <Painel titulo="Eventos e documentos" acao={<Selo tipo="fato" />} rodape="eventos_resultados · cvm_documentos">
          <EstadoDados r={eventos} vazio="Sem eventos de resultado registrados." />
          <ul className="space-y-1 text-[12px]">
            {eventos.dados.map((e, i) => <li key={i}><span className="font-mono text-apagado">{data(e.data_evento)}</span> resultado {e.periodo} <span className="text-[10px] text-apagado">({e.status})</span></li>)}
          </ul>
          <div className="my-2 h-px bg-filete" />
          <EstadoDados r={cvm} vazio="Nenhum documento CVM coletado para o ativo." />
          <ul className="space-y-1 text-[12px]">
            {cvm.dados.map((d) => <li key={d.link}><span className="font-mono text-apagado">{data(d.data)}</span> <LinkFonte href={d.link}>{d.tipo}: {d.assunto}</LinkFonte></li>)}
          </ul>
        </Painel>
        <Painel titulo="Números publicados" rodape="Agente de earnings (CVM/SEC)">
          <EstadoDados r={earnings} vazio="Nenhum resultado processado para o ativo." />
          {earnings.dados.map((n) => <NotaEarnings key={n.id} nota={n} />)}
        </Painel>
        <Painel titulo="Research" acao={<Selo tipo="analista" />} rodape="Carteiras vigentes e publicações das casas monitoradas">
          {recs.length ? (
            <ul className="mb-2 space-y-1 text-[12px]">
              {recs.map((r) => <li key={r.id}><span className="text-ambar">{r.casa}</span> · {r.recomendacao || "em carteira"}{r.preco_alvo ? ` · alvo R$ ${num(r.preco_alvo)}` : ""} <LinkFonte href={r.fonte_url}><span className="text-[10.5px] text-apagado">({data(r.data_publicacao)})</span></LinkFonte></li>)}
            </ul>
          ) : <p className="mb-2 text-[12px] text-apagado">Nenhuma casa monitorada com o ativo em carteira vigente.</p>}
          <EstadoDados r={itens} vazio="Nenhuma publicação sobre o ativo." />
          <ul className="space-y-1 text-[12px]">
            {itens.dados.map((i) => <li key={i.link}><span className="font-mono text-[10.5px] text-apagado">{data(i.data)}</span> <span className="text-ambar">{i.casa}</span> <LinkFonte href={i.link}>{i.titulo}</LinkFonte></li>)}
          </ul>
        </Painel>
      </div>
      <Painel titulo="Notícias · 7 dias" className="mt-3" rodape={`Fonte: ${noticias.fonte} · busca pelo ticker`}>
        <EstadoDados r={noticias} />
        <ul className="divide-y divide-filete/60">
          {noticias.dados.map((n) => (
            <li key={n.link} className="flex gap-3 py-1.5 text-[12.5px]">
              <span className="w-24 shrink-0 font-mono text-[11px] text-apagado">{dataHora(n.publicadaEm)}</span>
              <LinkFonte href={n.link}>{n.titulo}</LinkFonte>
              <span className="ml-auto hidden shrink-0 text-[11px] text-apagado sm:inline">{n.veiculo}</span>
            </li>
          ))}
        </ul>
      </Painel>
    </>
  );
}
