# CLAUDE.md — AIニュース収集パイプライン

このファイルはプロジェクトの**前提・ルール**を管理する。
作業の進捗は [PROGRESS.md](PROGRESS.md) を参照・更新すること。

---

## 1. プロジェクトの目的

AIエンジニア目線で「面白い」と思えるニュースを毎日自動で収集・選定・要約し、
`AI_NEWS.md` に蓄積する。人が毎朝ざっと目を通すだけでキャッチアップできる状態を目指す。

## 2. パイプライン概要

毎日1回、Claude Code が以下を自動実行する。

| # | ステップ | 内容 | 出力 |
|---|---------|------|------|
| ① | 収集 | 情報ソースから当日の候補ニュースを集める | `data/candidates/{日付}.json` |
| ② | 選定 | 選定基準に沿って候補を絞り込む | `data/selected/{日付}.json`（**1日1〜3件**） |
| ③ | 要約 | 採用ニュースを3行で要約する | `data/summaries/{日付}.json` → `AI_NEWS.md` に追記 |

### ステップ間のデータ（②→③）
`data/selected/{日付}.json` は次の形式とする（②選定はこの形式で出力すること）。

```json
{
  "date": "2026-10-02",
  "items": [
    {
      "rank": 1,
      "candidate_id": 12,
      "field": "LLM",
      "source": "Anthropic News",
      "title": "元のタイトル",
      "url": "https://...",
      "published": "2026-10-01T09:00:00+09:00",
      "summary": "候補の概要",
      "reason": "選んだ理由（1文）",
      "arxiv_url": "論文の場合のみ",
      "hn_url": "Hacker News の場合のみ"
    }
  ]
}
```

## 3. 情報ソース（確定）

ソースの一覧と取得方法は **`config/sources.json`** で管理する（追加・削除はこのファイルを編集）。

| カテゴリ | ソース | 取得方法 |
|---------|--------|---------|
| 公式ブログ | OpenAI / Google DeepMind / Google AI / Hugging Face | RSS（スクリプト） |
| 公式ブログ | Anthropic / Meta AI | ページを Claude が WebFetch（RSS が無いため） |
| 論文 | Hugging Face Daily Papers（upvote 上位30件） | API（スクリプト） |
| 英語コミュニティ | Hacker News（100ポイント以上） | Algolia API（スクリプト） |
| 英語コミュニティ | GitHub Trending（上位25件） | ページを Claude が WebFetch |
| 国内メディア | ITmedia AI+ / Zenn トレンド / Zenn LLM / Qiita 人気記事 | RSS（スクリプト） |
| 補完 | Web検索（最大3回） | Claude が WebSearch |

- 論文は arXiv を直接読むと1日数百件になるため、Hugging Face Daily Papers 経由で注目論文に絞る。
- 収集期間は **過去24時間**。ただしランキング系（Zenn トレンド、Qiita 人気記事、GitHub Trending）は「今の人気」なので期間で絞らない。

## 3.1 ①収集の仕組み

収集は3段階で行う。

1. **機械取得**: `scripts/collect_feeds.py` が RSS と API のソースを取得し、`data/raw/{日付}.json` に保存する（標準ライブラリのみ使用）。
2. **Claude取得**: `prompts/01_collect.md` に従い、Claude が RSS の無いソースと Web検索の結果だけを `data/raw/{日付}_claude.json` に保存する。
3. **統合**: `scripts/merge_candidates.py` が 1 と 2 をまとめ、URL の重複を除いて `data/candidates/{日付}.json` に保存する。

- 機械的にできる処理（取得・統合・AI_NEWS.md への書き込み）はスクリプトで行い、Claude には判断が必要な作業だけを任せる。

- 候補ファイル（`data/candidates/`）は日付ごとに残し、②選定の入力にする。
- 1つのソースで取得に失敗しても処理は止めず、失敗したことを `notes` / `errors` に記録する。

## 4. 選定基準（AIエンジニア目線）

**優先する**
- 新モデル・新API・新機能のリリース（実務ですぐ試せるもの）
- エージェント、RAG、評価、推論効率化など実装に効く技術トピック
- **LLM 以外の分野**: 画像・動画・3D／ロボティクス・自動運転／音声・音楽 の新モデル・注目論文・OSS
- 注目度の高い論文・OSS（再現・試用できるもの）
- 開発ツール（Claude Code 等）のアップデート

**除外する**
- 資金調達・人事・株価などビジネスのみのニュース
- 技術的中身のない宣伝記事・まとめ記事、入門記事
- 既に `AI_NEWS.md` に掲載済みのニュース（重複）
- 直近7日に載せた話題の続報で、新しい事実が無いもの

**選び方**（詳細は `prompts/02_select.md`）
- 1日 **1〜3件**（0件にはしない。面白いものが少なければ1件でよい）。
- 同じ話題は一次情報（公式ブログ・論文・リポジトリ）を代表にして1件にまとめる。
- 候補ごとに分野（`LLM` / `画像・動画・3D` / `ロボティクス・自動運転` / `音声・音楽` / `その他`）を付ける。
- **`LLM` は1日最大2件**。3件選ぶ日は少なくとも1件を LLM 以外にする。LLM 以外に良い候補が無ければ無理に埋めず件数を減らす。大きな LLM の発表が重なった日もこの上限は守る。
- 同じくらい面白ければ LLM 以外の分野同士もばらす。
- Zenn / Qiita の解説・試用記事は、新しい知見や実践的なノウハウがあれば選んでよい。
- 比べたが選ばなかった候補も理由付きで `shortlist` に残す（選定の傾向を見直すため）。

## 5. 出力仕様: AI_NEWS.md

- **新しいニュースはファイルの先頭（上）に追記**する。既存の内容は変更・削除しない。
- 書き込みは `scripts/update_news.py` が行う（Claude は `AI_NEWS.md` を直接編集しない）。
  既に載っている URL はスキップし、同じ日付の見出しがあればその下に追加する。
- 1日分を日付見出し（＝収集した日）でまとめる。1日 **1〜3件**。
- 各ニュースには **日付・ソース・タイトル・3行要約** を必ず記載する。
  - **タイトル**: 日本語以外の記事は `日本語訳（原題）`、日本語の記事は元のタイトルのまま。
  - **日付**: 記事の公開日（YYYY-MM-DD）。本文で確認できなければ、収集時の日付で補う（`update_news.py` が行う）。
    HN・Daily Papers の収集時の日付は記事の公開日ではないので `2026-10-21（HN投稿日）` / `（Daily Papers掲載日）` と添える。どちらも無ければ `不明`。

### フォーマット

```markdown
## 2026-10-02

### [Claude が新しい酵素系を発見（Claude discovers a novel enzyme system with CRISPR-like repeats）](記事URL)
- **日付**: 2026-09-23
- **ソース**: Anthropic News
- **要約**:
  1. 何が起きたか（事実）
  2. 技術的なポイント（何が新しいか）
  3. AIエンジニアにとっての意味（試す価値・影響）

---
```

### 要約ルール
- 日本語で書く。各行は1文・60字程度まで。
- 1行目=事実、2行目=技術ポイント、3行目=エンジニアへの示唆、の構成を守る。
- 記事に書かれていない推測は書かない。

## 6. 運用ルール

- 実行頻度: 1日1回
- 実行方式: **Windows タスクスケジューラ** から `scripts/run_daily.ps1` を起動する。
  - タスク名 `AI_NEWS_daily`、**毎日 9:00**。登録・変更・削除は `scripts/register_task.ps1`（`-Time HH:mm` / `-Unregister`）。
  - ログオン中のみ実行。9:00 に PC が起動していなかった場合は、次に起動したときに実行する。ネットワーク未接続時は実行しない。1時間で強制終了。
  - スクリプトが Python と `claude -p`（非対話モード）をステップ順に呼び出す。Claude はステップごとに別セッション。
  - `claude` コマンドが PATH に無ければ、VS Code 拡張機能に同梱の最新 `claude.exe` を自動で使う。
  - Claude の権限は `--permission-mode dontAsk` ＋ 許可ツール `Read, Glob, Grep, WebFetch, WebSearch, Edit(./data/**)` に限定する（`data/` 外への書き込みとコマンド実行は不可）。
  - 実行ログは `logs/{日付}.log` に追記する。失敗したステップで止まり、`-From <ステップ名>` で途中から再開できる。
  - 手動実行: `powershell -ExecutionPolicy Bypass -File scripts
un_daily.ps1 [-Date YYYY-MM-DD] [-From feeds|collect|merge|select|summarize|publish]`
  - PC が起動・ログインしていない時間帯は実行されない点に注意する。
- 同じ日付で再実行した場合は、その日の見出しに重複なく追記する。
- 取得に失敗したソースがあっても処理は止めず、取得できた分で続行する。

## 7. 作業ルール（Claude Code 向け）

- 作業を始める前に `PROGRESS.md` を読み、「今やっていること」を確認する。
- 作業の区切りごとに `PROGRESS.md` を更新する（完了したら「完了」へ移し、次のタスクを「今やっていること」へ）。
  - ただし **自動実行（`scripts/run_daily.ps1` から起動された `claude -p`）では `PROGRESS.md` を更新しない**。
    自動実行では `data/` 配下にしか書き込めない設定になっている。
- 前提（ソース・基準・フォーマット）を変えたら、このファイルを更新する。

## 8. ファイル構成

```
ニュース収集/
├── CLAUDE.md      # 前提・ルール（このファイル）
├── PROGRESS.md    # 進捗管理
├── AI_NEWS.md     # 成果物（パイプラインが生成）
├── config/
│   └── sources.json         # 情報ソースの一覧
├── prompts/
│   ├── 01_collect.md        # ①収集の手順（Claude 用）
│   ├── 02_select.md         # ②選定の手順（Claude 用）
│   └── 03_summarize.md      # ③要約の手順（Claude 用）
├── scripts/
│   ├── run_daily.ps1        # 毎日の実行スクリプト（タスクスケジューラから起動）
│   ├── register_task.ps1    # タスクスケジューラへの登録
│   ├── collect_feeds.py     # ①収集のうち RSS / API 取得
│   ├── merge_candidates.py  # ①収集のうち 統合・重複除去
│   └── update_news.py       # ③要約のうち AI_NEWS.md への書き込み
├── data/
│   ├── raw/{日付}.json        # 機械取得の結果
│   ├── raw/{日付}_claude.json # Claude 取得の結果
│   ├── candidates/{日付}.json # ①収集の出力（②選定の入力）
│   ├── selected/{日付}.json   # ②選定の出力（③要約の入力）
│   └── summaries/{日付}.json  # ③要約の出力（update_news.py の入力）
└── logs/{日付}.log           # 実行ログ
```
