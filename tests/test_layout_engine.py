import unittest
from unittest.mock import MagicMock
from py_mind_memo.layout import LayoutEngine
from py_mind_memo.models import MindMapModel

class TestLayoutEngine(unittest.TestCase):
    def setUp(self):
        self.engine = LayoutEngine()
        self.model = MindMapModel("Root")
        self.graphics = MagicMock()
        # デフォルトのテキストサイズ
        self.graphics.get_text_size.return_value = (100, 40)

    def test_calculate_subtree_height_leaf(self):
        root = self.model.root
        height = self.engine.calculate_subtree_height(root, self.graphics)
        self.assertEqual(height, 40)
        self.assertEqual(root.subtree_height, 40)

    def test_calculate_subtree_height_with_children(self):
        root = self.model.root
        c1 = self.model.add_node(root, "C1")
        c2 = self.model.add_node(root, "C2")
        
        # subtree_height = child1_h + child2_h + spacing = 40 + 40 + 30 = 110
        # ※ root 自身の高さ 40 よりも大きいため 110 が採用される
        height = self.engine.calculate_subtree_height(root, self.graphics)
        self.assertEqual(height, 110)
        self.assertEqual(root.subtree_height, 110)
        self.assertEqual(c1.subtree_height, 40)

    def test_apply_layout_basic(self):
        root = self.model.root
        c1 = self.model.add_node(root, "C1") # right
        
        self.engine.apply_layout(self.model, self.graphics, 0, 0)
        
        self.assertEqual(root.x, 0)
        self.assertEqual(root.y, 0)
        
        # c1 は右側に配置されるはず
        self.assertGreater(c1.x, 0)
        self.assertEqual(c1.y, 0) # 中心に1つだけなので y=0
        self.assertEqual(c1.direction, 'right')

    def test_collapsed_node_height(self):
        root = self.model.root
        c1 = self.model.add_node(root, "C1")
        c1.add_child("G1")
        
        c1.collapsed = True
        height = self.engine.calculate_subtree_height(c1, self.graphics)
        self.assertEqual(height, 40) # 子ノードがあっても折りたたまれていれば自身の高さのみ

if __name__ == '__main__':
    unittest.main()
