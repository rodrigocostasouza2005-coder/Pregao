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

/** Plano B oficial da meta Selic (mesmo de data/macro.py:
 * obter_selic_meta_copom): histórico de taxas do Copom no bcb.gov.br -
 * exatamente UMA meta vigente, senão indisponível. */
export async function selicPeloCopom(revalidar = 3600): Promise<Resultado<(LeituraSgs & { reuniao: number | null }) | null>> {
  const fonte = "Banco Central (histórico do Copom)";
  try {
    const r = await fetch("https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros", {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; PregaoTerminal/1.0)" }, next: { revalidate: revalidar },
    });
    if (!r.ok) return resultado("erro", null, fonte, "O histórico do Copom não respondeu.");
    const registros = ((await r.json()) as { conteudo?: Array<Record<string, string | number | null>> }).conteudo || [];
    const agora = Date.now();
    const vigentes = registros.filter((x) => {
      const inicio = Date.parse(String(x.DataInicioVigencia));
      const valor = Number(x.MetaSelic);
      return x.DataFimVigencia == null && Number.isFinite(inicio) && inicio <= agora && valor > 0 && valor < 100;
    });
    if (vigentes.length !== 1) return resultado("erro", null, fonte, "O histórico do Copom não trouxe uma única meta vigente.");
    const v = vigentes[0];
    return resultado("ok", { valor: Number(v.MetaSelic), data: String(v.DataInicioVigencia).slice(0, 10), reuniao: v.NumeroReuniaoCopom == null ? null : Number(v.NumeroReuniaoCopom) }, fonte);
  } catch {
    return resultado("erro", null, fonte, "O histórico do Copom não respondeu.");
  }
}

/** PTAX de venda pela API oficial PTAX (Olinda) - última cotação dos
 * últimos 10 dias. Alternativa oficial quando a série SGS 1 falha. */
export async function ptaxOlinda(revalidar = 1800): Promise<Resultado<LeituraSgs | null>> {
  const fonte = "Banco Central (PTAX)";
  const fmt = (d: Date) => `${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}-${d.getUTCFullYear()}`;
  const fim = new Date();
  const inicio = new Date(Date.now() - 10 * 86400000);
  const url = `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?@dataInicial='${fmt(inicio)}'&@dataFinalCotacao='${fmt(fim)}'&$format=json&$select=cotacaoVenda,dataHoraCotacao`;
  try {
    const r = await fetch(url, { next: { revalidate: revalidar } });
    if (!r.ok) return resultado("erro", null, fonte, "A PTAX não respondeu.");
    const valores = ((await r.json()) as { value?: Array<{ cotacaoVenda: number; dataHoraCotacao: string }> }).value || [];
    const ultimo = valores.sort((a, b) => a.dataHoraCotacao.localeCompare(b.dataHoraCotacao)).at(-1);
    if (!ultimo) return resultado("vazio", null, fonte, "Sem PTAX no período.");
    return resultado("ok", { valor: ultimo.cotacaoVenda, data: ultimo.dataHoraCotacao.slice(0, 10) }, fonte);
  } catch {
    return resultado("erro", null, fonte, "A PTAX não respondeu.");
  }
}
