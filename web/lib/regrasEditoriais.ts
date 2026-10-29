import regras from "@/contratos/regras_editoriais.json";

/** Regras editoriais do Morning Call (data/morning_call_editorial.py),
 * aplicadas a partir do contrato exportado pelo Python - mesma semântica
 * de _tem_marcador, editoria_por_assunto, e_opiniao, _fora_de_pauta,
 * e_noticia_de_empresa e tem_relevancia_financeira. */
type Rx = { padrao: string; flags: string };
const R = regras as unknown as {
  marcadores_exterior: string[]; marcadores_brasil: string[]; termos_opiniao: string[]; termos_financeiros: string[];
  termos_impacto_mercado: string[]; servico_financas_pessoais: string[]; termos_fora_de_pauta: string[]; nomes_empresas: string[];
  regex: Record<string, Rx>;
};

const rx = (nome: string, extra = "") => new RegExp(R.regex[nome].padrao, R.regex[nome].flags + extra);
const ROTULO_OPINIAO = rx("rotulo_opiniao");
const CARTA_DE_LEITOR = rx("carta_de_leitor");
const CARTA_COM_CITACAO = rx("carta_com_citacao");
const FORMATO_SERVICO = rx("formato_servico");
const SEM_SENTIDO_ECONOMICO = rx("sem_sentido_economico", "g");
const INICIO_RESUMO_DE_PREGAO = rx("inicio_resumo_de_pregao");
const TICKER_NO_TITULO = rx("ticker_no_titulo");

const escapar = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/** `(?<![a-z0-9])termo(?![a-z0-9])` - igual a _tem_marcador do Python. */
const marcador = (termos: string[]) => new RegExp(`(?<![a-z0-9])(?:${termos.map(escapar).join("|")})(?![a-z0-9])`);
const EXTERIOR = marcador(R.marcadores_exterior);
const BRASIL = marcador(R.marcadores_brasil);
const OPINIAO = marcador(R.termos_opiniao);
const FINANCEIROS = marcador(R.termos_financeiros);
const IMPACTO = marcador(R.termos_impacto_mercado);
const FORA_DE_PAUTA = new RegExp(`(?<![a-z])(?:${R.termos_fora_de_pauta.map(escapar).join("|")})(?![a-z])`);
const EMPRESAS = R.nomes_empresas.map(
  (n) => new RegExp(`(?<![\\p{L}\\p{N}_-])${escapar(n)}(?![\\p{L}\\p{N}_-])(?! a pena)(?! [a-zà-ú]+(?:ar|er|ir)\\b)`, "u"),
);

export const semAcento = (s: string) => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "");
const normal = (s: string) => semAcento(s).toLowerCase();

export function editoriaPorAssunto(titulo: string, regiaoColeta: "BR" | "INT"): "BR" | "INT" {
  const t = normal(titulo);
  const ext = EXTERIOR.test(t);
  const br = BRASIL.test(t) || TICKER_NO_TITULO.test(titulo);
  if (ext && !br) return "INT";
  if (br && !ext && regiaoColeta === "INT") return "BR";
  return regiaoColeta;
}

export function eOpiniao(titulo: string) {
  const t = normal(titulo);
  return ROTULO_OPINIAO.test(t) || OPINIAO.test(t);
}

export function foraDePauta(titulo: string) {
  const t = normal(titulo);
  const limpo = (titulo || "").trim();
  if (CARTA_DE_LEITOR.test(limpo) || CARTA_COM_CITACAO.test(limpo)) return true;
  if (eOpiniao(titulo)) return true;
  if (R.servico_financas_pessoais.some((s) => t.includes(s))) return true;
  return FORA_DE_PAUTA.test(t);
}

export function eNoticiaDeEmpresa(titulo: string) {
  if (INICIO_RESUMO_DE_PREGAO.test(titulo)) return false;
  if (TICKER_NO_TITULO.test(titulo)) return true;
  return EMPRESAS.some((r) => r.test(titulo));
}

export function temRelevanciaFinanceira(titulo: string) {
  const t = normal(titulo).replace(SEM_SENTIDO_ECONOMICO, " ").trim();
  const empresa = TICKER_NO_TITULO.test(titulo) || eNoticiaDeEmpresa(titulo);
  if (FORMATO_SERVICO.test(t)) return empresa || IMPACTO.test(t);
  return empresa || t.includes("%") || FINANCEIROS.test(t);
}
