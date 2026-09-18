import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.models import MindMapModel, Node, Reference
from py_mind_memo.view import MindMapView


class TestReferenceHistory(unittest.TestCase):
    """参照関係および制御点ドラッグのUndo/Redoに関する統合テスト"""

    def setUp(self):
        self.root = tk.Tk()
        # GUI描画やレイアウト等をモック化してヘッドレスで安定動作させる
        self.patchers = [
            patch('py_mind_memo.view.GraphicsEngine'),
            patch('py_mind_memo.view.LayoutEngine'),
            patch('py_mind_memo.view.DragDropHandler'),
            patch('py_mind_memo.view.KeyboardNavigator'),
            patch('py_mind_memo.view.MindMapView._create_menu'),
            patch('py_mind_memo.view.MindMapView.render'),
        ]
        for p in self.patchers:
            p.start()

        self.view = MindMapView(self.root)
        # 2つの子ノードを作成
        self.node_a = self.view.model.add_node(self.view.model.root, "Node A")
        self.node_b = self.view.model.add_node(self.view.model.root, "Node B")
        # 履歴をクリアしてクリーンな初期状態にする
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.root.destroy()

    def test_undo_redo_create_reference(self):
        """2トピック間の参照作成後のUndoで参照が削除され、Redoで復元・選択されること"""
        # 初期状態: 参照なし
        self.assertEqual(len(self.view.model.references), 0)
        self.assertFalse(self.view.history.can_undo())

        # 参照モード開始 (Ctrl+R)
        self.view.on_toggle_reference_mode(None)
        self.assertTrue(self.view.reference_edit_mode)

        # find_node_at をモックして node_a, node_b を順にクリック
        with patch.object(self.view, 'find_node_at') as mock_find:
            # 1回目クリック: node_a (ソース選択)
            mock_find.return_value = self.node_a
            self.view._handle_reference_mode_click(100, 100)
            self.assertEqual(self.view.reference_source_node, self.node_a)
            self.assertEqual(len(self.view.model.references), 0)

            # 2回目クリック: node_b (ターゲット選択 -> 参照作成)
            mock_find.return_value = self.node_b
            self.view._handle_reference_mode_click(200, 200)

        # 参照が作成されていること
        self.assertEqual(len(self.view.model.references), 1)
        created_ref = self.view.model.references[0]
        self.assertEqual(created_ref.source_id, self.node_a.id)
        self.assertEqual(created_ref.target_id, self.node_b.id)
        self.assertFalse(self.view.reference_edit_mode)
        self.assertTrue(self.view.model.is_modified)
        self.assertTrue(self.view.history.can_undo())
        # 作成された参照が選択されていること
        self.assertEqual(self.view.selected_reference, created_ref)

        # Undo 実行 (Ctrl+Z)
        self.view.on_undo(None)

        # 参照が削除され、Undo前の選択元ノードが選択されること
        self.assertEqual(len(self.view.model.references), 0)
        self.assertIsNone(self.view.selected_reference)
        self.assertEqual(self.view.selected_node.id, self.node_a.id)
        self.assertTrue(self.view.history.can_redo())

        # Redo 実行 (Ctrl+Y)
        self.view.on_redo(None)

        # 参照が復元され、対象の参照が選択されること
        self.assertEqual(len(self.view.model.references), 1)
        restored_ref = self.view.model.references[0]
        self.assertEqual(restored_ref.source_id, self.node_a.id)
        self.assertEqual(restored_ref.target_id, self.node_b.id)
        self.assertEqual(self.view.selected_reference.id, created_ref.id)
        self.assertIsNone(self.view.selected_node)

    def test_undo_redo_delete_reference(self):
        """参照削除後のUndoで参照線および制御点座標が復元され、Redoで再度削除されること"""
        ref = Reference(self.node_a.id, self.node_b.id)
        ref.cp1_x, ref.cp1_y = 120.0, 150.0
        ref.cp2_x, ref.cp2_y = 220.0, 250.0
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

        # Delete 実行
        res = self.view.on_delete(None)
        self.assertEqual(res, "break")
        self.assertEqual(len(self.view.model.references), 0)
        self.assertIsNone(self.view.selected_reference)
        self.assertTrue(self.view.model.is_modified)
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行 (Ctrl+Z)
        self.view.on_undo(None)

        # 参照および制御点が復元され、選択されること
        self.assertEqual(len(self.view.model.references), 1)
        restored = self.view.model.references[0]
        self.assertEqual(restored.id, ref.id)
        self.assertEqual(restored.cp1_x, 120.0)
        self.assertEqual(restored.cp1_y, 150.0)
        self.assertEqual(restored.cp2_x, 220.0)
        self.assertEqual(restored.cp2_y, 250.0)
        self.assertEqual(self.view.selected_reference.id, ref.id)
        self.assertIsNone(self.view.selected_node)
        self.assertFalse(self.view.model.is_modified)  # Save Point に戻るため

        # Redo 実行 (Ctrl+Y)
        self.view.on_redo(None)
        self.assertEqual(len(self.view.model.references), 0)
        self.assertIsNone(self.view.selected_reference)
        self.assertTrue(self.view.model.is_modified)

    def test_undo_redo_delete_topic_restores_attached_references(self):
        """トピック削除に伴い連動削除された参照が、Undoでトピックとともに復元されること"""
        ref = Reference(self.node_a.id, self.node_b.id)
        self.view.model.references.append(ref)
        self.view.selected_node = self.node_a
        self.view.selected_reference = None
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

        # node_a を削除
        self.view.on_delete(None)
        self.assertNotIn(self.node_a, self.view.model.root.children)
        self.assertEqual(len(self.view.model.references), 0)
        self.assertEqual(self.view.selected_node, self.view.model.root)

        # Undo 実行
        self.view.on_undo(None)
        # node_a と ref が両方復元されること
        self.assertEqual(len(self.view.model.root.children), 2)
        restored_node_a = self.view.model.find_node_by_id(self.node_a.id)
        self.assertIsNotNone(restored_node_a)
        self.assertEqual(len(self.view.model.references), 1)
        self.assertEqual(self.view.model.references[0].id, ref.id)
        self.assertEqual(self.view.selected_node.id, self.node_a.id)

    def _simulate_drag_handle(self, handle_tag: str, target_cx: float, target_cy: float):
        with patch.object(self.view.canvas, 'find_overlapping', return_value=[1]):
            with patch.object(self.view.canvas, 'gettags', return_value=["reference_handle", handle_tag]):
                click_event = MagicMock(x=100, y=100)
                with patch.object(self.view.canvas, 'canvasx', return_value=100), \
                     patch.object(self.view.canvas, 'canvasy', return_value=100):
                    self.view._on_canvas_click(click_event)

        motion_event = MagicMock(x=target_cx, y=target_cy)
        with patch.object(self.view.canvas, 'canvasx', return_value=target_cx), \
             patch.object(self.view.canvas, 'canvasy', return_value=target_cy):
            self.view._on_motion(motion_event)

        release_event = MagicMock(x=target_cx, y=target_cy)
        with patch.object(self.view.canvas, 'canvasx', return_value=target_cx), \
             patch.object(self.view.canvas, 'canvasy', return_value=target_cy):
            self.view._on_release(release_event)

    def _simulate_click_handle_without_drag(self, handle_tag: str):
        with patch.object(self.view.canvas, 'find_overlapping', return_value=[1]):
            with patch.object(self.view.canvas, 'gettags', return_value=["reference_handle", handle_tag]):
                click_event = MagicMock(x=100, y=100)
                with patch.object(self.view.canvas, 'canvasx', return_value=100), \
                     patch.object(self.view.canvas, 'canvasy', return_value=100):
                    self.view._on_canvas_click(click_event)

        release_event = MagicMock(x=100, y=100)
        with patch.object(self.view.canvas, 'canvasx', return_value=100), \
             patch.object(self.view.canvas, 'canvasy', return_value=100):
            self.view._on_release(release_event)

    def test_undo_redo_drag_control_point_cp1(self):
        """参照の制御点cp1をドラッグ移動後、Undoでドラッグ前の位置に戻り、Redoで新しい位置に進むこと"""
        ref = Reference(self.node_a.id, self.node_b.id)
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

        self.assertIsNone(ref.cp1_x)
        self.assertIsNone(ref.cp1_y)
        self.assertFalse(self.view.history.can_undo())

        # cp1 ハンドルを (150, 180) にドラッグ
        self._simulate_drag_handle(f"{ref.id}_cp1", 150.0, 180.0)

        self.assertEqual(ref.cp1_x, 150.0)
        self.assertEqual(ref.cp1_y, 180.0)
        self.assertTrue(self.view.history.can_undo())
        self.assertTrue(self.view.model.is_modified)

        # Undo 実行 (Ctrl+Z)
        self.view.on_undo(None)

        # ドラッグ前 (None) に戻り、参照が選択されていること
        restored_ref = self.view.selected_reference
        self.assertIsNotNone(restored_ref)
        self.assertIsNone(restored_ref.cp1_x)
        self.assertIsNone(restored_ref.cp1_y)
        self.assertEqual(restored_ref.id, ref.id)
        self.assertFalse(self.view.model.is_modified)  # Save Point
        self.assertTrue(self.view.history.can_redo())

        # Redo 実行 (Ctrl+Y)
        self.view.on_redo(None)
        redo_ref = self.view.selected_reference
        self.assertIsNotNone(redo_ref)
        self.assertEqual(redo_ref.cp1_x, 150.0)
        self.assertEqual(redo_ref.cp1_y, 180.0)
        self.assertEqual(redo_ref.id, ref.id)
        self.assertTrue(self.view.model.is_modified)

    def test_undo_redo_drag_control_point_cp2(self):
        """参照の制御点cp2をドラッグ移動後、Undo/Redoが正常に動作すること"""
        ref = Reference(self.node_a.id, self.node_b.id)
        ref.cp1_x, ref.cp1_y = 100.0, 100.0
        ref.cp2_x, ref.cp2_y = 200.0, 200.0
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

        # cp2 ハンドルを (250, 280) にドラッグ
        self._simulate_drag_handle(f"{ref.id}_cp2", 250.0, 280.0)

        self.assertEqual(self.view.model.references[0].cp2_x, 250.0)
        self.assertEqual(self.view.model.references[0].cp2_y, 280.0)
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行 (Ctrl+Z)
        self.view.on_undo(None)
        restored_ref = self.view.selected_reference
        self.assertIsNotNone(restored_ref)
        self.assertEqual(restored_ref.cp2_x, 200.0)
        self.assertEqual(restored_ref.cp2_y, 200.0)
        self.assertEqual(restored_ref.id, ref.id)

        # Redo 実行 (Ctrl+Y)
        self.view.on_redo(None)
        redo_ref = self.view.selected_reference
        self.assertIsNotNone(redo_ref)
        self.assertEqual(redo_ref.cp2_x, 250.0)
        self.assertEqual(redo_ref.cp2_y, 280.0)
        self.assertEqual(redo_ref.id, ref.id)

    def test_drag_control_point_without_change_does_not_record_snapshot(self):
        """制御点クリックまたは移動なしのドラッグではスナップショットが記録されないこと"""
        ref = Reference(self.node_a.id, self.node_b.id)
        ref.cp1_x, ref.cp1_y = 100.0, 100.0
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.model.is_modified = False
        self.view.history.mark_saved()

        # クリックのみで移動なし
        self._simulate_click_handle_without_drag(f"{ref.id}_cp1")

        self.assertFalse(self.view.history.can_undo())
        self.assertFalse(self.view.model.is_modified)

        # 同一座標へのドラッグ
        self._simulate_drag_handle(f"{ref.id}_cp1", 100.0, 100.0)

        self.assertFalse(self.view.history.can_undo())
        self.assertFalse(self.view.model.is_modified)

    def test_undo_redo_reference_ensures_visibility(self):
        """参照操作のUndo/Redo時に対象参照のsource_nodeに対してensure_node_visibleが呼ばれること"""
        ref = Reference(self.node_a.id, self.node_b.id)
        ref.cp1_x, ref.cp1_y = 100.0, 100.0
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.history.mark_saved()

        # cp1 をドラッグ移動
        self._simulate_drag_handle(f"{ref.id}_cp1", 150.0, 150.0)

        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            # Undo 実行
            self.view.on_undo(None)
            mock_visible.assert_called()
            called_node = mock_visible.call_args[0][0]
            called_kwargs = mock_visible.call_args[1]
            self.assertEqual(called_node.id, self.node_a.id)
            self.assertTrue(called_kwargs.get("force_center"))

        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            # Redo 実行
            self.view.on_redo(None)
            mock_visible.assert_called()
            called_node = mock_visible.call_args[0][0]
            called_kwargs = mock_visible.call_args[1]
            self.assertEqual(called_node.id, self.node_a.id)
            self.assertTrue(called_kwargs.get("force_center"))

    def test_reference_history_capacity_and_branching(self):
        """制御点変更を11回行った場合に最古のスナップショットが破棄され、Undo後に新規操作でRedoがクリアされること"""
        ref = Reference(self.node_a.id, self.node_b.id)
        self.view.model.references.append(ref)
        self.view.selected_reference = ref
        self.view.selected_node = None
        self.view.history.clear()
        self.view.history.mark_saved()

        # 11回制御点を移動
        for i in range(11):
            self._simulate_drag_handle(f"{ref.id}_cp1", float(100 + i * 10), float(100 + i * 10))

        # 最大10回までUndoできること
        undo_count = 0
        while self.view.history.can_undo():
            self.view.on_undo(None)
            undo_count += 1
        self.assertEqual(undo_count, 10)
        self.assertFalse(self.view.history.can_undo())
        self.assertTrue(self.view.history.can_redo())

        # 1回Redo
        self.view.on_redo(None)
        self.assertTrue(self.view.history.can_redo())

        # 新しい制御点変更を行い、Redoスタックがクリアされることを確認
        self._simulate_drag_handle(f"{ref.id}_cp1", 999.0, 999.0)
        self.assertFalse(self.view.history.can_redo())



