# RESULT6 — PLAN6 の実装: 右側に既にペインがあれば、そのペインにタブで開く

Source: チャットでの指示「implement @03_plans/PLAN6.md and write results in RESULT6.md」（仕様: `03_plans/PLAN6.md`）. Date: 2026-11-14

## Task

PLAN6 を実装する: ビューアを開くとき、基準ペインの右側に既にペインがあれば分割せずそのペインに
タブで開き、無いときだけ右に分割する。監視・hook・CLI の 3 モード共通。

## Result

**コード・テスト・ドキュメントは完了。実際にファイルを開く確認（V2〜V5）は未実施**で、ユーザーが
cmux で行う必要がある。開き先の決定までは、このワークスペースの実際のレイアウトで確認した
（下の「実機での確認」）。

**動作中の監視は再起動が必要**: 起動済みの `--watch` は古いコードのまま動いている。Ctrl-C で止めて
起動し直す。

### 実装ステップごとの状態

| PLAN6 のステップ | 状態 |
|---|---|
| 1. `open_in_cmux.py`: レイアウト取得、開き先の決定、分岐とフォールバック | 完了 |
| 2. テスト | 完了。23 件追加、合計 59 件 pass |
| 3. `SKILL.md` / `README.md` / `CLAUDE.md` の更新 | 完了 |
| 4. Verification | V1 完了。V2〜V5 はユーザーが cmux で実施 |
| 5. commit | ユーザー |

### 変更したファイル

| ファイル | 内容 |
|---|---|
| `.claude/skills/open-in-cmux/open_in_cmux.py` | `cmux tree --json` でレイアウトを読み、開き先を決めてから開くように変更。純粋な関数 `choose_target`（R1）と、`read_layout` / `plan_open` / `split_command` / `run_cmux` を追加。`open_file` は開き方（`tab in pane:…` / `new split`）を返す |
| `.claude/skills/open-in-cmux/test_open_in_cmux.py` | `ChooseTarget`（10 件、cmux なし）、`Placement`（9 件、CLI / hook）、`WatchPlacement`（4 件）を追加。偽の `cmux` が `tree` に応答するように変更。監視テストの共通部分を `WatchBase` に分離 |
| `.claude/skills/open-in-cmux/SKILL.md` / `README.md` | 「開く場所」の規則、監視を起動する場所（Claude と同じペインの別タブ）、`--surface` の意味の変更 |
| `CLAUDE.md` | 仕様の一覧に PLAN6 を追加 |

変更していないもの: `~/.claude-personal/settings.json`、管理ポリシーのファイル、`/prompt` スキル。

### 動作

| 状況 | 実行されるコマンド |
|---|---|
| 基準ペインの右にペインがある | `cmux open <path> --workspace … --pane <右のペイン> --no-focus` |
| 右にペインが無い | `cmux markdown open <path> --workspace … --surface <基準ペインで選択中の surface> --focus false` |
| レイアウトを読めない / 基準ペインが見つからない | 従来の呼び出し（`cmux markdown open …`）。理由を stderr に 1 行 |

基準ペイン: 監視は起動したターミナルのあるペイン（`--surface` で上書き）、hook / CLI は
`CMUX_SURFACE_ID` のあるペイン。

### Verification

| # | 結果 |
|---|---|
| V1 | **pass**: `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` → `Ran 59 tests … OK`（2 回実行して 2 回とも） |
| V2 | 未実施（右にペインがある状態で `/prompt` → タブで開く、`horizontal` = 左右の確定） |
| V3 | 未実施（右にペインが無い状態で 2 回 → 1 回目は分割、2 回目はタブ）。テストでは偽のレイアウトで同じ流れを確認 |
| V4 | 未実施（`cmux open` で開いたタブのライブリロード） |
| V5 | 未実施（右側が上下分割で、markdown タブのあるペインを選ぶ）。テストでは確認 |

### 実機での確認（開き先の決定まで）

このセッションのワークスペース（左に Claude のペイン、右に markdown タブのあるペイン）で、
実際の `cmux tree --json` を読ませて決定だけを行った（ファイルは開いていない）:

```
how: tab in pane:1000040059
cmd: cmux open <path> --workspace <id> --pane pane:1000040059 --no-focus
```

実際のレイアウトの JSON を解釈でき、右のペインが選ばれることを確認した。このコマンド自体が
タブを追加することは PLAN5 の調査時に確認済み。サンドボックスを外した読み取り専用のコマンド
1 回で行った。

### PLAN6 からの差分

- **既存テストの変更**: 監視の stdout の行に開き方が付くようになったため（R6）、その行を検証する
  既存テスト 1 件の期待値を `open: … (new split)` に変更した。他の既存 35 件は変更なし。
- **`--surface` の意味**: 「分割元の surface」から「基準ペインを決める surface」に変わった
  （PLAN6 の設計どおり）。`cmux tree` に出る `surface:<n>` の形で渡す。UUID を渡した場合、
  `cmux tree --json` の出力に UUID が含まれないため一致せず、フォールバック（その surface から
  分割）になる。
- **タイムアウト**: cmux の呼び出しが 2 回になったので、cmux が無応答だと最大 10 秒かかる。
  hook の登録は `timeout: 10` なので、その場合は hook 側で打ち切られる（Claude は止まらない）。

### 残作業（ユーザー）

1. 動作中の監視を止めて起動し直す。Claude と同じペインの別タブで起動する。
2. V2〜V5 を実施する。最初は V2 と V4（タブで開くか、編集が表示に反映されるか）。
3. commit。

## Items Requiring Confirmation（要確認）

1. **PLAN6 の Status** — options: (a) V2 が通ったら `Implemented · SHA: <commit>` にする /
   (b) 今 `Implemented` にする。
   (Recommendation: a。)
2. **V4 でライブリロードしなかった場合** — PLAN6 の Verification に書いたとおり、
   「`cmux markdown open` で開いてから `cmux move-surface` で右のペインに移す」方式を新しい PLAN に
   するか。実機で見てから判断。
3. **`--surface` に UUID を渡せるようにするか** — options: (a) 今のまま（`surface:<n>` のみ）/
   (b) UUID でも基準ペインを見つけられるようにする（cmux の `--id-format both` が `tree --json` に
   効くかの確認が必要）。
   (Recommendation: a。必要になってからでよい。)
