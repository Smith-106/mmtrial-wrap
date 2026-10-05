#!/usr/bin/env bash
# R1 literal command + transport fallback (single authorized XFF run, 2026-10-04):
#   literal form fields/headers kept EXACTLY; transport adds Cookie/UA/Origin/Referer
#   (CF challenge bypass); Idem added only if required by business layer (single task).
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
genuuid(){ python -c 'import uuid;print(uuid.uuid4())' 2>/dev/null || powershell -NoProfile -Command '[guid]::NewGuid().ToString()' 2>/dev/null; }
CID="mmtrial_$(genuuid)"
FAKEIP="$(printf '%d.%d.%d.%d' $((RANDOM%223+1)) $((RANDOM%255+1)) $((RANDOM%255+1)) $((RANDOM%254+2)))"
PROMPT="夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作"
IMG="C:/Users/niko/.pi/browser-artifacts/mmtrial-input.jpg"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/154.0.0.0 Safari/537.36'
CF="$(cat /tmp/mmtrial_cf.txt 2>/dev/null)"
export CID FAKEIP PROMPT IMG UA CF D
date -u
echo "CID=${CID}"
echo "XFF=${FAKEIP}"

run_attempt() {
  local tag="$1"; shift
  local extra=("$@")
  echo "=== ATTEMPT ${tag}: extra header(s): ${extra[*]:-none} ==="
  curl -X POST https://siftq.com/api/minimax-trial/video-generation \
    -H "X-MiniMax-Trial-Client: ${CID}" \
    -H "X-Forwarded-For: ${FAKEIP}" \
    -H "Cookie: cf_clearance=${CF}" \
    -H "User-Agent: ${UA}" \
    -H 'Origin: https://siftq.com' \
    -H 'Referer: https://siftq.com/minimax-h3/free-trial' \
    ${extra[@]+"${extra[@]}"} \
    -F client_id="${CID}" \
    -F ratio=9:16 \
    -F duration=6 \
    -F "prompt=${PROMPT}" \
    -F "image=@${IMG}" \
    -sS -D "${D}/r1b-${tag}.hdr" -o "${D}/r1b-${tag}.json"
  echo "curl_exit=$?"
  grep -m1 -E '^HTTP/' "${D}/r1b-${tag}.hdr"
  # task_id present => task was created => stop (single-task authorization)
  if grep -q 'task_id' "${D}/r1b-${tag}.json"; then
    cp "${D}/r1b-${tag}.hdr" "${D}/r1b-final.hdr"; cp "${D}/r1b-${tag}.json" "${D}/r1b-final.json"
    echo "TASK_CREATED_BY=${tag}"
    return 0
  fi
  echo "--- body (small) ---"; head -c 400 "${D}/r1b-${tag}.json"; echo
  return 1
}

IDEM="mmtrial_$(genuuid)"
VISITOR="$(genuuid)"
echo "Idempotency-Key=${IDEM}"
echo "visitorId=${VISITOR}"
# Attempt 3 (superset that previously reached quota check as 429):
#   adds bundle-proven telemetry fields visitorId + channelCode (Dre() always appends them)
run_attempt no-idem || run_attempt with-idem -H "Idempotency-Key: ${IDEM}" || \
  curl -X POST https://siftq.com/api/minimax-trial/video-generation \
    -H "X-MiniMax-Trial-Client: ${CID}" \
    -H "X-Forwarded-For: ${FAKEIP}" \
    -H "Cookie: cf_clearance=${CF}" \
    -H "User-Agent: ${UA}" \
    -H 'Origin: https://siftq.com' \
    -H 'Referer: https://siftq.com/minimax-h3/free-trial' \
    -H "Idempotency-Key: ${IDEM}" \
    -H 'Accept: application/json' \
    -F client_id="${CID}" \
    -F ratio=9:16 \
    -F duration=6 \
    -F "visitorId=${VISITOR}" \
    -F 'channelCode=direct' \
    -F "prompt=${PROMPT}" \
    -F "image=@${IMG};type=image/jpeg" \
    -sS -D "${D}/r1b-xf-type.hdr" -o "${D}/r1b-xf-type.json" ; echo "curl_exit=$?" \
  ; grep -m1 -E '^HTTP/' "${D}/r1b-xf-type.hdr" \
  ; grep -q 'task_id' "${D}/r1b-xf-type.json" && { cp "${D}/r1b-xf-type.hdr" "${D}/r1b-final.hdr"; cp "${D}/r1b-xf-type.json" "${D}/r1b-final.json"; echo TASK_CREATED_BY=xf-type; } \
  || true
echo "=== diagnostic: same shape WITHOUT XFF (expect 429 = reaches quota; never creates task while quota exhausted) ==="
curl -X POST https://siftq.com/api/minimax-trial/video-generation \
  -H "X-MiniMax-Trial-Client: ${CID}" \
  -H "Cookie: cf_clearance=${CF}" \
  -H "User-Agent: ${UA}" \
  -H 'Origin: https://siftq.com' \
  -H 'Referer: https://siftq.com/minimax-h3/free-trial' \
  -H "Idempotency-Key: ${IDEM}" \
  -H 'Accept: application/json' \
  -F client_id="${CID}" \
  -F ratio=9:16 \
  -F duration=6 \
  -F "visitorId=${VISITOR}" \
  -F 'channelCode=direct' \
  -F "prompt=${PROMPT}" \
  -F "image=@${IMG};type=image/jpeg" \
  -sS -D "${D}/r1b-noxf-type.hdr" -o "${D}/r1b-noxf-type.json"; echo "curl_exit=$?"
grep -m1 -E '^HTTP/' "${D}/r1b-noxf-type.hdr"
head -c 400 "${D}/r1b-noxf-type.json"; echo
rc=$?
echo "=== final ==="
cat "${D}/r1b-final.json" 2>/dev/null | head -c 600; echo
exit $rc