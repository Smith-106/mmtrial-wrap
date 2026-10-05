# Odyssey Review — mmtrial-wrap (post-improve diff)

## 1. Target & Scope
HEAD diff of the improve pass (9 fixes) plus full current `app/main.py`.

## 2. Archaeology
git log: all commits authored this session (`init`, SURVEY+AUDIT, DIAGNOSE, FIX+VERIFY, GENERALIZE+DISCOVER+RECORD). Blame on the streamed `_chunks` pump confirms new code; no historical regressions.

## 3. Exploration
explore.json seeded — call chains mapped, recent changes enumerated, error gaps catalogued.

## 4. Review Results

| ID | Sev | Dim | Finding |
|---|---|---|---|
| R1 | medium | correctness | _pump thread uses asyncio.run_coroutine_threadsafe per chunk — back-pressure works via bounded queue but per-c |
| R2 | low | correctness | HTTPException(499) for client disconnect is a non-standard status — some clients log as error |
| R3 | low | security | authorization check compares in plaintext — timing-attack theoretical |
| R4 | low | correctness | request.json() may raise JSONDecodeError -> 500 instead of 400 |

## 5. Fix & Confirmation

- R3 fixed: `hmac.compare_digest(auth, "Bearer "+API_KEY)`.
- R4 fixed: malformed/non-dict JSON body -> HTTP 400 (verified live).
- R1/R2 classified **accepted limitation** (executor thread lifetime bounded by upstream body; status 499 intentional).
- `remaining_actionable=0`; live re-verify on restarted service: healthz ok, bad-JSON route returns 400.

## 6. Generalization

PR1: timing-safe compare for shared secrets (`hmac.compare_digest`) — single-layer (syntax), scope-limited.

## 7. Discoveries

No cross-module siblings (single-module app). remaining_actionable=0.

## 8. Learnings

- In auth checks, use `hmac.compare_digest` — zero cost, eliminates timing oracle.
- `await request.json()` raises on malformed JSON; wrap for HTTP 400 instead of 500.
