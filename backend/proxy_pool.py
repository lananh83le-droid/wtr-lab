"""Free-proxy harvesting, bulk import, liveness checking and smart selection."""
import asyncio
import random
import re
import time
import uuid
from datetime import datetime, timezone

import httpx

import wtrlab

GH = "https://raw.githubusercontent.com/"
# Tier 1: small, frequently re-checked lists (high hit-rate). Tier 2: large raw dumps (sampled).
SOURCES = {
    "http": {
        1: [
            GH + "TheSpeedX/PROXY-List/master/http.txt",
            GH + "proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
            GH + "monosans/proxy-list/main/proxies/http.txt",
            GH + "jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
            GH + "elliottophellia/yakumo/master/results/http/global/http_checked.txt",
            GH + "vakhov/fresh-proxy-list/master/http.txt",
            GH + "zloi-user/hideip.me/main/http.txt",
            GH + "zloi-user/hideip.me/main/https.txt",
            GH + "Zaeem20/FREE_PROXIES_LIST/master/http.txt",
            GH + "ALIILAPRO/Proxy/main/http.txt",
            GH + "rdavydov/proxy-list/main/proxies/http.txt",
            GH + "proxylist-to/proxy-list/main/http.txt",
            GH + "im-razvan/proxy_list/main/http.txt",
            GH + "clarketm/proxy-list/master/proxy-list-raw.txt",
            GH + "themiralay/Proxy-List-World/master/data.txt",
            GH + "opsxcq/proxy-list/master/list.txt",
            GH + "almroot/proxylist/master/list.txt",
            GH + "hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
            GH + "andigwandi/free-proxy/main/proxy_list.txt",
            GH + "saisuiu/Lionkings-Http-Proxys-Proxies/main/free.txt",
            GH + "Vann-Dev/proxy-list/main/proxies/http.txt",
            GH + "berkay-digital/Proxy-Scraper/main/proxies.txt",
            "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=ipport&format=text",
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://www.proxy-list.download/api/v1/get?type=https",
        ],
        2: [
            GH + "sunny9577/proxy-scraper/master/proxies.txt",
            GH + "sunny9577/proxy-scraper/master/generated/http_proxies.txt",
            GH + "Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
            GH + "Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
            GH + "databay-labs/free-proxy-list/master/http.txt",
            GH + "ProxyScraper/ProxyScraper/main/http.txt",
            GH + "B4RC0DE-TM/proxy-list/main/HTTP.txt",
            GH + "aslisk/proxyhttps/main/https.txt",
            GH + "dpangestuw/Free-Proxy/refs/heads/main/http_proxies.txt",
            GH + "r00tee/Proxy-List/main/Https.txt",
            GH + "TuanMinPay/live-proxy/master/http.txt",
            GH + "Skiddle-ID/proxylist/main/proxies.txt",
            GH + "proxy4parsing/proxy-list/main/http.txt",
            GH + "yuceltoluyag/GoodProxy/main/raw.txt",
            GH + "ErcinDedeoglu/proxies/main/proxies/http.txt",
            GH + "zevtyardt/proxy-list/main/http.txt",
            GH + "MuRongPIG/Proxy-Master/main/http.txt",
            GH + "SoliSpirit/proxy-list/main/http.txt",
            GH + "Tsprnay/Proxy-lists/master/proxies/http.txt",
            GH + "casals-ar/proxy-list/main/http",
            "https://api.openproxylist.xyz/http.txt",
            "https://proxyspace.pro/http.txt",
        ],
    },
    "socks5": {
        1: [
            GH + "TheSpeedX/PROXY-List/master/socks5.txt",
            GH + "proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
            GH + "monosans/proxy-list/main/proxies/socks5.txt",
            GH + "hookzof/socks5_list/master/proxy.txt",
            GH + "jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
            GH + "elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
            GH + "ShiftyTR/Proxy-List/master/socks5.txt",
            GH + "zloi-user/hideip.me/main/socks5.txt",
            GH + "Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
            GH + "ALIILAPRO/Proxy/main/socks5.txt",
            GH + "rdavydov/proxy-list/main/proxies/socks5.txt",
            GH + "proxylist-to/proxy-list/main/socks5.txt",
            GH + "im-razvan/proxy_list/main/socks5.txt",
            GH + "B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
            GH + "databay-labs/free-proxy-list/master/socks5.txt",
            GH + "Firdoxx/proxy-list/main/socks5",
            "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks5&proxy_format=ipport&format=text",
            "https://www.proxy-list.download/api/v1/get?type=socks5",
        ],
        2: [
            GH + "Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5_proxies.txt",
            GH + "ProxyScraper/ProxyScraper/main/socks5.txt",
            GH + "dpangestuw/Free-Proxy/refs/heads/main/socks5_proxies.txt",
            GH + "r00tee/Proxy-List/main/Socks5.txt",
            GH + "TuanMinPay/live-proxy/master/socks5.txt",
            GH + "ErcinDedeoglu/proxies/main/proxies/socks5.txt",
            GH + "zevtyardt/proxy-list/main/socks5.txt",
            GH + "MuRongPIG/Proxy-Master/main/socks5.txt",
            GH + "SoliSpirit/proxy-list/main/socks5.txt",
            GH + "Tsprnay/Proxy-lists/master/proxies/socks5.txt",
            GH + "casals-ar/proxy-list/main/socks5",
            "https://api.openproxylist.xyz/socks5.txt",
            "https://proxyspace.pro/socks5.txt",
        ],
    },
}
SOURCE_COUNT = sum(len(v) for k in SOURCES.values() for v in k.values())
TIER2_SAMPLE = 4000
CHECK_CONCURRENCY = 250
LINE_RE = re.compile(r"^(?:(?P<scheme>https?|socks5h?|socks4):\/\/)?(?:(?P<auth>[^@\s]+)@)?(?P<host>[\w.\-\[\]:]+?):(?P<port>\d{2,5})$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_line(line, default_scheme="http"):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = LINE_RE.match(line)
    if not m:
        parts = line.split(":")
        if len(parts) == 4 and parts[1].isdigit():
            return f"{default_scheme}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return None
    scheme = (m.group("scheme") or default_scheme).lower()
    if scheme == "https":
        scheme = "http"
    if scheme == "socks4":
        return None
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


async def fetch_sources(kinds, tier):
    urls, seen = [], set()
    tasks = [(k, src) for k in kinds for src in SOURCES.get(k, {}).get(tier, [])]
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, verify=wtrlab.SSL_CTX) as c:
        results = await asyncio.gather(*[c.get(src) for _, src in tasks], return_exceptions=True)
    ok_sources = 0
    for (k, _), r in zip(tasks, results):
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        ok_sources += 1
        lines = r.text.splitlines()
        if tier == 2 and len(lines) > TIER2_SAMPLE:
            lines = random.sample(lines, TIER2_SAMPLE)
        for ln in lines:
            u = parse_line(ln, k)
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
    random.shuffle(urls)
    return urls, ok_sources


async def check_proxy(url, timeout=6.0):
    """Return latency ms if the proxy can reach wtr-lab.com with HTTP 200, else None."""
    try:
        return await asyncio.wait_for(_check(url, timeout), timeout + 2)
    except Exception:
        return None


async def _check(url, timeout):
    t0 = time.time()
    async with httpx.AsyncClient(headers=wtrlab.HEADERS, timeout=timeout, proxy=url,
                                 follow_redirects=True, verify=wtrlab.SSL_CTX) as c:
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
                        "last_run": None, "phase": None, "tier": 0, "sources": SOURCE_COUNT, "runs": 0}
        self._cache = []
        self._cache_ts = 0.0
        self.penalty = {}    # url -> cooldown until ts
        self.fails = {}      # url -> consecutive fail count
        self.lat = {}        # url -> EMA latency (ms) measured on real requests
        self.seen_dead = {}  # url -> ts (in-memory blacklist so harvest doesn't retest soon)

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
        self.harvest.update({"running": True, "fetched": 0, "tested": 0, "alive": 0, "added": 0,
                             "phase": "fetch", "tier": 1})
        added = 0
        try:
            alive_now = await self.db.proxies.count_documents({"enabled": True, "status": "alive"})
            need = max(0, int(max_pool) - alive_now)
            if need == 0:
                return
            existing = set(await self.db.proxies.distinct("url"))
            cutoff = time.time() - 3600
            self.seen_dead = {u: t for u, t in self.seen_dead.items() if t > cutoff}
            sem = asyncio.Semaphore(CHECK_CONCURRENCY)
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
                if lat is None:
                    self.seen_dead[u] = time.time()
                    return
                if stop.is_set():
                    return
                self.harvest["alive"] += 1
                await self.db.proxies.update_one(
                    {"url": u}, {"$setOnInsert": new_proxy_doc(u, "", "auto", "alive", lat)}, upsert=True)
                added += 1
                self.harvest["added"] = added
                if added >= need:
                    stop.set()

            for tier in (1, 2):
                if stop.is_set():
                    break
                self.harvest.update({"tier": tier, "phase": "fetch"})
                urls, ok_src = await fetch_sources(kinds, tier)
                urls = [u for u in urls if u not in existing and u not in self.seen_dead]
                self.harvest["fetched"] += len(urls)
                self.harvest["phase"] = "test"
                await log("INFO", f"Thu thập proxy tầng {tier}: {ok_src} nguồn, {len(urls)} proxy mới cần test")
                await asyncio.gather(*[one(u) for u in urls])
            self._cache_ts = 0
            await log("INFO", f"Thu thập proxy xong: test {self.harvest['tested']}, thêm {added} proxy sống "
                              f"(pool sống hiện {alive_now + added}/{max_pool})")
        except Exception as e:
            await log("ERROR", f"Thu thập proxy lỗi: {e}")
        finally:
            self.harvest.update({"running": False, "last_run": now_iso(), "phase": None,
                                 "runs": self.harvest.get("runs", 0) + 1})

    # ---------- recheck ----------
    async def recheck_all(self, log, only_enabled=False):
        q = {"enabled": True} if only_enabled else {}
        proxies = await self.db.proxies.find(q, {"_id": 0, "id": 1, "url": 1, "fail_count": 1}).to_list(20000)
        sem = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def one(p):
            async with sem:
                lat = await check_proxy(p["url"])
            if lat is not None:
                upd = {"status": "alive", "latency": lat, "fail_count": 0, "last_checked": now_iso(), "enabled": True}
                self.fails.pop(p["url"], None)
                self.penalty.pop(p["url"], None)
            else:
                upd = {"status": "dead", "latency": None, "fail_count": int(p.get("fail_count") or 0) + 1,
                       "last_checked": now_iso(), "enabled": False}
                await wtrlab.drop_client(p["url"])
            await self.db.proxies.update_one({"id": p["id"]}, {"$set": upd})
            return lat is not None

        res = await asyncio.gather(*[one(p) for p in proxies])
        alive = sum(1 for r in res if r)
        self._cache_ts = 0
        await log("INFO", f"Kiểm tra lại proxy: {alive}/{len(proxies)} sống")
        return {"alive": alive, "total": len(proxies)}

    async def purge_dead(self, older_than_sec=0):
        q = {"status": "dead"}
        if older_than_sec:
            cutoff = datetime.fromtimestamp(time.time() - older_than_sec, tz=timezone.utc).isoformat()
            q["last_checked"] = {"$lt": cutoff}
        r = await self.db.proxies.delete_many(q)
        self._cache_ts = 0
        return r.deleted_count

    # ---------- selection ----------
    async def _enabled(self):
        if time.time() - self._cache_ts > 10:
            self._cache = await self.db.proxies.find(
                {"enabled": True, "status": {"$ne": "dead"}}, {"_id": 0, "url": 1, "latency": 1}
            ).to_list(20000)
            self._cache_ts = time.time()
        return self._cache

    async def pick(self):
        proxies = await self._enabled()
        if not proxies:
            return None
        now = time.time()
        ready = [p for p in proxies if self.penalty.get(p["url"], 0) <= now]
        pool = ready or proxies
        weights = [1.0 / (0.3 + (self.lat.get(p["url"]) or p.get("latency") or 4000) / 1000.0) ** 2 for p in pool]
        return random.choices(pool, weights=weights, k=1)[0]["url"]

    async def report(self, url, ok, latency_ms=None):
        if not url:
            return
        if ok:
            self.fails[url] = 0
            if latency_ms is not None:
                prev = self.lat.get(url)
                self.lat[url] = latency_ms if prev is None else int(prev * 0.7 + latency_ms * 0.3)
            return
        self.fails[url] = self.fails.get(url, 0) + 1
        self.penalty[url] = time.time() + min(20 * self.fails[url], 240)
        if self.fails[url] >= 4:
            await self.db.proxies.update_one(
                {"url": url}, {"$set": {"enabled": False, "status": "dead", "last_checked": now_iso()},
                               "$inc": {"fail_count": 1}})
            await wtrlab.drop_client(url)
            self._cache_ts = 0

    async def available_count(self):
        now = time.time()
        return len([p for p in await self._enabled() if self.penalty.get(p["url"], 0) <= now])
