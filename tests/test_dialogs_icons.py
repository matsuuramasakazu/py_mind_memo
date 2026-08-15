import os
import glob
import unittest
import tkinter as tk
from py_mind_memo.constants import ICON_SIZE
from py_mind_memo.dialogs import IconPickerDialog

class TestDialogsIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            cls.root.destroy()

    def test_icons_exist_and_count(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icons_dir = os.path.join(base_dir, "py_mind_memo", "assets", "icons")
        self.assertTrue(os.path.exists(icons_dir), f"Icons directory not found: {icons_dir}")
        
        icon_files = glob.glob(os.path.join(icons_dir, "*.png"))
        self.assertGreaterEqual(len(icon_files), 30, f"Expected at least 30 icons, found {len(icon_files)}")

    def test_all_icons_are_valid_20x20(self):
        if not self.root:
            self.skipTest("Tkinter display not available")
            
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icons_dir = os.path.join(base_dir, "py_mind_memo", "assets", "icons")
        icon_files = sorted(glob.glob(os.path.join(icons_dir, "*.png")))
        
        for file_path in icon_files:
            with self.subTest(file=os.path.basename(file_path)):
                photo = tk.PhotoImage(file=file_path)
                self.assertEqual(photo.width(), ICON_SIZE, f"{file_path} width is not {ICON_SIZE}")
                self.assertEqual(photo.height(), ICON_SIZE, f"{file_path} height is not {ICON_SIZE}")

    def test_icon_picker_dialog_loads_icons(self):
        if not self.root:
            self.skipTest("Tkinter display not available")
            
        dialog = IconPickerDialog(self.root)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icons_dir = os.path.join(base_dir, "py_mind_memo", "assets", "icons")
        icon_files = glob.glob(os.path.join(icons_dir, "*.png"))
        
        self.assertEqual(len(dialog.photos), len(icon_files))
        dialog.destroy()

if __name__ == '__main__':
    unittest.main()
