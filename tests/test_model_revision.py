import unittest
from py_mind_memo.models import MindMapModel

class TestModelRevision(unittest.TestCase):
    def test_modification_count_increments_on_modified_true(self):
        """is_modified = True をセットするたびに modification_count が増えること"""
        model = MindMapModel()
        self.assertEqual(model.modification_count, 0)
        
        model.is_modified = True
        self.assertEqual(model.modification_count, 1)
        
        model.is_modified = True
        self.assertEqual(model.modification_count, 2)

    def test_modification_count_does_not_increment_on_modified_false(self):
        """is_modified = False では modification_count が増えないこと"""
        model = MindMapModel()
        model.is_modified = True
        count = model.modification_count
        
        model.is_modified = False
        self.assertEqual(model.modification_count, count)

    def test_save_with_revision(self):
        """save_with_revision が正しいデータとリビジョンを返すこと"""
        model = MindMapModel()
        model.is_modified = True # revision 1
        model.is_modified = True # revision 2
        
        data, revision = model.save_with_revision()
        self.assertEqual(revision, 2)
        self.assertIn("root", data)
        self.assertIn("references", data)

if __name__ == '__main__':
    unittest.main()
