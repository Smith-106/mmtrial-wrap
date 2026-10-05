# Odyssey Defensive — mmtrial-wrap (read-only)

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
