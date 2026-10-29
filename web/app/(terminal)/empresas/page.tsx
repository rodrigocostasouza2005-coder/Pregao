import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { Tabela } from "@/components/Tabela";
import { Variacao } from "@/components/Variacao";
import { num } from "@/lib/formatos";
import { type Acao, painelIbovespa } from "@/lib/server/dominio/mercado";
import { resultado } from "@/lib/tipos";

export const metadata = { title: "Empresas · Pregão" };

type Ordem = "ticker" | "variacao" | "setor";

function ordenar(acoes: Acao[], ordem: Ordem): Acao[] {
  const lista = [...acoes];
  if (ordem === "variacao") return lista.sort((a, b) => (b.cotacao.variacaoPct ?? -Infinity) - (a.cotacao.variacaoPct ?? -Infinity));
  if (ordem === "setor") return lista.sort((a, b) => a.setor.localeCompare(b.setor) || a.ticker.localeCompare(b.ticker));
  return lista.sort((a, b) => a.ticker.localeCompare(b.ticker));
}

const ORDENS: Array<{ id: Ordem; rotulo: string }> = [
  { id: "ticker", rotulo: "Ticker" },
  { id: "variacao", rotulo: "Variação" },
  { id: "setor", rotulo: "Setor" },
];

export default async function Empresas({ searchParams }: { searchParams: Promise<{ q?: string; setor?: string; ordem?: string }> }) {
  const { q = "", setor = "", ordem: ordemRaw = "ticker" } = await searchParams;
  const termo = q.trim().toUpperCase();
  const ordem: Ordem = ordemRaw === "variacao" || ordemRaw === "setor" ? ordemRaw : "ticker";
  const painel = await painelIbovespa();
  const setores = [...new Set(painel.acoes.map((a) => a.setor))].sort();
  let acoes = painel.acoes;
  if (setor) acoes = acoes.filter((a) => a.setor === setor);
  if (termo) acoes = acoes.filter((a) => a.ticker.includes(termo) || a.setor.toUpperCase().includes(termo));
  acoes = ordenar(acoes, ordem);
  const resultadoAcoes = resultado(acoes.length ? "ok" : "vazio", acoes, "Yahoo Finance (universo Ibovespa)");
  const linkFiltro = (patch: Record<string, string>) => {
    const p = new URLSearchParams({ q, setor, ordem, ...patch });
    for (const [k, v] of [...p.entries()]) if (!v) p.delete(k);
    const s = p.toString();
    return s ? `/empresas?${s}` : "/empresas";
  };
  return (
    <>
      <CabecalhoPagina
        titulo="Empresas"
        descricao={`Universo Ibovespa · ${painel.totalUniverso} ações${painel.semCotacao.length ? ` · ${painel.semCotacao.length} sem cotação nesta leitura` : ""}`}
      />
      <form action="/empresas" className="mb-3 flex flex-wrap items-center gap-2">
        <input type="hidden" name="setor" value={setor} />
        <input type="hidden" name="ordem" value={ordem} />
        <input
          name="q"
          defaultValue={q}
          placeholder="Buscar ticker ou setor…"
          aria-label="Buscar empresa"
          className="w-56 rounded-sm border border-filete bg-base px-2.5 py-1 text-[12.5px] text-texto placeholder:text-apagado focus:border-ambar focus:outline-none"
        />
        <div className="flex flex-wrap gap-1.5 text-[11.5px]">
          <a href={linkFiltro({ setor: "" })} className={`rounded-sm border px-2 py-0.5 ${!setor ? "border-ambar text-texto" : "border-filete text-suave"}`}>Todos os setores</a>
          {setores.map((s) => (
            <a key={s} href={linkFiltro({ setor: s })} className={`rounded-sm border px-2 py-0.5 ${setor === s ? "border-ambar text-texto" : "border-filete text-suave"}`}>{s}</a>
          ))}
        </div>
        <div className="ml-auto flex gap-1.5 text-[11.5px]">
          <span className="self-center text-apagado">Ordenar:</span>
          {ORDENS.map((o) => (
            <a key={o.id} href={linkFiltro({ ordem: o.id })} className={`rounded-sm border px-2 py-0.5 ${ordem === o.id ? "border-ambar text-texto" : "border-filete text-suave"}`}>{o.rotulo}</a>
          ))}
        </div>
      </form>
      <EstadoDados r={resultadoAcoes} vazio="Nenhuma empresa corresponde aos filtros." />
      <Tabela
        linhas={acoes}
        chave={(a) => a.ticker}
        vazio={null}
        colunas={[
          { titulo: "Ticker", celula: (a) => <a href={`/ativo/${a.ticker}`} className="font-mono text-texto hover:text-ambar">{a.ticker}</a> },
          { titulo: "Setor", celula: (a) => <span className="text-apagado">{a.setor}</span>, larga: true },
          { titulo: "Preço", celula: (a) => num(a.cotacao.preco), alinhar: "dir" },
          { titulo: "Var.", celula: (a) => <Variacao v={a.cotacao.variacaoPct} />, alinhar: "dir" },
        ]}
      />
    </>
  );
}
