import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { AvisoParcial, EstadoDados } from "@/components/EstadoDados";
import { ListaMudancas } from "@/components/ListaMudancas";
import { NotaEarnings } from "@/components/NotaEarnings";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { data, num } from "@/lib/formatos";
import { lerResultadosFuturos } from "@/lib/server/dominio/agenda";
import { lerEarnings, oQueMudou } from "@/lib/server/dominio/inteligencia";
import { CASAS, coberturaPorTicker, divergencias, lerCarteiras } from "@/lib/server/dominio/research";
import { ESTADOS_OK, painelSaude } from "@/lib/server/dominio/saude";

export const metadata = { title: "Inteligência · Pregão" };

export default async function Inteligencia() {
  const [mudou, carteiras, agenda, earnings, saude] = await Promise.all([oQueMudou(60), lerCarteiras(), lerResultadosFuturos(), lerEarnings(12), painelSaude()]);
  const div = divergencias(carteiras.dados);
  const cobertura = coberturaPorTicker(carteiras.dados);
  const cobertos = new Set(cobertura.map((c) => c.ticker));
  const limite = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
  const catalisadores = agenda.dados.filter((e) => e.data_evento <= limite && cobertos.has(e.ticker));
  const casasAtivas = CASAS.filter((c) => c.ativa_por_padrao).map((c) => c.nome);
  const casasComCarteira = new Set(carteiras.dados.map((c) => c.casa));
  const lacunas = casasAtivas.filter((c) => !casasComCarteira.has(c));
  const problemas = saude.linhas.filter((l) => !ESTADOS_OK.has(l.estado.codigo) && ["Noticias", "Cotacoes", "Macro", "CVM", "Radar", "Morning Call", "Research"].includes(l.categoria));
  return (
    <>
      <CabecalhoPagina
        titulo="Inteligência"
        descricao="Mudanças, divergências e catalisadores a partir dos coletores e agentes do Pregão · cada item mostra se é fato, visão de analista ou inferência"
        direita={<div className="flex gap-1"><Selo tipo="fato" /><Selo tipo="analista" /><Selo tipo="inferencia" /></div>}
      />
      {problemas.length ? (
        <p className="mb-3 border-l-2 border-ambar bg-ambar-fundo/50 px-3 py-1.5 text-[11.5px] text-suave">
          Evidência incompleta: {problemas.length} coletor(es) do núcleo sem coleta OK ({problemas.slice(0, 5).map((p) => p.nome).join(", ")}
          {problemas.length > 5 ? "…" : ""}). Conclusões abaixo podem estar desatualizadas - ver <a href="/configuracoes" className="text-ambar hover:underline">Configurações</a>.
        </p>
      ) : null}
      <div className="grid gap-3 xl:grid-cols-3">
        <Painel titulo="O que mudou?" sigla="INT" className="xl:col-span-2" rodape={`Fonte: ${mudou.r.fonte}`}>
          {mudou.parciais.map((p) => <AvisoParcial key={p} mensagem={p} />)}
          <EstadoDados r={mudou.r} vazio="Nenhuma mudança registrada pelos coletores." />
          <ListaMudancas itens={mudou.r.dados} />
        </Painel>
        <div className="space-y-3">
          <Painel titulo="Comitê · divergências" acao={<Selo tipo="analista" />} rodape="≥ 2 casas com recomendação estruturada diferente; nunca inferida">
            {div.length ? (
              <ul className="space-y-1.5 text-[12px]">
                {div.map((d) => (
                  <li key={d.ticker}>
                    <a href={`/ativo/${d.ticker}`} className="font-mono text-texto hover:text-ambar">{d.ticker}</a>{" "}
                    <span className="text-suave">{d.porCasa.map((p) => `${p.casa}: ${p.recomendacao}${p.preco_alvo ? ` (R$ ${num(p.preco_alvo)})` : ""}`).join(" · ")}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-[12px] text-apagado">{carteiras.estado === "ok" ? "Sem divergência estruturada nas carteiras vigentes." : carteiras.mensagem || "Sem carteiras."}</p>}
          </Painel>
          <Painel titulo="Comitê · cobertura" rodape="Quantas casas monitoradas incluem o ativo em carteira vigente">
            <div className="flex flex-wrap gap-1.5 text-[11.5px]">
              {cobertura.slice(0, 18).map((c) => (
                <a key={c.ticker} href={`/ativo/${c.ticker}`} className="rounded-sm border border-filete px-1.5 hover:border-ambar" title={c.casas.join(", ")}>
                  <span className="font-mono">{c.ticker}</span> <span className="text-apagado">{c.casas.length}</span>
                </a>
              ))}
            </div>
            {lacunas.length ? <p className="mt-2 text-[11px] text-apagado">Sem carteira vigente coletada: {lacunas.join(", ")}.</p> : null}
          </Painel>
          <Painel titulo="Catalisadores · 10 dias" acao={<Selo tipo="fato" texto="Data" />} rodape="Resultados de ativos com cobertura de research (agenda × carteiras)">
            <EstadoDados r={agenda} vazio="Sem eventos." />
            <ul className="space-y-1 text-[12px]">
              {catalisadores.map((e, i) => (
                <li key={i}>
                  <span className="font-mono text-[11px] text-apagado">{data(e.data_evento)}</span>{" "}
                  <a href={`/ativo/${e.ticker}`} className="font-mono hover:text-ambar">{e.ticker}</a>{" "}
                  <span className="text-suave">resultado {e.periodo}</span> <span className="text-[10px] text-apagado">({e.status})</span>
                </li>
              ))}
              {agenda.estado === "ok" && !catalisadores.length ? <li className="text-apagado">Nenhum resultado de ativo coberto nos próximos 10 dias.</li> : null}
            </ul>
          </Painel>
        </div>
      </div>
      <Painel titulo="Resultados processados · agente de earnings" className="mt-3" rodape="earnings_reviews · números da CVM/SEC; interpretações do agente marcadas como inferência">
        <EstadoDados r={earnings} vazio="Nenhum resultado processado ainda." />
        <div className="grid gap-x-6 lg:grid-cols-2">
          {earnings.dados.map((n) => <NotaEarnings key={n.id} nota={n} />)}
        </div>
      </Painel>
    </>
  );
}
