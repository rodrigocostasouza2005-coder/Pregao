import "server-only";

import { lerTabela } from "../supabase";

/** Estados do ciclo de vida de um incidente (Coordenador/Backoffice,
 * 2026-10-29). ABERTO/RESOLVIDO são os únicos que
 * data/market_researcher.py:registrar_achados_atuais() escreve (job
 * agendado, ver jobs/coordenador.py); os 3 do meio são triagem MANUAL
 * feita aqui na web (ver definirEstadoIncidente) - o job agendado nunca
 * os sobrescreve (ver o patch em registrar_achados_atuais). */
export type EstadoIncidente = "ABERTO" | "INVESTIGANDO" | "AGUARDANDO_INTERVENCAO" | "RESOLVIDO" | "INCONCLUSIVO";

const ROTULO_ESTADO: Record<EstadoIncidente, string> = {
  ABERTO: "Novo",
  INVESTIGANDO: "Investigando",
  AGUARDANDO_INTERVENCAO: "Aguardando intervenção",
  RESOLVIDO: "Resolvido",
  INCONCLUSIVO: "Inconclusivo",
};

/** Transições permitidas por estado atual - nunca "resolver" direto um
 * achado que ninguém investigou ainda não é proibido (pode ser um falso
 * positivo óbvio), mas reabrir um RESOLVIDO só acontece automaticamente
 * (job), nunca por clique manual aqui. */
const TRANSICOES_PERMITIDAS: Record<EstadoIncidente, EstadoIncidente[]> = {
  ABERTO: ["INVESTIGANDO", "AGUARDANDO_INTERVENCAO", "RESOLVIDO", "INCONCLUSIVO"],
  INVESTIGANDO: ["AGUARDANDO_INTERVENCAO", "RESOLVIDO", "INCONCLUSIVO", "ABERTO"],
  AGUARDANDO_INTERVENCAO: ["INVESTIGANDO", "RESOLVIDO", "INCONCLUSIVO", "ABERTO"],
  RESOLVIDO: ["ABERTO"],
  INCONCLUSIVO: ["INVESTIGANDO", "ABERTO"],
};

export type Achado = {
  id: number; chave: string; coletor: string; categoria: string; tipo: string; descricao: string | null;
  severidade: "CRITICO" | "ATENCAO"; status: EstadoIncidente; primeira_ocorrencia_em: string; ultima_ocorrencia_em: string;
  ocorrencias: number; causa_raiz: string | null; commit_correcao: string | null; resolvido_em: string | null;
};

export function lerAchados(limite = 200) {
  return lerTabela<Achado>("market_researcher_achados", {
    select: "id,chave,coletor,categoria,tipo,descricao,severidade,status,primeira_ocorrencia_em,ultima_ocorrencia_em,ocorrencias,causa_raiz,commit_correcao,resolvido_em",
    ordem: "ultima_ocorrencia_em.desc",
    limite,
  });
}

export type Execucao = {
  id: number; tipo: "backoffice" | "sintese"; status: "EM_ANDAMENTO" | "OK" | "PARCIAL" | "ERRO";
  iniciado_em: string; concluido_em: string | null; duracao_ms: number | null; resumo: string | null; erro: string | null;
};

/** Última execução de cada tipo (backoffice/síntese) - "status dos
 * especialistas" da Fase 4 (última execução, estado, cobertura). */
export async function ultimasExecucoes() {
  const r = await lerTabela<Execucao>("coordenador_execucoes", {
    select: "id,tipo,status,iniciado_em,concluido_em,duracao_ms,resumo,erro",
    ordem: "iniciado_em.desc",
    limite: 20,
  });
  const porTipo = new Map<string, Execucao>();
  for (const e of r.dados) if (!porTipo.has(e.tipo)) porTipo.set(e.tipo, e);
  return { r, ultimas: [...porTipo.values()] };
}

// --- Causa provável e próxima ação (hipóteses deterministicas) -----------
// Port de data/saude_dados.py:ESTADOS (mesmos 9 códigos) - nunca uma
// causa CONFIRMADA (isso é `causa_raiz`, preenchido manualmente após
// investigação real): aqui é só a leitura padrão de cada código de
// estado, sempre apresentada como hipótese na UI (ver Selo "inferencia").
const CAUSA_PROVAVEL: Record<string, string> = {
  FALHA_EXECUCAO: "Execução do coletor falhou (ver erro da última tentativa).",
  FALHA_PERSISTENCIA: "Coleta funcionou, mas a gravação no banco falhou.",
  FONTE_INDISPONIVEL: "Fonte externa bloqueando ou instável (timeout/403/WAF).",
  DADOS_DESATUALIZADOS: "Coletor não executa com sucesso há mais tempo que o esperado.",
  PARCIAL: "Execução parcial — algumas fontes ou itens não confirmados.",
  NUNCA_EXECUTADO: "Nenhuma evidência de execução ainda.",
  NAO_COMPROVADO: "Nenhum sucesso confirmado ainda.",
};

const PROXIMA_ACAO: Record<string, string> = {
  FALHA_EXECUCAO: "Ver log da última tentativa; se persistir, checar se a fonte mudou estrutura/bloqueio.",
  FALHA_PERSISTENCIA: "Verificar credenciais/RLS da tabela de destino no Supabase.",
  FONTE_INDISPONIVEL: "Aguardar e reconfirmar; se persistir por dias, considerar contato com a fonte.",
  DADOS_DESATUALIZADOS: "Confirmar se o cron (GitHub Actions) ou coletor_local.py está rodando.",
  PARCIAL: "Ver detalhe do erro — pode ser degradação parcial aceitável, não necessariamente falha.",
  NUNCA_EXECUTADO: "Rodar o coletor manualmente uma vez para confirmar.",
  NAO_COMPROVADO: "Rodar o coletor manualmente uma vez para confirmar.",
};

/** Port de data/market_researcher.py:_PRIORIDADE_ESTADO (mesma ordem de
 * severidade) + _CATEGORIAS_CRITICAS - usado só pra ORDENAR a fila, nunca
 * recalcula o estado em si (esse continua vindo do Python). */
const PRIORIDADE_ESTADO: Record<string, number> = {
  FALHA_PERSISTENCIA: 0, FALHA_EXECUCAO: 1, FONTE_INDISPONIVEL: 2, DADOS_DESATUALIZADOS: 3,
  NUNCA_EXECUTADO: 4, NAO_COMPROVADO: 5, PARCIAL: 6,
};
const CATEGORIAS_CRITICAS = new Set(["Noticias", "Cotacoes", "Macro", "CVM", "Radar", "Morning Call"]);

export type IncidenteEnriquecido = Achado & {
  rotuloEstado: string; causaProvavel: string | null; proximaAcao: string | null; critico: boolean; rankPrioridade: number;
};

/** Fila de incidentes priorizada (Fase 3): crítico primeiro, depois
 * código de estado mais grave, depois mais recorrente. Nunca inventa um
 * incidente sem achado real persistido - só ordena/enriquece o que
 * market_researcher_achados já tem. */
export function filaDeIncidentes(achados: Achado[]): IncidenteEnriquecido[] {
  const enriquecidos = achados.map((a) => {
    const critico = a.severidade === "CRITICO" || CATEGORIAS_CRITICAS.has(a.categoria);
    const rankEstado = PRIORIDADE_ESTADO[a.tipo] ?? 9;
    return {
      ...a, rotuloEstado: ROTULO_ESTADO[a.status] ?? a.status,
      causaProvavel: CAUSA_PROVAVEL[a.tipo] ?? null, proximaAcao: PROXIMA_ACAO[a.tipo] ?? null,
      critico, rankPrioridade: (critico ? 0 : 100) + rankEstado,
    };
  });
  return enriquecidos.sort((x, y) =>
    x.rankPrioridade - y.rankPrioridade || y.ocorrencias - x.ocorrencias || y.ultima_ocorrencia_em.localeCompare(x.ultima_ocorrencia_em));
}

export function transicoesPermitidas(estadoAtual: EstadoIncidente): EstadoIncidente[] {
  return TRANSICOES_PERMITIDAS[estadoAtual] ?? [];
}

export { ROTULO_ESTADO };
