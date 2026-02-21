import tkinter as tk
from .models import Node
from .graphics import GraphicsEngine

class NodeEditor:
    """ノードのテキスト編集（インライン編集）を管理するクラス"""
    def __init__(self, canvas: tk.Canvas, root: tk.Tk, graphics: GraphicsEngine, on_finish, model):
        self.canvas = canvas
        self.root = root
        self.graphics = graphics
        self.on_finish = on_finish # 完了時に呼び出すコールバック (renderなど)
        self.model = model
        self.editing_entry = None
        self.window_id = None
        self.finishing = False

    def is_editing(self):
        return self.editing_entry is not None

    def start_edit(self, node: Node):
        if self.editing_entry:
            return
            
        # Textウィジェットの作成 (Entryのかわりに)
        # 高さは行数に応じて動的に調整するが、最初は1か2程度
        lines = node.text.count("\n") + 1
        height = min(10, max(1, lines))
        
        entry = tk.Text(self.canvas, font=self.graphics.font, 
                         bg="white", fg="black", insertbackground="black",
                         relief="flat", highlightbackground="#0078d7", highlightthickness=2,
                         padx=5, pady=5)
        entry.insert("1.0", node.text)
        entry.tag_add("sel", "1.0", "end")
        
        # テキストの幅に合わせて調整
        edit_width = max(150, node.width + 30)
        
        self.window_id = self.canvas.create_window(
            node.x, node.y, window=entry, width=edit_width, height=height*25 + 20, anchor="center"
        )
        self.editing_entry = entry
        self.finishing = False
        
        def set_focus():
            if self.editing_entry == entry:
                entry.focus_set()
                entry.see("1.0")
        self.root.after(100, set_focus)
        
        # Enterで完了、Ctrl+Enterで改行
        entry.bind("<Return>", lambda e: self.finish_edit(node))
        def insert_newline(e):
            entry.insert("insert", "\n")
            return "break"
        entry.bind("<Control-Return>", insert_newline)
        entry.bind("<Escape>", lambda e: self.cancel_edit())
        entry.bind("<FocusOut>", lambda e: self.finish_edit(node))
        entry.bind("<Tab>", lambda e: "break")

    def finish_edit(self, node: Node):
        if self.finishing or not self.editing_entry:
            return "break"
        self.finishing = True
        
        # Textウィジェットからテキスト取得 (最後の改行を除く)
        new_text = self.editing_entry.get("1.0", "end-1c")
        if new_text is not None and new_text != node.text:
            node.text = new_text
            self.model.is_modified = True
            
        self._cleanup()
        self.on_finish()
        return "break"

    def cancel_edit(self):
        if self.finishing or not self.editing_entry:
            return "break"
        self.finishing = True
        
        self._cleanup()
        self.on_finish()
        return "break"

    def _cleanup(self):
        if self.editing_entry:
            self.editing_entry = None
        if self.window_id:
            self.canvas.delete(self.window_id)
            self.window_id = None
        self.canvas.focus_set()
