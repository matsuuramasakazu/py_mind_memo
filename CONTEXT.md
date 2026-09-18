# Mind Map Core

マインドマップのデータ構造（ノード階層と参照関係）の保持、編集、および履歴管理を行うコンテキスト。

## Language

**Topic (Node)**:
マインドマップの構成要素であり、テキスト、画像、アイコンおよび子トピックを持つ論理要素。
_Avoid_: Item, Element

**Reference**:
2つのトピック間を結ぶ視覚的な関連線（破線の矢印曲線）。
_Avoid_: Link, Relation, Arrow

**Snapshot (Memento)**:
ある時点におけるマインドマップ全体（全トピックと全参照関係）の完全な状態と、その時に選択されていたフォーカス情報の記録。
_Avoid_: Backup, StateDump

**Change History (Undo/Redo Stack)**:
直近の変更スナップショットを上限10件まで保持する履歴スタック。
_Avoid_: Revision Log, Event Log

**Save Point**:
ファイルに永続化された時点のスナップショットを指す目印であり、未保存状態（Dirty）の判定に用いる。
_Avoid_: Checkpoint, Commit
