# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.coordenador_central import modelagem

def test_model_builder_sem_premissas_nao_inventa():
    resultado = modelagem.modelar_empresa('PETR4', None, preco_atual=30)
    assert resultado['disponivel'] is False
    assert resultado['campos_faltantes'] == ['premissas_dcf']
    assert resultado['cenarios'] == {}
