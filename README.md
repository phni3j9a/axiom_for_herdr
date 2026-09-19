# Axiom for herdr

**Main decides. Astra advises. Sol designs. Luna executes. Sol reviews.**

Codexの担当作業を、herdrの分割ペインで同時に見られるプラグインです。
Mainが必要な担当を起動し、Workerはレビュー終了まで、AdvisorはMainの一連の作業の
終了まで保持します。結果を回収し、役割ごとの終了時点で担当ペインを閉じます。
既存の[Axiom](https://github.com/phni3j9a/axiom)の役割分担とレビュー方針を引き継ぎます。

バージョン系列 `v0.1.0`。共有app-serverで実行するCodexに対応し、
Mainの会話IDとherdr端末を実行記録に結び付けます。検証方法と実機で確認した範囲は
[実機確認手順](docs/MANUAL_VALIDATION.md)を参照してください。

## 動作方針

| 項目 | 動作 |
|---|---|
| Main | Sol XHIGH。左側で判断・分割・統合・最終受理を担当 |
| 難しい計画・判断相談 | Astra XHIGHをAdvisorとして別ペインで起動。採否はMainが判断 |
| 通常の調査・実装 | Luna MAX Fastを右側の別ペインで起動 |
| 長時間処理の監視 | CIなどの反復的な状態確認をLunaに完了まで委任。既存担当がいれば再利用 |
| 重要なUIデザイン | Sol MAXを別ペインで起動 |
| 独立レビュー | Sol XHIGH。再レビューは同じセッションを継続 |
| 子の権限・承認 | 全役割を`workspace-write + never`で起動。権限不足はMainへ報告 |
| 並列数 | 固定上限なし。Mainが作業の独立性と調整コストから判断 |
| 作業待ち | runロックで待機を1つに限定し、Mainは同じ実行セッションをイベントまで再開する |
| 担当の終了 | Worker・Reviewerはレビュー終了時、AdvisorはMainの作業全体の終了時。レビューしない作業は成果受理後 |
| 入力待ち・起動失敗 | 確認できるよう表示を残す |
| 手動操作 | 担当へ直接指示でき、手動で変更した配置を全体リセットしない |

全員が独立した対話型Codexとして動きます。Mainのサブエージェント機能で
隠れて実行する構成にはしていません。Mainが補助スクリプトを呼んで管理し、
常駐のオーケストレーターやダッシュボードは同梱しません。

## モデルと速度の設定

- Main: `gpt-5.6-sol` / `xhigh`
- Worker: `gpt-5.6-luna` / `max` / Fast
- Design: `gpt-5.6-sol` / `max`
- Reviewer: `gpt-5.6-sol` / `xhigh`
- Advisor: `gpt-6-astra` / `xhigh`（計画作成・相談ともに固定）

Mainはherdr内で`codex -m gpt-5.6-sol -c 'model_reasoning_effort="xhigh"'`として
起動します。プラグインは実行中のMainモデルやグローバル既定値を変更しません。
補助スクリプトはworkerだけに`-c 'service_tier="fast"' -c features.fast_mode=true`を
追加します。design・reviewer・advisorには速度の上書きを追加せず、既存のCodex設定に従います。
Fastと推論強度の`max`は別設定です。Codexの`fast`はリクエストの`priority`に対応します
（[公式設定リファレンス](https://learn.chatgpt.com/docs/config-file/config-reference)、
[Fast mode](https://learn.chatgpt.com/docs/agent-configuration/speed)）。

この割当は更新後に新しく起動する担当に適用します。起動引数は要求の記録であり、
実際のモデル・推論強度・速度はCodexセッションの証拠で確認します。

## Astra Advisor

難しいPlanの起草、設計案の比較、収束しない失敗、計画の前提変更などで、Mainが
Astra XHIGHへ相談します。計画作成と短い相談の両方でeffortは`xhigh`固定です。
MainまたはLunaが必要な現状調査を行ってから依頼し、単純な作業では相談を強制しません。

Mainは重要なユーザー発言・関連会話、現在の合意・制約、相談内容、選んだコードや
診断結果の抜粋を依頼ファイルへ記述します。Mainの仮説と事実を区別します。
会話の自動抽出や全履歴の転送は行いません。Astraは必要なファイルを読み取り、
情報不足なら`blocked`報告で具体的な追加証拠を求めます。

補助スクリプトには`advisor`役を追加しています。既存のrunと絶対パスを使う例です。

```bash
python3 "$helper" spawn --run "$run_dir" --role advisor \
  --label '移行計画の相談' --task-file "$consultation_file" --cwd "$project_dir"
```

一度起動したAdvisorは、Mainのセッション全体で保持します。個別の相談を解決して
現在の完了報告を回収しても、次の相談に備えて同じペインを残します。再相談では`send`で
新しい事実・変更した前提・Mainの採否判断と次の論点を渡します。会話は自動共有されません。
ここでのセッションは、追加指示を含むMainとユーザーの一連の作業です。途中報告、
ユーザーの返答待ち、コンテキスト圧縮では閉じず、作業全体を終える後片付けの時点で閉じます。
無関係な作業へ大きく移る場合や古い前提が混乱を招く場合は、理由と必要な情報を引き継いで
新しいAdvisorへ切り替えられます。追加情報待ちなどの未解決状態は終了扱いにしません。
Advisorにはプロジェクト編集をしない役割指示を渡し、独立したSol Reviewerには再利用しません。
Astraが起動できない場合、制約を報告してMainで進められる作業を続けます。
詳細は[advisor.md](plugins/axiom-for-herdr/skills/axiom-for-herdr/references/advisor.md)と
[操作手順](plugins/axiom-for-herdr/skills/axiom-for-herdr/references/operations.md#astra-consultations)を参照してください。
起動引数の模擬確認とherdr実機での動作・品質・消費量の確認は分けて記録します。

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

Worker・Design・Reviewer・Advisorは、全員次の起動引数で固定します。

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

Reviewer・Advisorも同じsandbox設定です。「プロジェクトは編集せず、報告先だけへ出力する」
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
インストール後、herdr内で次のコマンドを実行し、新しいMainのCodexセッションを開始してください。

```bash
codex -c background_terminal_max_timeout=3600000
```

この起動時設定で、実行ツールの結果待ち上限を1時間にします。指定しない場合の既定値は5分のため、
Mainの起動前に必要です。helper自身は`wait --until-event`でイベントまで継続します。
外側から同じプロセスを待つ際は別途`yield_time_ms=3600000`を渡す必要があり、
その指定はこのプラグインのスキルがMainへ指示します。

このスキルは明示呼び出しで利用します。`skills/axiom-for-herdr/agents/openai.yaml`に次を設定しています。

```yaml
policy:
  allow_implicit_invocation: false
```

スキルの`description`は機能を説明し、呼び出し方はこのpolicyで制御します。
通常の開発依頼やherdr内での作業だけでは自動選択されません。利用する作業で次のように指定します。

```text
$axiom-for-herdr:axiom-for-herdr

このプロジェクトを調査して、必要な変更を実装してください。
担当の作業はherdrの別ペインで見えるようにしてください。
```

明示呼び出しした作業とその続きに適用します。同じ作業の追加指示では、毎回指定し直す必要はありません。
呼び出された作業内では、必要な担当の起動・レビュー・結果回収・ペインの後片付けを行います。
`AXIOM_HERDR_ROLE`または依頼内容で担当として識別された
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

CI/CD、GitHub Actions、ビルド、テストなどで反復的な状態確認が必要な場合は、
通常のLuna workerに完了確認まで委任します。監視だけでも委任でき、既存の担当Lunaがいれば同じ担当に任せます。
Mainは委任後の状態確認を繰り返さず、他の作業を進めるか、以下の既存の待機機能で報告を待ちます。
Lunaは完了・失敗・監視不能・Mainの判断が必要になったときに、結果と証拠を簡潔に報告します。
変化のない状況の定期報告は不要です。

補助スクリプトの`wait --until-event`が全担当をまとめて監視します。runごとのファイルロックにより、
同時に動けるwaiterは1つだけです。状態が安定している間の確認間隔は2秒から最大10秒まで
バックオフし、MainのLLMを呼びません。1時間の結果待ちを使うには、Mainを起動する前に
Codexの`background_terminal_max_timeout=3600000`を設定することが必須です。推奨例は次のとおりです。

```bash
codex -c background_terminal_max_timeout=3600000
```

Mainには同じ実行セッションを保持し、ホストが対応する最長のイベント駆動結果待ちで再開するよう
指示します。上記の1時間設定を使う環境では`yield_time_ms=3600000`です。
`background_terminal_max_timeout`は技術的な上限を設定するだけで、実際に渡す`yield_time_ms`を
変更しません。内側コマンドの`session_id`と外側ラッパーの`cell_id`を別々に保持し、どちらかが
途中で制御を返しても、helperの終端JSONがなければ同じハンドルを再開します。新しいwaiter、
進捗を見るためだけの`status`・端末ログ取得、変化のない中間報告は行いません。
完了・要対応・プロセス終了・ユーザーの追加指示で早く戻った場合は、その時点で対応します。

同じ依頼・報告・担当状態の通知は実行ディレクトリの`wait-notices.json`に記録し、
待機を呼び直しても繰り返し返しません。新しい依頼・報告・状態変化は再通知します。
通知を抑えたタスクも未解決のまま数え、報告やペインは残します。Mainは通知を受けたら
必要な対応を行い、他の担当を待つ場合も未解決事項を保持します。

通常のhelper待機には内部timeoutがありません。明示的な`--timeout`は安全弁で、通常運用では
3600秒以上だけを受け付けます。短時間timeoutはテスト専用であり、Mainのポーリングには使えません。
helperの待機時間とCodexが実行結果を待つ時間は別設定です。上位の運用指針により
長い待機を避ける判断をした場合も、それを実行ツールが値を技術的にクランプした、または上限に
達したという観測とは別に記録します。実行ツールや外側ラッパーが1時間待機に対応するか、実際の
待機がクランプされるかが未確認なら、未検証として扱います。観測した制限、未確認の点、運用上の
判断を区別して一度報告し、短いポーリングへ自動で読み替えません。既存の待機・担当を保持し、対応済みの
イベント待機か独立した作業へ移ります。スキルの指示だけでホストの上限を変更・強制することは
できません。プラグインはユーザー設定を書き換えず、稼働中のMainを後から再設定したとも主張しません。
コンテキストやツール結果を失った場合は、`status`で一度だけ状況を確認し、未回収の報告を
復元します。`wait.lock`の待機ID・PIDは重複の診断情報であり、失った実行ハンドルの代わりには
なりません。`reason: waiter_already_active`は再試行の合図ではありません。

開発時は、Mainのrollout JSONLを次の読み取り専用スクリプトへ渡すと、wait回数、終了理由、
timeout引数、`status`・`read`回数、runごとの最大同時wait数を集計できます。

```bash
python3 plugins/axiom-for-herdr/skills/axiom-for-herdr/scripts/audit_wait_history.py \
  /path/to/main-rollout.jsonl
```

ディレクトリも指定できますが、Main以外の検証セッションが混ざる場合は対象ファイルを明示してください。

## 結果の扱い

依頼ごとにIDを付け、短いMarkdownの報告をJSONの受け渡しファイルへ格納します。
Mainは`collect`で報告を読み、差分や検証結果を確認します。`complete`は今回の依頼への
報告完了を表し、成果の受理やペインを閉じる時点とは別です。

| 役割・作業 | 保持と終了の判断 |
|---|---|
| レビュー対象のWorker | 実装・修正・再レビューを通じて保持。Mainが採用した指摘は元の担当へ`send`で戻し、レビュー全体が終わったら終了 |
| Reviewer | 同じ会話で再レビューを続け、Mainがレビュー全体の終了を判断したら終了 |
| Advisor | 個別相談が終わっても保持。Mainの一連の作業が終わる後片付けで終了 |
| Worker・Design（レビュー・追加作業なし） | 単独の調査など、Mainが成果を受理したら終了 |

Mainは担当ごとのtaskパス・担当範囲・報告・判断を次のターンやコンテキスト圧縮後にも
引き継ぎます。レビュー修正では元のWorkerを再利用し、会話を失った場合は以前の報告と
現在の意図を渡して新しいWorkerで復旧します。他の未完了作業がある担当は残します。

回収済みの`complete`報告と担当状態が変わらず、担当が`idle`または`done`で起動待ちでも
なければ、ペインを残していても`wait`の未完了件数には入りません。`pending: 0`は全ペインを
閉じる合図ではなく、待機の再起動も不要です。保持だけを理由に定期確認や追加相談を行いません。
`blocked`報告は回収後も未完了として残ります。

役割ごとの終了時点に達したら、Mainが現在の完了報告を回収したうえで`close`を実行します。
この保持・終了の判断はMainの運用指示であり、補助スクリプトがレビューやセッションの終了を
自動判定する機能ではありません。

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
同じWorker・Reviewerでの修正と再確認、Advisorのセッション全体での保持、
直接介入、入力待ちを確認する手順をまとめています。

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
| 同スキルの`references/` | 操作・Advisor相談・レビューの詳細 |
| 同スキルの`scripts/axiom_herdr.py` | herdr操作と報告の受け渡し |

## 参照・ライセンス

- [Axiom](https://github.com/phni3j9a/axiom) — MIT。レビューと委譲の方針を継承。
- [Herdr agent automation](https://herdr.dev/docs/agent-automation/)
- [Herdr CLI reference](https://herdr.dev/docs/cli-reference/)

MIT License。herdrおよびCodex本体のコードは同梱しません。
