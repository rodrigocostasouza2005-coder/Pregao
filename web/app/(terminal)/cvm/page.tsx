import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { Tabela } from "@/components/Tabela";
import { data, dataHora } from "@/lib/formatos";
import { lerDocumentosCvm } from "@/lib/server/dominio/cvm";

export const metadata = { title: "CVM · Pregão" };

export default async function Cvm({ searchParams }: { searchParams: Promise<{ destaque?: string }> }) {
  const { destaque } = await searchParams;
  const docs = await lerDocumentosCvm(200, destaque ? { destaque: "eq.true" } : undefined);
  return (
    <>
      <CabecalhoPagina titulo="CVM" descricao="Documentos coletados da CVM (IPE): fatos relevantes, comunicados e avisos" direita={<Selo tipo="fato" texto="Documento oficial" />} />
      <div className="mb-3 flex gap-1.5 text-[11.5px]">
        <a href="/cvm" className={`rounded-sm border px-2 py-0.5 ${!destaque ? "border-ambar" : "border-filete text-suave"}`}>Todos</a>
        <a href="/cvm?destaque=1" className={`rounded-sm border px-2 py-0.5 ${destaque ? "border-ambar" : "border-filete text-suave"}`}>Destaques</a>
      </div>
      <Painel titulo={`${docs.dados.length} documentos`} sigla="CVM" rodape="cvm_documentos · coletor CVM do Pregão · resumo do documento ainda não é gerado nesta tela">
        <EstadoDados r={docs} vazio="Nenhum documento coletado." />
        <Tabela
          linhas={docs.dados}
          chave={(d) => d.link}
          colunas={[
            { titulo: "Data", celula: (d) => <span className="font-mono text-[11px]">{data(d.data)}</span> },
            { titulo: "Empresa", celula: (d) => <a href={`/ativo/${d.ticker}`} className="font-mono hover:text-ambar">{d.ticker}</a> },
            { titulo: "Tipo", celula: (d) => <span className={d.destaque ? "text-ambar" : "text-suave"}>{d.tipo}</span> },
            { titulo: "Assunto", celula: (d) => <LinkFonte href={d.link}>{d.assunto || "(sem assunto)"}</LinkFonte> },
            { titulo: "Coletado", celula: (d) => <span className="font-mono text-[11px] text-apagado">{dataHora(d.coletado_em)}</span>, larga: true, alinhar: "dir" },
          ]}
        />
      </Painel>
    </>
  );
}
