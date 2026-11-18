#!/bin/bash
# Runner generico Fase 4 (validacao pos-reestruturacao) - adaptado de
# docs/evidencias/revisao-interface-bloomberg-20261113/_run_any.sh.
# $1 = caminho do harness (relativo a esta pasta, ou absoluto)
# $2 = args extras do harness (string vazia "" se nenhum)
# $3 = porta
# $4 = prefixo de saida (caminho completo, sem largura/extensao)
set -e
REPO="C:/Users/Dell/Projects/pregao-fase4-validacao-final"
PY="/c/Users/Dell/Projects/pregao/.venv/Scripts/python.exe"
SHOT="$REPO/docs/evidencias/validacao-visual-real-20261117/shot.py"
HARNESS="$1"
ARGS="$2"
PORT="$3"
PREFIX="$4"

cd "$REPO"
if [ -z "$ARGS" ]; then
  "$PY" -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true > "/tmp/st_$PORT.log" 2>&1 &
else
  "$PY" -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true -- $ARGS > "/tmp/st_$PORT.log" 2>&1 &
fi
SRV_PID=$!
echo "started pid=$SRV_PID port=$PORT harness=$HARNESS args=$ARGS"
for i in $(seq 1 30); do
  curl -s "http://127.0.0.1:$PORT" > /dev/null 2>&1 && break
  sleep 1
done
sleep 2
"$PY" "$SHOT" "$PORT" 1440 "${PREFIX}_1440.png"
"$PY" "$SHOT" "$PORT" 1024 "${PREFIX}_1024.png"
kill "$SRV_PID" 2>/dev/null || true
wait "$SRV_PID" 2>/dev/null || true
