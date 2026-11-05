"""محاسبه‌ی نمره و رتبه و ساخت فایل‌های عمومی سایت.

خروجی‌ها:
  docs/data/scores.json   داده‌ی عمومی سایت
  review/queue.js         صف بازبینی برای صفحه‌ی review/index.html (محلی)

اجرا:  python scripts/build_scores.py
"""
import argparse
import json
from collections import defaultdict

from common import (CONFIG, PUBLIC, REVIEW, STATE, load_json, now_utc, parse_iso,
                    save_json, to_iso)


def build(include_mock=False):
    settings = load_json(CONFIG / "settings.json", {})
    scfg = settings.get("scoring", {})
    people = load_json(CONFIG / "people.json", [])
    rubric = load_json(CONFIG / "rubric.json", {})
    overrides = load_json(CONFIG / "overrides.json", {})
    analyses = load_json(STATE / "analyses.json", {})

    now = now_utc()
    half_life = float(scfg.get("half_life_days", 90))
    min_items = int(scfg.get("min_items", 3))
    count_low = bool(scfg.get("count_low_confidence", False))
    max_shown = int(scfg.get("max_items_shown", 60))
    crit_by_id = {c["id"]: c for c in rubric["criteria"]}

    per_person = defaultdict(list)
    counts = defaultdict(int)
    mock_used = False
    review_rows = []

    for a in analyses.values():
        if a["provider"] == "mock":
            if not include_mock:
                continue
            mock_used = True
        if not a.get("relevant"):
            continue
        ov = overrides.get(a["id"], {})
        base_status = "pending" if a.get("needs_review") else "auto"
        if ov.get("status") == "rejected":
            status = "rejected"
        elif ov.get("status") == "approved":
            status = "approved"
        else:
            status = base_status
        counts[status] += 1

        scores = {}
        for cid, c in a["criteria"].items():
            if cid not in crit_by_id:
                continue
            s = ov.get("scores", {}).get(cid, c["score"])
            scores[cid] = {"score": s, "quote": c["quote"], "reason": c["reason"],
                           "quote_verified": c.get("quote_verified", False)}
        if not scores:
            continue

        pub = parse_iso(a["published"]) or now
        age_days = max(0.0, (now - pub).total_seconds() / 86400)
        recency = 0.5 ** (age_days / half_life)
        conf_w = 1.0 if status == "approved" else float(a.get("confidence", 0.5))
        counted = status in ("approved", "auto") or (status == "pending" and count_low)
        if status == "rejected":
            counted = False

        row = {
            "id": a["id"], "date": a["published"], "source": a["source"], "title": a["title"],
            "url": a["url"], "kind": a["kind"], "summary": a["summary"],
            "criteria": scores, "confidence": a["confidence"], "status": status,
            "note": ov.get("note", ""),
            "_weight": conf_w * recency, "_counted": counted, "_pub": pub,
        }
        if status != "rejected":
            per_person[a["person_id"]].append(row)
        review_rows.append({**{k: v for k, v in row.items() if not k.startswith("_")},
                            "person_id": a["person_id"], "provider": a["provider"],
                            "base_status": base_status})

    out_people = []
    for p in people:
        rows = per_person.get(p["id"], [])
        counted = [r for r in rows if r["_counted"]]
        sums, wsum, n = defaultdict(float), defaultdict(float), defaultdict(int)
        for r in counted:
            for cid, c in r["criteria"].items():
                sums[cid] += c["score"] * r["_weight"]
                wsum[cid] += r["_weight"]
                n[cid] += 1
        crit_out = {cid: {"avg": round(sums[cid] / wsum[cid], 2), "n": n[cid]}
                    for cid in sums if wsum[cid] > 0}
        tw = sum(crit_by_id[c]["weight"] for c in crit_out)
        overall = (round(sum(crit_out[c]["avg"] * crit_by_id[c]["weight"] for c in crit_out) / tw, 2)
                   if tw else None)

        months = defaultdict(list)
        for r in counted:
            vals = [c["score"] for c in r["criteria"].values()]
            months[r["_pub"].strftime("%Y-%m")].append(sum(vals) / len(vals))
        trend = [{"month": m, "avg": round(sum(v) / len(v), 2), "n": len(v)}
                 for m, v in sorted(months.items())][-12:]

        shown = sorted([r for r in rows if r["status"] != "pending"],
                       key=lambda r: r["_pub"], reverse=True)[:max_shown]
        out_people.append({
            "id": p["id"], "name": p["name"], "title": p.get("title", ""),
            "twitter": p.get("twitter", ""), "overall": overall, "criteria": crit_out,
            "counted_items": len(counted),
            "pending_items": sum(1 for r in rows if r["status"] == "pending"),
            "eligible": len(counted) >= min_items and overall is not None,
            "trend": trend,
            "items": [{k: v for k, v in r.items() if not k.startswith("_")} for r in shown],
        })

    eligible = [p for p in out_people if p["eligible"]]
    for p in out_people:
        p["rank"] = (1 + sum(1 for q in eligible if round(q["overall"], 1) > round(p["overall"], 1))
                     if p["eligible"] else None)
    out_people.sort(key=lambda p: (p["rank"] is None, p["rank"] or 0, p["name"]))

    public_rubric = {
        "template": bool(rubric.get("is_template")),
        "scale_note": rubric.get("scale_note", ""),
        "principles": rubric.get("principles", []),
        "criteria": [{k: c.get(k) for k in ("id", "title", "weight", "description", "anchors", "applies_to")}
                     for c in rubric["criteria"]],
    }
    data = {
        "meta": {
            "generated_at": to_iso(now),
            "site": settings.get("site", {}),
            "demo": mock_used,
            "counts": {"approved": counts["approved"], "auto": counts["auto"],
                       "pending": counts["pending"]},
            "method": {"half_life_days": half_life, "min_items": min_items,
                       "min_confidence": settings.get("analyze", {}).get("min_confidence", 0.6),
                       "count_low_confidence": count_low},
        },
        "rubric": public_rubric,
        "people": out_people,
    }
    save_json(PUBLIC / "scores.json", data)

    # صف بازبینی برای ویراستار (فایل محلی، نه بخشی از سایت عمومی)
    order = {"pending": 0, "auto": 1, "approved": 2, "rejected": 3}
    review_rows.sort(key=lambda r: (order[r["status"]], r["date"]), reverse=False)
    queue = {
        "generated_at": to_iso(now),
        "people": {p["id"]: p["name"] for p in people},
        "criteria": {c["id"]: c["title"] for c in rubric["criteria"]},
        "items": review_rows[:300],
        "overrides": overrides,
    }
    REVIEW.mkdir(parents=True, exist_ok=True)
    (REVIEW / "queue.js").write_text(
        "window.REVIEW_DATA = " + json.dumps(queue, ensure_ascii=False) + ";\n", encoding="utf-8")

    ranked = [p for p in out_people if p["rank"]]
    print(f"افراد رتبه‌دار: {len(ranked)} از {len(out_people)} | "
          f"تأییدشده {counts['approved']}، خودکار {counts['auto']}، در انتظار بازبینی {counts['pending']}")
    for p in ranked:
        print(f"  {p['rank']}. {p['name']}: {p['overall']} ({p['counted_items']} مورد)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-mock", action="store_true", help="فقط برای تست")
    build(ap.parse_args().include_mock)
