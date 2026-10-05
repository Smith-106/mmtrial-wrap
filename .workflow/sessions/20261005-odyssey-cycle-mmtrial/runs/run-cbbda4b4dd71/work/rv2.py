import json, time
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-cbbda4b4dd71"
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-review", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = json.load(open(f"{RD}/outputs/session.json",encoding="utf-8"))
fixes = [
 {"id":"R3","change":"hmac.compare_digest for bearer auth compare","risk":"low"},
 {"id":"R4","change":"register_task wraps request.json() -> 400 on malformed; non-dict body -> 400","risk":"low"},
]
for x in fixes:
    ev("fix","change",x["change"],finding_ref=x["id"],risk=x["risk"])
sess["review_result"]["remaining_actionable"] = 0
sess["phase_goals"][2]["status"]="done"; sess["phase_goals"][2]["completion_confirmed"]=True
sess["confirmation"]={"verdict":"confirmed","evidence":"live curl: bad JSON -> HTTP 400 body 'must be JSON'; healthz+routes OK on new code"}
sess["current_state"]="S_RECORD"
sess["phase_goals"][3]["status"]="done"; sess["phase_goals"][3]["completion_confirmed"]=True
sess["phase_goals"][4]["status"]="done"; sess["phase_goals"][4]["completion_confirmed"]=True
sess["phase_goals"][5]["status"]="done"; sess["phase_goals"][5]["completion_confirmed"]=True
sess["phase_goals_all_done"]=True
sess["generalization_stats"]={"patterns_extracted":1,"total_hits":1,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":1,"semantic":0,"structural":0},"deepening_triggered":False}
sess["patterns"]=[{"id":"PR1","layer":"syntax","signature":"timing-safe compare for secrets","desc":"compare_digest over == for bearer auth","risk":"timing leak","confidence":"high"}]
sess["updated_at"]="2026-10-05T05:19:00Z"
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
with open(f"{RD}/outputs/understanding.md","a",encoding="utf-8") as f:
    f.write("""
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
""")
ev("discovery","triage","no new actionable findings; R1/R2 accepted limitations")
ev("record","learn","learnings persisted §8")
print("review back-half done")
