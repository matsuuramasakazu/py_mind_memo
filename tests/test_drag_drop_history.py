import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.models import MindMapModel, Node
from py_mind_memo.history import HistoryManager
from py_mind_memo.drag_drop import DragDropHandler
from py_mind_memo.layout import LayoutEngine
from py_mind_memo.view import MindMapView


class TestDragDropHistoryUnit(unittest.TestCase):
    """DragDropHandler と HistoryManager の単体結合テスト"""

    def setUp(self):
        self.root = tk.Tk()
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        self.model = MindMapModel("Root")
        self.history = HistoryManager(self.model)
        self.layout_engine = LayoutEngine()
        self.graphics = MagicMock()
        self.render_called = False

        def mock_render():
            self.render_called = True

        self.mock_render = mock_render

        # トピック構造の構築:
        # Root
        #  ├── Child A (left)
        #  │    ├── Grandchild A1
        #  │    └── Grandchild A2
        #  └── Child B (right)
        self.child_a = self.model.add_node(self.model.root, "Child A")
        self.child_a.direction = "left"
        self.child_b = self.model.add_node(self.model.root, "Child B")
        self.child_b.direction = "right"
        self.grandchild_a1 = self.model.add_node(self.child_a, "Grandchild A1")
        self.grandchild_a2 = self.model.add_node(self.child_a, "Grandchild A2")

        self.handler = DragDropHandler(
            canvas=self.canvas,
            model=self.model,
            graphics=self.graphics,
            layout_engine=self.layout_engine,
            render_callback=self.mock_render,
            find_node_at=self._find_node_mock,
            logical_center_x=400,
            logical_center_y=300,
            history=self.history,
        )
        self.target_node = None
        self.model.is_modified = False
        self.history.mark_saved()

    def tearDown(self):
        self.root.destroy()

    def _find_node_mock(self, x, y):
        return self.target_node

    def _simulate_drag_and_drop(self, node: Node, target: Node, distance: int = 20):
        start_event = MagicMock(x=100, y=100)
        motion_event = MagicMock(x=100 + distance, y=100 + distance)
        drop_event = MagicMock(x=100 + distance, y=100 + distance)

        self.target_node = target
        self.handler.start_drag(start_event, node)
        self.handler.handle_motion(motion_event)
        self.handler.handle_drop(drop_event)

    def test_drag_drop_to_new_parent_records_snapshot_and_undo_redo(self):
        """新しい親へのドロップでスナップショットが記録され、Undoで元の親・順序・ブランチ方向が復元され、Redoで再適用されること"""
        # 初期状態の確認
        self.assertEqual(self.grandchild_a1.parent, self.child_a)
        self.assertEqual(self.child_a.children, [self.grandchild_a1, self.grandchild_a2])
        self.assertEqual(self.grandchild_a1.direction, "left")
        self.assertFalse(self.history.can_undo())

        # Grandchild A1 を Child B にドラッグ＆ドロップ
        self._simulate_drag_and_drop(self.grandchild_a1, self.child_b)

        # 移動後の確認
        self.assertTrue(self.history.can_undo())
        self.assertEqual(self.grandchild_a1.parent, self.child_b)
        self.assertIn(self.grandchild_a1, self.child_b.children)
        self.assertNotIn(self.grandchild_a1, self.child_a.children)
        self.assertEqual(self.grandchild_a1.direction, "right")
        self.assertTrue(self.model.is_modified)

        # Undo 実行: 元の親 Child A、順序（A2の前）、元の方向 'left' に復元されること
        res = self.history.undo(
            current_selected_id=self.grandchild_a1.id,
            current_selected_type="node"
        )
        self.assertIsNotNone(res)
        restored_id, restored_type = res
        self.assertEqual(restored_id, self.grandchild_a1.id)
        self.assertEqual(restored_type, "node")

        # 復元されたツリーの確認
        restored_a1 = self.model.find_node_by_id(self.grandchild_a1.id)
        restored_a = self.model.find_node_by_id(self.child_a.id)
        restored_b = self.model.find_node_by_id(self.child_b.id)
        self.assertIsNotNone(restored_a1)
        self.assertEqual(restored_a1.parent, restored_a)
        self.assertEqual(restored_a.children[0].id, restored_a1.id)
        self.assertEqual(len(restored_a.children), 2)
        self.assertEqual(len(restored_b.children), 0)
        self.assertEqual(restored_a1.direction, "left")

        # Redo 実行: 再び Child B の配下に移動すること
        res_redo = self.history.redo(
            current_selected_id=restored_a1.id,
            current_selected_type="node"
        )
        self.assertIsNotNone(res_redo)
        redo_id, redo_type = res_redo
        self.assertEqual(redo_id, self.grandchild_a1.id)

        redo_a1 = self.model.find_node_by_id(self.grandchild_a1.id)
        redo_a = self.model.find_node_by_id(self.child_a.id)
        redo_b = self.model.find_node_by_id(self.child_b.id)
        self.assertEqual(redo_a1.parent, redo_b)
        self.assertEqual(len(redo_a.children), 1)
        self.assertEqual(len(redo_b.children), 1)
        self.assertEqual(redo_a1.direction, "right")

    def test_drag_drop_to_root_and_undo_restores_balanced_direction(self):
        """ルート直下への移動後のUndoで元の親および方向が復元されること"""
        self.assertEqual(self.grandchild_a1.direction, "left")

        # Grandchild A1 を Root にドロップ
        self._simulate_drag_and_drop(self.grandchild_a1, self.model.root)

        self.assertEqual(self.grandchild_a1.parent, self.model.root)
        self.assertIn(self.grandchild_a1, self.model.root.children)

        # Undo
        self.history.undo(
            current_selected_id=self.grandchild_a1.id,
            current_selected_type="node"
        )
        restored_a1 = self.model.find_node_by_id(self.grandchild_a1.id)
        restored_a = self.model.find_node_by_id(self.child_a.id)
        self.assertEqual(restored_a1.parent, restored_a)
        self.assertEqual(restored_a1.direction, "left")

    def test_layout_calculations_restored_cleanly_on_undo_redo(self):
        """Undo/Redo時にブランチ方向およびレイアウト計算（座標配置）がクリーンに復元されること"""
        self.graphics.get_text_size.return_value = (100, 40)

        # 3つ目の子ノードを追加して左側グループ（240°）を作成
        child_c = self.model.add_node(self.model.root, "Child C")
        grandchild_c1 = self.model.add_node(child_c, "Grandchild C1")

        # 移動前のレイアウト計算
        self.layout_engine.apply_layout(self.model, self.graphics, 400, 300)
        orig_x, orig_y = grandchild_c1.x, grandchild_c1.y
        orig_dir = grandchild_c1.direction
        self.assertEqual(orig_dir, "left")
        self.assertLess(orig_x, 400) # 左側にあること

        # Grandchild C1 を Child A (右側) に移動
        self._simulate_drag_and_drop(grandchild_c1, self.child_a)
        self.layout_engine.apply_layout(self.model, self.graphics, 400, 300)
        moved_x, moved_y = grandchild_c1.x, grandchild_c1.y
        moved_dir = grandchild_c1.direction
        self.assertEqual(moved_dir, "right")
        self.assertGreater(moved_x, 400) # 右側に移動したこと

        # Undo 実行
        self.history.undo(
            current_selected_id=grandchild_c1.id,
            current_selected_type="node"
        )
        self.layout_engine.apply_layout(self.model, self.graphics, 400, 300)
        restored_c1 = self.model.find_node_by_id(grandchild_c1.id)
        self.assertEqual(restored_c1.direction, orig_dir)
        self.assertEqual(restored_c1.x, orig_x)
        self.assertEqual(restored_c1.y, orig_y)

        # Redo 実行
        self.history.redo(
            current_selected_id=restored_c1.id,
            current_selected_type="node"
        )
        self.layout_engine.apply_layout(self.model, self.graphics, 400, 300)
        redo_c1 = self.model.find_node_by_id(grandchild_c1.id)
        self.assertEqual(redo_c1.direction, moved_dir)
        self.assertEqual(redo_c1.x, moved_x)
        self.assertEqual(redo_c1.y, moved_y)

    def test_no_snapshot_when_dropped_on_current_parent(self):
        """現在の親にドロップした場合、変更されずスナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.grandchild_a1, self.child_a)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_no_snapshot_when_dropped_on_self(self):
        """自分自身にドロップした場合、スナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.grandchild_a1, self.grandchild_a1)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_no_snapshot_when_dropped_on_descendant(self):
        """自身の子孫にドロップした場合、スナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.child_a, self.grandchild_a1)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_no_snapshot_when_dropped_on_empty_canvas(self):
        """空のキャンバス領域にドロップした場合、スナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.grandchild_a1, None)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_no_snapshot_when_dragging_root_node(self):
        """ルートノードをドラッグしようとしても移動せずスナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.model.root, self.child_a)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_no_snapshot_when_drag_threshold_not_exceeded(self):
        """移動量が閾値（5px）以下の場合、ドラッグと判定されずスナップショットが記録されないこと"""
        self._simulate_drag_and_drop(self.grandchild_a1, self.child_b, distance=2)
        self.assertFalse(self.history.can_undo())
        self.assertFalse(self.model.is_modified)

    def test_save_point_synchronization(self):
        """保存ポイントでのUndo/Redo時に is_modified フラグが正しく同期すること"""
        self.history.mark_saved()
        self.assertFalse(self.model.is_modified)

        # 移動実行
        self._simulate_drag_and_drop(self.grandchild_a1, self.child_b)
        self.assertTrue(self.model.is_modified)

        # Undo で保存時点に戻る -> is_modified が False に戻ること
        self.history.undo(
            current_selected_id=self.grandchild_a1.id,
            current_selected_type="node"
        )
        self.assertFalse(self.model.is_modified)

        # Redo で未保存状態になる -> is_modified が True になること
        self.history.redo(
            current_selected_id=self.grandchild_a1.id,
            current_selected_type="node"
        )
        self.assertTrue(self.model.is_modified)

    def test_branching_clears_redo_stack(self):
        """Undo後に新たな操作を行うとRedoスタックがクリアされること"""
        self._simulate_drag_and_drop(self.grandchild_a1, self.child_b)
        self.assertTrue(self.history.can_undo())

        # Undo
        self.history.undo(
            current_selected_id=self.grandchild_a1.id,
            current_selected_type="node"
        )
        self.assertTrue(self.history.can_redo())

        # 新たな変更操作（子トピック追加）
        self.history.record_snapshot(selected_id=self.child_a.id, selected_type="node")
        self.model.add_node(self.child_a, "New Child")

        # Redoスタックがクリアされていること
        self.assertFalse(self.history.can_redo())


class TestDragDropHistoryViewIntegration(unittest.TestCase):
    """MindMapView を介したドラッグ＆ドロップとキーボードショートカット（Ctrl+Z / Ctrl+Y）の結合テスト"""

    def setUp(self):
        self.root = tk.Tk()
        self.patchers = [
            patch('py_mind_memo.view.GraphicsEngine'),
            patch('py_mind_memo.view.KeyboardNavigator'),
            patch('py_mind_memo.view.MindMapView._create_menu'),
            patch('py_mind_memo.view.MindMapView.render'),
        ]
        for p in self.patchers:
            p.start()

        self.view = MindMapView(self.root)

        self.child_a = self.view.model.add_node(self.view.model.root, "Child A")
        self.child_a.direction = "left"
        self.child_b = self.view.model.add_node(self.view.model.root, "Child B")
        self.child_b.direction = "right"
        self.sub_a = self.view.model.add_node(self.child_a, "Sub A")

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.root.destroy()

    def test_view_drag_drop_undo_redo_workflow(self):
        """View上でノードクリック〜ドラッグ〜ドロップ〜Undo〜Redoの一連のフローで選択状態と階層が正しく管理されること"""
        # Sub A を選択
        self.view.selected_node = self.sub_a

        # ドロップ先を Child B に設定してドロップ
        with patch.object(self.view.drag_handler, 'find_node_at', return_value=self.child_b):
            start_event = MagicMock(x=100, y=100)
            motion_event = MagicMock(x=150, y=150)
            drop_event = MagicMock(x=150, y=150)

            self.view.drag_handler.start_drag(start_event, self.sub_a)
            self.view.drag_handler.handle_motion(motion_event)
            self.view.drag_handler.handle_drop(drop_event)

        # 移動後の確認
        self.assertEqual(self.sub_a.parent, self.child_b)
        self.assertTrue(self.view.history.can_undo())

        # Ctrl+Z (Undo) 実行
        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            self.view.on_undo(None)
            self.assertTrue(mock_visible.called)
            # 復元されたノードが選択されていること
            self.assertEqual(self.view.selected_node.id, self.sub_a.id)
            self.assertEqual(self.view.selected_node.parent.id, self.child_a.id)

        # Ctrl+Y (Redo) 実行
        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            self.view.on_redo(None)
            self.assertTrue(mock_visible.called)
            # 再適用されたノードが選択されていること
            self.assertEqual(self.view.selected_node.id, self.sub_a.id)
            self.assertEqual(self.view.selected_node.parent.id, self.child_b.id)


if __name__ == '__main__':
    unittest.main()
