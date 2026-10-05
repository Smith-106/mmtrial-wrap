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
