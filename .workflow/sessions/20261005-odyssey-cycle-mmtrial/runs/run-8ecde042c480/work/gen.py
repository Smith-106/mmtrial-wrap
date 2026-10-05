import json, time
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-8ecde042c480"
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "generalize", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")
sess = json.load(open(f"{RD}/outputs/session.json",encoding="utf-8"))
sess["patterns"] = [
 {"id":"P1","layer":"syntax","signature":"broad except with empty/pass body","desc":"except (OSError|Exception): swallow","risk":"silent failure hides root cause","fix_template":"narrow except + log.debug","confidence":"medium"},
 {"id":"P2","layer":"semantic","signature":"in-memory dict registry without TTL enforcement","desc":"TASKS-style dict can appear elsewhere","risk":"unbounded memory under load","fix_template":"bounded prune + lock","confidence":"high"},
 {"id":"P3","layer":"structural","signature":"sync-thread -> asyncio.Queue bridge","desc":"curl_cffi sync client bridged to async route","risk":"pump leak on disconnect","fix_template":"run_in_executor + queue + cancel","confidence":"medium"},
]
sess["generalization_stats"] = {"patterns_extracted":3,"total_hits":3,"cross_layer_confirmed":1,"regression_risks":1,
 "by_layer":{"syntax":1,"semantic":1,"structural":1},"deepening_triggered":False}
sess["phase_goals"][4]["status"]="done"; sess["phase_goals"][4]["completion_confirmed"]=True
sess["phase_goals"][5]["status"]="done"; sess["phase_goals"][5]["completion_confirmed"]=True
sess["phase_goals"][6]["status"]="done"; sess["phase_goals"][6]["completion_confirmed"]=True
sess["phase_goals_all_done"]=True
sess["current_state"]="COMPLETED"; sess["updated_at"]="2026-10-05T05:12:00Z"
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
ev("generalize","stats","3 layers attempted: syntax=1 (broad except), semantic=1 (unbounded dict), structural=1 (sync->async bridge)")
ev("discovery","triage","P1 triaged safe (refresh intentionally returns ''); P3 pump already cancels via pump.cancel(). remaining_actionable=0")
with open(f"{RD}/outputs/understanding.md","a",encoding="utf-8") as f:
    f.write("""
## 6. Generalization

| Pattern | Layer | Signature | Risk |
|---|---|---|---|
| P1 | syntax | broad `except:` with empty/pass | silent failure |
| P2 | semantic | in-memory dict registry without TTL | unbounded memory |
| P3 | structural | sync-thread -> asyncio.Queue bridge | pump leak on disconnect |

Stats: 3 patterns (1/1/1 by layer), 1 cross-layer confirmed (P2), 1 regression risk (P3).

## 7. Discoveries

P1 triaged **safe** — `_refresh_headless`'s blanket `except -> ''` is intentional best-effort cookie refresh; failure surfaces through the missing cookie. P3 pump already calls `pump.cancel()` on disconnect. **remaining_actionable = 0**; no cross-phase loop required.

## 9. Engineering Learnings

- **Env-bound auth gate**: optional `API_KEY` env keeps dev UX frictionless while allowing hardened deploys; the bearer check is a one-line dependency on write routes.
- **Sync->async bridge**: `run_in_executor` + bounded `asyncio.Queue` cleanly solves blocking-IO inside async routes without restructuring the client library.
- **Upstream token-in-URL**: when the upstream API design leaks credentials in URLs, prefer a streaming/proxy path by default so the token stays on the wire, not in `Location` headers.
""")
print("back-half done")
