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

    @patch("py_mind_memo.persistence.open", new_callable=mock_open)
    def test_write_to_file(self, mocked_open):
        self.model.add_node(self.model.root, "Child")
        self.model.is_modified = True
        
        test_path = "test.json"
        self.handler._write_to_file(test_path)
        
        mocked_open.assert_called_once_with(test_path, "w", encoding="utf-8")
        self.assertEqual(self.handler.current_file_path, test_path)
        self.assertFalse(self.model.is_modified)
            
        # 書き込まれた内容の検証
        handle = mocked_open()
        written_data = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written_data)
        self.assertEqual(data["root"]["text"], "Root Topic")

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
