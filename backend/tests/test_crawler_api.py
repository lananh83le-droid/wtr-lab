"""Backend integration tests for WTR-Lab crawler API."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://story-harvester.preview.emergentagent.com"
API = f"{BASE}/api"

TEST_NOVEL_URL = "https://wtr-lab.com/en/novel/97812/tokyo-ghoul-re-zero-return-of-death"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# --- Basics ---
def test_root(s):
    r = s.get(f"{API}/")
    assert r.status_code == 200
    assert "message" in r.json()


def test_stats(s):
    r = s.get(f"{API}/stats")
    assert r.status_code == 200
    d = r.json()
    for k in ("total_novels", "total_chapters", "chapters_done", "running", "throughput"):
        assert k in d


def test_crawl_status(s):
    r = s.get(f"{API}/crawl/status")
    assert r.status_code == 200
    d = r.json()
    assert "running" in d and "enumerate" in d


# --- Crawler start/pause ---
def test_crawl_start_pause(s):
    r = s.post(f"{API}/crawl/start")
    assert r.status_code == 200
    assert r.json()["running"] is True
    time.sleep(0.5)
    assert s.get(f"{API}/crawl/status").json()["running"] is True

    r = s.post(f"{API}/crawl/pause")
    assert r.status_code == 200
    assert r.json()["running"] is False


# --- Settings ---
def test_settings_get_put(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    orig = r.json()
    r = s.put(f"{API}/settings", json={"concurrency": 3, "delay_ms": 300, "use_proxy": False})
    assert r.status_code == 200
    upd = r.json()
    assert upd["concurrency"] == 3
    assert upd["delay_ms"] == 300
    assert upd["use_proxy"] is False


# --- Proxies CRUD ---
def test_proxies_crud(s):
    r = s.post(f"{API}/proxies", json={"url": "http://TEST_proxy.invalid:8080", "label": "TEST_p"})
    assert r.status_code == 200
    p = r.json()
    pid = p["id"]
    assert p["enabled"] is True

    r = s.get(f"{API}/proxies")
    assert r.status_code == 200
    assert any(x["id"] == pid for x in r.json())

    r = s.post(f"{API}/proxies/{pid}/toggle")
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = s.delete(f"{API}/proxies/{pid}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


# --- Logs ---
def test_logs(s):
    r = s.get(f"{API}/logs?limit=20")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# --- Enumerate ---
def test_enumerate_starts_and_discovers(s):
    r = s.post(f"{API}/crawl/enumerate", json={"max_pages": 1})
    assert r.status_code in (200, 400)  # 400 if already running
    # Poll for up to 25s
    discovered = 0
    for _ in range(25):
        time.sleep(1)
        st = s.get(f"{API}/crawl/status").json()
        discovered = st.get("enumerate", {}).get("discovered", 0)
        if discovered > 0 and (st["enumerate"].get("done") or discovered >= 5):
            break
    assert discovered > 0, f"Enumerate discovered=0 after 25s"


# --- Add novel + crawl ---
@pytest.fixture(scope="module")
def novel_id(s):
    r = s.post(f"{API}/novels/add", json={"url": TEST_NOVEL_URL})
    assert r.status_code == 200
    d = r.json()
    assert "id" in d
    return d["id"]


def test_novel_added_and_listed(s, novel_id):
    r = s.get(f"{API}/novels?limit=100")
    assert r.status_code == 200
    assert any(n["id"] == novel_id for n in r.json()["items"])


def test_novel_get(s, novel_id):
    r = s.get(f"{API}/novels/{novel_id}")
    assert r.status_code == 200
    n = r.json()
    assert n["id"] == novel_id
    assert "chapter_status" in n


def test_novel_crawl_progress(s, novel_id):
    # Ensure running
    s.post(f"{API}/crawl/start")
    done = 0
    total = 0
    for _ in range(90):  # up to 90s
        time.sleep(1)
        r = s.get(f"{API}/novels/{novel_id}")
        n = r.json()
        total = n.get("total_chapters", 0)
        done = n.get("crawled_chapters", 0)
        if done >= 5:
            break
    assert total > 0, "total_chapters not discovered"
    assert done >= 5, f"Only {done}/{total} chapters done after 90s (partial expected but need >=5)"


def test_chapters_list_and_done_content(s, novel_id):
    r = s.get(f"{API}/novels/{novel_id}/chapters?limit=100&status=done")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1, "no done chapters found"
    ch_id = items[0]["id"]
    r = s.get(f"{API}/chapters/{ch_id}")
    assert r.status_code == 200
    ch = r.json()
    assert ch["status"] == "done"
    body = ch.get("body")
    assert isinstance(body, list) and len(body) > 0
    assert ch.get("word_count", 0) > 0
    # verify contains CJK
    joined = "\n".join(body)
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in joined)
    assert has_cjk, "Chapter body has no Chinese characters"


def test_export_txt_and_json(s, novel_id):
    r = s.get(f"{API}/novels/{novel_id}/export?fmt=txt")
    assert r.status_code == 200
    assert len(r.content) > 100
    assert any("\u4e00" <= c <= "\u9fff" for c in r.text[:5000])

    r = s.get(f"{API}/novels/{novel_id}/export?fmt=json")
    assert r.status_code == 200
    j = r.json()
    assert "chapters" in j and len(j["chapters"]) >= 1
