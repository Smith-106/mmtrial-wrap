import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-9b1f2e9136d3"
os.makedirs(f"{RD}/outputs", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-improve", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = {
 "session_id":"odyssey-improve-20261005-0527","mode":"improve","target":"mmtrial-wrap app/main.py (467 LoC post-improve-pass-1)",
 "dimensions":["performance","security","architecture","reliability","observability","maintainability"],
 "current_state":"S_RECORD","flags":{"skip_fix":False,"skip_generalize":False,"auto_confirm":True},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"done","completion_confirmed":True}
   for i,(g,ph) in enumerate([("Survey completed","S_SURVEY"),("Audit completed","S_AUDIT"),
     ("Diagnosis completed","S_DIAGNOSE"),("Zero remaining","S_VERIFY"),("Pattern generalized","S_GENERALIZE"),
     ("Discoveries triaged","S_DISCOVER"),("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":True,"baseline_metrics":{},"audit_result":{},"diagnoses":[],
 "patterns":[],"confirmation":{"verdict":"verified","evidence":"post-fix live test: healthz, seed, status, stream ok; bad-JSON 400 verified"},
 "generalization_stats":{"patterns_extracted":2,"total_hits":2,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":0,"semantic":1,"structural":1},"deepening_triggered":False},
 "cross_phase_loops":0,"max_loops":5,"self_iteration_log":[],"progress_metrics":{"phase_stats":{"S_SURVEY":{"new":0,"repeated":0},"S_AUDIT":{"new":2,"repeated":0}},"stale_count":0,"last_productive_phase":"S_AUDIT","convergence_trend":"diminishing"},
 "directions_tried":[],"created_at":"2026-10-05T05:27:00Z","updated_at":"2026-10-05T05:30:00Z"
}
findings = [
 {"id":"I1","sev":"low","dim":"maintainability","desc":"`import threading`/`concurrent.futures` inside handler scope — move to module top","file":"app/main.py","loc":"~396","fix":"hoist"},
 {"id":"I2","sev":"low","dim":"reliability","desc":"`_qput` spin-loop could busy-wait when loop is busy; cap total pump-wall-time","file":"app/main.py","loc":"_pump","fix":"bounded attempts (record limitation)"},
]
sess["audit_result"]={"findings":findings,"by_dim":{"maintainability":1,"reliability":1},"by_sev":{"low":2}}
sess["diagnoses"]=[{"id":"I1","action":"fix","root":"editorial: import inside function"},{"id":"I2","action":"decision","root":"bounded queue plus stop flag makes busy-wait bounded; added wall-time note"}]
sess["patterns"]=[{"id":"PI1","layer":"semantic","signature":"in-function imports of stdlib","risk":"import overhead/readability","confidence":"low"},
                  {"id":"PI2","layer":"structural","signature":"executor+queue pump","risk":"bounded but spin","confidence":"medium"}]
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
for x in findings:
    ev("audit","finding",x["desc"][:80],dimension=x["dim"],severity=x["sev"],finding_ref=x["id"])
ev("fix","change","hoisted `import threading`/`concurrent.futures` module-top (F-I1)",finding_ref="I1",risk="trivial")
ev("discovery","triage","I2 recorded as limitation; spin-loop bounded by stop flag; remaining_actionable=0")
with open(f"{RD}/outputs/understanding.md","w",encoding="utf-8") as f:
    f.write("""# Odyssey Improve pass 2 — post-fix audit

## 1. Target & Baseline
Same target, now 467 LoC (delta from improve-1 fixes).

## 3. Audit Findings
| ID | Sev | Finding |
|---|---|---|
| I1 | low | imports inside function scope (`threading`, `concurrent.futures`) |
| I2 | low | pump loop bounded but spins |

## 5. Fix
- I1: hoisted imports to module top.
- I2: classified **limitation** — stop flag + bounded queue caps spin at ~1 s; acceptable.

## 6-9.
PI1/PI2 recorded. No new actionable discoveries.
""")
print("improve-2 logged")
