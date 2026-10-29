/** Siglas de terminal (faixa do topo e mini-gráficos). Em arquivo
 * próprio (sem "server-only") porque FitaCotacoes.tsx é Client Component
 * (polling) e precisa importar isso em runtime no navegador -
 * lib/server/dominio/mercado.ts não pode ser importado por um Client
 * Component. Re-exportado de lá por compatibilidade (MiniGrafico.tsx). */
export const SIGLAS: Record<string, string> = {
  "^BVSP": "IBOV", "USDBRL=X": "USDBRL", "EURBRL=X": "EURBRL", "^GSPC": "SPX", "^IXIC": "CCMP", "^DJI": "INDU",
  "ES=F": "ES1", "^TNX": "UST10", "DX-Y.NYB": "DXY", "BZ=F": "CO1", "CL=F": "CL1", "GC=F": "GC1", "BTC-USD": "BTC",
};
