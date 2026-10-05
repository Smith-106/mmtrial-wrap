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
| `GET` | `/v1/tasks/{id}` | Poll status |
| `GET` | `/v1/tasks/{id}/content` | Download (302 or `?stream=1`) |
| `POST` | `/v1/tasks` | Seed registry with external task |

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `CDP_PORT` | `11611` | RoxyBrowser profile CDP port |
| `HOST` | `0.0.0.0` | Bind address (use `127.0.0.1` for local-only) |
| `PORT` | `8080` | Listen port |
| `API_KEY` | — | Optional bearer token for write endpoints |
| `POLL_SECONDS` | `7` | Poll interval for `:await` |
| `TASK_TTL_S` | `86400` | Task registry TTL |
| `DEFAULT_MAX_WAIT_S` | `600` | Max wait for `:await` |

## Security

- `API_KEY` optional — when set, write endpoints require `Authorization: Bearer <key>`
- Default bind is `0.0.0.0` — **set `HOST=127.0.0.1` for local-only use**
- No credentials stored; all auth is handled by the attached browser profile
