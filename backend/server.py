from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import asyncio
import json
import uuid
import zipfile
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

import proxy_pool
from crawler import CrawlManager, now_iso

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EXPORT_DIR = Path("/app/exports")
EXPORT_DIR.mkdir(exist_ok=True)

app = FastAPI()
api_router = APIRouter(prefix="/api")
manager = CrawlManager(db)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------------- models ----------------
class EnumerateReq(BaseModel):
    max_pages: Optional[int] = None


class AddNovelReq(BaseModel):
    url: str
    priority: int = 0


class ProxyReq(BaseModel):
    url: str
    label: Optional[str] = ""


class SettingsReq(BaseModel):
    concurrency: Optional[int] = None
    delay_ms: Optional[int] = None
    use_proxy: Optional[bool] = None
    auto_scan_enabled: Optional[bool] = None
    auto_scan_interval_min: Optional[int] = None
    auto_scan_pages: Optional[int] = None
    chapter_limit: Optional[int] = None
    parallel_novels: Optional[int] = None
    proxy_auto_harvest: Optional[bool] = None
    proxy_max_pool: Optional[int] = None
    proxy_kinds: Optional[list] = None


class BulkProxyReq(BaseModel):
    text: str
    label: Optional[str] = ""
    default_scheme: Optional[str] = "http"


class HarvestReq(BaseModel):
    kinds: Optional[list] = None
    max_pool: Optional[int] = None


class ScanNewReq(BaseModel):
    pages: Optional[int] = None


class QueueAllReq(BaseModel):
    only_new: bool = True
    priority: int = 0


# ---------------- health & stats ----------------
@api_router.get("/")
async def root():
    return {"message": "WTR-Lab Crawler API"}


@api_router.get("/stats")
async def stats():
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    by_status = {d["_id"]: d["n"] async for d in db.novels.aggregate(pipeline)}
    total_novels = await db.novels.count_documents({})
    total_chapters = await db.chapters.count_documents({})
    chapters_done = await db.chapters.count_documents({"status": "done"})
    chapters_error = await db.chapters.count_documents({"status": "error"})
    return {
        "total_novels": total_novels,
        "novels_by_status": by_status,
        "total_chapters": total_chapters,
        "chapters_done": chapters_done,
        "chapters_error": chapters_error,
        "throughput": manager.throughput(),
        "active": manager.active,
        "queue_size": by_status.get("queued", 0) + by_status.get("crawling", 0),
        "running": manager.running,
    }


@api_router.get("/crawl/status")
async def crawl_status():
    return {
        "running": manager.running,
        "active": manager.active,
        "throughput": manager.throughput(),
        "build_id": manager.build_id,
        "enumerate": manager.enum,
        "auto_scan": {k: v for k, v in manager.auto_scan.items() if k != "next_run_ts"},
    }


@api_router.post("/crawl/scan-new")
async def crawl_scan_new(req: ScanNewReq):
    if not await manager.scan_new_now(req.pages):
        raise HTTPException(400, "Đang quét truyện mới rồi")
    return {"started": True}


@api_router.post("/crawl/start")
async def crawl_start():
    manager.running = True
    manager.ensure_loop()
    await db.settings.update_one({"id": "settings"}, {"$set": {"running": True}}, upsert=True)
    await manager.log("INFO", "Đã khởi động crawler")
    return {"running": True}


@api_router.post("/crawl/pause")
async def crawl_pause():
    manager.running = False
    await db.settings.update_one({"id": "settings"}, {"$set": {"running": False}}, upsert=True)
    await manager.log("INFO", "Đã tạm dừng crawler")
    return {"running": False}


@api_router.post("/crawl/enumerate")
async def crawl_enumerate(req: EnumerateReq):
    if manager.enum["running"]:
        raise HTTPException(400, "Đang quét danh sách rồi")
    await manager.enumerate_all(req.max_pages)
    return {"started": True}


@api_router.post("/crawl/enumerate/stop")
async def crawl_enumerate_stop():
    manager.enum["running"] = False
    return {"stopped": True}


# ---------------- novels ----------------
@api_router.get("/novels")
async def list_novels(search: str = "", status: str = "", page: int = 1, limit: int = 20):
    q = {}
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"title_en": {"$regex": re.escape(search), "$options": "i"}},
            {"title_zh": {"$regex": re.escape(search), "$options": "i"}},
            {"slug": {"$regex": re.escape(search), "$options": "i"}},
        ]
    total = await db.novels.count_documents(q)
    skip = (page - 1) * limit
    docs = await db.novels.find(q, {"_id": 0}).sort(
        [("priority", -1), ("updated_at", -1)]
    ).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "page": page, "limit": limit, "items": docs}


@api_router.post("/novels/add")
async def add_novel(req: AddNovelReq):
    m = re.search(r"/novel/(\d+)(?:/([^/?#]+))?", req.url)
    if not m:
        raise HTTPException(400, "URL không hợp lệ. Ví dụ: https://wtr-lab.com/en/novel/1439/slug")
    source_id = int(m.group(1))
    slug = m.group(2) or str(source_id)
    existing = await db.novels.find_one({"source_id": source_id}, {"_id": 0})
    if existing:
        await db.novels.update_one(
            {"source_id": source_id},
            {"$set": {"status": "queued", "priority": req.priority, "updated_at": now_iso()}},
        )
        manager.running = True
        manager.ensure_loop()
        return {"added": False, "queued": True, "id": existing["id"]}
    doc = {
        "id": str(uuid.uuid4()), "source_id": source_id, "slug": slug,
        "title_en": slug.replace("-", " ").title(), "title_zh": "", "author": "",
        "cover": "", "description": "", "status": "queued", "priority": req.priority,
        "crawled_chapters": 0, "total_chapters": 0, "error": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.novels.insert_one(doc)
    manager.running = True
    manager.ensure_loop()
    await manager.log("INFO", f"Thêm & xếp hàng truyện #{source_id}", doc["id"])
    return {"added": True, "queued": True, "id": doc["id"]}


@api_router.post("/novels/queue-all")
async def queue_all(req: QueueAllReq):
    q = {"status": "new"} if req.only_new else {"status": {"$in": ["new", "error", "partial", "paused"]}}
    res = await db.novels.update_many(
        q, {"$set": {"status": "queued", "priority": req.priority, "updated_at": now_iso()}}
    )
    manager.running = True
    manager.ensure_loop()
    await manager.log("INFO", f"Xếp hàng {res.modified_count} truyện")
    return {"queued": res.modified_count}


@api_router.get("/novels/{novel_id}")
async def get_novel(novel_id: str):
    novel = await db.novels.find_one({"id": novel_id}, {"_id": 0})
    if not novel:
        raise HTTPException(404, "Không tìm thấy truyện")
    pipeline = [{"$match": {"novel_id": novel_id}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    chap_status = {d["_id"]: d["n"] async for d in db.chapters.aggregate(pipeline)}
    novel["chapter_status"] = chap_status
    return novel


@api_router.post("/novels/{novel_id}/queue")
async def queue_novel(novel_id: str, priority: int = 0):
    r = await db.novels.update_one(
        {"id": novel_id}, {"$set": {"status": "queued", "priority": priority, "updated_at": now_iso()}}
    )
    if not r.matched_count:
        raise HTTPException(404, "Không tìm thấy truyện")
    manager.running = True
    manager.ensure_loop()
    return {"queued": True}


@api_router.post("/novels/{novel_id}/pause")
async def pause_novel(novel_id: str):
    r = await db.novels.update_one(
        {"id": novel_id}, {"$set": {"status": "paused", "updated_at": now_iso()}}
    )
    if not r.matched_count:
        raise HTTPException(404, "Không tìm thấy truyện")
    return {"paused": True}


@api_router.post("/novels/{novel_id}/retry")
async def retry_novel(novel_id: str):
    novel = await db.novels.find_one({"id": novel_id}, {"_id": 0})
    if not novel:
        raise HTTPException(404, "Không tìm thấy truyện")
    await db.chapters.update_many(
        {"novel_id": novel_id, "status": "error"}, {"$set": {"status": "pending", "error": None}}
    )
    await db.novels.update_one(
        {"id": novel_id}, {"$set": {"status": "queued", "error": None, "updated_at": now_iso()}}
    )
    manager.running = True
    manager.ensure_loop()
    return {"retried": True}


@api_router.delete("/novels/{novel_id}")
async def delete_novel(novel_id: str):
    await db.chapters.delete_many({"novel_id": novel_id})
    await db.novels.delete_one({"id": novel_id})
    return {"deleted": True}


@api_router.get("/novels/{novel_id}/chapters")
async def novel_chapters(novel_id: str, page: int = 1, limit: int = 50, status: str = ""):
    q = {"novel_id": novel_id}
    if status:
        q["status"] = status
    total = await db.chapters.count_documents(q)
    skip = (page - 1) * limit
    docs = await db.chapters.find(
        q, {"_id": 0, "body": 0, "content": 0}
    ).sort("chapter_order", 1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "page": page, "limit": limit, "items": docs}


@api_router.get("/chapters/{chapter_id}")
async def get_chapter(chapter_id: str):
    ch = await db.chapters.find_one({"id": chapter_id}, {"_id": 0})
    if not ch:
        raise HTTPException(404, "Không tìm thấy chương")
    return ch


# ---------------- proxies ----------------
@api_router.get("/proxies")
async def list_proxies():
    items = await db.proxies.find({}, {"_id": 0}).sort([("status", 1), ("latency", 1)]).to_list(5000)
    return items


@api_router.get("/proxies/summary")
async def proxies_summary():
    pipeline = [{"$group": {"_id": {"s": "$status", "e": "$enabled"}, "n": {"$sum": 1}}}]
    total = alive = dead = enabled = 0
    async for d in db.proxies.aggregate(pipeline):
        n = d["n"]
        total += n
        if d["_id"]["s"] == "alive":
            alive += n
        if d["_id"]["s"] == "dead":
            dead += n
        if d["_id"]["e"]:
            enabled += n
    return {"total": total, "alive": alive, "dead": dead, "enabled": enabled,
            "available": await manager.pool.available_count(), "harvest": manager.pool.harvest}


@api_router.post("/proxies/bulk")
async def bulk_proxies(req: BulkProxyReq):
    res = await manager.pool.bulk_add(req.text, req.label or "", req.default_scheme or "http")
    await manager.log("INFO", f"Nhập hàng loạt: thêm {res['added']} proxy, bỏ qua {res['skipped']} trùng")
    return res


@api_router.post("/proxies/harvest")
async def harvest_proxies(req: HarvestReq):
    s = await manager.get_settings()
    kinds = req.kinds or s.get("proxy_kinds") or ["http", "socks5"]
    max_pool = req.max_pool or s.get("proxy_max_pool") or 200
    if not manager.pool.start_harvest(kinds, max_pool, manager.log):
        raise HTTPException(400, "Đang thu thập proxy rồi")
    await manager.log("INFO", f"Bắt đầu thu thập proxy miễn phí ({', '.join(kinds)}), tối đa {max_pool}")
    return {"started": True}


@api_router.post("/proxies/recheck")
async def recheck_proxies():
    asyncio.create_task(manager.pool.recheck_all(manager.log))
    return {"started": True}


@api_router.delete("/proxies/dead")
async def purge_dead_proxies():
    n = await manager.pool.purge_dead()
    return {"deleted": n}


@api_router.post("/proxies")
async def add_proxy(req: ProxyReq):
    url = proxy_pool.parse_line(req.url) or req.url.strip()
    if await db.proxies.find_one({"url": url}):
        raise HTTPException(400, "Proxy đã tồn tại")
    doc = proxy_pool.new_proxy_doc(url, req.label or "")
    await db.proxies.insert_one(doc)
    doc.pop("_id", None)
    manager.pool._cache_ts = 0
    return doc


@api_router.delete("/proxies/{proxy_id}")
async def delete_proxy(proxy_id: str):
    await db.proxies.delete_one({"id": proxy_id})
    return {"deleted": True}


@api_router.post("/proxies/{proxy_id}/toggle")
async def toggle_proxy(proxy_id: str):
    p = await db.proxies.find_one({"id": proxy_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Không tìm thấy proxy")
    await db.proxies.update_one({"id": proxy_id}, {"$set": {"enabled": not p["enabled"]}})
    return {"enabled": not p["enabled"]}


@api_router.post("/proxies/{proxy_id}/test")
async def test_proxy(proxy_id: str):
    p = await db.proxies.find_one({"id": proxy_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Không tìm thấy proxy")
    result = {"status": "dead", "latency": None}
    lat = await proxy_pool.check_proxy(p["url"], timeout=12.0)
    upd = {"status": "dead", "latency": None, "last_checked": now_iso()}
    if lat is not None:
        result = {"status": "alive", "latency": lat}
        upd = {"status": "alive", "latency": lat, "last_checked": now_iso(), "fail_count": 0}
    await db.proxies.update_one({"id": proxy_id}, {"$set": upd})
    manager.pool._cache_ts = 0
    return result


# ---------------- logs & settings ----------------
@api_router.get("/logs")
async def get_logs(limit: int = 100, level: str = ""):
    q = {"level": level} if level else {}
    return await db.logs.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


@api_router.delete("/logs")
async def clear_logs():
    await db.logs.delete_many({})
    return {"cleared": True}


@api_router.get("/settings")
async def get_settings():
    return await manager.get_settings()


@api_router.put("/settings")
async def update_settings(req: SettingsReq):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        await db.settings.update_one({"id": "settings"}, {"$set": updates}, upsert=True)
    return await manager.get_settings()


# ---------------- export ----------------
def _novel_txt(novel, chapters):
    parts = [f"{novel.get('title_zh') or novel.get('title_en')}\n作者: {novel.get('author','')}\n\n"]
    for c in chapters:
        title = c.get("title_zh_full") or c.get("title_zh") or f"第{c['chapter_order']}章"
        parts.append(f"\n\n===== {title} =====\n\n{c.get('content','')}")
    return "".join(parts)


def _novel_json(novel, chapters):
    return {
        "novel": {k: novel.get(k) for k in ("source_id", "slug", "title_en", "title_zh", "author")},
        "chapters": [
            {"order": c["chapter_order"], "title_zh": c.get("title_zh_full") or c.get("title_zh"),
             "title_en": c.get("title_en"), "body": c.get("body")}
            for c in chapters
        ],
    }


def _safe_name(novel):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", novel.get("slug") or str(novel["source_id"]))[:80]


@api_router.get("/novels/{novel_id}/export")
async def export_novel(novel_id: str, fmt: str = "txt"):
    novel = await db.novels.find_one({"id": novel_id}, {"_id": 0})
    if not novel:
        raise HTTPException(404, "Không tìm thấy truyện")
    chapters = await db.chapters.find(
        {"novel_id": novel_id, "status": "done"}, {"_id": 0}
    ).sort("chapter_order", 1).to_list(100000)
    if not chapters:
        raise HTTPException(400, "Chưa có chương nào được crawl xong để xuất")
    safe = _safe_name(novel)
    if fmt == "json":
        path = EXPORT_DIR / f"{safe}.json"
        path.write_text(json.dumps(_novel_json(novel, chapters), ensure_ascii=False, indent=2), encoding="utf-8")
        return FileResponse(path, media_type="application/json", filename=path.name)
    path = EXPORT_DIR / f"{safe}.txt"
    path.write_text(_novel_txt(novel, chapters), encoding="utf-8")
    return FileResponse(path, media_type="text/plain", filename=path.name)


@api_router.get("/export/all")
async def export_all(fmt: str = "txt"):
    novel_ids = await db.chapters.distinct("novel_id", {"status": "done"})
    if not novel_ids:
        raise HTTPException(400, "Chưa có truyện nào có chương đã crawl xong để xuất")
    zip_path = EXPORT_DIR / f"wtr-lab-export-{fmt}.zip"
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for nid in novel_ids:
            novel = await db.novels.find_one({"id": nid}, {"_id": 0})
            if not novel:
                continue
            chapters = await db.chapters.find(
                {"novel_id": nid, "status": "done"}, {"_id": 0}
            ).sort("chapter_order", 1).to_list(100000)
            if not chapters:
                continue
            base = f"{_safe_name(novel)}_{novel['source_id']}"
            if fmt == "json":
                zf.writestr(f"{base}.json", json.dumps(_novel_json(novel, chapters), ensure_ascii=False, indent=2))
            else:
                zf.writestr(f"{base}.txt", _novel_txt(novel, chapters))
            count += 1
    if count == 0:
        raise HTTPException(400, "Không có dữ liệu để xuất")
    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    await db.novels.create_index("source_id", unique=True)
    await db.novels.create_index("status")
    await db.chapters.create_index("novel_id")
    await db.chapters.create_index([("novel_id", 1), ("status", 1)])
    await db.logs.create_index("created_at")
    await db.proxies.create_index("url", unique=True)
    await db.novels.update_many({"status": "crawling"}, {"$set": {"status": "queued"}})
    await db.chapters.update_many({"status": "fetching"}, {"$set": {"status": "pending"}})
    s = await db.settings.find_one({"id": "settings"}, {"_id": 0, "running": 1})
    manager.running = bool(s and s.get("running"))
    manager.ensure_loop()
    logger.info("Crawler manager initialised")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
