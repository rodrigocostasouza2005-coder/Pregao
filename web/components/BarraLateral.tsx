import { NAVEGACAO, type SecaoId } from "@/lib/navegacao";

type BarraLateralProps = {
  ativa: SecaoId;
  urlStreamlit?: string;
};

/** Navegação lateral compacta: sigla em mono + rótulo; recolhe pra uma
 * faixa horizontal no celular. */
export function BarraLateral({ ativa, urlStreamlit }: BarraLateralProps) {
  return (
    <nav
      aria-label="Seções do Pregão"
      className="flex shrink-0 gap-1 overflow-x-auto border-b border-filete bg-painel p-2 md:w-52 md:flex-col md:overflow-visible md:border-r md:border-b-0"
    >
      {NAVEGACAO.map((item) => {
        const atual = item.id === ativa;
        return (
          <a
            key={item.id}
            href={`#${item.id}`}
            aria-current={atual ? "page" : undefined}
            title={item.descricao}
            className={`flex items-center gap-2 whitespace-nowrap rounded-sm px-2 py-1.5 text-[13px] transition-colors ${
              atual
                ? "bg-ambar-fundo text-texto shadow-[inset_2px_0_0_var(--color-ambar)]"
                : "text-suave hover:bg-painel-alto hover:text-texto"
            }`}
          >
            <span className={`w-7 font-mono text-[10px] ${atual ? "text-ambar" : "text-apagado"}`}>{item.sigla}</span>
            {item.rotulo}
          </a>
        );
      })}
      <div className="hidden flex-1 md:block" />
      {urlStreamlit ? (
        <a
          href={urlStreamlit}
          className="hidden rounded-sm border border-filete px-2 py-1.5 text-[11px] text-suave hover:border-ambar hover:text-texto md:block"
        >
          Abrir Pregão (Streamlit) ↗
        </a>
      ) : null}
    </nav>
  );
}
