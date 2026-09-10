# Axiom for herdr

**Main thinks. Astra designs. Luna executes. Sol reviews.**

Codexの担当作業を、herdrの分割ペインで同時に見られるプラグインです。
Mainが必要な担当を起動し、結果を回収したら担当ペインを閉じます。
既存の[Axiom](https://github.com/phni3j9a/axiom)の役割分担とレビュー方針を引き継ぎます。

初版 `v0.1.0`。herdr上の実動作・画面・モデル稼働の確認はユーザー環境で行う前提です。
このリリースで確認するのはパッケージ構成、Python構文、CLIヘルプです。

## 動作方針

| 項目 | 動作 |
|---|---|
| Main | 左側で判断・分割・統合・最終受理を担当 |
| 通常の調査・実装 | Luna MAXを右側の別ペインで起動 |
| 重要なUIデザイン | Astra MAXを別ペインで起動 |
| 独立レビュー | Sol XHIGH。再レビューは同じセッションを継続 |
| 並列数 | 固定上限なし。Mainが作業の独立性と調整コストから判断 |
| 担当の終了 | Mainが結果を回収し、完了した担当ペインを閉じる |
| 入力待ち・起動失敗 | 確認できるよう表示を残す |
| 手動操作 | 担当へ直接指示でき、手動で変更した配置を全体リセットしない |

全員が独立した対話型Codexとして動きます。Mainのサブエージェント機能で
隠れて実行する構成にはしていません。Mainが補助スクリプトを呼んで管理し、
常駐のオーケストレーターやダッシュボードは同梱しません。

## Luna MAXの経済性

Axiom v0.1.9から引き継ぐ設計上の前提として、通常のLuna MAX担当の利用コストは、
委譲判断では**ほぼ無料として扱います**。
**Mainのコンテキストは高価であり、その節約をLunaの利用量節約より優先します。**

Mainのコンテキストを守る、大量の調査ログを担当側に留める、独立した調査を行う、
有用な作業を並列に進める、といった効果があるなら、Lunaのトークンや利用量を
節約するためだけに委譲を控えません。委譲を制約するのは、調整コスト、待ち時間、
作業の重複・競合、依存順序、統合の複雑さです。固定の担当数上限は設けず、
独立して進められる仕事とこれらのコストからMainが判断します。

担当を増やすこと自体を目的に作業を細分化しません。調整コストが効果を上回る
単純な作業はMainで行い、意図・アーキテクチャ・統合・最終受理もMainが担います。

これはこのバージョンの経済性に関する明示的な仮定です。実際の料金が無料であることや、
将来も同じ料金であることを保証しません。Codexやモデルの経済性が大きく変わった場合は、
この方針を更新します。

## 必要な環境

- LinuxまたはmacOSを初版の対象とします。
- Python 3.10以上。追加のpipパッケージは不要です。
- 同じホストで動くherdrとCodex CLI。両方が`PATH`から見えること。
- herdr内のペインでMainのCodexを起動すること。
- Codexのプラグイン機能と、上記モデルを利用できること。

実装は2026年9月のherdr公式CLI/API定義を参照しています。対応する操作は
`pane current/layout/split/rename/close`、`agent list/start/prompt/read`です。
herdrの最低対応バージョンは実機確認後に確定します。
Codexの起動・導入引数は手元のCLI `0.154.0-alpha.3` のヘルプと公開設定定義で確認しています。

SSH先で使う場合は、そのSSH先でMain・herdr・各担当を動かしてください。
プラグインはCodexの承認・sandbox設定を変更せず、bypassフラグも付けません。
各担当はユーザーのCodex設定を読みます。モデルとreasoning effortのみ役割で指定し、
報告用ディレクトリを`--add-dir`で追加します。

## インストール

リポジトリ名は`axiom_for_herdr`、Codex内のプラグイン名・スキル名は
命名規則に合わせた`axiom-for-herdr`です。

```bash
git clone https://github.com/phni3j9a/axiom_for_herdr.git
cd axiom_for_herdr
codex --enable plugins plugin marketplace add "$PWD" --json
codex --enable plugins plugin add axiom-for-herdr@personal --json
```

同梱のリポジトリ用カタログ名は`personal`です。
インストール後、新しいCodexセッションをherdr内で開始してください。
このプラグインを使う作業では、通常のAxiomとの二重委譲を避けるため、初回は明示指定を推奨します。

```text
$axiom-for-herdr:axiom-for-herdr

このプロジェクトを調査して、必要な変更を実装してください。
担当の作業はherdrの別ペインで見えるようにしてください。
```

通常の自動選択も有効です。`AXIOM_HERDR_ROLE`または依頼内容で担当として識別された
Codexは、さらに別の担当を起動せず、割り当てられた作業を実行します。

## 結果の扱い

依頼ごとにIDを付け、短いMarkdownの報告をJSONの受け渡しファイルへ格納します。
Mainは報告を読み、差分や検証結果を確認してから、`close`操作で担当を終了します。
Reviewerはレビュー全体が終わるまで保持します。

herdrの`done`だけでペインを閉じることはありません。報告回収後の内容変更、
担当の稼働状態、元の端末との一致を補助スクリプトで確認します。
実装の正しさやレビュー指摘の採否はMainが判断します。

ユーザーが担当へ直接追加指示を出した場合、担当は`begin`で古い報告を無効化し、
作業後に追加指示とその影響を含めて再報告します。この処理は担当の指示遵守に依存し、
キー入力とペイン終了を完全に同期する仕組みではありません。

報告と起動記録は実行ごとの一時ディレクトリに残り、ペインを閉じてもすぐには削除しません。
OSによる一時ファイル削除の対象にはなります。重要な結果はMainの報告やプロジェクト文書へ残してください。

## 実機確認

[実機確認手順](docs/MANUAL_VALIDATION.md)に、1担当の起動、並列実行、
同じReviewerでの再確認、直接介入、入力待ちを確認する手順をまとめています。

補助スクリプトの入口は次です。

```bash
python3 plugins/axiom-for-herdr/skills/axiom-for-herdr/scripts/axiom_herdr.py --help
```

Mainが使う詳しいコマンドは[operations.md](plugins/axiom-for-herdr/skills/axiom-for-herdr/references/operations.md)、
レビュー方針は[review.md](plugins/axiom-for-herdr/skills/axiom-for-herdr/references/review.md)にあります。

## 構成

| ファイル | 役割 |
|---|---|
| `.agents/plugins/marketplace.json` | リポジトリのインストール用カタログ |
| `plugins/axiom-for-herdr/.codex-plugin/plugin.json` | Codexプラグイン定義 |
| `plugins/axiom-for-herdr/skills/axiom-for-herdr/SKILL.md` | Mainと担当の指針 |
| 同スキルの`references/` | 操作・レビューの詳細 |
| 同スキルの`scripts/axiom_herdr.py` | herdr操作と報告の受け渡し |

## 参照・ライセンス

- [Axiom](https://github.com/phni3j9a/axiom) — MIT。レビューと委譲の方針を継承。
- [Herdr agent automation](https://herdr.dev/docs/agent-automation/)
- [Herdr CLI reference](https://herdr.dev/docs/cli-reference/)

MIT License。herdrおよびCodex本体のコードは同梱しません。
