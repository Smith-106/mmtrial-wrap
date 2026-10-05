# Odyssey Review pass 3 — cookie-fix diff

## 4. Review Results
Diff reviewed: `invalidate()` now removes `cf_clearance.txt`; `cookie_override` plumbed through `_base_headers`/`_post_generation`; `_submit` uses `get_fresh()`/`ensure()` return values.

Single residual note (R5, informational): retry on 403/502 re-uses the same multipart builder — correct because the cookie travels in headers only, not in the multipart body. No action needed.

remaining_actionable = 0.
