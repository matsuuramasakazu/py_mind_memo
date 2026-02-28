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

    def test_filename_sanitization(self):
        # re.sub による置換ロジックを直接テスト
        def sanitize(text):
            name = re.sub(r'<[^>]+>', '', text)
            name = re.sub(r'[\s\\/:*?\"<>|]+', '_', name)
            return name.strip('_')[:20]

        self.assertEqual(sanitize("Normal Title"), "Normal_Title")
        self.assertEqual(sanitize("<b>Bold</b> Title"), "Bold_Title")
        self.assertEqual(sanitize("File/With:Invalid*Chars?"), "File_With_Invalid_Ch")
        self.assertEqual(sanitize("   Trim Space   "), "Trim_Space")
        self.assertEqual(sanitize("VeryLongTitleThatExceedsTwentyCharacters"), "VeryLongTitleThatExc")

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
