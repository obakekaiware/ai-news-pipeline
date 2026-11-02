"""③要約（書き込みパート）

data/summaries/YYYY-MM-DD.json を Markdown に整形し、AI_NEWS.md の先頭（タイトル行の直下）に追記する。

- 既存の内容は変更・削除しない。
- AI_NEWS.md に既に載っている URL のニュースはスキップする（再実行しても重複しない）。
- 同じ日付の見出しが既にあれば、その見出しの末尾に追加する。
- 日付は 記事の公開日（要約の published）→ 収集時の日付（選定の published）→ 不明 の順で決める。
  収集時の日付が記事の公開日でないソース（HN の投稿日など）は、何の日付かを添える。

使い方: python scripts/update_news.py [--date YYYY-MM-DD] [--news PATH]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_DIR = ROOT / "data" / "summaries"
SELECTED_DIR = ROOT / "data" / "selected"
JST = timezone(timedelta(hours=9))
HEADER = "# AI NEWS\n\nAIエンジニア目線で選んだ毎日のAIニュース（新しい順）\n"

# 収集時の published が「記事の公開日」ではないソースと、その日付の意味
COLLECTED_DATE_LABELS = {
    "Hacker News": "HN投稿日",
    "Hugging Face Daily Papers": "Daily Papers掲載日",
}


def load_selected(date: str) -> dict:
    """URL → 選定時の候補（収集時の published を持つ）"""
    path = SELECTED_DIR / f"{date}.json"
    if not path.exists():
        return {}
    return {i["url"]: i for i in json.loads(path.read_text(encoding="utf-8"))["items"]}


def resolve_date(item: dict, selected: dict) -> str:
    if item.get("published"):
        return item["published"][:10]
    picked = selected.get(item["url"], {})
    if picked.get("published"):
        label = COLLECTED_DATE_LABELS.get(picked.get("source"))
        day = picked["published"][:10]
        return f"{day}（{label}）" if label else day
    return "不明"


def render(item: dict, selected: dict) -> str:
    if len(item["summary"]) != 3:
        raise ValueError(f"要約が3行ではありません: {item['url']}")
    lines = [
        f"### [{item['title']}]({item['url']})",
        f"- **日付**: {resolve_date(item, selected)}",
        f"- **ソース**: {item['source']}",
        "- **要約**:",
        *[f"  {i}. {s}" for i, s in enumerate(item["summary"], 1)],
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    parser.add_argument("--news", type=Path, default=ROOT / "AI_NEWS.md")
    args = parser.parse_args()

    data = json.loads((SUMMARY_DIR / f"{args.date}.json").read_text(encoding="utf-8"))
    text = args.news.read_text(encoding="utf-8") if args.news.exists() else HEADER
    if not text.startswith("# "):
        text = HEADER + "\n" + text

    existing_urls = set(re.findall(r"^### \[.*\]\((.+)\)$", text, flags=re.MULTILINE))
    new_items = [i for i in data["items"] if i["url"] not in existing_urls]
    skipped = len(data["items"]) - len(new_items)
    if not new_items:
        print(f"[update_news] {args.date}: 追加 0 件（スキップ {skipped} 件）")
        return 0

    selected = load_selected(args.date)
    block = "\n".join(render(i, selected) for i in new_items)
    heading = f"## {args.date}\n"
    pos = text.find(heading)
    if pos >= 0:
        # 同じ日付の見出しがある → 次の日付見出しの直前（無ければ末尾）に追加
        nxt = text.find("\n## ", pos + len(heading))
        insert_at = len(text) if nxt < 0 else nxt + 1
        text = text[:insert_at].rstrip("\n") + "\n\n" + block + "\n" + text[insert_at:]
    else:
        # 新しい日付 → 最初の日付見出しの直前（＝ヘッダー直下）に追加
        first = re.search(r"^## ", text, flags=re.MULTILINE)
        insert_at = first.start() if first else len(text)
        head = text[:insert_at].rstrip("\n") + "\n\n"
        text = head + heading + "\n" + block + "\n" + text[insert_at:]

    args.news.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    print(f"[update_news] {args.date}: 追加 {len(new_items)} 件（スキップ {skipped} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
