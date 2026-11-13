---
name: open-in-cmux
description: /prompt が生成した PLAN<n>.md / RESULT<n>.md を cmux の markdown ビューアに自動表示する（監視プロセス、または PostToolUse hook）。手動で markdown ファイルを cmux に開くときにも使う。
---

# /open-in-cmux

Claude Code が `PROMPT<n>.md` を実行して `PLAN<n>.md` / `RESULT<n>.md` を書いたとき、そのファイルを
cmux の markdown ビューアで開く（フォーカスは端末のまま）。

自動表示はこのスキルを呼ばなくても動く。スキル本体（この手順）は、起動方法の案内と、手動で開く
ときに使う。仕様: `open-files-in-cmux` プロジェクトの `03_plans/PLAN2.md`（hook / 手動）、
`03_plans/PLAN4.md`（監視）、`03_plans/PLAN6.md`（開く場所）。

## 開く場所

3 つのモード（監視・hook・手動）で共通:

- **基準ペイン**（スクリプトを実行したターミナルのあるペイン）の**右側に既にペインがあれば、
  そのペインにタブで開く**。分割は増えない。右側がさらに分割されていれば、既に markdown の
  タブがあるペインを優先し、無ければ左上のペイン。
- 右側にペインが無ければ、基準ペインを右に分割して開く。次のファイルからはそのペインにタブで開く。
- レイアウトを取得できないときは、新しい分割で開く（理由を stderr に 1 行）。

開くたびにタブが 1 つ増える。古いタブは自動では閉じない。

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

プロジェクトのルートで、**Claude と同じペインの別タブ**（または同じ列のペイン）のターミナルから
起動する:

```
python3 ~/.claude-personal/skills/open-in-cmux/open_in_cmux.py --watch
```

監視を起動したペインが基準ペインになる。右端のペインで起動すると、右側が無いので毎回分割する。
別の場所で起動したいときは `--surface <Claude の surface>` で基準を指定する。

- `03_plans/` と `04_results/`（どちらも無ければカレントディレクトリ）を 1 秒ごとに見て、起動後に
  新しく現れたファイルだけを開く。起動時からあるファイル、既存ファイルの書き換えでは開かない。
- 止めるときは Ctrl-C。プロジェクトごとに 1 つ（2 つ起動すると 2 回開く）。
- Claude 以外が作ったファイル（手で作成、`git pull` で現れたもの）も条件を満たせば開く。
- オプション: `[dir]`（プロジェクトルート）、`--interval <秒>`、`--surface <ref>`（基準ペインを
  決める surface。`cmux tree` に出る `surface:<n>` の形で渡す。既定は監視を起動した surface）。
- 開くたびに `open: <file> (tab in pane:<n>)` または `(new split)` を 1 行出す。
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
