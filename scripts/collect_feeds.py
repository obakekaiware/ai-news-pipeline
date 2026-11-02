"""①収集（機械取得パート）

config/sources.json のうち method が feed / hf_daily_papers / hn_algolia のソースを取得し、
過去 window_hours 時間の記事を data/raw/YYYY-MM-DD.json に保存する。
method が claude のソースはここでは扱わない（prompts/01_collect.md で Claude が取得する）。

標準ライブラリのみ使用。1つのソースが失敗しても他のソースの取得は続ける。

使い方: python scripts/collect_feeds.py [--date YYYY-MM-DD]
"""

import argparse
import gzip
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
JST = timezone(timedelta(hours=9))
USER_AGENT = "Mozilla/5.0 (ai-news-pipeline)"
SUMMARY_MAX = 300

ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url: str, retries: int = 1) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                body = res.read()
            # 要求していなくても gzip 圧縮で返すサーバーがある（Google DeepMind 等）。urllib は自動展開しないため自前で展開する
            if body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            # 一時的に空や HTML のエラーページが返ることがあるため、XML/JSON らしくなければ再試行
            if body.lstrip()[:1] in (b"<", b"{", b"["):
                return body
            raise ValueError(f"unexpected response: {body[:50]!r}")
        except Exception:
            if attempt == retries:
                raise
            time.sleep(3)


def parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)  # RFC 822（RSS）
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))  # ISO 8601（Atom / API）
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:SUMMARY_MAX]


def item(source: dict, title: str, url: str, published: datetime | None, summary: str = "", **extra) -> dict:
    return {
        "source": source["name"],
        "category": source["category"],
        "title": clean(title),
        "url": url.strip(),
        "published": published.astimezone(JST).isoformat() if published else None,
        "summary": clean(summary),
        **extra,
    }


def collect_feed(source: dict, since: datetime) -> list[dict]:
    """RSS 2.0 / Atom の両方に対応"""
    root = ET.fromstring(fetch(source["url"]))
    results = []
    for node in root.iter("item"):  # RSS 2.0
        results.append(item(
            source,
            node.findtext("title"),
            node.findtext("link") or "",
            parse_date(node.findtext("pubDate") or node.findtext("{http://purl.org/dc/elements/1.1/}date")),
            node.findtext("description") or "",
        ))
    for node in root.iter(f"{ATOM}entry"):  # Atom
        # Element は子要素が無いと偽になるため `or` で繋がず None 判定する
        link = node.find(f"{ATOM}link[@rel='alternate']")
        if link is None:
            link = node.find(f"{ATOM}link")
        results.append(item(
            source,
            node.findtext(f"{ATOM}title"),
            link.get("href", "") if link is not None else "",
            parse_date(node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated")),
            node.findtext(f"{ATOM}summary") or node.findtext(f"{ATOM}content") or "",
        ))
    if source.get("ranking"):
        return results  # ランキング系は「今の人気」なので期間で絞らない
    return [r for r in results if r["published"] and datetime.fromisoformat(r["published"]) >= since]


def collect_hf_daily_papers(source: dict, since: datetime) -> list[dict]:
    # submittedOnDailyAt は日付単位なので、since の日付以降を対象にする
    since_date = since.astimezone(timezone.utc).date()
    results = []
    for entry in json.loads(fetch(source["url"])):
        paper = entry["paper"]
        submitted = parse_date(paper.get("submittedOnDailyAt"))
        if not submitted or submitted.date() < since_date:
            continue
        results.append(item(
            source,
            paper["title"],
            f"https://huggingface.co/papers/{paper['id']}",
            submitted,
            paper.get("summary", ""),
            upvotes=paper.get("upvotes", 0),
            arxiv_url=f"https://arxiv.org/abs/{paper['id']}",
        ))
    return sorted(results, key=lambda r: r["upvotes"], reverse=True)


def collect_hn_algolia(source: dict, since: datetime) -> list[dict]:
    # 期間内でポイントの高いストーリーを全件取得し、AI関連かどうかの判断は Claude に任せる
    params = urllib.parse.urlencode({
        "tags": "story",
        "numericFilters": f"created_at_i>{int(since.timestamp())},points>={source.get('min_points', 100)}",
        "hitsPerPage": 100,
    })
    data = json.loads(fetch(f"{source['url']}?{params}"))
    results = []
    for hit in data["hits"]:
        hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        results.append(item(
            source,
            hit["title"],
            hit.get("url") or hn_url,
            parse_date(hit["created_at"]),
            points=hit.get("points", 0),
            comments=hit.get("num_comments", 0),
            hn_url=hn_url,
        ))
    return sorted(results, key=lambda r: r["points"], reverse=True)


COLLECTORS = {
    "feed": collect_feed,
    "hf_daily_papers": collect_hf_daily_papers,
    "hn_algolia": collect_hn_algolia,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=config["window_hours"])

    items, errors, skipped = [], [], []
    for source in config["sources"]:
        collector = COLLECTORS.get(source["method"])
        if collector is None:
            skipped.append(source["name"])
            continue
        try:
            got = collector(source, since)
            if "max_items" in source:
                got = got[: source["max_items"]]
            items.extend(got)
            print(f"[OK]   {source['name']}: {len(got)} 件")
        except Exception as e:  # 1ソースの失敗で全体を止めない
            errors.append({"source": source["name"], "error": f"{type(e).__name__}: {e}"})
            print(f"[FAIL] {source['name']}: {e}", file=sys.stderr)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{args.date}.json"
    out.write_text(json.dumps({
        "date": args.date,
        "collected_at": now.astimezone(JST).isoformat(),
        "since": since.astimezone(JST).isoformat(),
        "items": items,
        "errors": errors,
        "skipped_for_claude": skipped,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=> {out}（{len(items)} 件, 失敗 {len(errors)} ソース）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
