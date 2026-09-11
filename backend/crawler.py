"""Background crawl manager: queue, worker loop, enumeration, proxy rotation."""
import asyncio
import math
import random
import time
import uuid
from datetime import datetime, timezone

import wtrlab

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
        return s

    async def pick_proxy(self):
        s = await self.get_settings()
        if not s.get("use_proxy"):
            return None
        proxies = await self.db.proxies.find({"enabled": True}, {"_id": 0}).to_list(1000)
        if not proxies:
            return None
        return random.choice(proxies)["url"]

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

    async def _loop(self):
        while True:
            try:
                if not self.running:
                    await asyncio.sleep(1)
                    continue
                novel = await self.db.novels.find_one(
                    {"status": "queued"}, sort=[("priority", -1), ("created_at", 1)]
                )
                if not novel:
                    await asyncio.sleep(2)
                    continue
                await self._process_novel(novel)
            except Exception as e:
                await self.log("ERROR", f"Worker loop: {e}")
                await asyncio.sleep(2)

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
            try:
                toc = await wtrlab.get_toc(novel["source_id"], proxy)
            except Exception as e:
                await self._fail_novel(nid, f"TOC lỗi: {e}")
                return
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
                {"id": nid}, {"$set": {"total_chapters": len(docs), "updated_at": now_iso()}}
            )

        settings = await self.get_settings()
        conc = max(1, int(settings.get("concurrency", 3)))
        delay = float(settings.get("delay_ms", 0)) / 1000.0
        sem = asyncio.Semaphore(conc)
        no_progress = 0
        backoff = 30.0

        while True:
            if not self.running:
                await self.db.novels.update_one({"id": nid}, {"$set": {"status": "queued"}})
                return
            fresh = await self.db.novels.find_one({"id": nid}, {"_id": 0, "status": 1})
            if not fresh or fresh["status"] == "paused":
                return
            wait = self.cooldown_until - time.time()
            if wait > 0:
                await self.log("WARN", f"Bị chặn tốc độ, chờ {int(wait)}s (nên bật proxy để nhanh hơn)", nid)
                await asyncio.sleep(min(wait, 60))
                continue
            batch = await self.db.chapters.find(
                {"novel_id": nid, "status": "pending"}
            ).limit(conc).to_list(conc)
            if not batch:
                break
            done_before = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
            await asyncio.gather(*[self._crawl_chapter(nid, ch, sem, delay) for ch in batch])
            done = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
            await self.db.novels.update_one(
                {"id": nid}, {"$set": {"crawled_chapters": done, "updated_at": now_iso()}}
            )
            if done == done_before:
                no_progress += 1
                if no_progress >= 6:
                    await self.log("WARN", "Tạm ngừng truyện do bị chặn liên tục. Thêm proxy rồi Thử lại.", nid)
                    break
                self.cooldown_until = time.time() + backoff
                backoff = min(backoff * 1.5, 180)
            else:
                no_progress = 0
                backoff = 30.0

        errors = await self.db.chapters.count_documents({"novel_id": nid, "status": "error"})
        pending = await self.db.chapters.count_documents({"novel_id": nid, "status": "pending"})
        done = await self.db.chapters.count_documents({"novel_id": nid, "status": "done"})
        status = "done" if (errors == 0 and pending == 0) else "partial"
        await self.db.novels.update_one(
            {"id": nid},
            {"$set": {"status": status, "crawled_chapters": done, "updated_at": now_iso()}},
        )
        await self.log("INFO", f"Kết thúc: {done} xong, {errors} lỗi, {pending} chờ", nid)

    async def _crawl_chapter(self, nid, ch, sem, delay):
        async with sem:
            if not self.running:
                return
            self.active += 1
            try:
                proxy = await self.pick_proxy()
                res = await wtrlab.get_chapter(ch["raw_id"], ch["chapter_order"], ch["chapter_id"], proxy)
                content = "\n".join(res["lines"])
                await self.db.chapters.update_one({"id": ch["id"]}, {"$set": {
                    "body": res["lines"], "content": content, "title_zh_full": res.get("title", ""),
                    "word_count": len(content), "status": "done", "error": None, "crawled_at": now_iso(),
                }})
                self._mark_done()
            except Exception as e:
                msg = str(e)
                if any(k in msg.lower() for k in RATE_MARKERS):
                    # rate-limited: keep pending for backoff/retry, do not count as error
                    await self.db.chapters.update_one(
                        {"id": ch["id"]}, {"$set": {"status": "pending", "error": msg[:300]}}
                    )
                    self.cooldown_until = max(self.cooldown_until, time.time() + 20)
                else:
                    await self.db.chapters.update_one(
                        {"id": ch["id"]}, {"$set": {"status": "error", "error": msg[:300]}}
                    )
                    await self.log("ERROR", f"Chương {ch['chapter_order']}: {msg}", nid)
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
