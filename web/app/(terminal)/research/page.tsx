import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { LinkFonte } from "@/components/LinkFonte";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { Tabela } from "@/components/Tabela";
import { data, dataHora, num } from "@/lib/formatos";
import { CASAS, coberturaPorTicker, divergencias, lerCarteiras, lerItens, mudancasRecomendacao } from "@/lib/server/dominio/research";

export const metadata = { title: "Research · Pregão" };

export default async function Research({ searchParams }: { searchParams: Promise<{ casa?: string }> }) {
  const { casa } = await searchParams;
  const [itens, carteiras, mudancas] = await Promise.all([lerItens(150), lerCarteiras(), mudancasRecomendacao(40)]);
  const itensFiltrados = casa ? itens.dados.filter((i) => i.casa === casa) : itens.dados;
  const div = divergencias(carteiras.dados);
  const cobertura = coberturaPorTicker(carteiras.dados).slice(0, 15);
  const porCasa = new Map<string, number>();
  for (const i of itens.dados) porCasa.set(i.casa, (porCasa.get(i.casa) || 0) + 1);
  return (
    <>
      <CabecalhoPagina
        titulo="Research"
        descricao={`Casas monitoradas: ${CASAS.length} · publicações, carteiras recomendadas e mudanças capturadas pelos coletores`}
        direita={<Selo tipo="analista" />}
      />
      <div className="mb-3 flex flex-wrap gap-1.5 text-[11.5px]">
        <a href="/research" className={`rounded-sm border px-2 py-0.5 ${!casa ? "border-ambar text-texto" : "border-filete text-suave"}`}>Todas</a>
        {CASAS.map((c) => (
          <a key={c.id} href={`/research?casa=${encodeURIComponent(c.nome)}`} className={`rounded-sm border px-2 py-0.5 ${casa === c.nome ? "border-ambar text-texto" : "border-filete text-suave"}`}>
            {c.nome} <span className="font-mono text-apagado">{porCasa.get(c.nome) || 0}</span>
          </a>
        ))}
      </div>
      <div className="grid gap-3 xl:grid-cols-3">
        <Painel titulo="Publicações" sigla="RSH" className="xl:col-span-2" rodape="research_itens · resumo por IA quando disponível, nunca o texto integral">
          <EstadoDados r={itens} vazio="Nenhuma publicação coletada." />
          <ul className="divide-y divide-filete/60">
            {itensFiltrados.slice(0, 40).map((i) => (
              <li key={i.link} className="py-2">
                <div className="flex flex-wrap items-baseline gap-x-2 text-[12.5px]">
                  <span className="font-mono text-[11px] text-apagado">{data(i.data)}</span>
                  <span className="text-[11px] text-ambar">{i.casa}</span>
                  <LinkFonte href={i.link}><span className="text-texto">{i.titulo}</span></LinkFonte>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-2 text-[11px] text-apagado">
                  <span>{i.tipo}</span>
                  {i.tickers?.map((t) => <a key={t} href={`/ativo/${t}`} className="font-mono text-suave hover:text-ambar">{t}</a>)}
                  {i.recomendacao ? <span className="text-suave">Recomendação: {i.recomendacao}</span> : null}
                  {i.preco_alvo ? <span className="text-suave">Alvo: R$ {num(i.preco_alvo)}</span> : null}
                </div>
                {i.resumo ? <p className="mt-1 line-clamp-3 text-[12px] text-suave">{i.resumo}</p> : null}
              </li>
            ))}
          </ul>
        </Painel>
        <div className="space-y-3">
          <Painel titulo="Mudanças de recomendação" rodape="Comparação entre capturas sucessivas (research_recomendacoes_historico)">
            <EstadoDados r={mudancas} vazio="Nenhuma mudança capturada ainda." />
            <ul className="space-y-1.5 text-[12px]">
              {mudancas.dados.slice(0, 12).map((m, i) => (
                <li key={i}>
                  <span className="font-mono text-[10.5px] text-apagado">{dataHora(m.em)}</span>{" "}
                  <span className="text-ambar">{m.casa}</span> · <a href={`/ativo/${m.ticker}`} className="font-mono hover:text-ambar">{m.ticker}</a>{" "}
                  <span className="text-suave">
                    {m.antes ? `${m.antes.recomendacao || "—"} → ` : "início · "}
                    {m.depois.recomendacao || "—"}
                    {m.depois.preco_alvo ? ` · alvo R$ ${num(m.depois.preco_alvo)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </Painel>
          <Painel titulo="Divergências entre casas" rodape="Só quando ≥ 2 casas têm recomendação estruturada diferente (regra do Market Researcher)">
            {div.length ? (
              <ul className="space-y-2 text-[12px]">
                {div.map((d) => (
                  <li key={d.ticker}>
                    <a href={`/ativo/${d.ticker}`} className="font-mono text-texto hover:text-ambar">{d.ticker}</a>
                    <ul className="ml-3 text-suave">
                      {d.porCasa.map((p) => <li key={p.casa}>{p.casa}: {p.recomendacao}{p.preco_alvo ? ` · R$ ${num(p.preco_alvo)}` : ""}</li>)}
                    </ul>
                  </li>
                ))}
              </ul>
            ) : <p className="text-[12px] text-apagado">{carteiras.estado === "ok" ? "Nenhuma divergência estruturada entre as carteiras vigentes." : "Sem carteiras para comparar."}</p>}
          </Painel>
        </div>
      </div>
      <Painel titulo="Carteiras recomendadas vigentes" className="mt-3" rodape="radar_carteiras_recomendadas · vigente = true">
        <EstadoDados r={carteiras} vazio="Nenhuma carteira vigente coletada." />
        <Tabela
          linhas={carteiras.dados}
          vazio={carteiras.estado === "ok" ? undefined : null}
          chave={(c) => String(c.id)}
          colunas={[
            { titulo: "Casa", celula: (c) => <span className="text-ambar">{c.casa}</span> },
            { titulo: "Carteira", celula: (c) => <span className="text-suave">{c.carteira}</span>, larga: true },
            { titulo: "Ativo", celula: (c) => <a href={`/ativo/${c.ticker}`} className="font-mono hover:text-ambar">{c.ticker}</a> },
            { titulo: "Recomendação", celula: (c) => c.recomendacao || "—" },
            { titulo: "Alvo", celula: (c) => (c.preco_alvo ? num(c.preco_alvo) : "—"), alinhar: "dir" },
            { titulo: "Publicação", celula: (c) => <LinkFonte href={c.fonte_url}>{data(c.data_publicacao)}</LinkFonte>, alinhar: "dir" },
          ]}
        />
      </Painel>
      <Painel titulo="Ativos com mais cobertura" className="mt-3">
        <div className="flex flex-wrap gap-2 text-[12px]">
          {cobertura.map((c) => (
            <a key={c.ticker} href={`/ativo/${c.ticker}`} className="rounded-sm border border-filete px-2 py-0.5 hover:border-ambar">
              <span className="font-mono">{c.ticker}</span> <span className="text-apagado">{c.casas.length} casa(s)</span>
            </a>
          ))}
          {!cobertura.length ? <span className="text-apagado">{carteiras.estado === "ok" ? "Nenhum ativo com carteira vigente coletada." : "Indisponível: a leitura das carteiras não retornou dados."}</span> : null}
        </div>
      </Painel>
    </>
  );
}
