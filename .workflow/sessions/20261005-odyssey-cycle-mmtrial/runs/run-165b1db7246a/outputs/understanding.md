# Odyssey Debug — pump thread leak on disconnect

## 1. Symptom
The `stream=1` content relay spawns a worker thread (`_pump`) that does
`iter_content()` + `asyncio.run_coroutine_threadsafe(q.put, loop)` per 64 KiB
chunk into a bounded `Queue(maxsize=8)`. If the HTTP client disconnects mid-body,
the async consumer stops pulling, the queue fills, `q.put` **blocks the worker
thread forever** — no exception path, no timeout; a zombie thread per aborted
stream + the upstream socket held open.

## 4. Root Cause
`asyncio.run_coroutine_threadsafe(q.put(chunk), loop)` on a bounded queue: the producer thread has no way to observe consumer-side cancellation — it blocks on `q.put` forever once the queue saturates.

## 5. Fix & Confirmation
`threading.Event` stop flag shared with the consumer's `finally`; producer wraps `q.put` with a 1 s timeout loop that returns early when `stop` is set, then closes the upstream response. Verified: 4 aborted client sockets followed by healthy server; full-body stream unchanged (sha256 `09e8e103…`).

## 6-8.
Pattern PD1 (structural): thread producer -> bounded asyncio queue -> consumer disconnect => producer leak. Triage: none further. Learning: any producer->bounded-queue bridge needs a `stop` flag + timeout loop, not bare `run_coroutine_threadsafe`.
