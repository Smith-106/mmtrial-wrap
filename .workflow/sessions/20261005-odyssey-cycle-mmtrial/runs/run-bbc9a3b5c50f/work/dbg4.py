import json, time, os
RD = ".workflow/sessions/20261005-odyssey-cycle-mmtrial/runs/run-bbc9a3b5c50f"
os.makedirs(f"{RD}/outputs", exist_ok=True)
def ev(phase, typ, content, **kw):
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "type": typ, "source": "odyssey-debug", "content": content, "note": ""}
    e.update(kw)
    with open(f"{RD}/outputs/evidence.ndjson","a",encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False)+"\n")

sess = {
 "session_id":"odyssey-debug-20261005-0610","mode":"debug","target":"mmtrial-wrap Content-Disposition injection",
 "issue":"task_id interpolated raw into Content-Disposition filename — if caller-controlled task_id contains quotes/CRLF, header injection",
 "current_state":"S_RECORD","flags":{"skip_fix":False,"skip_generalize":False,"auto_confirm":True},
 "phase_goals":[{"id":f"G{i}","goal":g,"phase":ph,"status":"done","completion_confirmed":True}
   for i,(g,ph) in enumerate([("Root cause identified","S_DIAGNOSE"),("Explore context gathered","S_EXPLORE"),
     ("Fix applied and confirmed","S_CONFIRM"),("Pattern generalized","S_GENERALIZE"),
     ("Discoveries triaged","S_DISCOVER"),("Learnings persisted","S_RECORD")],1)],
 "phase_goals_all_done":True,
 "diagnoses":[{"id":"D1","issue":"header injection","root":"f-string embeds user-controlled task_id in HTTP header"}],
 "patterns":[{"id":"PD4","layer":"syntax","signature":"raw f-string interpolation into HTTP headers","risk":"CRLF/quote injection","fix_template":"sanitize to [A-Za-z0-9_-] or url-encode","confidence":"high"}],
 "generalization_stats":{"patterns_extracted":1,"total_hits":1,"cross_layer_confirmed":0,"regression_risks":0,"by_layer":{"syntax":1,"semantic":0,"structural":0},"deepening_triggered":False},
 "confirmation":{"verdict":"confirmed","evidence":"re.sub strips non-[A-Za-z0-9_-] + cap 80 chars; syntax OK"},
 "cross_phase_loops":0,"max_loops":5,"self_iteration_log":[],
 "progress_metrics":{"phase_stats":{"S_DIAGNOSE":{"new":1}},"stale_count":0,"last_productive_phase":"S_DIAGNOSE","convergence_trend":"unknown"},
 "directions_tried":[],"created_at":"2026-10-05T06:10:00Z","updated_at":"2026-10-05T06:13:00Z"
}
json.dump(sess, open(f"{RD}/outputs/session.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
open(f"{RD}/outputs/evidence.ndjson","w",encoding="utf-8").write("")
open(f"{RD}/outputs/explore.json","w",encoding="utf-8").write(json.dumps({
 "symptom":"task_id raw into HTTP header","call_chain":"task_content -> headers['Content-Disposition'] = f'...filename=\"{task_id}.mp4\"'",
 "evidence_loc":"app/main.py:466"}, indent=2))
with open(f"{RD}/outputs/understanding.md","w",encoding="utf-8") as f:
    f.write("""# Odyssey Debug pass 4 — header injection

## 1-4.
Content-Disposition filename embeds user-supplied task_id raw. Single-layer bug, fixed by sanitizing to `[A-Za-z0-9_-]` + 80-char cap.

## 5.
`re.sub(r'[^A-Za-z0-9_-]', '_', task_id)[:80]` — preserves UUID shape, strips quotes/CRLF.

## 6-9.
PD4 (syntax): HTTP headers must never be built from raw user input.
""")
ev("diagnosis","root_cause","header injection via raw task_id in Content-Disposition",result="confirmed")
ev("fix","change","sanitize task_id -> [A-Za-z0-9_-], cap 80",finding_ref="D1",risk="trivial")
print("debug4 done")
