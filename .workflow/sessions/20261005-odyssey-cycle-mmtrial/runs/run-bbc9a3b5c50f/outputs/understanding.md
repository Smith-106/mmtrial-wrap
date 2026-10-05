# Odyssey Debug pass 4 — header injection

## 1-4.
Content-Disposition filename embeds user-supplied task_id raw. Single-layer bug, fixed by sanitizing to `[A-Za-z0-9_-]` + 80-char cap.

## 5.
`re.sub(r'[^A-Za-z0-9_-]', '_', task_id)[:80]` — preserves UUID shape, strips quotes/CRLF.

## 6-9.
PD4 (syntax): HTTP headers must never be built from raw user input.
