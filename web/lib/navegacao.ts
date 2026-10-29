export type SecaoId = "mercado" | "noticias" | "research" | "inteligencia" | "morning-call";

export type ItemNavegacao = {
  id: SecaoId;
  rotulo: string;
  sigla: string;
  descricao: string;
};

/** Seções do terminal. As mesmas áreas do Pregão em Streamlit; aqui só a
 * estrutura - os dados entram por etapas, conforme os coletores forem
 * expostos para a nova interface. */
export const NAVEGACAO: ItemNavegacao[] = [
  { id: "mercado", rotulo: "Mercado", sigla: "MKT", descricao: "Índices, câmbio, juros e commodities" },
  { id: "noticias", rotulo: "Notícias", sigla: "NWS", descricao: "Manchetes por editoria, com fonte e horário" },
  { id: "research", rotulo: "Research", sigla: "RSH", descricao: "Carteiras e relatórios das casas" },
  { id: "inteligencia", rotulo: "Inteligência", sigla: "INT", descricao: "Radar setorial e sinais" },
  { id: "morning-call", rotulo: "Morning Call", sigla: "MC", descricao: "Edição diária em PDF" },
];
