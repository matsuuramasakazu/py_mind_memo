import unittest
from unittest.mock import patch, mock_open
import base64
from py_mind_memo.image_utils import calculate_subsample, file_to_base64

class TestImageUtils(unittest.TestCase):
    def test_calculate_subsample(self):
        # 境界値テスト: 上限以下の場合は 1
        self.assertEqual(calculate_subsample(100, 100, 200, 200), 1)
        self.assertEqual(calculate_subsample(200, 200, 200, 200), 1)
        
        # 片方が上限を超える場合
        self.assertEqual(calculate_subsample(400, 200, 200, 200), 2)
        self.assertEqual(calculate_subsample(200, 400, 200, 200), 2)
        
        # 両方が上限を超える場合
        self.assertEqual(calculate_subsample(600, 800, 200, 200), 4) # max(600/200, 800/200) = 4
        
        # 端数の切り上げ
        self.assertEqual(calculate_subsample(201, 200, 200, 200), 2)

    @patch("os.path.exists", return_value=True)
    def test_file_to_base64(self, mock_exists):
        dummy_content = b"fake image data"
        expected_base64 = base64.b64encode(dummy_content).decode('utf-8')
        
        with patch("builtins.open", mock_open(read_data=dummy_content)):
            result = file_to_base64("dummy.png")
            self.assertEqual(result, expected_base64)

if __name__ == '__main__':
    unittest.main()
