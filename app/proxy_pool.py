"""mmtrial-wrap proxy pool — stdlib-only proxy health, rotation and usage stats.

Env:
    MM_PROXIES="host:port:user:pass[,host:port:user:pass...]"
    (entries may also be http://user:pass@host:port URLs)

Health check probes each proxy twice: first as a plain HTTP forward proxy,
then as SOCKS5 (RFC1928, incl. username/password auth), fetching the
caller's egress IP from http://api.ipify.org/ through the proxy.

Passwords are never logged, never persisted, and stripped from status().
"""
import asyncio
import base64
import logging
import os
import re
import socket
import struct
import time
import urllib.parse

log = logging.getLogger("mmtrial-proxy-pool")

_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


class Proxy:
    __slots__ = ("host", "port", "user", "password", "proto", "alive",
                 "latency_ms", "egress_ip", "last_check", "used", "failed")

    def __init__(self, host, port, user="", password=""):
        self.host = host
        self.port = int(port)
        self.user = user or ""
        self.password = password or ""
        self.proto = "unknown"  # http | socks5 after a successful probe
        self.alive = False
        self.latency_ms = None
        self.egress_ip = ""
        self.last_check = 0.0
        self.used = 0
        self.failed = 0

    def label(self):
        return f"{self.host}:{self.port}"

    def sanitized(self):
        return {
            "host": self.host, "port": self.port, "proto": self.proto,
            "alive": self.alive, "latency_ms": self.latency_ms,
            "egress_ip": self.egress_ip, "used": self.used,
            "failed": self.failed, "last_check": self.last_check,
        }


def parse_proxies(spec):
    """Parse MM_PROXIES into [Proxy]. Malformed entries are skipped."""
    out = []
    skipped = 0
    for raw in (spec or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            if "://" in raw:
                u = urllib.parse.urlparse(raw)
                host, port = u.hostname, u.port
                user = urllib.parse.unquote(u.username or "")
                pw = urllib.parse.unquote(u.password or "")
            else:
                parts = raw.split(":")
                if len(parts) < 2:
                    raise ValueError("need host:port")
                host = parts[0].strip()
                port = int(parts[1])
                user = parts[2] if len(parts) > 2 else ""
                pw = parts[3] if len(parts) > 3 else ""
            if not host or not port:
                raise ValueError("empty host/port")
            out.append(Proxy(host, port, user, pw))
        except Exception as e:
            skipped += 1
            log.warning("skip malformed proxy entry #%d: %s", skipped, type(e).__name__)
    if skipped:
        log.warning("skipped %d malformed proxy entries", skipped)
    return out


def _tcp_latency(host, port, timeout):
    t0 = time.monotonic()
    s = socket.create_connection((host, port), timeout=timeout)
    s.close()
    return (time.monotonic() - t0) * 1000


def _recvn(s, n, timeout=10):
    s.settimeout(timeout)
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise OSError("truncated reply")
        buf += chunk
    return buf


def _recv_all(s, timeout, limit=65536):
    s.settimeout(timeout)
    chunks = []
    total = 0
    try:
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
            total += len(b)
            if total > limit:
                break
    except socket.timeout:
        pass
    return b"".join(chunks)


def _split_body(resp):
    head, _, body = resp.partition(b"\r\n\r\n")
    try:
        status = int(head.decode("latin1").split(" ", 2)[1])
    except Exception:
        status = 0
    return status, body.decode("utf-8", "replace").strip()


def _probe_http_proxy(px, target_host, path, timeout):
    """Plain HTTP forward proxy (absolute-URI GET + Proxy-Authorization)."""
    s = socket.create_connection((px.host, px.port), timeout=timeout)
    try:
        cred = base64.b64encode(("%s:%s" % (px.user, px.password)).encode()).decode()
        req = ("GET http://%s%s HTTP/1.1\r\n"
               "Host: %s\r\n"
               "Proxy-Authorization: Basic %s\r\n"
               "Connection: close\r\n"
               "User-Agent: mmtrial-wrap/probe\r\n\r\n") % (target_host, path, target_host, cred)
        s.sendall(req.encode())
        return _split_body(_recv_all(s, timeout))
    finally:
        s.close()


def _probe_socks5_proxy(px, target_host, target_port, path, timeout):
    """SOCKS5 CONNECT (RFC1928, user/pass auth) then origin-form GET."""
    s = socket.create_connection((px.host, px.port), timeout=timeout)
    try:
        s.sendall(b"\x05\x01\x02" if (px.user or px.password) else b"\x05\x01\x00")
        ver, method = _recvn(s, 2)
        if ver != 5:
            raise OSError("bad socks5 greeting")
        if method == 2:
            u = px.user.encode()[:255]
            p = px.password.encode()[:255]
            s.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            if _recvn(s, 2)[1] != 0:
                raise OSError("socks5 auth failed")
        elif method != 0:
            raise OSError("socks5 no acceptable method (%d)" % method)
        host_b = target_host.encode()[:255]
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b
                  + struct.pack(">H", target_port))
        rep = _recvn(s, 4)
        if len(rep) < 4 or rep[1] != 0:
            raise OSError("socks5 connect refused")
        atyp = rep[3]
        if atyp == 1:
            _recvn(s, 4 + 2)
        elif atyp == 3:
            _recvn(s, _recvn(s, 1)[0] + 2)
        elif atyp == 4:
            _recvn(s, 16 + 2)
        get_req = ("GET %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n"
                   "User-Agent: mmtrial-wrap/probe\r\n\r\n" % (path, target_host))
        s.sendall(get_req.encode())
        return _split_body(_recv_all(s, timeout))
    finally:
        s.close()


async def check_proxy(px, target_host="api.ipify.org", timeout=15.0):
    """Probe one proxy; updates its fields in place. Never raises."""
    t0 = time.monotonic()
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _tcp_latency, px.host, px.port, min(timeout, 10))
    except Exception as e:
        log.info("proxy %s tcp failed: %s", px.label(), type(e).__name__)
        px.alive, px.latency_ms, px.egress_ip, px.proto = False, None, "", "unknown"
        px.last_check = time.time()
        return px
    for how in ("http", "socks5"):
        try:
            if how == "http":
                status, body = await loop.run_in_executor(
                    None, _probe_http_proxy, px, target_host, "/", timeout)
            else:
                status, body = await loop.run_in_executor(
                    None, _probe_socks5_proxy, px, target_host, 80, "/", timeout)
        except Exception as e:
            log.info("proxy %s %s probe error: %s", px.label(), how, type(e).__name__)
            continue
        if status == 200 and _IPV4.match(body):
            px.alive, px.proto = True, how
            px.egress_ip = body
            px.latency_ms = int((time.monotonic() - t0) * 1000)
            px.last_check = time.time()
            return px
        log.info("proxy %s %s probe status=%s body=%.40s", px.label(), how, status, body)
    px.alive, px.latency_ms, px.egress_ip, px.proto = False, None, "", "unknown"
    px.last_check = time.time()
    return px


class ProxyPool:
    def __init__(self, proxies=None, source=""):
        self._items = list(proxies or [])
        self._source = source
        self._idx = 0
        self._lock = asyncio.Lock()

    @classmethod
    def from_env(cls):
        spec = os.getenv("MM_PROXIES", "")
        return cls(parse_proxies(spec), source=spec)

    def maybe_refresh(self):
        """Rebuild from env when MM_PROXIES changed since last load."""
        spec = os.getenv("MM_PROXIES", "")
        if spec != self._source:
            self._items = parse_proxies(spec)
            self._source = spec
            self._idx = 0
            return True
        return False

    def __len__(self):
        return len(self._items)

    async def next(self):
        """Round-robin; prefers alive entries, else least-failed. Counts use."""
        async with self._lock:
            items = self._items
            if not items:
                return None
            alive = [p for p in items if p.alive]
            cand = alive or sorted(items, key=lambda p: (p.failed, p.used))
            px = cand[self._idx % len(cand)]
            self._idx += 1
            px.used += 1
            return px

    async def record_failed(self, px):
        async with self._lock:
            px.failed += 1

    def status(self):
        return {"size": len(self._items), "source": "env:MM_PROXIES",
                "proxies": [p.sanitized() for p in self._items]}

    async def check_all(self, concurrency=5, timeout=15.0):
        sem = asyncio.Semaphore(max(1, concurrency))

        async def one(px):
            async with sem:
                return await check_proxy(px, timeout=timeout)

        return await asyncio.gather(*(one(p) for p in self._items))
