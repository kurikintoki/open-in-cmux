# PLAN — `/prompt` が生成した PLAN / RESULT を cmux 内に自動表示するグローバルスキル

> Status: Draft

Source: `02_prompts/PROMPT.md`. Date: 2026-11-13

## Goal

Claude Code が `PROMPT<n>.md` を実行して `PLAN<n>.md` または `RESULT<n>.md` を生成したら、
そのファイルが **ユーザーの操作なしに** cmux の markdown ビューアで開く。どのプロジェクトでも
効くよう、グローバルスキルとして配布する。

## 調査で確定した事実

| # | 事実 | 確認方法 |
|---|---|---|
| F1 | cmux 0.65.2 に markdown を開くコマンドが 2 つある。`cmux markdown open <path>` = 右に分割した整形ビューア（ファイル変更でライブリロード、既定でフォーカスを奪わない）。`cmux open <path>` = 対象ペインに markdown プレビューの**タブ**を追加（エージェント / スクリプトから実行時は既定でバックグラウンド） | `cmux markdown --help` / `cmux open --help` |
| F2 | cmux 内の Claude Code セッションには `CMUX_WORKSPACE_ID` / `CMUX_SURFACE_ID` / `CMUX_SOCKET_PATH` / `CMUX_BUNDLED_CLI_PATH` が入っている。両コマンドとも `--workspace` / `--surface` の既定値はこの環境変数 | `env`、各 `--help` |
| F3 | **Bash ツールのサンドボックス内からは cmux のソケットに繋がらない**: `cmux ping` → `Failed to connect to socket at ~/.local/state/cmux/cmux.sock (Operation not permitted, errno 1)` | このセッションで実行 |
| F4 | `/prompt` は出力ファイルを必ず Write ツールで新規作成し、上書きしない（`output_name.py` exit 3）。旧 PLAN の `Superseded` 化は Edit | `prompt/SKILL.md` step 3, 6 |
| F5 | 既存のグローバルスキルは「各プロジェクトの `.claude/skills/<name>/` が実体、`~/.claude-personal/skills/<name>` が symlink」。グローバル hook は `~/.claude-personal/settings.json` にあり、`python3 "$CLAUDE_CONFIG_DIR/skills/<name>/<script>.py"` の形で呼んでいる（Stop hook: update-docs） | `ls -la ~/.claude-personal/skills/`、`settings.json` |
| F6 | この環境では Bash から `.claude/skills/` と `~/.claude-personal/settings.json` に書けない（サンドボックスの write deny）。スキルのファイルは Write / Edit ツールで作る。symlink 作成はユーザーの作業 | サンドボックス設定、`prompt/CLAUDE.md` |

未確認（実装時に検証、下の Verification 参照）: hook プロセスからは cmux ソケットに繋がること
（hook は Bash ツールのサンドボックス外で動く想定）、同じコマンドを繰り返したときのペインの増え方。

## 設計（要確認 1〜4 は推奨案で記述。回答で変わる箇所は各項に明記）

### 方式: PostToolUse hook + スキル同梱スクリプト

「自動的に」を確実に満たすため、モデルの手順ではなく **hook** で起動する。F3 により、`/prompt` の
手順に `cmux …` を 1 行足す方式は毎回サンドボックス解除の許可プロンプトが出るため、自動にならない。

```
Write ツールが PLAN<n>.md / RESULT<n>.md を作成
  └─ PostToolUse hook (matcher: Write)
       └─ open_in_cmux.py  ← stdin: hook JSON (tool_input.file_path, cwd)
            ├─ 対象外 / cmux 外 → 何もせず exit 0
            └─ cmux markdown open <abs path> --workspace $CMUX_WORKSPACE_ID --surface $CMUX_SURFACE_ID --focus false
```

### スキルの構成

実体はこのリポジトリ、グローバル公開は symlink（F5 の慣例どおり）。スキル名は `open-in-cmux`（要確認 4）。

```
.claude/skills/open-in-cmux/
├── SKILL.md              # 説明・導入手順・手動実行 (/open-in-cmux [path])
├── open_in_cmux.py       # hook 兼 CLI。Python 3.9+、標準ライブラリのみ
└── test_open_in_cmux.py  # 偽の cmux を PATH に置いて引数と exit code を検査
```

- `~/.claude-personal/skills/open-in-cmux` → 上記ディレクトリへの symlink（**ユーザーが作成**）。
- `~/.claude-personal/settings.json` の `hooks.PostToolUse` に追加（既存の Stop hook は残す）:

  ```json
  {
    "matcher": "Write",
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"$CLAUDE_CONFIG_DIR/skills/open-in-cmux/open_in_cmux.py\"",
        "timeout": 10
      }
    ]
  }
  ```

### `open_in_cmux.py` の仕様

| # | 要件 |
|---|---|
| R1 | **hook モード**（引数なし）: stdin の JSON から `tool_input.file_path` を読む。相対パスなら `cwd` で解決 |
| R2 | **対象判定**: ファイル名が `^(PLAN\|RESULT)\d*\.md$` に一致し、かつ同じ番号の `PROMPT<n>.md` が存在する（探索先: プロジェクトルートの `02_prompts/`、無ければ出力と同じディレクトリ。プロジェクトルート = `03_plans/` / `04_results/` の親、無ければ出力のディレクトリ。番号は整数比較・無番号 = 1 で `output_name.py` と同じ規則）。→ 要確認 2 |
| R3 | **cmux 外では何もしない**: `CMUX_WORKSPACE_ID` が無い、または cmux CLI が見つからない（`PATH` → `CMUX_BUNDLED_CLI_PATH` の順）なら exit 0 |
| R4 | **開く**: `cmux markdown open <絶対パス> --workspace $CMUX_WORKSPACE_ID --surface $CMUX_SURFACE_ID --focus false`（Claude のいるペインの右に分割、入力フォーカスは端末に残す）。→ 要確認 3 |
| R5 | **Claude を絶対に止めない**: どの失敗（JSON 不正、cmux エラー、タイムアウト 5 秒）でも exit 0、stdout には何も出さない。失敗理由は stderr に 1 行 |
| R6 | **CLI モード**: `open_in_cmux.py <path>...` は R2 の判定を飛ばして R3〜R5 を適用（`/open-in-cmux <path>` の手動実行とテスト用）。ただし F3 により、Bash ツール経由ではサンドボックス解除が必要 |
| R7 | Edit では発火しない（matcher は `Write` のみ）。旧 PLAN の `Superseded` 化や Status 更新で古いファイルが開かないようにするため（F4） |

### 対象外

- `/prompt` スキル（`SKILL.md`・スクリプト）は変更しない。
- cmux 以外のターミナル対応、開いたビューアを自動で閉じる処理、同一ファイルの二重オープン抑止
  （`/prompt` は 1 回の実行で出力を 1 度しか Write しない）。

## 実装ステップ

1. `.claude/skills/open-in-cmux/open_in_cmux.py` と `test_open_in_cmux.py` を作成（Write ツール）。
   テスト: 対象 / 対象外のファイル名、PROMPT の有無、番号の整数比較、cmux 外、cmux 失敗時も exit 0、
   渡した引数。
2. `SKILL.md` を作成（目的、導入 3 手順、手動実行、無効化の方法 = hook エントリの削除）。
3. **ユーザー作業**: symlink を作成
   `ln -s "<このリポジトリ>/.claude/skills/open-in-cmux" ~/.claude-personal/skills/open-in-cmux`
4. `~/.claude-personal/settings.json` に PostToolUse hook を追加（要確認 5）。
5. Verification を実施。
6. `CLAUDE.md` / `README.md` を実態に合わせて更新（`/update-docs`）。commit はユーザー。

## Verification

| # | 確認 | 期待 |
|---|---|---|
| V1 | `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` | 全件 pass |
| V2 | cmux 内の新しい Claude Code セッションで、このリポジトリに `PROMPT2.md` を置き `/prompt` | `RESULT2.md` / `PLAN2.md` が許可プロンプトなしで右分割に表示され、フォーカスは端末のまま。**hook からソケットに繋がること（F3 の裏）はここで確定する** |
| V3 | V2 の後にもう 1 つ出力を生成 | ペインの増え方を記録。分割が増え続けて使いにくい場合は要確認 3 の案 B / C に切り替え |
| V4 | cmux 外（Terminal.app 等）で `/prompt` | 何も起きず、エラーも出ない |
| V5 | `PROMPT<n>.md` の無いディレクトリで `PLAN.md` を Write、既存 PLAN を Edit | どちらも開かない |
| V6 | 別プロジェクト（例: `prompt`）で `/prompt` | 同様に開く（グローバルに効いている） |

V2 で hook からも繋がらなかった場合: サンドボックス設定でソケットを許可する別案が必要になるため、
実装を止めて報告する（回避策を黙って入れない）。

## Items Requiring Confirmation（要確認）

1. **自動起動の方式** — options: (a) PostToolUse hook（上記設計） / (b) `/prompt` の `SKILL.md`
   step 6 に「出力を書いたら `open_in_cmux.py <path>` を実行」を追加（`prompt` プロジェクト側の
   変更） / (c) 両方。
   (Recommendation: a。F3 により b は Bash サンドボックスに阻まれ、毎回の許可プロンプトか
   サンドボックス設定の緩和が必要。a はモデルの手順漏れもない。)
2. **発火する範囲** — options: (a) 同じ番号の `PROMPT<n>.md` がある `PLAN<n>.md` / `RESULT<n>.md`
   の Write のみ（R2） / (b) `PROMPT` の有無を問わず `PLAN*.md` / `RESULT*.md` の Write すべて /
   (c) `03_plans/` ・ `04_results/` 配下のみ。
   (Recommendation: a。hook は「`/prompt` 実行中か」を知れないので、要件の「PROMPT{number}.md を
   実行した後に生成した」を最も近く表せる条件。`/prompt` を通さず手で頼んだ PLAN も番号が合えば開く。)
3. **開き方** — options: (A) `cmux markdown open` = 右分割・ライブリロード（R4） /
   (B) `cmux open --no-focus` = Claude のいるペインにプレビュータブを追加（分割は増えないが、
   端末と同じペインなので見るにはタブ切替が必要） / (C) 初回だけ右分割し、2 回目以降はその
   ビューアペインにタブ追加（ペイン ID の記録が必要で実装が増える）。
   (Recommendation: A で始め、V3 の結果が悪ければ C。分割方向 `right` / `down` とフォーカス
   （既定: 奪わない）も希望があれば指定を。)
4. **スキル名** — options: `open-in-cmux` / `open-files-in-cmux`（プロジェクト名と同じ）/ その他。
   (Recommendation: `open-in-cmux`。)
5. **`~/.claude-personal/settings.json` への hook 追加を誰が行うか** — options: (a) 実装時に
   Claude が Edit ツールで追加（その場で許可を求める） / (b) `SKILL.md` に貼り付け用 JSON を
   載せ、ユーザーが追加。
   (Recommendation: a。symlink（ステップ 3）は F6 によりどちらの場合もユーザー作業。)
