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
        # 実オブジェクトのリビジョン機能を使用
        self.view.model.is_modified = True
        current_rev = self.view.model.modification_count
        self.view.editor.is_editing.return_value = False
        
        with patch('threading.Thread') as mock_thread:
            # ターゲット関数を即座に実行する
            def start_side_effect():
                target = mock_thread.call_args.kwargs['target']
                target()
            mock_thread.return_value.start.side_effect = start_side_effect

            self.view._auto_save_check()
            
            # データのキャプチャと書き込みの検証
            self.view.persistence._perform_write_to_file.assert_called_once()
            
            # メインスレッド処理の結果 (成功時) を手動で呼び出す
            self.root.after.assert_any_call(0, self.view._on_auto_save_complete, True, current_rev)
            
            # 完了処理を直接呼んで通知を検証
            self.view._on_auto_save_complete(True, current_rev)
            self.view.status_bar.config.assert_any_call(text="Saved automatically")

    def test_auto_save_check_does_not_notify_on_failure(self):
        """保存失敗時に通知が表示されないこと"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = True
        current_rev = self.view.model.modification_count
        self.view.editor.is_editing.return_value = False
        # 書き込み例外を発生させる
        self.view.persistence._perform_write_to_file.side_effect = Exception("error")
        
        with patch('threading.Thread') as mock_thread:
            def start_side_effect():
                target = mock_thread.call_args.kwargs['target']
                target()
            mock_thread.return_value.start.side_effect = start_side_effect

            self.view._auto_save_check()
            
            # 失敗時は True ではなく False で after が呼ばれる
            self.root.after.assert_any_call(0, self.view._on_auto_save_complete, False, current_rev)
            
            # 完了処理(失敗)を実行
            self.view.status_bar.config.reset_mock()
            self.view._on_auto_save_complete(False, current_rev)
            
            # 通知（Saved automatically）が呼ばれていないこと
            for call in self.view.status_bar.config.call_args_list:
                if call.kwargs.get('text') == "Saved automatically":
                    self.fail("Status message shown on failure")

    def test_auto_save_does_not_clear_modified_if_revision_mismatch(self):
        """保存中に新たな編集が発生した場合、変更フラグがクリアされないこと"""
        self.view.model.is_modified = True
        self.view.model.modification_count = 2 # 現在のリビジョンは 2
        
        # リビジョン 1 の保存が完了したとする
        self.view._on_auto_save_complete(True, 1)
        
        # リビジョンが一致しない（＝保存開始後に別の編集があった）ため、is_modified は True のまま
        # Note: MindMapModel.is_modified の実装に依存
        self.assertTrue(self.view.model.is_modified)

    def test_auto_save_clears_modified_if_revision_matches(self):
        """保存中に新たな編集が発生しなかった場合、変更フラグがクリアされること"""
        self.view.model.is_modified = True
        self.view.model.modification_count = 1
        
        self.view._on_auto_save_complete(True, 1)
        
        self.assertFalse(self.view.model.is_modified)

    def test_auto_save_check_does_not_call_on_save_when_not_modified(self):
        """変更がない場合は保存が実行されないこと"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = False
        
        self.view._auto_save_check()
        
        self.view.persistence._perform_write_to_file.assert_not_called()

    def test_auto_save_check_does_not_call_on_save_when_no_path(self):
        """ファイルパスがない（一度も保存されていない）場合は保存が実行されないこと"""
        self.view.persistence.current_file_path = None
        self.view.model.is_modified = True
        
        self.view._auto_save_check()
        
        self.view.persistence._perform_write_to_file.assert_not_called()

    def test_auto_save_check_does_not_call_on_save_when_editing(self):
        """ノード編集中は保存が実行されないこと"""
        self.view.persistence.current_file_path = "test.json"
        self.view.model.is_modified = True
        self.view.editor.is_editing.return_value = True
        
        self.view._auto_save_check()
        
        self.view.persistence._perform_write_to_file.assert_not_called()

    def test_after_is_called_again(self):
        """_auto_save_check の最後で再び after が呼ばれ、ループが継続すること"""
        self.root.after.reset_mock()
        self.view._auto_save_check()
        # 10000ms 後に再び自分を呼ぶように設定されているか
        self.root.after.assert_any_call(10000, self.view._auto_save_check)

if __name__ == '__main__':
    unittest.main()
