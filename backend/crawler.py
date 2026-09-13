"""Background crawl manager: queue, worker loop, enumeration, proxy rotation."""
import asyncio
import math
import time
import uuid
from datetime import datetime, timezone

import wtrlab
from proxy_pool import ProxyPool

RATE_MARKERS = ("turnstile", "challenge", "rate", "429", "403", "too many",
                "captcha", "blocked", "forbidden", "unavailable", "503", "502")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class CrawlManager:
    def __init__(self, db):
        self.db = db
        self.running = False
        self.build_id = None
        self.active = 0
        self._completed_ts = []
        self.loop_task = None
        self.enum = {"running": False, "discovered": 0, "total": 0, "page": 0, "pages": 0, "done": False}
        self.cooldown_until = 0.0
        self.scan_task = None
        self.auto_scan = {"running": False, "last_run": None, "next_run": None,
                          "last_found": 0, "total_found": 0, "page": 0, "pages": 0}
        self.pool = ProxyPool(db)
        self.novel_tasks = {}
        self.proxy_task = None
        self._settings_cache = (0.0, None)

    # ---------- helpers ----------
    async def log(self, level, message, novel_id=None):
        await self.db.logs.insert_one({
            "id": str(uuid.uuid4()), "level": level, "message": str(message)[:500],
            "novel_id": novel_id, "created_at": now_iso(),
        })

    async def get_settings(self):
        s = await self.db.settings.find_one({"id": "settings"}, {"_id": 0})
        if not s:
            s = {"id": "settings", "concurrency": 3, "delay_ms": 300, "use_proxy": False}
            await self.db.settings.insert_one(s)
            s.pop("_id", None)
        s.setdefault("auto_scan_enabled", False)
        s.setdefault("auto_scan_interval_min", 60)
        s.setdefault("auto_scan_pages", 3)
        s.setdefault("chapter_limit", 0)
        s.setdefault("parallel_novels", 1)
        s.setdefault("proxy_auto_harvest", True)
        s.setdefault("proxy_max_pool", 400)
        s.setdefault("auto_queue_new", True)
        s.setdefault("proxy_kinds", ["http", "socks5"])
        return s

    async def _settings_fast(self):
        ts, s = self._settings_cache
        if s is None or time.time() - ts > 3:
            s = await self.get_settings()
            self._settings_cache = (time.time(), s)
        return s

    async def pick_proxy(self):
        s = await self._settings_fast()
        if not s.get("use_proxy"):
            return None
        return await self.pool.pick()

    def _mark_done(self):
        self._completed_ts.append(time.time())
        cutoff = time.time() - 60
        self._completed_ts = [t for t in self._completed_ts if t > cutoff]

    def throughput(self):
        cutoff = time.time() - 60
        return len([t for t in self._completed_ts if t > cutoff])

    # ---------- lifecycle ----------
    def ensure_loop(self):
        if self.loop_task is None or self.loop_task.done():
            self.loop_task = asyncio.create_task(self._loop())
        if self.scan_task is None or self.scan_task.done():
            self.scan_task = asyncio.create_task(self._auto_scan_loop())
        if self.proxy_task is None or self.proxy_task.done():
            self.proxy_task = asyncio.create_task(self._proxy_maintenance_loop())

    async def _loop(self):
        while True:
            try:
                self.novel_tasks = {k: t for k, t in self.novel_tasks.items() if not t.done()}
                if not self.running:
                    await asyncio.sleep(1)
                    continue
                s = await self._settings_fast()
                slots = max(1, int(s.get("parallel_novels") or 1)) - len(self.novel_tasks)
                if slots <= 0:
                    await asyncio.sleep(1)
                    continue
                novel = await self.db.novels.find_one_and_update(
                    {"status": "queued", "id": {"$nin": list(self.novel_tasks)}},
                    {"$set": {"status": "crawling", "error": None, "updated_at": now_iso()}},
                    sort=[("priority", -1), ("created_at", 1)],
                )
                if not novel:
                    await asyncio.sleep(2)
                    continue
                self.novel_tasks[novel["id"]] = asyncio.create_task(self._run_novel(novel))
            except Exception as e:
                await self.log("ERROR", f"Worker loop: {e}")
                await asyncio.sleep(2)

    async def _run_novel(self, novel):
        try:
            await self._process_novel(novel)
        except Exception as e:
            await self._fail_novel(novel["id"], f"Lỗi worker: {e}")

    # ---------- novel processing ----------
    async def _process_novel(self, novel):
        nid = novel["id"]
        proxy = await self.pick_proxy()
        await self.db.novels.update_one(
            {"id": nid}, {"$set": {"status": "crawling", "error": None, "updated_at": now_iso()}}
        )
        await self.log("INFO", f"Bắt đầu crawl: {novel.get('title_en') or novel.get('slug')}", nid)

        # Build TOC if missing
        if await self.db.chapters.count_documents({"novel_id": nid}) == 0:
            toc, err = None, None
            for attempt in range(4):
                try:
                    toc = await asyncio.wait_for(
                        wtrlab.get_toc(novel["source_id"], proxy if attempt < 3 else None), 40)
                    await self.pool.report(proxy, True)
                    break
                except Exception as e:
                    err = e
                    await self.pool.report(proxy, False)
                    proxy = await self.pick_proxy()
            if toc is None:
                await self._fail_novel(nid, f"TOC lỗi: {err}")
                return
            site_total = len(toc)
            limit = novel.get("chapter_limit")
            if limit is None:
                limit = (await self.get_settings()).get("chapter_limit", 0)
            limit = int(limit or 0)
            if limit > 0:
                toc = sorted(toc, key=lambda x: x.get("order") or 0)[:limit]
            docs = []
            for it in toc:
                docs.append({
                    "id": str(uuid.uuid4()), "novel_id": nid, "source_id": novel["source_id"],
                    "raw_id": it.get("serie_id"), "chapter_id": it.get("id"),
                    "chapter_order": it.get("order"), "title_en": it.get("title", ""),
                    "title_zh": it.get("name", ""), "status": "pending",
                    "body": None, "content": None, "word_count": 0, "error": None, "crawled_at": None,
                })
            if docs:
                await self.db.chapters.insert_many(docs)
            await self.db.novels.update_one(
                {"id": nid}, {"$set": {"total_chapters": len(docs), "site_chapters": site_total,
                                       "chapter_limit": limit, "updated_at": now_iso()}}
            )

        settings = await self.get_settings()
        conc = max(1, int(settings.get("concurrency", 3)))
        delay = float(settings.get("delay_ms", 0)) / 1000.0
        state = {"stop": False, "fails": 0, "backoff": 30.0}

        async def worker():
            while not state["stop"]:
                if not self.running:
                    return
                fresh = await self.db.novels.find_one({"id": nid}, {"_id": 0, "status": 1})
                if not fresh or fresh["status"] == "paused":
                    state["stop"] = True
                    return
                use_proxy = (await self._settings_fast()).get("use_proxy") and await self.pool.available_count() > 0
                wait = self.cooldown_until - time.time()
                if wait > 0 and not use_proxy:
                    await asyncio.sleep(min(wait, 5))
                    continue
                ch = await self.db.chapters.find_one_and_update(
                    {"novel_id": nid, "status": "pending"}, {"$set": {"status": "fetching"}},
                    sort=[("chapter_order", 1)],
                )
                if not ch:
                    return
                ok = await self._crawl_chapter(nid, ch, delay, use_proxy)
                if ok:
                    state["fails"] = 0
                    state["backoff"] = 30.0
                elif ok is False:
                    state["fails"] += 1
                    if use_proxy:
                        if state["fails"] >= 60:
                            await self.log("WARN", "Tạm ngừng truyện: proxy liên tục thất bại. Làm mới pool proxy rồi Thử lại.", nid)
                            state["stop"] = True
                    else:
                        if state["fails"] >= 6:
                            await self.log("WARN", "Tạm ngừng truyện do bị chặn liên tục. Thêm proxy rồi Thử lại.", nid)
                            state["stop"] = True
                        elif self.cooldown_until <= time.time():
                            self.cooldown_until = time.time() + state["backoff"]
                            state["backoff"] = min(state["backoff"] * 1.5, 180)
                            await self.log("WARN", f"Bị chặn tốc độ, chờ {int(state['backoff'])}s (nên bật proxy để nhanh hơn)", nid)

        async def progress():
            while not state["stop"]:
                await asyncio.sleep(3)
                done = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
                await self.db.novels.update_one({"id": nid}, {"$set": {"crawled_chapters": done, "updated_at": now_iso()}})

        prog = asyncio.create_task(progress())
        await asyncio.gather(*[worker() for _ in range(conc)])
        state["stop"] = True
        prog.cancel()
        await self.db.chapters.update_many({"novel_id": nid, "status": "fetching"}, {"$set": {"status": "pending"}})

        if not self.running:
            done = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
            await self.db.novels.update_one({"id": nid}, {"$set": {"status": "queued", "crawled_chapters": done}})
            return
        fresh = await self.db.novels.find_one({"id": nid}, {"_id": 0, "status": 1})
        if fresh and fresh["status"] == "paused":
            return

        errors = await self.db.chapters.count_documents({"novel_id": nid, "status": "error"})
        pending = await self.db.chapters.count_documents({"novel_id": nid, "status": "pending"})
        done = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
        status = "done" if (errors == 0 and pending == 0) else "partial"
        await self.db.novels.update_one(
            {"id": nid},
            {"$set": {"status": status, "crawled_chapters": done, "updated_at": now_iso()}},
        )
        await self.log("INFO", f"Kết thúc: {done} xong, {errors} lỗi, {pending} chờ", nid)

    async def _crawl_chapter(self, nid, ch, delay, use_proxy):
        """Returns True on success, False on retryable failure, None on hard error."""
        self.active += 1
        proxy = None
        try:
            proxy = await self.pick_proxy() if use_proxy else None
            t0 = time.time()
            res = await asyncio.wait_for(
                wtrlab.get_chapter(ch["raw_id"], ch["chapter_order"], ch["chapter_id"], proxy),
                20 if proxy else 75)
            content = "\n".join(res["lines"])
            await self.db.chapters.update_one({"id": ch["id"]}, {"$set": {
                "body": res["lines"], "content": content, "title_zh_full": res.get("title", ""),
                "word_count": len(content), "status": "done", "error": None, "crawled_at": now_iso(),
            }})
            self._mark_done()
            await self.pool.report(proxy, True, int((time.time() - t0) * 1000))
            return True
        except Exception as e:
            msg = str(e)
            is_rate = any(k in msg.lower() for k in RATE_MARKERS)
            proxy_fault = proxy and not (isinstance(e, RuntimeError) and not is_rate)
            if is_rate or proxy_fault:
                # rate-limited or proxy failure: keep pending for retry, do not count as error
                await self.db.chapters.update_one(
                    {"id": ch["id"]}, {"$set": {"status": "pending", "error": msg[:300]}}
                )
                if proxy:
                    await self.pool.report(proxy, False)
                return False
            await self.db.chapters.update_one(
                {"id": ch["id"]}, {"$set": {"status": "error", "error": msg[:300]}}
            )
            await self.log("ERROR", f"Chương {ch['chapter_order']}: {msg}", nid)
            return None
        finally:
            self.active -= 1
            if delay:
                await asyncio.sleep(delay)

    async def _fail_novel(self, nid, msg):
        await self.db.novels.update_one(
            {"id": nid}, {"$set": {"status": "error", "error": str(msg)[:300], "updated_at": now_iso()}}
        )
        await self.log("ERROR", msg, nid)

    # ---------- enumeration ----------
    async def enumerate_all(self, max_pages=None):
        if self.enum["running"]:
            return
        asyncio.create_task(self._enumerate(max_pages))

    async def _enumerate(self, max_pages):
        self.enum = {"running": True, "discovered": 0, "total": 0, "page": 0, "pages": 0, "done": False}
        proxy = await self.pick_proxy()
        try:
            self.build_id = await wtrlab.get_build_id(proxy)
            _, total = await wtrlab.list_novels(self.build_id, 1, proxy)
            self.enum["total"] = total
            pages = math.ceil(total / 10) if total else 1
            if max_pages:
                pages = min(pages, int(max_pages))
            self.enum["pages"] = pages
            for p in range(1, pages + 1):
                if not self.enum["running"]:
                    break
                try:
                    series, _ = await wtrlab.list_novels(self.build_id, p, proxy)
                except Exception as e:
                    await self.log("WARN", f"Enumerate trang {p}: {e}")
                    continue
                for s in series:
                    await self._upsert_novel(s)
                self.enum["page"] = p
                self.enum["discovered"] = await self.db.novels.count_documents({})
            await self.log("INFO", f"Enumerate xong: {self.enum['discovered']} truyện")
        except Exception as e:
            await self.log("ERROR", f"Enumerate: {e}")
        finally:
            self.enum["running"] = False
            self.enum["done"] = True

    async def _upsert_novel(self, s):
        data = s.get("data", {}) or {}
        raw = data.get("raw", {}) or {}
        await self.db.novels.update_one(
            {"source_id": s["id"]},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()), "source_id": s["id"], "status": "new",
                    "crawled_chapters": 0, "total_chapters": 0, "priority": 0,
                    "error": None, "created_at": now_iso(),
                },
                "$set": {
                    "slug": s.get("slug", ""), "title_en": data.get("title", ""),
                    "title_zh": raw.get("title", ""), "author": data.get("author") or raw.get("author", ""),
                    "cover": data.get("image", ""), "description": data.get("description", ""),
                    "site_status": s.get("status", 0), "updated_at": now_iso(),
                },
            },
            upsert=True,
        )

    # ---------- auto scan for new novels ----------
    async def _auto_scan_loop(self):
        while True:
            try:
                s = await self.get_settings()
                if s.get("auto_scan_enabled"):
                    interval = max(5, int(s.get("auto_scan_interval_min") or 60)) * 60
                    nxt = self.auto_scan.get("next_run_ts") or 0
                    if not nxt:
                        self.auto_scan["next_run_ts"] = time.time() + interval
                        self.auto_scan["next_run"] = datetime.fromtimestamp(
                            self.auto_scan["next_run_ts"], tz=timezone.utc).isoformat()
                    elif time.time() >= nxt and not self.auto_scan["running"]:
                        await self._scan_new(int(s.get("auto_scan_pages") or 3), auto=True)
                else:
                    self.auto_scan["next_run_ts"] = 0
                    self.auto_scan["next_run"] = None
            except Exception as e:
                await self.log("ERROR", f"Auto scan loop: {e}")
            await asyncio.sleep(15)

    async def scan_new_now(self, pages=None):
        if self.auto_scan["running"]:
            return False
        s = await self.get_settings()
        asyncio.create_task(self._scan_new(int(pages or s.get("auto_scan_pages") or 3)))
        return True

    async def _scan_new(self, pages, auto=False):
        self.auto_scan.update({"running": True, "page": 0, "pages": pages})
        s = await self.get_settings()
        limit = int(s.get("chapter_limit") or 0)
        proxy = await self.pick_proxy()
        found = 0
        try:
            self.build_id = await wtrlab.get_build_id(proxy)
            for p in range(1, pages + 1):
                try:
                    series, _ = await wtrlab.list_novels(self.build_id, p, proxy)
                except Exception as e:
                    await self.log("WARN", f"Quét truyện mới trang {p}: {e}")
                    continue
                for sr in series:
                    if await self.db.novels.count_documents({"source_id": sr["id"]}, limit=1):
                        continue
                    await self._upsert_novel(sr)
                    await self.db.novels.update_one(
                        {"source_id": sr["id"]},
                        {"$set": {"status": "queued", "chapter_limit": limit, "auto_added": True}},
                    )
                    found += 1
                self.auto_scan["page"] = p
            if found:
                self.running = True
                self.ensure_loop()
            await self.log("INFO", f"{'Tự động quét' if auto else 'Quét'} truyện mới: phát hiện {found} truyện mới"
                                   + (f" (giới hạn {limit} chương/truyện)" if limit else ""))
        except Exception as e:
            await self.log("ERROR", f"Quét truyện mới: {e}")
        finally:
            interval = max(5, int(s.get("auto_scan_interval_min") or 60)) * 60
            now = time.time()
            self.auto_scan.update({
                "running": False, "last_run": now_iso(), "last_found": found,
                "total_found": self.auto_scan.get("total_found", 0) + found,
                "next_run_ts": now + interval if s.get("auto_scan_enabled") else 0,
                "next_run": datetime.fromtimestamp(now + interval, tz=timezone.utc).isoformat()
                if s.get("auto_scan_enabled") else None,
            })

    # ---------- proxy pool maintenance (continuous) ----------
    async def _proxy_maintenance_loop(self):
        last_recheck = last_purge = last_requeue = 0.0
        while True:
            try:
                s = await self.get_settings()
                now = time.time()
                if s.get("proxy_auto_harvest"):
                    max_pool = int(s.get("proxy_max_pool") or 400)
                    alive = await self.db.proxies.count_documents({"enabled": True, "status": "alive"})
                    if alive < max_pool * 0.9 and not self.pool.harvest["running"]:
                        self.pool.start_harvest(s.get("proxy_kinds") or ["http", "socks5"], max_pool, self.log)
                    if now - last_recheck > 10 * 60 and not self.pool.harvest["running"]:
                        last_recheck = now
                        await self.pool.recheck_all(self.log, only_enabled=True)
                    if now - last_purge > 60 * 60:
                        last_purge = now
                        n = await self.pool.purge_dead(older_than_sec=6 * 3600)
                        if n:
                            await self.log("INFO", f"Đã dọn {n} proxy chết cũ")
                if self.running and now - last_requeue > 60:
                    last_requeue = now
                    await self._requeue_partial()
            except Exception as e:
                await self.log("ERROR", f"Proxy maintenance: {e}")
            await asyncio.sleep(30)

    async def _requeue_partial(self):
        """Fully automatic: requeue partial novels with pending chapters, then feed 'new' novels."""
        if await self.db.novels.count_documents({"status": "queued"}, limit=1):
            return
        ids = await self.db.chapters.distinct("novel_id", {"status": "pending"})
        if ids:
            r = await self.db.novels.update_many(
                {"id": {"$in": ids}, "status": "partial"}, {"$set": {"status": "queued", "updated_at": now_iso()}})
            if r.modified_count:
                await self.log("INFO", f"Tự động xếp lại {r.modified_count} truyện còn chương chờ vào hàng đợi")
                return
        s = await self.get_settings()
        if not s.get("auto_queue_new"):
            return
        batch = max(1, int(s.get("parallel_novels") or 1)) * 3
        new_ids = [n["id"] for n in await self.db.novels.find(
            {"status": "new"}, {"_id": 0, "id": 1}).sort("created_at", 1).limit(batch).to_list(batch)]
        if new_ids:
            await self.db.novels.update_many(
                {"id": {"$in": new_ids}}, {"$set": {"status": "queued", "updated_at": now_iso()}})
            await self.log("INFO", f"Tự động đưa {len(new_ids)} truyện mới vào hàng đợi")
