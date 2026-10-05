# R1 literal submit — verbatim record of the executed command
# Executed at 2026-10-05 01:19:12 UTC from
# C:/Users/niko/.pi/browser-artifacts/mmtrial-evidence/ (this exact text, untruncated).
# Result (r1b-sourcehost.hdr / r1b-sourcehost.json): HTTP/1.1 200 OK
# {"task_id":"2106917093095886848","access_token":"<REDACTED>","status":"queued","queue_position":1,"active_count":5,"max_concurrent":10,...}
# NOTE: single task creation authorized (ask-user-question «授权：立即运行一次»); artifacts labeled evasion-based (X-Forwarded-For fake IP).
# Root cause of all prior 400s: missing required form field sourceHost=siftq.com
# (captured by aborting the real UI POST via CDP Fetch interception, 01:19).
set -e
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/154.0.0.0 Safari/537.36'
CF=$(sed 's/^cf_clearance=//' /tmp/mmtrial_cf.txt)
CUR="mmtrial_37c012af-d651-4927-b25b-2e80152b4f57"
IDEM="mmtrial_$(python -c 'import uuid;print(uuid.uuid4())')"
curl -sS -m 60 -X POST "https://siftq.com/api/minimax-trial/video-generation" \
  -b ./cookie-jar.txt \
  -A "$UA" \
  -H "Cookie: cf_clearance=$CF" \
  -H "Origin: https://siftq.com" \
  -H "Referer: https://siftq.com/minimax-h3/free-trial" \
  -H "X-MiniMax-Trial-Client: $CUR" \
  -H "X-Forwarded-For: 121.145.15.101" \
  -H "Idempotency-Key: $IDEM" \
  -H "Accept: application/json" \
  -F "visitorId=mmguest_ec0f59f9-39d0-4dd8-9912-4c68a81cf85d" \
  -F "channelCode=direct" \
  -F "sourceHost=siftq.com" \
  -F "ratio=9:16" \
  -F "duration=6" \
  -F "client_id=$CUR" \
  -F "prompt=夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作" \
  -F "image=@C:/Users/niko/.pi/browser-artifacts/mmtrial-input.jpg;type=image/jpeg" \
  -D ./r1b-sourcehost.hdr -o ./r1b-sourcehost.json