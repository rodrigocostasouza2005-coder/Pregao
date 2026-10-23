# -*- coding: utf-8 -*-
"""EARNINGS REVIEWER - analise de resultados trimestrais (Modulo 2 do
Pregao). Submodulos:

- cvm_dre.py: Demonstracao do Resultado (DRE) consolidada de empresas
  brasileiras, via dados abertos da CVM (ITR/DFP) - mesma fonte oficial
  e convencoes de data/cvm.py (User-Agent, cache, registrar_tentativa).
- sec_xbrl.py: conceitos XBRL (us-gaap) de empresas internacionais via
  SEC EDGAR (data.sec.gov), oficial e gratuito.
- reviewer.py: normaliza as duas fontes num schema comum de linha
  ({metrica, periodo, valor, fonte, url, ...}), calcula QoQ/YoY SO'
  quando o dado permitir (nunca inventa), e monta a nota estruturada
  (fatos/interpretacao/riscos/limitacoes) com proveniencia rastreavel.

Nunca afirma acesso a consenso de mercado, guidance ou relatorios pagos -
so' numeros reportados nas fontes oficiais acima. Ver REGISTRO_COLETORES
em data/saude_dados.py pelas 2 fontes novas registradas pro painel de
saude (CVM (DRE trimestral), SEC EDGAR (XBRL))."""
