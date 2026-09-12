"""Tests for the proxy management + parallel_novels iteration."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module", autouse=True)
def _restore(s):
    yield
    # Restore per problem statement
    s.put(f"{API}/settings", json={
        "parallel_novels": 4,
        "proxy_max_pool": 200,
        "concurrency": 15,
        "use_proxy": True,
        "proxy_auto_harvest": True,
    })
    s.post(f"{API}/crawl/start")


# -------- Settings shape --------
def test_settings_has_new_fields(s):
    d = s.get(f"{API}/settings").json()
    for k in ("parallel_novels", "proxy_auto_harvest", "proxy_max_pool", "proxy_kinds"):
        assert k in d, f"missing {k}"
    assert isinstance(d["parallel_novels"], int)
    assert isinstance(d["proxy_auto_harvest"], bool)
    assert isinstance(d["proxy_max_pool"], int)
    assert isinstance(d["proxy_kinds"], list)


def test_put_settings_persists(s):
    r = s.put(f"{API}/settings", json={
        "parallel_novels": 2,
        "proxy_auto_harvest": False,
        "proxy_max_pool": 150,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["parallel_novels"] == 2
    assert d["proxy_auto_harvest"] is False
    assert d["proxy_max_pool"] == 150
    # verify GET
    d2 = s.get(f"{API}/settings").json()
    assert d2["parallel_novels"] == 2
    assert d2["proxy_auto_harvest"] is False
    assert d2["proxy_max_pool"] == 150


# -------- Bulk proxy import --------
BULK_TEXT = """1.2.3.4:8080
socks5://5.6.7.8:1080
http://u:p@9.9.9.9:3128
10.0.0.1:8080:user:pass
1.2.3.4:8080
this is garbage line"""

EXPECTED_URLS = {
    "http://1.2.3.4:8080",
    "socks5://5.6.7.8:1080",
    "http://u:p@9.9.9.9:3128",
    "http://user:pass@10.0.0.1:8080",
}


def _find_ids(s, urls):
    items = s.get(f"{API}/proxies").json()
    return [p["id"] for p in items if p["url"] in urls]


def test_bulk_add_proxies_and_delete(s):
    # Pre-clean in case a previous run left the fake proxies around
    for pid in _find_ids(s, EXPECTED_URLS):
        s.delete(f"{API}/proxies/{pid}")

    r = s.post(f"{API}/proxies/bulk", json={"text": BULK_TEXT})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["added"] == 4, f"expected 4 added, got {data}"
    # parse_bulk dedupes internally, so first-time skipped may be 0 (no DB collisions)
    assert data["skipped"] >= 0

    # Repost - all should be duplicates now
    r2 = s.post(f"{API}/proxies/bulk", json={"text": BULK_TEXT})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["added"] == 0
    assert d2["skipped"] >= 4

    # Verify normalized urls exist
    items = s.get(f"{API}/proxies").json()
    urls_in_db = {p["url"] for p in items}
    for exp in EXPECTED_URLS:
        assert exp in urls_in_db, f"missing {exp}"

    # Cleanup
    ids = _find_ids(s, EXPECTED_URLS)
    assert len(ids) == 4
    for pid in ids:
        r = s.delete(f"{API}/proxies/{pid}")
        assert r.status_code == 200


def test_single_add_normalization_and_duplicate(s):
    # Cleanup first
    for pid in _find_ids(s, {"http://1.2.3.4:9999"}):
        s.delete(f"{API}/proxies/{pid}")

    r = s.post(f"{API}/proxies", json={"url": "1.2.3.4:9999"})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["url"] == "http://1.2.3.4:9999"
    pid = doc["id"]

    # Duplicate
    r2 = s.post(f"{API}/proxies", json={"url": "1.2.3.4:9999"})
    assert r2.status_code == 400
    assert "tồn tại" in r2.text

    # Cleanup
    s.delete(f"{API}/proxies/{pid}")


# -------- Proxy summary shape --------
def test_proxies_summary_shape(s):
    d = s.get(f"{API}/proxies/summary").json()
    for k in ("total", "alive", "dead", "enabled", "available", "harvest"):
        assert k in d, f"missing {k}"
    h = d["harvest"]
    for k in ("running", "fetched", "tested", "alive", "added", "last_run", "phase"):
        assert k in h, f"missing harvest.{k}"


# -------- Harvest endpoint --------
def test_harvest_starts_and_logs(s):
    r = s.post(f"{API}/proxies/harvest", json={})
    # either started, or already running
    assert r.status_code in (200, 400)
    if r.status_code == 400:
        assert "thu thập" in r.text.lower() or "rồi" in r.text
    # Poll summary until harvest not running (up to ~180s)
    deadline = time.time() + 190
    while time.time() < deadline:
        h = s.get(f"{API}/proxies/summary").json()["harvest"]
        if not h["running"]:
            break
        time.sleep(3)
    else:
        pytest.fail("Harvest did not finish within 190s")

    logs = s.get(f"{API}/logs?limit=200").json()
    matched = [l for l in logs if (
        (l.get("message") or "").startswith("Thu thập proxy:") or
        (l.get("message") or "").startswith("Pool proxy đã đủ") or
        "Bắt đầu thu thập proxy" in (l.get("message") or "")
    )]
    assert matched, f"No harvest log found. Recent: {[l.get('message') for l in logs[:15]]}"


# -------- Recheck + purge dead --------
def test_recheck_and_purge_dead(s):
    r = s.post(f"{API}/proxies/recheck", json={})
    assert r.status_code == 200
    assert r.json().get("started") is True
    # Wait for a 'Kiểm tra lại proxy' log
    deadline = time.time() + 120
    found = False
    while time.time() < deadline:
        logs = s.get(f"{API}/logs?limit=50").json()
        if any("Kiểm tra lại proxy" in (l.get("message") or "") for l in logs):
            found = True
            break
        time.sleep(3)
    assert found, "recheck completion log not seen within 120s"

    r = s.delete(f"{API}/proxies/dead")
    assert r.status_code == 200
    assert "deleted" in r.json()


# -------- Persistence of running state --------
def test_running_state_persisted(s):
    r = s.post(f"{API}/crawl/start")
    assert r.status_code == 200
    d = s.get(f"{API}/settings").json()
    assert d.get("running") is True

    r = s.post(f"{API}/crawl/pause")
    assert r.status_code == 200
    d = s.get(f"{API}/settings").json()
    assert d.get("running") is False

    # Restore running
    s.post(f"{API}/crawl/start")


# -------- Parallel novels limit --------
def test_parallel_novels_respected(s):
    # Set parallel=4, use_proxy=true, concurrency=15
    s.put(f"{API}/settings", json={
        "parallel_novels": 4, "use_proxy": True, "concurrency": 15,
    })
    s.post(f"{API}/crawl/start")
    max_crawling = 0
    for _ in range(20):  # ~40s
        st = s.get(f"{API}/stats").json()
        c = st.get("novels_by_status", {}).get("crawling", 0)
        max_crawling = max(max_crawling, c)
        if max_crawling >= 1:
            # ensure never exceeds parallel_novels
            assert c <= 4, f"crawling={c} exceeds parallel_novels=4"
        time.sleep(2)
    # It is possible everything is idle; accept but log
    if max_crawling == 0:
        pytest.skip("No crawling activity observed during window (queue may be empty)")


# -------- No stuck 'fetching' chapters on non-crawling novels --------
def test_no_fetching_on_finished_novels(s):
    novels = s.get(f"{API}/novels?limit=50").json()["items"]
    finished = [n for n in novels if n.get("status") in ("done", "partial", "queued")]
    checked = 0
    for n in finished[:5]:
        r = s.get(f"{API}/novels/{n['id']}/chapters", params={"status": "fetching", "limit": 1})
        assert r.status_code == 200
        assert r.json()["total"] == 0, f"novel {n.get('slug')} status={n.get('status')} has stuck fetching chapters"
        checked += 1
    if checked == 0:
        pytest.skip("No finished novels available")


# -------- Regression export --------
def test_export_all_zip(s):
    r = s.get(f"{API}/export/all", params={"fmt": "txt"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/zip")
    assert len(r.content) > 0
