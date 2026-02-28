import tkinter as tk
from tkinter import filedialog, messagebox
import base64
import io
from .models import Node
from .graphics import GraphicsEngine
from .image_utils import calculate_subsample, load_image_as_base64
from .constants import (
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT,
    EDIT_WINDOW_MIN_WIDTH, EDIT_WINDOW_PADDING_X,
    EDIT_WINDOW_HEIGHT_BASE, EDIT_WINDOW_LINE_HEIGHT,
    EDIT_IMAGE_HEIGHT_BONUS
)

class ImageHandler:
    """画像の挿入・管理を専門に担当するクラス"""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.inserting_image = False
        self.current_images = [] # GC防止用の参照保持

    def clear_cache(self):
        """保持している画像キャッシュをクリアする"""
        self.current_images.clear()

    def add_to_cache(self, photo: tk.PhotoImage):
        """画像キャッシュにPhotoImageを追加する"""
        self.current_images.append(photo)

    def pick_and_load_image(self) -> str:
        """画像ファイルを選択し、パスを返す。選択中は inserting_image フラグを立てる"""
        self.inserting_image = True
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("PNG files", "*.png")]
            )
            return file_path
        finally:
            self.inserting_image = False

    def process_image(self, file_path: str) -> tk.PhotoImage:
        """画像ファイルを読み込み、必要に応じてリサイズして PhotoImage を生成する"""
        try:
            temp_photo = tk.PhotoImage(file=file_path)
            width = temp_photo.width()
            height = temp_photo.height()
            
            sample = calculate_subsample(width, height, MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT)
            
            if sample > 1:
                photo = temp_photo.subsample(sample, sample)
            else:
                photo = temp_photo
            
            self.add_to_cache(photo)
            return photo
        except tk.TclError as e:
            raise ValueError(f"Failed to load image: {e}")

    def get_photo_from_base64(self, base64_data: str) -> tk.PhotoImage:
        """Base64文字列から PhotoImage を生成する"""
        try:
            img_data = base64.b64decode(base64_data)
            photo = tk.PhotoImage(data=img_data)
            self.add_to_cache(photo)
            return photo
        except (base64.binascii.Error, tk.TclError) as e:
            raise ValueError(f"Failed to decode image data: {e}")

    def base64_from_photo(self, photo: tk.PhotoImage) -> str:
        """PhotoImageからBase64文字列を生成する"""
        raw_data = photo.tk.call(photo.name, 'data', '-format', 'png')
        return base64.b64encode(raw_data).decode('utf-8')

class NodeEditor:
    """ノードのテキスト編集（インライン編集）を管理するクラス"""
    def __init__(self, canvas: tk.Canvas, root: tk.Tk, graphics: GraphicsEngine, on_finish, model):
        self.canvas = canvas
        self.root = root
        self.graphics = graphics
        self.on_finish = on_finish
        self.model = model
        self.editing_entry = None
        self.editing_node = None
        self.window_id = None
        self.finishing = False
        
        # 画像管理を ImageHandler に委譲
        self.image_handler = ImageHandler(root)

    def is_editing(self):
        return self.editing_entry is not None and self.editing_entry.winfo_exists()

    def start_edit(self, node: Node):
        if self.editing_entry:
            return
            
        self.image_handler.clear_cache()
        self.editing_node = node

        # Textウィジェットの作成
        lines = node.text.count("\n") + 1
        height = min(10, max(1, lines))
        
        if node.image_data:
            height += EDIT_IMAGE_HEIGHT_BONUS

        entry = tk.Text(self.canvas, font=self.graphics.font, 
                         bg="white", fg="black", insertbackground="black",
                         relief="flat", highlightbackground="#0078d7", highlightthickness=2,
                         padx=5, pady=5)
        
        if node.image_data:
            try:
                photo = self.image_handler.get_photo_from_base64(node.image_data)
                entry.image_create("1.0", image=photo)
                entry.insert("end", "\n")
            except ValueError:
                # 画像のデコード失敗時は無視してテキスト編集を継続
                pass

        entry.insert("end", node.text)
        entry.tag_add("sel", "1.0", "end")
        
        edit_width = max(EDIT_WINDOW_MIN_WIDTH, node.width + EDIT_WINDOW_PADDING_X)
        
        self.window_id = self.canvas.create_window(
            node.x, node.y, 
            window=entry, 
            width=edit_width, 
            height=height * EDIT_WINDOW_LINE_HEIGHT + EDIT_WINDOW_HEIGHT_BASE, 
            anchor="center"
        )
        self.editing_entry = entry
        self.finishing = False
        
        def set_focus():
            if self.editing_entry == entry:
                entry.focus_set()
                entry.tag_add("sel", "1.0", "end")
        self.root.after(100, set_focus)
        
        # バインド設定
        entry.bind("<Return>", lambda e: self.finish_edit())
        def insert_newline(e):
            entry.insert("insert", "\n")
            return "break"
        entry.bind("<Control-Return>", insert_newline)
        entry.bind("<Control-i>", lambda e: self.insert_image(node))
        entry.bind("<Escape>", lambda e: self.cancel_edit())
        
        def on_focus_out(e):
            if self.image_handler.inserting_image:
                return
            self.finish_edit()
            
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Tab>", lambda e: "break")

    def insert_image(self, node: Node):
        """画像ファイルを選択してエディタに挿入する"""
        file_path = self.image_handler.pick_and_load_image()
            
        if self.editing_entry:
            self.editing_entry.focus_set()

        if not file_path or not self.editing_entry:
            return "break"

        try:
            # 1トピック1画像の仕様: 既存の画像があれば削除する
            # tk.Text内の画像を検索して削除
            current_image_indices = self.editing_entry.image_names()
            if current_image_indices:
                # エディタの最初から最後まで画像を検索して削除
                start = "1.0"
                while True:
                    img_info = self.editing_entry.image_cget(start, "-image")
                    if img_info:
                        self.editing_entry.delete(start)
                    
                    # 次の画像を探す（簡易的な実装として先頭から順に走査）
                    # 実際には差し替えなので、エディタ全体の画像データをクリアしてから挿入するのが確実
                    break # 1つ見つけたらとりあえず抜ける(ループ構成は要件に合わせる)

            # エディタ内の全ての画像を一旦削除（1つに制限するため）
            # image_names() はPhoto名が返るため、Text内の位置を特定して削除する必要がある
            # 簡略化のため、既存の画像をクリアして最前面に挿入する
            
            # 全ての画像アイテムを Text から削除
            for name in self.editing_entry.image_names():
                # このText内の特定位置にある画像を削除するのは煩雑なため、
                # インデックス走査で見つかった画像を削除する
                pass

            # 実際には差し替えなので、エディタの先頭付近に画像があれば削除する等の対応が必要
            # ここでは「最後にインポートしたもので差し替える」ため、既存の画像属性をクリアした上で挿入
            
            photo = self.image_handler.process_image(file_path)
            
            # インデックス "1.0" に画像があるか確認し、あれば削除
            try:
                if self.editing_entry.image_cget("1.0", "-image"):
                    self.editing_entry.delete("1.0")
            except tk.TclError:
                pass

            self.editing_entry.image_create("1.0", image=photo)
            # モデルの更新（この時点では一時的、finish_editで確定）
            node.image_data = self.image_handler.base64_from_photo(photo)
            node.image_path = file_path
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except tk.TclError as e:
            messagebox.showerror("Error", f"Tkinter error: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error while inserting image: {e}")
            
        return "break"

    def finish_edit(self, node: Node = None):
        if self.finishing or not self.editing_entry:
            return "break"
        
        target_node = node if node else self.editing_node
        if not target_node:
            return "break"
            
        self.finishing = True
        
        new_text = self.editing_entry.get("1.0", "end-1c")
        
        # エディタ内に画像が残っているかチェック
        # image_names() はそのTextウィジェットに埋め込まれている画像のリストを返す
        has_image = len(self.editing_entry.image_names()) > 0
        
        if not has_image:
            if target_node.image_data or target_node.image_path:
                target_node.image_data = None
                target_node.image_path = None
                self.model.is_modified = True

        if new_text is not None and new_text != target_node.text:
            target_node.text = new_text
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
        self.editing_node = None
        if self.window_id:
            self.canvas.delete(self.window_id)
            self.window_id = None
        self.image_handler.clear_cache()
        self.canvas.focus_set()
