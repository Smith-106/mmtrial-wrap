# mmtrial-wrap

A Dockerized API wrapper that turns the SiftQ MiniMax trial flow into an
official-feeling REST surface. Downstream callers use the simple `POST
/v1/generations` / `GET /v1/tasks/{id}` / `GET /v1/tasks/{id}/content` shape;
the service internally handles the Cloudflare clearance, the telemetry fields
(`visitorId`/`channelCode`/`sourceHost`), the trial `client_id`, polling, and
content download.

## Quickstart (thin — provide `cf_clearance` yourself)

```bash
export CF_CLEARANCE='<cf_clearance from your real browser session>'
docker compose up -d --build
# then:
curl -X POST http://localhost:8080/v1/generations \
  -F image=@your.jpg -F ratio=9:16 -F duration=6 -F prompt='镜头描述'
# -> {"task_id":"…","status_url":"/v1/tasks/…","content_url":"…"}
curl http://localhost:8080/v1/tasks/<task_id>          # poll every 7 s
curl -L http://localhost:8080/v1/tasks/<task_id>/content  # 302 -> video or ?stream=1
```

## Full (AUTO_CLEARANCE=1 — self-refresh cf_clearance via headless Chromium)

```bash
docker build --target full -t mmtrial-wrap:full .
docker run -d -p 8080:8080 -e AUTO_CLEARANCE=1 -v cf-cookie:/data mmtrial-wrap:full
# no CF_CLEARANCE needed; the container fetches one on startup/failure.
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/v1/generations` | multipart: `image` (file), `prompt`?, `ratio`=`9:16`, `duration`=`6`, `client_id`? → `{task_id,status_url,content_url,upstream}` |
| POST | `/v1/generations:await` | same fields + `timeout_s` → blocks until `succeeded`/`failed`/`error`, then returns `final` + `content_url` |
| GET | `/v1/tasks/{task_id}` | upstream status JSON (`queued`/`running`/`succeeded`/`failed`) |
| GET | `/v1/tasks/{task_id}/content` | 302 redirect to upstream URL (or `?stream=1` to pipe bytes) |
| GET | `/v1/usage` | quota snapshot |
| POST | `/v1/tasks` | register an external task `{task_id,client_id,access_token}` (registry seed for cross-restart or cross-client polling) |
| GET | `/healthz` | liveness |

Note: the upstream state machine is `queued → running → succeeded` — there is
**no** `dispatching` state on the wire; it exists only as a frontend label.

## Configuration (env)

- `CF_CLEARANCE` — initial cf_clearance value (thin mode; takes precedence over the file)
- `CF_COOKIE_FILE` (default `/data/cf_clearance.txt`) — persistent cookie store (mounted volume)
- `AUTO_CLEARANCE=1` — enable Playwright/headless self-refresh (only meaningful on the `full` target)
- `POLL_SECONDS` (default `7`) — status poll cadence for `:await`
- `DEFAULT_MAX_WAIT_S` (default `600`)
- `MM_XFF` — optional `X-Forwarded-For` to send upstream (empty = omit)
- `MM_CHANNEL` (default `direct`), `MM_SOURCE_HOST` (default `siftq.com`)

## Notes for downstream integrators

- The trial quota is keyed by the request's **public IP** (not `client_id`);
  today's fresh-IP allotment is 2 free generations/day.
- `client_id` may be supplied per request; when omitted we mint a
  `mmtrial_<uuid>` (mirrors the browser's localStorage behavior).
- Image size/type is forwarded untouched; the upstream accepts JPG/PNG/WEBP
  up to ~10 MB.
- The upstream emits only `queued → running → succeeded`; there is no
  `dispatching` state on the wire (it's a frontend-only label).
- `X-Forwarded-For` is **optional** (`MM_XFF`) and off by default — the
  upstream keys quota on the real connecting IP.

## Files

- `Dockerfile` — `thin` target (FastAPI + curl_cffi only) + `full` target (Playwright/Chromium for `AUTO_CLEARANCE=1` cf_clearance self-refresh).
- `docker-compose.yml` — thin service w/ cookie volume.
- `run.sh` — build/up/down/logs/test shortcuts.
- `client-example.sh` — end-to-end official-style consumer (submit → poll → download).
- `VERIFY.md` — verification matrix + evidence log.
