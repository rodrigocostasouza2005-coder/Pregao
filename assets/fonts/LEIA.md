# Fontes do PDF do Morning Call

Embutidas no PDF por `jobs/morning_call_pdf.py`. Todas sob a SIL Open Font
License 1.1 (textos em `OFL-*.txt`), obtidas do repositório google/fonts.

| Arquivo | Família | Uso |
|---|---|---|
| `SourceSerif4Display-Bold.ttf` | Source Serif 4 (opsz 60, wght 700) | masthead e manchete principal |
| `SourceSerif4Display-SemiBold.ttf` | Source Serif 4 (opsz 36, wght 600) | manchetes internas |
| `SourceSerif4Display-Italic.ttf` | Source Serif 4 Italic (opsz 30, wght 400) | linha-fina da manchete |
| `SourceSerif4Text-*.ttf` | Source Serif 4 (opsz 12) | corpo das matérias |
| `LibreFranklin-*.ttf` | Libre Franklin (400/500/700) | rótulos, legendas, fontes, tabelas |
| `IBMPlexMono-*.ttf` | IBM Plex Mono | cotações e percentuais (mesma mono do terminal) |

Source Serif 4 e Libre Franklin são fontes variáveis no google/fonts; os
arquivos daqui são instâncias estáticas geradas com
`fontTools.varLib.instancer.instantiateVariableFont` nos eixos indicados
(o ReportLab não interpola fonte variável).
