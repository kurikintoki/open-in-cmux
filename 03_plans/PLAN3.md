# PLAN3 — `open-in-cmux` が開かない原因と修正方針（管理ポリシーがユーザー hook を無効化している）

> Status: Superseded · Superseded by: PLAN4

Source: `02_prompts/PROMPT3.md`. Date: 2026-11-13

[[PLAN2]] の実装（`RESULT2`）に対する修正プラン。PLAN2 を置き換えるものではない。
起動方式が要確認 1 で決まるまで実装できないため `Draft`。

## 報告された事象

`communication-with-recruiters` プロジェクトで Claude Code を再起動し、`PROMPT383.md` を実行。
`04_results/RESULT383.md` は作成されたが、cmux に表示されなかった。

## 原因

**管理ポリシーの `allowManagedHooksOnly: true` により、`~/.claude-personal/settings.json` の
hook は読み込まれない。** PLAN2 で登録した PostToolUse hook は一度も実行されていない。
スクリプト・symlink・設定の書き方に問題は見つかっていない。

これは管理ポリシーによるブロックであり、回避はしない（下の「修正方針」参照）。ポリシーの設定内容と、
自分のマシンから外す手順: https://github.com/secdev-whc/ai-cli-hardening
（ルール自体が不適切だと考える場合の報告先: https://github.com/secdev-whc/ai-cli-hardening/issues ）

### 根拠

| # | 確認したこと | 結果 |
|---|---|---|
| E1 | `/Library/Application Support/ClaudeCode/managed-settings.json` | `"allowManagedHooksOnly": true`。管理側の hook は PreToolUse（Bash ガード）と PostToolUse（監査）の 2 つだけ |
| E2 | ユーザー側の設定 | `hooks.PostToolUse`（matcher `Write`）は PLAN2 のとおり登録済み。symlink `~/.claude-personal/skills/open-in-cmux` も存在（13:42 作成）。プロジェクト側 `settings.local.json` に hook 関連の設定なし |
| E3 | `RESULT383.md` の書かれ方（そのセッションの記録） | Write ツールで `04_results/RESULT383.md` を作成（14:18:26 JST）。`02_prompts/PROMPT383.md` も存在。発火条件（R2）は満たしている |
| E4 | 同じ入力で `open_in_cmux.py` を手動実行 | 判定を通過して `cmux markdown open` の呼び出しまで到達（Bash サンドボックス内なのでソケット接続だけ失敗）。スクリプトの判定ロジックは正しい |
| E5 | このプロジェクトのセッションでの挙動 | hook 登録後・symlink 作成前に `RESULT2.md` を Write したが、存在しないスクリプトを指す hook のエラーは出なかった。hook が動いていないことと整合する（単独では証明にならない） |

確定させる方法（ユーザー）: Claude Code で `/hooks` を開き、PostToolUse にユーザーの hook が
有効として出ているかを見る。

### 未確認のまま残っていること

- hook が実行できた場合に、hook プロセスから cmux ソケットに繋がるか（PLAN2 の V2）。hook が
  一度も動いていないため、今回の事象からは何も分からない。
- 同じ理由で、既存の Stop hook（`update-docs` の `check_docs_stale.py`）も動いていないはず。
  設定からの推論で、実際の挙動は見ていない。

### 自分の見落とし

PLAN / PLAN2 は「ユーザー設定の hook は動く」前提で書いた。管理ポリシーの存在はセッション開始時に
分かっていたが、hook を制限する設定があるかを確認しなかった。

## 修正方針

ユーザー hook を使う設計（PLAN2）は、このマシンの現在のポリシーでは成立しない。取れる道は 3 つあり、
どれを選ぶかはユーザーの判断（要確認 1）。

| 案 | 内容 | 自動か | ポリシーとの関係 | 追加の作業 |
|---|---|---|---|---|
| A | ポリシーを外す、または `allowManagedHooksOnly` の見直しを依頼する。PLAN2 の実装はそのまま使う | 自動（hook） | 外すのはユーザー自身の操作（上記リポジトリの手順。承認不要。集中管理のマシンでは次回配布で再適用されうる）。外すと他の保護もなくなる | コード変更なし。PLAN2 の V2〜V6 を実施 |
| B | Claude Code の外で動く**監視プロセス**。`open_in_cmux.py --watch` を cmux のターミナルで動かし、新しい `PLAN<n>.md` / `RESULT<n>.md` を検知して開く | 監視を起動していれば自動 | Claude Code の hook を使わないので設定には触れない。ただし「ブロックされた hook と同じ結果を別経路で得る」ものなので、ポリシーの趣旨に照らして許容かはユーザーが判断する | スクリプトに監視モードを追加、起動方法を決める（要確認 2） |
| C | `/prompt` の `SKILL.md` step 6 に「出力を書いたら `open_in_cmux.py <path>` を実行」を追加（モデルが実行） | モデルが手順を守れば自動 | Bash サンドボックスが cmux ソケットを遮断するため、毎回サンドボックス解除の許可が要る。許可なしで通すにはサンドボックス設定の緩和が必要で、それは管理ポリシーの保護を弱める変更 | `prompt` プロジェクトの変更。`/prompt` 以外で作った PLAN / RESULT は開かない |

### 案 B を選んだ場合の設計（概要）

- `open_in_cmux.py --watch [dir]`: `dir`（既定: カレント）の `03_plans/` と `04_results/`
  （無ければ `dir` 自体）を 1 秒間隔でポーリング。標準ライブラリのみ。
- 起動時点で存在するファイルは開かない。起動後に現れたファイルのうち、PLAN2 の R2（同じ番号の
  `PROMPT<n>.md` がある `PLAN<n>.md` / `RESULT<n>.md`）を満たすものだけを、PLAN2 の R4 と同じ
  コマンドで開く。既存ファイルの変更（Edit）では開かない。
- cmux のターミナルで起動するので `CMUX_WORKSPACE_ID` を引き継ぎ、サンドボックスの外で動く。
  開く位置の基準にする surface の決め方は実装時に検証する（監視を動かす surface と Claude の
  surface は別になる）。
- cmux の外で起動されたら、理由を 1 行出して終了する。
- hook モードと CLI モード（PLAN2 の R1〜R7）は残す。案 A が後で可能になればそのまま使える。
- テスト: 既存 21 件に加え、監視モード（新規ファイルで開く / 既存は開かない / PROMPT 無しは
  開かない / 同じファイルを二度開かない）。
- Verification: 実際の cmux で、監視を起動 → `/prompt` 実行 → 許可プロンプトなしで表示される
  こと。ソケットに繋がるかはここで初めて確定する。

### どの案でも行うこと

- `README.md` / `SKILL.md` / `CLAUDE.md` に「`allowManagedHooksOnly` が有効な環境では hook 方式は
  動かない」と明記する。現在の記述は hook で動く前提になっている。
- `RESULT2.md` は書き換えない（当時の記録）。

## Items Requiring Confirmation（要確認）

1. **修正方針** — options: A（ポリシーを外す / 見直しを依頼し、PLAN2 のまま使う）/
   B（Claude Code 外の監視プロセス）/ C（`/prompt` の手順に追加 + サンドボックス解除）。
   (Recommendation: ポリシーを維持したいなら B。C は毎回の許可か、サンドボックスの緩和が必要。
   ポリシーを外してよいなら A が最小で、コード変更が要らない。B がポリシーの趣旨に反しないかの
   判断はユーザーに委ねる。)
2. **（B の場合）監視の起動方法** — options: (a) プロジェクトごとに cmux のターミナルで手動起動 /
   (b) cmux の保存レイアウト（`cmux layout`）に監視用の分割を含める / (c) シェル起動時に自動起動。
   (Recommendation: a で動作確認し、手間なら b。c はシェルの設定ファイルを変更するため勧めない。)
3. **`~/.claude-personal/settings.json` の PostToolUse hook エントリ** — 現状は読み込まれない
   設定。options: (a) 残す（A を選ぶ、または将来ポリシーが変わればそのまま動く）/ (b) 削除する。
   (Recommendation: A なら残す。B / C なら削除。残したままポリシーが外れると、監視と hook の
   両方が同じファイルを開く。)
4. **PLAN2 の Status** — options: (a) `Confirmed` のまま（A を選んで実機確認が通れば
   `Implemented`）/ (b) B / C を選ぶ場合、新しい PLAN で PLAN2 を `Superseded` にする。
   (Recommendation: 要確認 1 の回答に合わせる。)
5. **Stop hook（`update-docs`）も同じ理由で動いていない可能性** — このプロジェクトの範囲外。
   options: (a) 対応しない / (b) `update-claude-md` プロジェクト側で別途調べる。
   (Recommendation: b。`/hooks` で確認できる。)
