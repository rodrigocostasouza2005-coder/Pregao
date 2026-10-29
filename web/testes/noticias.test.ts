import { describe, expect, it } from "vitest";

import { foraDePauta, interpretarRss, regiaoPorAssunto } from "@/lib/server/noticias";

describe("editoria pelo assunto (mesma regra do PDF)", () => {
  it("notícia dos EUA coletada no pool BR vai para Mundo", () => {
    expect(regiaoPorAssunto("Déficit orçamentário dos EUA se aproxima de US$ 2 trilhões", "BR")).toBe("INT");
    expect(regiaoPorAssunto("Bitcoin recua após falas de Warsh, do Fed", "BR")).toBe("INT");
  });
  it("notícia do Brasil coletada no pool internacional vai para Brasil", () => {
    expect(regiaoPorAssunto("Brazil central bank holds Selic at 15%", "INT")).toBe("BR");
  });
  it("sem marcador, fica a região da coleta", () => {
    expect(regiaoPorAssunto("Tech stocks stumbled ahead of a crucial week", "INT")).toBe("INT");
  });
});

describe("filtros editoriais", () => {
  it("opinião, colunas em 1ª pessoa e loterias ficam fora", () => {
    expect(foraDePauta("O Estelionato Eleitoral e a Irresponsabilidade Fiscal do Governo Lula")).toBe(true);
    expect(foraDePauta("‘My husband suffered a massive stroke at 53’: I’m 64 and will rent")).toBe(true);
    expect(foraDePauta("Resultado da Quina concurso 6500")).toBe(true);
  });
  it("notícia de mercado continua", () => {
    expect(foraDePauta("Copom mantém Selic e sinaliza cautela")).toBe(false);
    expect(foraDePauta("Petrobras anuncia dividendos extraordinários")).toBe(false);
  });
});

describe("RSS", () => {
  const xml = `<rss><channel>
    <item><title>Ibovespa sobe 1% com Petrobras - InfoMoney</title><link>https://news.google.com/a</link>
      <pubDate>Wed, 29 Oct 2026 13:00:00 GMT</pubDate><source url="https://infomoney.com.br">InfoMoney</source></item>
    <item><title><![CDATA[Fed holds rates &amp; signals caution]]></title><link>https://cnbc.com/b</link>
      <pubDate>Wed, 29 Oct 2026 12:00:00 GMT</pubDate></item>
    <item><title>Alphabet&#x2019;s stock &#8212; worst day</title><link>https://mw.com/c</link></item>
    <item><title>sem link</title><link>javascript:alert(1)</link></item>
  </channel></rss>`;
  it("extrai manchete, veículo (sufixo do Google News), link e data; descarta link inválido", () => {
    const br = interpretarRss(xml, "BR");
    expect(br).toHaveLength(3);
    expect(br[2].titulo).toBe("Alphabet’s stock — worst day");
    expect(br[0]).toMatchObject({ titulo: "Ibovespa sobe 1% com Petrobras", veiculo: "InfoMoney", link: "https://news.google.com/a", regiao: "BR" });
    expect(br[0].publicadaEm).toBe("2026-10-29T13:00:00.000Z");
  });
  it("decodifica CDATA/entidades e aplica o veículo do feed direto", () => {
    const int = interpretarRss(xml, "INT", "CNBC");
    expect(int[1]).toMatchObject({ titulo: "Fed holds rates & signals caution", veiculo: "CNBC", regiao: "INT", idioma: "en" });
  });
});
