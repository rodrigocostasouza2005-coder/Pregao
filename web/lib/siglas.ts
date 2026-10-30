/** Siglas de terminal (faixa do topo e mini-gráficos). Em arquivo
 * próprio (sem "server-only") porque FitaCotacoes.tsx é Client Component
 * (polling) e precisa importar isso em runtime no navegador -
 * lib/server/dominio/mercado.ts não pode ser importado por um Client
 * Component. Re-exportado de lá por compatibilidade (MiniGrafico.tsx). */
export const SIGLAS: Record<string, string> = {
  "^BVSP": "IBOV", "USDBRL=X": "USDBRL", "EURBRL=X": "EURBRL", "^GSPC": "SPX", "^IXIC": "CCMP", "^DJI": "INDU",
  "ES=F": "ES1", "^TNX": "UST10", "DX-Y.NYB": "DXY", "BZ=F": "CO1", "CL=F": "CL1", "GC=F": "GC1", "BTC-USD": "BTC",
};

/** Nomes completos dos mesmos símbolos de SIGLAS (cabeçalho do gráfico
 * principal, GraficoPrincipal.tsx) - cópia client-safe de Indicador.nome
 * em lib/server/dominio/mercado.ts ("server-only"); mudar um nome ali
 * exige espelhar aqui. */
export const NOMES: Record<string, string> = {
  "^BVSP": "Ibovespa", "USDBRL=X": "Dólar (USD/BRL)", "EURBRL=X": "Euro (EUR/BRL)", "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones",
  "ES=F": "S&P 500 futuro", "^TNX": "Treasury 10 anos (%)", "DX-Y.NYB": "Índice dólar (DXY)", "BZ=F": "Petróleo Brent", "CL=F": "Petróleo WTI",
  "GC=F": "Ouro", "BTC-USD": "Bitcoin (USD)", DI: "DI (CDI anualizado)",
};
