import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.view import MindMapView
from py_mind_memo.models import MindMapModel

class TestAutoSave(unittest.TestCase):
    def setUp(self):
        # UIコンポーネントをすべてモック化して MindMapView を初期化
        self.root = MagicMock(spec=tk.Tk)
        with patch('py_mind_memo.view.GraphicsEngine'), \
             patch('py_mind_memo.view.LayoutEngine'), \
             patch('py_mind_memo.view.NodeEditor'), \
             patch('py_mind_memo.view.DragDropHandler'), \
             patch('py_mind_memo.view.KeyboardNavigator'), \
             patch('py_mind_memo.view.PersistenceHandler'), \
             patch('py_mind_memo.view.MindMapView.render'), \
             patch('tkinter.Canvas'), \
             patch('tkinter.Frame'), \
             patch('tkinter.Scrollbar'), \
             patch('tkinter.Menu'), \
             patch('tkinter.Label'):
            
            self.view = MindMapView(self.root)
            # 自動保存ループを止めるために after を固定する
            self.root.after.reset_mock()

    def test_auto_save_check_calls_on_save_when_modified_and_path_exists(self):
        """ファイルパスがあり、変更がある場合に保存が実行されること"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = True
        self.view.editor.is_editing.return_value = False
        self.view.persistence.on_save.return_value = True
        
        self.view._auto_save_check()
        
        self.view.persistence.on_save.assert_called_once()
        # 通知が表示されること
        self.view.status_bar.config.assert_any_call(text="Saved automatically")

        # 1000ms後の消去予約の検証
        # _auto_save_check内では after が2回呼ばれる (通知消去: 1000ms, 次のループ: 10000ms)
        calls = self.root.after.call_args_list
        status_clear_call = next(c for c in calls if c.args[0] == 1000)
        timeout, callback = status_clear_call.args
        self.assertEqual(timeout, 1000)
        
        # コールバックを実行して消去されることを確認
        callback()
        self.view.status_bar.config.assert_called_with(text="")

    def test_auto_save_check_does_not_call_on_save_when_not_modified(self):
        """変更がない場合は保存が実行されないこと"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = False
        
        self.view._auto_save_check()
        
        self.view.persistence.on_save.assert_not_called()

    def test_auto_save_check_does_not_call_on_save_when_no_path(self):
        """ファイルパスがない（一度も保存されていない）場合は保存が実行されないこと"""
        self.view.persistence.current_file_path = None
        self.view.model.is_modified = True
        
        self.view._auto_save_check()
        
        self.view.persistence.on_save.assert_not_called()

    def test_auto_save_check_does_not_call_on_save_when_editing(self):
        """ノード編集中は保存が実行されないこと"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = True
        self.view.editor.is_editing.return_value = True
        
        self.view._auto_save_check()
        
        self.view.persistence.on_save.assert_not_called()

    def test_after_is_called_again(self):
        """_auto_save_check の最後で再び after が呼ばれ、ループが継続すること"""
        self.root.after.reset_mock()
        self.view._auto_save_check()
        # 10000ms 後に再び自分を呼ぶように設定されているか
        self.root.after.assert_any_call(10000, self.view._auto_save_check)

if __name__ == '__main__':
    unittest.main()
