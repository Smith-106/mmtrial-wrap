"""mmtrial-wrap — official-API-style wrapper around the SiftQ MiniMax trial flow.

The upstream trial endpoint has a Cloudflare-gated POST that requires a live
`cf_clearance` cookie plus a full multipart body (visitorId / channelCode /
sourceHost / ratio / duration / client_id / image). This service hides all of
that so downstream clients can use a clean, official-looking API:

    POST /v1/generations          -> create generation task
    POST /v1/generations:await    -> create + block until terminal
    GET  /v1/tasks/{task_id}      -> poll status
    GET  /v1/tasks/{task_id}/content -> download (302 redirect or stream)
    GET  /v1/usage                -> quota snapshot
    GET  /healthz
"""
import asyncio, os, secrets, time, uuid, json
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, PlainTextResponse
from curl_cffi import requests as cr, CurlMime

BASE = "https://siftq.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) HeadlessChrome/154.0.0.0 Safari/537.36")
TRIAL_PATH = "/api/minimax-trial"
TRIAL_URL = BASE + TRIAL_PATH
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "7"))
TASK_TTL_S = int(os.getenv("TASK_TTL_S", "86400"))
DEFAULT_MAX_WAIT_S = int(os.getenv("DEFAULT_MAX_WAIT_S", "600"))
COOKIE_FILE = os.getenv("CF_COOKIE_FILE", "/data/cf_clearance.txt")
CF_CLEARANCE_ENV = os.getenv("CF_CLEARANCE", "").strip()
COOKIE_REFRESH_URL = os.getenv("CF_REFRESH_URL", BASE + "/minimax-h3/free-trial")
PROMPT_DEFAULT = "夜色中的东京街头，一个女孩转身回眸，霓虹在雨中晕开，电影感，慢动作"

app = FastAPI(title="mmtrial-wrap", version="1.0.0")
_session: Optional[cr.Session] = None
# in-memory task registry: task_id -> {access_token, client_id, created_at, status}
TASKS: dict[str, dict] = {}


def session() -> cr.Session:
    global _session
    if _session is None:
        _session = cr.Session(impersonate="chrome124")
    return _session


def _load_cookie() -> str:
    """cf_clearance: env beats file. Empty string means absent."""
    if CF_CLEARANCE_ENV:
        return CF_CLEARANCE_ENV
    try:
        return open(COOKIE_FILE, "r", encoding="utf-8").read().strip()
    except OSError:
        return ""


def _save_cookie(v: str) -> None:
    try:
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(v)
    except OSError:
        pass


class CookieProvider:
    """cf_clearance with lazy headless refresh. Refresh is opt-in (AUTO_CLEARANCE=1
    + playwright + chromium inside the container); otherwise env/file only."""

    def __init__(self) -> None:
        self._value = _load_cookie()
        self._lock = asyncio.Lock()
        self.refreshing = False

    def get(self) -> str:
        return self._value

    def invalidate(self) -> None:
        self._value = ""

    async def ensure(self, force: bool = False) -> str:
        if self._value and not force:
            return self._value
        async with self._lock:
            if self._value and not force:
                return self._value
            if self.refreshing:
                # wait briefly for in-flight refresh
                for _ in range(40):
                    await asyncio.sleep(0.5)
                    if not self.refreshing or self._value:
                        break
                return self._value
            self.refreshing = True
        try:
            v = await asyncio.to_thread(self._refresh_headless)
            if v:
                self._value = v
                _save_cookie(v)
        finally:
            self.refreshing = False
        return self._value

    def _refresh_headless(self) -> str:
        if os.getenv("AUTO_CLEARANCE", "0") != "1":
            return ""
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return ""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=[
                    "--no-sandbox", "--disable-blink-features=AutomationControlled"])
                ctx = browser.new_context(user_agent=UA)
                pg = ctx.new_page()
                pg.goto(COOKIE_REFRESH_URL, timeout=45000, wait_until="domcontentloaded")
                pg.wait_for_timeout(4000)  # let CF challenge settle
                for c in ctx.cookies(BASE):
                    if c["name"] == "cf_clearance":
                        browser.close()
                        return c["value"]
                browser.close()
        except Exception:
            pass
        return ""


COOKIES = CookieProvider()


def _base_headers(client_id: str, idem: str, with_cookie: bool = True) -> dict:
    h = {
        "Accept": "application/json",
        "Origin": BASE,
        "Referer": BASE + "/minimax-h3/free-trial",
        "X-MiniMax-Trial-Client": client_id,
        "Idempotency-Key": idem,
    }
    if with_cookie:
        c = COOKIES.get()
        if c:
            h["Cookie"] = "cf_clearance=" + c
    xff = os.getenv("MM_XFF", "").strip()
    if xff:
        h["X-Forwarded-For"] = xff
    return h


def _gen_multipart(client_id: str, image: bytes, image_name: str, prompt: str,
                   ratio: str, duration: str, visitor_id: str) -> CurlMime:
    mp = CurlMime()
    for k, v in [
        ("visitorId", visitor_id),
        ("channelCode", os.getenv("MM_CHANNEL", "direct")),
        ("sourceHost", os.getenv("MM_SOURCE_HOST", "siftq.com")),
        ("ratio", ratio),
        ("duration", str(duration)),
        ("client_id", client_id),
        ("prompt", prompt),
    ]:
        mp.addpart(name=k, data=v.encode("utf-8"))
    mp.addpart(name="image", data=image, filename=image_name or "image.jpg",
               content_type="image/jpeg")
    return mp


def _post_generation(client_id: str, idem: str, mp: CurlMime) -> cr.Response:
    return session().post(TRIAL_URL + "/video-generation", headers=_base_headers(client_id, idem),
                          multipart=mp, timeout=60)


async def _submit(client_id: str, idem: str, image: bytes, image_name: str,
                  prompt: str, ratio: str, duration: str, visitor_id: str) -> dict:
    mp = _gen_multipart(client_id, image, image_name, prompt, ratio, duration, visitor_id)
    r = await asyncio.to_thread(_post_generation, client_id, idem, mp)
    if r.status_code in (403, 502):
        # cf_clearance may be stale/invalid -> force headless refresh once, retry.
        COOKIES.invalidate()
        await COOKIES.ensure(force=True)
        if COOKIES.get():
            r = await asyncio.to_thread(_post_generation, client_id, idem, mp)
    try:
        data = r.json()
    except Exception:
        raise HTTPException(502, f"upstream non-JSON {r.status_code}: {r.text[:200]}")
    return {"http": r.status_code, "data": data}


# ------------------------- API surface -------------------------------------

@app.get("/healthz")
def healthz():
    return {"ok": True, "cookie": bool(COOKIES.get()), "tasks": len(TASKS)}


@app.get("/v1/usage")
async def usage(client_id: Optional[str] = None):
    cid = client_id or ("mmtrial_" + uuid.uuid4().hex[:32])
    r = await asyncio.to_thread(
        session().get, f"{TRIAL_URL}/usage?client_id={cid}", headers={"Accept": "application/json"}, timeout=20)
    try:
        return r.json()
    except Exception:
        raise HTTPException(502, f"upstream usage error {r.status_code}")


@app.post("/v1/generations")
async def create_generation(
    request: Request,
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    ratio: str = Form("9:16"),
    duration: str = Form("6"),
    client_id: Optional[str] = Form(None),
):
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
    out = await _create_generation_impl(image, prompt, ratio, duration, client_id)
    if out.status_code != 200:
        return out
    body = json.loads(out.body)
    tid = body["task_id"]
    deadline = time.time() + max(10, int(timeout_s))
    async def _next_state():
        return await _get_status(tid)
    while time.time() < deadline:
        st = await _next_state()
        if st["status"] in ("succeeded", "failed", "error"):
            body["final"] = st
            if st["status"] == "succeeded":
                body["content_url"] = f"/v1/tasks/{tid}/content"
            return JSONResponse(body)
        await asyncio.sleep(POLL_SECONDS)
    raise HTTPException(504, f"task {tid} still running after {timeout_s}s")


@app.post("/v1/tasks")
async def register_task(body: dict):
    """Seed the registry with an externally-created task so /v1/tasks and
    /v1/tasks/{id}/content work across restarts / other clients."""
    tid = str(body.get("task_id") or "")
    tok = body.get("access_token") or ""
    cid = body.get("client_id") or ""
    if not tid or not tok:
        raise HTTPException(400, "task_id and access_token required")
    TASKS[tid] = {"access_token": tok, "client_id": cid,
                  "created_at": time.time(), "status": "registered"}
    return {"ok": True, "task_id": tid}


async def _create_generation_impl(image: UploadFile, prompt: Optional[str],
                                  ratio: str, duration: str, client_id: Optional[str]):
    data = await image.read()
    if not data:
        raise HTTPException(400, "empty image")
    cid = client_id or ("mmtrial_" + str(uuid.uuid4()))
    idem = "mmtrial_" + str(uuid.uuid4())
    vid = "mmguest_" + str(uuid.uuid4())
    pr = prompt or PROMPT_DEFAULT
    out = await _submit(cid, idem, data, image.filename or "image.jpg", pr, ratio, duration, vid)
    if out["http"] != 200:
        raise HTTPException(out["http"], out["data"])
    d = out["data"]
    tid = str(d["task_id"])
    TASKS[tid] = {"access_token": d["access_token"], "client_id": cid,
                  "created_at": time.time(), "status": d.get("status", "queued")}
    _prune_tasks()
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
    r = await asyncio.to_thread(
        session().get,
        f"{TRIAL_URL}/video-generation/{tid}?access_token={t['access_token']}",
        headers={"Accept": "application/json"}, timeout=20)
    try:
        d = r.json()
    except Exception:
        raise HTTPException(502, f"upstream status error {r.status_code}")
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
    # stream: fetch then pipe
    r = await asyncio.to_thread(session().get, url,
                                headers={"Accept": "application/octet-stream"}, timeout=120)
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"upstream content error: {r.text[:200]}")
    return StreamingResponse(iter([r.content]), media_type="video/mp4",
                             headers={"Content-Disposition": f'inline; filename="{task_id}.mp4"'})


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
    uvicorn.run("app.main:app", host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8080")), log_level="info")
