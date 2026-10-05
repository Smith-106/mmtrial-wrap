# Odyssey Debug pass 2 — cookie refresh race

## 1. Symptom
Under concurrent `POST /v1/generations`, a request can race `CookieProvider`: `ensure()` holds an asyncio.Lock around `_refresh_headless`, but `get()` reads `_cookie` unsynchronized. If request A triggers refresh (clears `_cookie`) while request B has already passed `ensure()` and calls `get()`, B sees `None` and posts with no cf_clearance → CF 502.

## 4. Root Cause
Inconsistent lock scope: `ensure()` is async + locked, `get()` is sync + unlocked. Window between `_cookie = None` (in refresh) and `_cookie = new_value` is real.

## 5. Fix & Confirmation
Consolidate: make `get()` itself acquire the same asyncio.Lock (i.e., only `await ensure()` then `await get()` under one lock scope) OR change get() to read under lock. Implemented: `ensure()` returns the cookie under lock; `get()` deprecated on the hot path — callers use `await ensure()` which returns the fresh value.

## 6-9.
Pattern PD2 (structural): lock scope must cover check+read. Triage: clean. Learnings persisted.
