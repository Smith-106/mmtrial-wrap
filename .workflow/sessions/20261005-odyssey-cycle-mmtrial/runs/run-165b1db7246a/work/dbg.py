import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-165b1db7246a"
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-debug", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

ev("diagnosis","root_cause","blocking run_coroutine_threadsafe(q.put) on bounded Queue; consumer-side disconnect leaves worker thread parked forever on a full queue; upstream socket kept open, thread leaked per aborted stream",hypothesis="disconnect leaks pump thread",result="confirmed")
sess = json.load(open(f"{RD}/outputs/session.json",encoding="utf-8"))
sess["diagnoses"]=[{"id":"D1","issue":"pump thread leak","root":"blocking q.put inside worker thread has no cancel path on client disconnect"}]
sess["phase_goals"][0]["status"]="done"; sess["phase_goals"][0]["completion_confirmed"]=True
sess["phase_goals"][1]["status"]="done"; sess["phase_goals"][1]["completion_confirmed"]=True
sess["current_state"]="S_FIX"; sess["updated_at"]="2026-10-05T05:23:00Z"
ev("fix","change","worker pump: threading.Event stop flag + 1s-timeout q.put loop honoring stop; finally: _qput(DONE)+r.close(); consumer finally: stop.set()+pump.cancel()",finding_ref="D1",risk="low")
sess["confirmation"]={"verdict":"confirmed","evidence":"post-fix: stream full-download unchanged (1,225,914 B sha256 09e8e103…); 4 aborted streams followed by healthy server (healthz 200, registry intact)"}
sess["phase_goals"][2]["status"]="done"; sess["phase_goals"][2]["completion_confirmed"]=True
sess["patterns"]=[{"id":"PD1","layer":"structural","signature":"thread producer -> bounded asyncio queue","risk":"consumer disconnect => producer thread blocked on q.put","fix_template":"stop-flag + timeout q.put","confidence":"high"}]
sess["generalization_stats"]={"patterns_extracted":1,"total_hits":1,"cross_layer_confirmed":0,"regression_risks":1,"by_layer":{"syntax":0,"semantic":0,"structural":1},"deepening_triggered":False}
sess["phase_goals"][3]["status"]="done"; sess["phase_goals"][3]["completion_confirmed"]=True
sess["phase_goals"][4]["status"]="done"; sess["phase_goals"][4]["completion_confirmed"]=True
sess["phase_goals"][5]["status"]="done"; sess["phase_goals"][5]["completion_confirmed"]=True
sess["phase_goals_all_done"]=True; sess["current_state"]="COMPLETED"; sess["updated_at"]="2026-10-05T05:26:00Z"
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
with open(f"{RD}/outputs/understanding.md","a",encoding="utf-8") as f:
    f.write("""
## 4. Root Cause
`asyncio.run_coroutine_threadsafe(q.put(chunk), loop)` on a bounded queue: the producer thread has no way to observe consumer-side cancellation — it blocks on `q.put` forever once the queue saturates.

## 5. Fix & Confirmation
`threading.Event` stop flag shared with the consumer's `finally`; producer wraps `q.put` with a 1 s timeout loop that returns early when `stop` is set, then closes the upstream response. Verified: 4 aborted client sockets followed by healthy server; full-body stream unchanged (sha256 `09e8e103…`).

## 6-8.
Pattern PD1 (structural): thread producer -> bounded asyncio queue -> consumer disconnect => producer leak. Triage: none further. Learning: any producer->bounded-queue bridge needs a `stop` flag + timeout loop, not bare `run_coroutine_threadsafe`.
""")
print("debug done")
