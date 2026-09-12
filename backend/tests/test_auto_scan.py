"""Tests for the auto-scan / chapter_limit feature."""
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
def _restore_settings(s):
    # Snapshot the settings before running the module
    before = s.get(f"{API}/settings").json()
    yield
    # Restore per problem statement
    s.put(f"{API}/settings", json={
        "auto_scan_enabled": False,
        "chapter_limit": 0,
        "auto_scan_pages": 3,
        "auto_scan_interval_min": 60,
        "concurrency": before.get("concurrency", 3),
        "delay_ms": before.get("delay_ms", 300),
        "use_proxy": before.get("use_proxy", False),
    })


# --- Settings defaults / new fields ---
def test_settings_has_new_fields(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    d = r.json()
    for k in ("auto_scan_enabled", "auto_scan_interval_min", "auto_scan_pages", "chapter_limit"):
        assert k in d, f"missing settings key {k}"
    assert isinstance(d["auto_scan_enabled"], bool)
    assert isinstance(d["auto_scan_interval_min"], int)
    assert isinstance(d["auto_scan_pages"], int)
    assert isinstance(d["chapter_limit"], int)


def test_put_settings_persists_new_fields(s):
    r = s.put(f"{API}/settings", json={
        "auto_scan_enabled": True,
        "auto_scan_interval_min": 5,
        "auto_scan_pages": 1,
        "chapter_limit": 3,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["auto_scan_enabled"] is True
    assert d["auto_scan_interval_min"] == 5
    assert d["auto_scan_pages"] == 1
    assert d["chapter_limit"] == 3
    # Confirm persistence via GET
    d2 = s.get(f"{API}/settings").json()
    assert d2["auto_scan_enabled"] is True
    assert d2["chapter_limit"] == 3


# --- crawl/status auto_scan object ---
def test_crawl_status_auto_scan_shape(s):
    r = s.get(f"{API}/crawl/status")
    assert r.status_code == 200
    a = r.json().get("auto_scan")
    assert isinstance(a, dict)
    # required keys
    for k in ("running", "last_run", "next_run", "last_found", "total_found", "page", "pages"):
        assert k in a, f"missing auto_scan.{k}"
    # forbidden internal ts
    assert "next_run_ts" not in a


def test_next_run_populated_when_enabled(s):
    # ensure it's enabled
    s.put(f"{API}/settings", json={"auto_scan_enabled": True, "auto_scan_interval_min": 5})
    got_next = None
    for _ in range(24):  # up to ~24s
        time.sleep(1)
        a = s.get(f"{API}/crawl/status").json().get("auto_scan", {})
        if a.get("next_run"):
            got_next = a["next_run"]
            break
    assert got_next, "auto_scan.next_run did not populate within 24s while enabled"


# --- scan-new endpoint ---
def test_scan_new_starts_and_logs(s):
    # Trigger scan (pages=2 to increase odds of discovery per problem statement)
    r = s.post(f"{API}/crawl/scan-new", json={"pages": 2})
    assert r.status_code == 200, r.text
    assert r.json().get("started") is True

    # Wait for it to finish (up to 40s; each page fetch is a few seconds)
    finished = False
    last_run_after = None
    for _ in range(40):
        time.sleep(1)
        a = s.get(f"{API}/crawl/status").json().get("auto_scan", {})
        if a.get("running") is False and a.get("last_run"):
            finished = True
            last_run_after = a["last_run"]
            break
    assert finished, "scan-new did not complete within 40s"
    assert last_run_after

    # Log entry should mention "Quét truyện mới" (Vietnamese)
    logs = s.get(f"{API}/logs?limit=50").json()
    matched = [l for l in logs if "Quét truyện mới" in (l.get("message") or "")
                              or "quét truyện mới" in (l.get("message") or "").lower()
                              or "phát hiện" in (l.get("message") or "")]
    assert matched, f"No 'Quét truyện mới ...phát hiện' log found. Recent: {[l.get('message') for l in logs[:10]]}"


def test_scan_new_conflict_when_running(s):
    """Best-effort: try to hit the 400 conflict path (may not always trigger)."""
    r1 = s.post(f"{API}/crawl/scan-new", json={"pages": 2})
    # first call may return 200 or 400 depending on state
    assert r1.status_code in (200, 400)
    # Immediately retry — hopefully still running
    r2 = s.post(f"{API}/crawl/scan-new", json={"pages": 2})
    if r2.status_code == 400:
        assert "Đang quét truyện mới" in r2.text or "quét" in r2.text.lower()
    # Wait for it to finish before other tests
    for _ in range(40):
        time.sleep(1)
        a = s.get(f"{API}/crawl/status").json().get("auto_scan", {})
        if a.get("running") is False:
            break


# --- Chapter limit persistence on novels ---
def test_chapter_limit_reflected_on_novel(s):
    """Regression: existing novel with chapter_limit set has total_chapters==limit and site_chapters>=total."""
    r = s.get(f"{API}/novels?limit=100")
    assert r.status_code == 200
    items = r.json()["items"]
    # Look for any novel with chapter_limit>0 and site_chapters set
    candidates = [n for n in items if (n.get("chapter_limit") or 0) > 0 and n.get("site_chapters")]
    if not candidates:
        pytest.skip("No novel with chapter_limit>0 & site_chapters yet — worker cooldown likely")
    for n in candidates:
        assert n["total_chapters"] == n["chapter_limit"], \
            f"novel {n.get('slug')} total_chapters {n['total_chapters']} != chapter_limit {n['chapter_limit']}"
        assert n["site_chapters"] >= n["total_chapters"], \
            f"site_chapters {n['site_chapters']} < total_chapters {n['total_chapters']}"


# --- Regression on existing endpoints ---
def test_regression_existing_endpoints(s):
    assert s.get(f"{API}/stats").status_code == 200
    assert s.get(f"{API}/novels?limit=5").status_code == 200
    assert s.post(f"{API}/crawl/start").status_code == 200
    assert s.post(f"{API}/crawl/pause").status_code == 200
