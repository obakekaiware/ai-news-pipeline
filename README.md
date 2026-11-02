# AI NEWS パイプライン

AIエンジニア目線で「面白い」ニュースを毎日自動で収集・選定・要約し、[AI_NEWS.md](AI_NEWS.md) に蓄積するパイプライン。
機械的な取得・統合・書き込みは Python スクリプトが行い、判断が必要な作業（選定・要約など）だけを Claude Code（`claude -p`）に任せる。

選定基準・出力フォーマット・運用ルールなどの前提は [CLAUDE.md](CLAUDE.md) にまとめている（Claude は各ステップでこのファイルを読む）。

## 出力例

```markdown
## 2026-10-30

### [Mistral が1兆パラメータ級 MoE「Mistral Large 4」の重みを公開（We're releasing the weights of Mistral Large 4）](https://mistral.ai/news/mistral-large-4-oss/)
- **日付**: 2026-10-29（HN投稿日）
- **ソース**: Hacker News
- **要約**:
  1. 何が起きたか（事実）
  2. 技術的なポイント（何が新しいか）
  3. AIエンジニアにとっての意味（試す価値・影響）
```

- 1日 1〜3件。新しい日付がファイルの先頭に追加される。
- LLM は1日最大2件とし、画像・動画・3D／ロボティクス／音声などの分野も拾う。

## 仕組み

| # | ステップ | 担当 | 出力 |
|---|---------|------|------|
| ① | 収集（RSS / API） | `scripts/collect_feeds.py` | `data/raw/{日付}.json` |
| ① | 収集（RSS の無いソース・Web検索） | Claude（`prompts/01_collect.md`） | `data/raw/{日付}_claude.json` |
| ① | 統合・重複除去 | `scripts/merge_candidates.py` | `data/candidates/{日付}.json` |
| ② | 選定 | Claude（`prompts/02_select.md`） | `data/selected/{日付}.json` |
| ③ | 3行要約 | Claude（`prompts/03_summarize.md`） | `data/summaries/{日付}.json` |
| ③ | AI_NEWS.md へ追記 | `scripts/update_news.py` | `AI_NEWS.md` |
| — | GitHub へ反映 | `git commit` / `git push` | `AI_NEWS.md` のみコミット |

`scripts/run_daily.ps1` がこれらを順に実行する。失敗したステップで止まり、途中から再開できる。

### 情報ソース

[config/sources.json](config/sources.json) で管理する。

- **公式ブログ**: OpenAI / Google DeepMind / Google AI / Hugging Face / Anthropic / Meta AI
- **論文**: Hugging Face Daily Papers（upvote 上位30件）
- **英語コミュニティ**: Hacker News（100ポイント以上）/ GitHub Trending
- **国内メディア**: ITmedia AI+ / Zenn（トレンド・LLM）/ Qiita 人気記事
- **補完**: Web検索

収集期間は過去24時間（ランキング系のソースは期間で絞らない）。

## 必要なもの

- Windows（タスクスケジューラで定期実行する）
- Python 3（標準ライブラリのみ使用）
- [Claude Code](https://claude.com/claude-code)（ログイン済み）
  - `claude` が PATH に無い場合は、VS Code 拡張機能に同梱の `claude.exe` を自動で探す

## 使い方

### 手動実行

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1

# 日付を指定して、途中のステップから再開する
powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Date 2026-10-02 -From select
```

`-From` に指定できるステップ: `feeds` / `collect` / `merge` / `select` / `summarize` / `publish` / `git`

最後の `git` ステップでは `AI_NEWS.md` だけをコミットして `origin/main` に push する。
事前に一度手動で `git push` し、GitHub の認証情報を Git Credential Manager に保存しておくこと（自動実行中は認証を求めない）。

実行ログは `logs/{日付}.log` に追記される。

### 毎日自動で実行する

```powershell
# 毎日 9:00 に実行するタスク「AI_NEWS_daily」を登録
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1

# 時刻を変える / 登録を削除する
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Time 08:30
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Unregister
```

- ログオン中のみ実行する。9:00 に PC が起動していなかった場合は、次に起動したときに実行する。
- ネットワーク未接続時は実行しない。1時間で強制終了する。

## Claude の権限

自動実行時の `claude -p` は `--permission-mode dontAsk` で動かし、使えるツールを次に限定している。

```
Read, Glob, Grep, WebFetch, WebSearch, Edit(./data/**)
```

`data/` の外への書き込みとコマンドの実行はできない。

## ファイル構成

```
├── CLAUDE.md                # 前提・ルール（選定基準・出力フォーマットなど）
├── AI_NEWS.md               # 成果物
├── config/sources.json      # 情報ソースの一覧
├── prompts/                 # Claude 用の手順（収集・選定・要約）
├── scripts/
│   ├── run_daily.ps1        # 毎日の実行スクリプト
│   ├── register_task.ps1    # タスクスケジューラへの登録
│   ├── collect_feeds.py     # RSS / API 取得
│   ├── merge_candidates.py  # 統合・重複除去
│   └── update_news.py       # AI_NEWS.md への書き込み
├── data/                    # 中間データ（Git 管理外）
└── logs/                    # 実行ログ（Git 管理外）
```
