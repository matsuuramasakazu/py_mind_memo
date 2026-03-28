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
            return self._write_to_file(self.current_file_path)
        else:
            return self.on_save_as(event)

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
            return self._write_to_file(file_path)
        return False

    def _write_to_file(self, file_path):
        """共通のファイル書き込み処理"""
        try:
            data = self.model.save()
            self._perform_write_to_file(file_path, data)
            self.current_file_path = file_path
            self.model.is_modified = False
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save to {file_path}: {e}")
            return False

    def _perform_write_to_file(self, file_path, data):
        """アトミックな書き込みを行う。一時ファイルを作成し、成功時のみ置換する。"""
        import tempfile
        import os

        dir_name = os.path.dirname(os.path.abspath(file_path))
        # ターゲットと同じディレクトリに一時ファイルを作成
        fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            # アトミックに置換
            os.replace(temp_path, file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

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
                messagebox.showerror("Error", f"Failed to load from {file_path}: {e}")
