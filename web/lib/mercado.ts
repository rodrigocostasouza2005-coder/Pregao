import { IBOVESPA_SETORES, UNIVERSO_IBOVESPA } from "./setores";
import { obterCotacao, obterCotacoesLote, obterHistorico, type Cotacao } from "./yahoo";

export type ItemIndicador = {
  rotulo: string;
  preco: number | null;
  variacaoPct: number | null;
  casasDecimais: number;
};

/** Mesmos 7 indicadores essenciais do app Python original (IBOVESPA/
 * DÓLAR/DI/S&P 500/NASDAQ/PETR4/VALE3) - dados reais, None quando a
 * fonte falha (nunca inventado). */
export async function obterIndicadores(): Promise<ItemIndicador[]> {
  const [ibov, dolar, petr4, vale3, sp500, nasdaq, cdi] = await Promise.all([
    obterCotacao("IBOVESPA", "^BVSP"),
    obterCotacao("DÓLAR", "USDBRL=X"),
    obterCotacao("PETR4", "PETR4.SA"),
    obterCotacao("VALE3", "VALE3.SA"),
    obterCotacao("S&P 500", "^GSPC"),
    obterCotacao("NASDAQ", "^IXIC"),
    obterCdiAnualizado(),
  ]);
  return [
    { rotulo: "IBOVESPA", preco: ibov?.preco ?? null, variacaoPct: ibov?.variacaoPct ?? null, casasDecimais: 0 },
    { rotulo: "DÓLAR", preco: dolar?.preco ?? null, variacaoPct: dolar?.variacaoPct ?? null, casasDecimais: 2 },
    { rotulo: "DI (CDI ANUAL.)", preco: cdi, variacaoPct: cdi != null ? 0 : null, casasDecimais: 2 },
    { rotulo: "S&P 500", preco: sp500?.preco ?? null, variacaoPct: sp500?.variacaoPct ?? null, casasDecimais: 0 },
    { rotulo: "NASDAQ", preco: nasdaq?.preco ?? null, variacaoPct: nasdaq?.variacaoPct ?? null, casasDecimais: 0 },
    { rotulo: "PETR4", preco: petr4?.preco ?? null, variacaoPct: petr4?.variacaoPct ?? null, casasDecimais: 2 },
    { rotulo: "VALE3", preco: vale3?.preco ?? null, variacaoPct: vale3?.variacaoPct ?? null, casasDecimais: 2 },
  ];
}

/** CDI anualizado (% a.a.) - Banco Central, série SGS 4389 (mesma usada
 * pelo app Python, data/macro.py). Só o valor mais recente - a UI aqui
 * não precisa da variação dia-a-dia nesta 1a versão (pendência: comparar
 * com a leitura anterior como o Python faz). */
async function obterCdiAnualizado(): Promise<number | null> {
  try {
    const resp = await fetch(
      "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json",
      { cache: "no-store", headers: { Accept: "application/json" } }
    );
    if (!resp.ok) return null;
    const dados = (await resp.json()) as { valor: string }[];
    const valor = dados?.[0]?.valor;
    if (!valor) return null;
    const num = parseFloat(valor.replace(",", "."));
    return Number.isFinite(num) ? num : null;
  } catch {
    return null;
  }
}

export async function obterHistoricoIbovespa(periodo: string) {
  return obterHistorico("^BVSP", periodo);
}

export type PapelPanorama = Cotacao & { setor: string; volumeFinanceiro: number };

/** Panorama completo do universo Ibovespa (mesmos 84 tickers curados do
 * app Python, config.IBOVESPA_SETORES) - papel sem dado válido
 * simplesmente fica de fora (ver lib/yahoo.ts), nunca número inventado.
 * Base pra altas/baixas, mapa setorial e desempenho (mais negociados). */
export async function obterPanoramaIbovespa(): Promise<PapelPanorama[]> {
  const pedidos = UNIVERSO_IBOVESPA.map((ticker) => ({ ticker, symbolYahoo: `${ticker}.SA` }));
  const cotacoes = await obterCotacoesLote(pedidos);
  const papeis: PapelPanorama[] = [];
  for (const ticker of UNIVERSO_IBOVESPA) {
    const c = cotacoes.get(ticker);
    if (!c || c.volume == null) continue;
    papeis.push({
      ...c,
      setor: IBOVESPA_SETORES[ticker] ?? "Outros",
      volumeFinanceiro: c.preco * c.volume,
    });
  }
  return papeis;
}

export function calcularAltasBaixas(papeis: PapelPanorama[], n = 5) {
  const ordenado = [...papeis].sort((a, b) => b.variacaoPct - a.variacaoPct);
  const altas = ordenado.filter((p) => p.variacaoPct > 0).slice(0, n);
  const baixas = ordenado
    .filter((p) => p.variacaoPct < 0)
    .sort((a, b) => a.variacaoPct - b.variacaoPct)
    .slice(0, n);
  return { altas, baixas };
}

export type DesempenhoSetor = { setor: string; variacaoMediaPct: number; nPapeis: number };

export function calcularDesempenhoSetorial(papeis: PapelPanorama[]): DesempenhoSetor[] {
  const porSetor = new Map<string, number[]>();
  for (const p of papeis) {
    const lista = porSetor.get(p.setor) ?? [];
    lista.push(p.variacaoPct);
    porSetor.set(p.setor, lista);
  }
  const resultado: DesempenhoSetor[] = [];
  for (const [setor, valores] of porSetor) {
    const media = valores.reduce((a, b) => a + b, 0) / valores.length;
    resultado.push({ setor, variacaoMediaPct: media, nPapeis: valores.length });
  }
  return resultado.sort((a, b) => b.variacaoMediaPct - a.variacaoMediaPct);
}

export function calcularMaisNegociados(papeis: PapelPanorama[], n = 6): PapelPanorama[] {
  return [...papeis].sort((a, b) => b.volumeFinanceiro - a.volumeFinanceiro).slice(0, n);
}

export function concentracaoSetorial(papeis: PapelPanorama[], amostra: PapelPanorama[]) {
  if (amostra.length === 0) return null;
  const contagem = new Map<string, number>();
  for (const p of amostra) {
    contagem.set(p.setor, (contagem.get(p.setor) ?? 0) + 1);
  }
  let setorTop = "";
  let qtdTop = 0;
  for (const [setor, qtd] of contagem) {
    if (qtd > qtdTop) {
      setorTop = setor;
      qtdTop = qtd;
    }
  }
  if (qtdTop < 3) return null;
  return { setor: setorTop, qtd: qtdTop, total: amostra.length };
}
