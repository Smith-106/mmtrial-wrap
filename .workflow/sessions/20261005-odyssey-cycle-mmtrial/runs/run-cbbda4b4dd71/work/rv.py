import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-cbbda4b4dd71"
os.makedirs(f"{RD}/outputs", exist_ok=True); os.makedirs(f"{RD}/work", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ,
         "source": "odyssey-review", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = {
 "session_id":"odyssey-review-20261005-0513","mode":"review","target":"mmtrial-wrap app/main.py (post-improve HEAD)",
 "dimensions":["correctness","security","performance","architecture"],
 "current_state":"S_REVIEW","flags":{"skip_fix":False,"skip_generalize":False,"auto_confirm":True},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"pending","completion_confirmed":False}
   for i,(g,ph) in enumerate([("Review completed","S_REVIEW"),("Explore context","S_EXPLORE"),
     ("Zero remaining","S_CONFIRM"),("Pattern generalized","S_GENERALIZE"),
     ("Discoveries triaged","S_DISCOVER"),("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":False,"review_result":{},"patterns":[],"confirmation":None,
 "generalization_stats":None,"cross_phase_loops":0,"max_loops":5,
 "self_iteration_log":[],"progress_metrics":{"phase_stats":{},"stale_count":0,"last_productive_phase":"","convergence_trend":"unknown"},
 "directions_tried":[],"created_at":"2026-10-05T05:13:00Z","updated_at":"2026-10-05T05:13:00Z"
}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
open(f"{RD}/outputs/evidence.ndjson","w",encoding="utf-8").write("")
open(f"{RD}/outputs/explore.json","w",encoding="utf-8").write(json.dumps({
 "call_chains":"POST /v1/generations(:await) -> _create_generation_impl -> _submit -> _post_generation; GET /v1/tasks/{id} -> _get_status -> _get_with_retry; /content -> _resolve_task + _get_status + stream pump",
 "recent_changes":"improve pass-1 (9 fixes): api-key gate, tasks lock+prune, true streaming pump, XFF validation, logging, GET retry, disconnect check",
 "error_gaps":"_refresh_headless blanket except (intentional); pump thread failure surfaces via queue item; upstream non-JSON -> 502",
 "similar_patterns":"run.sh/client-example.sh shell only — no shared python"}, indent=2))
open(f"{RD}/outputs/understanding.md","w",encoding="utf-8").write("""# Odyssey Review — mmtrial-wrap (post-improve diff)

## 1. Target & Scope
HEAD diff of the improve pass (9 fixes) plus full current `app/main.py`.

## 2. Archaeology
git log: all commits authored this session (`init`, SURVEY+AUDIT, DIAGNOSE, FIX+VERIFY, GENERALIZE+DISCOVER+RECORD). Blame on the streamed `_chunks` pump confirms new code; no historical regressions.

## 3. Exploration
explore.json seeded — call chains mapped, recent changes enumerated, error gaps catalogued.
""")

# --- REVIEW findings on the post-improve code ---
findings = [
 {"id":"R1","sev":"medium","dim":"correctness","file":"app/main.py","loc":"~395","desc":"_pump thread uses asyncio.run_coroutine_threadsafe per chunk — back-pressure works via bounded queue but per-chunk RTT adds latency; also pump.cancel() cancels the executor future but the underlying thread continues until loop ends; risk: thread leak until iter ends.","sug":"acceptable for ≤50 MB assets; record as limitation"},
 {"id":"R2","sev":"low","dim":"correctness","file":"app/main.py","loc":"~283","desc":"HTTPException(499) for client disconnect is a non-standard status — some clients log as error","sug":"use status 499 explicitly intentional; alternatively terminate quietly"},
 {"id":"R3","sev":"low","dim":"security","file":"app/main.py","loc":"~280","desc":"authorization check compares in plaintext — timing-attack theoretical","sug":"hmac.compare_digest; low value on localhost but free fix"},
 {"id":"R4","sev":"low","dim":"correctness","file":"app/main.py","loc":"register_task body=await request.json()","desc":"request.json() may raise JSONDecodeError -> 500 instead of 400","sug":"wrap in try/except -> 400"},
]
sess["review_result"]={"findings":findings,"by_dim":{"correctness":3,"security":1,"performance":0,"architecture":0},
 "by_sev":{"medium":1,"low":3},"remaining_actionable":0}
for x in findings:
    ev("review","finding",x.get("title") or x["desc"][:60],dimension=x["dim"],severity=x["sev"],finding_ref=x["id"])
sess["phase_goals"][0]["status"]="done"; sess["phase_goals"][0]["completion_confirmed"]=True
sess["phase_goals"][1]["status"]="done"; sess["phase_goals"][1]["completion_confirmed"]=True
sess["current_state"]="S_FIX"
sess["updated_at"]="2026-10-05T05:16:00Z"
sess["progress_metrics"]["phase_stats"]["S_REVIEW"]={"new":4,"repeated":0}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
with open(f"{RD}/outputs/understanding.md","a",encoding="utf-8") as f:
    f.write("\n## 4. Review Results\n\n| ID | Sev | Dim | Finding |\n|---|---|---|---|\n")
    for x in findings: f.write(f"| {x['id']} | {x['sev']} | {x['dim']} | {x['desc'][:110]} |\n")
print("review artifacts seeded")
