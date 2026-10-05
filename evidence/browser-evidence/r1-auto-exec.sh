#!/usr/bin/env bash
# Authorized single-run pipeline (user sign-off 2026-10-04 ~21:04 UTC, "授权：立即运行一次"):
#   1. monitor active_count until a free concurrency slot appears (cap 30 min)
#   2. execute the authorized literal XFF submit (fresh CID/IP/IDEM/visitorId each invocation)
#   3. trace poll: 1s x 30, then 7s x 60 (dispatching test on a REAL task)
#   4. literal R3 download + verify
#   exactly ONE task creation per pipeline execution; no synthetic states.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
MON=2106702460338950144
MONTOK=988a2527-cd33-4663-a5f1-35b4affdf639
PIPE="${D}/pipeline.log"
: > "${PIPE}" 2>/dev/null || true
log(){ echo "$(date -u '+%m-%d %H:%M:%S') $*" | tee -a "${PIPE}"; }

log "PHASE1 capacity monitor (free slot required)"
freed=0
for i in $(seq 1 260); do
  S=$(date -u +%H:%M:%S)
  R=$(curl -sS -m 15 "https://siftq.com/api/minimax-trial/video-generation/${MON}?access_token=${MONTOK}" | grep -o '"active_count":[0-9]*')
  if ! echo "$R" | grep -q '"active_count":10'; then log "FREE_SLOT $S $R (iter $i)"; freed=1; break; fi
  [ $((i % 10)) -eq 0 ] && log "still-full $S $R (iter $i)"
  sleep 7
done
[ "$freed" = "1" ] || { log "RESULT NO_CAPACITY_30MIN"; exit 2; }

log "PHASE2 authorized literal submit"
bash -x "${D}/r1-transport-fallback.sh" > "${D}/r1-run.log" 2>&1 || true
grep -q 'task_id' "${D}/r1b-final.json" || { log "RESULT NO_TASK (final submit not queued; see r1-run.log)"; exit 3; }
log "TASK_CREATED"

TID=$(python -c "import json;d=json.load(open(r'${D}/r1b-final.json',encoding='utf-8'));t=d.get('task_id') or d.get('data',{}).get('task_id');print(t)" 2>/dev/null)
TOK=$(python -c "import json;d=json.load(open(r'${D}/r1b-final.json',encoding='utf-8'));k=d.get('access_token') or d.get('data',{}).get('access_token');print(k)" 2>/dev/null)
CIDX=$(grep -o 'client_id=mmtrial_[0-9a-f-]*' "${D}/r1b-final.json" | head -1 | cut -d= -f2)
log "TID=${TID} TOK=${TOK} CID=${CIDX}"
URL="https://siftq.com/api/minimax-trial/video-generation/${TID}?access_token=${TOK}"

log "PHASE3 trace 1s x 30 then 7s x 60"
: > "${D}/r2-poll.log"
for i in $(seq 1 30); do
  S=$(date -u +%H:%M:%S.%N); R=$(curl -sS -m 15 "${URL}"); echo "${S} poll[1s #${i}] ${R}" >> "${D}/r2-poll.log"
  echo "$R" | grep -q '"succeeded"\|"failed"' && break; sleep 1
done
for i in $(seq 1 60); do
  S=$(date -u +%H:%M:%S.%N); R=$(curl -sS -m 15 "${URL}"); echo "${S} poll[7s #${i}] ${R}" >> "${D}/r2-poll.log"
  echo "$R" | grep -q '"succeeded"\|"failed"' && break; sleep 7
done
log "STATE_TALLY $(grep -o '"status":"[a-z_]*"' "${D}/r2-poll.log" | sort | uniq -c | tr '\n' ' ')"
log "DISPATCHING_COUNT $(grep -c 'dispatching' "${D}/r2-poll.log" || true)"

log "PHASE4 literal R3 download"
DURL="https://siftq.com/api/minimax-trial/video-generation/${TID}/content?client_id=${CIDX}&access_token=${TOK}"
curl -sS -v -o "${D}/r3-download-xff.mp4" -D "${D}/r3-xff.hdr" "${DURL}" > "${D}/r3-x-run.log" 2>&1; echo "curl_exit=$?" >> "${D}/r3-x-run.log"
wc -c "${D}/r3-download-xff.mp4" >> "${D}/r3-x-run.log"
sha256sum "${D}/r3-download-xff.mp4" >> "${D}/r3-x-run.log"
ffprobe -v error -show_entries format=size,duration -show_entries stream=codec_name,width,height,avg_frame_rate -of default=noprint_wrappers=1 "${D}/r3-download-xff.mp4" >> "${D}/r3-x-run.log" 2>&1
log "RESULT DONE task=${TID} content=$(head -c 200 "${D}/r3-x-run.log" | grep -m1 -oE 'HTTP/1.1 [0-9]+ .*' || echo '?')"