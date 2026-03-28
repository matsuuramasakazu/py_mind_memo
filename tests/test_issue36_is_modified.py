import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.models import MindMapModel, Node
from py_mind_memo.editor import NodeEditor
from py_mind_memo.view import MindMapView

class TestIssue36IsModified(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.canvas = tk.Canvas(self.root)
        self.model = MindMapModel("Root")
        self.node = self.model.root
        
    def tearDown(self):
        self.root.destroy()

    @patch('py_mind_memo.editor.ImageHandler.pick_and_load_image')
    @patch('py_mind_memo.editor.ImageHandler.process_image')
    @patch('py_mind_memo.editor.ImageHandler.base64_from_photo')
    def test_insert_image_sets_is_modified(self, mock_b64, mock_process, mock_pick):
        # Setup mocks
        mock_pick.return_value = "dummy.png"
        mock_process.return_value = MagicMock(spec=tk.PhotoImage)
        mock_b64.return_value = "dummy_base64"
        
        # Initialize NodeEditor
        editor = NodeEditor(self.canvas, self.root, MagicMock(), lambda: None, self.model)
        
        # Start editing (needed to set editing_entry)
        editor.start_edit(self.node)
        # Mock image_create to avoid TclError with Mock PhotoImage
        editor.editing_entry.image_create = MagicMock()
        
        # Initial state
        self.model.is_modified = False
        
        # Execute insert_image
        editor.insert_image(self.node)
        
        # Verification
        self.assertTrue(self.model.is_modified, "is_modified should be True after inserting image")

    def test_collapse_click_sets_is_modified(self):
        # Initialize MindMapView (with mocks to avoid full GUI setup issues)
        with patch('py_mind_memo.view.GraphicsEngine'), \
             patch('py_mind_memo.view.LayoutEngine'), \
             patch('py_mind_memo.view.NodeEditor'), \
             patch('py_mind_memo.view.DragDropHandler'), \
             patch('py_mind_memo.view.KeyboardNavigator'), \
             patch('py_mind_memo.view.PersistenceHandler'), \
             patch('py_mind_memo.view.MindMapView._create_menu'), \
             patch('py_mind_memo.view.MindMapView.render'):
            
            view = MindMapView(self.root)
            view.model = self.model
            
            # Create a node and tag it as collapse_icon
            node = self.model.add_node(self.model.root, "Child")
            node_id = node.id
            
            # Mock canvas.find_overlapping and canvas.gettags
            view.canvas.find_overlapping = MagicMock(return_value=[123])
            view.canvas.gettags = MagicMock(return_value=("collapse_icon", node_id))
            
            # Initial state
            self.model.is_modified = False
            
            # Execute _handle_node_collapse_click
            # Use real coordinates but find_overlapping is mocked
            view._handle_node_collapse_click(10, 10)
            
            # Verification
            self.assertTrue(self.model.is_modified, "is_modified should be True after toggling collapse")

if __name__ == '__main__':
    unittest.main()
