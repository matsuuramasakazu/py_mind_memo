import copy
import uuid
from collections import deque
from typing import Deque, List, Optional, Tuple

from .models import MindMapModel


class Snapshot:
    """ある時点におけるマインドマップ全体と選択状態の記録（メメント）"""

    def __init__(
        self,
        data: dict,
        selected_entity_id: Optional[str] = None,
        selected_entity_type: str = "node",
        state_id: Optional[str] = None,
    ):
        self.data = copy.deepcopy(data)
        self.selected_entity_id = selected_entity_id
        self.selected_entity_type = selected_entity_type
        self.state_id = state_id or uuid.uuid4().hex


class HistoryManager:
    """直近の変更スナップショットを上限10件まで保持する変更履歴管理クラス"""

    def __init__(self, model: MindMapModel, max_snapshots: int = 10):
        self.model = model
        self.max_snapshots = max_snapshots
        self._undo_stack: Deque[Snapshot] = deque(maxlen=max_snapshots)
        self._redo_stack: List[Snapshot] = []
        # 現在の状態IDと、保存時点（Save Point）の状態ID
        self.current_state_id: str = uuid.uuid4().hex
        self.save_point_state_id: Optional[str] = self.current_state_id

    def can_undo(self) -> bool:
        """Undo可能かどうかを返す"""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Redo可能かどうかを返す"""
        return len(self._redo_stack) > 0

    def record_snapshot(
        self, selected_id: Optional[str] = None, selected_type: str = "node"
    ) -> Snapshot:
        """現在のモデル状態をスナップショットとしてUndoスタックに記録し、Redoスタックをクリアする。
        その後、次の変更状態を表す新しい state_id を採番する。
        """
        snapshot = Snapshot(
            data=self.model.save(),
            selected_entity_id=selected_id,
            selected_entity_type=selected_type,
            state_id=self.current_state_id,
        )
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        self.current_state_id = uuid.uuid4().hex
        return snapshot

    def undo(
        self,
        current_selected_id: Optional[str] = None,
        current_selected_type: str = "node",
    ) -> Optional[Tuple[Optional[str], str]]:
        """直前のスナップショットに戻す（Undo）。
        成功した場合、復元対象の (selected_entity_id, selected_entity_type) を返す。
        """
        if not self.can_undo():
            return None

        # 現在の状態をRedoスタックに保存
        current_snapshot = Snapshot(
            data=self.model.save(),
            selected_entity_id=current_selected_id,
            selected_entity_type=current_selected_type,
            state_id=self.current_state_id,
        )
        self._redo_stack.append(current_snapshot)

        # Undoスタックから直前状態を取り出して復元
        snapshot = self._undo_stack.pop()
        self.model.load(snapshot.data)
        self.current_state_id = snapshot.state_id

        # Save Pointとの一致判定
        self.model.is_modified = self.current_state_id != self.save_point_state_id

        return snapshot.selected_entity_id, snapshot.selected_entity_type

    def redo(
        self,
        current_selected_id: Optional[str] = None,
        current_selected_type: str = "node",
    ) -> Optional[Tuple[Optional[str], str]]:
        """取り消した変更をやり直す（Redo）。
        成功した場合、復元対象の (selected_entity_id, selected_entity_type) を返す。
        """
        if not self.can_redo():
            return None

        # 現在の状態をUndoスタックに保存
        current_snapshot = Snapshot(
            data=self.model.save(),
            selected_entity_id=current_selected_id,
            selected_entity_type=current_selected_type,
            state_id=self.current_state_id,
        )
        self._undo_stack.append(current_snapshot)

        # Redoスタックから進む状態を取り出して復元
        snapshot = self._redo_stack.pop()
        self.model.load(snapshot.data)
        self.current_state_id = snapshot.state_id

        # Save Pointとの一致判定
        self.model.is_modified = self.current_state_id != self.save_point_state_id

        return snapshot.selected_entity_id, snapshot.selected_entity_type

    def mark_saved(self):
        """現在の状態を保存済み（Save Point）としてマークする"""
        self.save_point_state_id = self.current_state_id
        self.model.is_modified = False

    def clear(self, is_saved: Optional[bool] = None):
        """履歴スタックを初期化する（新規作成やファイルオープン時）"""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.current_state_id = uuid.uuid4().hex
        if is_saved is None:
            is_saved = not getattr(self.model, "is_modified", False)
        self.save_point_state_id = self.current_state_id if is_saved else None
