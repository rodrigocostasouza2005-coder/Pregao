import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { AvisoParcial, EstadoDados } from "@/components/EstadoDados";
import { NotaEarnings } from "@/components/NotaEarnings";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { data, dataHora, idade, num } from "@/lib/formatos";
import { lerResultadosFuturos } from "@/lib/server/dominio/agenda";
import { definirEstadoIncidenteForm } from "@/lib/server/dominio/backofficeAcoes";
import {
  filaDeIncidentes, lerAchados, ROTULO_ESTADO, transicoesPermitidas, ultimasExecucoes,
  type EstadoIncidente, type IncidenteEnriquecido,
} from "@/lib/server/dominio/backoffice";
import { consolidar, type ItemConsolidado } from "@/lib/server/dominio/coordenador";
import { lerEarnings, oQueMudou } from "@/lib/server/dominio/inteligencia";
import { CASAS, coberturaPorTicker, divergencias, lerCarteiras, mudancasRecomendacao } from "@/lib/server/dominio/research";
import { ESTADOS_OK, painelSaude } from "@/lib/server/dominio/saude";
import { usuarioAtual } from "@/lib/server/auth";

export const metadata = { title: "Inteligência · Pregão" };

type Filtros = { ticker?: string; tipo?: string; estado?: string; critico?: string };

function filtroAtivo(atual: string | undefined, valor: string) {
  return atual === valor;
}

function linkFiltro(base: Filtros, mudanca: Partial<Filtros>) {
  const p = new URLSearchParams({ ...base, ...mudanca } as Record<string, string>);
  for (const [k, v] of Object.entries(mudanca)) if (!v) p.delete(k);
  for (const [k, v] of Object.entries(base)) if (!v) p.delete(k);
  const s = p.toString();
  return s ? `/inteligencia?${s}` : "/inteligencia";
}

const ROTULO_CATEGORIA: Record<ItemConsolidado["categoria"], string> = {
  incidente: "Backoffice", mudanca: "Mudança", divergencia: "Divergência", catalisador: "Catalisador",
};

function ChipFiltro({ ativo, href, children }: { ativo: boolean; href: string; children: React.ReactNode }) {
  return <a href={href} className={`rounded-sm border px-2 py-0.5 text-[11.5px] ${ativo ? "border-ambar text-texto" : "border-filete text-suave"}`}>{children}</a>;
}

function ItemDaFila({ item }: { item: ItemConsolidado }) {
  return (
    <li className="grid grid-cols-[6rem_1fr] gap-x-3 py-1.5 text-[12.5px]">
      <span className="font-mono text-[11px] text-apagado">{dataHora(item.em)}</span>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Selo tipo={item.natureza} />
          <span className="font-mono text-[10px] uppercase text-apagado">{ROTULO_CATEGORIA[item.categoria]}</span>
          {item.link ? (
            <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-texto hover:text-ambar hover:underline">{item.titulo}</a>
          ) : <span className="text-texto">{item.titulo}</span>}
        </div>
        <div className="mt-0.5 text-[11px] text-apagado">
          {item.detalhe ? <span className="mr-2 text-suave">{item.detalhe}</span> : null}
          Fonte: {item.fonte}
          {item.tickers.map((t) => <a key={t} href={`/ativo/${t}`} className="ml-2 font-mono text-suave hover:text-ambar">{t}</a>)}
        </div>
      </div>
    </li>
  );
}

const COR_ESTADO_COLETOR: Record<string, string> = {
  SUCESSO_COM_NOVIDADE: "text-alta", SUCESSO_SEM_NOVIDADE: "text-alta", PARCIAL: "text-ambar", DADOS_DESATUALIZADOS: "text-ambar",
  FONTE_INDISPONIVEL: "text-baixa", FALHA_EXECUCAO: "text-baixa", FALHA_PERSISTENCIA: "text-baixa", NAO_COMPROVADO: "text-apagado", NUNCA_EXECUTADO: "text-apagado",
};
const COR_EXECUCAO: Record<string, string> = { OK: "text-alta", PARCIAL: "text-ambar", ERRO: "text-baixa", EM_ANDAMENTO: "text-apagado" };

function LinhaIncidente({ a, admin, filtros }: { a: IncidenteEnriquecido; admin: boolean; filtros: Filtros }) {
  return (
    <li className="border-b border-filete/60 py-2 text-[12px] last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        {a.critico ? <Selo tipo="alerta" texto="Crítico" /> : <Selo tipo="neutro" texto="Atenção" />}
        <span className="font-mono text-[10px] uppercase text-apagado">{ROTULO_ESTADO[a.status]}</span>
        <span className="text-texto">{a.coletor}</span>
        <span className="text-apagado">({a.categoria})</span>
        {a.ocorrencias > 1 ? <span className="text-[10.5px] text-apagado">{a.ocorrencias}x desde {data(a.primeira_ocorrencia_em)}</span> : null}
      </div>
      <p className="mt-0.5 text-suave">{a.descricao}</p>
      {a.causaProvavel ? (
        <p className="mt-0.5 text-[11px] text-apagado">
          <Selo tipo="inferencia" texto="Hipótese" /> <span className="ml-1">Causa provável: {a.causaProvavel}</span>
        </p>
      ) : null}
      {a.proximaAcao ? <p className="text-[11px] text-apagado">Próxima ação recomendada: {a.proximaAcao}</p> : null}
      <p className="mt-0.5 text-[10.5px] text-apagado">Última ocorrência: {dataHora(a.ultima_ocorrencia_em)} ({idade(a.ultima_ocorrencia_em)})</p>
      {admin && transicoesPermitidas(a.status).length ? (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {transicoesPermitidas(a.status).map((destino) => (
            <form key={destino} action={definirEstadoIncidenteForm.bind(null, a.id, a.status, destino)}>
              <button type="submit" className="rounded-sm border border-filete px-1.5 py-0.5 text-[10.5px] text-suave hover:border-ambar hover:text-ambar">
                {ROTULO_ESTADO[destino]}
              </button>
            </form>
          ))}
        </div>
      ) : null}
      {!admin ? <p className="mt-1 text-[10px] text-apagado">Só administradores podem alterar o estado · <a href={linkFiltro(filtros, {})} className="hover:text-ambar">ver tudo</a></p> : null}
    </li>
  );
}

export default async function Inteligencia({ searchParams }: { searchParams: Promise<Filtros> }) {
  const filtros = await searchParams;
  const [usuario, mudou, carteiras, agenda, earnings, saude, coordenado, execucoes, mudancasTese, achados] = await Promise.all([
    usuarioAtual(), oQueMudou(60), lerCarteiras(), lerResultadosFuturos(), lerEarnings(12), painelSaude(),
    consolidar(80), ultimasExecucoes(), mudancasRecomendacao(20), lerAchados(200),
  ]);
  const resolvidos = filaDeIncidentes(achados.dados).filter((a) => a.status === "RESOLVIDO").slice(0, 15);

  const div = divergencias(carteiras.dados);
  const cobertura = coberturaPorTicker(carteiras.dados);
  const cobertos = new Set(cobertura.map((c) => c.ticker));
  const limite = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
  const catalisadores = agenda.dados.filter((e) => e.data_evento <= limite && cobertos.has(e.ticker));
  const casasAtivas = CASAS.filter((c) => c.ativa_por_padrao).map((c) => c.nome);
  const casasComCarteira = new Set(carteiras.dados.map((c) => c.casa));
  const lacunas = casasAtivas.filter((c) => !casasComCarteira.has(c));
  const problemas = saude.linhas.filter((l) => !ESTADOS_OK.has(l.estado.codigo) && ["Noticias", "Cotacoes", "Macro", "CVM", "Radar", "Morning Call", "Research"].includes(l.categoria));

  // --- Filtros (Fase 4: ativo, tipo de evento, prioridade, estado) -------
  const itensFiltrados = coordenado.itens.filter((it) => {
    if (filtros.ticker && !it.tickers.includes(filtros.ticker.toUpperCase())) return false;
    if (filtros.tipo && it.categoria !== filtros.tipo) return false;
    if (filtros.critico === "1" && it.prioridade > 50) return false;
    return true;
  });
  const filaInvestigacao = itensFiltrados.filter((it) => it.categoria !== "catalisador").slice(0, 40);

  const todosAchados = [...coordenado.incidentesAbertos];
  const incidentesFiltrados = filtros.estado ? todosAchados.filter((a) => a.status === filtros.estado) : todosAchados;

  const execBackoffice = execucoes.ultimas.find((e) => e.tipo === "backoffice");
  const execSintese = execucoes.ultimas.find((e) => e.tipo === "sintese");

  return (
    <>
      <CabecalhoPagina
        titulo="Inteligência"
        descricao="Coordenador: consolida mudanças, divergências, incidentes operacionais e síntese de IA a partir dos coletores e agentes do Pregão · cada item mostra se é fato, visão de analista, cálculo interno ou inferência"
        direita={<div className="flex gap-1"><Selo tipo="fato" /><Selo tipo="analista" /><Selo tipo="calculo" /><Selo tipo="inferencia" /></div>}
      />
      {problemas.length ? (
        <p className="mb-3 border-l-2 border-ambar bg-ambar-fundo/50 px-3 py-1.5 text-[11.5px] text-suave">
          Evidência incompleta: {problemas.length} coletor(es) do núcleo sem coleta OK ({problemas.slice(0, 5).map((p) => p.nome).join(", ")}
          {problemas.length > 5 ? "…" : ""}). Conclusões abaixo podem estar desatualizadas - ver <a href="/configuracoes" className="text-ambar hover:underline">Configurações</a>.
        </p>
      ) : null}
      {coordenado.fontesIndisponiveis.map((f) => <AvisoParcial key={f} mensagem={f} />)}

      <div className="mb-3 flex flex-wrap items-center gap-1.5 text-[11px] text-apagado">
        <span className="mr-1 uppercase tracking-wider">Filtrar:</span>
        <ChipFiltro ativo={!filtros.tipo} href={linkFiltro(filtros, { tipo: undefined })}>Todos os tipos</ChipFiltro>
        {(["incidente", "mudanca", "divergencia", "catalisador"] as const).map((t) => (
          <ChipFiltro key={t} ativo={filtroAtivo(filtros.tipo, t)} href={linkFiltro(filtros, { tipo: t })}>{ROTULO_CATEGORIA[t]}</ChipFiltro>
        ))}
        <span className="mx-1">·</span>
        <ChipFiltro ativo={filtros.critico === "1"} href={linkFiltro(filtros, { critico: filtros.critico === "1" ? undefined : "1" })}>Só crítico</ChipFiltro>
        {filtros.ticker ? <ChipFiltro ativo href={linkFiltro(filtros, { ticker: undefined })}>Ativo: {filtros.ticker.toUpperCase()} ✕</ChipFiltro> : null}
      </div>

      <Painel
        titulo="Coordenador · Resumo executivo"
        sigla="COORD"
        className="mb-3"
        acao={<Selo tipo="inferencia" />}
        rodape={coordenado.sintese.dados
          ? `Síntese via IA (Groq) · fatos de ${coordenado.sintese.dados.geradoEm ? dataHora(coordenado.sintese.dados.geradoEm) : "—"} · gerada ${dataHora(coordenado.sintese.dados.criadoEm)}${coordenado.sintese.dados.desatualizada ? " · ⚠ desatualizada, nenhuma rodada recente conseguiu gerar uma nova" : ""}`
          : "resumos_ia_cache · origem=sintese_mercado"}
      >
        <EstadoDados r={coordenado.sintese} vazio="Síntese ainda não gerada - roda a cada ciclo do Coordenador (jobs/coordenador.py)." />
        {coordenado.sintese.dados ? (
          <div className="grid gap-3 lg:grid-cols-[1fr_18rem]">
            <div>
              <p className="text-[13px] text-texto">{coordenado.sintese.dados.dados.resumo_executivo.texto}</p>
              {coordenado.sintese.dados.dados.resumo_executivo.ressalvas ? (
                <p className="mt-1 text-[11px] text-apagado">Ressalvas: {coordenado.sintese.dados.dados.resumo_executivo.ressalvas}</p>
              ) : null}
              {coordenado.sintese.dados.dados.o_que_nao_sabemos.length ? (
                <p className="mt-2 text-[11px] text-apagado">
                  <Selo tipo="insuficiente" /> <span className="ml-1">{coordenado.sintese.dados.dados.o_que_nao_sabemos.join(" · ")}</span>
                </p>
              ) : null}
            </div>
            <div className="space-y-1.5 border-l border-filete pl-3 text-[11.5px]">
              <p className="text-[10px] uppercase tracking-wider text-apagado">Cenários (qualitativo, sem probabilidade)</p>
              {coordenado.sintese.dados.dados.cenarios.map((c, i) => (
                <p key={i}><span className={c.tipo === "principal" ? "text-ambar" : "text-suave"}>{c.tipo === "principal" ? "Principal" : "Alternativo"}:</span> {c.cenario}</p>
              ))}
              {!coordenado.sintese.dados.dados.cenarios.length ? <p className="text-apagado">Sem cenário extraído nesta rodada.</p> : null}
            </div>
          </div>
        ) : null}
      </Painel>

      <div className="grid gap-3 xl:grid-cols-3">
        <Painel titulo="Fila de investigação" sigla="INV" className="xl:col-span-2" rodape="Incidentes do Backoffice + mudanças e divergências mais relevantes, priorizados · nunca duplica o mesmo evento">
          <EstadoDados r={mudou.r} vazio="Nenhum item na fila." />
          {filaInvestigacao.length ? <ul className="divide-y divide-filete/60">{filaInvestigacao.map((it, i) => <ItemDaFila key={i} item={it} />)}</ul> : <p className="text-[12px] text-apagado">Nenhum item com os filtros atuais.</p>}
        </Painel>
        <div className="space-y-3">
          <Painel titulo="Status dos especialistas" rodape="Última execução de cada agente agendado (jobs/coordenador.py)">
            <ul className="space-y-1.5 text-[11.5px]">
              <li className="flex items-center justify-between"><span className="text-suave">Backoffice (achados)</span>{execBackoffice ? <span className={COR_EXECUCAO[execBackoffice.status]}>{execBackoffice.status} · {idade(execBackoffice.iniciado_em)}</span> : <span className="text-apagado">nunca rodou</span>}</li>
              <li className="flex items-center justify-between"><span className="text-suave">Síntese (IA)</span>{execSintese ? <span className={COR_EXECUCAO[execSintese.status]}>{execSintese.status} · {idade(execSintese.iniciado_em)}</span> : <span className="text-apagado">nunca rodou</span>}</li>
              {saude.linhas.filter((l) => problemas.includes(l)).slice(0, 6).map((l) => (
                <li key={l.nome} className="flex items-center justify-between"><span className="text-suave">{l.nome}</span><span className={COR_ESTADO_COLETOR[l.estado.codigo]}>{l.estado.codigo}</span></li>
              ))}
            </ul>
          </Painel>
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
        </div>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Painel titulo="Mudanças de tese" rodape="research_recomendacoes_historico · comparação entre capturas sucessivas por casa+ticker">
          <EstadoDados r={mudancasTese} vazio="Nenhuma mudança capturada ainda." />
          <ul className="space-y-1.5 text-[12px]">
            {mudancasTese.dados.slice(0, 10).map((m, i) => (
              <li key={i}>
                <span className="font-mono text-[10.5px] text-apagado">{dataHora(m.em)}</span>{" "}
                <span className="text-ambar">{m.casa}</span> · <a href={`/ativo/${m.ticker}`} className="font-mono hover:text-ambar">{m.ticker}</a>{" "}
                <span className="text-suave">{m.antes ? `${m.antes.recomendacao || "—"} → ` : "início · "}{m.depois.recomendacao || "—"}{m.depois.preco_alvo ? ` · alvo R$ ${num(m.depois.preco_alvo)}` : ""}</span>
              </li>
            ))}
          </ul>
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
      </div>

      <Painel
        titulo="Backoffice · fila de incidentes"
        className="mt-3"
        sigla="OPS"
        acao={<span className="font-mono text-[11px] text-suave">{incidentesFiltrados.length} aberto(s)</span>}
        rodape="market_researcher_achados · prioridade = crítico primeiro, depois estado mais grave, depois mais recorrente"
      >
        <div className="mb-2 flex flex-wrap gap-1.5 text-[11px] text-apagado">
          <ChipFiltro ativo={!filtros.estado} href={linkFiltro(filtros, { estado: undefined })}>Todos</ChipFiltro>
          {(["ABERTO", "INVESTIGANDO", "AGUARDANDO_INTERVENCAO", "INCONCLUSIVO"] as EstadoIncidente[]).map((e) => (
            <ChipFiltro key={e} ativo={filtroAtivo(filtros.estado, e)} href={linkFiltro(filtros, { estado: e })}>{ROTULO_ESTADO[e]}</ChipFiltro>
          ))}
        </div>
        {incidentesFiltrados.length ? (
          <ul>{incidentesFiltrados.slice(0, 30).map((a) => <LinhaIncidente key={a.id} a={a} admin={!!usuario?.admin} filtros={filtros} />)}</ul>
        ) : <p className="text-[12px] text-apagado">Nenhum incidente aberto com os filtros atuais - não significa ausência de coleta nova, só que nada precisa de atenção agora.</p>}
      </Painel>

      <Painel titulo="Histórico · incidentes resolvidos" className="mt-3" rodape="market_researcher_achados · status=RESOLVIDO (fechado automaticamente quando o achado deixa de aparecer)">
        {resolvidos.length ? (
          <ul className="space-y-1 text-[12px]">
            {resolvidos.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-2">
                <span className="text-apagado">{a.resolvido_em ? data(a.resolvido_em) : "—"}</span>
                <span className="text-texto">{a.coletor}</span>
                <span className="text-apagado">({a.categoria})</span>
                <span className="text-suave">{a.descricao}</span>
                <span className="text-[10.5px] text-apagado">{a.ocorrencias}x</span>
              </li>
            ))}
          </ul>
        ) : <p className="text-[12px] text-apagado">Nenhum incidente resolvido ainda.</p>}
      </Painel>

      <Painel titulo="Resultados processados · agente de earnings" className="mt-3" rodape="earnings_reviews · números da CVM/SEC; interpretações do agente marcadas como inferência">
        <EstadoDados r={earnings} vazio="Nenhum resultado processado ainda." />
        <div className="grid gap-x-6 lg:grid-cols-2">
          {earnings.dados.map((n) => <NotaEarnings key={n.id} nota={n} />)}
        </div>
      </Painel>
    </>
  );
}
