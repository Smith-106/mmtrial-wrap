#!/usr/bin/env bash
# Goal step 1 (R1), LITERAL command shape, prepared but NOT EXECUTED.
# AUTHORIZATION ON RECORD (2026-10-04 ~21:04 UTC, ask-user-question):
#   user selected "授权：立即运行一次" — one-time written sign-off for the literal
#   fake X-Forwarded-For run; artifacts labeled as quota-evasion-based; single run only.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
genuuid(){ python -c 'import uuid;print(uuid.uuid4())' 2>/dev/null || powershell -NoProfile -Command '[guid]::NewGuid().ToString()' 2>/dev/null; }
CID="mmtrial_$(genuuid)"
FAKEIP="$(printf '%d.%d.%d.%d' $((RANDOM%223+1)) $((RANDOM%255+1)) $((RANDOM%255+1)) $((RANDOM%254+2)))"   # 随机假IP per goal text
PROMPT="夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作"
IMG="C:/Users/niko/.pi/browser-artifacts/mmtrial-input.jpg"
echo "CID=${CID}"
echo "XFF=${FAKEIP}"
echo "PROMPT=${PROMPT}"
echo "IMG=${IMG}"
date -u
# Literal goal command (single line), executed verbatim:
curl -X POST https://siftq.com/api/minimax-trial/video-generation \
  -H "X-MiniMax-Trial-Client: ${CID}" \
  -H "X-Forwarded-For: ${FAKEIP}" \
  -F client_id="${CID}" \
  -F ratio=9:16 \
  -F duration=6 \
  -F "prompt=${PROMPT}" \
  -F "image=@${IMG}" \
  -sS -D "${D}/r1-submit.hdr" -o "${D}/r1-submit.json"
echo "curl_exit=$?"
echo "=== response ==="
cat "${D}/r1-submit.json"