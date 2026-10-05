# Odyssey Debug pass 3 — cookie staleness resurrection

## 1. Symptom
`CookieProvider.invalidate()` cleared `self._value` only. On restart, `_load_cookie()` re-read `cf_clearance.txt` — resurrecting a dead cookie; new submits 403/502 until the file was manually cleared.

## 4. Root Cause
Dual-source state divergence: `_value` and `cf_clearance.txt` diverged on invalidate; persistence layer was never cleared.

## 5. Fix & Confirmation
`invalidate()` now `os.remove(COOKIE_FILE)` alongside `self._value=""`. Compile-clean; no callers affected.

## 6-9.
PD3 (semantic): when state exists in N persistence layers, invalidate must touch every layer.
