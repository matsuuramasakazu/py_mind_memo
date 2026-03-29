import os
import tkinter as tk
from tkinter import ttk
from .constants import ICON_SIZE

class IconPickerDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Select Icon")
        self.result_path = None
        self.result_photo = None
        
        self.transient(parent)
        self.grab_set()
        
        self.photos = {}  # GC防止
        self._build_ui()
        
    def _build_ui(self):
        main_frame = tk.Frame(self, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # py_mind_memo/__file__ のあるディレクトリを基準にして assets/icons を探索
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(base_dir, "assets", "icons")
        
        if not os.path.exists(icons_dir):
            tk.Label(main_frame, text=f"アイコンディレクトリが見つかりません: {icons_dir}").pack()
            return

        row = 0
        col = 0
        max_cols = 5
        
        has_icons = False
        for file in os.listdir(icons_dir):
            if file.lower().endswith(".png"):
                file_path = os.path.join(icons_dir, file)
                try:
                    photo = tk.PhotoImage(file=file_path)
                    # ICON_SIZE 以下の画像のみを表示対象とする
                    if photo.width() <= ICON_SIZE and photo.height() <= ICON_SIZE:
                        has_icons = True
                        self.photos[file_path] = photo
                        btn = tk.Button(main_frame, image=photo, command=lambda p=file_path, ph=photo: self.on_select(p, ph), cursor="hand2")
                        btn.grid(row=row, column=col, padx=4, pady=4)
                        col += 1
                        if col >= max_cols:
                            col = 0
                            row += 1
                except tk.TclError:
                    pass
                    
        if not has_icons:
            tk.Label(main_frame, text="利用可能なアイコンがありません。").pack()
            
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)
        
        clear_btn = tk.Button(btn_frame, text="Clear Icon", command=lambda: self.on_select("CLEAR", None), width=10)
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        close_btn = tk.Button(btn_frame, text="Cancel", command=self.destroy, width=10)
        close_btn.pack(side=tk.RIGHT, padx=10)

    def on_select(self, path, photo):
        self.result_path = path
        self.result_photo = photo
        self.destroy()

    def show(self):
        # 画面中央に配置
        self.update_idletasks()
        try:
            parent = self.master
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_reqheight()) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self.wait_window(self)
        return self.result_path, self.result_photo
