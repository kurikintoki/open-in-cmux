# RESULT4 — PLAN4 の実装: `open-in-cmux` の監視モード

Source: チャットでの指示「implement PLAN4 and write results in RESULT4.md」（仕様: `03_plans/PLAN4.md`）. Date: 2026-11-13

## Task

PLAN4 を実装する: 管理ポリシーでユーザー hook が動かないため、Claude Code の外で動く監視プロセス
（`open_in_cmux.py --watch`）で、新しい `PLAN<n>.md` / `RESULT<n>.md` を cmux に表示する。

## Result

**コード・テスト・ドキュメントは完了。実際の cmux での動作（V2〜V6）は未確認**で、ユーザーが
cmux のターミナルで実行する必要がある（Claude の Bash サンドボックスからは cmux ソケットに
繋がらないため、こちらでは試せない）。

### 使い方

プロジェクトのルートで、cmux の別ターミナル（分割またはタブ）から:

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py --watch
```

symlink は作成済みなので、どのプロジェクトでもこのコマンドで起動できる。止めるときは Ctrl-C。

### 実装ステップごとの状態

| PLAN4 のステップ | 状態 |
|---|---|
| 1. `open_in_cmux.py` に監視モードを追加 | 完了（W1〜W10） |
| 2. 監視モードのテスト | 完了。15 件追加、既存 21 件と合わせて 36 件 pass |
| 3. `SKILL.md` / `README.md` / `CLAUDE.md` の更新 | 完了 |
| 4. Verification | V1 のみ完了。V2〜V6 はユーザーが cmux で実施 |
| 5. commit | ユーザー |

### 変更したファイル

| ファイル | 内容 |
|---|---|
| `.claude/skills/open-in-cmux/open_in_cmux.py` | `--watch [dir] [--interval] [--surface]` を追加。`open_file` が分割元の surface を引数で受け取るように変更（hook / CLI モードは従来どおり `CMUX_SURFACE_ID` を渡す） |
| `.claude/skills/open-in-cmux/test_open_in_cmux.py` | `WatchMode` の 15 テストを追加。偽の `cmux` が呼び出しごとの記録を残すように 1 行追加。既存テストは変更なし |
| `.claude/skills/open-in-cmux/SKILL.md` | 2 方式（監視 / hook）の使い分け、監視の使い方、「併用しない」「Bash ツールからは起動しない」を記載 |
| `README.md` | 同じ内容を人間向けに書き直し |
| `CLAUDE.md` | 概要に監視を追加。「このマシンでは hook は動かない（`allowManagedHooksOnly`）」を明記 |

変更していないもの: `~/.claude-personal/settings.json`（hook エントリは残したまま）、管理ポリシーの
ファイル、`RESULT2.md`、`/prompt` スキル。

### Verification

| # | 結果 |
|---|---|
| V1 | **pass**: `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` → `Ran 36 tests … OK`（2 回実行して 2 回とも） |
| V2 | 未実施。監視から cmux ソケットに繋がるかはここで初めて確定する |
| V3 | 未実施（どのペインから分割されるか、フォーカス、2 つ目を開いたときのペインの増え方） |
| V4 | 実機では未実施。テストでは「既存ファイルの書き換えでは開かない」を確認 |
| V5 | 実機では未実施。テストでは「`CMUX_WORKSPACE_ID` 無し → 理由を出して exit 1」を確認 |
| V6 | 未実施 |

テストで確認した監視モードの動作: 起動後に作ったファイルを開く / 起動時からあるファイルは開かない /
同番号の PROMPT が無ければ開かない / 同じファイルは 1 回だけ / 削除後の作り直しは再度開く /
`03_plans` 等が無ければ `dir` 自体を監視 / 後から作られた `03_plans` を拾う / `--surface` の有無で
cmux への引数が変わる / cmux が失敗しても監視を続ける / Ctrl-C で exit 0（stderr 出力なし）/
cmux 外・`cmux` 無し・存在しない `dir` で exit 1。

### PLAN4 からの差分

- W7 に 1 点追加: `dir` が存在しないときも、理由を出して exit 1。
- それ以外は PLAN4 のとおり。

### 残作業（ユーザー）

1. cmux で V2〜V6 を実施する。最初は V2: このプロジェクトのルートで監視を起動し、Claude Code で
   `/prompt` を 1 回実行する。
2. commit。

## Items Requiring Confirmation（要確認）

1. **PLAN4 の Status** — options: (a) V2 が通ったら `Implemented · SHA: <commit>` にする /
   (b) 今 `Implemented` にする。
   (Recommendation: a。監視からソケットに繋がるかが未確認のため。)
2. **V3 の結果次第の対応** — 分割元のペインが期待と違う、または分割が増え続けて使いにくい場合に、
   `--surface` の既定値の変更や「タブで開く」方式を新しい PLAN にするか。実機で見てから判断。
