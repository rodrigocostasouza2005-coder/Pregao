import { AreaPendente } from "@/components/AreaPendente";
import { BarraLateral } from "@/components/BarraLateral";
import { Cabecalho } from "@/components/Cabecalho";
import { Painel } from "@/components/Painel";
import { SeloDemonstrativo } from "@/components/SeloDemonstrativo";
import { TabelaMercado } from "@/components/TabelaMercado";
import { obterCotacoes } from "@/lib/mercado";

export default async function Inicio() {
  const cotacoes = await obterCotacoes();
  const semDados = Object.values(cotacoes).every((c) => c === null);
  const urlStreamlit = process.env.NEXT_PUBLIC_STREAMLIT_URL || undefined;

  return (
    <div className="flex min-h-screen flex-col">
      <Cabecalho />
      <div className="flex flex-1 flex-col md:flex-row">
        <BarraLateral ativa="mercado" urlStreamlit={urlStreamlit} />
        <main className="flex-1 space-y-3 p-3 md:p-4">
          {semDados ? (
            <p className="border-l-2 border-ambar bg-ambar-fundo/60 px-3 py-2 text-[12px] text-suave">
              Nova interface em migração. Os painéis abaixo mostram a estrutura do terminal; nenhum dado de
              mercado está conectado ainda e nenhum número exibido é cotação real.
            </p>
          ) : null}

          <div className="grid gap-3 xl:grid-cols-3">
            <Painel
              titulo="Mercado"
              sigla="MKT"
              className="xl:col-span-2"
              acao={semDados ? <SeloDemonstrativo texto="Sem dados" /> : null}
            >
              <span id="mercado" />
              <TabelaMercado cotacoes={cotacoes} />
            </Painel>

            <Painel titulo="Inteligência" sigla="INT" acao={<SeloDemonstrativo />}>
              <span id="inteligencia" />
              <AreaPendente
                origem="radar setorial (data/radar_setorial.py)"
                itens={["Radar setorial do dia", "Setores em rodízio, com fontes", "Sinais e alertas de queda"]}
              />
            </Painel>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Painel titulo="Notícias" sigla="NWS" acao={<SeloDemonstrativo />}>
              <span id="noticias" />
              <AreaPendente
                origem="coletor de notícias (data/news.py)"
                itens={[
                  "Brasil, Empresas e Mundo, pelo assunto da manchete",
                  "Veículo, data e link em cada matéria",
                  "Filtro de relevância financeira",
                ]}
              />
            </Painel>
            <Painel titulo="Research" sigla="RSH" acao={<SeloDemonstrativo />}>
              <span id="research" />
              <AreaPendente
                origem="carteiras e relatórios (data/research/)"
                itens={["Carteiras recomendadas das casas", "Relatórios por ativo", "Agenda de resultados"]}
              />
            </Painel>
          </div>

          <Painel titulo="Morning Call" sigla="MC" acao={<SeloDemonstrativo />}>
            <span id="morning-call" />
            <AreaPendente
              origem="edição diária (jobs/morning_call_pdf.py)"
              itens={["Última edição em PDF", "Histórico de edições"]}
            />
          </Painel>
        </main>
      </div>
      <footer className="border-t border-filete px-4 py-2 text-[11px] text-apagado">
        Conteúdo informativo, não constitui recomendação de investimento.
      </footer>
    </div>
  );
}
