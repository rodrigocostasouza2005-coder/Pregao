# -*- coding: utf-8 -*-
"""Registro das casas de research: um coletor por casa, todos no mesmo
formato (casa, titulo, data, autor, tipo, setor, tickers, link).

Pra ligar/desligar uma casa (por padrao ou por usuario, via prefs), mexa
so nessa lista - a UI (ui/research_tab.py) le CASAS pra montar o filtro.

Estado atual das fontes (revisado em 2026-11-04):
- Genial Analisa, XP Investimentos e Genial (Lives): DESATIVADAS. Os
  bloqueios persistentes (WAF/Akamai HTTP 403 e YouTube RSS HTTP 404)
  fizeram o projeto parar novas tentativas automatizadas; dados antigos
  continuam preservados no Supabase e fora do consenso decisorio.
- BTG Research: API real (content.btgpactual.com/api/research/content-hub/
  analysis/filter) coletavel - achado que corrigiu a investigacao anterior
  (2026-10-17): o campo "tier" (AREA_PUBLICA/AREA_LOGADA) JA' vem no
  proprio lote, nao so' no detalhe - coletor filtra por AREA_PUBLICA antes
  de persistir, nunca toca em conteudo de area logada (ver data/research/
  btg.py e CASAS['btg'] abaixo pros detalhes completos da investigacao).
- Itau BBA, Santander, Bradesco BBI: investigadas em 2026-10-29 (pedido
  explicito do Rodrigo) - nenhuma tem fonte publica coletavel. Itau BBA e
  Santander bloqueiam fetch automatizado (403, mesmo padrao de borda do
  XP/Genial) nas paginas institucionais de research; o unico acesso real
  e' um portal logado de cliente (Itau: "Open Finance" nao cobre research
  de acoes; Santander: "Painel do Investidor" da corretora). Bradesco BBI
  nao bloqueia a pagina institucional, mas ela e' so' apresentacao da
  equipe - zero link de relatorio, RSS ou API; a area com conteudo real
  nao e' publica. Nenhuma tem RSS/sitemap no estilo Monte Bravo/Nord nem
  API publica no estilo BTG - sao research sell-side distribuido so a
  cliente autenticado, nao HTML frio que valha a pena tentar raspar.
  Registradas abaixo com disponivel=False (nunca tenta coletar, aparece
  em SAUDE DOS DADOS via falhas em preparar_leitura) em vez de um coletor
  fragil sem fonte real. BB Investimentos, Safra (research de acoes;
  Safra Corretora/carteiras recomendadas e' outro coletor, ver
  data/research/safra_carteiras.py), Inter: ainda nao investigadas.
- Agora Investimentos, Ativa Investimentos, Andbank Brasil, Planner
  Investimentos: investigadas em 2026-10-30 (pedido explicito do Rodrigo,
  expansao do ecossistema apos dificuldade de coleta de XP/BTG/Genial) -
  nenhuma virou coletor nesta rodada, por motivos diferentes entre si
  (ver comentario de cada entrada abaixo pro detalhe completo da
  sondagem real):
  - Agora: tem conteudo real e publico por item JA CONHECIDO (plataforma
    "Agora Insights", teaser sem login), mas SEM nenhum RSS/sitemap/API
    de listagem encontrado pra descobrir relatorio NOVO, e o texto
    completo e' pago (carrinho de compra) - unico caso aqui que nao e'
    bloqueio de borda, e' ausencia de mecanismo de descoberta.
  - Ativa: bloqueio de borda (403) consistente em toda rota testada,
    inclusive no robots.txt.
  - Andbank e Planner: robots.txt do dominio e' "Disallow: /" (proibe
    coleta do site inteiro) - decisao da propria instituicao, respeitada
    sem excecao.
  Itau BBA reconfirmado na mesma rodada (403 de novo, sem mudanca desde
  29/10/2026).
- J.P. Morgan, BofA, Morgan Stanley, Citi: adicionadas em 2026-11-11
  (pedido explicito do Rodrigo, bancos globais prioritarios). Pra todos os
  4, o research institucional completo (rating/preco-alvo por ativo) e'
  client-only (JP Morgan Markets, portal de research da BofA, Morgan
  Stanley Research, Citi Velocity/ICG) - NUNCA coletado por este projeto.
  Os 4 bancos tambem publicam, sem login, um hub editorial proprio com
  conteudo macro/tematico real e atual (confirmado com requisicao real
  deste ambiente, nao WebSearch/suposicao): J.P. Morgan "Global Research"
  (jpmorgan.com/insights/global-research), "Bank of America Institute"
  (institute.bankofamerica.com), Morgan Stanley "Insights"
  (morganstanley.com/insights/articles) e Citi "Global Insights"
  (citigroup.com/global/insights) - todos com nome de casa deliberadamente
  diferente de "<Banco> Research" pra nunca sugerir que e' a mesma coisa
  que o research institucional pago (ver docstring de cada
  data/research/<banco>.py pro detalhe completo da investigacao e da
  limitacao). Itau BBA permanece so' com carteiras recomendadas
  (data/research/itau_carteiras.py) - reconfirmado nesta mesma rodada
  (HTTP 403 de novo na pagina institucional de research, sem mudanca
  desde 29/10/2026); Bradesco BBI permanece sem nenhum canal publico
  (reconfirmado: pagina institucional carrega, mas continua sem nenhum
  link de relatorio/RSS/API).
- Goldman Sachs, Jefferies, Deutsche Bank Research Institute, Levante
  Ideias de Investimentos: adicionadas em 2026-11-12 (missao Agente B -
  expansao de casas de research, pedido explicito do Rodrigo). Goldman
  Sachs e Jefferies seguem o MESMO padrao dos 4 bancos de 11/11/2026
  (hub editorial publico via sitemap + ld+json por pagina, research
  institucional pago nunca coletado - ver data/research/goldman_sachs.py
  e data/research/jefferies.py). Deutsche Bank Research Institute usa um
  padrao novo: sem sitemap funcional, descoberta direto na pagina-indice
  de topico (widget HTML customizado, titulo+data+link de varios itens
  num unico request - ver data/research/dbresearch.py). Levante e' a
  primeira casa INDEPENDENTE brasileira nova desde Nord/Monte Bravo -
  feed RSS real com disclaimer formal de analista CNPI (ver
  data/research/levante.py).
  Na mesma rodada, investigadas e NAO implementadas (ver comentario de
  cada entrada abaixo pro detalhe completo da sondagem real): Barclays
  (hub existe, sem mecanismo de descoberta de item novo - paginas
  evergreen sem arquivo/data), HSBC (sem secao de insights descobrivel no
  orcamento desta rodada - investigacao incompleta), UBS (hub existe,
  sitemap multi-pais grande demais pra analisar por completo no
  orcamento desta rodada - investigacao incompleta), Safra research de
  acoes (oespecialista.safra.com.br, HTTP 403 reconfirmado, sem mudanca
  desde 22/10/2026), BB Investimentos (Investalk - pagina carrega sem
  bloqueio mas catalogo e' client-side sem API publica encontrada), Suno
  Research (feed publico e' blog educacional geral; paginas por ticker
  sao perfil de cotacao, nao relatorio datado), Eleven Financial (SPA
  client-side, sem sitemap/listagem real encontrado), Terra Investimentos
  (falha de TLS neste ambiente - nao foi possivel conectar, limitacao do
  ambiente). UBS, HSBC, Eleven Financial e Terra Investimentos tem
  investigacao MARCADA COMO INCOMPLETA (nao e' veredito final de
  bloqueio/ausencia de conteudo) - revisitar com mais orcamento de tempo
  ou outro ambiente de rede antes de descartar de vez.

Os itens coletados sao persistidos no Supabase (tabela research_itens,
ver data/research/store.py) - a aba RESEARCH sempre le do banco primeiro
(preparar_leitura, rapido) e so depois dispara coleta pras casas
desatualizadas (coletar_pendentes, com timeout por requisicao e orcamento
total de tempo - ver data/research/base.py); a coleta roda no maximo a
cada 30min por casa (store.precisa_recoletar)."""

import time
from datetime import datetime, timezone

import streamlit as st

from data.coletores_status import obter_status, registrar_tentativa

from . import (
    bankofamerica, btg, citi, dbresearch, genial, genial_lives, goldman_sachs, jefferies,
    jpmorgan, levante, montebravo, morgan_stanley, nord, store, xp,
)
from .base import TEMPO_MAX_COLETA_S, CooldownPorChave

# nao tenta recoletar a mesma casa antes desse tempo desde a ULTIMA
# TENTATIVA (sucesso ou falha) - existe pra nao martelar uma fonte que
# acabou de falhar a cada interacao do usuario na aba RESEARCH (era o
# caso real do Genial/XP quando bloqueados em producao: cada rerun
# tentava de novo, ate ~25s de orcamento, deixando a aba lenta em TODA
# interacao, nao so na primeira). store.precisa_recoletar() so evita
# recoleta apos SUCESSO (coletado_em so avanca quando salva); este
# cooldown cobre a lacuna de tentativas que falharam.
_COOLDOWN_FALHA_S = 10 * 60

CASAS = [
    {
        "id": "genial",
        "nome": "Genial Analisa",
        "fonte": "analisa.genialinvestimentos.com.br",
        "ativa_por_padrao": False,
        "disponivel": False,
        "motivo_indisponivel": "Coleta desativada por decisão do projeto: bloqueio WAF persistente nas execuções de produção e em nuvem; mantém apenas o histórico já salvo.",
        "obter_relatorios": genial.obter_relatorios,
        "extrator_texto": None,  # generico (baixa a pagina publica do relatorio)
        # diagnostico de producao (2026-09-24): bloqueada no Streamlit
        # Cloud (~20s pra desistir, orcamento de _tentar_buscar). O app
        # nao tenta mais coletar essa casa - so le o que o
        # coletor_local.py (fora do Cloud) ja tiver salvo no Supabase.
        "tentar_coleta_automatica": False,
        # achado real (auditoria 2026-10-15): sem isso, SAUDE DOS DADOS
        # so mostrava "obter_relatorios retornou None apos Xs" - o motivo
        # especifico (timeout/HTTP-2-reset/orcamento esgotado) so
        # aparecia no print(), nunca no painel. Opcional - casas sem essa
        # chave continuam exatamente como antes.
        "motivo_falha": genial.motivo_ultima_falha,
        # achado real (auditoria 2026-10-18, correcao do exit code de
        # coletor_local.py): sem isso, uma falha aqui (bloqueio de WAF
        # ja' documentado, cronico desde 24/09) derrubava o exit code
        # igual a uma regressao nova em qualquer outra casa - opcional,
        # casa sem essa chave continua tratada como 'erro' (nunca
        # bloqueio conhecido por padrao), ver _classificar_falha.
        "categoria_falha": genial.categoria_ultima_falha,
        # achado real (auditoria SAUDE DOS DADOS 2026-10-26): coletor_local.py
        # (coletar_todas_disponiveis, abaixo) nao tinha NENHUM cooldown -
        # cada execucao (processo novo, agendador do sistema) tentava de
        # novo as 4 tentativas/20s de orcamento mesmo sabendo, pela ultima
        # tentativa PERSISTIDA, que o bloqueio de WAF e' o mesmo de sempre.
        # Usado por _bloqueio_conhecido_em_cooldown pra pular a tentativa
        # cara quando a ULTIMA falha real teve esse marcador exato ha'
        # menos de _COOLDOWN_BLOQUEIO_CONHECIDO_S - qualquer erro diferente
        # (ou sucesso) sempre tenta de novo.
        "marcador_bloqueio_conhecido": genial.MARCADOR_BLOQUEIO_WAF,
    },
    {
        "id": "xp",
        "nome": "XP Investimentos",
        "fonte": "conteudos.xpi.com.br (WP REST)",
        "ativa_por_padrao": False,  # campos confirmados com requisicao real (fora do sandbox), ver xp.py
        "disponivel": False,
        "motivo_indisponivel": "Coleta desativada por decisão do projeto: CDN/Akamai responde HTTP 403; não serão feitas novas tentativas automatizadas.",
        "obter_relatorios": xp.obter_relatorios,
        "extrator_texto": xp.obter_texto_aberto,  # nunca baixa a pagina publica (paywall)
        "tentar_coleta_automatica": False,  # idem Genial - bloqueada no Cloud (403), ver coletor_local.py
        "motivo_falha": xp.motivo_ultima_falha,
        "categoria_falha": xp.categoria_ultima_falha,  # ver comentario equivalente em Genial Analisa acima
        "marcador_bloqueio_conhecido": xp.MARCADOR_BLOQUEIO_CDN,  # ver comentario equivalente em Genial Analisa acima
    },
    {
        # Ligada em 2026-09-28 a pedido explicito do Rodrigo ("quero a
        # transcricao das lives da Genial") - ver ATENCAO no topo de
        # genial_lives.py: ignora deliberadamente o robots.txt do
        # YouTube (que proibe /feeds/videos.xml pra bots genericos),
        # excecao unica no projeto, justificada por uso pessoal/nao
        # comercial e volume baixo. Nao copiar esse padrao pra outra
        # fonte sem a mesma decisao explicita.
        "id": "genial_lives",
        "nome": "Genial (Lives)",
        "fonte": "YouTube RSS (canal Genial Analisa)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "motivo_indisponivel": "Coleta desativada por decisão do projeto: feed RSS do YouTube retorna HTTP 404; não serão feitas novas tentativas automatizadas.",
        "obter_relatorios": genial_lives.obter_relatorios,
        "extrator_texto": genial_lives.obter_texto_transcricao,
        # achado real (2026-10-17): a execucao de producao no GitHub
        # Actions (run 38989522110) mostrou essa casa falhando ("[research]
        # coleta Genial (Lives) falhou apos 4.5s") sem nenhum detalhe -
        # motivo_ultima_falha novo em genial_lives.py (mesmo padrao de
        # genial.py/xp.py) pra essa falha aparecer em SAUDE DOS DADOS.
        "motivo_falha": genial_lives.motivo_ultima_falha,
        # achado real (2026-10-24): o feed do canal passou a devolver
        # "HTTP 404, text/html" pro endpoint /feeds/videos.xml inteiro
        # (confirmado contra 2 canais de controle sem nenhuma relacao
        # com a Genial, ver _MARCADOR_BLOQUEIO_YOUTUBE em
        # genial_lives.py) - sem isso, essa falha (bloqueio de IP,
        # fora do controle do projeto) derrubava o exit code de
        # coletor_local.py igual a uma regressao nova, mesmo padrao
        # ja corrigido pra Genial Analisa/XP em 2026-10-18.
        "categoria_falha": genial_lives.categoria_ultima_falha,
    },
    {
        # Investigado de novo em 2026-10-17 (reinvestigacao da mesma
        # sessao, apos pedido explicito do Rodrigo pra nao parar so' no
        # diagnostico): a conclusao anterior ("tier so' aparece no
        # detalhe, filtrar exigiria N+1 requisicoes contra conteudo ja'
        # recebido") estava ERRADA - testada de novo com requisicao real,
        # o campo "tier" ("AREA_PUBLICA"/"AREA_LOGADA") JA' vem no proprio
        # POST /filter em lote, item por item, sem precisar de nenhuma
        # chamada de detalhe. Confirmado com 300 itens reais (12 paginas),
        # tier presente em 100% deles, 123/300 (41%) e 68/200 (34%) em
        # amostras distintas "AREA_PUBLICA" - volume real suficiente pra
        # coletor. robots.txt de content.btgpactual.com permite tudo
        # ("Allow: /"); nenhum bloqueio observado em dezenas de requisicoes
        # reais, com o UA identificado do projeto OU um UA de navegador
        # comum - sem diferenca nenhuma (diferente de genial.py/xp.py,
        # que SAO bloqueados por fingerprint/WAF - aqui nao ha' bloqueio
        # algum pra contornar).
        #
        # Coletor implementado (data/research/btg.py) filtra por
        # tier=="AREA_PUBLICA" ANTES de qualquer persistencia - usa o
        # controle de acesso que a BTG expoe, em vez de ignora-lo; nunca
        # inclui item AREA_LOGADA nem item sem tier reconhecido. A pagina
        # www.btgpactual.com/acoes/ultimos-relatorios (SPA diferente,
        # dominio diferente) continua bloqueada pra Chromium/Playwright
        # (0/8 tentativas, auditorias anteriores) - mas o coletor nunca
        # depende dela, le direto a API publica de content.btgpactual.com.
        #
        # Link persistido e' o endpoint de detalhe da API (real, publico,
        # estavel, unico por item) - nao foi encontrada no bundle Angular
        # publico (111 chunks JS verificados) uma rota de pagina com slug
        # amigavel confirmada; usar o endpoint de API e' honesto (nao
        # inventa uma URL de pagina nao verificada).
        "id": "btg",
        "nome": "BTG Pactual Research",
        "fonte": "content.btgpactual.com (API de research, filtrado por tier publico)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": btg.obter_relatorios,
        # nao usa o generico (baixa a pagina com curl_cffi impersonate,
        # pensado pra HTML/PDF) - link e' um endpoint JSON da propria API
        # publica; obter_texto_publico reconsulta e RECONFIRMA tier antes
        # de devolver texto (defesa em profundidade contra item que tenha
        # virado AREA_LOGADA depois da coleta).
        "extrator_texto": btg.obter_texto_publico,
        "motivo_falha": btg.motivo_ultima_falha,
    },
    {
        # Adicionada em 22/10/2026: feed RSS público do WordPress oficial
        # (robots.txt permite tudo), sondado de verdade a partir do runner do
        # GitHub Actions - análises de empresas e carta mensal; imprensa e
        # eventos ficam fora (ver montebravo.py). Texto para resumo: página
        # pública do próprio post (extrator genérico, respeita robots).
        "id": "montebravo",
        "nome": "Monte Bravo",
        "fonte": "montebravo.com.br (feed RSS do blog, seção de análise)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": montebravo.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": montebravo.motivo_ultima_falha,
    },
    {
        # Adicionada em 24/10/2026 (pedido explicito do Rodrigo, lista de
        # 10 casas prioritarias): sem feed RSS (/feed/ e /blog/feed/ dao
        # HTTP 404) - descoberta via /blog/sitemap.xml, publico e listado
        # no proprio robots.txt ("Allow: /"). So entram posts com ticker
        # B3 + "resultado(s)" no slug (ver nord.py) - a categoria mais
        # claramente "research de acoes" confirmada com texto real
        # (recomendacao explicita no post da Petrobras 1T26, assinado por
        # analista nomeado). Sem isso, o sitemap tem ~7700 URLs, a maioria
        # conteudo educacional/opiniao ("X vale a pena investir"), que nao
        # e' research. Ainda NAO testada a partir do Streamlit Cloud/
        # GitHub Actions (so' deste ambiente de dev) - se bloquear la',
        # vira candidata a tentar_coleta_automatica=False como Genial/XP.
        "id": "nord",
        "nome": "Nord Research",
        "fonte": "nordinvestimentos.com.br (sitemap do blog, posts de resultado por ticker)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": nord.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": nord.motivo_ultima_falha,
    },
    {
        # Adicionada em 11/11/2026 (pedido explicito do Rodrigo - lista de
        # bancos globais prioritarios: JPM, Bradesco BBI, BofA, Morgan
        # Stanley, Citi). Sondagem real (deste ambiente, rede disponivel):
        # o research institucional completo do J.P. Morgan (rating/preco-
        # alvo por ativo) e' client-only via J.P. Morgan Markets - NUNCA
        # coletado aqui. O banco tambem publica, sem login, uma secao com
        # marca propria "Global Research" (eyebrow "Global Research" em
        # cada artigo, pagina-indice "Global Research & Market Insights
        # from J.P. Morgan") - mais perto de research macro/tematico
        # publico do que de cobertura formal de 1 acao (ver docstring de
        # data/research/jpmorgan.py pro detalhe completo, inclusive a
        # limitacao). Descoberta via sitemap real (US/en/sitemap.xml,
        # confirmado com 2 paginas reais, datas de 19/10 e 06/11/2026, sem
        # nenhuma simulada); robots.txt permite /insights e /sitemap.xml.
        "id": "jpmorgan",
        "nome": "J.P. Morgan Global Research",
        "fonte": "jpmorgan.com/insights/global-research (conteudo publico; research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": jpmorgan.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": jpmorgan.motivo_ultima_falha,
    },
    {
        # Adicionada em 11/11/2026 (mesmo pedido acima). Sondagem real:
        # "BofA Global Research" (sell-side, rating/preco-alvo) e'
        # client-only - NUNCA coletado aqui. O "Bank of America Institute"
        # (institute.bankofamerica.com) e' uma publicacao PUBLICA separada,
        # sem login, com analises macro/de consumo a partir de dados
        # agregados do proprio banco (ex: "Consumer Checkpoint",
        # "Economic Insights") - instituicao e publicacao reais, nome
        # deliberadamente "BofA Institute" (nunca "BofA Research") pra nao
        # confundir as duas coisas (ver docstring de
        # data/research/bankofamerica.py). As paginas nao expoem uma data
        # de publicacao confiavel no HTML - a 'data' usada vem do lastmod
        # real do sitemap oficial do site (nunca inventada, so' com essa
        # ressalva documentada). robots.txt do dominio permite tudo
        # relevante aqui.
        "id": "bankofamerica",
        "nome": "BofA Institute",
        "fonte": "institute.bankofamerica.com (sitemap, secao Economic Insights; nao e' BofA Global Research)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": bankofamerica.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": bankofamerica.motivo_ultima_falha,
    },
    {
        # Adicionada em 11/11/2026 (mesmo pedido acima). Sondagem real:
        # Morgan Stanley Research institucional (client-only) NUNCA e'
        # coletado aqui. O hub publico e' hoje morganstanley.com/insights
        # (a URL antiga /ideas redireciona pra la') - alguns artigos
        # resumem achados do proprio Morgan Stanley Research em linguagem
        # publica (confirmado com og:description real: "Morgan Stanley
        # Research assesses..."), mas o coletor nunca chama isso de nota
        # de research completa (ver docstring de
        # data/research/morgan_stanley.py). Descoberta via sitemap oficial
        # (sitemapindex.xml -> sitemap.xml, ~4600 URLs reais, lastmod
        # confirmado na mesma semana da sondagem); filtra so'
        # /insights/articles/ (exclui podcasts/videos/press-releases, sem
        # o metadado de data usado aqui). robots.txt permite esse path.
        "id": "morgan_stanley",
        "nome": "Morgan Stanley Insights",
        "fonte": "morganstanley.com/insights/articles (conteudo publico; research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": morgan_stanley.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": morgan_stanley.motivo_ultima_falha,
    },
    {
        # Adicionada em 11/11/2026 (mesmo pedido acima). Sondagem real:
        # "Citi Research" institucional (Citi Velocity/ICG, client-only)
        # NUNCA e' coletado aqui. O hub publico "Insights"
        # (citigroup.com/global/insights) tem conteudo de mercado/
        # estrategia muitas vezes assinado por analista nomeado NO PROPRIO
        # TEXTO (confirmado com nota real de 10/11/2026: "Beata Manthey
        # and David Groman assess..."); o coletor nunca chama isso de
        # "Citi Research" por esse motivo (ver docstring de
        # data/research/citi.py). Descoberta via sitemap oficial
        # (declarado no proprio robots.txt, ~3600 URLs reais, lastmod do
        # mesmo dia da sondagem - cadencia bem mais alta que as outras
        # casas novas); filtra so' "/global/insights/" (exclui
        # "/global/news/perspectives/", que e' conteudo institucional
        # sobre a propria Citi, nao mercado). Cada pagina tem um bloco
        # ld+json real (nao inferido) com headline/datePublished.
        "id": "citi",
        "nome": "Citi Global Insights",
        "fonte": "citigroup.com/global/insights (conteudo publico; research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": citi.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": citi.motivo_ultima_falha,
    },
    {
        # Adicionada em 12/11/2026 (missao Agente B - expansao de casas de
        # research, pedido explicito do Rodrigo: Goldman Sachs, UBS,
        # Barclays, HSBC, Deutsche Bank, Jefferies). Sondagem real: o
        # research institucional completo da Goldman Sachs (rating/
        # preco-alvo por ativo, via GS Marquee/GS Research) e' client-only
        # - NUNCA coletado aqui. O banco tambem publica, sem login, um hub
        # editorial proprio "Insights" (goldmansachs.com/insights/articles)
        # com conteudo macro/tematico real e atual (confirmado com pagina
        # real: "Why the ECB Is Unlikely to Keep Rates Higher Than 3%",
        # datePublished 2026-09-25, e itens de 11/2026 no sitemap) - mesma
        # distincao documentada pros bancos globais de 11/11/2026 (ver
        # docstring de data/research/goldman_sachs.py pro detalhe completo
        # da investigacao, inclusive a limitacao). Descoberta via sitemap
        # real (indice -> sitemap-1.xml, ~1.5MB, filtra so'
        # "/insights/articles/" - exclui ~3700 ocorrencias de "insights" do
        # blog de filantropia "/community-transformation/.../insights/",
        # que nao e' mercado).
        "id": "goldman_sachs",
        "nome": "Goldman Sachs Insights",
        "fonte": "goldmansachs.com/insights/articles (conteudo publico; research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": goldman_sachs.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": goldman_sachs.motivo_ultima_falha,
    },
    {
        # Adicionada em 12/11/2026 (mesma missao acima). Sondagem real: o
        # research institucional completo da Jefferies (cobertura de
        # acoes por ativo, via Jefferies Live/portal de clientes) e'
        # client-only - NUNCA coletado aqui. O banco tambem publica, sem
        # login, um hub editorial proprio em jefferies.com/insights
        # (WordPress publico) com conteudo tematico real e atual sobre
        # mercados/setores/politica (confirmado com pagina real:
        # "What's Driving Healthcare Dealmaking Right Now?", datePublished
        # 2026-11-10, author real "amarx", articleSection "Markets") - ver
        # docstring de data/research/jefferies.py pro detalhe completo da
        # investigacao, inclusive a limitacao. Descoberta via sitemap
        # padrao do Yoast SEO (post-sitemap.xml, ~230 URLs, hoje todos sob
        # "/insights/" - filtra por esse prefixo mesmo assim, por
        # seguranca).
        "id": "jefferies",
        "nome": "Jefferies Insights",
        "fonte": "jefferies.com/insights (conteudo publico; research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": jefferies.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": jefferies.motivo_ultima_falha,
    },
    {
        # Adicionada em 12/11/2026 (mesma missao acima). Sondagem real: o
        # research institucional completo do Deutsche Bank (cobertura de
        # acoes por ativo, via DB Research/Autobahn) e' client-only -
        # NUNCA coletado aqui. O banco tambem publica, sem login, uma
        # secao propria "Research Institute" (dbresearch.com/PROD/IE-PROD/
        # <Topico>__Research_Institute/<alias>.alias) com conteudo macro
        # real e atual, assinado por nomes reais do research global do
        # banco (confirmado com pagina real de Macro: "Jim Reid on AI and
        # bond vigilantes", "CPI Reaction", itens de 11-12/11/2026) - ver
        # docstring de data/research/dbresearch.py pro detalhe completo da
        # investigacao, inclusive a limitacao. Sem sitemap.xml funcional
        # (404) - descoberta direto na pagina-indice do topico Macro
        # (RI_MAC.alias), que lista varios itens (titulo+data+link) num
        # unico request, sem precisar de 1 request por item (diferente de
        # citi.py/nord.py). robots.txt tem "Allow: /" pro grupo "*" -
        # bloqueia so' user-agents de bot NOMEADOS (incluindo crawlers de
        # IA), nenhum deles bate o UA deste projeto.
        "id": "dbresearch",
        "nome": "Deutsche Bank Research Institute",
        "fonte": "dbresearch.com/PROD/IE-PROD (secao Macro; conteudo publico, research completo e' client-only)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": dbresearch.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": dbresearch.motivo_ultima_falha,
    },
    {
        # Adicionada em 12/11/2026 (missao Agente B - expansao de casas de
        # research, Grupo 3: independentes). Levante Ideias de
        # Investimentos e' uma casa de research independente de verdade
        # (CVM/APIMEC, analistas CNPI nomeados) - confirmado com amostra
        # real do feed: o content:encoded de cada post traz o disclaimer
        # formal completo da "INSIDE RESEARCH LTDA." (empresa do Grupo
        # Levante), com nome e numero de registro CNPI do analista
        # responsavel. robots.txt "Allow: /" (tudo permitido, Sitemap:
        # declarado); feed RSS 2.0 real em levanteideias.com.br/feed/
        # (o content-type do servidor vem errado como "text/html", mas o
        # corpo e' XML real - nao e' motivo pra descartar). Filtra por
        # ticker B3 na categoria OU por categoria de research conhecida
        # ("research"/"insideresearch"/"EECI") - ver docstring de
        # data/research/levante.py pro detalhe completo.
        "id": "levante",
        "nome": "Levante Ideias de Investimentos",
        "fonte": "levanteideias.com.br (feed RSS do blog, itens com ticker B3 ou categoria de research)",
        "ativa_por_padrao": True,
        "disponivel": True,
        "obter_relatorios": levante.obter_relatorios,
        "extrator_texto": None,
        "motivo_falha": levante.motivo_ultima_falha,
    },
    {
        # Investigada em 2026-10-29 (pedido explicito do Rodrigo): pagina
        # institucional de research bloqueia fetch automatizado (403,
        # borda/WAF) - mesmo padrao de genial.py/xp.py, mas sem nenhum
        # endpoint publico alternativo encontrado (o portal de API do
        # Itau e' Open Finance/bancario, nao cobre research de acoes).
        # disponivel=False (nunca tenta coletar) em vez de
        # tentar_coleta_automatica=False (que ainda tentaria 1x/30min no
        # app ao vivo) - aqui nao ha' NENHUM endpoint coletavel, tentar
        # de novo nao vai mudar isso.
        "id": "itau_bba",
        "nome": "Itaú BBA Research",
        "fonte": "itau.com.br/itaubba-pt (bloqueado - sem API/RSS publico)",
        "ativa_por_padrao": False,
        "disponivel": False,
        # ui/research_tab.py monta _EXTRATOR_POR_CASA pra TODA casa em
        # CASAS sem .get() - precisa da chave mesmo nunca sendo chamada.
        "extrator_texto": None,
        "motivo_indisponivel": "research institucional sem canal publico - distribuicao so a cliente autenticado (403 na pagina institucional)",
    },
    {
        # Investigada em 2026-10-29: pagina institucional bloqueia fetch
        # automatizado (403); relatorios reais ficam no "Painel do
        # Investidor" da corretora (login), sem API/RSS publico.
        "id": "santander_research",
        "nome": "Santander Research",
        "fonte": "santander.com.br/investimentos (bloqueado - sem API/RSS publico)",
        "ativa_por_padrao": False,
        "disponivel": False,
        # ui/research_tab.py monta _EXTRATOR_POR_CASA pra TODA casa em
        # CASAS sem .get() - precisa da chave mesmo nunca sendo chamada.
        "extrator_texto": None,
        "motivo_indisponivel": "relatorios so acessiveis via login no Painel do Investidor da corretora - nenhum endpoint publico encontrado",
    },
    {
        # Investigada em 2026-10-29: pagina institucional carrega
        # normalmente (sem bloqueio), mas e' so apresentacao da equipe -
        # zero link de relatorio/RSS/API; nao ha' NADA coletavel ali, nao
        # e' caso de scraping fragil e sim de fonte sem conteudo publico.
        "id": "bradesco_bbi",
        "nome": "Bradesco BBI Research",
        "fonte": "bradescobbi.com.br/pt/research (sem relatorios na area publica)",
        "ativa_por_padrao": False,
        "disponivel": False,
        # ui/research_tab.py monta _EXTRATOR_POR_CASA pra TODA casa em
        # CASAS sem .get() - precisa da chave mesmo nunca sendo chamada.
        "extrator_texto": None,
        "motivo_indisponivel": "pagina institucional sem nenhum relatorio/RSS/API publico - distribuicao institucional sem canal aberto identificado",
    },
    {
        # Investigada em 2026-10-30 (pedido explicito do Rodrigo, expansao
        # do ecossistema de Research - Agora/Ativa/Andbank/Planner).
        #
        # Agora e' white-label da Bradesco (ver link "BFO - Bradesco Family
        # Office" na home institucional) com conteudo real de research numa
        # plataforma de terceiro ("Agora Insights", insights.
        # agorainvestimentos.com.br, plataforma Toolzz/LMS). robots.txt do
        # subdominio permite tudo ("User-agent: * " sem Disallow), e paginas
        # de detalhe de relatorio ja' conhecidas (ex: /play/text/6614139/
        # detalhe?school=visitantes) respondem 200 com titulo e um TEASER
        # curto reais, sem exigir login - confirmado com texto real
        # ("Estrategia para renda variavel: as Small Caps..."). Mas:
        # (1) o relatorio COMPLETO fica atras de carrinho de compra/
        #     pagamento ("Finalizar compra", mesmo texto de teaser) - e'
        #     paywall de verdade, nunca contornado aqui;
        # (2) a pagina de catalogo (/analisedeempresas-aberto) e' um SPA
        #     React que nao renderiza nenhum item no HTML puro (sem JS) e
        #     nenhum endpoint de API publico foi encontrado nos bundles JS
        #     (index-BPSgioq2.js e' so o shell); nenhum RSS, nenhum
        #     sitemap.xml (varias rotas tentadas, todas 404), nenhum
        #     Sitemap: no robots.txt. Google tem paginas individuais
        #     indexadas (confirma que ALGUM caminho de navegacao existe),
        #     mas raspar resultado de busca nao e' um mecanismo de
        #     descoberta aceitavel/estavel pra um coletor agendado.
        # Sem mecanismo de descoberta de item NOVO, nao da' pra implementar
        # um coletor de verdade (so' saberiamos reler um ID ja' conhecido,
        # nunca descobrir o relatorio de hoje) - registrado indisponivel
        # por ora, nao por bloqueio de borda e sim por falta de feed/API
        # publica de listagem. Revisitar se a Agora publicar RSS/sitemap/
        # API no futuro.
        "id": "agora_insights",
        "nome": "Ágora Insights",
        "fonte": "insights.agorainvestimentos.com.br (sem RSS/sitemap/API de listagem; relatorio completo pago)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "conteudo publico existe por item conhecido (teaser, sem login), mas sem RSS/sitemap/API de descoberta de relatorio novo e com texto completo pago (carrinho de compra) - nao ha' como um coletor agendado encontrar relatorio novo de forma confiavel",
    },
    {
        # Investigada em 2026-10-30: robots.txt do proprio dominio devolve
        # 403 (nem o robots.txt e' servido pro nosso User-Agent OU pra um
        # UA de navegador comum - mesmo resultado nos dois casos, varias
        # rotas testadas) - bloqueio de borda consistente, mesmo padrao de
        # Genial/XP (WAF/CDN), confirmado tambem no feed RSS pela sondagem
        # anterior de 22/10/2026 (docstring de montebravo.py: Ativa deu 403
        # no feed). Sem NENHUM endpoint respondendo, nao ha' fonte real pra
        # tentar coletar.
        "id": "ativa_investimentos",
        "nome": "Ativa Investimentos",
        "fonte": "ativainvestimentos.com.br (bloqueio de borda/WAF - 403 ate' no robots.txt)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "bloqueio de borda (403) em toda rota testada, inclusive robots.txt, com UA do projeto e UA de navegador comum - nenhum endpoint publico acessivel",
    },
    {
        # Investigada em 2026-10-30: o dominio brasileiro (andbank.com.br)
        # so' redireciona pro dominio global (andbank.com/brasil), cujo
        # robots.txt e' "Disallow: /" pra todo User-agent - proibe
        # explicitamente qualquer coleta automatizada do site inteiro,
        # independente do conteudo existir ou nao (a pagina carrega
        # normalmente, HTTP 200, mas o projeto respeita robots.txt sempre -
        # ver data/research/base.py:permitido). Nao foi encontrada secao de
        # research de acoes/recomendacoes (Andbank e' private
        # banking/gestao de patrimonio, nao corretora de varejo com
        # cobertura de acoes individuais).
        "id": "andbank_brasil",
        "nome": "Andbank Brasil",
        "fonte": "andbank.com/brasil (robots.txt proibe coleta - 'Disallow: /')",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "robots.txt do dominio ('Disallow: /') proibe qualquer coleta automatizada, independente de conteudo; nenhuma secao de research de acoes encontrada (perfil de private banking)",
    },
    {
        # Investigada em 2026-10-30: robots.txt de www.planner.com.br e'
        # "Disallow: /" pra todo User-agent - proibe coleta do site
        # inteiro. Nao investigamos conteudo alem disso (a proibicao no
        # robots.txt e' suficiente pra decidir, nao importa o que exista
        # atras dela - mesmo principio do Andbank acima).
        "id": "planner_investimentos",
        "nome": "Planner Investimentos",
        "fonte": "planner.com.br (robots.txt proibe coleta - 'Disallow: /')",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "robots.txt do dominio ('Disallow: /') proibe qualquer coleta automatizada do site inteiro",
    },
    {
        # Investigada em 12/11/2026 (missao Agente B, Grupo 1 - bancos
        # internacionais). O hub editorial publico existe
        # (ib.barclays/our-insights.html, varias sub-paginas: "Weekly
        # Insights", "Barclays Brief", "3-Point Perspective") e responde
        # sem bloqueio (HTTP 200, robots.txt permite), mas cada sub-pagina
        # e' uma unica pagina EVERGREEN (confirmado com "Weekly Insights":
        # so' 1 data no HTML, "06 Nov 2026", sem lista/arquivo de edicoes
        # anteriores) - os 4 blocos ld+json reais da pagina sao so'
        # metadado de Organization/WebSite, nenhum com headline/
        # datePublished por item. Sem um mecanismo de descoberta de ITEM
        # NOVO (sitemap, feed ou lista datada), um coletor agendado nao
        # teria como saber se o conteudo mudou - mesma logica de
        # "agora_insights" acima (nao e' bloqueio de borda, e' ausencia de
        # mecanismo de descoberta).
        "id": "barclays_insights",
        "nome": "Barclays Insights",
        "fonte": "ib.barclays/our-insights.html (sem mecanismo de descoberta de item novo)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "hub editorial publico existe mas cada secao e' 1 pagina evergreen sem arquivo/data por item - sem sitemap/feed proprio, nao ha' como descobrir relatorio novo de forma confiavel",
    },
    {
        # Investigada em 12/11/2026 (mesma missao acima). sitemap.xml do
        # dominio responde (robots.txt permite), mas e' majoritariamente
        # navegacional/institucional - a pagina www.hsbc.com/insights
        # devolve HTTP 404 (caminho nao existe mais) e
        # www.hsbc.com/news-and-insight carrega mas nao tem nenhum link
        # para sub-paginas no HTML estatico (renderizacao client-side) - 0
        # URLs "/news-and-insight/..." encontradas no sitemap de 339KB
        # (so' a pagina-indice e aparece). Sem orcamento de tempo pra
        # investigar mais a fundo (ex: achar o dominio/produto certo de
        # "HSBC Global Research" publico, se existir) nesta rodada -
        # registrada indisponivel por ora, revisitar se houver pista nova.
        "id": "hsbc_insights",
        "nome": "HSBC Global Viewpoint",
        "fonte": "hsbc.com/news-and-insight (nao confirmado - sem secao de insights descobrivel no orcamento desta rodada)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "pagina /insights da' HTTP 404 e /news-and-insight carrega mas e' renderizada client-side (0 sub-paginas no sitemap/HTML estatico) - nenhum mecanismo de descoberta encontrado no orcamento de tempo desta rodada; investigacao incompleta, nao e' veredito final",
    },
    {
        # Investigada em 12/11/2026 (mesma missao acima). O hub publico
        # "UBS CIO" (ubs.com/global/en/wealthmanagement/insights.html)
        # existe e carrega (HTTP 200); o sitemap.xml e' um indice bem
        # maior que o dos outros bancos (dezenas de sitemaps por
        # pais/idioma, o do "en" global sozinho tem 3.9MB e ~2400
        # ocorrencias de "/insights/"). Nao foi possivel, no orcamento de
        # tempo desta rodada, confirmar quais desses itens sao RECENTES
        # (o filtro por <lastmod> adjacente ao <loc> nao bateu no formato
        # real do arquivo - precisa de um parser mais cuidadoso da
        # estrutura) nem distinguir conteudo editorial atual de paginas
        # antigas (ha' itens de 2018-2024 misturados). Registrada
        # indisponivel por ora - candidata a revisitar com mais tempo de
        # investigacao, diferente de bloqueio de borda ou paywall.
        "id": "ubs_insights",
        "nome": "UBS CIO Insights",
        "fonte": "ubs.com/global/en/wealthmanagement/insights.html (nao confirmado - sitemap multi-pais nao analisado por completo no orcamento desta rodada)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "hub publico existe mas o sitemap real e' um indice multi-pais/idioma muito grande (3.9MB so' pro 'en' global); nao foi possivel confirmar recencia/estrutura dos itens no orcamento de tempo desta rodada - investigacao incompleta, nao e' veredito final",
    },
    {
        # Investigada em 12/11/2026 (missao Agente B, Grupo 2 - research
        # de acoes do Safra, alem da carteira recomendada ja' coberta por
        # data/research/safra_carteiras.py). Reconfirma o achado de
        # 22/10/2026 (docs/research-fontes-20261022.md): o portal
        # "O Especialista" (oespecialista.safra.com.br) devolve HTTP 403
        # tanto no robots.txt quanto no feed RSS (/feed/), deste ambiente
        # e com o mesmo User-Agent do projeto - bloqueio de borda
        # consistente, sem mudanca desde a sondagem anterior.
        "id": "safra_research",
        "nome": "Safra O Especialista",
        "fonte": "oespecialista.safra.com.br (bloqueio de borda - HTTP 403 no robots.txt e no feed)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "HTTP 403 no robots.txt e no feed RSS, reconfirmado em 12/11/2026 (mesmo bloqueio de borda de 22/10/2026) - sem mudanca; carteira recomendada do Safra continua coletada separadamente em data/research/safra_carteiras.py",
    },
    {
        # Investigada em 12/11/2026 (mesma missao acima, BB Investimentos
        # ainda nao tinha sido investigada - ver comentario de 2026-10-29
        # acima). O portal "BB Investalk" (investalk.bb.com.br) nao
        # bloqueia mais (HTTP 200 em toda rota testada, diferente do 403
        # de 22/10/2026 no /feed/ e /wp-json/) e tem um sitemap.xml real,
        # mas ele so' lista paginas de NAVEGACAO (ex: "/noticias",
        # "/relatorios-e-analises", "/carteiras-sugeridas" - sem nenhuma
        # URL de item individual). A pagina "/relatorios-e-analises"
        # carrega (1.25MB de HTML) mas nao tem nenhum link
        # "/noticias/onde-investir/..." no HTML estatico nem
        # __NEXT_DATA__/JSON embutido - catalogo client-side (XHR), sem
        # API publica encontrada nos bundles carregados. Sem mecanismo de
        # descoberta de item novo (mesma logica de "agora_insights" e
        # "barclays_insights" acima).
        "id": "bb_investimentos",
        "nome": "BB Investimentos (Investalk)",
        "fonte": "investalk.bb.com.br/relatorios-e-analises (sem mecanismo de descoberta de item novo)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "paginas carregam sem bloqueio, mas o sitemap so' lista navegacao (sem item individual) e o catalogo de relatorios e' renderizado client-side sem API publica encontrada - sem sitemap/feed/API de listagem, nao ha' como descobrir relatorio novo de forma confiavel",
    },
    {
        # Investigada em 12/11/2026 (missao Agente B, Grupo 3 -
        # independentes). O feed publico (suno.com.br/feed/) existe e
        # responde (RSS real, robots.txt permite), mas e' o blog GERAL do
        # site (conteudo educacional: "Financas pessoais: guia completo",
        # "O que e' CDB" etc.), nao analise de acoes. O subdominio/secao
        # "Suno Analitica" (suno.com.br/analitica/, com sitemaps proprios
        # "acao-sitemap.xml"/"bdr-sitemap.xml"/"fiis-sitemap.xml") tem 1
        # pagina POR TICKER (ex: /analitica/acoes/itub4/), mas cada pagina
        # e' um perfil de COTACAO (schema.org WebPage/Article generico,
        # "dateModified" atualizado todo dia so' pela cotacao mudar, nao
        # por um relatorio novo ter sido publicado) - confirmado com o
        # ld+json real da pagina ITUB4, sem nenhum item de analise datado
        # dentro. Sem um feed/sitemap que liste RELATORIOS individuais
        # (so' cotacoes por ticker), nao ha' como diferenciar "relatorio
        # novo" de "cotacao atualizada hoje".
        "id": "suno_research",
        "nome": "Suno Research",
        "fonte": "suno.com.br/analitica (paginas sao perfil de cotacao por ticker, nao relatorio datado)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "feed publico e' o blog educacional geral (nao analise de acoes); as paginas por ticker de 'Suno Analitica' sao perfil de cotacao continuamente atualizado (dateModified muda por cotacao, nao por relatorio novo) - sem um feed/sitemap de RELATORIOS individuais, nao ha' como distinguir relatorio novo de atualizacao de cotacao",
    },
    {
        # Investigada em 12/11/2026 (mesma missao acima). O dominio real
        # da empresa (elevenfinancial.com.br, confirmado pelo <title>
        # "ELEVEN FINANCIAL" na resposta real) carrega sem bloqueio, mas e'
        # uma SPA client-side (bundle JS de inicializacao de popups/
        # tracking no HTML, sem nenhum link de navegacao no HTML
        # estatico). "/sitemap.xml" e "/sitemap_index.xml" devolvem o
        # MESMO HTML da home (fallback de rota SPA, nao um sitemap real) -
        # nenhum XML valido encontrado. Sem conseguir enumerar nenhuma
        # pagina de research no orcamento de tempo desta rodada, nao ha'
        # fonte coletavel identificada - investigacao incompleta (um
        # endpoint de API client-side pode existir e nao foi encontrado),
        # nao e' veredito final de bloqueio.
        "id": "eleven_financial",
        "nome": "Eleven Financial",
        "fonte": "elevenfinancial.com.br (SPA client-side - nenhum sitemap/listagem real encontrado no orcamento desta rodada)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "site carrega sem bloqueio mas e' renderizado inteiramente client-side (SPA); '/sitemap.xml' cai no fallback de rota SPA (mesmo HTML da home, nao XML real) - nenhuma pagina de research nem API publica encontrada no orcamento de tempo desta rodada",
    },
    {
        # Investigada em 12/11/2026 (mesma missao acima). Nao foi possivel
        # nem ESTABELECER UMA CONEXAO HTTPS com o dominio oficial
        # (www.terrainvestimentos.com.br, confirmado via busca como o site
        # real da casa) deste ambiente - erro de certificado TLS
        # ("Hostname mismatch... not valid for
        # 'terrainvestimentos.com.br'") em toda tentativa, inclusive com
        # verificacao de certificado desligada. Diferente das outras
        # casas desta lista (onde a pagina carrega e falta so' o
        # mecanismo de descoberta, ou ha' bloqueio HTTP explicito), aqui
        # nem a camada de rede/TLS completa deste ambiente - limitacao
        # honesta do ambiente de investigacao, nao um veredito sobre a
        # fonte em si (mesmo princípio ja' documentado pra outras
        # ferramentas indisponiveis no projeto, ex: Genial/XP via
        # WebFetch em 22/10/2026).
        "id": "terra_investimentos",
        "nome": "Terra Investimentos",
        "fonte": "terrainvestimentos.com.br (falha de TLS neste ambiente - nao foi possivel conectar)",
        "ativa_por_padrao": False,
        "disponivel": False,
        "extrator_texto": None,
        "motivo_indisponivel": "falha de certificado TLS ao conectar neste ambiente ('Hostname mismatch'), mesmo com verificacao desligada - nao foi possivel buscar nenhuma pagina do dominio; limitacao do ambiente de investigacao, nao um veredito sobre bloqueio/disponibilidade da fonte",
    },
]


def coletar_casa(casa: dict) -> tuple[int, bool]:
    """Busca relatorios de uma casa na fonte real e grava no Supabase
    (upsert por link, coletado_em=agora). Retorna (n_itens, ok) - ok=False
    se a fonte ou o Supabase falharem. Funcao separada (nao inline no
    fluxo de leitura da UI) pra poder ser chamada tambem por um job
    agendado no futuro (GitHub Actions, fase opcional do roadmap), sem
    depender da UI nem do gate de 30min - so import data.research e chama
    coletar_casa(casa) ou coletar_todas_disponiveis() direto.

    Print() de proposito (nao logging): Streamlit Cloud captura stdout no
    painel de Logs - da pra conferir dali se a fonte esta respondendo a
    partir do servidor do Cloud (pode se comportar diferente do ambiente
    local, ex: bloqueio de WAF por IP/regiao).

    Metricas de resiliencia (auditoria de arquitetura 2026-11-12, pedido
    Rodrigo): `tempo_s` (duracao real desta chamada), `publicacoes_
    encontradas` (quantas obter_relatorios() devolveu), `documentos_
    extraidos` (quantas de fato foram SALVAS - 0 se a persistencia
    falhar, nunca conta como "extraido" so' por ter sido encontrado) e
    `duplicidades` (links repetidos dentro do MESMO lote, ver
    store.contar_duplicados) vao pra registrar_tentativa, que so' SOMA
    aos contadores cumulativos (coletores_status.taxa_sucesso/
    tempo_medio_s) - nunca inventa um numero que esta funcao nao mediu de
    verdade."""
    inicio = time.monotonic()
    itens = casa["obter_relatorios"]()
    duracao = time.monotonic() - inicio
    # registro de SAUDE DOS DADOS (ver data/saude_dados.py/coletores_status.py)
    # - mesmo padrao ja usado em data/news.py, data/mercado.py, data/macro.py,
    # data/cvm.py: registra no PONTO REAL de coleta, nao em quem chama, pra
    # cobrir tanto a coleta ao vivo (genial_lives, via coletar_pendentes) quanto
    # a coleta standalone (coletor_local.py, via coletar_todas_disponiveis).
    if itens is None:
        print(f"[research] coleta {casa['nome']} falhou apos {duracao:.1f}s")
        motivo_especifico = None
        obter_motivo = casa.get("motivo_falha")
        if obter_motivo is not None:
            try:
                motivo_especifico = obter_motivo()
            except Exception:
                motivo_especifico = None
        erro = f"obter_relatorios retornou None apos {duracao:.1f}s"
        if motivo_especifico:
            erro = f"{erro}; {motivo_especifico}"
        registrar_tentativa(
            casa["nome"], casa.get("fonte", casa["nome"]), execucao_ok=False,
            erro=erro, categoria="Research",
            tempo_s=duracao, publicacoes_encontradas=0, documentos_extraidos=0, duplicidades=0,
        )
        return 0, False
    duplicidades = store.contar_duplicados(itens)
    ok = store.salvar_itens(itens)
    print(f"[research] coleta {casa['nome']}: {len(itens)} itens em {duracao:.1f}s (salvou={ok})")
    registrar_tentativa(
        casa["nome"], casa.get("fonte", casa["nome"]), execucao_ok=True,
        persistencia_ok=ok, registros_novos=len(itens), categoria="Research",
        tempo_s=duracao, publicacoes_encontradas=len(itens),
        documentos_extraidos=len(itens) if ok else 0, duplicidades=duplicidades,
    )
    return len(itens), ok


def _classificar_falha(casa: dict) -> str:
    """Classifica a falha de `casa` (so' chamada quando coletar_casa
    devolveu ok=False) pra coletor_local.py decidir se ela sozinha deve
    derrubar o exit code (ver _falha_critica la'). Regra dura (pedido
    explicito, achado real auditoria 2026-10-18): 'bloqueio_externo_
    conhecido' SO' quando a casa expoe 'categoria_falha' (callable) E ele
    devolve exatamente essa string - campo ausente, excecao ao chamar, ou
    qualquer valor diferente (incluindo None/vazio) sempre volta 'erro'.
    Nunca usa um flag estatico por casa (ex: 'essa casa e bloqueada,
    ignora falha dela') - a classificacao e' sempre da falha ESPECIFICA
    que aconteceu agora, lida do motivo real (ver categoria_ultima_falha
    em genial.py/xp.py) - uma falha nova/diferente na mesma casa (ex: a
    XP comecar a devolver HTTP 500 em vez do 403 do Akamai) continua
    'erro', nao fica mascarada so' porque a casa 'e' conhecida por
    falhar'."""
    obter_categoria = casa.get("categoria_falha")
    if obter_categoria is None:
        return "erro"
    try:
        categoria = obter_categoria()
    except Exception:
        return "erro"
    return categoria if categoria == "bloqueio_externo_conhecido" else "erro"


# Mesmo cooldown do path do app ao vivo (_COOLDOWN_FALHA_S acima) -
# coletor_local.py roda como PROCESSO NOVO a cada chamada (agendador do
# sistema), diferente do servidor do Cloud (st.cache_resource sobrevive
# entre reruns no MESMO processo); por isso este cooldown le' a ULTIMA
# TENTATIVA PERSISTIDA (coletores_status), nunca um dict em memoria.
_COOLDOWN_BLOQUEIO_CONHECIDO_S = 10 * 60


def _bloqueio_conhecido_em_cooldown(casa: dict) -> str | None:
    """Achado real (auditoria SAUDE DOS DADOS 2026-10-26, P2 Genial/XP):
    coletar_todas_disponiveis() nao tinha NENHUM cooldown - cada execucao
    de coletor_local.py (processo novo) tentava de novo as ~4 tentativas/
    20s de orcamento (genial.py)/~15s (xp.py) mesmo quando a ULTIMA
    tentativa real, ja' persistida em coletores_status, foi exatamente o
    MESMO bloqueio de borda ja' documentado (WAF Akamai/CDN Akamai) ha'
    poucos minutos - tentativa inutil, sem nenhuma informacao nova desde
    a ultima vez.

    Devolve o `ultimo_erro` persistido (pra log) quando: a casa declara
    `marcador_bloqueio_conhecido` (so' Genial/XP, ver CASAS); a ULTIMA
    tentativa registrada falhou (execucao_ok=False) E contem esse
    marcador exato; e essa tentativa foi ha' menos de
    _COOLDOWN_BLOQUEIO_CONHECIDO_S. None (sempre tenta de novo) em
    qualquer outro caso - casa sem o campo, nunca tentou, ultimo
    resultado foi sucesso, falha SEM o marcador (erro novo/diferente -
    nunca mascara uma mudanca real), ou cooldown ja' expirado."""
    marcador = casa.get("marcador_bloqueio_conhecido")
    if not marcador:
        return None
    status = obter_status(casa["nome"])
    if not status or status.get("execucao_ok") is not False:
        return None
    erro = status.get("ultimo_erro") or ""
    if marcador not in erro:
        return None
    tentativa_em = status.get("ultima_tentativa_em")
    if not tentativa_em:
        return None
    try:
        quando = datetime.fromisoformat(str(tentativa_em).replace("Z", "+00:00"))
    except ValueError:
        return None
    if (datetime.now(timezone.utc) - quando).total_seconds() >= _COOLDOWN_BLOQUEIO_CONHECIDO_S:
        return None
    return erro


def coletar_todas_disponiveis() -> dict:
    """Coleta (sem gate de tempo) todas as casas marcadas como disponiveis.
    Pensada pra ser chamada por um job agendado, nao pelo app ao vivo (o
    app usa obter_relatorios_unificado, que respeita o gate de 30min).
    Retorna {nome_da_casa: {'coletados': N, 'ok': bool, 'categoria_falha':
    str | None}} - 'categoria_falha' so' e' diferente de None quando
    ok=False (ver _classificar_falha); usado por coletor_local.py pra
    decidir o exit code sem derrubar a build por um bloqueio externo ja'
    documentado (ex: Akamai na Genial/XP), mas sem mascarar nenhuma falha
    nova ou falha de persistencia (que continua sempre 'erro').

    Pula a tentativa cara (sem chamar obter_relatorios) quando o MESMO
    bloqueio conhecido ja' foi confirmado ha' poucos minutos (ver
    _bloqueio_conhecido_em_cooldown) - NUNCA chama registrar_tentativa de
    novo nesse caso (a tentativa real/persistida continua sendo a
    anterior; pular nao e' uma nova tentativa).

    Correcao real (revisao independente 2026-10-26, achado na PR #177):
    uma excecao inesperada so' na VERIFICACAO do cooldown (ex: timestamp
    persistido sem timezone, Supabase devolvendo formato inesperado)
    propagava e abortava este for inteiro - impedindo a coleta de TODAS
    as casas seguintes na lista (genial_lives, btg, montebravo, nord),
    nao so' a casa que falhou a verificacao. Agora essa falha e' isolada
    por casa: trata como 'sem bloqueio conhecido confirmado' (sempre
    tenta a coleta normal dessa casa) e nunca impede as demais. Nunca
    esconde excecao real da COLETA em si (coletar_casa abaixo continua
    sem nenhum try/except novo)."""
    resultado = {}
    for casa in CASAS:
        if not casa["disponivel"]:
            continue
        try:
            bloqueio = _bloqueio_conhecido_em_cooldown(casa)
        except Exception as exc:
            print(f"[research] falha ao verificar cooldown de {casa['nome']} (tentando coleta normal): {exc!r}")
            bloqueio = None
        if bloqueio:
            print(f"[research] pulando {casa['nome']}: bloqueio conhecido confirmado há poucos minutos ({bloqueio})")
            resultado[casa["nome"]] = {"coletados": 0, "ok": False, "categoria_falha": "bloqueio_externo_conhecido"}
            continue
        coletados, ok = coletar_casa(casa)
        entrada = {"coletados": coletados, "ok": ok, "categoria_falha": None}
        if not ok:
            entrada["categoria_falha"] = _classificar_falha(casa)
        resultado[casa["nome"]] = entrada
    return resultado


def preparar_leitura(casas_ativas=None):
    """So a leitura do que ja esta salvo no Supabase (rapida, sem tocar em
    nenhuma fonte externa) - pensada pra UI desenhar a tela imediatamente
    com isso antes de tentar coletar algo novo. Retorna (relatorios,
    falhas, casas_para_coletar, nomes_para_ler):
    - falhas: casas indisponiveis ou erro de leitura do banco;
    - casas_para_coletar: casas ativas+disponiveis cuja ultima coleta
      salva tem mais de 30min (store.precisa_recoletar) - quem chama
      decide se/quando coletar (ver coletar_pendentes);
    - nomes_para_ler: nomes de casa usados pra reler o banco depois de
      coletar (ver ler_itens_salvos)."""
    if casas_ativas is None:
        casas_ativas = [c["id"] for c in CASAS if c["ativa_por_padrao"]]

    falhas = []
    nomes_para_ler = []
    casas_para_coletar = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas:
            continue
        if not casa["disponivel"]:
            falhas.append(f"{casa['nome']} ({casa.get('motivo_indisponivel', 'indisponível')})")
            continue
        nomes_para_ler.append(casa["nome"])
        if not casa.get("tentar_coleta_automatica", True):
            continue
        if store.precisa_recoletar(casa["nome"]):
            casas_para_coletar.append(casa)

    if not nomes_para_ler:
        return [], falhas, casas_para_coletar, nomes_para_ler

    relatorios = store.listar_itens(nomes_para_ler)
    if relatorios is None:
        falhas.append("Supabase (leitura do research)")
        return [], falhas, casas_para_coletar, nomes_para_ler
    return relatorios, falhas, casas_para_coletar, nomes_para_ler


def ler_itens_salvos(nomes: list):
    """So a leitura do banco (sem gate nem coleta) - usado pra reler apos
    coletar_pendentes(). None se o banco estiver fora do ar."""
    return store.listar_itens(nomes)


def ultimas_coletas_formatadas(casas_ativas: list) -> str:
    """Texto "última coleta: <casa> hh:mm · <casa> hh:mm" (fuso
    America/Sao_Paulo) com o horario da ultima coleta BEM-SUCEDIDA de
    cada casa ativa+disponivel - transparencia de quando os dados foram
    atualizados de verdade. Especialmente util quando a coleta pelo
    proprio servidor (Cloud) esta bloqueada e quem mantem os dados
    frescos e' o coletor_local.py rodando na maquina do usuario (ver
    coletor_local.py e docs/agendador_tarefas.md)."""
    from zoneinfo import ZoneInfo

    tz_br = ZoneInfo("America/Sao_Paulo")
    partes = []
    for casa in CASAS:
        if casa["id"] not in casas_ativas or not casa["disponivel"]:
            continue
        ultima = store.ultima_coleta_em(casa["nome"])
        if ultima is None:
            partes.append(f"{casa['nome']}: nunca")
        else:
            partes.append(f"{casa['nome']}: {ultima.astimezone(tz_br).strftime('%d/%m %H:%M')}")
    return " · ".join(partes)


@st.cache_resource(show_spinner=False)
def _cooldown_coleta() -> CooldownPorChave:
    """Cooldown de PROCESSO por casa_id (mais a chave especial
    '_limpeza', ver coletar_pendentes) - st.cache_resource = estado
    compartilhado entre sessoes e reruns no MESMO processo do servidor
    (reseta em redeploy).

    Generalizado em data/research/base.py:CooldownPorChave (auditoria de
    arquitetura 2026-11-12) - antes vivia so' aqui como um dict cru
    (`_ultimas_tentativas`). A janela padrao da instancia e'
    _COOLDOWN_FALHA_S (cooldown por casa); a chave '_limpeza' usa uma
    janela DIFERENTE e maior (_INTERVALO_LIMPEZA_S), passada
    explicitamente em cada chamada (CooldownPorChave.em_cooldown aceita
    `janela_s` por chamada) - mesma estrutura compartilhada, sem precisar
    de 2 caches/dicts separados."""
    return CooldownPorChave(_COOLDOWN_FALHA_S)


_INTERVALO_LIMPEZA_S = 60 * 60  # limpeza de itens antigos roda no maximo 1x por hora


def coletar_pendentes(casas: list) -> list:
    """Coleta uma lista de casas (ja filtradas como pendentes por
    preparar_leitura), respeitando um orcamento total de tempo
    (base.TEMPO_MAX_COLETA_S) e um cooldown por casa desde a ultima
    tentativa (_COOLDOWN_FALHA_S) - se estourar o orcamento, ou se a casa
    tiver falhado ha pouco tempo, pula e deixa pra proxima chamada (a
    casa nao coletada continua 'pendente' porque seu coletado_em nao foi
    atualizado). Retorna as falhas (nomes de casa que nao atualizaram,
    por erro, cooldown ou tempo esgotado).

    Tambem aproveita esse ponto de atividade pra rodar a limpeza de itens
    com mais de store.RETENCAO_DIAS (store.apagar_itens_antigos),
    throttled a 1x por hora (_INTERVALO_LIMPEZA_S) via a mesma instancia
    de cooldown - nao vale a pena bater no banco toda vez so' pra isso."""
    cooldown = _cooldown_coleta()
    if not cooldown.em_cooldown("_limpeza", janela_s=_INTERVALO_LIMPEZA_S):
        store.apagar_itens_antigos()
        cooldown.marcar_tentativa("_limpeza")

    falhas = []
    limite = time.monotonic() + TEMPO_MAX_COLETA_S
    for casa in casas:
        if cooldown.em_cooldown(casa["id"]):
            falhas.append(f"{casa['nome']} (tentativa recente, aguardando)")
            continue
        if time.monotonic() > limite:
            falhas.append(f"{casa['nome']} (tempo esgotado)")
            continue
        _, ok = coletar_casa(casa)
        cooldown.marcar_tentativa(casa["id"])
        if not ok:
            falhas.append(casa["nome"])
    return falhas
