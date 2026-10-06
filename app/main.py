"""mmtrial-wrap — official-API-style wrapper around the SiftQ MiniMax trial flow.

All upstream traffic goes through the attached browser profile's own
fetch() (CDP in-page execution), so the browser's real fingerprint, cookies
and IP handle Cloudflare. This service exposes a clean, official-looking API:

    POST /v1/generations          -> create generation task
    POST /v1/generations:await    -> create + block until terminal
    POST /v1/batches              -> submit N images x N prompts (202 + batch_id)
    GET  /v1/batches/{batch_id}   -> batch progress
    POST /v1/batches/{id}:await   -> block until batch terminal
    GET  /v1/tasks/{task_id}      -> poll status
    GET  /v1/tasks/{task_id}/content -> download (302 redirect or stream)
    GET  /v1/usage                -> quota snapshot
    GET  /v1/proxies              -> proxy pool health/rotation stats
    POST /v1/proxies/check        -> probe all configured proxies
    GET  /healthz
"""
import asyncio, base64, hmac, logging, os, re, time, uuid, json
from typing import Optional

try:
    from app.proxy_pool import ProxyPool
except ImportError:  # direct module run
    from proxy_pool import ProxyPool

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse


log = logging.getLogger("mmtrial-wrap")

TRIAL_PATH = "/api/minimax-trial"
TRIAL_URL = "https://siftq.com" + TRIAL_PATH
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "7"))
TASK_TTL_S = int(os.getenv("TASK_TTL_S", "86400"))
DEFAULT_MAX_WAIT_S = int(os.getenv("DEFAULT_MAX_WAIT_S", "600"))
CDP_HOST = os.getenv("CDP_HOST", "localhost")
CDP_PORT = os.getenv("CDP_PORT", "11611")
PROMPT_DEFAULT = "夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作"
API_KEY = os.getenv("API_KEY", "").strip()  # optional: require on write endpoints
BATCH_MAX_ITEMS = int(os.getenv("BATCH_MAX_ITEMS", "20"))
BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "2"))
BATCH_STAGGER_S = float(os.getenv("BATCH_STAGGER_S", "2"))

# NOTE on proxies: upstream quota is keyed on egress public IP. Batch items
# get effective per-proxy egress via fresh Playwright browser contexts created
# with proxy={server,username,password} on the CDP-attached browser
# (verified: new_context(proxy=...) works over connect_over_cdp, egress IP ==
# proxy IP). Single-generation endpoints keep the profile-tab path (cookies
# intact); batch items trade cookies for fresh IPs — CF may re-challenge a
# fresh context, which surfaces per-item as 503/403 and never aborts siblings.
PROXIES = ProxyPool.from_env()

app = FastAPI(title="mmtrial-wrap", version="1.1.0")
# in-memory task registry: task_id -> {access_token, client_id, created_at, status}
TASKS: dict[str, dict] = {}
_tasks_lock = asyncio.Lock()


def _check_api_key(request: Request) -> None:
    """Optional bearer-token gate for write endpoints when API_KEY is set."""
    if not API_KEY:
        return
    auth = request.headers.get("authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {API_KEY}"):
        raise HTTPException(401, "invalid or missing API key")





# NOTE: the old curl_cffi cookie layer (CookieProvider/_base_headers/MM_XFF)
# was fully removed. All upstream traffic goes through CDP in-page fetch below.


# ------------------------- CDP in-page fetch ----------------------------------

async def _get_cdp_page():
    """Attach to the running RoxyBrowser profile's CDP and return the siftq.com page."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(503, "playwright not installed")
    cdp_url = f"http://{CDP_HOST}:{CDP_PORT}"
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)
    # Find the siftq.com page in the attached browser context
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "siftq.com" in page.url:
                return pw, browser, page
    raise HTTPException(503, "no siftq.com tab found in attached browser")


async def _post_via_cdp(client_id: str, image_b64: str, image_name: str,
                       prompt: str, ratio: str, duration: str, visitor_id: str) -> dict:
    """POST generation via the browser page's own fetch() — real fingerprint/cookies/IP."""
    pw, browser, page = await _get_cdp_page()
    try:
        result = await page.evaluate("""async ([fields, b64]) => {
            const fd = new FormData();
            for (const [k, v] of Object.entries(fields)) fd.append(k, v);
            const blob = await (await fetch('data:image/jpeg;base64,' + b64)).blob();
            fd.append('image', blob, fields.image_name || 'image.jpg');
            const r = await fetch('/api/minimax-trial/video-generation', {
                method: 'POST', body: fd
            });
            const text = await r.text();
            let data; try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 500) }; }
            return { status: r.status, ok: r.ok, data, headers: Object.fromEntries(r.headers.entries()) };
        }""", [{
            "visitorId": visitor_id,
            "channelCode": os.getenv("MM_CHANNEL", "direct"),
            "sourceHost": os.getenv("MM_SOURCE_HOST", "siftq.com"),
            "ratio": ratio,
            "duration": str(duration),
            "client_id": client_id,
            "prompt": prompt,
            "image_name": image_name,
        }, image_b64])
        return result
    finally:
        await browser.close()
        await pw.stop()


async def _get_status_via_cdp(task_id: str, access_token: str) -> dict:
    """GET task status via the page's fetch — no cookie management needed."""
    pw, browser, page = await _get_cdp_page()
    try:
        result = await page.evaluate("""async (url) => {
            const r = await fetch(url);
            const text = await r.text();
            let data; try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 500) }; }
            return { status: r.status, data };
        }""", f"/api/minimax-trial/video-generation/{task_id}?access_token={access_token}")
        return result
    finally:
        await browser.close()
        await pw.stop()


async def _submit(client_id: str, image: bytes, image_name: str,
                  prompt: str, ratio: str, duration: str, visitor_id: str) -> dict:
    image_b64 = base64.b64encode(image).decode()
    r = await _post_via_cdp(client_id, image_b64, image_name, prompt, ratio, duration, visitor_id)
    if not r.get("ok"):
        raise HTTPException(r.get("status", 502), f"upstream error: {r.get('data', {})}")
    return {"http": 200, "data": r["data"]}


async def _open_proxy_page(px):
    """Fresh siftq.com page in a proxy-egress browser context.

    Returns (pw, browser, context, page). Caller must close all three.
    Verified live: egress IP of the page == proxy IP. The context starts
    cookie-free, so Cloudflare may re-challenge — callers treat non-task
    payloads as per-item failures, never fatal."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(503, "playwright not installed")
    cdp_url = f"http://{CDP_HOST}:{CDP_PORT}"
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
    except Exception:
        await pw.stop()
        raise
    try:
        ctx = await browser.new_context(
            proxy={"server": "http://%s:%d" % (px.host, px.port),
                   "username": px.user, "password": px.password})
    except Exception:
        await browser.close()
        await pw.stop()
        raise
    page = None
    try:
        page = await ctx.new_page()
        # wait_until=commit: only needs the origin committed, not the full
        # DOM — the relative fetch works regardless, and CF interstitial
        # pages must not stall this on domcontentloaded.
        await page.goto("https://siftq.com/minimax-h3/free-trial",
                        timeout=30000, wait_until="commit")
    except Exception as e:
        await ctx.close()
        await browser.close()
        await pw.stop()
        raise HTTPException(503, "proxy page goto failed: %s: %s"
                            % (type(e).__name__, str(e)[:150]))
    return pw, browser, ctx, page


async def _close_proxy_page(pw, browser, ctx) -> None:
    for closer in (ctx.close, browser.close, pw.stop):
        try:
            await closer()
        except Exception:
            pass


async def _post_on_page(page, client_id: str, image_b64: str, image_name: str,
                       prompt: str, ratio: str, duration: str,
                       visitor_id: str) -> dict:
    """POST generation on an already-open siftq.com page (any egress)."""
    return await page.evaluate("""async ([fields, b64]) => {
            const fd = new FormData();
            for (const [k, v] of Object.entries(fields)) fd.append(k, v);
            const blob = await (await fetch('data:image/jpeg;base64,' + b64)).blob();
            fd.append('image', blob, fields.image_name || 'image.jpg');
            const r = await fetch('/api/minimax-trial/video-generation', {
                method: 'POST', body: fd
            });
            const text = await r.text();
            let data; try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 500) }; }
            return { status: r.status, ok: r.ok, data, headers: Object.fromEntries(r.headers.entries()) };
        }""", [{
            "visitorId": visitor_id,
            "channelCode": os.getenv("MM_CHANNEL", "direct"),
            "sourceHost": os.getenv("MM_SOURCE_HOST", "siftq.com"),
            "ratio": ratio,
            "duration": str(duration),
            "client_id": client_id,
            "prompt": prompt,
            "image_name": image_name,
        }, image_b64])


async def _post_via_proxy(px, client_id: str, image_b64: str, image_name: str,
                          prompt: str, ratio: str, duration: str,
                          visitor_id: str) -> dict:
    """POST generation from a proxy-egress page (open-use-close)."""
    pw, browser, ctx, page = await _open_proxy_page(px)
    try:
        return await _post_on_page(page, client_id, image_b64, image_name,
                                   prompt, ratio, duration, visitor_id)
    finally:
        await _close_proxy_page(pw, browser, ctx)


async def _get_status_on_page(page, task_id: str, access_token: str) -> dict:
    """GET task status on an already-open siftq.com page (any egress)."""
    return await page.evaluate("""async (url) => {
            const r = await fetch(url);
            const text = await r.text();
            let data; try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 500) }; }
            return { status: r.status, data };
        }""", f"/api/minimax-trial/video-generation/{task_id}?access_token={access_token}")


async def _get_status_via_proxy(px, task_id: str, access_token: str) -> dict:
    """GET task status from a proxy-egress page (open-use-close)."""
    pw, browser, ctx, page = await _open_proxy_page(px)
    try:
        return await _get_status_on_page(page, task_id, access_token)
    finally:
        await _close_proxy_page(pw, browser, ctx)


async def _submit_via(px, client_id: str, image: bytes, image_name: str,
                      prompt: str, ratio: str, duration: str,
                      visitor_id: str) -> dict:
    """Route submit: proxy-egress page when px given, else profile-tab path."""
    image_b64 = base64.b64encode(image).decode()
    if px is None:
        r = await _post_via_cdp(client_id, image_b64, image_name, prompt,
                                ratio, duration, visitor_id)
    else:
        r = await _post_via_proxy(px, client_id, image_b64, image_name,
                                  prompt, ratio, duration, visitor_id)
    if not r.get("ok"):
        raise HTTPException(r.get("status", 502), f"upstream error: {r.get('data', {})}")
    return {"http": 200, "data": r["data"]}\



# ------------------------- API surface -------------------------------------

@app.get("/healthz")
def healthz():
    return {"ok": True, "cdp": f"{CDP_HOST}:{CDP_PORT}", "tasks": len(TASKS)}


@app.get("/v1/usage")
async def usage(client_id: Optional[str] = None):
    cid = client_id or ("mmtrial_" + uuid.uuid4().hex[:32])
    pw, browser, page = await _get_cdp_page()
    try:
        result = await page.evaluate("""async (url) => {
            const r = await fetch(url);
            const text = await r.text();
            let data; try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 500) }; }
            return { status: r.status, data };
        }""", f"/api/minimax-trial/usage?client_id={cid}")
        if result["status"] != 200:
            raise HTTPException(result["status"], f"upstream usage error: {result.get('data', {})}")
        return result["data"]
    finally:
        await browser.close()
        await pw.stop()


@app.post("/v1/generations")
async def create_generation(
    request: Request,
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    ratio: str = Form("9:16"),
    duration: str = Form("6"),
    client_id: Optional[str] = Form(None),
):
    _check_api_key(request)
    return await _create_generation_impl(image, prompt, ratio, duration, client_id)


@app.post("/v1/generations:await")
async def create_generation_await(
    request: Request,
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    ratio: str = Form("9:16"),
    duration: str = Form("6"),
    client_id: Optional[str] = Form(None),
    timeout_s: int = Form(DEFAULT_MAX_WAIT_S),
):
    _check_api_key(request)
    out = await _create_generation_impl(image, prompt, ratio, duration, client_id)
    if out.status_code != 200:
        return out
    body = json.loads(bytes(out.body))
    tid = body["task_id"]
    deadline = time.time() + max(10, int(timeout_s))
    while time.time() < deadline:
        # F8: cooperative client-disconnect check.
        try:
            if await request.is_disconnected():
                log.info("client disconnected; stop polling %s", tid)
                raise HTTPException(499, "client closed request")
        except HTTPException:
            raise
        except Exception:
            pass
        st = await _get_status(tid)
        if st["status"] in ("succeeded", "failed", "error"):
            body["final"] = st
            if st["status"] == "succeeded":
                body["content_url"] = f"/v1/tasks/{tid}/content"
            return JSONResponse(body)
        await asyncio.sleep(POLL_SECONDS)
    raise HTTPException(504, f"task {tid} still running after {timeout_s}s")


@app.post("/v1/tasks")
async def register_task(request: Request):
    """Seed the registry with an externally-created task so /v1/tasks and
    /v1/tasks/{id}/content work across restarts / other clients."""
    _check_api_key(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "body must be JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    tid = str(body.get("task_id") or "")
    tok = body.get("access_token") or ""
    cid = body.get("client_id") or ""
    if not tid or not tok:
        raise HTTPException(400, "task_id and access_token required")
    async with _tasks_lock:
        TASKS[tid] = {"access_token": tok, "client_id": cid,
                      "created_at": time.time(), "status": "registered"}
    return {"ok": True, "task_id": tid}


async def _create_generation_from_bytes(data: bytes, image_name: str, prompt: Optional[str],
                                        ratio: str, duration: str,
                                        client_id: Optional[str],
                                        proxy=None, page=None) -> dict:
    """Bytes-level core shared by single and batch creation. Returns body dict.
    page (pre-opened siftq.com page) wins; else proxy routes via proxy egress;
    proxy=None keeps the profile-tab path."""
    if not data:
        raise HTTPException(400, "empty image")
    cid = client_id or ("mmtrial_" + str(uuid.uuid4()))
    vid = "mmguest_" + str(uuid.uuid4())
    pr = prompt or PROMPT_DEFAULT
    if page is not None:
        image_b64 = base64.b64encode(data).decode()
        r = await _post_on_page(page, cid, image_b64, image_name, pr,
                                ratio, duration, vid)
        if not r.get("ok"):
            raise HTTPException(r.get("status", 502),
                                f"upstream error: {r.get('data', {})}")
        out = {"http": 200, "data": r["data"]}
    else:
        out = await _submit_via(proxy, cid, data, image_name, pr, ratio, duration, vid)
    if out["http"] != 200:
        raise HTTPException(out["http"], out["data"])
    d = out["data"]
    if not isinstance(d, dict) or "task_id" not in d or "access_token" not in d:
        # Upstream returned no task payload — typically a CF re-challenge HTML
        # page surfacing as {raw: ...} through the in-page fetch.
        raise HTTPException(503, "upstream returned no task (browser tab may need a CF re-challenge; reload siftq.com)")
    tid = str(d["task_id"])
    async with _tasks_lock:
        TASKS[tid] = {"access_token": d["access_token"], "client_id": cid,
                      "created_at": time.time(), "status": d.get("status", "queued"),
                      "proxy": proxy.label() if proxy is not None else None}
        _prune_tasks()
    log.info("generation created task_id=%s upstream_status=%s", tid, d.get("status"))
    return {
        "task_id": tid,
        "status": d.get("status", "queued"),
        "status_url": f"/v1/tasks/{tid}",
        "content_url": f"/v1/tasks/{tid}/content",
        "upstream": d,
    }


async def _create_generation_impl(image: UploadFile, prompt: Optional[str],
                                  ratio: str, duration: str, client_id: Optional[str]):
    data = await image.read()
    body = await _create_generation_from_bytes(
        data, image.filename or "image.jpg", prompt, ratio, duration, client_id)
    return JSONResponse(body)


def _resolve_task(task_id: str, client_id: Optional[str], access_token: Optional[str]) -> dict:
    """Resolve task credentials: registry first, then explicit query params."""
    t = TASKS.get(task_id, {}).copy()
    if access_token:
        t["access_token"] = access_token
    if client_id:
        t["client_id"] = client_id
    if not t.get("access_token"):
        raise HTTPException(404, f"unknown task_id {task_id} (pass ?client_id=…&access_token=… to seed)")
    return t


def _proxy_for_task(t: dict):
    """Resolve the pool Proxy for a task entry by its recorded label."""
    label = t.get("proxy")
    if not label:
        return None
    return PROXIES.find(label)


async def _get_status(tid: str, client_id: Optional[str] = None,
                      access_token: Optional[str] = None, proxy=None,
                      page=None) -> dict:
    t = _resolve_task(tid, client_id, access_token)
    if page is not None:
        r = await _get_status_on_page(page, tid, t["access_token"])
        d = r["data"]
        async with _tasks_lock:
            TASKS.setdefault(tid, {"created_at": time.time()})["status"] = d.get("status")
        return d
    px = proxy if proxy is not None else _proxy_for_task(t)
    if px is None:
        r = await _get_status_via_cdp(tid, t["access_token"])
    else:
        r = await _get_status_via_proxy(px, tid, t["access_token"])
    if r["status"] != 200:
        raise HTTPException(r["status"], f"upstream status error: {r.get('data', {})}")
    d = r["data"]
    async with _tasks_lock:
        TASKS.setdefault(tid, {"created_at": time.time()})["status"] = d.get("status")
    return d


@app.get("/v1/tasks/{task_id}")
async def task_status(task_id: str, client_id: Optional[str] = None,
                      access_token: Optional[str] = None):
    return await _get_status(task_id, client_id, access_token)


@app.api_route("/v1/tasks/{task_id}/content", methods=["GET", "HEAD"])
async def task_content(task_id: str, stream: bool = False,
                       client_id: Optional[str] = None, access_token: Optional[str] = None):
    t = _resolve_task(task_id, client_id, access_token)
    st = await _get_status(task_id, client_id, access_token)
    if st.get("status") != "succeeded":
        raise HTTPException(409, f"task not ready: {st.get('status')}")
    url = (f"{TRIAL_URL}/video-generation/{task_id}/content"
           f"?client_id={t['client_id']}&access_token={t['access_token']}")
    if not stream:
        return RedirectResponse(url)
    # Stream via the task's own egress (proxy page when recorded, else
    # profile tab): fetch full body in-page, base64 -> decode -> stream.
    px = _proxy_for_task(t)
    if px is None:
        pw, browser, page = await _get_cdp_page()
        closer = None
    else:
        pw, browser, ctx, page = await _open_proxy_page(px)
        closer = (pw, browser, ctx)
    try:
        result = await page.evaluate("""async (url) => {
            const r = await fetch(url);
            if (!r.ok) return { status: r.status, error: await r.text() };
            const buf = await r.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let binary = '';
            for (let i = 0; i < bytes.length; i += 8192) {
                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
            }
            return { status: r.status, b64: btoa(binary),
                     content_type: r.headers.get('content-type'),
                     content_length: buf.byteLength };
        }""", f"/api/minimax-trial/video-generation/{task_id}/content?client_id={t['client_id']}&access_token={t['access_token']}")
        if result.get("status") != 200:
            raise HTTPException(result.get("status", 502),
                                f"upstream content error: {result.get('error', '')[:200]}")
        body = base64.b64decode(result["b64"])
        safe_tid = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)[:80]
        headers = {
            "Content-Disposition": f'inline; filename="{safe_tid}.mp4"',
            "Content-Length": str(result.get("content_length", len(body))),
        }
        return StreamingResponse(
            iter([body]), media_type="video/mp4", headers=headers)
    finally:
        if closer is None:
            await browser.close()
            await pw.stop()
        else:
            await _close_proxy_page(*closer)


# ------------------------- Batch + proxy pool -------------------------------

BATCHES: dict[str, dict] = {}
_batches_lock = asyncio.Lock()


async def _wait_task_terminal(tid: str, timeout_s: int, proxy=None,
                              page=None) -> dict:
    """Poll until terminal status or deadline. Never raises."""
    deadline = time.time() + max(10, int(timeout_s))
    last: dict[str, object] = {}
    while time.time() < deadline:
        try:
            st = await _get_status(tid, proxy=proxy, page=page)
        except HTTPException as e:
            return {"status": "error", "task_id": tid,
                    "error": "http %s: %s" % (e.status_code, e.detail)}
        except Exception as e:
            return {"status": "error", "task_id": tid,
                    "error": "%s: %s" % (type(e).__name__, str(e)[:200])}
        last = st
        if st.get("status") in ("succeeded", "failed", "error"):
            return st
        await asyncio.sleep(POLL_SECONDS)
    out: dict[str, object] = {"status": "timeout", "task_id": tid}
    if last:
        out["last"] = last
    return out


async def _run_batch_item(batch_id: str, index: int, spec: dict, timeout_s: int,
                          sem: asyncio.Semaphore) -> None:
    """One batch item: submit, await terminal, record. Per-item isolation —
    any failure lands in the item entry, never aborts siblings."""
    async with sem:
        px = await PROXIES.next()
        label = px.label() if px else None
        entry = {"index": index, "status": "running", "proxy": label,
                 "task_id": None, "content_url": None, "error": None}
        async with _batches_lock:
            b = BATCHES.get(batch_id)
            if b is None:
                return
            b["items"][index] = entry
        # Persistent proxy page per item: one goto, reused for submit + all
        # polls. Without this, every poll opens a fresh page whose goto can
        # stall and kill an otherwise healthy item.
        opener = None
        if px is not None:
            try:
                pw0, browser0, ctx0, page0 = await _open_proxy_page(px)
                opener = (pw0, browser0, ctx0, page0)
            except Exception as e:
                # Single record point is the outer handler; just stash the
                # message here and raise so the item fails cleanly.
                entry["status"] = "failed"
                if isinstance(e, HTTPException):
                    entry["error"] = "proxy page open: http %s: %s" % (
                        e.status_code, str(e.detail)[:150])
                else:
                    entry["error"] = "proxy page open: %s: %s" % (
                        type(e).__name__, str(e)[:150])
                opener = None
        try:
            if opener is None and px is not None and entry["error"]:
                raise HTTPException(503, entry["error"])
            page0 = opener[3] if opener is not None else None
            body = await _create_generation_from_bytes(
                spec["data"], spec.get("image_name") or "image.jpg",
                spec.get("prompt"), spec.get("ratio", "9:16"),
                spec.get("duration", "6"), spec.get("client_id"),
                proxy=px, page=page0)
            tid = body["task_id"]
            final = await _wait_task_terminal(tid, timeout_s, proxy=px,
                                              page=page0)
            entry["task_id"] = tid
            if final.get("status") == "succeeded":
                entry["status"] = "succeeded"
                entry["content_url"] = f"/v1/tasks/{tid}/content"
            else:
                entry["status"] = "failed"
                entry["error"] = "terminal=%s %s" % (
                    final.get("status"), str(final.get("error", ""))[:200])
                if px is not None:
                    await PROXIES.record_failed(px)
        except HTTPException as e:
            entry["status"] = "failed"
            entry["error"] = "http %s: %s" % (e.status_code, str(e.detail)[:200])
            if px is not None:
                await PROXIES.record_failed(px)
        except Exception as e:
            entry["status"] = "failed"
            entry["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            if px is not None:
                await PROXIES.record_failed(px)
        finally:
            if opener is not None:
                await _close_proxy_page(opener[0], opener[1], opener[2])
        async with _batches_lock:
            b = BATCHES.get(batch_id)
            if b is None:
                return
            b["items"][index] = entry
            b["done"] = sum(1 for it in b["items"]
                            if it["status"] in ("succeeded", "failed"))
            b["succeeded"] = sum(1 for it in b["items"]
                                 if it["status"] == "succeeded")
            b["failed"] = sum(1 for it in b["items"]
                              if it["status"] == "failed")
            if b["done"] >= b["total"]:
                b["status"] = "completed"
                b["completed_at"] = time.time()


async def _run_batch(batch_id: str, timeout_s: int, stagger_s: float) -> None:
    async with _batches_lock:
        b = BATCHES.get(batch_id)
        if b is None:
            return
        specs = list(b["specs"])
        concurrency = max(1, int(b.get("concurrency") or BATCH_CONCURRENCY))
    sem = asyncio.Semaphore(concurrency)

    async def one(i, spec):
        if stagger_s > 0 and i > 0:
            await asyncio.sleep(stagger_s * i)
        await _run_batch_item(batch_id, i, spec, timeout_s, sem)

    await asyncio.gather(*(one(i, s) for i, s in enumerate(specs)))
    log.info("batch %s finished", batch_id)


@app.post("/v1/batches", status_code=202)
async def create_batch(request: Request):
    """Submit N images x N prompts at once. 202 + batch_id; poll GET /v1/batches/{id}."""
    _check_api_key(request)
    PROXIES.maybe_refresh()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "body must be JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    raw_items = body.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(400, "items must be a non-empty list")
    if len(raw_items) > BATCH_MAX_ITEMS:
        raise HTTPException(400, f"too many items (max {BATCH_MAX_ITEMS})")
    specs = []
    for i, it in enumerate(raw_items):
        if not isinstance(it, dict):
            raise HTTPException(400, f"items[{i}] must be an object")
        try:
            data = base64.b64decode(it.get("image_b64") or "", validate=True)
        except Exception:
            raise HTTPException(400, f"items[{i}].image_b64 is not valid base64")
        if not data:
            raise HTTPException(400, f"items[{i}] image is empty")
        specs.append({
            "data": data,
            "image_name": str(it.get("image_name") or "image.jpg")[:120],
            "prompt": it.get("prompt"),
            "ratio": str(it.get("ratio") or "9:16"),
            "duration": str(it.get("duration") or "6"),
            "client_id": it.get("client_id"),
        })
    concurrency = max(1, int(body.get("concurrency") or BATCH_CONCURRENCY))
    timeout_s = max(10, int(body.get("timeout_s") or DEFAULT_MAX_WAIT_S))
    stagger_s = max(0.0, float(body.get("stagger_s", BATCH_STAGGER_S)))
    batch_id = "mmbatch_" + uuid.uuid4().hex[:16]
    async with _batches_lock:
        BATCHES[batch_id] = {
            "batch_id": batch_id, "created_at": time.time(),
            "completed_at": None, "total": len(specs), "done": 0,
            "succeeded": 0, "failed": 0, "status": "running",
            "concurrency": concurrency, "specs": specs,
            "items": [{"index": i, "status": "queued", "proxy": None,
                         "task_id": None, "content_url": None, "error": None}
                        for i in range(len(specs))],
        }
        now = time.time()
        for k in [k for k, v in BATCHES.items()
                  if now - v["created_at"] > TASK_TTL_S]:
            BATCHES.pop(k, None)
    asyncio.create_task(_run_batch(batch_id, timeout_s, stagger_s))
    log.info("batch created batch_id=%s total=%d concurrency=%d",
             batch_id, len(specs), concurrency)
    return JSONResponse({
        "batch_id": batch_id, "total": len(specs), "status": "running",
        "status_url": f"/v1/batches/{batch_id}",
        "await_url": f"/v1/batches/{batch_id}:await",
    }, status_code=202)


@app.get("/v1/batches/{batch_id}")
async def batch_status(batch_id: str):
    b = BATCHES.get(batch_id)
    if b is None:
        raise HTTPException(404, f"unknown batch_id {batch_id}")
    return {k: v for k, v in b.items() if k != "specs"}


@app.post("/v1/batches/{batch_id}:await")
async def batch_await(batch_id: str, timeout_s: int = DEFAULT_MAX_WAIT_S):
    b = BATCHES.get(batch_id)
    if b is None:
        raise HTTPException(404, f"unknown batch_id {batch_id}")
    deadline = time.time() + max(10, int(timeout_s))
    while time.time() < deadline:
        async with _batches_lock:
            snap = {k: v for k, v in BATCHES.get(batch_id, {}).items()
                    if k != "specs"}
        if not snap:
            raise HTTPException(404, f"unknown batch_id {batch_id}")
        if snap.get("status") == "completed":
            return JSONResponse(snap)
        await asyncio.sleep(POLL_SECONDS)
    raise HTTPException(504, f"batch {batch_id} still running after {timeout_s}s")


@app.get("/v1/proxies")
async def proxies_status():
    """Proxy pool health/rotation stats. Passwords never exposed."""
    PROXIES.maybe_refresh()
    return PROXIES.status()


@app.post("/v1/proxies/check")
async def proxies_check(request: Request, concurrency: int = 5,
                        timeout_s: float = 15.0):
    """Probe every configured proxy (TCP + HTTP/SOCKS5 + egress IP)."""
    _check_api_key(request)
    PROXIES.maybe_refresh()
    if not len(PROXIES):
        raise HTTPException(400, "no proxies configured (set MM_PROXIES)")
    await PROXIES.check_all(concurrency=max(1, concurrency),
                            timeout=max(5.0, timeout_s))
    return PROXIES.status()


def _prune_tasks() -> None:
    now = time.time()
    for k in [k for k, v in TASKS.items() if now - v["created_at"] > TASK_TTL_S]:
        TASKS.pop(k, None)


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    return JSONResponse({"error": {"status": exc.status_code, "detail": exc.detail}},
                        status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "8080")), log_level="info")
