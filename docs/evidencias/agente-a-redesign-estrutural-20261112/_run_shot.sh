#!/bin/bash
# $1 = harness file, $2 = aba arg (or "" for none), $3 = port, $4 = out prefix
HARNESS="$1"
ABA="$2"
PORT="$3"
PREFIX="$4"
if [ -z "$ABA" ]; then
  python -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true > "/tmp/st_$PORT.log" 2>&1 &
else
  python -m streamlit run "$HARNESS" --server.port "$PORT" --server.headless true -- "$ABA" > "/tmp/st_$PORT.log" 2>&1 &
fi
SRV_PID=$!
echo "started pid=$SRV_PID port=$PORT"
for i in $(seq 1 30); do
  curl -s "http://127.0.0.1:$PORT" > /dev/null 2>&1 && break
  sleep 1
done
sleep 2
python "docs/evidencias/agente-a-redesign-estrutural-20261112/shot.py" "$PORT" 1440 "docs/evidencias/agente-a-redesign-estrutural-20261112/${PREFIX}_1440.png"
python "docs/evidencias/agente-a-redesign-estrutural-20261112/shot.py" "$PORT" 1440 "docs/evidencias/agente-a-redesign-estrutural-20261112/${PREFIX}_1440.png"
python "docs/evidencias/agente-a-redesign-estrutural-20261112/shot.py" "$PORT" 1024 "docs/evidencias/agente-a-redesign-estrutural-20261112/${PREFIX}_1024.png"
kill "$SRV_PID" 2>/dev/null
wait "$SRV_PID" 2>/dev/null
