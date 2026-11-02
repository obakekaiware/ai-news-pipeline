# ①収集（Claude 取得パート）

あなたは AI ニュース収集パイプラインの「①収集」担当です。
このステップでは **スクリプトでは取れないソースの記事を集めて保存するだけ** を行う。
選定・要約・`AI_NEWS.md` / `PROGRESS.md` の編集はしないこと。

RSS / API のソースは `scripts/collect_feeds.py` が取得済みで、統合と重複除去は後で `scripts/merge_candidates.py` が行う。
**スクリプト取得分（`data/raw/{DATE}.json`）を書き写したり、統合したりしないこと。**

## 入力

- 対象日 `DATE`: 指示で与えられた日付（YYYY-MM-DD）。
- `config/sources.json`: 情報ソースの一覧
- `data/raw/{DATE}.json`: スクリプト取得分。**`since`（収集期間の開始）と、Web検索で同じ記事を拾わないための確認にだけ使う。**

## 手順

### 1. `method: "claude"` のソースを取得する
`config/sources.json` で `method` が `"claude"` のソースは、WebFetch で `url` のページを読んで記事を取り出す。

| ソース | 取り出すもの |
|--------|-------------|
| Anthropic News | `since` 以降に公開された記事（タイトル・URL・公開日・概要） |
| Meta AI Blog | 同上 |
| GitHub Trending | 当日のトレンド上位のリポジトリ（最大25件、取れた分だけでよい）。リポジトリ名・URL・説明・言語・今日のスター数。期間での絞り込みはしない |

- URL が相対パス（例: `/news/xxx`）の場合はドメインを補って絶対 URL にする。
- 公開日がページから判断できない記事は `published: null` とする。日付だけ分かる場合は `"YYYY-MM-DD"` でよい。
- ページが取得できなければ、そのソースは諦めて `notes` に記録し、次へ進む。

### 2. Web検索で取りこぼしを補う
ソースに無い大きな発表を拾うため、WebSearch を **最大3回** 実行する。

- 例: `AI model release {DATE}`、`LLM announcement this week`、`生成AI 発表 {DATE}`
- `since` 以降の、AI 企業・研究機関の一次情報（公式ブログ・公式発表）または信頼できる技術メディアの記事のみ追加する。
- `data/raw/{DATE}.json` に既にある記事は追加しない。
- 追加した記事の `source` には掲載サイト名、`category` には `"Web検索"` を入れる。

### 3. 保存
`data/raw/{DATE}_claude.json` に以下の形式で保存する（UTF-8、既存ファイルがあれば上書き）。
手順1・2で集めた記事だけを入れる。0件でもファイルは作る。

```json
{
  "date": "2026-10-02",
  "items": [
    {
      "source": "GitHub Trending",
      "category": "英語コミュニティ",
      "title": "owner/repo",
      "url": "https://github.com/owner/repo",
      "published": null,
      "summary": "説明（300字以内、無ければ空文字）",
      "stars_today": 1200,
      "language": "Python"
    }
  ],
  "notes": ["Meta AI Blog: 期間内の新着なし"]
}
```

- 人気度の指標があれば項目として入れる（GitHub Trending の `stars_today` など）。

## 完了時の出力
最後に次の形式で1行だけ出力する。

```
[収集完了] {DATE}: Claude取得 B 件 / Web検索 C 件, 失敗ソース: なし or ソース名
```
