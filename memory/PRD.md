# PRD — WTR-Lab Crawler Control Center

## Original problem statement
Vietnamese user: "tôi cần app crawl toàn bộ truyện của web này https://wtr-lab.com/".
Chosen: web app to manage crawling; enumerate the whole site into a background queue
(pause/resume, realtime progress); store RAW Chinese chapter text in MongoDB; export to
.txt/.json on disk; dashboard with novels list, per-novel progress, total chapters,
start/pause/retry, error logs, proxy manager. UI in Vietnamese. No reading UI, no AI translation.

## Architecture
- Backend: FastAPI + MongoDB (motor). Background asyncio worker loop (CrawlManager).
- Target site API (reverse-engineered, public):
  - Enumerate: GET /_next/data/{buildId}/en/novel-list.json?page=N (10/page, ~94,679 novels)
  - TOC: GET /api/chapters/{source_id} (returns all chapters incl. serie_id/raw_id, order, zh name)
  - Content: POST /api/reader/get {translate:"web"} -> AES-GCM encrypted body
    (key IJAFUUxjM25hyzL2AZrn0wl7cESED6Ru) -> raw Chinese lines.
- Collections: novels, chapters, proxies, logs, settings.
- Files: backend/wtrlab.py (site client), backend/crawler.py (queue/worker), backend/server.py (API).
- Frontend: React dark "ops" dashboard (Sidebar, TopBar, Dashboard, NovelsTable,
  NovelDetailDrawer raw-Chinese viewer, ProxyManager, LogsPanel, SettingsPanel).

## Implemented (2026-06-11)
- Enumerate all/N pages of catalog into queue (background, live progress).
- Add single novel by URL; queue-all (new); per-novel start/pause/retry/delete.
- Background worker: concurrency + delay settings, proxy rotation, self-throttling
  backoff on Cloudflare Turnstile/HTTP rate limits (blocked chapters kept 'pending').
- Raw Chinese chapter storage in MongoDB (body as line list + joined content).
- Chapter inspector drawer with raw Chinese preview + copy.
- Export per novel to .txt / .json on disk (/app/exports).
- Proxy CRUD + enable/disable + latency test. Live logs terminal. Dashboard stats.
- Tested: 13/13 backend pytest + full frontend e2e pass (iteration_1).

## Notes / constraints
- No auth, no external API keys.
- wtr-lab.com rate-limits (~15 rapid requests/IP via Turnstile) -> use proxies for full-speed
  large crawls. Full-site crawl (94k novels / millions of chapters) is supported by the queue
  but is a long-running operation; validated on small novels + 1 enumerate page.

## Backlog (P1/P2)
- P1: Proxy-aware buildId refresh scheduling; bulk export (whole DB) as zip.
- P1: Per-novel priority controls in UI; resume 'pending' automatically after cooldown for all novels.
- P2: EPUB export; search across chapter content; scheduled/auto re-crawl of updated novels.
