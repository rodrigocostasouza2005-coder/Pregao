export type ItemNavegacao = { rota: string; rotulo: string; sigla: string; descricao: string; admin?: boolean };

/** As áreas do terminal - mesmas do Pregão em Streamlit (ui/navegacao.py),
 * com Visão Geral como entrada. */
export const NAVEGACAO: ItemNavegacao[] = [
  { rota: "/", rotulo: "Visão Geral", sigla: "VG", descricao: "Síntese, alertas e atalhos" },
  { rota: "/mercado", rotulo: "Mercado", sigla: "MKT", descricao: "Índices, câmbio, altas e baixas, setores" },
  { rota: "/macro", rotulo: "Macro", sigla: "MAC", descricao: "Juros, inflação, câmbio e expectativas" },
  { rota: "/research", rotulo: "Research", sigla: "RSH", descricao: "Casas de análise, recomendações e teses" },
  { rota: "/noticias", rotulo: "Notícias", sigla: "NWS", descricao: "Brasil e internacional, com fonte e horário" },
  { rota: "/cvm", rotulo: "CVM", sigla: "CVM", descricao: "Fatos relevantes e comunicados" },
  { rota: "/agenda", rotulo: "Agenda", sigla: "AGD", descricao: "Resultados e eventos por data" },
  { rota: "/morning-call", rotulo: "Morning Call", sigla: "MC", descricao: "Edições enviadas" },
  { rota: "/inteligencia", rotulo: "Inteligência", sigla: "INT", descricao: "O que mudou, comitê e alertas" },
  { rota: "/configuracoes", rotulo: "Configurações", sigla: "CFG", descricao: "Status dos coletores e conta" },
];
