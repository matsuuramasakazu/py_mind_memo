import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from py_mind_memo.models import MindMapModel, Node
from py_mind_memo.history import HistoryManager
from py_mind_memo.view import MindMapView


class TestSavePointSynchronization(unittest.TestCase):
    """スライス 1: セーブポイント同期（Save Point Tracking & is_modified 同期）のテスト"""

    def setUp(self):
        self.model = MindMapModel("Root")
        self.history = HistoryManager(self.model, max_snapshots=10)

    def test_save_point_undo_redo_and_further_mutation(self):
        """保存によるセーブポイント確立、Undoによるis_modified=False復元、Redoおよび更なる変更によるis_modified=True化"""
        # 初期状態
        self.assertFalse(self.model.is_modified)

        # 変更1: トピック追加
        self.history.record_snapshot(selected_id=self.model.root.id)
        child1 = self.model.add_node(self.model.root, "Child 1")
        self.assertTrue(self.model.is_modified)

        # ファイル保存（セーブポイント確立）
        self.history.mark_saved()
        self.assertFalse(self.model.is_modified)
        self.assertEqual(self.history.save_point_state_id, self.history.current_state_id)

        # 変更2: トピック追加
        self.history.record_snapshot(selected_id=child1.id)
        child2 = self.model.add_node(child1, "Child 2")
        self.assertTrue(self.model.is_modified)

        # 変更3: トピック追加
        self.history.record_snapshot(selected_id=child2.id)
        child3 = self.model.add_node(child2, "Child 3")
        self.assertTrue(self.model.is_modified)

        # Undo 1回目 -> 変更2の時点（未保存なので is_modified == True）
        self.history.undo()
        self.assertTrue(self.model.is_modified)

        # Undo 2回目 -> 変更1（保存時点）に戻る -> is_modified == False
        self.history.undo()
        self.assertFalse(self.model.is_modified)
        self.assertEqual(self.history.current_state_id, self.history.save_point_state_id)

        # Redo 1回目 -> 変更2の時点 -> is_modified == True
        self.history.redo()
        self.assertTrue(self.model.is_modified)

        # 再度 Undo -> 保存時点に戻る -> is_modified == False
        self.history.undo()
        self.assertFalse(self.model.is_modified)

        # 保存時点から新たな変更（分岐）を実行
        self.history.record_snapshot(selected_id=child1.id)
        self.model.add_node(child1, "Branch Child")
        self.assertTrue(self.model.is_modified)
        self.assertFalse(self.history.can_redo())

        # Undo -> 再び保存時点に戻る -> is_modified == False
        self.history.undo()
        self.assertFalse(self.model.is_modified)

    def test_save_point_past_undo(self):
        """保存時点より過去へUndoした場合にis_modified=Trueとなり、Redoで保存時点に戻るとis_modified=Falseになること"""
        # 初期状態 -> 変更1
        self.history.record_snapshot(selected_id=self.model.root.id)
        child = self.model.add_node(self.model.root, "Topic")
        self.assertTrue(self.model.is_modified)

        # 保存
        self.history.mark_saved()
        self.assertFalse(self.model.is_modified)

        # 変更2
        self.history.record_snapshot(selected_id=child.id)
        self.model.add_node(child, "SubTopic")
        self.assertTrue(self.model.is_modified)

        # Undo -> 保存時点 (変更1)
        self.history.undo()
        self.assertFalse(self.model.is_modified)

        # さらに Undo -> 保存時点より前の初期状態 -> is_modified == True
        self.history.undo()
        self.assertTrue(self.model.is_modified)

        # Redo -> 保存時点 (変更1) に戻る -> is_modified == False
        self.history.redo()
        self.assertFalse(self.model.is_modified)


class TestAutoSaveIntegration(unittest.TestCase):
    """自動保存完了時のセーブポイント同期テスト"""

    def setUp(self):
        self.root = tk.Tk()
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

    def test_auto_save_complete_establishes_save_point(self):
        """自動保存成功時にセーブポイントが同期され、その後のUndoでis_modifiedが正しく復元されること"""
        root_node = self.view.model.root
        self.view.selected_node = root_node

        # 変更1: 子トピック追加
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        child = self.view.selected_node
        self.assertTrue(self.view.model.is_modified)
        rev = self.view.model.modification_count

        # 自動保存完了をシミュレート
        self.view._on_auto_save_complete(True, rev)
        self.assertFalse(self.view.model.is_modified)
        self.assertEqual(self.view.history.save_point_state_id, self.view.history.current_state_id)

        # 変更2: さらに子トピック追加
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.model.is_modified)

        # Undo -> 自動保存時点に戻るため is_modified == False
        self.view.on_undo(None)
        self.assertFalse(self.view.model.is_modified)

        # Undo -> 自動保存より過去に戻るため is_modified == True
        self.view.on_undo(None)
        self.assertTrue(self.view.model.is_modified)

        # Redo -> 自動保存時点に戻るため is_modified == False
        self.view.on_redo(None)
        self.assertFalse(self.view.model.is_modified)


class TestDocumentLifecycle(unittest.TestCase):
    """スライス 2: ドキュメントライフサイクル時の履歴リセット（Ctrl+N, Ctrl+O, open_from_path）"""

    def setUp(self):
        self.root = tk.Tk()
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

    def test_open_file_clears_history_and_establishes_save_point(self):
        """ファイルを開いた（Ctrl+O）際にUndo/Redo履歴が完全にクリアされ、読み込み時点がセーブポイントとなること"""
        # 操作履歴を作る
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.history.can_undo())

        dummy_data = {
            "root": {
                "id": "root-opened",
                "text": "Opened Map",
                "children": [],
                "side": "root",
                "collapsed": False,
                "icon_path": None,
                "icon_data": None,
                "image_path": None,
                "image_data": None
            },
            "references": []
        }

        with patch('tkinter.filedialog.askopenfilename', return_value="test.json"), \
             patch('builtins.open', unittest.mock.mock_open(read_data='{}')), \
             patch('json.load', return_value=dummy_data):
            self.view.persistence.on_open()

        # 履歴スタックが完全に消去されていること
        self.assertFalse(self.view.history.can_undo())
        self.assertFalse(self.view.history.can_redo())
        self.assertEqual(len(self.view.history._undo_stack), 0)
        self.assertEqual(len(self.view.history._redo_stack), 0)
        self.assertFalse(self.view.model.is_modified)

        # 開いた後にトピックを追加してUndoすると、セーブポイントに戻りis_modified=Falseになること
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.model.is_modified)

        self.view.on_undo(None)
        self.assertFalse(self.view.model.is_modified)

    def test_open_template_clears_history_and_preserves_dirty_on_undo(self):
        """テンプレートから新規作成（Ctrl+N）した際、履歴がクリアされ、編集後初期状態にUndoしても未保存（is_modified=True）が維持されること"""
        # 操作履歴を作る
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.history.can_undo())

        template_data = {
            "root": {
                "id": "tpl-root",
                "text": "Template Root",
                "children": [],
                "side": "root",
                "collapsed": False,
                "icon_path": None,
                "icon_data": None,
                "image_path": None,
                "image_data": None
            },
            "references": []
        }

        with patch('builtins.open', unittest.mock.mock_open(read_data='{}')), \
             patch('json.load', return_value=template_data):
            self.view.persistence.on_open_template("template.json")

        # 履歴スタックが消去され、テンプレート読み込み直後は is_modified == True
        self.assertFalse(self.view.history.can_undo())
        self.assertFalse(self.view.history.can_redo())
        self.assertTrue(self.view.model.is_modified)

        # 編集を加える
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.model.is_modified)

        # テンプレート適用直後まで Undo
        self.view.on_undo(None)
        # まだディスクに保存されていないため、Undoしても is_modified は True のままであること
        self.assertTrue(self.view.model.is_modified)

    def test_open_from_path_clears_history(self):
        """open_from_path実行時に履歴がクリアされること"""
        self.view.on_add_child(None)
        self.view.editor.finish_edit()
        self.assertTrue(self.view.history.can_undo())

        dummy_data = {
            "root": {
                "id": "path-root",
                "text": "Path Root",
                "children": [],
                "side": "root",
                "collapsed": False,
                "icon_path": None,
                "icon_data": None,
                "image_path": None,
                "image_data": None
            },
            "references": []
        }

        with patch('builtins.open', unittest.mock.mock_open(read_data='{}')), \
             patch('json.load', return_value=dummy_data):
            self.view.persistence.open_from_path("dummy.json")

        self.assertFalse(self.view.history.can_undo())
        self.assertFalse(self.view.history.can_redo())
        self.assertFalse(self.view.model.is_modified)


class TestBoundaryUX(unittest.TestCase):
    """スライス 3: 履歴境界UX（ステータスバーフィードバック & タイマー管理）"""

    def setUp(self):
        self.root = tk.Tk()
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

    def test_undo_boundary_status_message(self):
        """これ以上Undoできない場合にステータスバーに「これ以上元に戻せません」と表示され、breakが返ること"""
        self.assertFalse(self.view.history.can_undo())
        ret = self.view.on_undo(None)
        self.assertEqual(ret, "break")
        self.assertEqual(self.view.status_bar.cget("text"), "これ以上元に戻せません")

    def test_redo_boundary_status_message(self):
        """これ以上Redoできない場合にステータスバーに「これ以上やり直せません」と表示され、breakが返ること"""
        self.assertFalse(self.view.history.can_redo())
        ret = self.view.on_redo(None)
        self.assertEqual(ret, "break")
        self.assertEqual(self.view.status_bar.cget("text"), "これ以上やり直せません")

    def test_show_status_message_timer_management(self):
        """show_status_messageが連続で呼ばれた際に既存タイマーがキャンセルされ、指定時間後に消去されること"""
        with patch.object(self.view.root, 'after', wraps=self.view.root.after) as mock_after, \
             patch.object(self.view.root, 'after_cancel', wraps=self.view.root.after_cancel) as mock_after_cancel:

            # 1回目のメッセージ呼び出し
            self.view.show_status_message("First Message", timeout=500)
            self.assertEqual(self.view.status_bar.cget("text"), "First Message")
            first_timer = getattr(self.view, '_status_timer', None)
            self.assertIsNotNone(first_timer)

            # 2回目のメッセージ呼び出し（直後に連続呼出）
            self.view.show_status_message("Second Message", timeout=500)
            self.assertEqual(self.view.status_bar.cget("text"), "Second Message")
            # 既存タイマーがキャンセルされたこと
            mock_after_cancel.assert_called_with(first_timer)
            second_timer = getattr(self.view, '_status_timer', None)
            self.assertIsNotNone(second_timer)
            self.assertNotEqual(first_timer, second_timer)

            # タイマーコールバック実行でステータスバーが空になり、_status_timerがNoneになること
            if hasattr(self.view, '_clear_status_message'):
                self.view._clear_status_message()
                self.assertEqual(self.view.status_bar.cget("text"), "")
                self.assertIsNone(self.view._status_timer)


class TestCapacityAndEviction(unittest.TestCase):
    """スライス 4: 履歴容量上限（10スナップショット上限）と押し出し時のセーブポイント整合性"""

    def setUp(self):
        self.root = tk.Tk()
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

    def test_capacity_strict_limit_10_and_boundary(self):
        """15回連続で変更を加えた場合、スタックサイズが10に制限され、10回Undoで枯渇し、11回目で境界通知が出ること"""
        # 15回トピックを追加
        for i in range(15):
            self.view.on_add_child(None)
            self.view.editor.finish_edit()

        # 履歴深さが10を超えていないこと
        self.assertEqual(len(self.view.history._undo_stack), 10)
        self.assertEqual(self.view.history._undo_stack.maxlen, 10)

        # 10回Undo可能であることを検証
        for u in range(10):
            self.assertTrue(self.view.history.can_undo())
            self.view.on_undo(None)

        # 11回目はUndo不可であり、ステータスバーに境界メッセージが表示されること
        self.assertFalse(self.view.history.can_undo())
        ret = self.view.on_undo(None)
        self.assertEqual(ret, "break")
        self.assertEqual(self.view.status_bar.cget("text"), "これ以上元に戻せません")

    def test_save_point_evicted_from_undo_stack(self):
        """保存後の変更が10回を超えてセーブポイントが押し出された場合でも、安全に動作しis_modified=Trueが維持されること"""
        # 変更1
        self.view.on_add_child(None)
        self.view.editor.finish_edit()

        # 保存実行（セーブポイント確立）
        self.view.history.mark_saved()
        self.assertFalse(self.view.model.is_modified)
        saved_state_id = self.view.history.save_point_state_id

        # その後、11回の変更を実行（保存時点のスナップショットが最古として破棄される）
        for i in range(11):
            self.view.on_add_child(None)
            self.view.editor.finish_edit()

        # 10回すべてUndoする
        for _ in range(10):
            self.view.on_undo(None)

        # 限界に到達
        self.assertFalse(self.view.history.can_undo())
        # セーブポイントは押し出されたため、現在の状態IDはセーブポイントIDとは一致せず、is_modified は True のまま
        self.assertNotEqual(self.view.history.current_state_id, saved_state_id)
        self.assertTrue(self.view.model.is_modified)


if __name__ == '__main__':
    unittest.main()



