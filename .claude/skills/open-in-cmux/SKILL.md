---
name: open-in-cmux
description: /prompt が生成した PLAN<n>.md / RESULT<n>.md を cmux の markdown ビューアに自動表示する（監視プロセス、または PostToolUse hook）。手動で markdown ファイルを cmux に開くときにも使う。
---

# /open-in-cmux

Claude Code が `PROMPT<n>.md` を実行して `PLAN<n>.md` / `RESULT<n>.md` を書いたとき、そのファイルを
cmux の markdown ビューア（右分割・ライブリロード・フォーカスは端末のまま）で開く。

自動表示はこのスキルを呼ばなくても動く。スキル本体（この手順）は、起動方法の案内と、手動で開く
ときに使う。仕様: `open-files-in-cmux` プロジェクトの `03_plans/PLAN2.md`（hook / 手動）と
`03_plans/PLAN4.md`（監視）。

## 2 つの自動表示方式

| 方式 | 使う場面 | 起動 |
|---|---|---|
| **監視**（`--watch`） | 管理ポリシーの `allowManagedHooksOnly` でユーザー hook が無効な環境 | プロジェクトごとにユーザーが cmux のターミナルで起動 |
| **hook**（PostToolUse） | ユーザー hook が動く環境 | `settings.json` に登録すれば常時 |

**併用しない。** hook が動く環境で監視も起動すると、同じファイルが 2 回開く。hook が有効かどうかは
Claude Code の `/hooks` で確認できる。

どちらの方式も、開くのは次を満たすファイルだけ:

- ファイル名が `PLAN<n>.md` / `RESULT<n>.md`（無番号 = 1）。
- 同じ番号の `PROMPT<n>.md` がある。探索先はプロジェクトルートの `02_prompts/`、無ければ出力と同じ
  ディレクトリ。番号は整数比較（`PLAN3.md` ↔ `PROMPT03.md`）。

## 監視: `--watch`

プロジェクトのルートで、**cmux の別ターミナル**（分割またはタブ）から起動する:

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py --watch
```

- `03_plans/` と `04_results/`（どちらも無ければカレントディレクトリ）を 1 秒ごとに見て、起動後に
  新しく現れたファイルだけを開く。起動時からあるファイル、既存ファイルの書き換えでは開かない。
- 止めるときは Ctrl-C。プロジェクトごとに 1 つ（2 つ起動すると 2 回開く）。
- Claude 以外が作ったファイル（手で作成、`git pull` で現れたもの）も条件を満たせば開く。
- オプション: `[dir]`（プロジェクトルート）、`--interval <秒>`、`--surface <id|ref>`（分割元の
  surface。既定はフォーカス中の surface）。
- cmux の外では理由を出して exit 1。

**Claude の Bash ツールからは起動しない。** サンドボックスが cmux のソケットを遮断するため動かない。
ユーザーに上のコマンドを cmux のターミナルで実行するよう案内する。

## hook

Write ツールの PostToolUse hook として `open_in_cmux.py`（引数なし）を登録する。Edit では発火
しない。失敗しても Claude を止めない（常に exit 0。理由は stderr に 1 行）。

`~/.claude-personal/settings.json` の `hooks.PostToolUse`:

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

管理ポリシーが `allowManagedHooksOnly: true` を設定している環境では、このエントリは読み込まれず、
何も起きない（エラーも出ない）。その場合は監視を使う。symlink より先に hook を登録しない:
スクリプトが無いと `python3` が exit 2 を返す。

## 手動で開く: `/open-in-cmux <path>...`

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>...
```

ファイル名の条件なしで、渡した markdown を同じ方法で開く。

Bash ツールのサンドボックス内からは cmux のソケットに繋がらない（`Operation not permitted`）。
このコマンドがそのエラーを stderr に出したら、サンドボックスが原因だと伝え、ユーザーに
`! python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py <path>` の実行を案内する。

引数が無いときは、何を開くかをユーザーに尋ねる。

## 導入

symlink を作る（ユーザーが実行）:

```
ln -s "<open-files-in-cmux リポジトリ>/.claude/skills/open-in-cmux" ~/.claude-personal/skills/open-in-cmux
```

そのうえで、監視を起動するか、hook を登録する。

## テスト

```
python3 .claude/skills/open-in-cmux/test_open_in_cmux.py
```

偽の `cmux` を PATH に置くので、実際の cmux には触れない。
