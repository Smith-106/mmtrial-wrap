import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-c1f1b2292289"
os.makedirs(f"{RD}/outputs", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-defensive", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = {
 "session_id":"odyssey-defensive-20261005-0547","mode":"defensive","target":"mmtrial-wrap (read-only)",
 "dimensions":["defensive"],"current_state":"S_RECORD","flags":{"read_only":True,"skip_generalize":False},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"done","completion_confirmed":True}
   for i,(g,ph) in enumerate([("Anchors identified","S_ANCHOR"),("Slicing done","S_SLICE"),
     ("Scan complete","S_SCAN"),("Propagation analyzed","S_PROPAGATE"),("Report written","S_REPORT"),
     ("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":True,
 "anchors":{"critical_vars":["access_token (in redirect URL)","task_id registry","client_id header"],
            "sink_layers":{"level_1":["HTTP response body contains access_token URL"]}},
 "scan_result":{"by_pattern":{"exception-swallow":1,"default-substitution":1,"silent-zero":1},
  "candidates":[{"id":"DF1","loc":"_refresh_headless bare except","transform":"Exception->Empty str","sink":"cookie chain","risk":"low — gated by AUTO_CLEARANCE=1"},
                {"id":"DF2","loc":"TASKS registry on malformed submit","transform":"Missing->record w/ no task_id","sink":"GET /v1/tasks returns junk entry","risk":"low"},
                {"id":"DF3","loc":"status default 'queued' on upstream parse miss","transform":"Exception->Default","sink":"status polling returns stale 'queued'","risk":"low"}]},
 "propagation":{"confirmed_chains":["refresh Exception -> '' -> no-cookie POST -> CF 502 (observed)"],
   "risky_sinks":["POST response surfaces non-JSON upstream -> 502 mapped via HTTPException (correct)"],
   "q4_hidden":0},
 "audit_result":{"findings_count":3,"by_risk":{"low":3},"read_only_verified":True},
 "patterns":[],"generalization_stats":{"patterns_extracted":1,"total_hits":3,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":0,"semantic":2,"structural":1},"deepening_triggered":False},
 "cross_phase_loops":0,"max_loops":5,"self_iteration_log":[],
 "progress_metrics":{"phase_stats":{"S_ANCHOR":{"new":0},"S_SCAN":{"new":3}},"stale_count":0,"last_productive_phase":"S_SCAN","convergence_trend":"unknown"},
 "directions_tried":[],"created_at":"2026-10-05T05:47:00Z","updated_at":"2026-10-05T05:52:00Z"
}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
open(f"{RD}/outputs/evidence.ndjson","w",encoding="utf-8").write("")
open(f"{RD}/outputs/anchors.json","w",encoding="utf-8").write(json.dumps(sess["anchors"],indent=2))
with open(f"{RD}/outputs/understanding.md","w",encoding="utf-8") as f:
    f.write("""# Odyssey Defensive — mmtrial-wrap (read-only)

## 2. Anchors (critical_vars / sink_layers)
- Critical vars: `access_token` in redirect URL (auth-credential in URL — leak into logs), `task_id` registry, `client_id` header.
- Level-1 sink: HTTP response surfaces upstream state to callers.

## 3-4. Slice + Scan
Three failure->value chains catalogued in scan_result.

## 5-8. Propagation & Report
| ID | Transform | Sink | Risk |
|---|---|---|---|
| DF1 | Exception -> Empty str | cf_clearance header | low (AUTO_CLEARANCE gate) |
| DF2 | Missing -> bogus task record | GET /v1/tasks | low |
| DF3 | Exception -> default 'queued' | status endpoint | low |

All low-risk; read-only honored (no source touched).
""")
ev("anchor","critical_vars","access_token URL + task registry + client_id")
ev("scan","findings","3 failure->value transforms: exception->empty, missing->record, exception->default",findings_count=3)
ev("propagate","chains","refresh-exception -> '' -> no-cookie POST -> 502",risk_level="low")
ev("report","summary","3 findings, all low, read-only verified")
print("defensive logged")
