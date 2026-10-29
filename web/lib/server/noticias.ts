import "server-only";

import { editoriaPorAssunto, eNoticiaDeEmpresa, foraDePauta, semAcento, temRelevanciaFinanceira } from "@/lib/regrasEditoriais";
import { resultado, type Resultado } from "@/lib/tipos";

/** Mesmos feeds de data/news.py (Google News Brasil/EUA + diretos). */
const FEEDS: Array<{ url: string; regiao: "BR" | "INT"; veiculo?: string }> = [
  { url: "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=pt-BR&gl=BR&ceid=BR:pt-419", regiao: "BR" },
  ...["Ibovespa", "Copom", "Selic", "dólar", "IPCA", "fiscal"].map((t) => ({
    url: `https://news.google.com/rss/search?q=${encodeURIComponent(`${t} when:1d`)}&hl=pt-BR&gl=BR&ceid=BR:pt-419`,
    regiao: "BR" as const,
  })),
  { url: "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en", regiao: "INT" },
  { url: "https://www.cnbc.com/id/10001147/device/rss/rss.html", regiao: "INT", veiculo: "CNBC" },
  { url: "http://feeds.marketwatch.com/marketwatch/topstories/", regiao: "INT", veiculo: "MarketWatch" },
];

export type Noticia = {
  titulo: string;
  link: string;
  veiculo: string;
  publicadaEm: string | null;
  regiao: "BR" | "INT";
  idioma: "pt" | "en";
  /** veículos que publicaram o mesmo título (deduplicação) */
  veiculos: string[];
  /** empresa listada/ticker no título (regra de e_noticia_de_empresa) */
  empresa: boolean;
};

const ENTIDADES: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&apos;": "'" };

function texto(bloco: string, tag: string): string {
  const m = bloco.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i"));
  if (!m) return "";
  return m[1]
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&(amp|lt|gt|quot|#39|apos);/g, (e) => ENTIDADES[e] || e)
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/<[^>]+>/g, "")
    .trim();
}

export { foraDePauta, editoriaPorAssunto as regiaoPorAssunto } from "@/lib/regrasEditoriais";

function chaveTitulo(titulo: string) {
  return semAcento(titulo).toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim().slice(0, 90);
}

export function interpretarRss(xml: string, regiao: "BR" | "INT", veiculoPadrao?: string): Noticia[] {
  const itens = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  return itens.flatMap((bloco) => {
    let titulo = texto(bloco, "title");
    const link = texto(bloco, "link");
    let veiculo = texto(bloco, "source") || veiculoPadrao || "";
    // Google News: "Manchete - Veículo"
    if (!veiculoPadrao && titulo.includes(" - ")) {
      const i = titulo.lastIndexOf(" - ");
      veiculo = veiculo || titulo.slice(i + 3);
      titulo = titulo.slice(0, i);
    }
    if (!titulo || !/^https?:\/\//.test(link)) return [];
    const data = texto(bloco, "pubDate");
    const publicadaEm = data && !Number.isNaN(Date.parse(data)) ? new Date(data).toISOString() : null;
    return [{
      titulo, link, veiculo: veiculo || "—", publicadaEm,
      regiao: editoriaPorAssunto(titulo, regiao), empresa: eNoticiaDeEmpresa(titulo), idioma: regiao === "INT" ? "en" : "pt", veiculos: [veiculo || "—"],
    } satisfies Noticia];
  });
}

/** Feed consolidado: últimas 36h, sem fora de pauta, deduplicado por
 * título (fica o mais recente; os veículos repetidos são somados). */
export async function obterNoticias(revalidar = 900): Promise<Resultado<Noticia[]>> {
  const fonte = "Google News, CNBC e MarketWatch (RSS)";
  const respostas = await Promise.allSettled(
    FEEDS.map(async (f) => {
      const r = await fetch(f.url, { headers: { "User-Agent": "Mozilla/5.0 (compatible; PregaoTerminal/1.0)" }, next: { revalidate: revalidar } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return interpretarRss(await r.text(), f.regiao, f.veiculo);
    }),
  );
  const falhas = respostas.filter((r) => r.status === "rejected").length;
  if (falhas === FEEDS.length) return resultado("erro", [], fonte, "Nenhum feed de notícias respondeu.");
  const limite = Date.now() - 36 * 3600 * 1000;
  const porChave = new Map<string, Noticia>();
  for (const r of respostas) {
    if (r.status !== "fulfilled") continue;
    for (const n of r.value) {
      // mesmas regras do PDF: fora de pauta/opinião e piso de relevância
      if (foraDePauta(n.titulo) || !temRelevanciaFinanceira(n.titulo)) continue;
      if (n.publicadaEm && Date.parse(n.publicadaEm) < limite) continue;
      const chave = chaveTitulo(n.titulo);
      const existente = porChave.get(chave);
      if (existente) {
        if (!existente.veiculos.includes(n.veiculo)) existente.veiculos.push(n.veiculo);
        continue;
      }
      porChave.set(chave, n);
    }
  }
  const lista = [...porChave.values()].sort((a, b) => (b.publicadaEm || "").localeCompare(a.publicadaEm || ""));
  const msg = falhas ? `${falhas} de ${FEEDS.length} feeds não responderam nesta leitura.` : undefined;
  return resultado(lista.length ? "ok" : "vazio", lista, fonte, msg);
}

/** Busca no Google News (mesma URL de busca do coletor) - para a página
 * de um ativo. */
export async function buscarNoticias(termo: string, revalidar = 900): Promise<Resultado<Noticia[]>> {
  const fonte = "Google News (RSS de busca)";
  try {
    const url = `https://news.google.com/rss/search?q=${encodeURIComponent(`${termo} when:7d`)}&hl=pt-BR&gl=BR&ceid=BR:pt-419`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (compatible; PregaoTerminal/1.0)" }, next: { revalidate: revalidar } });
    if (!r.ok) return resultado("erro", [], fonte, "A busca de notícias não respondeu.");
    const lista = interpretarRss(await r.text(), "BR").filter((n) => !foraDePauta(n.titulo)).slice(0, 15);
    return resultado(lista.length ? "ok" : "vazio", lista, fonte);
  } catch {
    return resultado("erro", [], fonte, "A busca de notícias não respondeu.");
  }
}
