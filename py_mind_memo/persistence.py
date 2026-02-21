import json
import re
from tkinter import filedialog, messagebox

class PersistenceHandler:
    """ファイルの保存・読み込みを管理するクラス"""
    def __init__(self, model, render_callback):
        self.model = model
        self.render_callback = render_callback
        self.current_file_path = None

    def on_save(self, event=None):
        if self.current_file_path:
            self._write_to_file(self.current_file_path)
        else:
            self.on_save_as(event)

    def on_save_as(self, event=None):
        raw_text = self.model.root.text
        # マークアップタグを除去 (e.g. <b>...</b>)
        name = re.sub(r'<[^>]+>', '', raw_text)
        # 改行、タブ、スペース、禁止文字をアンダースコアに置換
        name = re.sub(r'[\s\\/:*?\"<>|]+', '_', name)
        # 前後のアンダースコアを除去
        default_name = name.strip('_')
        
        if len(default_name) > 20:
            default_name = default_name[:20]
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            self._write_to_file(file_path)

    def _write_to_file(self, file_path):
        """共通のファイル書き込み処理"""
        try:
            data = self.model.save()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.current_file_path = file_path
            self.model.is_modified = False
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def on_open(self, event=None):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.model.load(data)
                self.model.is_modified = False
                self.current_file_path = file_path
                self.render_callback(root_node=self.model.root)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
