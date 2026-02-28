import unittest
from unittest.mock import MagicMock, patch
from py_mind_memo.graphics import GraphicsEngine

class TestGraphicsLogic(unittest.TestCase):
    def setUp(self):
        self.canvas = MagicMock()
        self.engine = GraphicsEngine(self.canvas)

    def test_parse_markup(self):
        # シンプルなテキスト (デフォルト色は COLOR_TEXT = "#333333")
        self.assertEqual(self.engine._parse_markup("Hello"), [("Hello", "normal", False, "#333333")])
        
        # ボールドとイタリック
        text = "<b>Bold</b> and <i>Italic</i>"
        expected = [
            ("Bold", "bold", False, "#333333"),
            (" and ", "normal", False, "#333333"),
            ("Italic", "italic", False, "#333333")
        ]
        self.assertEqual(self.engine._parse_markup(text), expected)
        
        # カラータグ
        text = "<c:#ff0000>Red</c>"
        expected = [("Red", "normal", False, "#ff0000")]
        self.assertEqual(self.engine._parse_markup(text), expected)

    def test_calc_rect_edge_point(self):
        # 中心(0,0), 半幅10, 半高5
        # 右方向 (1,0)
        self.assertEqual(self.engine._calc_rect_edge_point(0, 0, 10, 5, 1, 0), (10, 0))
        # 上方向 (0,-1)
        self.assertEqual(self.engine._calc_rect_edge_point(0, 0, 10, 5, 0, -1), (0, -5))
        # 斜め方向 (1,1) -> (5,5) か (10,10) か？ 
        # t = min(10/1, 5/1) = 5
        self.assertEqual(self.engine._calc_rect_edge_point(0, 0, 10, 5, 1, 1), (5, 5))

    @patch("tkinter.font.Font")
    def test_wrap_rich_text(self, mock_font):
        # measure メソッドが一定の値を返すように設定
        # 1文字 10px と仮定
        mock_font_instance = mock_font.return_value
        mock_font_instance.measure.side_effect = lambda char: 10
        
        # max_width 50px なので 5文字で折り返されるはず
        text = "1234567890"
        base_font = ("Arial", 10)
        wrapped = self.engine._wrap_rich_text(text, base_font, 50)
        
        self.assertEqual(len(wrapped), 2) # "12345", "67890" の2行
        self.assertEqual("".join(s[0] for s in wrapped[0]), "12345")
        self.assertEqual("".join(s[0] for s in wrapped[1]), "67890")

if __name__ == '__main__':
    unittest.main()
