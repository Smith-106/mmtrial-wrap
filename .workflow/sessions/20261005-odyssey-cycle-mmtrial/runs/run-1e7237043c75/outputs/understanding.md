# Odyssey Security — mmtrial-wrap (read-only)

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
