#!/usr/bin/env bash
# Official-API-style client usage — copy/paste after `run.sh up`.
# Requires curl; jq optional (pretty-prints).
BASE="${BASE:-http://localhost:8080}"
IMAGE="${IMAGE:-/tmp/wrap-test.jpg}"
set -euo pipefail

# 1) create + block until terminal (mirrors the original 3-step flow)
curl -sS -X POST "$BASE/v1/generations:await" \
  -F "image=@$IMAGE" -F "ratio=9:16" -F "duration=6" \
  -F "prompt=夜色中的东京街头，一个女孩转身回眸" \
  -F "timeout_s=300" -o /tmp/gen-await.json -w "HTTP %{http_code}\n"
cat /tmp/gen-await.json

TID=$(python -c 'import json;print(json.load(open("/tmp/gen-await.json"))["task_id"])')
TOK=$(python -c 'import json;print(json.load(open("/tmp/gen-await.json"))["upstream"]["access_token"])')

# 2) official-style polling (7 s cadence already baked in server side)
while true; do
  st=$(curl -sS "$BASE/v1/tasks/$TID" | python -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status=$st"
  [ "$st" = succeeded ] || [ "$st" = failed ] || [ "$st" = error ] && break || sleep 7
done

# 3) download
curl -sS "$BASE/v1/tasks/$TID/content?stream=1" -o "/tmp/$TID.mp4" -w "bytes=%{size_download}\n"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "/tmp/$TID.mp4"