#!/bin/bash
# r2-fast-trace.sh — race the pipeline: the instant r1b-final.json contains a task_id,
# poll at 0.2s x100 (~20s) to catch a transient 'dispatching' state.
# Logs to r2-fast-trace.log. No-ops silently until the submit result appears.
cd "$(dirname "$0")"
OUT=r2-fast-trace.log
{
echo "=== fast-trace armed $(date -u '+%Y-%m-%d %H:%M:%S') UTC; waiting for r1b-final.json ==="
} >> "$OUT"

# wait up to 15 min for the submit result (0.1s * 9000)
for i in $(seq 1 9000); do
  if [ -s r1b-final.json ]; then
    # parse task_id + access_token (python for robustness)
    TID=$(python - <<'EOF'
import json,re,sys
try:
    raw=open('r1b-final.json',encoding='utf-8',errors='replace').read()
    m=re.search(r'"task_id"\s*:\s*"?(\d{8,30})"?',raw)
    t=re.search(r'"access_token"\s*:\s*"([0-9a-fA-F-]{8,64})"',raw)
    if m: print(m.group(1)+("\t"+t.group(1) if t else ""))
except Exception: pass
EOF
)
    if [ -n "$TID" ]; then break; fi
  fi
  sleep 0.1
done
if [ -z "$TID" ]; then
  { echo "RESULT NO_TASK $(date -u '+%H:%M:%S')"; } >> "$OUT"; exit 0
fi
TASK="${TID%%$'\t'*}"; TOK="${TID##*$'\t'}"
echo "RESULT TASK=$TASK TOKEN=${TOK:0:8}… armed-submit $(date -u '+%H:%M:%S')" >> "$OUT"

# fast cadence: 0.2s x100
for i in $(seq 1 100); do
  S=$(date -u +%H:%M:%S.%3N 2>/dev/null || date -u +%H:%M:%S)
  R=$(curl -sS -m 8 "https://siftq.com/api/minimax-trial/video-generation/$TASK?access_token=$TOK" 2>/dev/null | head -c 400)
  echo "$S $R" >> "$OUT"
  case "$R" in *succeeded*) break;; esac
  sleep 0.2
done
echo "RESULT FAST_TRACE_DONE $(date -u '+%H:%M:%S')" >> "$OUT"