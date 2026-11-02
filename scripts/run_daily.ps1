<#
.SYNOPSIS
  AIニュース収集パイプラインを ①収集 → ②選定 → ③要約 の順に実行する（タスクスケジューラから起動する想定）。

.DESCRIPTION
  1. python scripts/collect_feeds.py      … ①収集（RSS / API の機械取得）
  2. claude -p  prompts/01_collect.md     … ①収集（RSS の無いソース・Web検索）
  3. python scripts/merge_candidates.py   … ①収集（統合・重複除去）
  4. claude -p  prompts/02_select.md      … ②選定
  5. claude -p  prompts/03_summarize.md   … ③要約（data/summaries に JSON を保存）
  6. python scripts/update_news.py        … ③要約（AI_NEWS.md の先頭に追記）

  どこかのステップが失敗したらそこで止める。ログは logs/{日付}.log に追記する。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1
  powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Date 2026-10-02 -From select
#>
param(
    # 対象日（既定: 今日の JST）
    [string]$Date = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Tokyo Standard Time').ToString('yyyy-MM-dd'),
    # 途中から再開するときのステップ名
    [ValidateSet('feeds', 'collect', 'merge', 'select', 'summarize', 'publish')]
    [string]$From = 'feeds',
    # claude.exe のパス（省略時は自動検出）
    [string]$ClaudePath = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root  # タスクスケジューラは System32 で起動するため、必ずプロジェクト直下へ移動する

$LogDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force $LogDir | Out-Null
$LogFile = Join-Path $LogDir "$Date.log"

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Find-Claude {
    if ($ClaudePath) { return $ClaudePath }
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # CLI 未インストールの場合は VS Code 拡張機能に同梱された最新版を使う（更新でフォルダ名が変わるため毎回探す）
    $bundled = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' } |
        Where-Object { Test-Path $_ } |
        Sort-Object { [version]((Split-Path (Split-Path (Split-Path $_))) -replace '^.*claude-code-([\d.]+).*$', '$1') } -Descending |
        Select-Object -First 1
    if ($bundled) { return $bundled }
    throw 'claude.exe が見つかりません。-ClaudePath で指定してください。'
}

# 各ステップ（$From より前はスキップ）
$Steps = 'feeds', 'collect', 'merge', 'select', 'summarize', 'publish'
function Should-Run([string]$Step) { $Steps.IndexOf($Step) -ge $Steps.IndexOf($From) }

# PowerShell 5.1 は外部コマンドの stderr 出力をエラー扱いするため、呼び出し中だけ Continue にして終了コードで判定する
function Invoke-Native([scriptblock]$Block) {
    $ErrorActionPreference = 'Continue'
    $out = & $Block 2>&1 | ForEach-Object { "$_" }
    return @{ Out = $out; Code = $LASTEXITCODE }
}

function Invoke-Python([string]$Script) {
    $r = Invoke-Native { python $Script --date $Date }
    $out, $code = $r.Out, $r.Code
    $out | ForEach-Object { Write-Log "  $_" }
    if ($code -ne 0) { throw "$Script が失敗しました (exit $code)" }
}

# Claude に許可するツール: 読み取り・Web 取得・検索と、data/ 配下への書き込みのみ
$AllowedTools = 'Read,Glob,Grep,WebFetch,WebSearch,Edit(./data/**)'

function Invoke-ClaudeStep([string]$PromptFile) {
    if (-not (Test-Path $PromptFile)) { throw "$PromptFile がありません" }
    $instruction = "CLAUDE.md と $PromptFile を読み、$PromptFile の手順に従って実行してください。対象日 DATE は $Date です。これは自動実行なので PROGRESS.md は更新しないでください。"
    $r = Invoke-Native { & $script:Claude -p $instruction --permission-mode dontAsk --allowedTools $AllowedTools --no-session-persistence }
    $out, $code = $r.Out, $r.Code
    $out | ForEach-Object { Write-Log "  $_" }
    if ($code -ne 0) { throw "claude ($PromptFile) が失敗しました (exit $code)" }
}

function Assert-Output([string]$Path) {
    if (-not (Test-Path $Path)) { throw "期待した出力 $Path が作られていません" }
}

try {
    Write-Log "===== 開始: DATE=$Date FROM=$From ====="
    $script:Claude = Find-Claude
    Write-Log "claude: $script:Claude"

    if (Should-Run 'feeds') {
        Write-Log '--- ①収集（機械取得） ---'
        Invoke-Python 'scripts/collect_feeds.py'
        Assert-Output "data/raw/$Date.json"
    }
    if (Should-Run 'collect') {
        Write-Log '--- ①収集（Claude） ---'
        Invoke-ClaudeStep 'prompts/01_collect.md'
        Assert-Output "data/raw/${Date}_claude.json"
    }
    if (Should-Run 'merge') {
        Write-Log '--- ①収集（統合） ---'
        Invoke-Python 'scripts/merge_candidates.py'
        Assert-Output "data/candidates/$Date.json"
    }
    if (Should-Run 'select') {
        Write-Log '--- ②選定 ---'
        Invoke-ClaudeStep 'prompts/02_select.md'
        Assert-Output "data/selected/$Date.json"
    }
    if (Should-Run 'summarize') {
        Write-Log '--- ③要約 ---'
        Invoke-ClaudeStep 'prompts/03_summarize.md'
        Assert-Output "data/summaries/$Date.json"
    }
    if (Should-Run 'publish') {
        Write-Log '--- ③AI_NEWS.md へ追記 ---'
        Invoke-Python 'scripts/update_news.py'
    }
    Write-Log '===== 正常終了 ====='
    exit 0
}
catch {
    Write-Log "!!!!! 失敗: $($_.Exception.Message)"
    Write-Log "再開するには: powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Date $Date -From <ステップ名>"
    exit 1
}
