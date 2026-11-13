#!/bin/bash
# Runner generico: $1 = caminho do harness (absoluto ou relativo ao repo root),
# $2 = arg de aba (ou "" pra nenhum), $3 = porta, $4 = prefixo de saida
# (caminho completo, sem largura/extensao). Screenshots em 1440/1024/390.
set -e
REPO="C:/Users/Dell/Projects/pregao-fase8-interface"
PY="/c/Users/Dell/Projects/pregao/.venv/Scripts/python.exe"
SHOT="$REPO/docs/evidencias/revisao-interface-bloomberg-20261113/shot.py"
HARNESS="$1"
ABA="$2"
PORT="$3"
PREFIX="$4"

cd "$REPO"
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
"$PY" "$SHOT" "$PORT" 1440 "${PREFIX}_1440.png"
"$PY" "$SHOT" "$PORT" 1024 "${PREFIX}_1024.png"
"$PY" "$SHOT" "$PORT" 390  "${PREFIX}_390.png"
kill "$SRV_PID" 2>/dev/null || true
wait "$SRV_PID" 2>/dev/null || true
