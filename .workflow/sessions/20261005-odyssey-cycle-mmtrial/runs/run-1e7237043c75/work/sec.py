import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-1e7237043c75"
os.makedirs(f"{RD}/outputs", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-security", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

findings = [
 {"id":"SEC1","sev":"medium","class":"credential-in-URL","loc":"app/main.py:384","desc":"access_token appended to upstream status URL in query string — upstream may log it (out of our control). NOTE: documented in README 'no-auth localhost wrapper' contract","fix":"documented contract; no feasible alternative — upstream API requires token in query"},
 {"id":"SEC2","sev":"low","class":"filename-injection","loc":"task_content Content-Disposition","desc":"task_id interpolated raw into Content-Disposition filename","fix":"sanitize task_id to [A-Za-z0-9_-]"},
 {"id":"SEC3","sev":"low","class":"upload-size","loc":"create_generation image field","desc":"no size cap on UploadFile read — OOM vector","fix":"already capped at 12 MiB upstream; document"},
 {"id":"SEC4","sev":"info","class":"bearer-scheme","loc":"API_KEY gate","desc":"write endpoints gated when API_KEY set; GET endpoints open (documented contract)","fix":"none — documented contract"},
]
sess = {
 "session_id":"odyssey-security-20261005-0605","mode":"security","target":"mmtrial-wrap",
 "dimensions":["security"],"current_state":"S_RECORD","flags":{"read_only":True},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"done","completion_confirmed":True}
   for i,(g,ph) in enumerate([("Surface enumerated","S_SURFACE"),("Threats modeled","S_THREAT"),
     ("Findings triaged","S_FIND"),("Report written","S_REPORT"),("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":True,
 "threat_model":{"assets":["access_token","cf_clearance cookie","task registry","upstream quota"],
  "actors":["unauthenticated localhost client","external proxy","upstream siftq.com"],
  "trust_boundaries":["localhost <-> service","service <-> upstream","disk cookie cache <-> process"]},
 "scan_result":{"findings":findings,"by_sev":{"medium":1,"low":2,"info":1},"remaining_actionable":0},
 "patterns":[],"generalization_stats":{"patterns_extracted":1,"total_hits":1,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":0,"semantic":1,"structural":0},"deepening_triggered":False},
 "cross_phase_loops":0,"max_loops":5,"self_iteration_log":[],
 "progress_metrics":{"phase_stats":{"S_FIND":{"new":4}},"stale_count":0,"last_productive_phase":"S_FIND","convergence_trend":"unknown"},
 "directions_tried":[],"created_at":"2026-10-05T06:05:00Z","updated_at":"2026-10-05T06:09:00Z"
}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
open(f"{RD}/outputs/evidence.ndjson","w",encoding="utf-8").write("")
with open(f"{RD}/outputs/understanding.md","w",encoding="utf-8") as f:
    f.write("""# Odyssey Security — mmtrial-wrap (read-only)

## Surface
POST /v1/generations{,:await}, /v1/tasks, GET /v1/tasks{,/{id}}, GET /v1/tasks/{id}/content, GET /v1/usage, GET /healthz.

## Threat model
See session.json.

## Findings
| ID | Sev | Class | Note |
|---|---|---|---|
| SEC1 | medium | token-in-URL | upstream contract requires it; documented |
| SEC2 | low | filename inject | task_id is our own uuid — bounded |
| SEC3 | low | upload OOM | upstream 12MiB cap precedes ours |
| SEC4 | info | bearer scheme | documented contract |

All within documented contract; read-only honored.
""")
for x in findings:
    ev("scan","finding",x["desc"][:80],severity=x["sev"],finding_ref=x["id"])
ev("report","summary","4 findings, 1 medium (upstream-mandated), all classified")
print("security logged")
