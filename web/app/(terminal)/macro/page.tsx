import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { Grafico } from "@/components/Grafico";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { TabelaIndicadores } from "@/components/TabelaIndicadores";
import { data, hojeSaoPaulo, num } from "@/lib/formatos";
import { focus, historicoPtax, historicoSgs, ptaxOlinda, selicPeloCopom, SERIES_SGS, ultimaSgs, type LeituraSgs } from "@/lib/server/bcb";
import { lerIndicadores, type Indicador } from "@/lib/server/dominio/mercado";
import { obterSerie } from "@/lib/server/yahoo";
import type { Resultado } from "@/lib/tipos";

export const metadata = { title: "Macro · Pregão" };

const EXTERIOR: Indicador[] = [
  { nome: "Treasury 10 anos (%)", simbolo: "^TNX", grupo: "Juros e moedas", casas: 3 },
  { nome: "Treasury 5 anos (%)", simbolo: "^FVX", grupo: "Juros e moedas", casas: 3 },
  { nome: "Treasury 30 anos (%)", simbolo: "^TYX", grupo: "Juros e moedas", casas: 3 },
  { nome: "Índice dólar (DXY)", simbolo: "DX-Y.NYB", grupo: "Juros e moedas", casas: 2 },
  { nome: "Dólar (USD/BRL)", simbolo: "USDBRL=X", grupo: "Juros e moedas", casas: 4 },
  { nome: "Petróleo Brent", simbolo: "BZ=F", grupo: "Commodities", casas: 2 },
];

export default async function Macro() {
  const ano = Number(new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric" }).format(new Date()));
  const hoje = hojeSaoPaulo();
  const chaves = Object.keys(SERIES_SGS) as Array<keyof typeof SERIES_SGS>;
  const [sgsBruto, expectativas, exterior, histSelic, histIpca, histPtax, treasury] = await Promise.all([
    Promise.all(chaves.map((k) => ultimaSgs(SERIES_SGS[k].codigo))),
    focus(["IPCA", "Selic", "PIB Total", "Câmbio"], [ano, ano + 1]),
    lerIndicadores(EXTERIOR),
    historicoSgs(SERIES_SGS.selicMeta.codigo, 3 * 365),
    historicoSgs(SERIES_SGS.ipca12m.codigo, 5 * 365),
    historicoSgs(SERIES_SGS.ptaxVenda.codigo, 365).then((r) => (r.estado === "ok" ? r : historicoPtax(365))),
    obterSerie("^TNX", "1A"),
  ]);
  // a série diária da meta já vem até a próxima reunião: só até hoje
  const ate = (r: Resultado<LeituraSgs[]>) => r.dados.filter((l) => l.data <= hoje).map((l) => ({ t: Date.parse(l.data), v: l.valor }));
  const historicos = [
    { titulo: "Selic meta · 3 anos", r: histSelic, pontos: ate(histSelic), degrau: true, sufixo: "% a.a.", eixo: "mes" as const },
    { titulo: "IPCA 12 meses · 5 anos", r: histIpca, pontos: ate(histIpca), degrau: false, sufixo: "%", eixo: "ano" as const },
    { titulo: "Dólar PTAX · 1 ano", r: histPtax, pontos: ate(histPtax), degrau: false, sufixo: "", eixo: "mes" as const },
  ];
  // planos B oficiais (mesma instituição): Selic pelo histórico do Copom,
  // dólar pela API PTAX - a fonte usada fica escrita na linha
  const sgs = await Promise.all(
    chaves.map(async (k, i) => {
      if (sgsBruto[i].estado === "ok") return sgsBruto[i];
      if (k === "selicMeta") return selicPeloCopom();
      if (k === "ptaxVenda") return ptaxOlinda();
      return sgsBruto[i];
    }),
  );
  return (
    <>
      <CabecalhoPagina titulo="Macro" descricao="Dados oficiais divulgados, expectativas de mercado e referências internacionais" />
      <div className="grid gap-3 xl:grid-cols-2">
        <Painel titulo="Brasil · dado divulgado" acao={<Selo tipo="fato" />} rodape="Fonte: Banco Central do Brasil - SGS; planos B oficiais: histórico do Copom (Selic) e API PTAX (dólar)">
          <table className="w-full text-[12.5px]">
            <tbody>
              {chaves.map((k, i) => {
                const s = SERIES_SGS[k];
                const r = sgs[i];
                return (
                  <tr key={k} className="border-b border-filete/60 last:border-0">
                    <td className="py-1.5">{s.nome} <span className="ml-1 font-mono text-[10px] text-apagado">{r.fonte.replace("Banco Central ", "")}</span></td>
                    <td className="py-1.5 text-right font-mono">
                      {r.dados ? `${num(r.dados.valor, s.unidade === "R$" ? 4 : 2)}${s.unidade === "R$" ? "" : ` ${s.unidade}`}` : <span className="text-apagado" title={r.mensagem}>indisponível</span>}
                    </td>
                    <td className="py-1.5 text-right font-mono text-[11px] text-apagado">
                      {/* a série diária da meta Selic já traz datas até a próxima reunião */}
                      {r.dados ? (r.dados.data > hoje ? "vigente" : data(r.dados.data)) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Painel>
        <Painel titulo="Brasil · expectativas de mercado" acao={<Selo tipo="analista" texto="Expectativa (Focus)" />} rodape="Mediana do Boletim Focus (Banco Central) · data do boletim na linha">
          <EstadoDados r={expectativas} />
          {expectativas.dados.length ? (
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-filete text-[10px] uppercase tracking-wider text-apagado">
                  <th className="py-1.5 text-left font-medium">Indicador</th>
                  <th className="py-1.5 text-right font-medium">Ano</th>
                  <th className="py-1.5 text-right font-medium">Mediana</th>
                  <th className="py-1.5 text-right font-medium">Boletim</th>
                </tr>
              </thead>
              <tbody>
                {expectativas.dados
                  .sort((a, b) => a.indicador.localeCompare(b.indicador) || a.ano.localeCompare(b.ano))
                  .map((e) => (
                    <tr key={`${e.indicador}${e.ano}`} className="border-b border-filete/60 last:border-0">
                      <td className="py-1.5">{e.indicador}</td>
                      <td className="py-1.5 text-right font-mono">{e.ano}</td>
                      <td className="py-1.5 text-right font-mono">{num(e.mediana, 2)}{e.indicador === "Câmbio" ? "" : "%"}</td>
                      <td className="py-1.5 text-right font-mono text-[11px] text-apagado">{data(e.data)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          ) : null}
        </Painel>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {historicos.map((h) => (
          <Painel key={h.titulo} titulo={h.titulo} acao={<Selo tipo="fato" />} rodape={`Fonte: ${h.r.fonte}${h.pontos.length ? ` · até ${data(new Date(h.pontos.at(-1)!.t).toISOString().slice(0, 10))}` : ""}`}>
            <EstadoDados r={h.r} vazio="Série sem leituras no período." />
            {h.pontos.length > 1 ? (
              <Grafico pontos={h.pontos} eixoX={h.eixo} fuso="UTC" rotulosX={4} casas={h.sufixo ? 2 : 4} sufixo={h.sufixo} degrau={h.degrau} cor="neutro" altura={150} titulo={h.titulo} />
            ) : null}
          </Painel>
        ))}
        <Painel titulo="Treasury 10 anos · 1 ano" acao={<Selo tipo="fato" texto="Cotação" />} rodape={`Fonte: ${treasury.fonte} · rendimento em % ao ano`}>
          <EstadoDados r={treasury} vazio="Sem negócios no período." />
          {treasury.dados ? <Grafico pontos={treasury.dados.pontos} eixoX="mes" fuso={treasury.dados.fuso} rotulosX={4} casas={2} sufixo="%" cor="neutro" altura={150} titulo="Treasury 10 anos" /> : null}
        </Painel>
      </div>
      <Painel titulo="Exterior · juros, dólar e petróleo" className="mt-3" acao={<Selo tipo="fato" texto="Cotação" />} rodape="Fonte: Yahoo Finance · juros dos Treasuries em % ao ano">
        <TabelaIndicadores linhas={exterior} />
      </Painel>
    </>
  );
}
