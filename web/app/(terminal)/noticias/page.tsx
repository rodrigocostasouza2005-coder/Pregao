import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { AvisoParcial, EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { dataHora } from "@/lib/formatos";
import { obterNoticias } from "@/lib/server/noticias";

export const metadata = { title: "Notícias · Pregão" };

const FILTROS = [
  { id: "todas", rotulo: "Todas" },
  { id: "BR", rotulo: "Brasil" },
  { id: "INT", rotulo: "Internacional" },
  { id: "EMP", rotulo: "Empresas" },
] as const;

const POR_PAGINA = 60;

export default async function Noticias({ searchParams }: { searchParams: Promise<{ r?: string; p?: string }> }) {
  const { r: filtro = "todas", p = "1" } = await searchParams;
  const pagina = Math.max(1, Number(p) || 1);
  const noticias = await obterNoticias();
  const filtradas = noticias.dados.filter((n) => filtro === "todas" || (filtro === "EMP" ? n.empresa : n.regiao === filtro));
  const lista = filtradas.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);
  const paginas = Math.max(1, Math.ceil(filtradas.length / POR_PAGINA));
  return (
    <>
      <CabecalhoPagina titulo="Notícias" descricao="Últimas 36 h · manchete original, veículo, horário e link · duplicatas agrupadas" />
      <div className="mb-3 flex gap-1.5 text-[11.5px]">
        {FILTROS.map((f) => (
          <a key={f.id} href={`/noticias?r=${f.id}`} className={`rounded-sm border px-2 py-0.5 ${filtro === f.id ? "border-ambar text-texto" : "border-filete text-suave"}`}>
            {f.rotulo}
          </a>
        ))}
      </div>
      <Painel titulo={`${filtradas.length} manchetes`}
        acao={paginas > 1 ? (
          <span className="flex gap-2 font-mono text-[11px]">
            {pagina > 1 ? <a href={`/noticias?r=${filtro}&p=${pagina - 1}`} className="text-ambar">←</a> : null}
            <span className="text-apagado">{pagina}/{paginas}</span>
            {pagina < paginas ? <a href={`/noticias?r=${filtro}&p=${pagina + 1}`} className="text-ambar">→</a> : null}
          </span>
        ) : null} sigla="NWS" rodape={`Fonte: ${noticias.fonte} · editoria pelo assunto da manchete · mesmas regras do Morning Call: opinião, serviço e matérias sem relevância financeira ficam fora`}>
        <AvisoParcial mensagem={noticias.estado === "ok" ? noticias.mensagem : undefined} />
        <EstadoDados r={noticias} />
        <ul className="divide-y divide-filete/60">
          {lista.map((n) => (
            <li key={n.link} className="grid grid-cols-[5.5rem_1fr] gap-x-3 py-2 text-[12.5px] sm:grid-cols-[6rem_1fr_auto]">
              <span className="font-mono text-[11px] text-apagado">{dataHora(n.publicadaEm)}</span>
              <div>
                <LinkFonte href={n.link}><span className="text-texto">{n.titulo}</span></LinkFonte>
                <div className="mt-0.5 text-[11px] text-apagado">
                  {n.veiculos.join(" · ")}
                  {n.idioma === "en" ? <span className="ml-2 font-mono text-[9.5px] uppercase text-suave">em inglês · tradução pendente</span> : null}
                </div>
              </div>
              <span className={`hidden self-start rounded-sm border px-1.5 font-mono text-[9.5px] sm:inline ${n.regiao === "BR" ? "border-alta/40 text-alta" : "border-[#6aa7ff]/40 text-[#8fbcff]"}`}>
                {n.regiao === "BR" ? "BRASIL" : "MUNDO"}
              </span>
            </li>
          ))}
        </ul>
      </Painel>
    </>
  );
}
