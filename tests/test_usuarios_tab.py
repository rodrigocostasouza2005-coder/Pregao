# -*- coding: utf-8 -*-
"""Testes de ui/usuarios_tab.py: métricas honestas (calcular_metricas,
função pura) e a aplicação REAL da autorização dentro do fluxo de
renderização - um e-mail não-admin chamando render_usuarios nunca
chega a consultar data/admin_usuarios.obter_usuarios_admin (prova que a
autorização protege a CONSULTA, não só a mensagem de erro na tela).

Bare mode (sem ScriptRunContext real) - mesmo padrão de
tests/test_mercado_ranking_ui.py/test_radar_tab_fontes_ui.py deste
projeto: st.columns/st.metric/st.markdown/st.segmented_control
funcionam fora de uma sessão Streamlit real, só avisam no log.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import ui.usuarios_tab as usuarios_tab

_ADMIN = "admin@exemplo.com"
_NAO_ADMIN = "intruso@exemplo.com"


# ---------------------------------------------------------------------
# calcular_metricas - função pura, sem Streamlit/Supabase
# ---------------------------------------------------------------------

def test_metricas_com_dados_vazios_nao_inventa_nada():
    metricas = usuarios_tab.calcular_metricas([])
    assert metricas == {
        "total": 0, "novos": 0, "ativos_7d": 0, "ativos_30d": 0,
        "inscritos": 0, "nao_responderam": 0,
    }


def test_metricas_contam_corretamente():
    agora = datetime(2026, 10, 18, tzinfo=timezone.utc)
    usuarios = [
        {  # novo, ativo 7d e 30d, inscrito
            "created_at": (agora - timedelta(days=2)).isoformat(),
            "last_seen_at": (agora - timedelta(days=1)).isoformat(),
            "status_inscricao": "inscrito",
        },
        {  # antigo, ativo so' 30d, recusou
            "created_at": (agora - timedelta(days=200)).isoformat(),
            "last_seen_at": (agora - timedelta(days=20)).isoformat(),
            "status_inscricao": "recusou",
        },
        {  # sem created_at/last_seen_at (usuario anterior a' migracao) -
           # nao conta como novo nem como ativo, mas tambem nao gera erro
            "created_at": None,
            "last_seen_at": None,
            "status_inscricao": "nao_respondeu",
        },
    ]
    metricas = usuarios_tab.calcular_metricas(usuarios, dias_novos=30, agora=agora)
    assert metricas["total"] == 3
    assert metricas["novos"] == 1
    assert metricas["ativos_7d"] == 1
    assert metricas["ativos_30d"] == 2
    assert metricas["inscritos"] == 1
    assert metricas["nao_responderam"] == 1


def test_ausencia_de_historico_nao_gera_metrica_inventada():
    """Usuario sem nenhum dado de data (anterior a' migracao) nunca
    conta como "novo" nem "ativo" - ausencia de dado != zero/inativo
    fabricado, so' fica fora dessas 2 contagens."""
    usuarios = [{"created_at": None, "last_seen_at": None, "status_inscricao": "nao_respondeu"}]
    metricas = usuarios_tab.calcular_metricas(usuarios)
    assert metricas["novos"] == 0
    assert metricas["ativos_7d"] == 0
    assert metricas["ativos_30d"] == 0
    assert metricas["total"] == 1  # mas ainda conta como usuario total


# ---------------------------------------------------------------------
# render_usuarios - autorização protege a CONSULTA, não só a tela
# ---------------------------------------------------------------------

def test_usuario_nao_admin_nao_consulta_nenhum_dado(monkeypatch):
    monkeypatch.setattr(usuarios_tab.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(usuarios_tab, "obter_usuarios_admin") as mock_obter, \
         patch("streamlit.error") as mock_error:
        usuarios_tab.render_usuarios({"email": _NAO_ADMIN, "sub": "s-intruso"})

    mock_obter.assert_not_called()
    mock_error.assert_called_once()


def test_admin_autorizado_consulta_os_dados(monkeypatch):
    monkeypatch.setattr(usuarios_tab.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(usuarios_tab, "obter_usuarios_admin", return_value=[]) as mock_obter:
        usuarios_tab.render_usuarios({"email": _ADMIN, "sub": "s-admin"})
    mock_obter.assert_called_once_with(_ADMIN)


def test_banco_indisponivel_mostra_aviso_sem_quebrar(monkeypatch):
    monkeypatch.setattr(usuarios_tab.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(usuarios_tab, "obter_usuarios_admin", return_value=None), \
         patch("streamlit.warning") as mock_warning:
        usuarios_tab.render_usuarios({"email": _ADMIN, "sub": "s-admin"})  # nao deve lancar
    mock_warning.assert_called_once()


def test_lista_vazia_mostra_info_sem_quebrar(monkeypatch):
    monkeypatch.setattr(usuarios_tab.config, "obter_emails_admin", lambda: [_ADMIN])
    with patch.object(usuarios_tab, "obter_usuarios_admin", return_value=[]), \
         patch("streamlit.info") as mock_info:
        usuarios_tab.render_usuarios({"email": _ADMIN, "sub": "s-admin"})
    mock_info.assert_called_once()


# ---------------------------------------------------------------------
# CSV: mitigação de injeção de fórmula (email pode vir de texto digitado
# pelo usuário no banner de onboarding quando o e-mail do Google não é
# válido, ver app.py) - um valor começando com =/+/-/@/tab/CR nunca pode
# chegar "crú" numa célula, senão Excel/LibreOffice/Google Sheets
# executam como fórmula ao abrir o CSV exportado pelo admin.
# ---------------------------------------------------------------------

def test_csv_neutraliza_valor_que_parece_formula():
    linhas = [
        {
            "email": "=HYPERLINK(\"http://evil\",\"clique\")",
            "created_at": None, "last_seen_at": None,
            "status_inscricao": "inscrito", "ativo_7d": False, "ativo_30d": False,
        },
    ]
    csv_texto = usuarios_tab._csv_bytes(linhas).decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_texto
    # garante que nenhuma linha do CSV comeca com um dos prefixos perigosos
    for linha_csv in csv_texto.splitlines()[1:]:
        primeira_celula = linha_csv.split(",")[0].strip('"')
        assert not primeira_celula.startswith(("=", "+", "-", "@", "\t", "\r"))


def test_csv_preserva_email_normal_sem_modificar():
    linhas = [
        {
            "email": "pessoa@exemplo.com",
            "created_at": None, "last_seen_at": None,
            "status_inscricao": "inscrito", "ativo_7d": False, "ativo_30d": False,
        },
    ]
    csv_texto = usuarios_tab._csv_bytes(linhas).decode("utf-8-sig")
    assert "pessoa@exemplo.com" in csv_texto
    assert "'pessoa@exemplo.com" not in csv_texto


def test_render_com_dados_nao_lanca_excecao(monkeypatch):
    monkeypatch.setattr(usuarios_tab.config, "obter_emails_admin", lambda: [_ADMIN])
    usuarios = [
        {"sub": "s1", "email": "a@exemplo.com", "created_at": "2026-10-18T10:00:00+00:00",
         "last_seen_at": "2026-10-18T10:00:00+00:00", "status_inscricao": "inscrito"},
        {"sub": "s2", "email": "b@exemplo.com", "created_at": None, "last_seen_at": None,
         "status_inscricao": "nao_respondeu"},
    ]
    with patch.object(usuarios_tab, "obter_usuarios_admin", return_value=usuarios):
        usuarios_tab.render_usuarios({"email": _ADMIN, "sub": "s-admin"})  # nao deve lancar
