import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { ListaMudancas } from "@/components/ListaMudancas";
import { MiniGraficoGridAoVivo } from "@/components/MiniGraficoGridAoVivo";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { TabelaIndicadoresAoVivo } from "@/components/TabelaIndicadoresAoVivo";
import { data, dataHora, hojeSaoPaulo, num } from "@/lib/formatos";
import { lerResultadosFuturos } from "@/lib/server/dominio/agenda";
import { lerSinteseMercado } from "@/lib/server/dominio/coordenador";
import { oQueMudou } from "@/lib/server/dominio/inteligencia";
import { INDICADORES, lerIndicadores } from "@/lib/server/dominio/mercado";
import { lerEdicoes, secoes } from "@/lib/server/dominio/morningCall";
import { mudancasRecomendacao } from "@/lib/server/dominio/research";
import { ESTADOS_OK, painelSaude } from "@/lib/server/dominio/saude";

export const metadata = { title: "Visão Geral · Pregão" };

const PRINCIPAIS = ["^BVSP", "USDBRL=X", "^GSPC", "ES=F", "BZ=F", "^TNX"];

export default async function VisaoGeral() {
  const [indicadores, mudou, edicoes, agenda, saude, sintese, mudancasTese] = await Promise.all([
    lerIndicadores(INDICADORES.filter((i) => PRINCIPAIS.includes(i.simbolo))),
    oQueMudou(8),
    lerEdicoes(1),
    lerResultadosFuturos(40),
    painelSaude(),
    lerSinteseMercado(),
    mudancasRecomendacao(6),
  ]);
  const hoje = hojeSaoPaulo();
  const eventosHoje = agenda.dados.filter((e) => e.data_evento === hoje);
  const ultima = edicoes.dados[0];
  const resumo = ultima ? secoes(ultima.conteudo).find((s) => s.titulo.includes("RESUMO")) : undefined;
  const problemas = saude.linhas.filter((l) => !ESTADOS_OK.has(l.estado.codigo)).length;
  return (
    <>
      <CabecalhoPagina titulo="Visão Geral" descricao="O que importa agora, com atalhos para cada área" />
      <MiniGraficoGridAoVivo inicial={indicadores} className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6" />

      <Painel
        titulo="Resumo executivo · Coordenador de Inteligência"
        sigla="COORD"
        className="mb-3"
        acao={<><Selo tipo="inferencia" /><a href="/inteligencia" className="ml-2 text-[11px] text-ambar hover:underline">Inteligência →</a></>}
      >
        <EstadoDados r={sintese} vazio="Síntese ainda não gerada - roda a cada ciclo do Coordenador." />
        {sintese.dados ? (
          <>
            <p className="text-[13px] text-texto">{sintese.dados.dados.resumo_executivo.texto}</p>
            <p className="mt-1 text-[10.5px] text-apagado">
              Fatos de {sintese.dados.geradoEm ? dataHora(sintese.dados.geradoEm) : "—"} · gerada {dataHora(sintese.dados.criadoEm)}
              {sintese.dados.desatualizada ? " · desatualizada, nenhuma rodada recente conseguiu gerar uma nova" : ""}
            </p>
          </>
        ) : null}
      </Painel>

      <div className="grid gap-3 xl:grid-cols-3">
        <Painel titulo="Mercado agora" sigla="MKT" acao={<a href="/mercado" className="text-[11px] text-ambar hover:underline">Mercado →</a>}>
          <TabelaIndicadoresAoVivo inicial={indicadores} semSessao />
        </Painel>
        <Painel titulo="Morning Call" sigla="MC" acao={<a href="/morning-call" className="text-[11px] text-ambar hover:underline">Edição →</a>}>
          <EstadoDados r={edicoes} vazio="Nenhuma edição registrada." />
          {ultima ? (
            <>
              <p className="mb-1 text-[11px] text-apagado">Edição de {data(ultima.dia)} · enviada {dataHora(ultima.executadoEm)}</p>
              <ul className="space-y-0.5 text-[12px] text-suave">{(resumo?.linhas || []).slice(0, 4).map((l, i) => <li key={i}>{l}</li>)}</ul>
            </>
          ) : null}
        </Painel>
        <Painel titulo="Hoje" sigla="AGD" acao={<a href="/agenda" className="text-[11px] text-ambar hover:underline">Agenda →</a>}>
          <EstadoDados r={agenda} vazio="Sem eventos." />
          {agenda.estado === "ok" ? (
            eventosHoje.length ? (
              <ul className="space-y-1 text-[12px]">{eventosHoje.map((e, i) => <li key={i}><a href={`/ativo/${e.ticker}`} className="font-mono hover:text-ambar">{e.ticker}</a> resultado {e.periodo} <span className="text-[10px] text-apagado">({e.status})</span></li>)}</ul>
            ) : <p className="text-[12px] text-apagado">Nenhum resultado corporativo no calendário para hoje.</p>
          ) : null}
          <p className="mt-2 border-t border-filete pt-2 text-[11px] text-apagado">
            Coletores: {saude.linhas.length - problemas}/{saude.linhas.length} OK · <a href="/configuracoes" className="text-ambar hover:underline">detalhes</a>
          </p>
        </Painel>
      </div>
      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Painel titulo="O que mudou" sigla="INT" className="xl:col-span-2" acao={<a href="/inteligencia" className="text-[11px] text-ambar hover:underline">Inteligência →</a>}>
          <EstadoDados r={mudou.r} vazio="Nenhuma mudança registrada." />
          <ListaMudancas itens={mudou.r.dados} />
        </Painel>
        <Painel titulo="Mudanças de tese" acao={<a href="/research" className="text-[11px] text-ambar hover:underline">Research →</a>}>
          <EstadoDados r={mudancasTese} vazio="Nenhuma mudança capturada ainda." />
          <ul className="space-y-1.5 text-[12px]">
            {mudancasTese.dados.map((m, i) => (
              <li key={i}>
                <span className="font-mono text-[10.5px] text-apagado">{dataHora(m.em)}</span>{" "}
                <span className="text-ambar">{m.casa}</span> · <a href={`/ativo/${m.ticker}`} className="font-mono hover:text-ambar">{m.ticker}</a>{" "}
                <span className="text-suave">
                  {m.antes ? `${m.antes.recomendacao || "—"} → ` : "início · "}
                  {m.depois.recomendacao || "—"}{m.depois.preco_alvo ? ` · alvo R$ ${num(m.depois.preco_alvo)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </Painel>
      </div>
    </>
  );
}
