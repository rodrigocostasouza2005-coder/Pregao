# -*- coding: utf-8 -*-
"""data/x_radar/conector.py - unico arquivo do projeto que importa
data.x_signals direto (ver test_x_signals.py test_7b). Cobre: monta a
query do universo configurado e delega integralmente pra
x_signals.buscar_sinais (nunca duplica logica de paginacao/dedup aqui -
isso e' testado em tests/test_x_signals.py)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.x_radar.conector as conector_mod


def test_coletar_monta_query_do_universo_e_delega_pra_x_signals():
    with patch.object(conector_mod.x_signals, "buscar_sinais", return_value=([], {"leituras": 1, "limite_restante": 299})) as mock_buscar:
        sinais, info = conector_mod.coletar(tickers=["PETR4"], contas=["GenialInveste"])
    assert sinais == []
    assert info == {"leituras": 1, "limite_restante": 299}
    chamada_query = mock_buscar.call_args.args[0]
    assert "PETR4" in chamada_query
    assert "from:GenialInveste" in chamada_query
    assert mock_buscar.call_args.kwargs["desde"] is not None


def test_coletar_propaga_notimplementederror_sem_mascarar():
    with patch.object(conector_mod.x_signals, "buscar_sinais", side_effect=NotImplementedError("sem credencial")):
        try:
            conector_mod.coletar()
            assert False, "deveria ter lancado"
        except NotImplementedError as exc:
            assert "sem credencial" in str(exc)
