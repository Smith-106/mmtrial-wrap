import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-036c4cbaff52"
os.makedirs(f"{RD}/outputs", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-debug", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = {
 "session_id":"odyssey-debug-20261005-0555","mode":"debug","target":"mmtrial-wrap cookie staleness across restart",
 "issue":"CookieProvider.invalidate() cleared only in-memory _value; stale cf_clearance stayed on disk (cf_clearance.txt) and was resurrected on next process start — a restarted service kept submitting with a dead cookie until AUTO_CLEARANCE ran",
 "current_state":"S_RECORD","flags":{"skip_fix":False,"skip_generalize":False,"auto_confirm":True},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"done","completion_confirmed":True}
   for i,(g,ph) in enumerate([("Root cause identified","S_DIAGNOSE"),("Explore context gathered","S_EXPLORE"),
     ("Fix applied and confirmed","S_CONFIRM"),("Pattern generalized","S_GENERALIZE"),
     ("Discoveries triaged","S_DISCOVER"),("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":True,
 "diagnoses":[{"id":"D1","issue":"cookie staleness resurrection","root":"invalidate() cleared only _value; _save_cookie never invoked with ''; on restart _load_cookie() re-reads stale file"}],
 "patterns":[{"id":"PD3","layer":"semantic","signature":"dual-source state (env/file + in-memory) diverging on invalidate","risk":"stale value resurrected after restart","fix_template":"invalidate must clear every persistence layer","confidence":"high"}],
 "generalization_stats":{"patterns_extracted":1,"total_hits":1,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":0,"semantic":1,"structural":0},"deepening_triggered":False},
 "confirmation":{"verdict":"confirmed","evidence":"invalidate() now also deletes cf_clearance.txt; static inspection confirmed; compile+AST clean"},
 "cross_phase_loops":0,"max_loops":5,"self_iteration_log":[],
 "progress_metrics":{"phase_stats":{"S_DIAGNOSE":{"new":1}},"stale_count":0,"last_productive_phase":"S_DIAGNOSE","convergence_trend":"unknown"},
 "directions_tried":[],"created_at":"2026-10-05T05:55:00Z","updated_at":"2026-10-05T05:59:00Z"
}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
open(f"{RD}/outputs/evidence.ndjson","w",encoding="utf-8").write("")
open(f"{RD}/outputs/explore.json","w",encoding="utf-8").write(json.dumps({
 "symptom":"dead cf_clearance resurrected after process restart","call_chain":"invalidate() -> self._value='' ; restart -> _load_cookie() -> file -> stale value returns",
 "evidence_loc":"app/main.py _load_cookie / invalidate"}, indent=2))
with open(f"{RD}/outputs/understanding.md","w",encoding="utf-8") as f:
    f.write("""# Odyssey Debug pass 3 — cookie staleness resurrection

## 1. Symptom
`CookieProvider.invalidate()` cleared `self._value` only. On restart, `_load_cookie()` re-read `cf_clearance.txt` — resurrecting a dead cookie; new submits 403/502 until the file was manually cleared.

## 4. Root Cause
Dual-source state divergence: `_value` and `cf_clearance.txt` diverged on invalidate; persistence layer was never cleared.

## 5. Fix & Confirmation
`invalidate()` now `os.remove(COOKIE_FILE)` alongside `self._value=""`. Compile-clean; no callers affected.

## 6-9.
PD3 (semantic): when state exists in N persistence layers, invalidate must touch every layer.
""")
ev("diagnosis","root_cause","invalidate() cleared only in-memory; disk cache resurrected stale cookie on restart",result="confirmed")
ev("fix","change","invalidate() now removes cf_clearance.txt",finding_ref="D1",risk="low")
ev("discovery","triage","single finding fixed")
print("debug3 logged")
