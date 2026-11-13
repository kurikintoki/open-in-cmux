# RESULT8 — `RESULT7` の要確認 2 件をクローズ（ライブリロード確認済み、`--surface` は現状維持）

Source: `02_prompts/PROMPT8.md`（`RESULT7` の要確認への回答）. Date: 2026-11-14

## Task

`RESULT7` の要確認 2 件への回答を反映する。

## Result

どちらの回答も、コードやドキュメントの変更を必要としない。**このファイル以外は何も変更していない。**

| `RESULT7` の要確認 | PROMPT8 の回答 | 結論 |
|---|---|---|
| 1. V4: `cmux open` で開いたタブがライブリロードするか | 「V4 ライブリロード成功」 | 対応不要。「`cmux markdown open` で開いてから `cmux move-surface` で移す」方式の PLAN は作らない |
| 2. `--surface` に UUID を渡せるようにするか | a | 現状維持。`--surface` は `surface:<n>` の形だけを受け付ける |

### PLAN6 の Verification の最終状況

| # | 状態 |
|---|---|
| V1 | pass（59 テスト。`RESULT6`） |
| V2 | pass（ユーザー確認。`RESULT7`）: 右にペインがある状態で、右のペインにタブで開く |
| V3 | 報告なし（右にペインが無い状態で 2 回 → 1 回目は分割、2 回目はタブ）。偽のレイアウトを使った自動テストでは確認済み |
| V4 | **pass**（ユーザー確認。PROMPT8）: タブで開いたファイルの編集が表示に反映される |
| V5 | 報告なし（右側が上下分割のとき、markdown タブのあるペインを選ぶ）。自動テストでは確認済み |

PLAN5 / PLAN6 で「未確認」としていた 2 点（`horizontal` = 左右の並び、タブのライブリロード）は、
V2 と V4 の結果でどちらも確定した。

### プロジェクトの現状

- `open-in-cmux` スキルは、監視モード（`open_in_cmux.py --watch`）で実機動作を確認済み。
  PLAN4 と PLAN6 は `Implemented`。
- PLAN2（hook 方式）は `Confirmed` のまま。このマシンでは管理ポリシー（`allowManagedHooksOnly`）に
  より hook が動かないため、hook 経由の実機確認はできていない（PLAN4 の Decisions 4 のとおり）。
- 未解決の要確認は無い。

## Items Requiring Confirmation（要確認）

None.
