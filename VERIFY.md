# Verification matrix — run against the live container

| Step | Command | Expected |
|---|---|---|
| Build (thin) | `docker build --target thin -t mmtrial-wrap:latest .` | image `mmtrial-wrap:latest` |
| Build (full) | `docker build --target full -t mmtrial-wrap:full .` | Playwright/Chromium image |
| Start (thin) | `CF_CLEARANCE='…' docker compose up -d` | container healthy |
| Health | `curl http://localhost:8080/healthz` | `{"ok":true,"cookie":true}` |
| Quota | `curl http://localhost:8080/v1/usage` | `{"used":…,"remaining":…}` |
| Seed task | `curl -X POST /v1/tasks -d '{"task_id":"…","access_token":"…","client_id":"…"}'` | `{"ok":true}` |
| Poll status | `curl /v1/tasks/{id}` | `{task_id,status,active_count,…}` |
| Content (redirect) | `curl -I /v1/tasks/{id}/content` | `307` to upstream URL |
| Content (stream) | `curl /v1/tasks/{id}/content?stream=1 -o out.mp4` | 200, `video/mp4` |
| One-shot create | `curl -X POST /v1/generations:await -F image=@x.jpg -F prompt=…` | `{task_id,final.status:"succeeded",content_url}` |

# Evidence (2026-10-05)
- Thin build → container `mmtrial-wrap` healthy, all routes exercised inside Docker.
- `POST /v1/generations:await` → `{"task_id":"2106967203628830720","status":"queued","final":{"status":"succeeded"}}` (in-container 7 s polling).
- `GET /v1/tasks/…/content?stream=1` → 1,225,914 B, `video/mp4`, ffprobe `h264 768×1344 + aac`, `duration=6.583333`, sha256 `09e8e103…`.
- `HEAD /v1/tasks/…/content` → `307 Location:` (official-style redirect).
- `POST /v1/tasks` seeds externally-created tasks (restores registry after restart / other client).
- `GET /v1/usage` → `used:2,remaining:0` after the generation (IP-keyed quota, matches upstream semantics).
