import "server-only";

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
};

const ENTIDADES: Record<string, string> = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&apos;": "'" };

function texto(bloco: string, tag: string): string {
  const m = bloco.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i"));
  if (!m) return "";
  return m[1]
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&(amp|lt|gt|quot|#39|apos);/g, (e) => ENTIDADES[e] || e)
    .replace(/<[^>]+>/g, "")
    .trim();
}

function semAcento(s: string) {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

// Regras editoriais do Pregão (data/morning_call_editorial.py): opinião,
// colunas em 1ª pessoa e serviço/loterias ficam fora do feed.
const OPINIAO = /\b(estelionato|irresponsabilidade|vergonh|vexame|farsa|desgoverno|descalabro|hipocrisia)\b/;
const FORA_DE_PAUTA = /\b(quina|mega-sena|mega sena|lotofacil|loteria|horoscopo)\b|^(opiniao|artigo|editorial|coluna)\s*[:|]/;
const CARTA = /^["'‘’“”].{3,}?["'‘’“”]\s*:\s*(i\b|i['’]m\b|my\b|we\b)|^i['’]m \d+/i;
const MARCADOR_EXTERIOR = /\b(eua|estados unidos|fed|trump|wall street|treasury|china|europa|bce|nasdaq|s&p 500|dow jones)\b/;
const MARCADOR_BRASIL = /\b(brasil|brasileir\w*|ibovespa|b3|copom|selic|ipca|lula|haddad|petrobras|reais|brazil\w*)\b/;

export function foraDePauta(titulo: string) {
  const t = semAcento(titulo);
  return OPINIAO.test(t) || FORA_DE_PAUTA.test(t) || CARTA.test(titulo.trim());
}

/** Editoria pelo assunto do título (mesma regra do PDF): assunto do
 * exterior sem marcador do Brasil vai para INT, e vice-versa. */
export function regiaoPorAssunto(titulo: string, regiaoColeta: "BR" | "INT"): "BR" | "INT" {
  const t = semAcento(titulo);
  const ext = MARCADOR_EXTERIOR.test(t);
  const br = MARCADOR_BRASIL.test(t);
  if (ext && !br) return "INT";
  if (br && !ext) return "BR";
  return regiaoColeta;
}

function chaveTitulo(titulo: string) {
  return semAcento(titulo).replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim().slice(0, 90);
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
      regiao: regiaoPorAssunto(titulo, regiao), idioma: regiao === "INT" ? "en" : "pt", veiculos: [veiculo || "—"],
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
      if (foraDePauta(n.titulo)) continue;
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
