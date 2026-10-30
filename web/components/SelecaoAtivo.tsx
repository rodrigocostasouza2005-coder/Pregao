"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type SelecaoAtivo = { simbolo: string; selecionar: (simbolo: string) => void };

const Contexto = createContext<SelecaoAtivo | null>(null);

/** Contexto do "ativo selecionado" de UMA tela (Visão Geral ou Mercado):
 * clicar num ticker em qualquer painel (ranking, setor, watchlist, fita)
 * atualiza o gráfico principal da própria tela sem navegar (brief:
 * "seleção de um ativo deve abrir ou atualizar seu contexto no
 * terminal"). Cada página instancia o seu próprio Provider - nunca é
 * global (a página de Ativo, por ex., não precisa disto). */
export function SelecaoAtivoProvider({ padrao, children }: { padrao: string; children: ReactNode }) {
  const [simbolo, selecionar] = useState(padrao);
  const valor = useMemo(() => ({ simbolo, selecionar }), [simbolo]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

/** Usar dentro de um SelecaoAtivoProvider (ex.: GraficoPrincipal). */
export function useAtivoSelecionado(): SelecaoAtivo {
  const v = useContext(Contexto);
  if (!v) throw new Error("useAtivoSelecionado precisa de um SelecaoAtivoProvider");
  return v;
}

/** Usar em componentes globais (ex.: FitaCotacoes, renderizado no layout
 * fora de qualquer Provider) que devem atualizar o contexto QUANDO existir
 * um, e cair para navegação normal (link pra /ativo/:ticker) quando não. */
export function useAtivoSelecionadoOpcional(): SelecaoAtivo | null {
  return useContext(Contexto);
}

/** Botão "chip" clicável que seleciona um ativo no contexto da tela -
 * usado em rankings, setores e watchlist pra trocar o gráfico principal
 * sem navegar. Sempre dentro de um SelecaoAtivoProvider. */
export function BotaoSelecionarAtivo({ simbolo, children, className = "" }: { simbolo: string; children: ReactNode; className?: string }) {
  const { selecionar } = useAtivoSelecionado();
  return (
    <button type="button" onClick={() => selecionar(simbolo)} className={className}>
      {children}
    </button>
  );
}
