# Axiom for herdr

**Main thinks. Astra designs. Luna executes. Sol reviews.**

Codexの担当作業を、herdrの分割ペインで同時に見られるプラグインです。
Mainが必要な担当を起動し、結果を回収したら担当ペインを閉じます。
既存の[Axiom](https://github.com/phni3j9a/axiom)の役割分担とレビュー方針を引き継ぎます。

バージョン系列 `v0.1.0`。共有app-serverで実行するCodexに対応し、
Mainの会話IDとherdr端末を実行記録に結び付けます。検証方法と実機で確認した範囲は
[実機確認手順](docs/MANUAL_VALIDATION.md)を参照してください。

## 動作方針

| 項目 | 動作 |
|---|---|
| Main | 左側で判断・分割・統合・最終受理を担当 |
| 通常の調査・実装 | Luna MAXを右側の別ペインで起動 |
| 重要なUIデザイン | Astra MAXを別ペインで起動 |
| 独立レビュー | Sol XHIGH。再レビューは同じセッションを継続 |
| 子の権限・承認 | 全役割を`workspace-write + never`で起動。権限不足はMainへ報告 |
| 並列数 | 固定上限なし。Mainが作業の独立性と調整コストから判断 |
| 作業待ち | 1つの待機プロセスで全担当を監視。Mainは同じ実行セッションを最大1時間待つ |
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
`pane current/get/list/layout/split/rename/close`、`agent list/start/prompt/read`です。
JSONの`result.pane`、`result.panes`、`result.agent`等を使います。
herdrの最低対応バージョンは実機確認後に確定します。
今回の共有app-server対応はherdr `0.9.0`、Codex CLI `0.154.0`と共有app-server
`0.153.4`の組み合わせで実機確認しています。他バージョンの動作は未確認です。

SSH先で使う場合は、そのSSH先でMain・herdr・各担当を動かしてください。

## 子の権限と承認

Worker・Design・Reviewerは、全員次の起動引数で固定します。

```text
--sandbox workspace-write --ask-for-approval never
```

起動時には`-c default_permissions=":workspace"`も渡します。これは上記の実機環境で
従来の引数だけでは子がフルアクセスになったことへの対処であり、その組み合わせで
実際に`workspace-write / never`と範囲外書き込みの拒否を確認しています。
[Codexの公式説明](https://learn.chatgpt.com/docs/permissions)では旧sandbox指定と
権限プロファイルは合成されず、通常は旧指定が選ばれます。この起動引数を一般的な
設定ファイルの書き方として推奨するものではありません。Codexの更新時は起動引数だけでなく、
実際の子の権限も再確認してください。

MainのAuto・Auto-review・フルアクセスなどの選択には追従せず、Main自身の設定も
変更しません。ユーザー・プロジェクトのCodex設定ファイルを書き換える処理はありません。

`never`は全操作の許可ではなく、設定された範囲内で動き、追加の承認を求めない設定です。
担当するプロジェクトまたは準備済みworktreeを`--cwd`に指定し、報告用の一時ディレクトリを
`--add-dir`で追加します。ネットワーク設定やその他の制限は既存のCodex設定に従い、
プラグインがネットワークを有効化したりbypassフラグを付けたりすることはありません。

権限不足で必要な作業ができない場合、担当は操作内容・対象・エラー・必要な理由・
完了済みの作業を`blocked`として報告し、ペインを残します。Mainは内容を確認し、
自分の権限・承認ルールで対応してから、同じ担当へ続きを依頼します。
子の権限を自動で広げることはありません。

Reviewerも同じsandbox設定です。「プロジェクトは編集せず、報告先だけへ出力する」
制約は役割の指示として適用します。

この固定設定は更新後に新しく起動する担当へ適用します。すでに動いている担当の設定を
途中で変更する機能はありません。

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

## 共有app-serverでMainを登録する

Codexの画面をherdrから起動しても、共有app-serverが実行するコマンドには
`HERDR_PANE_ID`がない場合があります。この場合は、最初にMainの会話と画面を
明示的に結び付けます。app-serverやCCpocketを停止する操作は不要です。

Mainがこの会話を表示している端末を確認してから、次の形で登録します。

```bash
python3 "$helper" init --cwd "$project_dir" \
  --main-pane "$verified_pane_id" \
  --main-terminal-id "$verified_terminal_id" \
  --socket "$herdr_socket_path"
python3 "$helper" doctor --run "$run_dir"
```

`helper`はスキルに同梱する`axiom_herdr.py`の絶対パス、`run_dir`は`init`の出力です。
画面IDと端末IDは`herdr pane list`等で取得しますが、フォーカスや作業ディレクトリの
一致だけで自分の画面と判断しません。herdrに会話IDが記録されている場合は
`CODEX_THREAD_ID`と照合し、ない場合は端末内容を確認するか、ユーザーが明示した
対応を使います。初回の明示登録には、この確認が必要です。

登録後の操作では、実行側の会話IDが登録したMainと一致すること、元の端末が
今も存在することを確認します。画面を選び直しても対象は変わりません。
端末が移動した場合はその端末を追い、端末が閉じられたりIDが再利用されたりした場合は停止します。
担当の起動直前にもMainを確認し直しますが、herdrの照会と分割は別操作のため、
その間の同時移動まで原子的に防ぐことはできません。
登録内容がない古い実行記録には、従来のherdr環境変数による確認を適用します。

子の役割・報告先・画面情報も、起動するCodexごとの`-c shell_environment_policy.set.…`で
明示的に渡します。ユーザー設定ファイルや共有app-server全体の環境変数は書き換えません。
子の`workspace-write + never`は維持します。

## 待機中のポーリング抑制

補助スクリプトの`wait --timeout 3600`が、最大1時間、全担当をまとめて監視します。
内部の2秒ごとの確認ではMainのLLMを呼びません。1時間の結果待ちを使うには、Mainを起動する前に
Codexの`background_terminal_max_timeout=3600000`を設定することが必須です。推奨例は次のとおりです。

```bash
codex -c background_terminal_max_timeout=3600000
```

Mainには同じ実行セッションを保持し、**結果待ちを1時間（3600秒、
`yield_time_ms=3600000`）固定**にするよう指示します。`background_terminal_max_timeout`は
技術的な上限を設定するだけで、実際に渡す`yield_time_ms`を変更しません。そのため、両方を
1時間に設定する必要があります。「環境で許される最長間隔」という裁量は設けず、Mainが自己判断で
短い値へ変更することを禁止します。外側の実行ラッパーが待機を返す場合も同じ値を使い、進捗を見る
ためだけの`status`・端末ログの反復取得は行いません。完了・要対応・プロセス終了・ユーザーの追加
指示で早く戻った場合は、その時点で対応します。1時間経つまで結果を保留する設定ではありません。

同じ依頼・報告・担当状態の通知は実行ディレクトリの`wait-notices.json`に記録し、
待機を呼び直しても繰り返し返しません。新しい依頼・報告・状態変化は再通知します。
通知を抑えたタスクも未解決のまま数え、報告やペインは残します。Mainは通知を受けたら
必要な対応を行い、他の担当を待つ場合も未解決事項を保持します。

補助スクリプトの待機時間と、Codexが実行結果を待つ時間は別設定です。上位の運用指針により
長い待機を避ける判断をした場合も、それを実行ツールが値を技術的にクランプした、または上限に
達したという観測とは別に記録します。実行ツールや外側ラッパーが1時間待機に対応するか、実際の
待機がクランプされるかが未確認なら、未検証として扱います。観測した制限、未確認の点、運用上の
判断を区別して一度報告し、短いポーリングへ自動で読み替えません。既存の待機・担当を保持し、対応済みの
イベント待機か独立した作業へ移ります。スキルの指示だけでホストの上限を変更・強制することは
できません。プラグインはユーザー設定を書き換えず、稼働中のMainを後から再設定したとも主張しません。
コンテキストやツール結果を失った場合は、`status`で
一度状況を確認し、未回収の報告を復元してから待機を再開します。

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
