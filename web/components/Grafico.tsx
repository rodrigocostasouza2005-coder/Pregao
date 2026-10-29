import { num, pct } from "@/lib/formatos";
import { geometria, marcasX, type PontoGrafico } from "@/lib/grafico";

const CORES = { alta: "var(--color-alta)", baixa: "var(--color-baixa)", neutro: "var(--color-ambar)" } as const;

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
  // hora: um rótulo por hora cheia; dia: por dia; mes: por mês; ano: por ano
  const partes: Record<EixoX, Intl.DateTimeFormatOptions> = {
    hora: { day: "2-digit", hour: "2-digit" },
    dia: { year: "numeric", month: "2-digit", day: "2-digit" },
    mes: { year: "numeric", month: "2-digit" },
    ano: { year: "numeric" },
  };
  const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: fuso, ...partes[eixo] });
  return (t: number) => fmt.format(new Date(t));
}

type GraficoProps = {
  pontos: PontoGrafico[];
  /** linha tracejada (ex.: fechamento anterior); também define a cor */
  referencia?: number | null;
  rotuloReferencia?: string;
  eixoX: EixoX;
  fuso?: string;
  casas?: number;
  sufixo?: string;
  /** séries que mudam por decisão (meta Selic): desenho em degraus */
  degrau?: boolean;
  /** "neutro" para séries sem leitura de alta/baixa (juros, inflação) */
  cor?: "auto" | "neutro";
  altura?: number;
  titulo?: string;
  /** máximo de rótulos no eixo x (menos em gráficos estreitos) */
  rotulosX?: number;
};

/** Gráfico de linha do terminal: área discreta, grade horizontal, eixo de
 * valores à direita e etiqueta do último valor - desenhado no servidor. */
export function Grafico({ pontos, referencia = null, rotuloReferencia, eixoX, fuso = "America/Sao_Paulo", casas = 2, sufixo = "", degrau, cor = "auto", altura = 160, titulo, rotulosX = 6 }: GraficoProps) {
  const g = geometria(pontos, { referencia, degrau });
  if (!g) return <p className="text-[12px] text-apagado">Sem pontos suficientes para o gráfico.</p>;
  const base = referencia ?? g.primeiro.v;
  const tom = cor === "neutro" ? "neutro" : g.ultimo.v > base ? "alta" : g.ultimo.v < base ? "baixa" : "neutro";
  const corLinha = CORES[tom];
  const yUltimo = 100 - ((g.ultimo.v - g.min) / (g.max - g.min)) * 100;
  const fx = formatadorX(eixoX, fuso);
  const marcas = marcasX(pontos, chaveX(eixoX, fuso), rotulosX);
  // a etiqueta do último valor tem prioridade sobre o rótulo da grade
  const ticksVisiveis = g.ticksY.filter((t) => Math.abs(t.y - yUltimo) * altura / 100 > 11);
  const id = `g${Math.abs(hash(`${titulo}${pontos.length}${g.ultimo.t}`))}`;
  const variacao = base ? ((g.ultimo.v - base) / base) * 100 : null;
  return (
    <figure className="min-w-0" aria-label={titulo}>
      <div className="relative pr-14" style={{ height: altura }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-[calc(100%-3.5rem)] overflow-visible">
          <defs>
            <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={corLinha} stopOpacity="0.22" />
              <stop offset="1" stopColor={corLinha} stopOpacity="0" />
            </linearGradient>
          </defs>
          {g.ticksY.map((t) => (
            <line key={t.v} x1="0" x2="100" y1={t.y} y2={t.y} stroke="var(--color-filete)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {marcas.map((i) => {
            const x = (i / (pontos.length - 1)) * 100;
            return <line key={i} x1={x} x2={x} y1="0" y2="100" stroke="var(--color-filete)" strokeOpacity="0.5" strokeWidth="1" vectorEffect="non-scaling-stroke" />;
          })}
          {g.yReferencia !== null ? (
            <line x1="0" x2="100" y1={g.yReferencia} y2={g.yReferencia} stroke="var(--color-suave)" strokeDasharray="3 3" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ) : null}
          <path d={g.area} fill={`url(#${id})`} />
          <path d={g.linha} fill="none" stroke={corLinha} strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
        {/* eixo de valores à direita, como nos terminais */}
        {ticksVisiveis.map((t) => (
          <span key={t.v} className="absolute right-0 w-14 -translate-y-1/2 pl-1.5 font-mono text-[10px] text-apagado" style={{ top: `${t.y}%` }}>
            {num(t.v, casas)}
          </span>
        ))}
        <span
          className="absolute right-0 w-14 -translate-y-1/2 px-1 py-px font-mono text-[10px] font-semibold text-base"
          style={{ top: `${yUltimo}%`, background: corLinha }}
        >
          {num(g.ultimo.v, casas)}
        </span>
        {g.yReferencia !== null && rotuloReferencia ? (
          <span className="absolute left-1 -translate-y-full font-mono text-[9.5px] text-suave" style={{ top: `${g.yReferencia}%` }}>
            {rotuloReferencia} {num(referencia, casas)}
          </span>
        ) : null}
      </div>
      <div className="relative mr-14 h-4">
        {marcas.map((i) => (
          <span key={i} className="absolute -translate-x-1/2 whitespace-nowrap font-mono text-[9.5px] text-apagado" style={{ left: `${(i / (pontos.length - 1)) * 100}%` }}>
            {fx(pontos[i].t)}
          </span>
        ))}
      </div>
      {titulo ? (
        <figcaption className="sr-only">
          {titulo}: último {num(g.ultimo.v, casas)}{sufixo}{variacao !== null ? `, ${pct(variacao)} no período` : ""}
        </figcaption>
      ) : null}
    </figure>
  );
}

/** Linha mínima para tabelas (sem eixos). */
export function Sparkline({ pontos, referencia = null, largura = 84, altura = 22 }: { pontos: PontoGrafico[]; referencia?: number | null; largura?: number; altura?: number }) {
  const g = geometria(pontos, { referencia });
  if (!g) return <span className="inline-block font-mono text-[10px] text-apagado" style={{ width: largura }}>—</span>;
  const base = referencia ?? g.primeiro.v;
  const corLinha = CORES[g.ultimo.v > base ? "alta" : g.ultimo.v < base ? "baixa" : "neutro"];
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" width={largura} height={altura} className="inline-block align-middle" aria-hidden>
      {g.yReferencia !== null ? <line x1="0" x2="100" y1={g.yReferencia} y2={g.yReferencia} stroke="var(--color-apagado)" strokeDasharray="2 3" strokeWidth="1" vectorEffect="non-scaling-stroke" /> : null}
      <path d={g.linha} fill="none" stroke={corLinha} strokeWidth="1.25" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Barras horizontais divergentes a partir do zero (variação por setor). */
export function BarrasVariacao({ itens }: { itens: Array<{ rotulo: string; valor: number; detalhe?: string; href?: string }> }) {
  if (!itens.length) return <p className="text-[12px] text-apagado">Sem dados para o gráfico.</p>;
  const maior = Math.max(...itens.map((i) => Math.abs(i.valor)), 0.01);
  return (
    <ul className="space-y-1">
      {itens.map((i) => {
        const largura = (Math.abs(i.valor) / maior) * 50;
        const rotulo = <span className="truncate">{i.rotulo}</span>;
        return (
          <li key={i.rotulo} className="grid grid-cols-[minmax(0,9rem)_1fr_3.75rem] items-center gap-2 text-[11.5px]">
            {i.href ? <a href={i.href} className="truncate hover:text-ambar">{rotulo}</a> : rotulo}
            <span className="relative h-3">
              <span className="absolute inset-y-0 left-1/2 w-px bg-filete" />
              <span
                className={`absolute inset-y-0.5 ${i.valor >= 0 ? "bg-alta/80" : "bg-baixa/80"}`}
                style={i.valor >= 0 ? { left: "50%", width: `${largura}%` } : { right: "50%", width: `${largura}%` }}
                title={i.detalhe}
              />
            </span>
            <span className={`text-right font-mono ${i.valor > 0 ? "text-alta" : i.valor < 0 ? "text-baixa" : "text-suave"}`}>{pct(i.valor)}</span>
          </li>
        );
      })}
    </ul>
  );
}

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}
