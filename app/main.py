"""mmtrial-wrap — official-API-style wrapper around the SiftQ MiniMax trial flow.

All upstream traffic goes through the attached browser profile's own
fetch() (CDP in-page execution), so the browser's real fingerprint, cookies
and IP handle Cloudflare. This service exposes a clean, official-looking API:

    POST /v1/generations          -> create generation task
    POST /v1/generations:await    -> create + block until terminal
    GET  /v1/tasks/{task_id}      -> poll status
    GET  /v1/tasks/{task_id}/content -> download (302 redirect or stream)
    GET  /v1/usage                -> quota snapshot
    GET  /healthz
"""
import asyncio, base64, hmac, logging, os, re, time, uuid, json
from typing import Optional

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

app = FastAPI(title="mmtrial-wrap", version="1.0.0")
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


async def _create_generation_impl(image: UploadFile, prompt: Optional[str],
                                  ratio: str, duration: str, client_id: Optional[str]):
    data = await image.read()
    if not data:
        raise HTTPException(400, "empty image")
    cid = client_id or ("mmtrial_" + str(uuid.uuid4()))
    vid = "mmguest_" + str(uuid.uuid4())
    pr = prompt or PROMPT_DEFAULT
    out = await _submit(cid, data, image.filename or "image.jpg", pr, ratio, duration, vid)
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
                      "created_at": time.time(), "status": d.get("status", "queued")}
        _prune_tasks()
    log.info("generation created task_id=%s upstream_status=%s", tid, d.get("status"))
    return JSONResponse({
        "task_id": tid,
        "status": d.get("status", "queued"),
        "status_url": f"/v1/tasks/{tid}",
        "content_url": f"/v1/tasks/{tid}/content",
        "upstream": d,
    })


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


async def _get_status(tid: str, client_id: Optional[str] = None,
                      access_token: Optional[str] = None) -> dict:
    t = _resolve_task(tid, client_id, access_token)
    r = await _get_status_via_cdp(tid, t["access_token"])
    if r["status"] != 200:
        raise HTTPException(r["status"], f"upstream status error: {r.get('data', {})}")
    d = r["data"]
    async with _tasks_lock:
        TASKS.setdefault(tid, {})["status"] = d.get("status")
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
    # Stream via CDP: fetch full body in the page (real fingerprint/cookies/IP),
    # return as base64 -> decode -> stream to client. No curl_cffi needed.
    pw, browser, page = await _get_cdp_page()
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
        await browser.close()
        await pw.stop()


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
