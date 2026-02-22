import tkinter as tk
from tkinter import filedialog
import base64
import io
from .models import Node
from .graphics import GraphicsEngine
from .image_utils import calculate_subsample, file_to_base64

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
        self.inserting_image = False
        self.current_images = [] # GC防止用の参照保持

    def is_editing(self):
        return self.editing_entry is not None

    def start_edit(self, node: Node):
        if self.editing_entry:
            return
            
        # Textウィジェットの作成 (Entryのかわりに)
        lines = node.text.count("\n") + 1
        height = min(10, max(1, lines))
        
        # 画像がある場合は高さを少し多めに確保
        if node.image_data:
            height += 4

        entry = tk.Text(self.canvas, font=self.graphics.font, 
                         bg="white", fg="black", insertbackground="black",
                         relief="flat", highlightbackground="#0078d7", highlightthickness=2,
                         padx=5, pady=5)
        
        # 既存の画像があれば挿入
        if node.image_data:
            try:
                img_data = base64.b64decode(node.image_data)
                photo = tk.PhotoImage(data=img_data)
                self.current_images.append(photo)
                entry.image_create("1.0", image=photo)
                entry.insert("end", "\n")
            except Exception:
                pass

        entry.insert("end", node.text)
        entry.tag_add("sel", "1.0", "end")
        
        # テキストの幅に合わせて調整
        edit_width = max(200, node.width + 50)
        
        self.window_id = self.canvas.create_window(
            node.x, node.y, window=entry, width=edit_width, height=height*25 + 100, anchor="center"
        )
        self.editing_entry = entry
        self.finishing = False
        
        def set_focus():
            if self.editing_entry == entry:
                entry.focus_set()
                # 最初から全選択状態にするための調整
                entry.tag_add("sel", "1.0", "end")
        self.root.after(100, set_focus)
        
        # バインド設定
        entry.bind("<Return>", lambda e: self.finish_edit(node))
        def insert_newline(e):
            entry.insert("insert", "\n")
            return "break"
        entry.bind("<Control-Return>", insert_newline)
        entry.bind("<Control-i>", lambda e: self.insert_image(node))
        entry.bind("<Escape>", lambda e: self.cancel_edit())
        
        def on_focus_out(e):
            if self.inserting_image:
                return
            self.finish_edit(node)
            
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Tab>", lambda e: "break")

    def insert_image(self, node: Node):
        """画像ファイルを選択してエディタに挿入する"""
        self.inserting_image = True
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("PNG files", "*.png")]
            )
        finally:
            self.inserting_image = False
            
        if self.editing_entry:
            self.editing_entry.focus_set()

        if not file_path or not self.editing_entry:
            return "break"

        try:
            # PhotoImageで一度読み込んでサイズを確認
            temp_photo = tk.PhotoImage(file=file_path)
            width = temp_photo.width()
            height = temp_photo.height()
            
            # subsampleによる縮小率の計算
            sample = calculate_subsample(width, height, 200, 200)
            
            if sample > 1:
                photo = temp_photo.subsample(sample, sample)
            else:
                photo = temp_photo
            
            self.current_images.append(photo)
            # カーソル位置に画像を挿入
            self.editing_entry.image_create("insert", image=photo)
            
            # 実装をシンプルにするため、挿入した画像のデータをその場でNodeに一時保存（またはフラグ立て）
            # ここではBase64化して保持
            raw_data = photo.tk.call(photo.name, 'data', '-format', 'png')
            node.image_data = base64.b64encode(raw_data).decode('utf-8')
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to insert image: {e}")
            
        return "break"

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
        self.current_images.clear()
        self.canvas.focus_set()
