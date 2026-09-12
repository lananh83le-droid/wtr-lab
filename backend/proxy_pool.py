"""Free-proxy harvesting, bulk import, liveness checking and smart selection."""
import asyncio
import random
import re
import time
import uuid
from datetime import datetime, timezone

import httpx

import wtrlab

SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=ipport&format=text",
    ],
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    ],
}
LINE_RE = re.compile(r"^(?:(?P<scheme>https?|socks5h?|socks4):\/\/)?(?:(?P<auth>[^@\s]+)@)?(?P<host>[\w.\-\[\]:]+?):(?P<port>\d{2,5})$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_line(line, default_scheme="http"):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = LINE_RE.match(line)
    if not m:
        # ip:port:user:pass format
        parts = line.split(":")
        if len(parts) == 4 and parts[1].isdigit():
            return f"{default_scheme}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return None
    scheme = (m.group("scheme") or default_scheme).lower()
    if scheme == "https":
        scheme = "http"
    auth = f"{m.group('auth')}@" if m.group("auth") else ""
    return f"{scheme}://{auth}{m.group('host')}:{m.group('port')}"


def parse_bulk(text, default_scheme="http"):
    out, seen = [], set()
    for ln in re.split(r"[\r\n,;\s]+", text or ""):
        u = parse_line(ln, default_scheme)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def fetch_sources(kinds):
    urls, seen = [], set()
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
        tasks = [(k, c.get(src)) for k in kinds for src in SOURCES.get(k, [])]
        results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
        for (k, _), r in zip(tasks, results):
            if isinstance(r, Exception) or r.status_code != 200:
                continue
            for ln in r.text.splitlines():
                u = parse_line(ln, k)
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
    random.shuffle(urls)
    return urls


async def check_proxy(url, timeout=8.0):
    """Return latency ms if the proxy can reach wtr-lab.com with HTTP 200, else None."""
    try:
        return await asyncio.wait_for(_check(url, timeout), timeout + 2)
    except Exception:
        return None


async def _check(url, timeout):
    t0 = time.time()
    async with httpx.AsyncClient(headers=wtrlab.HEADERS, timeout=timeout, proxy=url,
                                 follow_redirects=True) as c:
        r = await c.get(f"{wtrlab.BASE}/api/chapters/1")
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return int((time.time() - t0) * 1000)
    return None


def new_proxy_doc(url, label="", source="manual", status="unknown", latency=None):
    return {
        "id": str(uuid.uuid4()), "url": url, "label": label, "source": source,
        "enabled": True, "status": status, "latency": latency, "fail_count": 0,
        "last_checked": now_iso() if status != "unknown" else None, "created_at": now_iso(),
    }


class ProxyPool:
    def __init__(self, db):
        self.db = db
        self.harvest = {"running": False, "fetched": 0, "tested": 0, "alive": 0, "added": 0,
                        "last_run": None, "phase": None}
        self._cache = []
        self._cache_ts = 0.0
        self.penalty = {}   # url -> cooldown until ts
        self.fails = {}     # url -> consecutive fail count

    # ---------- import ----------
    async def bulk_add(self, text, label="", default_scheme="http"):
        urls = parse_bulk(text, default_scheme)
        if not urls:
            return {"added": 0, "skipped": 0}
        existing = set(await self.db.proxies.distinct("url", {"url": {"$in": urls}}))
        docs = [new_proxy_doc(u, label, "bulk") for u in urls if u not in existing]
        if docs:
            await self.db.proxies.insert_many(docs)
        self._cache_ts = 0
        return {"added": len(docs), "skipped": len(urls) - len(docs)}

    # ---------- harvest ----------
    def start_harvest(self, kinds, max_pool, log):
        if self.harvest["running"]:
            return False
        asyncio.create_task(self._harvest(kinds, max_pool, log))
        return True

    async def _harvest(self, kinds, max_pool, log):
        self.harvest.update({"running": True, "fetched": 0, "tested": 0, "alive": 0, "added": 0, "phase": "fetch"})
        try:
            alive_now = await self.db.proxies.count_documents({"enabled": True, "status": "alive"})
            need = max(0, int(max_pool) - alive_now)
            urls = await fetch_sources(kinds)
            existing = set(await self.db.proxies.distinct("url"))
            urls = [u for u in urls if u not in existing]
            self.harvest["fetched"] = len(urls)
            self.harvest["phase"] = "test"
            if need == 0:
                await log("INFO", f"Pool proxy đã đủ {alive_now} proxy sống, bỏ qua thu thập")
                return
            sem = asyncio.Semaphore(150)
            added = 0
            stop = asyncio.Event()

            async def one(u):
                nonlocal added
                if stop.is_set():
                    return
                async with sem:
                    if stop.is_set():
                        return
                    lat = await check_proxy(u)
                self.harvest["tested"] += 1
                if lat is not None and not stop.is_set():
                    self.harvest["alive"] += 1
                    await self.db.proxies.update_one(
                        {"url": u}, {"$setOnInsert": new_proxy_doc(u, "", "auto", "alive", lat)}, upsert=True)
                    added += 1
                    self.harvest["added"] = added
                    if added >= need:
                        stop.set()

            await asyncio.gather(*[one(u) for u in urls])
            self._cache_ts = 0
            await log("INFO", f"Thu thập proxy: kiểm tra {self.harvest['tested']}/{len(urls)}, thêm {added} proxy sống")
        except Exception as e:
            await log("ERROR", f"Thu thập proxy lỗi: {e}")
        finally:
            self.harvest.update({"running": False, "last_run": now_iso(), "phase": None})

    # ---------- recheck ----------
    async def recheck_all(self, log, disable_dead=True):
        proxies = await self.db.proxies.find({}, {"_id": 0, "id": 1, "url": 1, "fail_count": 1}).to_list(5000)
        sem = asyncio.Semaphore(150)

        async def one(p):
            async with sem:
                lat = await check_proxy(p["url"])
            if lat is not None:
                upd = {"status": "alive", "latency": lat, "fail_count": 0, "last_checked": now_iso()}
            else:
                fc = int(p.get("fail_count") or 0) + 1
                upd = {"status": "dead", "latency": None, "fail_count": fc, "last_checked": now_iso()}
                if disable_dead and fc >= 2:
                    upd["enabled"] = False
            await self.db.proxies.update_one({"id": p["id"]}, {"$set": upd})
            return lat is not None

        res = await asyncio.gather(*[one(p) for p in proxies])
        alive = sum(1 for r in res if r)
        self._cache_ts = 0
        await log("INFO", f"Kiểm tra lại proxy: {alive}/{len(proxies)} sống")
        return {"alive": alive, "total": len(proxies)}

    async def purge_dead(self):
        r = await self.db.proxies.delete_many({"status": "dead"})
        self._cache_ts = 0
        return r.deleted_count

    # ---------- selection ----------
    async def _enabled(self):
        if time.time() - self._cache_ts > 10:
            self._cache = await self.db.proxies.find(
                {"enabled": True, "status": {"$ne": "dead"}}, {"_id": 0, "url": 1, "latency": 1}
            ).to_list(5000)
            self._cache_ts = time.time()
        return self._cache

    async def pick(self):
        proxies = await self._enabled()
        if not proxies:
            return None
        now = time.time()
        ready = [p for p in proxies if self.penalty.get(p["url"], 0) <= now]
        pool = ready or proxies
        # weight: faster proxies picked more often
        weights = [1.0 / (1.0 + (p.get("latency") or 3000) / 1000.0) for p in pool]
        return random.choices(pool, weights=weights, k=1)[0]["url"]

    async def report(self, url, ok):
        if not url:
            return
        if ok:
            self.fails[url] = 0
            return
        self.fails[url] = self.fails.get(url, 0) + 1
        self.penalty[url] = time.time() + min(30 * self.fails[url], 300)
        if self.fails[url] >= 5:
            await self.db.proxies.update_one(
                {"url": url}, {"$set": {"enabled": False, "status": "dead", "last_checked": now_iso()},
                               "$inc": {"fail_count": 1}})
            self._cache_ts = 0

    async def available_count(self):
        now = time.time()
        return len([p for p in await self._enabled() if self.penalty.get(p["url"], 0) <= now])
