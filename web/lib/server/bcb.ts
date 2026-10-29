import "server-only";

import { resultado, type Resultado } from "@/lib/tipos";

/** Mesmas séries de data/macro.py. */
export const SERIES_SGS = {
  selicMeta: { codigo: 432, nome: "Selic meta", unidade: "% a.a." },
  cdiAnualizado: { codigo: 4389, nome: "CDI anualizado", unidade: "% a.a." },
  ipcaMensal: { codigo: 433, nome: "IPCA no mês", unidade: "%" },
  ipca12m: { codigo: 13522, nome: "IPCA em 12 meses", unidade: "%" },
  ptaxVenda: { codigo: 1, nome: "Dólar PTAX (venda)", unidade: "R$" },
} as const;

export type LeituraSgs = { valor: number; data: string };

/** Última leitura de uma série SGS (endpoint .../dados/ultimos/N). */
export async function ultimaSgs(codigo: number, revalidar = 3600): Promise<Resultado<LeituraSgs | null>> {
  const fonte = `Banco Central (SGS ${codigo})`;
  try {
    const resp = await fetch(`https://api.bcb.gov.br/dados/serie/bcdata.sgs.${codigo}/dados/ultimos/1?formato=json`, {
      next: { revalidate: revalidar },
    });
    if (!resp.ok) return resultado("erro", null, fonte, "A fonte oficial não respondeu.");
    const corpo = await resp.json().catch(() => null);
    const linha = Array.isArray(corpo) ? corpo[0] : null;
    const valor = linha ? Number(String(linha.valor).replace(",", ".")) : NaN;
    if (!linha || !Number.isFinite(valor)) return resultado("erro", null, fonte, "A fonte oficial não respondeu.");
    const [d, m, a] = String(linha.data).split("/");
    return resultado("ok", { valor, data: `${a}-${m}-${d}` }, fonte);
  } catch {
    return resultado("erro", null, fonte, "A fonte oficial não respondeu.");
  }
}

export type ExpectativaFocus = { indicador: string; ano: string; mediana: number; data: string; respondentes: number | null };

/** Mediana do Boletim Focus (Olinda/Expectativas) por indicador, para o
 * ano corrente e o seguinte - o boletim mais recente de cada ano. */
export async function focus(indicadores: string[], anos: number[], revalidar = 3600): Promise<Resultado<ExpectativaFocus[]>> {
  const fonte = "Banco Central (Boletim Focus)";
  const filtroInd = indicadores.map((i) => `Indicador eq '${i}'`).join(" or ");
  const filtroAno = anos.map((a) => `DataReferencia eq '${a}'`).join(" or ");
  const params = [
    `$filter=${encodeURIComponent(`(${filtroInd}) and (${filtroAno}) and baseCalculo eq 0`)}`,
    "$orderby=Data%20desc",
    "$top=200",
    "$format=json",
    "$select=Indicador,Data,DataReferencia,Mediana,numeroRespondentes",
  ].join("&");
  try {
    const resp = await fetch(
      `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?${params}`,
      { next: { revalidate: revalidar } },
    );
    if (!resp.ok) return resultado("erro", [], fonte, "O Boletim Focus não respondeu.");
    const corpo = (await resp.json()) as { value?: Array<Record<string, string | number>> };
    const vistos = new Set<string>();
    const saida: ExpectativaFocus[] = [];
    for (const v of corpo.value || []) {
      const chave = `${v.Indicador}|${v.DataReferencia}`;
      if (vistos.has(chave)) continue;
      vistos.add(chave);
      saida.push({
        indicador: String(v.Indicador),
        ano: String(v.DataReferencia),
        mediana: Number(v.Mediana),
        data: String(v.Data),
        respondentes: v.numeroRespondentes == null ? null : Number(v.numeroRespondentes),
      });
    }
    return resultado(saida.length ? "ok" : "vazio", saida, fonte);
  } catch {
    return resultado("erro", [], fonte, "O Boletim Focus não respondeu.");
  }
}
