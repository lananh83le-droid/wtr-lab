"""Low-level async client for wtr-lab.com (reverse-engineered public API)."""
import base64
import json
import re
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE = "https://wtr-lab.com"
KEY = b"IJAFUUxjM25hyzL2AZrn0wl7cESED6Ru"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"}


def decrypt_body(encrypted):
    """Decrypt AES-GCM chapter body. Returns list[str] (arr:) or str (str:)."""
    if isinstance(encrypted, list):
        return encrypted
    if not isinstance(encrypted, str):
        raise ValueError("Unknown chapter content type")
    is_array = False
    if encrypted.startswith("arr:"):
        is_array = True
        encrypted = encrypted[4:]
    elif encrypted.startswith("str:"):
        encrypted = encrypted[4:]
    else:
        raise ValueError("Unknown chapter content format")
    parts = encrypted.split(":")
    if len(parts) != 3:
        raise ValueError("Invalid encrypted data format")
    s, n, a = parts
    iv = base64.b64decode(s)
    n_bytes = base64.b64decode(n)
    a_bytes = base64.b64decode(a)
    plaintext = AESGCM(KEY).decrypt(iv, a_bytes + n_bytes, None).decode("utf-8")
    return json.loads(plaintext) if is_array else plaintext


def make_client(proxy=None):
    return httpx.AsyncClient(headers=HEADERS, timeout=60.0, proxy=proxy, follow_redirects=True)


async def get_build_id(proxy=None):
    async with make_client(proxy) as c:
        r = await c.get(f"{BASE}/en")
        m = re.search(r'"buildId":"([^"]+)"', r.text)
        if not m:
            raise RuntimeError("Could not locate buildId on wtr-lab.com")
        return m.group(1)


async def list_novels(build_id, page, proxy=None):
    """Return (series_list, total_count) for a novel-list page (10 per page)."""
    url = f"{BASE}/_next/data/{build_id}/en/novel-list.json?page={page}"
    async with make_client(proxy) as c:
        r = await c.get(url)
        r.raise_for_status()
        pp = r.json()["pageProps"]
        return pp.get("series", []), int(pp.get("count", 0))


async def get_toc(source_id, proxy=None):
    """Return full chapter list for a novel. Each item: order, id, serie_id, name(zh), title(en)."""
    async with make_client(proxy) as c:
        r = await c.get(f"{BASE}/api/chapters/{source_id}")
        r.raise_for_status()
        return r.json().get("chapters", [])


async def get_chapter(raw_id, chapter_no, chapter_id, proxy=None):
    """Fetch and decrypt one chapter. Returns dict {title, lines}. Raw Chinese via translate='web'."""
    payload = json.dumps({
        "translate": "web",
        "language": "en",
        "raw_id": raw_id,
        "chapter_no": chapter_no,
        "retry": False,
        "force_retry": False,
        "chapter_id": chapter_id,
    })
    async with make_client(proxy) as c:
        r = await c.post(f"{BASE}/api/reader/get", data=payload)
        if r.status_code in (401, 403, 429, 500, 502, 503, 520, 521, 522, 524):
            raise RuntimeError(f"rate-limit / blocked (HTTP {r.status_code})")
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(data.get("error") or data.get("message") or "reader/get failed")
        inner = data["data"]["data"]
        lines = decrypt_body(inner["body"])
        if isinstance(lines, str):
            lines = [x for x in lines.split("\n") if x.strip()]
        return {"title": inner.get("title", ""), "lines": lines}
