import unittest
from py_mind_memo.models import MindMapModel, Reference
from py_mind_memo.history import HistoryManager, Snapshot

class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.model = MindMapModel("Root")
        self.history = HistoryManager(self.model, max_snapshots=10)

    def test_record_snapshot_and_undo_redo(self):
        """スナップショット記録、Undo、Redoによってモデル状態が復元されること"""
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.history.can_redo())

        # ルートのみの初期状態を記録
        self.history.record_snapshot(selected_id=self.model.root.id, selected_type="node")
        # トピック追加
        child = self.model.add_node(self.model.root, "Child 1")
        self.assertEqual(len(self.model.root.children), 1)
        self.assertTrue(self.history.can_undo())
        self.assertFalse(self.history.can_redo())

        # Undo 実行
        res = self.history.undo(current_selected_id=child.id, current_selected_type="node")
        self.assertIsNotNone(res)
        selected_id, selected_type = res
        self.assertEqual(selected_id, self.model.root.id)
        self.assertEqual(selected_type, "node")
        self.assertEqual(len(self.model.root.children), 0)
        self.assertFalse(self.history.can_undo())
        self.assertTrue(self.history.can_redo())

        # Redo 実行
        res_redo = self.history.redo(current_selected_id=self.model.root.id, current_selected_type="node")
        self.assertIsNotNone(res_redo)
        redo_id, redo_type = res_redo
        self.assertEqual(redo_id, child.id)
        self.assertEqual(redo_type, "node")
        self.assertEqual(len(self.model.root.children), 1)
        self.assertEqual(self.model.root.children[0].text, "Child 1")
        self.assertTrue(self.history.can_undo())
        self.assertFalse(self.history.can_redo())

    def test_capacity_limit_10_snapshots(self):
        """11個以上のスナップショットを記録した場合、最古が破棄され最大10回までUndoできること"""
        for i in range(11):
            self.history.record_snapshot(selected_id=self.model.root.id, selected_type="node")
            self.model.add_node(self.model.root, f"Node {i}")

        self.assertEqual(len(self.model.root.children), 11)

        # 最大10回Undo可能であることを検証
        for _ in range(10):
            self.assertTrue(self.history.can_undo())
            res = self.history.undo()
            self.assertIsNotNone(res)

        # 11回目はUndo不可
        self.assertFalse(self.history.can_undo())
        self.assertIsNone(self.history.undo())

        # 最古（Node 0 追加前の状態）はドロップされたため、残っているのは Node 0（1個）の状態
        self.assertEqual(len(self.model.root.children), 1)
        self.assertEqual(self.model.root.children[0].text, "Node 0")

    def test_branching_clears_redo_stack(self):
        """Undo後に新たな操作（スナップショット記録）が行われた場合、Redoスタックがクリアされること"""
        self.history.record_snapshot(selected_id=self.model.root.id)
        self.model.add_node(self.model.root, "Child A")

        self.history.undo()
        self.assertTrue(self.history.can_redo())

        # 新規操作を実行
        self.history.record_snapshot(selected_id=self.model.root.id)
        self.model.add_node(self.model.root, "Child B")

        # 分岐によりRedoスタックが破棄されていること
        self.assertFalse(self.history.can_redo())
        self.assertIsNone(self.history.redo())

    def test_save_point_is_modified(self):
        """Undo/Redoにより保存時点（Save Point）と状態が一致した際にis_modifiedが同期されること"""
        self.history.mark_saved()
        self.assertFalse(self.model.is_modified)

        # 変更1
        self.history.record_snapshot(selected_id=self.model.root.id)
        self.model.add_node(self.model.root, "Topic 1")
        self.assertTrue(self.model.is_modified)

        # Undo -> 保存時点に戻るため is_modified == False
        self.history.undo()
        self.assertFalse(self.model.is_modified)

        # Redo -> 未保存状態になるため is_modified == True
        self.history.redo()
        self.assertTrue(self.model.is_modified)

        # Topic 1 時点で保存
        self.history.mark_saved()
        self.assertFalse(self.model.is_modified)

        # Undo -> Topic 1 保存時点より前になるため is_modified == True
        self.history.undo()
        self.assertTrue(self.model.is_modified)

        # Redo -> 再び Topic 1 保存時点に戻るため is_modified == False
        self.history.redo()
        self.assertFalse(self.model.is_modified)

    def test_selection_info_saved_and_restored(self):
        """エンティティIDおよびエンティティ種別（node, reference）が保持・復元されること"""
        node1 = self.model.add_node(self.model.root, "Topic 1")
        node2 = self.model.add_node(self.model.root, "Topic 2")
        ref = Reference(node1.id, node2.id)
        self.model.references.append(ref)

        # reference 選択状態のスナップショット
        self.history.record_snapshot(selected_id=ref.id, selected_type="reference")
        # 参照線を削除
        self.model.references.remove(ref)

        # Undoで reference 選択情報が復元されること
        res = self.history.undo()
        self.assertIsNotNone(res)
        sel_id, sel_type = res
        self.assertEqual(sel_id, ref.id)
        self.assertEqual(sel_type, "reference")
        self.assertEqual(len(self.model.references), 1)

    def test_clear_resets_history(self):
        """clear() で履歴スタックおよび状態がリセットされること"""
        self.history.record_snapshot(selected_id=self.model.root.id)
        self.model.add_node(self.model.root, "Topic")
        self.assertTrue(self.history.can_undo())

        self.history.clear()
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.history.can_redo())
        self.assertIsNone(self.history.undo())
        self.assertIsNone(self.history.redo())

    def test_boundary_conditions(self):
        """スタックが空の場合の安全な挙動"""
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.history.can_redo())
        self.assertIsNone(self.history.undo())
        self.assertIsNone(self.history.redo())

if __name__ == '__main__':
    unittest.main()
