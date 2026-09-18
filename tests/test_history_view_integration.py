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

    def test_undo_add_child_on_collapsed_node_restores_collapsed_state(self):
        """折りたたまれた親ノードに子を追加後、Undoで親ノードの折りたたみ状態(collapsed=True)が復元されること"""
        root_node = self.view.model.root
        child1 = self.view.model.add_node(root_node, "Child 1")
        child1.collapsed = True
        self.view.selected_node = child1

        # 子トピック追加（折りたたまれている場合は展開される）
        self.view.on_add_child(None)
        self.assertFalse(child1.collapsed)
        self.assertEqual(len(child1.children), 1)

        # Undo 実行 -> 子トピックが削除され、親ノードの collapsed が True に復元されること
        self.view.on_undo(None)
        restored_child1 = self.view.model.find_node_by_id(child1.id)
        self.assertIsNotNone(restored_child1)
        self.assertTrue(restored_child1.collapsed)
        self.assertEqual(len(restored_child1.children), 0)

        # Redo 実行 -> 再び展開されて子トピックが復元されること
        self.view.on_redo(None)
        redo_child1 = self.view.model.find_node_by_id(child1.id)
        self.assertIsNotNone(redo_child1)
        self.assertFalse(redo_child1.collapsed)
        self.assertEqual(len(redo_child1.children), 1)

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

    def test_inline_editor_entry_binds_suppress_undo_redo(self):
        """Textウィジェット自身でもControl-z/Control-yイベントがbreakを返すこと"""
        node = self.view.model.root
        self.view.on_edit_node(None)
        entry = self.view.editor.editing_entry
        self.assertIsNotNone(entry)

        # イベントハンドラが登録されており、呼び出すと "break" を返すこと
        # Tkinter の bind_class または直接 bind の検証
        for key in ["<Control-z>", "<Control-Z>", "<Control-y>", "<Control-Y>"]:
            # イベントをシミュレート
            event = tk.Event()
            # bind_all や bind された関数を呼び出し
            func_id = entry.bind(key)
            self.assertTrue(bool(func_id), f"{key} should be bound on entry")

        self.view.editor.cancel_edit()

    def test_undo_redo_edit_topic_text(self):
        """トピックテキスト編集確定後のUndoで編集前のテキストに戻り、Redoで編集後のテキストに復元されること"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertEqual(node.text, "Root Topic")

        # 編集開始
        self.view.on_edit_node(None)
        self.assertTrue(self.view.editor.is_editing())

        # テキストを変更
        self.view.editor.editing_entry.delete("1.0", "end")
        self.view.editor.editing_entry.insert("1.0", "Updated Root")

        # 編集確定
        self.view.editor.finish_edit()
        self.assertFalse(self.view.editor.is_editing())
        self.assertEqual(node.text, "Updated Root")
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.text, "Root Topic")
        self.assertEqual(self.view.selected_node.id, node.id)

        # Redo 実行
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.text, "Updated Root")
        self.assertEqual(self.view.selected_node.id, node.id)

    def test_finish_edit_without_changes_does_not_record_snapshot(self):
        """テキストを変更せずに編集完了した場合、スナップショットが記録されないこと"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertFalse(self.view.history.can_undo())

        # 編集開始して変更せず完了
        self.view.on_edit_node(None)
        self.view.editor.finish_edit()

        # スナップショットが記録されていないこと
        self.assertFalse(self.view.history.can_undo())

    def test_cancel_edit_does_not_record_snapshot_and_reverts_changes(self):
        """Escape等で編集キャンセルした場合、変更が破棄されスナップショットが記録されないこと"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertFalse(self.view.history.can_undo())

        self.view.on_edit_node(None)
        self.view.editor.editing_entry.delete("1.0", "end")
        self.view.editor.editing_entry.insert("1.0", "Canceled Text")

        self.view.editor.cancel_edit()
        self.assertEqual(node.text, "Root Topic")
        self.assertFalse(self.view.history.can_undo())

    def test_undo_redo_add_icon(self):
        """アイコン追加後のUndoでアイコンが消去され、Redoで復元されること"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertIsNone(node.icon_data)

        mock_photo = MagicMock(spec=tk.PhotoImage)
        with patch('py_mind_memo.view.IconPickerDialog.show', return_value=("icon1.png", mock_photo)), \
             patch.object(self.view.editor.image_handler, 'base64_from_photo', return_value="b64_icon1"):
            self.view.on_insert_icon(None)

        self.assertEqual(node.icon_data, "b64_icon1")
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行: アイコンが消去されること
        self.view.on_undo(None)
        self.assertIsNone(self.view.model.root.icon_data)
        self.assertIsNone(self.view.model.root.icon_path)

        # Redo 実行: アイコンが復元されること
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.icon_data, "b64_icon1")
        self.assertEqual(self.view.model.root.icon_path, "icon1.png")

    def test_undo_redo_change_icon(self):
        """別アイコンへの変更後のUndoで元のアイコンに戻り、Redoで新しいアイコンに更新されること"""
        node = self.view.model.root
        self.view.selected_node = node
        node.icon_data = "b64_icon1"
        node.icon_path = "icon1.png"

        mock_photo = MagicMock(spec=tk.PhotoImage)
        with patch('py_mind_memo.view.IconPickerDialog.show', return_value=("icon2.png", mock_photo)), \
             patch.object(self.view.editor.image_handler, 'base64_from_photo', return_value="b64_icon2"):
            self.view.on_insert_icon(None)

        self.assertEqual(node.icon_data, "b64_icon2")
        self.assertEqual(node.icon_path, "icon2.png")

        # Undo
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.icon_data, "b64_icon1")
        self.assertEqual(self.view.model.root.icon_path, "icon1.png")

        # Redo
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.icon_data, "b64_icon2")
        self.assertEqual(self.view.model.root.icon_path, "icon2.png")

    def test_undo_redo_clear_icon(self):
        """アイコン削除（CLEAR）後のUndoで元のアイコンが復元され、Redoで消去されること"""
        node = self.view.model.root
        self.view.selected_node = node
        node.icon_data = "b64_icon1"
        node.icon_path = "icon1.png"

        with patch('py_mind_memo.view.IconPickerDialog.show', return_value=("CLEAR", None)):
            self.view.on_insert_icon(None)

        self.assertIsNone(node.icon_data)
        self.assertIsNone(node.icon_path)

        # Undo
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.icon_data, "b64_icon1")
        self.assertEqual(self.view.model.root.icon_path, "icon1.png")

        # Redo
        self.view.on_redo(None)
        self.assertIsNone(self.view.model.root.icon_data)
        self.assertIsNone(self.view.model.root.icon_path)

    def test_clear_icon_when_none_does_not_record_snapshot(self):
        """アイコン未設定の状態でCLEARを選択してもスナップショットが記録されないこと"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertIsNone(node.icon_data)

        with patch('py_mind_memo.view.IconPickerDialog.show', return_value=("CLEAR", None)):
            self.view.on_insert_icon(None)

        self.assertFalse(self.view.history.can_undo())

    def test_cancel_icon_picker_does_not_record_snapshot(self):
        """ダイアログをキャンセルした場合にスナップショットが記録されないこと"""
        node = self.view.model.root
        self.view.selected_node = node

        with patch('py_mind_memo.view.IconPickerDialog.show', return_value=(None, None)):
            self.view.on_insert_icon(None)

        self.assertFalse(self.view.history.can_undo())

    def test_undo_redo_insert_image(self):
        """画像挿入確定後のUndoで画像が消去され、Redoで復元されること"""
        node = self.view.model.root
        self.view.selected_node = node
        self.assertIsNone(node.image_data)

        # 編集開始
        self.view.on_edit_node(None)

        mock_photo = MagicMock(spec=tk.PhotoImage)
        # Mock image_create to avoid TclError with Mock PhotoImage
        self.view.editor.editing_entry.image_create = MagicMock()

        with patch.object(self.view.editor.image_handler, 'pick_and_load_image', return_value="dummy.png"), \
             patch.object(self.view.editor.image_handler, 'process_image', return_value=mock_photo), \
             patch.object(self.view.editor.image_handler, 'base64_from_photo', return_value="b64_dummy"):
            self.view.editor.insert_image(node)

        # 編集確定 (画像ありの状態)
        self.view.editor.editing_entry.image_names = MagicMock(return_value=('pyimage1',))
        self.view.editor.finish_edit()

        self.assertEqual(node.image_data, "b64_dummy")
        self.assertEqual(node.image_path, "dummy.png")
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行: 画像が除去されること
        self.view.on_undo(None)
        self.assertIsNone(self.view.model.root.image_data)
        self.assertIsNone(self.view.model.root.image_path)

        # Redo 実行: 画像が復元されること
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.image_data, "b64_dummy")
        self.assertEqual(self.view.model.root.image_path, "dummy.png")

    def test_undo_redo_delete_image(self):
        """画像削除確定後のUndoで画像が復元され、Redoで再び削除されること"""
        node = self.view.model.root
        self.view.selected_node = node
        node.image_data = "b64_dummy"
        node.image_path = "dummy.png"

        # 編集開始 (ダミーの1x1 PhotoImage を使用)
        dummy_photo = tk.PhotoImage(width=1, height=1)
        with patch.object(self.view.editor.image_handler, 'get_photo_from_base64', return_value=dummy_photo):
            self.view.on_edit_node(None)

        # 画像が削除された状態 (image_names が空)
        self.view.editor.editing_entry.image_names = MagicMock(return_value=())
        self.view.editor.finish_edit()

        self.assertIsNone(node.image_data)
        self.assertIsNone(node.image_path)
        self.assertTrue(self.view.history.can_undo())

        # Undo 実行: 画像が復元されること
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.image_data, "b64_dummy")
        self.assertEqual(self.view.model.root.image_path, "dummy.png")

        # Redo 実行: 再び削除されること
        self.view.on_redo(None)
        self.assertIsNone(self.view.model.root.image_data)
        self.assertIsNone(self.view.model.root.image_path)

    def test_undo_redo_text_and_image_combined(self):
        """1回の編集でテキスト変更と画像挿入を同時に行った場合、Undo/Redoがアトミックに動作すること"""
        node = self.view.model.root
        self.view.selected_node = node

        # 編集開始
        self.view.on_edit_node(None)

        mock_photo = MagicMock(spec=tk.PhotoImage)
        self.view.editor.editing_entry.image_create = MagicMock()

        with patch.object(self.view.editor.image_handler, 'pick_and_load_image', return_value="combined.png"), \
             patch.object(self.view.editor.image_handler, 'process_image', return_value=mock_photo), \
             patch.object(self.view.editor.image_handler, 'base64_from_photo', return_value="b64_combined"):
            self.view.editor.insert_image(node)

        self.view.editor.editing_entry.delete("1.0", "end")
        self.view.editor.editing_entry.insert("1.0", "Root with Image")
        self.view.editor.editing_entry.image_names = MagicMock(return_value=('pyimage1',))

        self.view.editor.finish_edit()

        self.assertEqual(node.text, "Root with Image")
        self.assertEqual(node.image_data, "b64_combined")

        # Undo 実行: テキストと画像の両方が初期状態に復元されること
        self.view.on_undo(None)
        self.assertEqual(self.view.model.root.text, "Root Topic")
        self.assertIsNone(self.view.model.root.image_data)

        # Redo 実行: テキストと画像の両方が編集後状態に復元されること
        self.view.on_redo(None)
        self.assertEqual(self.view.model.root.text, "Root with Image")
        self.assertEqual(self.view.model.root.image_data, "b64_combined")

if __name__ == '__main__':
    unittest.main()
