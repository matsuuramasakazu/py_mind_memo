import tkinter as tk
import os
import sys
import threading
from typing import Optional, Tuple
from .models import MindMapModel, Node, Reference
from .history import HistoryManager
from .graphics import GraphicsEngine
from .layout import LayoutEngine
from .editor import NodeEditor
from .drag_drop import DragDropHandler
from .navigation import KeyboardNavigator
from .persistence import PersistenceHandler
from .dialogs import IconPickerDialog, TemplatePickerDialog
from tkinter import messagebox
from .constants import (
    DEFAULT_LOGICAL_CENTER_X, DEFAULT_LOGICAL_CENTER_Y,
    CANVAS_MARGIN, COLOR_CANVAS_BG, MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT,
    FONT_SIZE_NORMAL, FONT_SIZE_ROOT, FONT_SIZE_MIN, FONT_SIZE_MAX, FONT_SIZE_STEP
)

class MindMapView:
    LOGICAL_CENTER_X = DEFAULT_LOGICAL_CENTER_X
    LOGICAL_CENTER_Y = DEFAULT_LOGICAL_CENTER_Y

    def __init__(self, root: tk.Tk, read_only: bool = False):
        self.root = root
        self.read_only = read_only
        self.root.title("py_mind_memo - Mindmap like Tool")
        
        # 参照関係の編集状態
        self.reference_edit_mode = False
        self.reference_source_node = None
        self.selected_reference = None
        self.selected_handle = None
        self.reference_drag_data = {}
        
        # 拡大画像ウィンドウの管理 (node.id -> tk.Toplevel)
        self.enlarged_image_windows = {}
        
        # フォントサイズの管理（初期値: 10pt）
        self.current_font_size = FONT_SIZE_NORMAL
        self._font_render_timer = None
        
        # メインフレーム（CanvasとScrollbarを配置）
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # スクロールバー
        self.v_scroll = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = tk.Scrollbar(self.main_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas = tk.Canvas(self.main_frame, bg=COLOR_CANVAS_BG, highlightthickness=0,
                                xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.model = MindMapModel()
        self.history = HistoryManager(self.model)
        self.graphics = GraphicsEngine(self.canvas)
        self.layout_engine = LayoutEngine()
        self.selected_node: Node = self.model.root
        self.editor = NodeEditor(self.canvas, self.root, self.graphics, self.render, self.model, history=self.history)
        self.drag_handler = DragDropHandler(
            self.canvas, self.model, self.graphics, self.layout_engine, self.render, self.find_node_at,
            self.LOGICAL_CENTER_X, self.LOGICAL_CENTER_Y, history=self.history
        )
        self.navigator = KeyboardNavigator(self.model, self.render)
        self.persistence = PersistenceHandler(self.model, self._on_load_complete, history=self.history)
        
        # メニューバーの作成
        self._create_menu()
        
        # イベントバインド
        # イベントバインド (bind_allではなくroot.bindを使用し、breakが機能するようにする)
        def bind_key(key, handler):
            self.root.bind(key, self._wrap_handler(handler))

        if not self.read_only:
            # 編集系ショートカット（read_onlyモードでは無効）
            bind_key("<Tab>", self.on_add_child)
            bind_key("<Return>", self.on_add_sibling)
            bind_key("<F2>", self.on_edit_node)
            bind_key("<Delete>", self.on_delete)
            bind_key("<Control-z>", self.on_undo)
            bind_key("<Control-Z>", self.on_undo)
            bind_key("<Control-y>", self.on_redo)
            bind_key("<Control-Y>", self.on_redo)
            bind_key("<Control-r>", self.on_toggle_reference_mode)
            bind_key("<Control-i>", self.on_insert_icon)
            bind_key("<Control-s>", self.persistence.on_save)
            bind_key("<Control-S>", self.persistence.on_save_as) # Ctrl+Shift+S
            bind_key("<Control-o>", self.persistence.on_open)
            bind_key("<Control-n>", self.on_new_from_template)
            bind_key("<Control-Up>", self.on_move_node_up)
            bind_key("<Control-Down>", self.on_move_node_down)

        # ナビゲーション系ショートカット（read_onlyモードでも有効）
        bind_key("<Up>", lambda e: self._navigate("up"))
        bind_key("<Down>", lambda e: self._navigate("down"))
        bind_key("<Left>", lambda e: self._navigate("left"))
        bind_key("<Right>", lambda e: self._navigate("right"))

        # フォントサイズリセット（Ctrl+0, Ctrl+テンキー0、read_onlyモードでも有効）
        bind_key("<Control-0>", self.on_font_zoom_reset)
        bind_key("<Control-Key-0>", self.on_font_zoom_reset)
        bind_key("<Control-KP_0>", self.on_font_zoom_reset)

        if not self.read_only:
            # Ctrl+M: 操作マニュアル（メインウィンドウのみ）
            bind_key("<Control-m>", self.on_show_manual)
        
        # マウスホイール（スクロールおよびフォントサイズ変更）
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_wheel_x)
        self.canvas.bind("<Control-MouseWheel>", self.on_font_zoom_wheel)
        self.canvas.bind("<Control-Button-4>", self.on_font_zoom_in)
        self.canvas.bind("<Control-Button-5>", self.on_font_zoom_out)
        # ステータスバーの追加
        self.status_bar = tk.Label(self.root, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self._is_saving = False
        self._status_timer = None
        
        self.first_render = True
        self.render()
        
        # 自動保存タイマーの開始（read_onlyモードでは無効）
        if not self.read_only:
            self._start_auto_save_timer()

        # マウスイベントのバインド
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_hover_motion)

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def on_font_zoom_wheel(self, event):
        """Ctrl+マウスホイールによるフォントサイズの拡大・縮小"""
        if event.delta > 0:
            self.change_font_size(FONT_SIZE_STEP)
        elif event.delta < 0:
            self.change_font_size(-FONT_SIZE_STEP)
        return "break"

    def on_font_zoom_in(self, event=None):
        """Linux用: Ctrl+Button-4によるフォントサイズ拡大"""
        self.change_font_size(FONT_SIZE_STEP)
        return "break"

    def on_font_zoom_out(self, event=None):
        """Linux用: Ctrl+Button-5によるフォントサイズ縮小"""
        self.change_font_size(-FONT_SIZE_STEP)
        return "break"

    def on_font_zoom_reset(self, event=None):
        """Ctrl+0によるフォントサイズリセット"""
        self.reset_font_size()
        return "break"

    def change_font_size(self, delta: int):
        """フォントサイズを変更し、リミット範囲内であれば適用して再描画する"""
        new_size = self.current_font_size + delta
        if new_size < FONT_SIZE_MIN:
            new_size = FONT_SIZE_MIN
        elif new_size > FONT_SIZE_MAX:
            new_size = FONT_SIZE_MAX

        if new_size == self.current_font_size:
            return

        self.current_font_size = new_size

        # ステータスバーは即時更新して指先の操作感にリアルタイム同期させる
        status = f"フォントサイズ: {self.current_font_size}pt"
        if self.current_font_size == FONT_SIZE_NORMAL:
            status += " (初期値)"
        self.show_status_message(status, timeout=1500)

        # 連続ホイール操作中は再描画を遅延（デバウンス）し、静止後に最終フォントサイズで1回だけ描画
        self._schedule_font_render()

    def reset_font_size(self):
        """フォントサイズを初期サイズにリセットする"""
        if self.current_font_size == FONT_SIZE_NORMAL:
            return

        # 予約中のデバウンス描画があればキャンセルして即時実行
        if self._font_render_timer is not None:
            try:
                self.root.after_cancel(self._font_render_timer)
            except Exception:
                pass
            self._font_render_timer = None

        self.current_font_size = FONT_SIZE_NORMAL
        self._apply_font_size()

        status = f"フォントサイズ: {self.current_font_size}pt (初期値)"
        self.show_status_message(status, timeout=1500)

    def _schedule_font_render(self, debounce_ms: int = 120):
        """フォントサイズ変更時の描画をデバウンスして高負荷を防ぐ"""
        if self._font_render_timer is not None:
            try:
                self.root.after_cancel(self._font_render_timer)
            except Exception:
                pass
            self._font_render_timer = None

        self._font_render_timer = self.root.after(debounce_ms, self._on_debounced_font_render)

    def _on_debounced_font_render(self):
        """デバウンスタイマー満了時に最新のフォントサイズで再描画を行う"""
        self._font_render_timer = None
        self._apply_font_size()

    def _apply_font_size(self):
        """現在のフォントサイズを描画エンジンに反映し、再描画を行う"""
        root_size = self.current_font_size + (FONT_SIZE_ROOT - FONT_SIZE_NORMAL)
        self.graphics.set_font_sizes(self.current_font_size, root_size)
        if self.editor.is_editing():
            self.editor.update_font()
        self.render()

    def _on_canvas_click(self, event):
        self.canvas.focus_set()
        if self.editor.is_editing():
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # read_onlyモードでは参照モード操作・ドラッグ移動・参照線操作をブロックする
        if self.read_only:
            # 画像クリック（拡大表示）は許可
            if self._handle_image_click(cx, cy):
                return "break"
            # 折りたたみ・展開は許可
            if self._handle_node_collapse_click(cx, cy):
                return "break"
            # ノード選択（視覚的フィードバックのため）
            clicked_node = self.find_node_at(cx, cy)
            if clicked_node:
                self._select_node(clicked_node)
            return

        # 1. 参照モードの処理
        if self.reference_edit_mode:
            if self._handle_reference_mode_click(cx, cy):
                return "break"
            return "break"

        # 2. 画像クリック（最優先）
        if self._handle_image_click(cx, cy):
            return "break"

        # 3. 参照ハンドル・線のクリック
        if self._handle_reference_click(cx, cy):
            return "break"

        # 4. 折りたたみアイコンのクリック
        if self._handle_node_collapse_click(cx, cy):
            return "break"

        # 5. 通常のノード選択/ドラッグ開始
        clicked_node = self.find_node_at(cx, cy)
        if clicked_node:
            self._select_node(clicked_node)
            self.drag_handler.start_drag(event, self.selected_node)
        else:
            self._deselect_all()

    def _handle_reference_mode_click(self, cx, cy) -> bool:
        """参照モード選択中のクリック処理を行う"""
        clicked_node = self.find_node_at(cx, cy)
        if not clicked_node:
            return False

        if self.reference_source_node is None:
            self.reference_source_node = clicked_node
            self.root.title("py_mind_memo - Mindmap like Tool [Reference Mode - Select Target]")
        else:
            if self.reference_source_node != clicked_node:
                exists = any(r.source_id == self.reference_source_node.id and r.target_id == clicked_node.id 
                           for r in self.model.references)
                if not exists:
                    self.history.record_snapshot(
                        selected_id=self.reference_source_node.id,
                        selected_type="node"
                    )
                    ref = Reference(self.reference_source_node.id, clicked_node.id)
                    self.model.references.append(ref)
                    self.model.is_modified = True
                    self._select_reference(ref)
            
            self._exit_reference_mode()
        self.render()
        return True

    def _exit_reference_mode(self):
        """参照モードを終了し、UI状態を解除する"""
        self.graphics.clear_temporary_reference()
        self.reference_edit_mode = False
        self.reference_source_node = None
        self.root.title("py_mind_memo - Mindmap like Tool")
        self.canvas.config(cursor="")


    def _handle_image_click(self, cx, cy) -> bool:
        """ノード画像のクリック判定と拡大表示処理を行う"""
        items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "node_image" in tags:
                for t in tags:
                    if t not in ("node_image", "text", "current", "node"):
                        node = self.model.find_node_by_id(t)
                        if node and node.image_path:
                            return self._show_enlarged_image(node)
        return False

    def _handle_reference_click(self, cx, cy) -> bool:
        """参照線またはそのハンドルのクリック判定と選択処理を行う"""
        items = self.canvas.find_overlapping(cx-4, cy-4, cx+4, cy+4)
        clicked_ref = None
        clicked_handle = None
        
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "reference_handle" in tags:
                for t in tags:
                    if t != "reference_handle" and t != "current" and "_" in t and "cp" in t:
                        clicked_handle = t
                if clicked_handle:
                    break
            elif "reference" in tags and not clicked_handle:
                for t in tags:
                    if t != "reference" and t != "current":
                        ref = self.model.find_reference_by_id(t)
                        if ref:
                            clicked_ref = ref

        if clicked_handle:
            self.selected_handle = clicked_handle
            if clicked_ref:
                self.selected_reference = clicked_ref
            else:
                try:
                    ref_id, _ = clicked_handle.rsplit("_", 1)
                    ref = self.model.find_reference_by_id(ref_id)
                    if ref:
                        self.selected_reference = ref
                except ValueError:
                    pass

            ref = self.selected_reference
            if ref:
                try:
                    ref_id, cp_type = clicked_handle.rsplit("_", 1)
                    self.reference_drag_data = {
                        "handle": clicked_handle,
                        "ref_id": ref.id,
                        "cp_type": cp_type,
                        "initial_cp1": (ref.cp1_x, ref.cp1_y),
                        "initial_cp2": (ref.cp2_x, ref.cp2_y),
                        "initial_is_modified": getattr(self.model, "is_modified", False),
                    }
                except ValueError:
                    self.reference_drag_data = {}
            else:
                self.reference_drag_data = {}

            if self.selected_node is not None:
                old_node = self.selected_node
                self.selected_node = None
                self.graphics.draw_node(old_node, is_selected=False)
            return True
            
        if clicked_ref:
            self._select_reference(clicked_ref)
            return True
            
        return False

    def _handle_node_collapse_click(self, cx, cy) -> bool:
        """折りたたみアイコンのクリック判定と開閉処理を行う"""
        items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "collapse_icon" in tags:
                for t in tags:
                    if t != "collapse_icon" and t != "current":
                        node = self.model.find_node_by_id(t)
                        if node:
                            node.collapsed = not node.collapsed
                            self.model.is_modified = True
                            self.selected_node = node
                            self.render()
                            return True
        return False

    def _select_node(self, node):
        """指定したノードを選択状態にする（他の選択は解除される）"""
        if self.selected_node != node or self.selected_reference is not None:
            old_node = self.selected_node
            self.selected_node = node
            
            if old_node and old_node != self.selected_node:
                self.graphics.draw_node(old_node, is_selected=False)
            self.graphics.draw_node(self.selected_node, is_selected=True)
            
            if self.selected_reference is not None:
                old_ref = self.selected_reference
                self.selected_reference = None
                self._redraw_reference(old_ref, is_selected=False)

    def _select_reference(self, ref):
        """指定した参照を選択状態にする（他の選択は解除される）"""
        if self.selected_reference != ref or self.selected_node is not None:
            old_ref = self.selected_reference
            self.selected_reference = ref
            
            if old_ref and old_ref != self.selected_reference:
                self._redraw_reference(old_ref, is_selected=False)
            
            self._redraw_reference(self.selected_reference, is_selected=True)
            
            if self.selected_node is not None:
                old_node = self.selected_node
                self.selected_node = None
                self.graphics.draw_node(old_node, is_selected=False)

    def _deselect_all(self):
        """全てのノード・参照の選択を解除する（参照のみ先行して解除）"""
        if self.selected_reference is not None:
            old_ref = self.selected_reference
            self.selected_reference = None
            self._redraw_reference(old_ref, is_selected=False)
        # selected_node の選択解除は find_node_at が None を返したときに行うべきだが、
        # 現在の logic ではクリックした場所に何もなければ選択を維持する仕様のようなので、
        # ここでは参照の解除にとどめる（既存の振る舞いを維持）。

    def _redraw_reference(self, ref, is_selected):
        """特定の参照線を再描画する"""
        if not ref:
            return
        source_node = self.model.find_node_by_id(ref.source_id)
        target_node = self.model.find_node_by_id(ref.target_id)
        if source_node and target_node:
            self.graphics.draw_reference(ref, source_node, target_node, is_selected=is_selected)

    def _on_motion(self, event):
        if self.read_only:
            return
        if self.selected_handle:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            try:
                ref_id, cp_type = self.selected_handle.rsplit("_", 1)
                ref = self.model.find_reference_by_id(ref_id)
                if ref:
                    if cp_type == "cp1":
                        ref.cp1_x, ref.cp1_y = cx, cy
                    elif cp_type == "cp2":
                        ref.cp2_x, ref.cp2_y = cx, cy
                    self.model.is_modified = True
                    
                    # 全体を再描画すると点滅するため、対象の参照線のみを部分再描画する
                    source_node = self.model.find_node_by_id(ref.source_id)
                    target_node = self.model.find_node_by_id(ref.target_id)
                    if source_node and target_node:
                        self.graphics.draw_reference(ref, source_node, target_node, is_selected=True)
            except ValueError:
                pass
        else:
            self.drag_handler.handle_motion(event)
            
    def _on_release(self, event):
        if self.read_only:
            return
        if self.selected_handle:
            if hasattr(self, 'reference_drag_data') and self.reference_drag_data:
                ref_id = self.reference_drag_data.get("ref_id")
                ref = self.model.find_reference_by_id(ref_id)
                if ref:
                    initial_cp1 = self.reference_drag_data.get("initial_cp1")
                    initial_cp2 = self.reference_drag_data.get("initial_cp2")
                    initial_is_modified = self.reference_drag_data.get("initial_is_modified")

                    new_cp1 = (ref.cp1_x, ref.cp1_y)
                    new_cp2 = (ref.cp2_x, ref.cp2_y)

                    if new_cp1 != initial_cp1 or new_cp2 != initial_cp2:
                        # 座標が変更された場合
                        # 一旦初期値に戻してスナップショット記録
                        ref.cp1_x, ref.cp1_y = initial_cp1
                        ref.cp2_x, ref.cp2_y = initial_cp2
                        self.history.record_snapshot(
                            selected_id=ref.id,
                            selected_type="reference"
                        )
                        # 新しい値を再適用
                        ref.cp1_x, ref.cp1_y = new_cp1
                        ref.cp2_x, ref.cp2_y = new_cp2
                        self.model.is_modified = True
                    else:
                        # 変更がなかった場合
                        ref.cp1_x, ref.cp1_y = initial_cp1
                        ref.cp2_x, ref.cp2_y = initial_cp2
                        self.model.is_modified = initial_is_modified
                        source_node = self.model.find_node_by_id(ref.source_id)
                        target_node = self.model.find_node_by_id(ref.target_id)
                        if source_node and target_node:
                            self.graphics.draw_reference(ref, source_node, target_node, is_selected=True)
                self.reference_drag_data = {}
            self.selected_handle = None
        else:
            self.drag_handler.handle_drop(event)

    def _on_hover_motion(self, event):
        """マウスホバー時の処理。参照モードでの一時線描画等を行う"""
        if self.reference_edit_mode and self.reference_source_node:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            self.graphics.draw_temporary_reference(self.reference_source_node, cx, cy)

    def _on_canvas_double_click(self, event):
        """ダブルクリックで編集モードを開始（read_onlyモードでは無効）"""
        if self.read_only:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_node = self.find_node_at(cx, cy)
        
        if clicked_node:
            # 既に編集中なら一旦保存・終了
            if self.editor.is_editing():
                self.editor.finish_edit()
            
            self.selected_node = clicked_node
            # self.render() は on_edit_node -> start_edit 内で必要な場合に行われるか、
            # あるいは編集開始時にウィジェットを重ねるだけなので、ここでは一旦不要。
            # むしろ render() を呼ぶとウィジェットが消える原因になる。
            self.on_edit_node(None)

    def find_node_at(self, x, y):
        """指定座標にあるノードを返す"""
        # 矩形の当たり判定 (クリック範囲を少し広げる)
        # find_overlapping は (x1, y1, x2, y2) で指定
        padding = 10
        items = self.canvas.find_overlapping(x-padding, y-padding, x+padding, y+padding)
        # 描画順（スタッキング順）の逆順でチェックすることで、前面にある（新しい）ノードを優先する
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            if "node" in tags or "text" in tags:
                # タグからnode_idを取得 (e.g., "node <uuid>")
                for tag in tags:
                    if tag not in ("node", "text", "current", "ghost"):
                        node_id = tag
                        return self.model.find_node_by_id(node_id)
        return None

    def _navigate(self, direction):
        old_node = self.selected_node
        self.selected_node = self.navigator.navigate(self.selected_node, direction)
        
        if old_node == self.selected_node:
            if self.selected_node:
                self.ensure_node_visible(self.selected_node, force_center=True)
            return

        needs_full_render = False
        if self.selected_node and self.selected_node.parent:
            curr = self.selected_node.parent
            while curr:
                if curr.collapsed:
                    curr.collapsed = False
                    needs_full_render = True
                curr = curr.parent

        if needs_full_render:
            self.model.is_modified = True
            self.render(force_center=True)
        else:
            # 画面全体ではなくトピックの枠のみ再描画する
            if old_node:
                self.graphics.draw_node(old_node, is_selected=False)
            if self.selected_node:
                self.graphics.draw_node(self.selected_node, is_selected=True)
                self.ensure_node_visible(self.selected_node, force_center=True)
        
        if not self.selected_node and not needs_full_render:
            self.render(force_center=True)

    def _close_enlarged_image_windows(self):
        for win in list(self.enlarged_image_windows.values()):
            if win.winfo_exists():
                win.destroy()
        self.enlarged_image_windows.clear()

    def _on_load_complete(self, root_node):
        self._close_enlarged_image_windows()
        self.selected_node = root_node
        self.history.clear()
        self.render(force_center=True)

    def _wrap_handler(self, func):
        """編集中は入力を無視し、かつイベントが他へ伝播しないようにする"""
        def wrapper(event):
            if self.editor.is_editing():
                return "break"
            res = func(event)
            return "break" # 基本的にマインドマップの操作はここで完結させる
        return wrapper

    def _is_node_visible(self, node: Node) -> bool:
        curr = node.parent
        while curr:
            if curr.collapsed:
                return False
            curr = curr.parent
        return True

    def render(self, force_center=False):
        self.graphics.clear()
        w, h = self._get_canvas_size()
        
        # レイアウト計算: ウィンドウサイズに依存しない固定の基準点を使用
        self.layout_engine.apply_layout(self.model, self.graphics, self.LOGICAL_CENTER_X, self.LOGICAL_CENTER_Y)
        
        # 全ノード描画
        self._draw_subtree(self.model.root)
        
        # 参照関係の描画
        for ref in self.model.references:
            source_node = self.model.find_node_by_id(ref.source_id)
            target_node = self.model.find_node_by_id(ref.target_id)
            if source_node and target_node:
                if self._is_node_visible(source_node) and self._is_node_visible(target_node):
                    is_selected = (ref == self.selected_reference)
                    self.graphics.draw_reference(ref, source_node, target_node, is_selected=is_selected)
        
        # スクロールと自動センタリング
        self._update_scroll_and_focus(w, h, force_center)

    def _get_canvas_size(self):
        # ウィンドウサイズが確定していない初期のみ update_idletasks を呼ぶ
        if self.first_render:
            self.root.update_idletasks()
        w = max(100, self.canvas.winfo_width())
        h = max(100, self.canvas.winfo_height())
        return w, h


    def _update_scroll_and_focus(self, w, h, force_center=False):
        bbox = self.canvas.bbox("all")
        if not bbox: return
        
        # コンテンツ周囲に余白
        margin = CANVAS_MARGIN
        new_sr = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
        self.canvas.config(scrollregion=new_sr)
        
        if self.first_render:
            self.canvas.update_idletasks() # 表示状態を確定
            bbox = self.canvas.bbox("all") # 再計算後のbboxを取得
            if bbox:
                new_sr = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
                self.canvas.config(scrollregion=new_sr)
            self._center_on_root(new_sr, w, h)
            self.first_render = False
        
        self.ensure_node_visible(self.selected_node, force_center=force_center)

    def _center_on_root(self, sr, w, h):
        sr_w, sr_h = sr[2] - sr[0], sr[3] - sr[1]
        fraction_x = (self.LOGICAL_CENTER_X - sr[0] - w/2) / sr_w
        fraction_y = (self.LOGICAL_CENTER_Y - sr[1] - h/2) / sr_h
        self.canvas.xview_moveto(max(0, fraction_x))
        self.canvas.yview_moveto(max(0, fraction_y))

    def ensure_node_visible(self, node: Node, force_center=False):
        """指定したノードが画面外にある場合、見える位置までスクロールする"""
        if not node or not self.canvas.cget("scrollregion"): return

        
        # キャンバス上の現在の表示領域を取得 (比率 0.0 to 1.0)
        vx1, vx2 = self.canvas.xview()
        vy1, vy2 = self.canvas.yview()
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # scrollregionを取得
        sr = [float(c) for c in self.canvas.cget("scrollregion").split()]
        sr_w = sr[2] - sr[0]
        sr_h = sr[3] - sr[1]
        
        # ノードの現在位置（比率）
        node_rel_x = (node.x - sr[0]) / sr_w
        node_rel_y = (node.y - sr[1]) / sr_h
        
        # 画面の幅の比率
        view_w_ratio = w / sr_w
        view_h_ratio = h / sr_h
        
        margin = 0.05
        
        # すでに十分見えている場合は何もしない（ジャンプ防止）
        if not force_center:
            if vx1 + margin <= node_rel_x <= vx2 - margin and \
               vy1 + margin <= node_rel_y <= vy2 - margin:
                return

        # 画面外（または端に近い）なら移動
        if force_center or node_rel_x < vx1 + margin or node_rel_x > vx2 - margin:
            self.canvas.xview_moveto(max(0, node_rel_x - view_w_ratio / 2))
            
        if force_center or node_rel_y < vy1 + margin or node_rel_y > vy2 - margin:
            self.canvas.yview_moveto(max(0, node_rel_y - view_h_ratio / 2))

    def _draw_subtree(self, node: Node):
        self.graphics.draw_node(node, is_selected=(node == self.selected_node))
        if not node.collapsed:
            for child in node.children:
                self._draw_subtree(child)

    def _get_selected_id(self) -> Optional[str]:
        if self.selected_node:
            return self.selected_node.id
        elif self.selected_reference:
            return self.selected_reference.id
        return None

    def _get_selected_type(self) -> str:
        if self.selected_reference:
            return "reference"
        return "node"

    def _restore_selection(self, selected_id: Optional[str], selected_type: str = "node"):
        if selected_type == "reference" and selected_id:
            ref = self.model.find_reference_by_id(selected_id)
            if ref:
                self.selected_reference = ref
                self.selected_node = None
                return
        if selected_id:
            node = self.model.find_node_by_id(selected_id)
            if node:
                self.selected_node = node
                self.selected_reference = None
                return
        self.selected_node = self.model.root
        self.selected_reference = None

    def _ensure_selected_visible(self):
        if self.selected_node:
            self.ensure_node_visible(self.selected_node, force_center=True)
        elif self.selected_reference:
            source_node = self.model.find_node_by_id(self.selected_reference.source_id)
            if source_node:
                self.ensure_node_visible(source_node, force_center=True)

    def on_undo(self, event=None):
        if not self.history.can_undo():
            self.show_status_message("これ以上元に戻せません")
            return "break"

        res = self.history.undo(
            current_selected_id=self._get_selected_id(),
            current_selected_type=self._get_selected_type()
        )
        if res:
            selected_id, selected_type = res
            self._restore_selection(selected_id, selected_type)
        self.render()
        self._ensure_selected_visible()
        return "break"

    def on_redo(self, event=None):
        if not self.history.can_redo():
            self.show_status_message("これ以上やり直せません")
            return "break"

        res = self.history.redo(
            current_selected_id=self._get_selected_id(),
            current_selected_type=self._get_selected_type()
        )
        if res:
            selected_id, selected_type = res
            self._restore_selection(selected_id, selected_type)
        self.render()
        self._ensure_selected_visible()
        return "break"

    def on_add_child(self, event):
        if self.editor.is_editing(): return
        
        self.history.record_snapshot(
            selected_id=self.selected_node.id if self.selected_node else None,
            selected_type="node"
        )

        # 折りたたまれている場合は展開する
        if self.selected_node.collapsed:
            self.selected_node.collapsed = False
            
        new_node = self.model.add_node(self.selected_node)
        self.selected_node = new_node
        self.render()
        self.on_edit_node(None)

    def on_add_sibling(self, event):
        if self.editor.is_editing(): return
        if self.selected_node.parent:
            self.history.record_snapshot(
                selected_id=self.selected_node.id if self.selected_node else None,
                selected_type="node"
            )
            new_node = self.model.add_node(self.selected_node.parent)
            self.selected_node = new_node
            self.render()
            self.on_edit_node(None)

    def on_edit_node(self, event):
        self.editor.start_edit(self.selected_node)
        return "break"

    def on_delete(self, event):
        if self.editor.is_editing(): return
        
        # 参照の削除が優先
        if self.selected_reference:
            if self.selected_reference in self.model.references:
                self.history.record_snapshot(
                    selected_id=self.selected_reference.id,
                    selected_type="reference"
                )
                self.model.references.remove(self.selected_reference)
                self.model.is_modified = True
            self.selected_reference = None
            self.render()
            return "break"
            
        if self.selected_node and self.selected_node.parent:
            parent = self.selected_node.parent
            self.history.record_snapshot(
                selected_id=self.selected_node.id,
                selected_type="node"
            )
            parent.remove_child(self.selected_node)
            # 関連する参照関係も削除
            self.model.references = [ref for ref in self.model.references 
                                     if ref.source_id != self.selected_node.id and ref.target_id != self.selected_node.id]
            self.model.is_modified = True
            self.selected_node = parent
            self.render()

    def _on_move_node(self, move_func, direction: int):
        if not self.selected_node or not self.selected_node.parent:
            return "break"
            
        siblings = self.selected_node.parent.children
        try:
            idx = siblings.index(self.selected_node)
        except ValueError:
            return "break"
            
        new_idx = idx + direction
        if 0 <= new_idx < len(siblings):
            self.history.record_snapshot(
                selected_id=self.selected_node.id,
                selected_type="node"
            )
            if move_func(self.selected_node):
                self.render()
                self.ensure_node_visible(self.selected_node)
        return "break"

    def on_move_node_up(self, event=None):
        return self._on_move_node(self.model.move_node_up, -1)

    def on_move_node_down(self, event=None):
        return self._on_move_node(self.model.move_node_down, 1)

    def on_toggle_reference_mode(self, event):
        if self.editor.is_editing(): return
        self.reference_edit_mode = not self.reference_edit_mode
        if not self.reference_edit_mode:
            self._exit_reference_mode()
        else:
            self.selected_node = None
            self.selected_reference = None
            self.root.title("py_mind_memo - Mindmap like Tool [Reference Mode]")
            self.canvas.config(cursor="crosshair")
        self.render()
        return "break"

    def on_new_from_template(self, event=None):
        if self.editor.is_editing():
            return "break"
            
        dialog = TemplatePickerDialog(self.root)
        path = dialog.show()
        if path:
            self.persistence.on_open_template(path)
            
        return "break"

    def on_insert_icon(self, event):
        if self.editor.is_editing():
            return
        if not self.selected_node:
            return
        
        dialog = IconPickerDialog(self.root)
        path, photo = dialog.show()
        
        if path == "CLEAR":
            if self.selected_node.icon_data is not None or self.selected_node.icon_path is not None:
                if self.history:
                    self.history.record_snapshot(
                        selected_id=self.selected_node.id,
                        selected_type="node"
                    )
                self.selected_node.icon_data = None
                self.selected_node.icon_path = None
                self.model.is_modified = True
                self.render()
        elif path and photo:
            try:
                base64_data = self.editor.image_handler.base64_from_photo(photo)
                if self.selected_node.icon_data != base64_data or self.selected_node.icon_path != path:
                    if self.history:
                        self.history.record_snapshot(
                            selected_id=self.selected_node.id,
                            selected_type="node"
                        )
                    self.selected_node.icon_data = base64_data
                    self.selected_node.icon_path = path
                    self.model.is_modified = True
                    self.render()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to insert icon: {e}")
                
        return "break"

    def _create_menu(self):
        # ウィンドウの閉じるボタン（×）のハンドラ（read_onlyモードでも必要）
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        if self.read_only:
            # read_onlyモードではメニューバーを表示しない
            return

        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New from Template (Ctrl+N)", command=self.on_new_from_template)
        filemenu.add_command(label="Open (Ctrl+O)", command=self.persistence.on_open)
        filemenu.add_command(label="Save (Ctrl+S)", command=self.persistence.on_save)
        filemenu.add_command(label="Save As (Ctrl+Shift+S)", command=self.persistence.on_save_as)
        filemenu.add_separator()
        filemenu.add_command(label="操作マニュアル (Ctrl+M)", command=self.on_show_manual)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

    def on_show_manual(self, event=None):
        """操作マニュアルをモーダルダイアログで表示する"""
        manual_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "documents", "操作方法マニュアル.json"
        )
        if not os.path.exists(manual_path):
            messagebox.showerror("Error", f"操作マニュアルファイルが見つかりません: {manual_path}")
            return "break"

        top = tk.Toplevel(self.root)
        top.title("操作マニュアル - py_mind_memo")
        top.transient(self.root)  # メインウィンドウに紐付け

        # クロスプラットフォーム対応の最大化
        if sys.platform == "win32":
            top.state("zoomed")
        elif sys.platform == "darwin":
            # macOSはzoomed相当なし; 画面サイズに合わせてウィンドウを設定
            top.geometry(f"{top.winfo_screenwidth()}x{top.winfo_screenheight()}+0+0")
        else:
            # Linux (X11)
            top.attributes("-zoomed", True)

        manual_view = MindMapView(top, read_only=True)
        top.title("操作マニュアル - py_mind_memo") # MindMapView.__init__による上書きを修正
        manual_view.persistence.open_from_path(manual_path)

        top.grab_set()
        top.focus_set()
        return "break"

    def on_exit(self):
        """ウィンドウを閉じる。read_onlyモードでは確認なしで閉じる"""
        if self.read_only:
            # read_onlyモード（マニュアルウィンドウ）では確認ダイアログを表示せず、
            # destroy()でウィンドウ自身のみを閉じる（quit()はアプリ全体を終了させるためNG）
            self.root.destroy()
            return

        if self.model.is_modified:
            response = messagebox.askyesnocancel(
                "py_mind_memo",
                "Do you want to save changes before exiting?"
            )
            if response is True: # Save
                self.persistence.on_save()
                if not self.model.is_modified: # 保存に成功した場合
                    self.root.quit()
            elif response is False: # Discard
                self.root.quit()
            else: # Cancel
                pass
        else:
            self.root.quit()

    def _show_enlarged_image(self, node: Node) -> bool:
        """元の画像を拡大表示ウィンドウで表示する"""
        try:
            # 既にウィンドウが開いている場合は最前面に持ってくる
            if node.id in self.enlarged_image_windows:
                win = self.enlarged_image_windows[node.id]
                if win.winfo_exists():
                    win.lift()
                    win.focus_set()
                    return True
                else:
                    del self.enlarged_image_windows[node.id]

            # 画像の読み込み（サイズ取得のために先に読み込む）
            # ファイル存在チェックとオープンの間の時間差によるエラーを防ぐため try-except 内で行う
            photo = tk.PhotoImage(file=node.image_path)
            img_w = photo.width()
            img_h = photo.height()

            # インポートした画像サイズが定数未満の場合は拡大表示ウィンドウを表示しない
            if img_w < MAX_IMAGE_WIDTH and img_h < MAX_IMAGE_HEIGHT:
                return False

            # 拡大表示用のウィンドウ作成
            top = tk.Toplevel(self.root)
            self.enlarged_image_windows[node.id] = top
            top.title(f"Enlarged Image - {os.path.basename(node.image_path)}")
            
            # デフォルトの最大サイズ
            max_w, max_h = 800, 600
            # ボタンやスクロールバーのための余白
            padding_w, padding_h = 40, 100 
            
            # ウィンドウサイズを画像に合わせて調整（ただし最大サイズを超えない）
            win_w = min(max_w, img_w + padding_w)
            win_h = min(max_h, img_h + padding_h)
            
            top.geometry(f"{int(win_w)}x{int(win_h)}")

            # --- 下から順に配置していくことでボタンを確実に表示させる ---
            
            # ウィンドウが閉じられた時の処理
            def on_close():
                if node.id in self.enlarged_image_windows:
                    del self.enlarged_image_windows[node.id]
                top.destroy()
                
            top.protocol("WM_DELETE_WINDOW", on_close)

            # 1. 閉じるボタンを一番下に配置
            close_btn = tk.Button(top, text="Close", command=on_close, padx=20)
            close_btn.pack(side=tk.BOTTOM, pady=10)

            # 2. 水平スクロールバーをその上に配置
            h_scroll = tk.Scrollbar(top, orient=tk.HORIZONTAL) 
            h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

            # 3. 残りのメイン領域にフレームを配置
            frame = tk.Frame(top)
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # スクロールバー (垂直)
            v_scroll = tk.Scrollbar(frame, orient=tk.VERTICAL)
            v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # キャンバス（画像表示用）
            canvas = tk.Canvas(frame, bg="gray", highlightthickness=0,
                               xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            v_scroll.config(command=canvas.yview)
            h_scroll.config(command=canvas.xview)

            # GC防止
            canvas.image = photo 
            
            # 画像を配置
            canvas.create_image(0, 0, image=photo, anchor="nw")
            
            # スクロール領域の設定
            canvas.config(scrollregion=(0, 0, img_w, img_h))
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open enlarged image: {e}")
            return False

    def show_status_message(self, message, timeout=1000):
        """ステータスバーにメッセージを表示し、timeoutミリ秒後に消去する"""
        if getattr(self, '_status_timer', None) is not None:
            try:
                self.root.after_cancel(self._status_timer)
            except Exception:
                pass
            self._status_timer = None

        self.status_bar.config(text=message)
        self._status_timer = self.root.after(timeout, self._clear_status_message)

    def _clear_status_message(self):
        self.status_bar.config(text="")
        self._status_timer = None

    def _start_auto_save_timer(self):
        # 10秒 (10000ms) 後にチェックを実行
        self.root.after(10000, self._auto_save_check)

    def _auto_save_check(self):
        # ファイルパスが設定されており、変更があり、かつ編集中・保存中でない場合のみ保存
        try:
            if (self.persistence.current_file_path and 
                self.model.is_modified and 
                not self.editor.is_editing() and
                not self._is_saving):
                
                self._is_saving = True
                # メインスレッドでデータをキャプチャ。その時点のリビジョンと state_id を取得。
                data, revision = self.model.save_with_revision()
                save_state_id = self.history.current_state_id if self.history else None
                file_path = self.persistence.current_file_path
                
                def run_save():
                    try:
                        self.persistence._perform_write_to_file(file_path, data)
                        self.root.after(0, self._on_auto_save_complete, True, revision, save_state_id)
                    except Exception:
                        self.root.after(0, self._on_auto_save_complete, False, revision, save_state_id)

                threading.Thread(target=run_save, daemon=True).start()
        except Exception:
            # スレッド開始前までのエラーに対するフェイルセーフ
            self._is_saving = False
        finally:
            # 次のタイマーをセット (例外に関わらず呼び出す)
            self._start_auto_save_timer()

    def _on_auto_save_complete(self, success, revision, save_state_id=None):
        self._is_saving = False
        if success:
            if self.history and save_state_id is not None:
                self.history.mark_saved(save_state_id)
            elif self.model.modification_count == revision:
                self.model.is_modified = False
                if self.history:
                    self.history.mark_saved()
            self.show_status_message("Saved automatically", 1000)
