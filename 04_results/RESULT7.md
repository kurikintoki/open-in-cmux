# RESULT7 — PLAN6 を Implemented にする（V2 が実機で pass）

Source: `02_prompts/PROMPT7.md`（`RESULT6` の要確認への回答）. Date: 2026-11-14

## Task

`RESULT6` の要確認 1 への回答「a。V2 は pass」を反映する: 実機確認が通ったので、PLAN6 の Status を
`Implemented` にする。

## Result

| ファイル | 変更 |
|---|---|
| `03_plans/PLAN6.md` | ヘッダを `> Status: Implemented · Depends-on: PLAN4 · SHA: 44e1787` に変更（他は変更なし） |

`44e1787` は PLAN6 を実装した commit（`feat: open in the pane already on the right as a tab (PLAN6)`）。
`03_plans/` に `INDEX.md` は無いので、再生成は行っていない。

### PLAN6 の Verification の状況

| # | 状態 |
|---|---|
| V1 | pass（59 テスト。`RESULT6` に記録） |
| V2 | **pass**（PROMPT7 でのユーザー報告: 右にペインがある状態で、右のペインにタブで開いた）。これにより、レイアウトの `direction: "horizontal"` が左右の並びを表すことも確定した |
| V3 | 報告なし（右にペインが無い状態で 2 回 → 1 回目は分割、2 回目はタブ） |
| V4 | 報告なし（`cmux open` で開いたタブのライブリロード） |
| V5 | 報告なし（右側が上下分割のとき、markdown タブのあるペインを選ぶ） |

### 各 PLAN の現在の Status

| PLAN | Status |
|---|---|
| PLAN | Superseded（→ PLAN2） |
| PLAN2 | Confirmed（hook 方式。このマシンでは管理ポリシーにより hook が動かないため、実機確認ができていない） |
| PLAN3 | Superseded（→ PLAN4） |
| PLAN4 | Implemented · SHA: 2a99bcb |
| PLAN5 | Superseded（→ PLAN6） |
| PLAN6 | Implemented · SHA: 44e1787 |

## Items Requiring Confirmation（要確認）

`RESULT6` の要確認のうち、PROMPT7 が答えていない 2 件を引き継ぐ。

1. **（`RESULT6` 要確認 2）V4: タブがライブリロードするか** — PROMPT7 に結果の記載なし。
   開いたタブのファイルを編集して、表示が更新されるかを確認してほしい。更新されない場合は
   「`cmux markdown open` で開いてから `cmux move-surface` で右のペインに移す」方式を新しい PLAN に
   するか。options: (a) 更新された → 対応不要 / (b) 更新されない → 新しい PLAN を作る。
2. **（`RESULT6` 要確認 3）`--surface` に UUID を渡せるようにするか** — options: (a) 今のまま
   （`surface:<n>` のみ）/ (b) UUID でも基準ペインを見つけられるようにする。
   (Recommendation: a。必要になってからでよい。)
