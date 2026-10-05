# Verification matrix — CDP-attach variant

Prerequisites: RoxyBrowser running, `siftq.com/minimax-h3/free-trial` tab open
with a valid `cf_clearance`, CDP port discoverable via `DevToolsActivePort`
(default `11611`). No cookie env vars needed — the browser profile owns auth.

| Step | Command | Expected |
|---|---|---|
| Build | `docker build -t mmtrial-wrap:latest .` | image `mmtrial-wrap:latest` |
| Start | `CDP_PORT=11611 docker compose up -d` | container healthy |
| Health | `curl http://localhost:8080/healthz` | `{"ok":true,"cdp":"…","tasks":…}` |
| Quota | `curl http://localhost:8080/v1/usage` | `{"used":…,"remaining":…}` |
| Seed task | `curl -X POST /v1/tasks -d '{"task_id":"…","access_token":"…","client_id":"…"}'` | `{"ok":true}` |
| Poll status | `curl /v1/tasks/{id}` | `{…,"status":"succeeded",…}` |
| Content (redirect) | `curl -I /v1/tasks/{id}/content` | `307` to upstream URL |
| Content (stream) | `curl /v1/tasks/{id}/content?stream=1 -o out.mp4` | 200, `video/mp4` |
| One-shot create | `curl -X POST /v1/generations:await -F image=@x.jpg -F prompt=…` | `{task_id,final.status:"succeeded",content_url}` |
| Bad JSON | `curl -X POST /v1/tasks -d 'not json'` | `400 {"error":…}` |
| Batch submit | `curl -X POST /v1/batches -d '{items:[2x image_b64]}'` | `202 {batch_id,total:2}` |
| Batch progress | `curl /v1/batches/{id}` | per-item status/proxy/error |
| Batch await | `curl -X POST /v1/batches/{id}:await` | terminal summary |
| Proxy pool | `curl /v1/proxies` | `{size,proxies:[...]}` (no passwords) |
| Proxy check | `curl -X POST /v1/proxies/check` | alive/latency/egress per proxy |
| No-task payload | upstream returns non-task body (e.g. CF HTML) | `503` with re-challenge hint |

# Evidence (2026-10-05, CDP-attach cleanup pass)
- `app/main.py`: dead curl_cffi cookie layer removed
  (`CookieProvider`/`COOKIES`/`_base_headers`/`MM_XFF`/`IPV4`/cookie envs);
  imports trimmed; `_submit` drops unused `idem`; `healthz` reports the `cdp`
  endpoint; default bind `127.0.0.1`; non-task upstream payload → `503` with
  an actionable CF re-challenge message instead of a `KeyError` 500.
- Live (local uvicorn, RoxyBrowser Chrome/154 @ `:11611`):
  - `GET /healthz` → `{"ok":true,"cdp":"localhost:11611","tasks":0}`
  - `GET /v1/usage` → `{enabled:true,…,limit:2,used:2,remaining:0}`
  - `POST /v1/tasks` (bad json) → `400 body must be JSON`
  - `GET /docs` → 200 (1011 B); `openapi.json` → 7 paths
  - `POST /v1/tasks` seed → `{"ok":true}`; `GET /v1/tasks/{id}` with
    placeholder creds → upstream `400 A valid trial client id is required`
    surfaced as a JSON error (no crash — the request genuinely reached
    siftq.com through the browser's in-page fetch).
- Prior full-flow evidence (pre-cleanup, unchanged CDP code path):
  task `2106967203628830720` succeeded; stream 1,225,914 B, `video/mp4`,
  ffprobe `h264 768×1344 + aac`, `duration=6.583333`, sha256 `09e8e103…`.
- Batch/proxy evidence (2026-10-05, quota-exhausted browser IP):
  - `POST /v1/batches` (2 valid items) → `202 {batch_id:mmbatch_7c5f1476218b4ebd}`
  - progress → `completed total:2 done:2 ok:0 fail:2`, each item isolated with
    its proxy label (`31.59.20.176:6754`, `64.137.96.74:6641`) and clean
    `http 429 rate_limit_error` (browser-IP quota, not a code fault)
  - `POST /v1/batches/{id}:await` → terminal summary; bad base64 → `400`
  - `POST /v1/proxies/check` → `alive 10/10`, all `proto:http`,
    latencies ~1–1.9s, no password keys in output
  - Blocking point: browser egress IP quota `limit:2 used:2 remaining:0`;
    pool entries need per-profile browser egress to take effect.
