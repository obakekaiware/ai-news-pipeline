"""①収集（統合パート）

data/raw/YYYY-MM-DD.json（スクリプト取得）と data/raw/YYYY-MM-DD_claude.json（Claude 取得）をまとめ、
URL の重複を除いて data/candidates/YYYY-MM-DD.json に保存する。

使い方: python scripts/merge_candidates.py [--date YYYY-MM-DD]
"""

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "candidates"
JST = timezone(timedelta(hours=9))

SIGNAL_KEYS = ("points", "comments", "upvotes", "stars_today")
BASE_KEYS = ("source", "category", "title", "url", "published", "summary")


def normalize_url(url: str) -> str:
    """重複判定用: スキーム・末尾の / ・utm_* 等の追跡クエリ・# 以降を無視する"""
    p = urllib.parse.urlsplit(url.strip())
    query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.startswith("utm_") and k not in ("ref", "source")]
    return urllib.parse.urlunsplit(("", p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), urllib.parse.urlencode(query), ""))


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    raw = load(RAW_DIR / f"{args.date}.json")
    if not raw:
        print(f"data/raw/{args.date}.json がありません", file=sys.stderr)
        return 1
    claude = load(RAW_DIR / f"{args.date}_claude.json")
    if not claude:
        print(f"[警告] data/raw/{args.date}_claude.json がありません。スクリプト取得分のみで続行します", file=sys.stderr)

    notes = [f"{e['source']}: {e['error']}" for e in raw.get("errors", [])]
    notes += claude.get("notes", [])

    items, seen = [], set()
    for src in raw.get("items", []) + claude.get("items", []):
        key = normalize_url(src.get("url", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        item = {"id": len(items) + 1, **{k: src.get(k) for k in BASE_KEYS}}
        item["summary"] = item["summary"] or ""
        item["signals"] = {k: src[k] for k in SIGNAL_KEYS if src.get(k) is not None}
        item.update({k: v for k, v in src.items() if k not in BASE_KEYS and k not in SIGNAL_KEYS})
        items.append(item)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.date}.json"
    out.write_text(json.dumps({
        "date": args.date,
        "since": raw.get("since"),
        "count": len(items),
        "items": items,
        "notes": notes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    n_raw, n_claude = len(raw.get("items", [])), len(claude.get("items", []))
    print(f"=> {out}（候補 {len(items)} 件 = スクリプト {n_raw} + Claude {n_claude} − 重複 {n_raw + n_claude - len(items)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
