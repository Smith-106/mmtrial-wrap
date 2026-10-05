#!/usr/bin/env bash
# Goal step 3 (R3), literal shape:
#   GET https://siftq.com/api/minimax-trial/video-generation/{task_id}/content?client_id=X&access_token=Y
# Values: REAL legit task .144 (browser E2E, real identity; no XFF anywhere).
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
TID=2106702460338950144
CID=mmtrial_37c012af-d651-4927-b25b-2e80152b4f57
TOK=988a2527-cd33-4663-a5f1-35b4affdf639
URL="https://siftq.com/api/minimax-trial/video-generation/${TID}/content?client_id=${CID}&access_token=${TOK}"
echo "URL=${URL}"
curl -sS -v -o "${D}/r3-download.mp4" -D "${D}/r3-content.hdr" "${URL}"
echo "curl_exit=$?"
echo "=== verify ==="
wc -c "${D}/r3-download.mp4"
sha256sum "${D}/r3-download.mp4"
file "${D}/r3-download.mp4" 2>/dev/null
ffprobe -v error -show_entries format=size,duration -show_entries stream=codec_name,width,height,avg_frame_rate -of default=noprint_wrappers=1 "${D}/r3-download.mp4" 2>&1
echo "expected_sha=54dc57809bec26c79390d05fdd92413c30a5a7f1ece350272de27caeb76665c3"