# Odyssey Improve ¡ª mmtrial-wrap

## 1. Target & Baseline

Target:  (358 LoC, FastAPI wrapper over SiftQ MiniMax trial). Baseline: manual E2E verified (container) ¡ª no unit test suite exists. Dependencies: fastapi/uvicorn/python-multipart/curl_cffi (4). Project: 6 files, ~23.6 KB.

## 2. Current State Survey

- Deps: fastapi, uvicorn[standard], python-multipart, curl_cffi==0.16.3 (4 prod deps). Dead imports: `secrets`, `PlainTextResponse`.
- No test suite; verification to date = container-level manual E2E (VERIFY.md).
- Error handling: HTTPException-based; blanket `except` in `_refresh_headless`; upstream JSON parse fail -> 502.

## 3. Audit Findings (10)

| ID | Sev | Dim | Finding |
|---|---|---|---|
| F1 | high | security | Unauthenticated task registry + access_token in redirect |
| F2 | medium | reliability | Unbounded TASKS dict |
| F3 | medium | performance | Pseudo-streaming buffers whole MP4 in memory |
| F4 | medium | security | MM_XFF env injected unvalidated into X-Forwarded-For |
| F5 | medium | observability | Zero logging |
| F6 | low | maintainability | Dead imports |
| F7 | low | reliability | Unlocked TASKS mutation |
| F8 | low | reliability | :await poll ignores client disconnect |
| F9 | low | architecture | God-module |
| F10 | medium | reliability | No upstream timeout/retry policy on GETs |

Severity matrix: 1 high (F1), 6 medium, 3 low.

## 4. Root Cause Diagnosis

- **F1** (fix_partially): wrapper designed as a localhost/dev tool; no auth layer by design. Token-in-URL is inherent to the upstream API (its own URLs embed access_token). True fix = keep 302 default but add API-key gate on write endpoints; proxy-stream default avoids token-in-URL when `stream` not asked.
- **F2** (fix): _prune_tasks only in create path
- **F3** (fix): used iter([r.content]) as quick impl
- **F4** (fix): env passthrough unvalidated
- **F5** (fix): no logging ever added
- **F6** (fix): leftover imports
- **F7** (fix): dict mutation w/o lock
- **F8** (fix): no disconnect check
- **F9** (decision): size OK
- **F10** (fix): no retry on idempotent GETs

Action plan: fix 9 (F1-partial, F2-F8, F10); decision 1 (F9 module split deferred).

## 5. Fix & Verification

- **F1**: Added optional API_KEY env bearer gate on POST /v1/generations*, POST /v1/tasks; access_token now only leaves via ?stream=1 path or explicit RedirectResponse (risk: low)
- **F2**: _prune_tasks also invoked inside tasks_lock on register/generate; async lock guards TASKS mutations (risk: low)
- **F3**: True chunked relay: upstream stream=True via run_in_executor, asyncio.Queue pump yields iter_content(64K), Content-Length passthrough (risk: medium (threading))
- **F4**: MM_XFF validated as IPv4/CSV via IPV4 regex before use (risk: low)
- **F5**: stdlib logging; INFO create/refresh, WARNING upstream 4xx, ERROR refresh fail (risk: low)
- **F6**: Removed dead imports secrets, PlainTextResponse (risk: trivial)
- **F7**: asyncio.Lock _tasks_lock around TASKS mutations (risk: low)
- **F8**: request.is_disconnected() checked each poll iter in :await (risk: low)
- **F10**: _get_with_retry bounded 2-retry exp backoff for idempotent GETs on 5xx/network (risk: low)

Verification: service restarted on new code; /healthz ¡ú ok, /v1/usage ¡ú upstream usage JSON, POST /v1/tasks seed ¡ú ok, GET /v1/tasks/{id} ¡ú upstream status, GET /v1/tasks/{id}/content?stream=1 ¡ú 1,225,914 B, ffprobe h264 768¡Á1344 + aac, duration 6.583333 s.

## 8. Improvement Metrics

| Metric | Before | After |
|---|---|---|
| Dead imports | 2 | 0 |
| TASKS unbounded | yes | lock-guarded, pruned |
| Streaming buffered full MP4 | yes | chunked relay |
| Logging | none | stdlib INFO/WARN/ERROR |
| GET retry | none | 2-retry exp backoff |
| API key gate | none | optional `API_KEY` env |
| MM_XFF validation | none | IPv4 regex |
| :await disconnect stop | no | is_disconnected check |

## 6. Generalization

| Pattern | Layer | Signature | Risk |
|---|---|---|---|
| P1 | syntax | broad `except:` with empty/pass | silent failure |
| P2 | semantic | in-memory dict registry without TTL | unbounded memory |
| P3 | structural | sync-thread -> asyncio.Queue bridge | pump leak on disconnect |

Stats: 3 patterns (1/1/1 by layer), 1 cross-layer confirmed (P2), 1 regression risk (P3).

## 7. Discoveries

P1 triaged **safe** â€” `_refresh_headless`'s blanket `except -> ''` is intentional best-effort cookie refresh; failure surfaces through the missing cookie. P3 pump already calls `pump.cancel()` on disconnect. **remaining_actionable = 0**; no cross-phase loop required.

## 9. Engineering Learnings

- **Env-bound auth gate**: optional `API_KEY` env keeps dev UX frictionless while allowing hardened deploys; the bearer check is a one-line dependency on write routes.
- **Sync->async bridge**: `run_in_executor` + bounded `asyncio.Queue` cleanly solves blocking-IO inside async routes without restructuring the client library.
- **Upstream token-in-URL**: when the upstream API design leaks credentials in URLs, prefer a streaming/proxy path by default so the token stays on the wire, not in `Location` headers.
