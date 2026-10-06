# mmtrial-wrap

Official-API-style wrapper around the SiftQ MiniMax trial flow, built on **CDP attach to a real RoxyBrowser profile**.

## Architecture

```
Client → FastAPI (:8080) → CDP attach to RoxyBrowser profile (:11611)
         → in-page fetch() on siftq.com → upstream response
```

**No cookie management, no fingerprint spoofing, no curl_cffi.** The browser's real fingerprint, real cookies (cf_clearance), and real IP (via profile proxy) handle authentication and CF challenges.

## Prerequisites

1. **RoxyBrowser** running with an open profile that has `siftq.com/minimax-h3/free-trial` loaded
2. That profile must have passed the Cloudflare challenge (cf_clearance cookie present)
3. The profile's CDP port must be discoverable via `DevToolsActivePort` file

## Quick Start

```bash
# 1. Open the profile in RoxyBrowser (navigate to siftq.com, pass CF challenge)

# 2. Find the CDP port
cat "$APPDATA/Roaming/RoxyBrowser/browser-cache/<profile-hash>/DevToolsActivePort"

# 3. Set env and run
export CDP_PORT=11611  # adjust to your profile
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Service health |
| `GET` | `/v1/usage` | Quota snapshot |
| `POST` | `/v1/generations` | Create generation (multipart form) |
| `POST` | `/v1/generations:await` | Create + block until terminal |
| `POST` | `/v1/batches` | Submit N images x N prompts (202 + batch_id) |
| `GET` | `/v1/batches/{id}` | Batch progress (per-item status/proxy/error) |
| `POST` | `/v1/batches/{id}:await` | Block until batch terminal |
| `GET` | `/v1/proxies` | Proxy pool health/rotation stats (no passwords) |
| `POST` | `/v1/proxies/check` | Probe all configured proxies |
| `GET` | `/v1/tasks/{id}` | Poll status |
| `GET` | `/v1/tasks/{id}/content` | Download (302 or `?stream=1`) |
| `POST` | `/v1/tasks` | Seed registry with external task |

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `CDP_HOST` | `localhost` | RoxyBrowser profile CDP host |
| `CDP_PORT` | `11611` | RoxyBrowser profile CDP port |
| `MM_PROXIES` | — | Proxy pool: `host:port:user:pass,...` (env only, never logged/persisted) |
| `BATCH_MAX_ITEMS` | `20` | Max items per batch |
| `BATCH_CONCURRENCY` | `2` | Concurrent in-flight batch items |
| `BATCH_STAGGER_S` | `2` | Stagger between item submissions (s) |
| `HOST` | `127.0.0.1` | Bind address (use `0.0.0.0` only behind `API_KEY`) |
| `PORT` | `8080` | Listen port |
| `API_KEY` | — | Optional bearer token for write endpoints |
| `POLL_SECONDS` | `7` | Poll interval for `:await` |
| `TASK_TTL_S` | `86400` | Task registry TTL |
| `DEFAULT_MAX_WAIT_S` | `600` | Max wait for `:await` |

## Security

- `API_KEY` optional — when set, write endpoints require `Authorization: Bearer <key>`
- Default bind is `127.0.0.1` (fail-closed for local use); set `HOST=0.0.0.0` only when exposing behind `API_KEY`
- No credentials stored; all auth is handled by the attached browser profile
- `MM_PROXIES` is read from env at request time; passwords never appear in logs, status output, or git
- Batch items are isolated: one item's failure never aborts siblings; each records its proxy label

## Batch example

```bash
# items: [{image_b64, image_name?, prompt?, ratio?, duration?, client_id?}]
python3 -c "import base64,json; b64=base64.b64encode(open('x.jpg','rb').read()).decode(); json.dump({'items':[{'image_b64':b64,'prompt':'a cat'},{'image_b64':b64,'prompt':'a dog'}]}, open('b.json','w'))"
curl -X POST localhost:8080/v1/batches -H 'Content-Type: application/json' -d @b.json
# -> {"batch_id":"mmbatch_...","total":2,"status":"running",...}
curl localhost:8080/v1/batches/mmbatch_...
```

Note: upstream quota is keyed on egress IP. Batch items get effective
per-proxy egress via fresh Playwright browser contexts created with
`proxy={server,username,password}` on the CDP-attached browser
(verified: `new_context(proxy=...)` works over `connect_over_cdp`,
egress IP == proxy IP). Single-generation endpoints keep the profile-tab
path (cookies intact); batch items trade cookies for fresh IPs — a fresh
context may hit a CF re-challenge, which surfaces per-item as 503/403
and never aborts siblings. Each batch item reuses one proxy page for
submit + all polls; the task record pins its proxy label so status and
content-stream reuse the same egress.
