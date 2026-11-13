# PLAN5 — `open-in-cmux`: 右側に既にペインがあれば、分割せずそのペインにタブで開く

> Status: Draft · Depends-on: PLAN4

Source: `02_prompts/PROMPT5.md`. Date: 2026-11-14

[[PLAN4]]（監視モード）の実機確認の結果を受けた改良。PLAN4 は置き換えない。

PROMPT5 は「プランを作って」とは書いていないが、このプロジェクトでは動作変更は PLAN から始める
規約（`CLAUDE.md`）なので、RESULT ではなく PLAN にした（要確認 6）。

## PROMPT5 の報告

| PLAN4 の確認項目 | 結果（ユーザーが実機で確認） |
|---|---|
| V2 | **成功**。監視から cmux ソケットに繋がり、`/prompt` の出力が表示された |
| V3 | Claude のいるペインから右に分割して表示された。**もともと分割されたペインがあったため、全体で 3 分割になり見づらい** |

要望: **既に右側にペインがある場合は、ビューアをそのペインに表示する。**

## 調査で確定した事実（2026-11-14、このワークスペースの実機で確認）

| # | 事実 |
|---|---|
| F1 | `cmux tree --json --workspace <id>` はワークスペースのレイアウトを返す。`windows[].workspaces[].layout` は二分木で、節は `{"direction": "horizontal"\|"vertical", "split": <比率>, "children": [<節>, <節>]}`、葉は `{"pane": {"ref": "pane:…"}}`。同じ階層の `panes[]` に各ペインの `ref` / `focused` / `surfaces[]`（`ref`, `type`: `terminal` / `markdown` …）がある |
| F2 | 同じ出力の `caller.pane_ref` / `caller.surface_ref` は、コマンドを実行した surface（`CMUX_SURFACE_ID`）のペインと surface |
| F3 | `cmux open <path> --pane <pane ref> --no-focus` は、そのペインに **`markdown` 型のタブを追加**する。分割は増えず、レイアウトは変わらない。追加したタブがそのペイン内で選択され、キーボードのフォーカスは元のペインに残る。出力は `OK files=1 surface=surface:… pane=pane:…` |
| F4 | 現在の実装（PLAN4）は `cmux markdown open <path> --workspace … --focus false` を呼ぶ。これは常に新しい分割を作る（監視モードではフォーカス中の surface から右に分割） |

F1〜F3 の確認のため、このワークスペースの右ペインに `PLAN4.md` のタブを 1 つ開き、確認後に閉じた
（レイアウトとタブは確認前の状態に戻っている）。

未確認（Verification で確定させる）:

- `direction: "horizontal"` が「左右に並ぶ」（`children[0]` が左、`children[1]` が右）を意味すること。
  確認したワークスペースは 2 ペインで `horizontal` だったが、画面上の並びはこちらからは見えない。
- `cmux open` で開いたタブが、`cmux markdown open` のビューアと同じくライブリロードするか。
  surface の型は同じ `markdown`。

## 設計（要確認 1〜3 は推奨案で記述）

### 開き方の決定

ファイルを開くたびに次の順で決める:

1. `cmux tree --json --workspace $CMUX_WORKSPACE_ID` でレイアウトを取得する。
2. **基準ペイン**を決める（要確認 1。推奨: 監視を起動したターミナルのあるペイン = `caller.pane_ref`。
   `--surface` が渡されていればその surface のあるペイン）。
3. レイアウトの木から、基準ペインの**右隣のペイン**を探す:
   基準ペインの葉から根に向かって辿り、`direction` が `horizontal` で、基準ペインが `children[0]`
   側にある最初の節を見つける。その `children[1]` 側が右隣。そこがさらに分割されていれば、
   `children[0]` を辿った先の葉（左上のペイン）を使う（要確認 2）。
4. **右隣があれば**: `cmux open <絶対パス> --workspace … --pane <右隣の ref> --no-focus`（F3）。
5. **右隣が無ければ**: 従来どおり `cmux markdown open …` で右に分割する。分割元は基準ペインの
   選択中の surface（`--surface` で渡す）。次のファイルからはこの新しいペインが右隣になるので、
   以降はタブで開く。
6. 1 が失敗した、JSON が想定と違う、基準ペインがレイアウトに見つからない場合は、5 と同じ
   （PLAN4 の動作）にフォールバックし、理由を stderr に 1 行出す。

### 要件

| # | 要件 |
|---|---|
| R1 | 右隣の探索は純粋な関数（`layout`, 基準ペインの ref → 右隣の ref または None）にして、cmux なしでテストする |
| R2 | 監視モードで適用する。hook モード・CLI モードにも同じ関数を使い、基準ペインは `CMUX_SURFACE_ID` のあるペイン（要確認 3） |
| R3 | hook / CLI モードの約束は変えない: 常に exit 0、stdout に何も出さない。cmux の呼び出しが 1 回から 2 回（`tree` + 開く）に増えるので、それぞれ 5 秒でタイムアウト |
| R4 | 監視モードの他の動作（W1〜W10: 対象判定、起動時のファイルは開かない、cmux 失敗後も継続 …）は変えない |
| R5 | 監視の stdout の 1 行に、どちらで開いたかを出す（例: `open: 04_results/RESULT7.md (tab in pane:…)` / `(new split)`） |

### 既知の挙動（対象外として受け入れる）

- ファイルを開くたびに右ペインのタブが 1 つ増える。古いタブは自動では閉じない。
- 右隣のペインがビューアでなくても（ターミナルやブラウザでも）、そこにタブを追加する。
- 基準ペインの右ではなく下や左にしかペインが無い場合は、右隣なしとして分割する。

## 実装ステップ

1. `open_in_cmux.py`: レイアウト取得、右隣の探索（R1）、開き方の分岐を追加。
2. `test_open_in_cmux.py`: 右隣の探索の単体テスト（2 ペイン / 入れ子 / 基準が右端 / 上下分割のみ /
   基準が見つからない）、偽の `cmux` に `tree --json` の応答を持たせた分岐テスト（右隣あり →
   `open --pane`、なし → `markdown open`、`tree` 失敗 → フォールバック）。既存 36 件は pass のまま。
3. `SKILL.md` / `README.md` / `CLAUDE.md` を更新。
4. Verification。
5. commit はユーザー。

## Verification

| # | 確認 | 期待 |
|---|---|---|
| V1 | `python3 .claude/skills/open-in-cmux/test_open_in_cmux.py` | 全件 pass |
| V2 | 左に Claude、右に別ペインがある状態で監視を起動し、`/prompt` を実行 | 右ペインにタブで開く。分割は増えない。フォーカスは Claude のまま |
| V3 | 右にペインが無い状態で同じことを 2 回 | 1 回目は右に分割、2 回目はそのペインにタブ |
| V4 | V2 で開いたタブのファイルを編集 | 表示が更新される（ライブリロード）。更新されない場合は「`markdown open` で開いてから `move-surface` で移す」方式を新しい PLAN にする |
| V5 | 右側が上下に分割されている状態 | 右上のペインに開く |

## Items Requiring Confirmation（要確認）

1. **「右側」の基準にするペイン** — options: (a) 監視を起動したターミナルのあるペイン
   （Claude と同じペインの別タブ、または同じ列で監視を動かす前提）/ (b) その時点でフォーカスのある
   ペイン / (c) 常に `--surface` で明示させる。
   (Recommendation: a、`--surface` で上書き可。b は、ビューア側にフォーカスがあるときに新しい
   ファイルが来ると「右隣なし」と判定され、ビューアのペインがさらに分割される。)
2. **右側がさらに分割されているときの選び方** — options: (a) 左上のペイン（`children[0]` を辿る）/
   (b) 既に `markdown` 型のタブがあるペインを優先し、無ければ左上。
   (Recommendation: b。ビューアが 1 か所に集まる。実装は数行増えるだけ。)
3. **hook モード・CLI モードにも適用するか** — options: (a) 3 モードすべて / (b) 監視モードだけ。
   (Recommendation: a。hook はこのマシンでは動かないが、動く環境で同じ表示になる。)
4. **古いタブの扱い** — 開くたびにタブが増える。options: (a) 何もしない / (b) 同じファイルの
   タブが既にあれば新しく開かない / (c) このスキルが開いたタブを一定数で古い順に閉じる。
   (Recommendation: a で始める。b は cmux がタブとファイルの対応を返すかが未確認。)
5. **PLAN4 の Status** — V2 が成功したので、`RESULT4` の要確認 1 の推奨どおり
   `Implemented · SHA: 2a99bcb` にしてよいか。options: (a) する / (b) PLAN5 の実装後にまとめて。
   (Recommendation: a。PLAN5 は `Depends-on: PLAN4` なので、a にすると PLAN5 が実装可能になる。)
6. **この出力を PLAN にしたこと** — PROMPT5 は出力の種類を指定していない。options: (a) PLAN で
   よい / (b) RESULT にして直接実装すべきだった。
   (Recommendation: a。)
