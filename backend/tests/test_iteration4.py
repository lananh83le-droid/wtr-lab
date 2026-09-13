"""Iteration 4: max-speed + full automation.
Covers: auto_queue_new setting, proxy harvest tiers/78 sources, event-loop responsiveness,
throughput, auto-queue log lines, proxy harvest endpoint, regression exports.
"""
import os
import time
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- Settings: auto_queue_new ----------
def test_settings_has_auto_queue_new(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    d = r.json()
    assert "auto_queue_new" in d, f"missing auto_queue_new; keys={list(d)}"
    assert isinstance(d["auto_queue_new"], bool)


def test_settings_toggle_auto_queue_new_persists(s):
    r = s.put(f"{API}/settings", json={"auto_queue_new": False})
    assert r.status_code == 200
    assert s.get(f"{API}/settings").json()["auto_queue_new"] is False
    # restore
    r = s.put(f"{API}/settings", json={"auto_queue_new": True})
    assert r.status_code == 200
    assert s.get(f"{API}/settings").json()["auto_queue_new"] is True


# ---------- Proxy summary ----------
def test_proxies_summary_harvest_shape(s):
    r = s.get(f"{API}/proxies/summary")
    assert r.status_code == 200
    d = r.json()
    assert "harvest" in d, d
    h = d["harvest"]
    for k in ("tier", "sources", "runs"):
        assert k in h, f"missing key {k} in harvest={h}"
    assert h["sources"] == 78, f"expected 78 sources, got {h['sources']}"
    alive = d.get("alive") or d.get("enabled_alive") or h.get("alive")
    # try multiple shape variants
    candidates = [d.get("alive"), h.get("alive"), d.get("total_alive")]
    alive_val = next((c for c in candidates if isinstance(c, int)), None)
    assert alive_val is not None, f"no alive count in {d}"
    assert alive_val > 100, f"expected alive > 100, got {alive_val}"


# ---------- Event-loop responsiveness ----------
def test_stats_responsive_under_load(s):
    slow = []
    for i in range(10):
        t0 = time.time()
        r = s.get(f"{API}/stats", timeout=5)
        dt = time.time() - t0
        assert r.status_code == 200
        if dt >= 3:
            slow.append((i, dt))
    assert not slow, f"slow GET /api/stats calls: {slow}"


# ---------- Throughput ----------
def test_throughput_or_no_work(s):
    st = s.get(f"{API}/stats").json()
    tp = st.get("throughput", 0)
    by_status = st.get("novels_by_status", {}) or {}
    has_work = (by_status.get("queued", 0) + by_status.get("crawling", 0)) > 0
    if has_work:
        assert tp > 20, f"throughput={tp} chapters/min but there is work: {by_status}"
    # cap on crawling
    parallel = s.get(f"{API}/settings").json().get("parallel_novels", 8)
    assert by_status.get("crawling", 0) <= parallel, by_status


# ---------- Auto-queue log line ----------
def test_auto_queue_log_line_appears(s):
    # Ensure crawler running
    s.post(f"{API}/crawl/start")
    deadline = time.time() + 100
    found = False
    while time.time() < deadline:
        logs = s.get(f"{API}/logs?limit=200").json()
        text = " | ".join(l.get("message", "") for l in logs)
        if ("Tự động đưa" in text) or ("Tự động xếp lại" in text):
            found = True
            break
        time.sleep(5)
    # If not found, only fail if there was pending work
    if not found:
        st = s.get(f"{API}/stats").json().get("novels_by_status", {})
        # There are ~5700 new novels — so it should trigger
        assert False, f"auto-queue log not seen in 100s; novels_by_status={st}"


# ---------- Proxy harvest endpoint ----------
def test_proxy_harvest_endpoint(s):
    r = s.post(f"{API}/proxies/harvest", json={})
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        assert r.json().get("started") is True
    else:
        assert "Đang thu thập" in r.text or "thu thập" in r.text.lower()
    # Check log line
    time.sleep(3)
    logs = s.get(f"{API}/logs?limit=200").json()
    text = " | ".join(l.get("message", "") for l in logs)
    assert ("Thu thập proxy tầng" in text) or ("Tầng" in text), f"no harvest tier log; sample={text[:400]}"


# ---------- Regression ----------
def test_novels_list(s):
    r = s.get(f"{API}/novels?limit=5")
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and len(d["items"]) <= 5


def test_done_novel_chapters_and_export(s):
    # find a done novel
    r = s.get(f"{API}/novels?limit=50&status=done")
    items = r.json().get("items", [])
    if not items:
        # try any list and filter
        items = [n for n in s.get(f"{API}/novels?limit=200").json().get("items", []) if n.get("status") == "done"]
    if not items:
        pytest.skip("no 'done' novel available to test")
    nid = items[0]["id"]
    r = s.get(f"{API}/novels/{nid}/chapters?limit=5&status=done")
    assert r.status_code == 200
    assert len(r.json().get("items", [])) >= 1
    # export
    r = s.get(f"{API}/novels/{nid}/export?fmt=txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "").lower()
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in r.text[:5000])
    assert has_cjk, "no Chinese content in export"


def test_pause_start_leaves_running(s):
    assert s.post(f"{API}/crawl/pause").status_code == 200
    time.sleep(1)
    r = s.post(f"{API}/crawl/start")
    assert r.status_code == 200
    assert s.get(f"{API}/crawl/status").json()["running"] is True
