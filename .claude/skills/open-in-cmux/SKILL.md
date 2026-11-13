---
name: open-in-cmux
description: /prompt が生成した PLAN<n>.md / RESULT<n>.md を cmux の markdown ビューアに自動表示する（PostToolUse hook）。手動で markdown ファイルを cmux に開くときにも使う。
---

# /open-in-cmux

Claude Code が `PROMPT<n>.md` を実行して `PLAN<n>.md` / `RESULT<n>.md` を書いたとき、そのファイルを
cmux の markdown ビューア（右分割・ライブリロード・フォーカスは端末のまま）で開く。

自動表示は **hook** が行う。このスキルを呼ぶ必要はない。スキル本体（この手順）は、手動で開くときと
導入・無効化の案内に使う。仕様: `open-files-in-cmux` プロジェクトの `03_plans/PLAN2.md`。

## 自動表示の条件

`open_in_cmux.py` は Write ツールの PostToolUse hook として動き、次をすべて満たすときだけ開く:

- ファイル名が `PLAN<n>.md` / `RESULT<n>.md`（無番号 = 1）。
- 同じ番号の `PROMPT<n>.md` がある。探索先はプロジェクトルートの `02_prompts/`、無ければ出力と同じ
  ディレクトリ。番号は整数比較（`PLAN3.md` ↔ `PROMPT03.md`）。
- cmux の中で動いている（`CMUX_WORKSPACE_ID` があり、`cmux` CLI が見つかる）。

Edit では発火しない（Status 行の書き換えで古い PLAN が開かないように）。失敗しても Claude を
止めない（常に exit 0。理由は stderr に 1 行）。

## 手動で開く: `/open-in-cmux <path>...`

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>...
```

ファイル名の条件なしで、渡した markdown を同じ方法で開く。

**Bash ツールのサンドボックス内からは cmux のソケットに繋がらない**（`Operation not permitted`）。
このコマンドがそのエラーを stderr に出したら、サンドボックスが原因だと伝え、ユーザーに
`! python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>` の実行を案内する。

引数が無いときは、何を開くかをユーザーに尋ねる。

## 導入

1. symlink を作る（ユーザーが実行）:

   ```
   ln -s "<open-files-in-cmux リポジトリ>/.claude/skills/open-in-cmux" ~/.claude-personal/skills/open-in-cmux
   ```

2. `~/.claude-personal/settings.json` の `hooks.PostToolUse` に追加する:

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

3. cmux 内で Claude Code の新しいセッションを開始する。

symlink より先に hook を登録しない: スクリプトが無いと `python3` が exit 2 を返し、Write のたびに
hook エラーが出る。

## 無効化

`settings.json` から上の hook エントリを削除する。symlink は残してよい。

## テスト

```
python3 .claude/skills/open-in-cmux/test_open_in_cmux.py
```

偽の `cmux` を PATH に置くので、実際の cmux には触れない。
