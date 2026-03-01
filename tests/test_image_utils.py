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
        
    def test_calculate_subsample_validation(self):
        # max_width/max_height が 0 以下の場合、ValueError が発生することを確認
        with self.assertRaisesRegex(ValueError, "max_width and max_height must be positive"):
            calculate_subsample(100, 100, 0, 100)
        with self.assertRaisesRegex(ValueError, "max_width and max_height must be positive"):
            calculate_subsample(100, 100, 100, -5)

    def test_file_to_base64_not_found(self):
        # ファイルが存在しない場合、FileNotFoundError が発生することを確認
        with self.assertRaises(FileNotFoundError):
            file_to_base64("non_existent.png")

    def test_file_to_base64(self):
        dummy_content = b"fake image data"
        expected_base64 = base64.b64encode(dummy_content).decode('utf-8')
        
        with patch("builtins.open", mock_open(read_data=dummy_content)):
            result = file_to_base64("dummy.png")
            self.assertEqual(result, expected_base64)

if __name__ == '__main__':
    unittest.main()
