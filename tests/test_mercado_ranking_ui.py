# -*- coding: utf-8 -*-
"""Testes de regressao da auditoria visual do ranking MAIORES ALTAS/
BAIXAS (ui/mercado_tab.py), 3a passada (2026-10-17) - cobre os 4
problemas reais encontrados/corrigidos nas rodadas anteriores desta
auditoria, sem depender de navegador/screenshot (Chrome e secrets.toml
continuam indisponiveis nesta sessao - ver PROGRESSO.md/relatorios da
auditoria):

1. Grid de colunas da linha do ranking (numero/ticker/nome+valor/barra)
   tem que ser IDENTICO independente do tamanho do ticker, do nome da
   empresa ou da magnitude do percentual (ex: "+1,07%" vs "-12,34%") -
   e' isso que garante que a barra nasce sempre na MESMA posicao
   horizontal em toda linha (o usuario suspeitava do contrario; esta
   auditoria confirmou por analise de CSS/flexbox que nao acontece, mas
   nunca tinha teste automatizado que comprovasse isso de verdade).
2. Largura da barra (%) e' clampada em 100% e a classe/cor CSS (alta/
   baixa) reflete o SINAL do valor, nao o grupo (alta/baixa) em que a
   linha esta' sendo renderizada.
3. O filtro SETOR (22 pills, config.IBOVESPA_SETORES) nao fica mais
   espremido numa coluna de 56% ao lado de PERIODO/QTD (22% cada) - a
   linha de controles agora tem SO' 2 colunas iguais (periodo/qtd),
   SETOR ganhou linha propria de largura total.
4. Nenhuma cor "#1A1A1A"/"#111111"/rgba(255,160,40,...) hardcoded fora
   dos tokens de tema (var(--...)/tema[...]) sobrevive em nenhum
   arquivo de UI - esses hardcodes so' funcionavam no tema AMBAR/
   escuro, quebrando contraste/consistencia nos temas FOSFORO/AZUL/
   CLARO (ver config.TEMAS).

st.columns/st.segmented_control/st.pills/st.session_state funcionam em
"bare mode" (fora de um ScriptRunContext real) sem lancar excecao -
so' avisam no log (confirmado na pratica, mesmo mecanismo que os outros
testes de UI deste projeto - ver tests/test_calendario_ui.py) - por
isso e' seguro chamar as funcoes de render diretamente aqui, sem
precisar de Playwright/AppTest.

Uso: python tests/test_mercado_ranking_ui.py (python do .venv do
projeto) ou `pytest tests/test_mercado_ranking_ui.py`."""
import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import ui.mercado_tab as mercado_tab_mod

_BASE_DIR = Path(__file__).parent.parent
_PREFS = {"formato_numerico": "BR", "watchlist": []}

_FALHAS = []


def _checar(nome, condicao, detalhe=""):
    status = "OK" if condicao else "FALHOU"
    print(f"[{status}] {nome} {detalhe}")
    if not condicao:
        _FALHAS.append(nome)
        # mesmo padrao dos outros testes de UI deste projeto: faz a
        # checagem falhar de verdade sob pytest, nao so' sob o runner
        # __main__ (ver tests/test_calendario_ui.py/test_research_resumo_live_sync.py)
        raise AssertionError(f"{nome} {detalhe}".strip())


def _renderizar_linha(papel: dict, campo: str, max_abs: float, numero: int = 1):
    """Chama _linha_ranking de verdade, espiando (sem substituir) o
    st.columns real - pra capturar as fracoes/kwargs usadas - e
    capturando todo HTML passado a st.markdown. Retorna
    (chamadas_columns, htmls)."""
    chamadas_columns = []
    columns_original = mercado_tab_mod.st.columns

    def _espiao_columns(*args, **kwargs):
        chamadas_columns.append((args, kwargs))
        return columns_original(*args, **kwargs)

    htmls = []
    with patch.object(mercado_tab_mod.st, "columns", side_effect=_espiao_columns), \
         patch.object(mercado_tab_mod.st, "markdown", side_effect=lambda html, **k: htmls.append(html)):
        mercado_tab_mod._linha_ranking(numero, papel, campo, _PREFS, max_abs)

    return chamadas_columns, htmls


# ============================================================
# 1. Grid de colunas identico independente do tamanho do conteudo
# ============================================================

def test_1_grid_de_colunas_identico_para_ticker_nome_e_percentual_de_tamanhos_diferentes():
    casos = [
        # ticker curto, SEM nome curado (config.NOMES_ATIVOS_BUSCA/TICKER_NOME
        # nao tem entrada - _nome_papel devolve ""), percentual pequeno
        {"ticker": "XPTO9", "variacao_pct": 1.07},
        # ticker curado com nome ("Petrobras"), percentual com 2 digitos
        # antes da virgula - string formatada bem mais larga
        {"ticker": "PETR4", "variacao_pct": -12.34},
        # ticker de 6 caracteres (o maior tamanho real de ticker B3,
        # ex: BPAC11/SANB11/TAEE11), percentual quase zero
        {"ticker": "BPAC11", "variacao_pct": 0.01},
    ]
    fracoes_vistas = set()
    kwargs_vistos = set()
    for i, papel in enumerate(casos):
        chamadas, htmls = _renderizar_linha(papel, campo="variacao_pct", max_abs=20.0, numero=i + 1)
        _checar(f"1.{i} st.columns chamado exatamente 1x por linha", len(chamadas) == 1, f"(ticker={papel['ticker']})")
        args, kwargs = chamadas[0]
        fracoes_vistas.add(tuple(args[0]))
        kwargs_vistos.add(kwargs.get("vertical_alignment"))
        _checar(
            f"1.{i} cada coluna tem seu HTML (numero/nome+valor/barra) presente",
            any("rank-numero" in h for h in htmls) and any("rank-nome-valor" in h for h in htmls)
            and any("rank-barra-trilho" in h for h in htmls),
            f"(ticker={papel['ticker']})",
        )

    _checar(
        "1 o grid de colunas (fracoes passadas a st.columns) NAO varia entre linhas com "
        "ticker/nome/percentual de tamanhos bem diferentes - garante que a barra nasce "
        "sempre na MESMA posicao horizontal em toda linha do ranking",
        len(fracoes_vistas) == 1, f"(fracoes vistas: {fracoes_vistas})",
    )
    _checar(
        "1b toda linha usa vertical_alignment='center' (alinhamento vertical consistente, "
        "nao depende de padding/margin calibrado 'no olho' pra 1 fonte so')",
        kwargs_vistos == {"center"}, f"(valores vistos: {kwargs_vistos})",
    )


# ============================================================
# 2. Largura da barra clampada + classe/cor conforme o SINAL do valor
# ============================================================

def _largura_pct_da_barra(html_barra: str) -> float:
    m = re.search(r"rank-barra-fill ([\w-]+)' style='width:(\d+\.\d)%;'", html_barra)
    assert m, f"nao encontrou a barra no HTML: {html_barra!r}"
    return m.group(1), float(m.group(2))


def test_2_largura_da_barra_clampada_e_classe_reflete_o_sinal_do_valor():
    casos = [
        # (valor, max_abs, classe_esperada, largura_esperada_pct)
        (10.0, 20.0, "rank-barra-pos", 50.0),
        (-10.0, 20.0, "rank-barra-neg", 50.0),
        (25.0, 20.0, "rank-barra-pos", 100.0),  # valor > max_abs: clampa em 100%, nunca estoura
        (0.0, 20.0, "rank-barra-pos", 0.0),  # zero conta como "alta" (valor >= 0), barra vazia
        (-0.01, 20.0, "rank-barra-neg", 0.1),
    ]
    for valor, max_abs, classe_esperada, largura_esperada in casos:
        papel = {"ticker": "TEST3", "variacao_pct": valor}
        _, htmls = _renderizar_linha(papel, campo="variacao_pct", max_abs=max_abs)
        html_barra = next(h for h in htmls if "rank-barra-trilho" in h)
        classe, largura = _largura_pct_da_barra(html_barra)
        _checar(
            f"2 valor={valor}/max_abs={max_abs}: classe da barra e' {classe_esperada}",
            classe == classe_esperada, f"(obtido: {classe})",
        )
        _checar(
            f"2 valor={valor}/max_abs={max_abs}: largura da barra e' {largura_esperada}% "
            "(nunca > 100%, mesmo com valor > max_abs)",
            abs(largura - largura_esperada) < 0.05, f"(obtido: {largura})",
        )


# ============================================================
# 3. Filtro SETOR tem linha propria (nao espreme mais com PERIODO/QTD)
# ============================================================

def test_3_linha_periodo_qtd_tem_so_2_colunas_iguais_setor_ficou_de_fora():
    """Regressao do achado real (2a passada da auditoria, 2026-10-17):
    config.IBOVESPA_SETORES tem 21 setores unicos + 'TODOS' = 22 pills,
    varias com rotulo de 20-29 caracteres - antes disputavam 56% da
    linha de controles ao lado de PERIODO/QTD (22% cada), quebrando em
    varias linhas e deixando aquela coluna muito mais alta que as
    vizinhas (filtro desproporcional). Agora a linha de controles tem
    SO' periodo+qtd, 2 colunas iguais - sem fracoes assimetricas
    [0.22, 0.22, 0.56] sobrevivendo em nenhum st.columns() da funcao."""
    papel_alta = {"ticker": "PETR4", "setor": "Petróleo e Gás", "variacao_pct": 1.5}
    papel_baixa = {"ticker": "VALE3", "setor": "Mineração e Siderurgia", "variacao_pct": -1.2}

    chamadas_columns = []
    columns_original = mercado_tab_mod.st.columns

    def _espiao_columns(*args, **kwargs):
        chamadas_columns.append((args, kwargs))
        return columns_original(*args, **kwargs)

    with patch.object(mercado_tab_mod, "obter_cotacao_indice", return_value={"erro": "sem rede no teste"}), \
         patch.object(mercado_tab_mod, "obter_altas_baixas", return_value=([papel_alta], [papel_baixa])), \
         patch.object(mercado_tab_mod, "obter_composicao_oficial", return_value=None), \
         patch.object(mercado_tab_mod.st, "columns", side_effect=_espiao_columns):
        mercado_tab_mod._painel_altas_baixas(_PREFS)

    # a 1a chamada de st.columns() na funcao e' a linha periodo+qtd
    # (a de SETOR nao usa mais st.columns nenhum - virou st.pills direto,
    # em largura total, fora de qualquer coluna)
    _checar("3 st.columns foi chamado ao menos 1 vez (linha periodo/qtd)", len(chamadas_columns) >= 1)
    primeira_chamada_args = chamadas_columns[0][0]
    _checar(
        "3a a 1a linha de controles (periodo/qtd) usa st.columns(2, ...) - 2 colunas IGUAIS, "
        "nao mais 3 colunas assimetricas [0.22, 0.22, 0.56] (versao antiga, onde SETOR "
        "disputava espaco com periodo/qtd na mesma linha)",
        primeira_chamada_args == (2,), f"(args vistos: {primeira_chamada_args})",
    )
    for args, _kwargs in chamadas_columns:
        if args and isinstance(args[0], (list, tuple)):
            _checar(
                "3b nenhuma chamada de st.columns usa a antiga divisao assimetrica "
                "[0.22, 0.22, 0.56] (periodo/qtd/setor espremidos na mesma linha)",
                list(args[0]) != [0.22, 0.22, 0.56], f"(args: {args[0]})",
            )


def test_3b_label_setor_aparece_fora_de_qualquer_coluna_com_largura_total():
    papel_alta = {"ticker": "PETR4", "setor": "Petróleo e Gás", "variacao_pct": 1.5}
    papel_baixa = {"ticker": "VALE3", "setor": "Mineração e Siderurgia", "variacao_pct": -1.2}
    htmls = []

    with patch.object(mercado_tab_mod, "obter_cotacao_indice", return_value={"erro": "sem rede no teste"}), \
         patch.object(mercado_tab_mod, "obter_altas_baixas", return_value=([papel_alta], [papel_baixa])), \
         patch.object(mercado_tab_mod, "obter_composicao_oficial", return_value=None), \
         patch.object(mercado_tab_mod.st, "markdown", side_effect=lambda html, **k: htmls.append(html)):
        mercado_tab_mod._painel_altas_baixas(_PREFS)

    _checar(
        "3b label 'SETOR' (mesmo padrao visual ja usado em CVM/CALENDARIO acima das pills) "
        "aparece no HTML renderizado",
        any(">SETOR<" in h for h in htmls),
    )


# ============================================================
# 4. Nenhuma cor hardcoded fora dos tokens de tema sobrevive na UI
# ============================================================

_PADROES_PROIBIDOS = [r"#1A1A1A", r"#111111", r"rgba\(\s*255\s*,\s*160\s*,\s*40"]

_ARQUIVOS_UI = [_BASE_DIR / "app.py", _BASE_DIR / "auth.py"] + sorted((_BASE_DIR / "ui").glob("*.py"))


def _sem_comentarios(texto: str) -> str:
    """Remove comentarios CSS /* ... */ (multi-linha, embutidos em
    strings Python triplo-aspas) e linhas de comentario Python puro
    (comecam com '#' depois de strip) - sem isso, as proprias
    EXPLICACOES desta auditoria (ex: "nao '#1A1A1A' fixo, achado da
    auditoria...") dariam falso-positivo no detector abaixo."""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    linhas = [linha for linha in texto.splitlines() if not linha.strip().startswith("#")]
    return "\n".join(linhas)


def test_4_sem_cores_hardcoded_fora_dos_tokens_de_tema():
    """Regressao dos achados da auditoria visual (rodadas 1 e 2,
    2026-10-16/17): rgba(255,160,40,...) e #1A1A1A/#111111 hardcoded em
    ui/calendario_tab.py, ui/cvm_tab.py (x2), ui/macro_tab.py,
    ui/mercado_tab.py, ui/news_tab.py (x2), ui/visao_geral.py, app.py e
    auth.py so' funcionavam no tema AMBAR/escuro - quebravam contraste/
    consistencia nos temas FOSFORO/AZUL/CLARO (ver config.TEMAS). Todos
    corrigidos pra var(--destaque)/var(--borda)/var(--bg)/tema['borda'],
    conforme o caso. Confirmado manualmente (auditoria) que este
    detector FALHA no commit base (1e8dbb1, antes das correcoes) e
    PASSA depois - ver relatorios da auditoria."""
    violacoes = []
    for caminho in _ARQUIVOS_UI:
        texto = caminho.read_text(encoding="utf-8")
        texto_limpo = _sem_comentarios(texto)
        for padrao in _PADROES_PROIBIDOS:
            achado = re.search(padrao, texto_limpo, flags=re.I)
            if achado:
                violacoes.append(f"{caminho.relative_to(_BASE_DIR)}: {achado.group(0)!r}")

    _checar(
        "4 nenhum arquivo de UI tem cor hardcoded (#1A1A1A/#111111/rgba(255,160,40,...)) "
        "fora dos tokens de tema (var(--...) ou tema['...'])",
        not violacoes, f"(violacoes: {violacoes})",
    )


# ============================================================
# 5. MAIS NEGOCIADOS: ticker clicavel (achado real da auditoria 360,
# 2026-10-18, docs/auditoria-redesign-360.md) - igual ao ranking
# altas/baixas acima, mas ESTE painel so' tinha texto cru <td>{ticker}</td>
# dentro de uma tabela HTML, sem NENHUM jeito de ir direto pro ticker em
# EQUITY. Reusa o MESMO mecanismo ja validado (_ir_para_equity).
# ============================================================

def test_5_mais_negociados_ticker_e_botao_real_com_on_click_para_equity():
    negociados = [
        {"ticker": "PETR4", "volume_financeiro": 1_500_000_000.0, "variacao_pct": 1.23},
        {"ticker": "VALE3", "volume_financeiro": 980_000_000.0, "variacao_pct": -0.87},
    ]
    chamadas_button = []

    def _espiao_button(label, **kwargs):
        chamadas_button.append((label, kwargs))
        return False

    with patch.object(mercado_tab_mod, "obter_mais_negociados", return_value=negociados), \
         patch.object(mercado_tab_mod.st, "button", side_effect=_espiao_button):
        mercado_tab_mod._painel_mais_negociados(_PREFS)

    _checar("5a st.button chamado 1x por ticker (2 tickers -> 2 botoes)", len(chamadas_button) == 2,
            f"(chamadas={chamadas_button})")
    rotulos = [label for label, _k in chamadas_button]
    _checar("5b rotulos dos botoes sao os tickers, na ordem recebida", rotulos == ["PETR4", "VALE3"],
            f"(rotulos={rotulos})")
    for label, kwargs in chamadas_button:
        _checar(
            f"5c botao de {label} usa on_click=_ir_para_equity com args=(ticker, prefs) - mesmo "
            "mecanismo ja validado no ranking de altas/baixas",
            kwargs.get("on_click") is mercado_tab_mod._ir_para_equity and kwargs.get("args") == (label, _PREFS),
            f"(kwargs={kwargs})",
        )


def test_5d_mais_negociados_sem_dado_nao_quebra():
    with patch.object(mercado_tab_mod, "obter_mais_negociados", return_value=None), \
         patch.object(mercado_tab_mod.st, "button") as mock_button:
        mercado_tab_mod._painel_mais_negociados(_PREFS)
    _checar("5d sem dado -> nenhum botao criado, sem excecao", mock_button.call_count == 0)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError:
                pass  # ja' registrado em _FALHAS por _checar

    print()
    if _FALHAS:
        print(f"FALHARAM {len(_FALHAS)}: {_FALHAS}")
        sys.exit(1)
    print("TODOS OS TESTES DO RANKING/TOKENS DE TEMA PASSARAM")
