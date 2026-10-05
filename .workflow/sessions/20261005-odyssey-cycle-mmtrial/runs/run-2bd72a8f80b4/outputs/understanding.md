# Odyssey UI — mmtrial-wrap /docs

## Surface
`GET /docs` (Swagger UI) + `GET /openapi.json` — sole rendered surface; wrapper is API-first.

## Render Evidence
- `/docs` HTTP 200, 1,011 B, `swagger-ui` marker present.
- `/openapi.json` HTTP 200, 6,137 B; exposes all 7 routes.

## Findings
- UI1 (info): no custom UI by design — Swagger UI is the documented contract.

## Read-only honored
No source touched.
