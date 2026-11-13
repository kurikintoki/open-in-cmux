# PLAN4 — `open-in-cmux` に監視モードを追加する（管理ポリシーで hook が動かないため）

> Status: Confirmed

Source: `02_prompts/PROMPT4.md`（[[PLAN3]] の要確認への回答）. Date: 2026-11-13

Replaces [[PLAN3]]（PLAN3 は `Superseded by: PLAN4`）。PROMPT4 が PLAN3 を名指ししている。
[[PLAN2]]（hook 方式）は置き換えない: PLAN2 の実装は残し、その上に監視モードを足す。
このファイルは自己完結しており、PLAN3 を読まずに実装できる。

## Goal

Claude Code が `PROMPT<n>.md` を実行して `PLAN<n>.md` / `RESULT<n>.md` を生成したら、cmux の
markdown ビューアで開く。**このマシンでは管理ポリシーがユーザー hook を無効化しているため**、
Claude Code の外で動く監視プロセスで実現する。

## Decisions

PROMPT4 による、PLAN3 の要確認への決定:

| # | 項目 | 決定 |
|---|---|---|
| 1 | 修正方針 | **B**: Claude Code 外の監視プロセス（`open_in_cmux.py --watch`）。管理ポリシーと Claude Code の設定には触れない |
| 2 | 監視の起動方法 | (a) プロジェクトごとに cmux のターミナルで手動起動 |
| 3 | `~/.claude-personal/settings.json` の PostToolUse hook エントリ | (a) 残す。将来ポリシーが変わればそのまま動く。そのとき監視も動かしていると同じファイルが 2 回開くので、その場合は監視を使わない（`SKILL.md` / `README.md` に明記） |
| 4 | PLAN2 の Status | (a) `Confirmed` のまま。hook が動く環境で実機確認が通れば `Implemented` |
| 5 | Stop hook（`update-docs`）が同じ理由で動いていない可能性 | (b) `update-claude-md` プロジェクト側で別途調べる。このプランの範囲外で、ここでは何もしない |

## 背景: なぜ hook で開かなかったか

`communication-with-recruiters` で `PROMPT383.md` を実行し `RESULT383.md` が作られたが、
開かなかった。原因は管理ポリシーの `allowManagedHooksOnly: true`
（`/Library/Application Support/ClaudeCode/managed-settings.json`）で、ユーザー設定の hook は
読み込まれない。PLAN2 の hook は一度も実行されていない。スクリプト・symlink・設定の書き方に問題は
見つかっていない（同じ入力を手で与えると `cmux markdown open` の呼び出しまで到達する）。

ポリシーの設定内容と外す手順: https://github.com/secdev-whc/ai-cli-hardening

## 前提として確定している事実

| # | 事実 |
|---|---|
| F1 | `cmux markdown open <path> [--workspace] [--surface] [--focus]` は右分割の整形ビューアを開く（ライブリロード）。`--surface` は「分割元の surface」で、省略時はフォーカス中の surface |
| F2 | cmux のターミナルには `CMUX_WORKSPACE_ID` / `CMUX_SURFACE_ID` が入っている |
| F3 | Claude Code の Bash サンドボックス内からは cmux ソケットに繋がらない（`Operation not permitted`）。ユーザーが cmux のターミナルで直接起動したプロセスはサンドボックスの外 |
| F4 | `/prompt` は出力を新規作成し、上書きしない。旧 PLAN の Status 変更は既存ファイルの編集 |
| F5 | 現在の実装（PLAN2）: `.claude/skills/open-in-cmux/` に `open_in_cmux.py`（hook モード / CLI モード）、`test_open_in_cmux.py`（21 件 pass）、`SKILL.md`。`~/.claude-personal/skills/open-in-cmux` は symlink 済み |

未確認（Verification で確定させる）: ユーザーのターミナルから起動した監視が cmux ソケットに繋がる
こと、分割がどのペインから作られるか。

## 設計

### 使い方

Claude Code を動かすプロジェクトのルートで、cmux の別ターミナル（分割またはタブ）から起動する:

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py --watch
```

止めるときは Ctrl-C。プロジェクトごとに 1 つ起動する。

### `--watch` の仕様

| # | 要件 |
|---|---|
| W1 | `open_in_cmux.py --watch [dir] [--interval <秒>] [--surface <id\|ref>]`。`dir` の既定はカレントディレクトリ、`--interval` の既定は 1 |
| W2 | **監視対象**: `dir/03_plans/` と `dir/04_results/` のうち存在するもの。どちらも無ければ `dir` 自体。毎回のポーリングで判定し直す（後から作られたディレクトリも拾う） |
| W3 | **起動時に存在するファイルは開かない。** 起動後に新しく現れたファイル名だけが対象 |
| W4 | **対象判定**は hook モードと同じ関数を使う: ファイル名が `^(PLAN\|RESULT)\d*\.md$` に一致し、同じ番号の `PROMPT<n>.md` がある（探索先: プロジェクトルートの `02_prompts/`、無ければ出力と同じディレクトリ。番号は整数比較・無番号 = 1） |
| W5 | **開く**: `cmux markdown open <絶対パス> --workspace $CMUX_WORKSPACE_ID --focus false`。`--surface` は既定では付けない（cmux の既定 = フォーカス中の surface から右分割。監視自身のペインを分割元にしないため）。`--surface` 引数が渡されたときだけ付ける |
| W6 | 既存ファイルの内容変更では開かない（ファイル名の出現だけを見る）。同じファイルを 2 回開かない。削除後に同名で作り直された場合は新規として開く |
| W7 | **cmux の外で起動されたら**（`CMUX_WORKSPACE_ID` が無い、または `cmux` が見つからない）理由を stderr に 1 行出して exit 1 |
| W8 | cmux の呼び出しが失敗・タイムアウトしても監視は続ける（stderr に 1 行） |
| W9 | 起動時に監視対象を 1 行、開くたびにファイル名を 1 行 stdout に出す。Ctrl-C で traceback を出さずに exit 0 |
| W10 | ポーリングは標準ライブラリのみ（`os.listdir` + `time.sleep`）。外部ツール（fswatch 等）に依存しない |

hook モード（引数なし）と CLI モード（`<path>...`）の動作は変えない: 常に exit 0、stdout に何も
出さない。

### 既知の挙動（対象外として受け入れる）

- Claude 以外が作ったファイル（手で作成、`git pull` / `git checkout` で現れた PLAN / RESULT）も、
  W4 を満たせば開く。
- 同じプロジェクトで監視を 2 つ起動すると 2 回開く（排他制御はしない）。
- 監視を起動していないプロジェクトでは何も起きない。
- 監視の自動起動（保存レイアウト、シェル起動時）は行わない。

## 実装ステップ

1. `open_in_cmux.py` に監視モードを追加（Edit ツール）。`open_file` に surface を引数で渡せるように
   し、hook / CLI モードは従来どおり `CMUX_SURFACE_ID` を使う。
2. `test_open_in_cmux.py` に監視モードのテストを追加（偽の `cmux`、`--interval 0.1`）:
   起動後に作ったファイルで開く / 起動時からあるファイルは開かない / PROMPT 無しは開かない /
   既存ファイルの書き換えでは開かない / 同じファイルを 2 回開かない / `--surface` の有無 /
   cmux 外で exit 1 / cmux 失敗後も次のファイルを開く / `03_plans` 等が無いときは `dir` を監視。
   既存 21 件は変更せず pass のまま。
3. `SKILL.md` / `README.md` / `CLAUDE.md` を更新: 監視モードの使い方、
   「`allowManagedHooksOnly` が有効な環境では hook 方式は動かない」、
   「hook が動く環境では監視と併用しない」。
4. Verification を実施（V2 以降はユーザーが cmux で実行）。
5. commit はユーザー。

`~/.claude-personal/settings.json` と管理ポリシーのファイルは変更しない。`RESULT2.md` も
書き換えない（当時の記録）。

## Verification

| # | 確認 | 期待 |
|---|---|---|
| V1 | `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` | 全件 pass |
| V2 | cmux でプロジェクトのルートに別ターミナルを開き `--watch` を起動。Claude Code で `/prompt` を実行 | 生成された `PLAN<n>.md` / `RESULT<n>.md` が、許可プロンプトなしで表示される。**監視からソケットに繋がることはここで確定する** |
| V3 | V2 でどのペインから分割されたか、フォーカスが動いたか、続けて 2 つ目を開いたときのペインの増え方 | 記録する。使いにくければ `--surface` 指定や「タブで開く」方式を新しい PLAN にする |
| V4 | 監視起動中に既存 PLAN の Status 行を編集 | 開かない |
| V5 | cmux 外のターミナルで `--watch` | 理由を 1 行出して exit 1 |
| V6 | 別プロジェクト（例: `communication-with-recruiters`）で V2 を繰り返す | 同様に開く |

V2 でソケットに繋がらなかった場合は、実装を止めて報告する（回避策を黙って入れない）。

## Items Requiring Confirmation（要確認）

None.
