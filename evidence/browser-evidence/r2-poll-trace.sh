#!/usr/bin/env bash
# Goal step 2 (R2) fresh-submission poll trace, REAL client identity (no XFF).
# Prepared but NOT EXECUTED. Gate: run only after ONE bounded usage probe at >=00:00 UTC
# shows remaining>0 (quota reset), because the standing advisory bans re-submitting while
# quota is exhausted. Cadence: 1s for first ~30s, then 7s — tests whether "dispatching"
# is transient rather than absent. Never fabricated; only logged responses count.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
export D
date -u
CID=mmtrial_37c012af-d651-4927-b25b-2e80152b4f57
IMG="C:/Users/niko/.pi/browser-artifacts/mmtrial-input.jpg"
PROMPT="夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作"
genuuid(){ python -c 'import uuid;print(uuid.uuid4())' 2>/dev/null || powershell -NoProfile -Command '[guid]::NewGuid().ToString()' 2>/dev/null; }
PIDEM="mmtrial_$(genuuid)"
IDEM="${PIDEM}"
SUB="${D}/r2-submit.json"
POLL="${D}/r2-poll.log"
: > "${POLL}"
echo "Idempotency-Key=${IDEM}"
curl -X POST https://siftq.com/api/minimax-trial/video-generation \
  -H "X-MiniMax-Trial-Client: ${CID}" \
  -H "Accept: application/json" \
  -H "Idempotency-Key: ${IDEM}" \
  -F client_id="${CID}" \
  -F ratio=9:16 \
  -F duration=6 \
  -F "prompt=${PROMPT}" \
  -F "image=@${IMG}" \
  -sS -D "${D}/r2-submit.hdr" -o "${SUB}"
echo "curl_exit=$?"; cat "${SUB}"
python - "$SUB" "$D" <<'EOF'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
t=d.get('task_id') or d.get('data',{}).get('task_id')
k=d.get('access_token') or d.get('data',{}).get('access_token')
open(sys.argv[2]+'/r2-ids.txt','w').write(f"task_id={t}\naccess_token={k}\n")
EOF
. "${D}/r2-ids.txt"
URL="https://siftq.com/api/minimax-trial/video-generation/${task_id}?access_token=${access_token}"
for i in $(seq 1 30); do
  S=$(date -u +%H:%M:%S); R=$(curl -sS -m 15 "${URL}"); echo "${S} poll[1s #${i}] ${R}" >> "${POLL}"; echo "${R}"
  echo "${R}" | grep -q '"succeeded"' && break
  echo "${R}" | grep -q '"failed"' && break
  sleep 1
done
for i in $(seq 1 40); do
  S=$(date -u +%H:%M:%S); R=$(curl -sS -m 15 "${URL}"); echo "${S} poll[7s #${i}] ${R}" >> "${POLL}"; echo "${R}"
  echo "${R}" | grep -q '"succeeded"' && break
  echo "${R}" | grep -q '"failed"' && break
  sleep 7
done
echo "=== state tally ==="
grep -o '"status":"[a-z_]*"' "${POLL}" | sort | uniq -c
echo "=== dispatching occurrences (literal grep must be 0 unless API emits it) ==="
grep -c 'dispatching' "${POLL}" || true