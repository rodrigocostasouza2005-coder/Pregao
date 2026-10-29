import { CabecalhoPagina } from "@/components/CabecalhoPagina";
import { EstadoDados } from "@/components/EstadoDados";
import { Painel } from "@/components/Painel";
import { data, dataHora } from "@/lib/formatos";
import { lerEdicoes, secoes } from "@/lib/server/dominio/morningCall";

export const metadata = { title: "Morning Call · Pregão" };

function linhaComLinks(texto: string) {
  const partes = texto.split(/(https?:\/\/\S+)/g);
  return partes.map((p, i) =>
    /^https?:\/\//.test(p) ? <a key={i} href={p} target="_blank" rel="noopener noreferrer" className="text-ambar hover:underline">fonte</a> : <span key={i}>{p}</span>,
  );
}

export default async function MorningCall({ searchParams }: { searchParams: Promise<{ dia?: string }> }) {
  const { dia } = await searchParams;
  const edicoes = await lerEdicoes();
  const atual = edicoes.dados.find((e) => e.dia === dia) || edicoes.dados[0];
  return (
    <>
      <CabecalhoPagina
        titulo="Morning Call"
        descricao="Edições geradas e enviadas pelo job do Pregão (GitHub Actions) · o envio, o PDF e os assinantes continuam no pipeline existente"
      />
      <EstadoDados r={edicoes} vazio="Nenhuma edição enviada registrada." />
      {atual ? (
        <div className="grid gap-3 xl:grid-cols-[1fr_14rem]">
          <Painel titulo={`Edição de ${data(atual.dia)}`} sigla="MC" rodape={`Gerada e enviada às ${dataHora(atual.executadoEm)} (Brasília) · ${atual.envios} envio(s) registrado(s) · texto do e-mail enviado`}>
            <div className="space-y-4">
              {secoes(atual.conteudo).map((s) => (
                <section key={s.titulo}>
                  <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ambar">{s.titulo}</h3>
                  <ul className="space-y-0.5 text-[12.5px] text-suave">
                    {s.linhas.map((l, i) => <li key={i}>{linhaComLinks(l)}</li>)}
                  </ul>
                </section>
              ))}
            </div>
          </Painel>
          <Painel titulo="Histórico">
            <ul className="space-y-1 text-[12px]">
              {edicoes.dados.map((e) => (
                <li key={e.dia}>
                  <a href={`/morning-call?dia=${e.dia}`} className={e.dia === atual.dia ? "text-ambar" : "text-suave hover:text-texto"}>
                    {data(e.dia)}
                  </a>
                </li>
              ))}
            </ul>
          </Painel>
        </div>
      ) : null}
    </>
  );
}
