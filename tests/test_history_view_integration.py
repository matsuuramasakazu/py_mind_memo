import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.models import MindMapModel, Node, Reference
from py_mind_memo.view import MindMapView

class TestHistoryViewIntegration(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        # 不要な描画やファイルI/O等をモックしてテストを高速・安定化
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

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.root.destroy()

    def test_undo_redo_add_child(self):
        """子トピック追加後のUndoでトピックが削除され親が選択され、Redoで復元されること"""
        root_node = self.view.model.root
        self.view.selected_node = root_node

        # 子トピック追加
        self.view.on_add_child(None)
        self.assertEqual(len(root_node.children), 1)
        child = root_node.children[0]
        self.assertEqual(self.view.selected_node, child)

        # Undo 実行
        self.view.on_undo(None)
        self.assertEqual(len(self.view.model.root.children), 0)
        self.assertEqual(self.view.selected_node.id, root_node.id)

        # Redo 実行
        self.view.on_redo(None)
        self.assertEqual(len(self.view.model.root.children), 1)
        self.assertEqual(self.view.selected_node.id, child.id)

    def test_undo_redo_add_sibling(self):
        """兄弟トピック追加後のUndoで兄弟が削除され直前のトピックが選択されること"""
        child1 = self.view.model.add_node(self.view.model.root, "Child 1")
        self.view.selected_node = child1

        # 兄弟トピック追加
        self.view.on_add_sibling(None)
        self.assertEqual(len(self.view.model.root.children), 2)
        child2 = self.view.model.root.children[1]
        self.assertEqual(self.view.selected_node, child2)

        # Undo 実行
        self.view.on_undo(None)
        self.assertEqual(len(self.view.model.root.children), 1)
        self.assertEqual(self.view.selected_node.id, child1.id)

        # Redo 実行
        self.view.on_redo(None)
        self.assertEqual(len(self.view.model.root.children), 2)
        self.assertEqual(self.view.selected_node.id, child2.id)

    def test_undo_redo_delete_topic(self):
        """トピック削除後のUndoで削除されたトピック、部分木、関連参照線が復元されること"""
        child = self.view.model.add_node(self.view.model.root, "Child")
        grandchild = self.view.model.add_node(child, "Grandchild")
        ref = Reference(child.id, self.view.model.root.id)
        self.view.model.references.append(ref)

        self.view.selected_node = child

        # 削除実行
        self.view.on_delete(None)
        self.assertEqual(len(self.view.model.root.children), 0)
        self.assertEqual(len(self.view.model.references), 0)
        self.assertEqual(self.view.selected_node.id, self.view.model.root.id)

        # Undo 実行: 子トピック、孫トピック、参照線が全て復元され、削除対象だったトピックが選択されること
        self.view.on_undo(None)
        self.assertEqual(len(self.view.model.root.children), 1)
        restored_child = self.view.model.root.children[0]
        self.assertEqual(restored_child.id, child.id)
        self.assertEqual(len(restored_child.children), 1)
        self.assertEqual(restored_child.children[0].id, grandchild.id)
        self.assertEqual(len(self.view.model.references), 1)
        self.assertEqual(self.view.model.references[0].id, ref.id)
        self.assertEqual(self.view.selected_node.id, child.id)

        # Redo 実行: 再び削除されること
        self.view.on_redo(None)
        self.assertEqual(len(self.view.model.root.children), 0)
        self.assertEqual(len(self.view.model.references), 0)
        self.assertEqual(self.view.selected_node.id, self.view.model.root.id)

    def test_undo_redo_reorder_topic(self):
        """トピック移動（Ctrl+Up / Ctrl+Down）のUndo/Redoで並び順が復元されること"""
        child1 = self.view.model.add_node(self.view.model.root, "Child 1")
        child2 = self.view.model.add_node(self.view.model.root, "Child 2")

        self.view.selected_node = child2

        # 上へ移動 (child2 が先頭へ)
        self.view.on_move_node_up(None)
        self.assertEqual(self.view.model.root.children[0].id, child2.id)
        self.assertEqual(self.view.model.root.children[1].id, child1.id)

        # Undo 実行: 元の順序 [child1, child2] に戻ること
        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            self.view.on_undo(None)
            self.assertTrue(mock_visible.called)
            self.assertEqual(mock_visible.call_args[0][0].id, child2.id)
            self.assertEqual(mock_visible.call_args[1].get('force_center'), True)
            self.assertEqual(self.view.model.root.children[0].id, child1.id)
            self.assertEqual(self.view.model.root.children[1].id, child2.id)
            self.assertEqual(self.view.selected_node.id, child2.id)

        # Redo 実行: 再び [child2, child1] になること
        with patch.object(self.view, 'ensure_node_visible') as mock_visible:
            self.view.on_redo(None)
            self.assertTrue(mock_visible.called)
            self.assertEqual(mock_visible.call_args[0][0].id, child2.id)
            self.assertEqual(mock_visible.call_args[1].get('force_center'), True)
            self.assertEqual(self.view.model.root.children[0].id, child2.id)
            self.assertEqual(self.view.model.root.children[1].id, child1.id)
            self.assertEqual(self.view.selected_node.id, child2.id)

    def test_undo_redo_move_node_down(self):
        """Ctrl+Down によるトピック下移動のUndo/Redoテスト"""
        child1 = self.view.model.add_node(self.view.model.root, "Child 1")
        child2 = self.view.model.add_node(self.view.model.root, "Child 2")

        self.view.selected_node = child1

        # 下へ移動 (child1 が2番目へ)
        self.view.on_move_node_down(None)
        self.assertEqual(self.view.model.root.children[0].id, child2.id)
        self.assertEqual(self.view.model.root.children[1].id, child1.id)

        # Undo
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.children[0].id, child1.id)
        self.assertEqual(self.view.model.root.children[1].id, child2.id)
        self.assertEqual(self.view.selected_node.id, child1.id)

        # Redo
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.children[0].id, child2.id)
        self.assertEqual(self.view.model.root.children[1].id, child1.id)
        self.assertEqual(self.view.selected_node.id, child1.id)

    def test_boundary_status_messages(self):
        """これ以上Undo/Redoできない場合にステータスバーメッセージが表示されること"""
        with patch.object(self.view, 'show_status_message') as mock_status:
            # 何もしていない初期状態でUndo
            self.view.on_undo(None)
            mock_status.assert_called_with("これ以上元に戻せません")

            # 何もしていない初期状態でRedo
            mock_status.reset_mock()
            self.view.on_redo(None)
            mock_status.assert_called_with("これ以上やり直せません")

    def test_inline_editor_suppresses_undo_redo(self):
        """インライン編集中はCtrl+Z / Ctrl+Yが抑止されること"""
        self.view.editor.is_editing = MagicMock(return_value=True)
        with patch.object(self.view.history, 'undo') as mock_undo, \
             patch.object(self.view.history, 'redo') as mock_redo:
            wrapped_undo = self.view._wrap_handler(self.view.on_undo)
            wrapped_redo = self.view._wrap_handler(self.view.on_redo)

            res_u = wrapped_undo(None)
            self.assertEqual(res_u, "break")
            mock_undo.assert_not_called()

            res_r = wrapped_redo(None)
            self.assertEqual(res_r, "break")
            mock_redo.assert_not_called()

if __name__ == '__main__':
    unittest.main()
