import tkinter as tk
from .models import MindMapModel, Node, Reference
from .graphics import GraphicsEngine
from .graphics import GraphicsEngine
from .layout import LayoutEngine
from .editor import NodeEditor
from .drag_drop import DragDropHandler
from .navigation import KeyboardNavigator
from .persistence import PersistenceHandler
from tkinter import messagebox
from .constants import (
    DEFAULT_LOGICAL_CENTER_X, DEFAULT_LOGICAL_CENTER_Y,
    CANVAS_MARGIN, COLOR_CANVAS_BG
)

class MindMapView:
    LOGICAL_CENTER_X = DEFAULT_LOGICAL_CENTER_X
    LOGICAL_CENTER_Y = DEFAULT_LOGICAL_CENTER_Y

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("py_mind_memo - Mindmap like Tool")
        
        # 参照関係の編集状態
        self.reference_edit_mode = False
        self.reference_source_node = None
        self.selected_reference = None
        self.selected_handle = None
        
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
        self.graphics = GraphicsEngine(self.canvas)
        self.layout_engine = LayoutEngine()
        self.selected_node: Node = self.model.root
        self.editor = NodeEditor(self.canvas, self.root, self.graphics, self.render, self.model)
        self.drag_handler = DragDropHandler(
            self.canvas, self.model, self.graphics, self.layout_engine, self.render, self.find_node_at,
            self.LOGICAL_CENTER_X, self.LOGICAL_CENTER_Y
        )
        self.navigator = KeyboardNavigator(self.model, self.render)
        self.persistence = PersistenceHandler(self.model, self._on_load_complete)
        
        # メニューバーの作成
        self._create_menu()
        
        # イベントバインド
        # イベントバインド (bind_allではなくroot.bindを使用し、breakが機能するようにする)
        def bind_key(key, handler):
            self.root.bind(key, self._wrap_handler(handler))

        bind_key("<Tab>", self.on_add_child)
        bind_key("<Return>", self.on_add_sibling)
        bind_key("<F2>", self.on_edit_node)
        bind_key("<Delete>", self.on_delete)
        bind_key("<Control-r>", self.on_toggle_reference_mode)
        bind_key("<Control-s>", self.persistence.on_save)
        bind_key("<Control-S>", self.persistence.on_save_as) # Ctrl+Shift+S
        bind_key("<Control-o>", self.persistence.on_open)
        bind_key("<Up>", lambda e: self._navigate("up"))
        bind_key("<Down>", lambda e: self._navigate("down"))
        bind_key("<Left>", lambda e: self._navigate("left"))
        bind_key("<Right>", lambda e: self._navigate("right"))
        
        # マウスホイール
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_wheel_x)
        
        self.first_render = True
        self.render()

        # マウスイベントのバインド
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_click(self, event):
        self.canvas.focus_set()
        if not self.editor.is_editing():
            
            # 座標の取得（スクロール位置を考慮）
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            
            if self.reference_edit_mode:
                clicked_node = self.find_node_at(cx, cy)
                if clicked_node:
                    if self.reference_source_node is None:
                        self.reference_source_node = clicked_node
                        self.root.title("py_mind_memo - Mindmap like Tool [Reference Mode - Select Target]")
                    else:
                        if self.reference_source_node != clicked_node:
                            # 既に同じ接続元→接続先の参照が存在するかチェック
                            exists = any(r.source_id == self.reference_source_node.id and r.target_id == clicked_node.id for r in self.model.references)
                            if not exists:
                                # 新しい参照を作成
                                ref = Reference(self.reference_source_node.id, clicked_node.id)
                                self.model.references.append(ref)
                                self.model.is_modified = True
                            
                            # 編集モード終了
                            self.reference_edit_mode = False
                            self.reference_source_node = None
                            self.root.title("py_mind_memo - Mindmap like Tool")
                            self.canvas.config(cursor="")
                    self.render()
                return "break"

            # 参照のハンドル（操作点）や線のクリック判定を優先する
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
                            if ref: clicked_ref = ref

            if clicked_handle:
                self.selected_handle = clicked_handle
                if clicked_ref: self.selected_reference = clicked_ref
                self.selected_node = None
                return "break"

            clicked_node = self.find_node_at(cx, cy)
            
            # アイコンクリックの判定を最優先にする（ノード選択状態の切り替え等の前に処理）
            items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
            for item_id in reversed(items):
                tags = self.canvas.gettags(item_id)
                if "collapse_icon" in tags:
                    for t in tags:
                        if t != "collapse_icon" and t != "current":
                            node = self.model.find_node_by_id(t)
                            if node:
                                node.collapsed = not node.collapsed
                                self.selected_node = node
                                self.render()
                                return "break"
            
            # 通常モードの処理
            if clicked_node:
                # 別のノードをクリックした場合は、全体再描画ではなく選択状態の部分更新のみ行う
                if self.selected_node != clicked_node or self.selected_reference is not None:
                    old_node = self.selected_node
                    self.selected_node = clicked_node
                    
                    if old_node and old_node != self.selected_node:
                        self.graphics.draw_node(old_node, is_selected=False)
                    self.graphics.draw_node(self.selected_node, is_selected=True)
                    
                    if self.selected_reference is not None:
                        # 参照の選択状態も解除する
                        old_ref = self.selected_reference
                        self.selected_reference = None
                        source_node = self.model.find_node_by_id(old_ref.source_id)
                        target_node = self.model.find_node_by_id(old_ref.target_id)
                        if source_node and target_node:
                            self.graphics.draw_reference(old_ref, source_node, target_node, is_selected=False)

                # ドラッグ開始の準備
                self.drag_handler.start_drag(event, self.selected_node)
            else:
                if clicked_ref:
                    if self.selected_reference != clicked_ref or self.selected_node is not None:
                        old_ref = self.selected_reference
                        self.selected_reference = clicked_ref
                        
                        if old_ref and old_ref != self.selected_reference:
                            source_node = self.model.find_node_by_id(old_ref.source_id)
                            target_node = self.model.find_node_by_id(old_ref.target_id)
                            if source_node and target_node:
                                self.graphics.draw_reference(old_ref, source_node, target_node, is_selected=False)
                        
                        source_node = self.model.find_node_by_id(self.selected_reference.source_id)
                        target_node = self.model.find_node_by_id(self.selected_reference.target_id)
                        if source_node and target_node:
                            self.graphics.draw_reference(self.selected_reference, source_node, target_node, is_selected=True)
                        
                        if self.selected_node is not None:
                            old_node = self.selected_node
                            self.selected_node = None
                            self.graphics.draw_node(old_node, is_selected=False)
                else:
                    if self.selected_reference is not None:
                        old_ref = self.selected_reference
                        self.selected_reference = None
                        source_node = self.model.find_node_by_id(old_ref.source_id)
                        target_node = self.model.find_node_by_id(old_ref.target_id)
                        if source_node and target_node:
                            self.graphics.draw_reference(old_ref, source_node, target_node, is_selected=False)

    def _on_motion(self, event):
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
        if self.selected_handle:
            self.selected_handle = None
        else:
            self.drag_handler.handle_drop(event)

    def _on_canvas_double_click(self, event):
        """ダブルクリックで編集モードを開始"""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_node = self.find_node_at(cx, cy)
        
        if clicked_node:
            # 既に編集中なら一旦キャンセル（前の変更はFocusOutで保存されているはず）
            if self.editor.is_editing():
                self.editor.cancel_edit()
            
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
        
        # 画面全体ではなくトピックの枠のみ再描画する
        if old_node and old_node != self.selected_node:
            self.graphics.draw_node(old_node, is_selected=False)
        if self.selected_node:
            self.graphics.draw_node(self.selected_node, is_selected=True)
            self.ensure_node_visible(self.selected_node, force_center=True)
        else:
            self.render(force_center=True)

    def _on_load_complete(self, root_node):
        self.selected_node = root_node
        self.render()

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

    def on_add_child(self, event):
        if self.editor.is_editing(): return
        
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
                self.model.references.remove(self.selected_reference)
                self.model.is_modified = True
            self.selected_reference = None
            self.render()
            return "break"
            
        if self.selected_node and self.selected_node.parent:
            parent = self.selected_node.parent
            parent.remove_child(self.selected_node)
            # 関連する参照関係も削除
            self.model.references = [ref for ref in self.model.references 
                                     if ref.source_id != self.selected_node.id and ref.target_id != self.selected_node.id]
            self.model.is_modified = True
            self.selected_node = parent
            self.render()

    def on_toggle_reference_mode(self, event):
        if self.editor.is_editing(): return
        self.reference_edit_mode = not self.reference_edit_mode
        if not self.reference_edit_mode:
            self.reference_source_node = None
            self.root.title("py_mind_memo - Mindmap like Tool")
            self.canvas.config(cursor="")
        else:
            self.selected_node = None
            self.selected_reference = None
            self.root.title("py_mind_memo - Mindmap like Tool [Reference Mode]")
            self.canvas.config(cursor="crosshair")
        self.render()
        return "break"

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open (Ctrl+O)", command=self.persistence.on_open)
        filemenu.add_command(label="Save (Ctrl+S)", command=self.persistence.on_save)
        filemenu.add_command(label="Save As (Ctrl+Shift+S)", command=self.persistence.on_save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)
        
        # ウィンドウの閉じるボタン(×)のハンドラ
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def on_exit(self):
        """アプリを終了する際の確認"""
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
