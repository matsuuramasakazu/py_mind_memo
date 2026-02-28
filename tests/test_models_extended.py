import unittest
from py_mind_memo.models import MindMapModel, Node

class TestModelsExtended(unittest.TestCase):
    def setUp(self):
        self.model = MindMapModel("Root")

    def test_node_add_child(self):
        root = self.model.root
        child1 = root.add_child("Child 1", direction="right")
        self.assertEqual(len(root.children), 1)
        self.assertEqual(child1.text, "Child 1")
        self.assertEqual(child1.parent, root)
        self.assertEqual(child1.direction, "right")

        # 親の方向を継承
        grandchild = child1.add_child("Grandchild")
        self.assertEqual(grandchild.direction, "right")

    def test_node_remove_child(self):
        root = self.model.root
        child = root.add_child("Child")
        root.remove_child(child)
        self.assertEqual(len(root.children), 0)

    def test_node_move_to(self):
        root = self.model.root
        parent1 = self.model.add_node(root, "Parent 1")
        parent2 = self.model.add_node(root, "Parent 2")
        child = parent1.add_child("Child")
        
        child.move_to(parent2)
        self.assertNotIn(child, parent1.children)
        self.assertIn(child, parent2.children)
        self.assertEqual(child.parent, parent2)
        self.assertEqual(child.direction, parent2.direction)

    def test_balanced_direction(self):
        # 左右バランスのテスト
        self.model.add_node(self.model.root, "Node 1") # right
        self.model.add_node(self.model.root, "Node 2") # left
        self.model.add_node(self.model.root, "Node 3") # right
        
        directions = [c.direction for c in self.model.root.children]
        self.assertEqual(directions, ["right", "left", "right"])
        
        new_dir = self.model.get_balanced_direction()
        self.assertEqual(new_dir, "left")

    def test_is_descendant_of(self):
        root = self.model.root
        child = root.add_child("Child")
        grandchild = child.add_child("Grandchild")
        
        self.assertTrue(grandchild.is_descendant_of(root))
        self.assertTrue(grandchild.is_descendant_of(child))
        self.assertTrue(child.is_descendant_of(root))
        self.assertFalse(root.is_descendant_of(child))
        self.assertTrue(root.is_descendant_of(root))

    def test_serialization_full_tree(self):
        root = self.model.root
        child = self.model.add_node(root, "Child")
        child.image_data = "dummy_base64"
        child.collapsed = True
        
        data = self.model.save()
        
        new_model = MindMapModel()
        new_model.load(data)
        
        self.assertEqual(new_model.root.text, "Root")
        self.assertEqual(len(new_model.root.children), 1)
        restored_child = new_model.root.children[0]
        self.assertEqual(restored_child.text, "Child")
        self.assertEqual(restored_child.image_data, "dummy_base64")
        self.assertTrue(restored_child.collapsed)

if __name__ == '__main__':
    unittest.main()
