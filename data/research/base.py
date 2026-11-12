# -*- coding: utf-8 -*-
"""Utilitarios compartilhados pelos coletores de research: headers de
requisicao, timeouts, checagem de robots.txt antes de qualquer coleta, e
(auditoria de arquitetura, PR Agente A, 2026-11-12) o CONTRATO padrao de
registro + utilitarios de orquestracao reaproveitaveis entre casas.

CONTRATO PADRAO DE ITEM (ver `normalizar_item` abaixo): todo coletor
(`<casa>.py:obter_relatorios()`) devolve uma lista de dicts com, no
MINIMO, os campos abaixo (os 3 primeiros ja eram obrigatorios antes desta
auditoria - `data/research/store.py:salvar_itens` acessa direto, sem
`.get()`):

    casa, titulo, tipo, link   (obrigatorios - store.salvar_itens falha
                                 com KeyError sem eles, de proposito:
                                 nunca persiste um item sem identidade
                                 minima)
    data, autor, tickers       (opcionais há mais tempo - `.get()` com
                                 fallback em todo consumidor)
    publicado_em                (opcional, fase 3 - timestamp completo,
                                 ver data/research/genial_lives.py)

Campos NOVOS do contrato ampliado (pedido Rodrigo, missao arquitetura
2026-11-12 - ver auditoria da PR): `empresa`, `setor`, `preco_referencia`,
`horizonte`, `texto_integral_disponivel`. Nenhum coletor existente foi
OBRIGADO a passar a preenche-los (seria reescrever 11 adapters so' pra
isso, risco de regressao sem beneficio imediato) - `normalizar_item`
preenche o que faltar com um default seguro (None/False, NUNCA um valor
inventado) antes de persistir, e `data/research/store.py:salvar_itens` ja
sabe mandar essas colunas pro Supabase quando presentes (aditivo, mesmo
padrao defensivo ja usado pra `publicado_em`/`riscos` - se a coluna ainda
nao existir no banco de quem esta rodando, tenta de novo sem elas, nunca
quebra a coleta de TODAS as casas por isso). `analista`/`ticker`
(singular, do pedido original) nao ganharam coluna nova: o projeto ja usa
`autor` (mesmo papel de `analista`) e `tickers` (lista, mais geral que
`ticker` singular - 1 relatorio pode cobrir mais de 1 ativo) - ver
mapeamento completo no dict `CAMPOS_CANONICOS_PARA_STORE` abaixo. Casas
NOVAS (fora desta missao) devem preencher o que souberem de verdade; o
resto fica None/False ate' existir uma fonte real pra preencher - nunca
inventado so' pra bater o contrato."""

import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

import requests
import streamlit as st

HEADERS = {"User-Agent": "PregaoApp/0.1 (uso pessoal, nao comercial; contato via github)"}
TIMEOUT = 10  # segundos por requisicao HTTP individual (robots.txt, home da casa, download de relatorio)
TEMPO_MAX_COLETA_S = 25  # orcamento total pra coletar todas as casas pendentes numa unica abertura da aba
TTL_COLETA = 30 * 60  # 30 min, conforme pedido


@st.cache_resource(show_spinner=False)
def _robots_parser(dominio: str):
    """Baixa e parseia o robots.txt com timeout explicito - RobotFileParser.
    read() sozinho usa urlopen sem timeout, que pode ficar pendurado
    indefinidamente se o dominio nao responder (ja aconteceu em teste)."""
    rp = RobotFileParser()
    rp.set_url(f"https://{dominio}/robots.txt")
    try:
        r = requests.get(f"https://{dominio}/robots.txt", headers=HEADERS, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None
        rp.parse(r.text.splitlines())
    except Exception:
        return None
    return rp


def permitido(url: str) -> bool:
    """Confere o robots.txt do dominio antes de coletar. Se o robots.txt
    nao puder ser lido (erro, timeout ou ausente), assume permitido (mesmo
    comportamento 'fail open' do RobotFileParser padrao)."""
    dominio = urlparse(url).netloc
    rp = _robots_parser(dominio)
    if rp is None:
        return True
    return rp.can_fetch(HEADERS["User-Agent"], url)


# ============================================================
# Contrato padrao de item (auditoria de arquitetura 2026-11-12)
# ============================================================

# Campos opcionais do contrato ampliado - normalizar_item preenche o que
# faltar com este default (nunca inventa valor real). 'ticker'/'analista'
# do pedido original nao entram aqui de proposito (ver docstring do
# modulo): ja existem como 'tickers' (lista) e 'autor'.
_DEFAULTS_CAMPOS_OPCIONAIS = {
    "empresa": None,
    "setor": "",
    "preco_referencia": None,
    "horizonte": None,
    "texto_integral_disponivel": False,
    "autor": "",
    "tickers": (),
    "data": "",
    "publicado_em": None,
    "recomendacao": None,
    "preco_alvo": None,
}

CAMPOS_OBRIGATORIOS_ITEM = ("casa", "titulo", "tipo", "link")

# Documenta o mapeamento entre o vocabulario do pedido original (Rodrigo,
# missao 2026-11-12) e as colunas reais de research_itens (nunca duas
# colunas pro mesmo conceito) - usado so' como referencia/teste de
# contrato, nao executado em runtime.
CAMPOS_CANONICOS_PARA_STORE = {
    "casa": "casa", "analista": "autor", "empresa": "empresa",
    "ticker": "tickers", "setor": "setor", "data_publicacao": "data",
    "tipo_relatorio": "tipo", "recomendacao": "recomendacao",
    "preco_alvo": "preco_alvo", "preco_referencia": "preco_referencia",
    "horizonte": "horizonte", "url_fonte": "link",
    "texto_integral_disponivel": "texto_integral_disponivel",
}


def validar_item(item: dict) -> list:
    """Campos OBRIGATORIOS (ver CAMPOS_OBRIGATORIOS_ITEM) ausentes/vazios
    em `item` - [] se o item e' valido. Checagem pura, sem rede/banco;
    pensada pra um coletor novo se auto-validar antes de devolver a lista
    pra `coletar_casa` (ou pra teste), nunca para persistencia em si
    (store.salvar_itens continua sendo a autoridade final - ver seu
    proprio tratamento de KeyError)."""
    faltantes = []
    for campo in CAMPOS_OBRIGATORIOS_ITEM:
        valor = item.get(campo) if isinstance(item, dict) else None
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltantes.append(campo)
    return faltantes


def normalizar_item(item: dict) -> dict:
    """Devolve uma COPIA de `item` com todo campo OPCIONAL do contrato
    ampliado presente (preenchido com o default seguro de
    _DEFAULTS_CAMPOS_OPCIONAIS quando ausente) - nunca sobrescreve um
    valor real já presente, nunca inventa um valor novo, só garante que a
    CHAVE existe (consumidores podem usar item['setor'] direto, sem
    `.get()` defensivo em todo lugar). Os campos OBRIGATORIOS (ver
    CAMPOS_OBRIGATORIOS_ITEM) não são tocados aqui - item sem eles
    continua invalido (ver validar_item); normalizar_item nunca mascara
    essa falta."""
    normalizado = dict(item)
    for campo, default in _DEFAULTS_CAMPOS_OPCIONAIS.items():
        if campo not in normalizado:
            normalizado[campo] = default
    return normalizado


# ============================================================
# Retry com backoff (pedido Rodrigo: "retry automatico com backoff")
# ============================================================

def requisitar_com_retry(
    fn: Callable,
    tentativas: int = 2,
    espera_inicial_s: float = 0.5,
    fator_backoff: float = 2.0,
    excecoes: tuple = (Exception,),
    dormir: Callable[[float], None] = None,
):
    """Chama `fn()` (sem argumentos - quem chama fecha os argumentos
    reais num lambda/partial) ate' `tentativas` vezes, com espera
    exponencial entre elas (espera_inicial_s, depois x fator_backoff,
    x fator_backoff^2, ...). So' retenta excecoes que casem `excecoes`
    (por padrao, qualquer Exception) - outra excecao propaga na hora, sem
    retry. Se TODAS as tentativas falharem, relanca a ULTIMA excecao (quem
    chama decide o que fazer, mesmo padrao de deixar o try/except de cada
    coletor classificar o erro). `dormir` e' injetavel pra teste (evita
    sleep de verdade); por padrao usa time.sleep.

    Nunca usado pra HTTP 404/403 (erro PERMANENTE, retry nao ajuda e so'
    desperdica orcamento de tempo) - so' pra excecao de rede/timeout de
    verdade (ConnectionError, Timeout etc.), decisao deliberada (ver
    coletar_via_sitemap abaixo: so' a requisicao do SITEMAP usa isto; a
    busca de cada pagina individual NAO retenta - 1 pagina lenta/instavel
    nao deve consumir 2x o orcamento de tempo de TODAS as paginas daquela
    casa)."""
    dormir = dormir or time.sleep
    espera = espera_inicial_s
    ultimo_exc = None
    for tentativa in range(1, max(1, tentativas) + 1):
        try:
            return fn()
        except excecoes as exc:
            ultimo_exc = exc
            if tentativa >= tentativas:
                break
            dormir(espera)
            espera *= fator_backoff
    raise ultimo_exc


# ============================================================
# Cooldown generico por chave (generaliza o padrao ja usado em
# data/research/__init__.py:_ultimas_tentativas antes desta auditoria)
# ============================================================

class CooldownPorChave:
    """Registra time.monotonic() da ultima tentativa (sucesso OU falha)
    por chave, em memoria (dict simples - quem quiser persistencia entre
    processos, como coletor_local.py precisa, continua usando o registro
    PERSISTIDO em coletores_status, ver _bloqueio_conhecido_em_cooldown
    em data/research/__init__.py - este cooldown aqui e' so' o de
    PROCESSO/sessao, equivalente ao _COOLDOWN_FALHA_S original).

    Extraido de data/research/__init__.py (achado real da auditoria de
    arquitetura 2026-11-12: a logica de "nao tenta de novo antes de N
    segundos desde a ultima tentativa" so' existia hard-coded dentro de
    coletar_pendentes - generalizada aqui pra poder ser testada isolada e,
    se algum coletor novo precisar do mesmo padrao fora do fluxo de
    CASAS/coletar_pendentes, reaproveitada sem copiar a logica de novo)."""

    def __init__(self, janela_s: float):
        self.janela_s = janela_s
        self._tentativas: dict = {}

    def em_cooldown(self, chave, janela_s: float = None) -> bool:
        """`janela_s` sobrescreve self.janela_s so' pra ESTA chamada -
        permite a mesma instancia/dict compartilhar chaves com janelas
        DIFERENTES (ex: cooldown por casa de 10min e throttle de limpeza
        de 1h na mesma estrutura, caso real de
        data/research/__init__.py:coletar_pendentes)."""
        ultima = self._tentativas.get(chave)
        if ultima is None:
            return False
        janela = self.janela_s if janela_s is None else janela_s
        return (time.monotonic() - ultima) < janela

    def marcar_tentativa(self, chave) -> None:
        self._tentativas[chave] = time.monotonic()

    def tempo_restante_s(self, chave, janela_s: float = None) -> float:
        """0 se nao estiver em cooldown; segundos restantes caso
        contrario - so' pra log/diagnostico, nunca usado pra decisao."""
        ultima = self._tentativas.get(chave)
        if ultima is None:
            return 0.0
        janela = self.janela_s if janela_s is None else janela_s
        restante = janela - (time.monotonic() - ultima)
        return max(0.0, restante)


# ============================================================
# Orquestracao generica "sitemap + N paginas individuais" (auditoria
# 2026-11-12: jpmorgan.py/bankofamerica.py/citi.py/morgan_stanley.py/
# nord.py tinham literalmente o MESMO obter_relatorios()/testar_conexao()
# - ~45 e ~12 linhas cada, copiadas ao escrever cada casa nova - so' o
# PARSER de candidatos/item mudava (formato de pagina diferente: painel
# HTML, ld+json, meta tag). Extraido aqui pra as 5 casas pararem de
# divergir silenciosamente (achado real: nord.py tinha ficado SEM
# testar_conexao() nessa copia - ver data/diagnostico.py, agora corrigido
# junto). Comportamento PRESERVADO byte a byte nas mensagens de
# motivo_falha testadas (tests/test_research_<casa>.py) - esta extracao
# NAO muda nenhum resultado observavel, so' onde o codigo mora.
# ============================================================

def testar_conexao_url(url: str, permitido_fn: Callable[[str], bool], timeout: float = 5) -> tuple:
    """Testa so' se `url` responde (GET simples, sem interpretar o
    conteudo) - usado tanto pro sitemap de uma casa quanto pro feed RSS de
    outra (mesma checagem, URL diferente). Retorna (ok, detalhe)."""
    if not permitido_fn(url):
        return False, "bloqueado pelo robots.txt"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"OK ({len(r.content)} bytes)"


@dataclass
class ResultadoSitemap:
    itens: list | None
    motivo_falha: str | None


def coletar_via_sitemap(
    *,
    sitemap_url: str,
    candidatos_do_sitemap: Callable[[bytes], list],
    parser_item: Callable,
    permitido_fn: Callable[[str], bool],
    passar_lastmod_ao_parser: bool = False,
    sitemap_timeout: float = 15,
    pagina_timeout: float = 10,
    orcamento_total_s: float = 20,
    max_itens: int = 8,
    descricao_esperada: str = "com o metadado esperado",
    log_prefixo: str = "research",
    retentar_sitemap: bool = True,
) -> tuple:
    """Implementacao generica do padrao "sitemap + N paginas individuais,
    com orcamento de tempo e robots.txt" (ver docstring da secao acima).
    `candidatos_do_sitemap(conteudo_bytes) -> [(lastmod, loc), ...]` e
    `parser_item(html, loc)` ou `parser_item(html, loc, lastmod)` (se
    `passar_lastmod_ao_parser=True`) continuam especificos de cada casa -
    so' a ORQUESTRACAO (ordem das checagens, orcamento, limite de itens,
    classificacao de motivo_falha) e' compartilhada.

    `permitido_fn` e' SEMPRE a referencia `permitido` do MODULO QUE CHAMA
    (nunca `base.permitido` direto) - importante pra teste: os testes
    existentes (tests/test_research_<casa>.py) fazem
    `patch.object(<modulo_da_casa>, "permitido", ...)`, que so' troca o
    nome `permitido` DENTRO daquele modulo; se este helper usasse
    `base.permitido` fixo, esse patch deixaria de ter efeito e os testes
    tentariam uma chamada de rede de verdade. Cada adapter continua
    passando `permitido_fn=permitido` (resolvido no NAMESPACE do adapter,
    no momento da chamada) - ver jpmorgan.py/nord.py etc.

    A requisicao do SITEMAP (1 por chamada) usa `requisitar_com_retry`
    quando `retentar_sitemap=True` (padrao) - so' pra excecao de
    rede/timeout de verdade, nunca pra HTTP de erro (ver docstring de
    requisitar_com_retry). A busca de cada PAGINA individual nunca
    retenta (orcamento de tempo e' compartilhado por todas as paginas
    daquela casa - 1 pagina lenta nao pode consumir o dobro do
    orcamento). Retorna (itens, motivo_falha) - NUNCA lanca excecao."""
    if not permitido_fn(sitemap_url):
        return None, "sitemap bloqueado pelo robots.txt"

    try:
        if retentar_sitemap:
            r = requisitar_com_retry(
                lambda: requests.get(sitemap_url, headers=HEADERS, timeout=sitemap_timeout),
                tentativas=2, espera_inicial_s=0.5,
                excecoes=(requests.exceptions.RequestException, ConnectionError, TimeoutError, OSError),
            )
        else:
            r = requests.get(sitemap_url, headers=HEADERS, timeout=sitemap_timeout)
    except Exception as exc:
        motivo = f"sitemap indisponível: {type(exc).__name__}"
        print(f"[{log_prefixo}] {motivo}: {exc}")
        return None, motivo
    if r.status_code != 200:
        tipo = (r.headers.get("content-type") or "").split(";")[0]
        motivo = f"sitemap respondeu HTTP {r.status_code} ({tipo})"
        print(f"[{log_prefixo}] {motivo}")
        return None, motivo
    try:
        candidatos = candidatos_do_sitemap(r.content)
    except ET.ParseError as exc:
        motivo = f"sitemap não é XML válido: {exc}"
        print(f"[{log_prefixo}] {motivo}")
        return None, motivo
    if not candidatos:
        return [], None

    itens, tentativas = [], 0
    limite = time.monotonic() + orcamento_total_s
    for candidato in candidatos[:max_itens]:
        lastmod, link = candidato
        if time.monotonic() > limite:
            print(f"[{log_prefixo}] orçamento de tempo esgotado após {tentativas} tentativa(s)")
            break
        if not permitido_fn(link):
            continue
        tentativas += 1
        try:
            resp = requests.get(link, headers=HEADERS, timeout=pagina_timeout)
            if resp.status_code != 200:
                print(f"[{log_prefixo}] página respondeu HTTP {resp.status_code}: {link}")
                continue
            item = parser_item(resp.text, link, lastmod) if passar_lastmod_ao_parser else parser_item(resp.text, link)
        except Exception as exc:
            print(f"[{log_prefixo}] falha ao buscar página ({type(exc).__name__}): {link}")
            continue
        if item:
            itens.append(item)

    if tentativas > 0 and not itens:
        sufixo = f" {descricao_esperada}" if descricao_esperada else ""
        motivo = f"{tentativas} candidato(s) no sitemap, nenhuma página individual respondeu{sufixo}"
        print(f"[{log_prefixo}] {motivo}")
        return None, motivo
    return itens, None
