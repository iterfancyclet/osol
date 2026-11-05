"""خواندن RSS خبرگزاری‌ها، پیدا کردن اسم شخصیت‌ها و فیلتر موضوعی.

اجرا:  python scripts/fetch_news.py
"""
import argparse
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from common import (CONFIG, ROOT, STATE, has_keyword, load_json, match_people, now_utc,
                    person_matchers, parse_iso, save_json, stable_id, strip_html, to_iso)

UA = "SiasatRankBot/1.0 (news analysis project)"
MAX_BYTES = 5_000_000


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        dt = parse_iso(s)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed(data):
    if b"<!ENTITY" in data:  # جلوگیری از حمله‌ی entity expansion
        raise ValueError("feed contains entity declarations")
    root = ET.fromstring(data)
    entries = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        d = {}
        for ch in el:
            k = local(ch.tag)
            text = (ch.text or "").strip()
            if k == "link":
                href = ch.get("href")
                if href and (ch.get("rel") in (None, "alternate") or "link" not in d):
                    d["link"] = href
                elif text and "link" not in d:
                    d["link"] = text
            elif k == "title":
                d["title"] = strip_html(text)
            elif k in ("description", "summary", "encoded", "content"):
                # بلندترین متن را نگه می‌داریم
                body = strip_html(text)
                if len(body) > len(d.get("body", "")):
                    d["body"] = body
            elif k in ("pubDate", "published", "updated", "date"):
                d.setdefault("date", text)
            elif k in ("guid", "id"):
                d.setdefault("guid", text)
        if d.get("title") or d.get("body"):
            entries.append(d)
    return entries


def fetch_url(url, allow_file=False):
    if url.startswith("file://") and not allow_file:
        raise ValueError("file:// is only allowed with --allow-file")
    if url.startswith("file://"):
        p = Path(url[7:])
        return (p if p.is_absolute() else ROOT / p).read_bytes()[:MAX_BYTES]
    if not url.startswith(("http://", "https://")):
        raise ValueError("unsupported URL scheme")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read(MAX_BYTES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default=str(CONFIG / "feeds.json"))
    ap.add_argument("--allow-file", action="store_true", help="برای تست محلی")
    args = ap.parse_args()

    settings = load_json(CONFIG / "settings.json", {})
    fcfg = settings.get("fetch", {})
    people = load_json(CONFIG / "people.json", [])
    feeds = [f for f in load_json(args.feeds, []) if f.get("enabled", True)]
    matchers = person_matchers(people)
    keywords = fcfg.get("topic_keywords", [])
    now = now_utc()
    min_date = now - timedelta(days=fcfg.get("max_age_days", 14))
    keep_date = now - timedelta(days=fcfg.get("keep_days", 400))

    news = load_json(STATE / "news.json", {})
    added = 0
    failed = 0

    for feed in feeds:
        try:
            entries = parse_feed(fetch_url(feed["url"], args.allow_file))
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[!] {feed.get('name', feed['url'])}: {type(e).__name__}: {e}")
            continue
        n_match = 0
        for e in entries:
            text = (e.get("title", "") + ". " + e.get("body", "")).strip()
            pub = parse_date(e.get("date")) or now
            if pub < min_date:
                continue
            people_ids = match_people(text, matchers)
            if not people_ids or not has_keyword(text, keywords):
                continue
            nid = stable_id(e.get("link") or e.get("guid") or text[:200])
            if nid in news:
                known = set(news[nid]["people"])
                news[nid]["people"] = sorted(known | set(people_ids))
                continue
            news[nid] = {
                "id": nid,
                "title": e.get("title", "")[:300],
                "text": text[:6000],
                "url": e.get("link", ""),
                "source": feed.get("name", feed.get("id", "")),
                "published": to_iso(pub),
                "people": sorted(people_ids),
                "fetched_at": to_iso(now),
            }
            added += 1
            n_match += 1
        print(f"[ok] {feed.get('name')}: {len(entries)} خبر، {n_match} مورد جدید مرتبط")

    # موارد دستی (مثلاً توییت‌هایی که خودتان کپی می‌کنید)
    for m in load_json(CONFIG / "manual_items.json", []):
        ids = m.get("people") or ([m["person_id"]] if m.get("person_id") else [])
        text = (m.get("text") or "").strip()
        if not ids or not text:
            continue
        pub = parse_date(m.get("date")) or now
        nid = stable_id(m.get("url") or text[:200])
        if nid in news:
            continue
        news[nid] = {
            "id": nid,
            "title": (m.get("title") or text[:80])[:300],
            "text": text[:6000],
            "url": m.get("url", ""),
            "source": m.get("source", "ورود دستی"),
            "published": to_iso(pub),
            "people": sorted(ids),
            "fetched_at": to_iso(now),
        }
        added += 1

    # حذف موارد خیلی قدیمی
    news = {k: v for k, v in news.items()
            if (parse_iso(v["published"]) or now) >= keep_date}
    save_json(STATE / "news.json", news)
    print(f"جمع: {len(news)} خبر ذخیره‌شده، {added} مورد جدید")

    if feeds and failed == len(feeds):
        print("همه‌ی منابع RSS خطا دادند.")
        sys.exit(1)


if __name__ == "__main__":
    main()
