import unittest
import json
from py_mind_memo.models import MindMapModel, Node, Reference

class TestReferenceModel(unittest.TestCase):
    def test_reference_serialization_and_deserialization(self):
        # Setup model with references
        model = MindMapModel("Root")
        node1 = model.add_node(model.root, "Node 1")
        node2 = model.add_node(model.root, "Node 2")
        
        # Create a reference from node1 to node2
        ref = Reference(node1.id, node2.id)
        ref.cp1_x, ref.cp1_y = 100.0, 200.0
        ref.cp2_x, ref.cp2_y = 300.0, 400.0
        model.references.append(ref)
        
        # Serialize to dict
        data = model.save()
        
        self.assertIn("root", data)
        self.assertIn("references", data)
        self.assertEqual(len(data["references"]), 1)
        
        ref_data = data["references"][0]
        self.assertEqual(ref_data["source_id"], node1.id)
        self.assertEqual(ref_data["target_id"], node2.id)
        self.assertEqual(ref_data["cp1_x"], 100.0)
        self.assertEqual(ref_data["cp1_y"], 200.0)
        
        # Deserialize from dict
        new_model = MindMapModel()
        new_model.load(data)
        
        self.assertEqual(len(new_model.references), 1)
        restored_ref = new_model.references[0]
        self.assertEqual(restored_ref.source_id, node1.id)
        self.assertEqual(restored_ref.target_id, node2.id)
        self.assertEqual(restored_ref.cp1_x, 100.0)
        self.assertEqual(restored_ref.cp2_y, 400.0)
        
        # Test backward compatibility (loading old format JSON)
        old_data = {"text": "Old Root", "color": "#000000"}  # Simplified old node dict structure
        compat_model = MindMapModel()
        compat_model.load(old_data)
        
        self.assertEqual(compat_model.root.text, "Old Root")
        self.assertEqual(len(compat_model.references), 0)

if __name__ == '__main__':
    unittest.main()
