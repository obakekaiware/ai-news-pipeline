# ③要約

あなたは AI ニュース収集パイプラインの「③要約」担当です。
②選定で選ばれたニュース（1〜3件）を読み、3行要約を作って JSON に保存する。
**`AI_NEWS.md` は直接編集しないこと**（書き込みは `scripts/update_news.py` が行う）。

## 入力

- 対象日 `DATE`: 指示で与えられた日付（YYYY-MM-DD）。与えられていなければ今日の日付（JST）。
- `data/selected/{DATE}.json`: ②選定の結果

## 手順

### 1. 記事を読む
`data/selected/{DATE}.json` の各ニュースについて、WebFetch で `url` の本文を読む。

- 論文（Hugging Face Daily Papers）は `arxiv_url` があればそちらの概要（Abstract）を読む。
- Hacker News は `url`（元記事）を読む。元記事が読めなければ `hn_url` の議論から事実を確認する。
- GitHub リポジトリは README を読む。
- 本文が取得できない場合は、候補の `summary` だけで要約し、`notes` に「本文取得失敗」と書く。**推測で内容を補わない。**

### 2. タイトルを決める
- 英語など日本語以外の記事: `日本語訳（原題）` の形にする。
  - 例: `Claude が新しい酵素系を発見（Claude discovers a novel enzyme system with CRISPR-like repeats）`
  - 日本語訳は直訳でなく、内容が一目で分かる自然な日本語にする（40字程度まで）。
- 日本語の記事: 元のタイトルをそのまま使う。

### 3. 3行要約を書く
次の構成を必ず守る。日本語、各行1文、60字程度まで。

| 行 | 内容 |
|----|------|
| 1行目 | **事実**: 何が起きたか（誰が・何を発表/公開したか） |
| 2行目 | **技術ポイント**: 何が新しいか、どう実現しているか |
| 3行目 | **AIエンジニアへの示唆**: 試す価値、実務への影響、注目すべき理由 |

- 記事に書かれていない数値・事実は書かない。
- 「〜と思われる」のような推測は3行目に限り、記事の内容から言える範囲で書く。
- 宣伝文句（「革命的」「画期的」等）は使わない。

### 4. 保存
`data/summaries/{DATE}.json` に以下の形式で保存する（UTF-8、既存ファイルがあれば上書き）。

```json
{
  "date": "2026-10-02",
  "items": [
    {
      "title": "Claude が新しい酵素系を発見（Claude discovers a novel enzyme system with CRISPR-like repeats）",
      "url": "https://www.anthropic.com/news/claude-discovers-novel-enzyme-system",
      "source": "Anthropic News",
      "published": "2026-09-23",
      "summary": [
        "1行目（事実）",
        "2行目（技術ポイント）",
        "3行目（AIエンジニアへの示唆）"
      ]
    }
  ],
  "notes": []
}
```

- `items` の並び順は②選定の順位どおりにする。
- `published` は **記事本文で確認できた公開日**（YYYY-MM-DD）。確認できなければ `null` でよい。
  `null` の場合は `scripts/update_news.py` が収集時の日付（HN の投稿日など）で補うので、推測で埋めないこと。
- `summary` は必ず3要素。

`AI_NEWS.md` への反映は、このステップの後に `scripts/run_daily.ps1` が `scripts/update_news.py` を実行して行う。

## 完了時の出力
最後に次の形式で1行だけ出力する。

```
[要約完了] {DATE}: N 件を要約, 備考: なし or notes の内容
```
