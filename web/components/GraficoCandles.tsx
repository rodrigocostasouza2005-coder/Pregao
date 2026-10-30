import { num, numCompacto, pct } from "@/lib/formatos";
import { geometriaVelas, marcasX, type VelaGrafico } from "@/lib/grafico";
import { PainelVolume } from "./Grafico";

const CORES = { alta: "var(--color-alta)", baixa: "var(--color-baixa)" } as const;

export type EixoX = "hora" | "dia" | "mes" | "ano";

function formatadorX(eixo: EixoX, fuso: string) {
  const opcoes: Record<EixoX, Intl.DateTimeFormatOptions> = {
    hora: { hour: "2-digit", minute: "2-digit" },
    dia: { day: "2-digit", month: "2-digit" },
    mes: { month: "short", year: "2-digit" },
    ano: { year: "numeric" },
  };
  const fmt = new Intl.DateTimeFormat("pt-BR", { timeZone: fuso, ...opcoes[eixo] });
  return (t: number) => fmt.format(new Date(t)).replace(".", "");
}

function chaveX(eixo: EixoX, fuso: string) {
  const partes: Record<EixoX, Intl.DateTimeFormatOptions> = {
    hora: { day: "2-digit", hour: "2-digit" },
    dia: { year: "numeric", month: "2-digit", day: "2-digit" },
    mes: { year: "numeric", month: "2-digit" },
    ano: { year: "numeric" },
  };
  const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: fuso, ...partes[eixo] });
  return (t: number) => fmt.format(new Date(t));
}

type GraficoCandlesProps = {
  velas: VelaGrafico[];
  volumes?: Array<{ t: number; v: number }>;
  referencia?: number | null;
  rotuloReferencia?: string;
  eixoX: EixoX;
  fuso?: string;
  casas?: number;
  altura?: number;
  titulo?: string;
  rotulosX?: number;
};

/** Candlestick real do terminal (corpo abre/fecha + pavio alta/baixa) -
 * nunca desenha a partir só do fechamento (ver lib/server/yahoo.ts:
 * `velas` só tem a barra quando a fonte trouxe OHLC completo). Mesma
 * régua visual do Grafico.tsx (linha): grade horizontal, eixo de valor à
 * direita, rótulo do último preço, painel de volume opcional abaixo. */
export function GraficoCandles({ velas, volumes, referencia = null, rotuloReferencia, eixoX, fuso = "America/Sao_Paulo", casas = 2, altura = 260, titulo, rotulosX = 6 }: GraficoCandlesProps) {
  const g = geometriaVelas(velas, { referencia });
  if (!g) return <p className="text-[12px] text-apagado">Sem candles suficientes para o gráfico.</p>;
  const fx = formatadorX(eixoX, fuso);
  const pontosX = velas.map((v) => ({ t: v.t, v: v.close }));
  const marcas = marcasX(pontosX, chaveX(eixoX, fuso), rotulosX);
  const yUltimo = g.itens.at(-1)?.yFecha ?? 50;
  const ticksVisiveis = g.ticksY.filter((t) => Math.abs(t.y - yUltimo) * altura / 100 > 11);
  const corUltimo = g.itens.at(-1)?.alta ? CORES.alta : CORES.baixa;
  const base = referencia ?? g.primeiro.open;
  const variacao = base ? ((g.ultimo.close - base) / base) * 100 : null;

  return (
    <figure className="min-w-0" aria-label={titulo}>
      <div className="relative pr-14" style={{ height: altura }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-[calc(100%-3.5rem)] overflow-visible">
          {g.ticksY.map((t) => (
            <line key={t.v} x1="0" x2="100" y1={t.y} y2={t.y} stroke="var(--color-filete)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {marcas.map((i) => {
            const x = (i / (velas.length - 1)) * 100;
            return <line key={i} x1={x} x2={x} y1="0" y2="100" stroke="var(--color-filete)" strokeOpacity="0.5" strokeWidth="1" vectorEffect="non-scaling-stroke" />;
          })}
          {g.yReferencia !== null ? (
            <line x1="0" x2="100" y1={g.yReferencia} y2={g.yReferencia} stroke="var(--color-suave)" strokeDasharray="3 3" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ) : null}
          {g.itens.map((v, i) => {
            const cor = v.alta ? CORES.alta : CORES.baixa;
            const corpoTopo = Math.min(v.yAbre, v.yFecha);
            const corpoAltura = Math.max(Math.abs(v.yFecha - v.yAbre), 0.5);
            return (
              <g key={i}>
                <line x1={v.x} x2={v.x} y1={v.yAlta} y2={v.yBaixa} stroke={cor} strokeWidth="0.6" vectorEffect="non-scaling-stroke" />
                <rect x={v.x - v.largura / 2} y={corpoTopo} width={v.largura} height={corpoAltura} fill={cor} />
              </g>
            );
          })}
        </svg>
        {ticksVisiveis.map((t) => (
          <span key={t.v} className="absolute right-0 w-14 -translate-y-1/2 pl-1.5 font-mono text-[10px] text-apagado" style={{ top: `${t.y}%` }}>
            {num(t.v, casas)}
          </span>
        ))}
        <span
          className="absolute right-0 w-14 -translate-y-1/2 px-1 py-px font-mono text-[10px] font-semibold text-base"
          style={{ top: `${yUltimo}%`, background: corUltimo }}
        >
          {num(g.ultimo.close, casas)}
        </span>
        {g.yReferencia !== null && rotuloReferencia ? (
          <span className="absolute left-1 -translate-y-full font-mono text-[9.5px] text-suave" style={{ top: `${g.yReferencia}%` }}>
            {rotuloReferencia} {num(referencia, casas)}
          </span>
        ) : null}
      </div>
      {volumes?.length ? (
        <>
          <PainelVolume volumes={volumes} />
          <p className="mr-14 mt-0.5 text-right font-mono text-[9.5px] text-apagado">
            volume fin. acumulado no período: R$ {numCompacto(volumes.reduce((soma, p) => soma + p.v, 0))}
          </p>
        </>
      ) : null}
      <div className="relative mr-14 h-4">
        {marcas.map((i) => (
          <span key={i} className="absolute -translate-x-1/2 whitespace-nowrap font-mono text-[9.5px] text-apagado" style={{ left: `${(i / (velas.length - 1)) * 100}%` }}>
            {fx(velas[i].t)}
          </span>
        ))}
      </div>
      {titulo ? (
        <figcaption className="sr-only">
          {titulo}: abertura {num(g.ultimo.open, casas)}, máxima {num(g.ultimo.high, casas)}, mínima {num(g.ultimo.low, casas)}, fechamento {num(g.ultimo.close, casas)}
          {variacao !== null ? `, ${pct(variacao)} no período` : ""}
        </figcaption>
      ) : null}
    </figure>
  );
}
