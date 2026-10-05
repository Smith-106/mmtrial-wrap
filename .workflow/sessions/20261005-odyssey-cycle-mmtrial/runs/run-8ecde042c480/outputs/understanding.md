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
