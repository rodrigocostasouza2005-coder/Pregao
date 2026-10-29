"""Os contratos que a interface web/ lê (web/contratos/*.json) precisam
refletir o Python - senão a nova interface passaria a mostrar uma lista
de ativos/casas/coletores diferente da do Streamlit e dos coletores."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.exportar_contratos_web import DESTINO, contratos, serializar  # noqa: E402


def test_contratos_web_em_sincronia_com_o_python():
    for nome, conteudo in contratos().items():
        arquivo = DESTINO / nome
        assert arquivo.exists(), f"rode: python scripts/exportar_contratos_web.py ({nome} ausente)"
        assert arquivo.read_text(encoding="utf-8") == serializar(conteudo), (
            f"{nome} desatualizado - rode: python scripts/exportar_contratos_web.py")
