#!/bin/bash
# $1 = harness file (caminho relativo a esta pasta), $2 = aba arg (ou "" pra nenhum),
# $3 = porta, $4 = prefixo do arquivo de saida (sem largura/extensao)
# Captura os 3 viewports pedidos pela missao: desktop 1440, tablet 1024, mobile 390.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="/c/Users/Dell/Projects/pregao/.venv/Scripts/python.exe"
HARNESS="$1"
ABA="$2"
PORT="$3"
PREFIX="$4"

cd "$DIR"
if [ -z "$ABA" ]; then
  "$PY" -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true > "/tmp/st_$PORT.log" 2>&1 &
else
  "$PY" -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true -- "$ABA" > "/tmp/st_$PORT.log" 2>&1 &
fi
SRV_PID=$!
echo "started pid=$SRV_PID port=$PORT harness=$HARNESS aba=$ABA"
for i in $(seq 1 30); do
  curl -s "http://127.0.0.1:$PORT" > /dev/null 2>&1 && break
  sleep 1
done
sleep 2
"$PY" shot.py "$PORT" 1440 "${PREFIX}_1440.png"
"$PY" shot.py "$PORT" 1024 "${PREFIX}_1024.png"
"$PY" shot.py "$PORT" 390  "${PREFIX}_390.png"
kill "$SRV_PID" 2>/dev/null || true
wait "$SRV_PID" 2>/dev/null || true
