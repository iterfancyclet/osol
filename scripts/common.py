"""توابع مشترک. فقط کتابخانه‌ی استاندارد پایتون."""
import hashlib
import html
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
STATE = Path(os.environ.get("SIASATRANK_STATE", ROOT / "data"))
PUBLIC = Path(os.environ.get("SIASATRANK_PUBLIC", ROOT / "docs" / "data"))
REVIEW = Path(os.environ.get("SIASATRANK_REVIEW", ROOT / "review"))


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    """نوشتن اتمی تا در صورت قطع شدن اجرا، فایل نصفه نماند."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def now_utc():
    return datetime.now(timezone.utc)


def to_iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def stable_id(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


_CHAR_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا"})
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_MARKS = re.compile("[ً-ٰٟـ]")


def normalize(text):
    """یکسان‌سازی متن فارسی برای جست‌وجو و مقایسه."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.translate(_CHAR_MAP).translate(_DIGITS)
    text = _MARKS.sub("", text)
    text = text.replace("‌", " ").replace("‏", " ").replace("‎", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(s or ""), flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def name_regex(name):
    words = [re.escape(w) for w in normalize(name).split() if w]
    if not words:
        return None
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)")


def person_matchers(people):
    """برای هر شخص، الگوهای نام و نام‌های دیگر را می‌سازد."""
    out = []
    for p in people:
        pats = [name_regex(n) for n in [p["name"]] + list(p.get("aliases", []))]
        out.append((p["id"], [x for x in pats if x]))
    return out


def match_people(text, matchers):
    norm = normalize(text)
    return [pid for pid, pats in matchers if any(p.search(norm) for p in pats)]


def has_keyword(text, keywords):
    norm = normalize(text)
    return any(normalize(k) in norm for k in keywords if k)
