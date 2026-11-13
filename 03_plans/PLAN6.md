# PLAN6 — `open-in-cmux`: 右側に既にペインがあれば、分割せずそのペインにタブで開く

> Status: Confirmed · Depends-on: PLAN4

Source: `02_prompts/PROMPT6.md`（[[PLAN5]] の要確認への回答）. Date: 2026-11-14

Replaces [[PLAN5]]（PLAN5 は `Superseded by: PLAN6`）。PROMPT6 が PLAN5 を名指ししている。
[[PLAN4]]（監視モード）と [[PLAN2]]（hook / CLI モード）の上に載せる改良で、どちらも置き換えない。
このファイルは自己完結しており、PLAN5 を読まずに実装できる。

## Goal

ビューアを開くとき、**基準ペインの右側に既にペインがあれば、新しく分割せずそのペインにタブで開く。**
右側にペインが無いときだけ、従来どおり右に分割する。

背景（PROMPT5 の実機確認）: 監視モードは動作した（PLAN4 の V2 成功）。ただし、もともと分割された
ペインがある状態で Claude のいるペインからさらに右に分割され、全体で 3 分割になり見づらかった。

## Decisions

PROMPT6 による、PLAN5 の要確認への決定:

| # | 項目 | 決定 |
|---|---|---|
| 1 | 「右側」の基準にするペイン | (a) 監視を起動したターミナルのあるペイン。`--surface` で上書きできる |
| 2 | 右側がさらに分割されているとき | (b) 既に `markdown` 型のタブがあるペインを優先。無ければ左上のペイン |
| 3 | 適用するモード | (a) 監視・hook・CLI の 3 モードすべて |
| 4 | 古いタブ | (a) 何もしない。開くたびにタブが増える |
| 5 | PLAN4 の Status | (a) `Implemented · SHA: 2a99bcb` にする（このプランの作成時に反映済み） |
| 6 | PROMPT5 の出力を PLAN にしたこと | (a) PLAN でよい |

## 前提として確定している事実（2026-11-14、実機で確認）

| # | 事実 |
|---|---|
| F1 | `cmux tree --json --workspace <id>` はワークスペースのレイアウトを返す。`windows[].workspaces[].layout` は二分木で、節は `{"direction": "horizontal"\|"vertical", "split": <比率>, "children": [<節>, <節>]}`、葉は `{"pane": {"ref": "pane:…"}}`。同じ階層の `panes[]` に各ペインの `ref` / `selected_surface_ref` / `surfaces[]`（`ref`, `type`: `terminal` / `markdown` …）がある |
| F2 | 同じ出力の `caller.pane_ref` / `caller.surface_ref` は、コマンドを実行した surface（`CMUX_SURFACE_ID`）のペインと surface |
| F3 | `cmux open <path> --pane <pane ref> --no-focus` は、そのペインに `markdown` 型のタブを追加する。分割は増えず、追加したタブがそのペイン内で選択され、キーボードのフォーカスは元のペインに残る |
| F4 | 現在の実装は `cmux markdown open <path> --workspace … [--surface …] --focus false` を呼び、常に新しい分割を作る。`--surface` は分割元（監視モードでは既定で付けない = フォーカス中の surface、hook / CLI モードでは `CMUX_SURFACE_ID`） |
| F5 | Claude の Bash サンドボックスからは cmux ソケットに繋がらない。監視はユーザーが cmux のターミナルで起動するので繋がる（PLAN4 の V2 で確認済み） |

未確認（Verification で確定させる）:

- `direction: "horizontal"` が「左右に並ぶ」（`children[0]` が左、`children[1]` が右）を意味すること。
- `cmux open` で開いたタブが、`cmux markdown open` のビューアと同じくライブリロードするか
  （surface の型は同じ `markdown`）。

## 設計

### 開き方の決定

ファイルを開くたびに次の順で決める:

1. `cmux tree --json --workspace $CMUX_WORKSPACE_ID` でレイアウトを取得する。
2. **基準ペイン**を決める:

   | モード | 基準ペイン |
   |---|---|
   | 監視（`--surface` なし） | `caller.pane_ref`（監視を起動したターミナルのあるペイン） |
   | 監視（`--surface <値>` あり） | `panes[].surfaces[]` の `ref`（JSON に `id` があればそれも）が `<値>` に一致する surface のあるペイン |
   | hook / CLI | `caller.pane_ref`（`CMUX_SURFACE_ID` のあるペイン = Claude のいるペイン） |

3. **右側の部分木**を探す: 基準ペインの葉から根に向かって辿り、`direction` が `horizontal` で、
   基準ペインが `children[0]` 側にある最初の節を見つける。その `children[1]` が右側の部分木。
4. **右側の部分木から開き先のペインを選ぶ**: 部分木の葉を `children[0]` 優先の深さ優先で並べ、
   `markdown` 型の surface を持つ最初のペイン。無ければ最初の葉（左上のペイン）。
5. **開き先があれば**: `cmux open <絶対パス> --workspace … --pane <開き先の ref> --no-focus`。
6. **右側の部分木が無ければ**: `cmux markdown open <絶対パス> --workspace … --surface <基準ペインの
   selected_surface_ref> --focus false` で、基準ペインの右に分割する。次のファイルからはこの新しい
   ペインが右側になるので、以降はタブで開く。
7. **フォールバック**: 1 が失敗・タイムアウトした、JSON が想定と違う、基準ペインがレイアウトに
   見つからない場合は、F4 の従来の呼び出しをそのまま行い、理由を stderr に 1 行出す。

### 要件

| # | 要件 |
|---|---|
| R1 | 3・4 は純粋な関数（`layout`, `panes`, 基準ペインの ref → 開き先の ref または None）にして、cmux なしでテストする |
| R2 | 監視・hook・CLI の 3 モードで同じ決定手順を使う |
| R3 | hook / CLI モードの約束は変えない: 常に exit 0、stdout に何も出さない、cmux 外では何もしない |
| R4 | cmux の呼び出しはファイルごとに 2 回（`tree` + 開く）。それぞれ 5 秒でタイムアウト |
| R5 | 監視モードの他の動作（対象判定、起動時からあるファイルは開かない、既存ファイルの書き換えでは開かない、cmux 失敗後も継続、cmux 外で exit 1 …）は変えない |
| R6 | 監視の stdout の 1 行に、どちらで開いたかを出す（例: `open: 04_results/RESULT7.md (tab in pane:…)` / `(new split)`） |

### 既知の挙動（対象外として受け入れる）

- ファイルを開くたびに右ペインのタブが 1 つ増える。古いタブは自動では閉じない。同じファイルを
  既に開いていても新しいタブを作る。
- 右側のペインがビューアでなくても（ターミナルやブラウザでも）、そこにタブを追加する。
- 基準ペインの下や左にしかペインが無い場合は、右側なしとして分割する。
- 監視を右端のペインで起動すると、常に「右側なし」になり毎回分割する。監視は Claude と同じ
  ペイン（別タブ）か、同じ列で起動する。必要なら `--surface` で Claude の surface を渡す。

## 実装ステップ

1. `open_in_cmux.py`: レイアウト取得、開き先の決定（R1）、開き方の分岐とフォールバックを追加。
2. `test_open_in_cmux.py`:
   - 決定関数の単体テスト: 2 ペイン / 基準が右端 / 上下分割のみ / 入れ子（右側が上下分割）で
     `markdown` を持つペインを優先 / `markdown` が無ければ左上 / 基準が入れ子の中にある /
     基準が見つからない。
   - 偽の `cmux` に `tree --json` の応答を持たせた分岐テスト（3 モード）: 右側あり → `open --pane`、
     なし → `markdown open --surface <selected>`、`tree` 失敗・不正な JSON → フォールバック、
     `--surface` での基準の上書き。
   - 既存 36 件は、期待する動作が変わらないものは変更せず pass のまま。
3. `SKILL.md` / `README.md` / `CLAUDE.md` を更新（開き方の規則、監視を起動する場所）。
4. Verification。V2 以降はユーザーが cmux で実施。
5. commit はユーザー。

## Verification

| # | 確認 | 期待 |
|---|---|---|
| V1 | `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` | 全件 pass |
| V2 | 左に Claude、右に別ペインがある状態で、Claude と同じペインの別タブで監視を起動し、`/prompt` を実行 | 右ペインにタブで開く。分割は増えない。フォーカスは Claude のまま。**`horizontal` = 左右はここで確定する** |
| V3 | 右にペインが無い状態で同じことを 2 回 | 1 回目は右に分割、2 回目はそのペインにタブ |
| V4 | V2 で開いたタブのファイルを編集 | 表示が更新される（ライブリロード）。更新されない場合は「`markdown open` で開いてから `move-surface` で移す」方式を新しい PLAN にする |
| V5 | 右側が上下に分割され、下のペインにだけ markdown タブがある状態 | 下のペインに開く |

## Items Requiring Confirmation（要確認）

None.
