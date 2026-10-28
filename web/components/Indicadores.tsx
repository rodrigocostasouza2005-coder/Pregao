import { obterIndicadores } from "@/lib/mercado";
import { formatarNumero, formatarPct } from "@/lib/format";

export async function Indicadores() {
  const itens = await obterIndicadores();
  return (
    <div className="border border-border bg-bg flex flex-wrap">
      {itens.map((item) => (
        <div key={item.rotulo} className="px-4 py-2.5 border-r border-border flex-1 min-w-28">
          <div className="text-[0.6rem] tracking-wide text-text-faint">{item.rotulo}</div>
          {item.preco == null || item.variacaoPct == null ? (
            <>
              <div className="text-[0.88rem] font-bold mt-0.5 text-text-faint">—</div>
              <div className="text-[0.64rem] mt-0.5 text-text-faint">SEM DADO</div>
            </>
          ) : (
            <>
              <div className="text-[0.88rem] font-bold mt-0.5">
                {formatarNumero(item.preco, item.casasDecimais)}
              </div>
              <div
                className={`text-[0.66rem] font-semibold mt-0.5 ${
                  item.variacaoPct >= 0 ? "text-up" : "text-down"
                }`}
              >
                {item.variacaoPct >= 0 ? "▲" : "▼"} {formatarPct(item.variacaoPct)}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
