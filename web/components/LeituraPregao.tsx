import { formatarNumero } from "@/lib/format";
import type { PapelPanorama } from "@/lib/mercado";

type Concentracao = { setor: string; qtd: number; total: number } | null;

export function LeituraPregao({
  concentracao,
  maisNegociado,
}: {
  concentracao: Concentracao;
  maisNegociado: PapelPanorama | null;
}) {
  const chips: { tipo: "DADO" | "NOTÍCIA" | "AGENDA"; texto: React.ReactNode }[] = [];
  if (concentracao) {
    chips.push({
      tipo: "DADO",
      texto: (
        <>
          <b>{concentracao.setor}</b> concentra {concentracao.qtd} dos {concentracao.total} maiores movimentos do dia
        </>
      ),
    });
  }
  if (maisNegociado) {
    chips.push({
      tipo: "DADO",
      texto: (
        <>
          Maior volume financeiro do dia: <b>{maisNegociado.ticker}</b> (R${" "}
          {formatarNumero(maisNegociado.volumeFinanceiro / 1_000_000, 0)} mi)
        </>
      ),
    });
  }

  const corTipo: Record<string, string> = {
    DADO: "text-[#7fb8ff]",
    NOTÍCIA: "text-accent",
    AGENDA: "text-text-dim",
  };

  return (
    <div className="border border-border bg-bg border-l-2 border-l-accent">
      <div className="px-3 py-2 border-b border-border">
        <span className="text-[0.68rem] tracking-wide font-bold text-accent">LEITURA DO PREGÃO</span>
      </div>
      <div className="px-3 py-2.5">
        <div className="text-[0.62rem] text-text-faint mb-2">
          síntese por IA ainda não integrada nesta versão (pendente — ver data/sintese_mercado.py no app
          Python) - fatos abaixo vêm direto dos dados, sem IA
        </div>
        {chips.length === 0 ? (
          <div className="text-text-faint text-[0.76rem]">Sem fatos com evidência suficiente nesta rodada.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {chips.map((c, i) => (
              <span key={i} className="text-[0.68rem] border border-border rounded-[2px] px-2 py-1 inline-flex items-center gap-1.5">
                <em className={`not-italic font-bold text-[0.56rem] tracking-wide ${corTipo[c.tipo]}`}>{c.tipo}</em>
                <span>{c.texto}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
