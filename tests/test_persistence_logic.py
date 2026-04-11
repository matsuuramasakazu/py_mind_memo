import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import re
from py_mind_memo.persistence import PersistenceHandler
from py_mind_memo.models import MindMapModel

class TestPersistenceLogic(unittest.TestCase):
    def setUp(self):
        self.model = MindMapModel("Root Topic")
        self.render_callback = MagicMock()
        self.handler = PersistenceHandler(self.model, self.render_callback)

    @patch("tkinter.filedialog.asksaveasfilename")
    def test_on_save_as_sanitization(self, mock_ask):
        # 正常なタイトル
        mock_ask.return_value = "" # 保存をキャンセル
        self.model.root.text = "Normal Title"
        self.handler.on_save_as()
        self.assertEqual(mock_ask.call_args.kwargs['initialfile'], "Normal_Title")
        
        # タグと特殊文字を含むタイトル
        mock_ask.reset_mock()
        self.model.root.text = "<b>Bold</b>/File:Name"
        self.handler.on_save_as()
        self.assertEqual(mock_ask.call_args.kwargs['initialfile'], "Bold_File_Name")

        # 長いタイトル
        mock_ask.reset_mock()
        self.model.root.text = "VeryLongTitleThatExceedsTwentyCharacters"
        self.handler.on_save_as()
        self.assertEqual(mock_ask.call_args.kwargs['initialfile'], "VeryLongTitleThatExc")

    def test_write_to_file(self):
        self.model.add_node(self.model.root, "Child")
        self.model.is_modified = True
        
        test_path = "test.json"
        # _perform_write_to_file をモックして、実ファイルI/Oをスキップする
        with patch.object(self.handler, "_perform_write_to_file") as mock_write:
            result = self.handler._write_to_file(test_path)
        
        mock_write.assert_called_once()
        # 第1引数がtest_path、第2引数がdictであることを確認
        args = mock_write.call_args.args
        self.assertEqual(args[0], test_path)
        self.assertIsInstance(args[1], dict)
        self.assertEqual(self.handler.current_file_path, test_path)
        self.assertFalse(self.model.is_modified)
        self.assertTrue(result)


    @patch("py_mind_memo.persistence.open", new_callable=mock_open, read_data='{"root": {"text": "Loaded"}}')
    def test_on_open_logic(self, mocked_open):
        # filedialog をモック
        with patch("tkinter.filedialog.askopenfilename", return_value="open.json"):
            self.handler.on_open()
            
            self.assertEqual(self.model.root.text, "Loaded")
            self.assertEqual(self.handler.current_file_path, "open.json")
            self.render_callback.assert_called_once()

if __name__ == '__main__':
    unittest.main()
