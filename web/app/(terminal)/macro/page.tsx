import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { Painel } from "@/components/Painel";
import { Selo } from "@/components/Selo";
import { TabelaIndicadores } from "@/components/TabelaIndicadores";
import { data, num } from "@/lib/formatos";
import { focus, SERIES_SGS, ultimaSgs } from "@/lib/server/bcb";
import { lerIndicadores, type Indicador } from "@/lib/server/dominio/mercado";

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
  const chaves = Object.keys(SERIES_SGS) as Array<keyof typeof SERIES_SGS>;
  const [sgs, expectativas, exterior] = await Promise.all([
    Promise.all(chaves.map((k) => ultimaSgs(SERIES_SGS[k].codigo))),
    focus(["IPCA", "Selic", "PIB Total", "Câmbio"], [ano, ano + 1]),
    lerIndicadores(EXTERIOR),
  ]);
  return (
    <>
      <CabecalhoPagina titulo="Macro" descricao="Dados oficiais divulgados, expectativas de mercado e referências internacionais" />
      <div className="grid gap-3 xl:grid-cols-2">
        <Painel titulo="Brasil · dado divulgado" acao={<Selo tipo="fato" />} rodape="Fonte: Banco Central do Brasil (SGS)">
          <table className="w-full text-[12.5px]">
            <tbody>
              {chaves.map((k, i) => {
                const s = SERIES_SGS[k];
                const r = sgs[i];
                return (
                  <tr key={k} className="border-b border-filete/60 last:border-0">
                    <td className="py-1.5">{s.nome} <span className="ml-1 font-mono text-[10px] text-apagado">SGS {s.codigo}</span></td>
                    <td className="py-1.5 text-right font-mono">
                      {r.dados ? `${num(r.dados.valor, s.unidade === "R$" ? 4 : 2)}${s.unidade === "R$" ? "" : ` ${s.unidade}`}` : <span className="text-apagado" title={r.mensagem}>indisponível</span>}
                    </td>
                    <td className="py-1.5 text-right font-mono text-[11px] text-apagado">{r.dados ? data(r.dados.data) : "—"}</td>
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
      <Painel titulo="Exterior · juros, dólar e petróleo" className="mt-3" acao={<Selo tipo="fato" texto="Cotação" />} rodape="Fonte: Yahoo Finance · juros dos Treasuries em % ao ano">
        <TabelaIndicadores linhas={exterior} />
      </Painel>
    </>
  );
}
