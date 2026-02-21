import tkinter as tk
from .models import MindMapModel, Node
from .graphics import GraphicsEngine
from .layout import LayoutEngine
from .editor import NodeEditor
from .drag_drop import DragDropHandler
from .navigation import KeyboardNavigator
from .persistence import PersistenceHandler

class MindMapView:
    LOGICAL_CENTER_X = 5000
    LOGICAL_CENTER_Y = 5000

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("py_mind_memo - Mindmap like Tool")
        
        # メインフレーム（CanvasとScrollbarを配置）
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # スクロールバー
        self.v_scroll = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = tk.Scrollbar(self.main_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas = tk.Canvas(self.main_frame, bg="#fafafa", highlightthickness=0,
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
        bind_key("<Delete>", self.on_delete_node)
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
        self.canvas.bind("<B1-Motion>", lambda e: self.drag_handler.handle_motion(e))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.drag_handler.handle_drop(e))

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_mouse_wheel_x(self, event):
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_click(self, event):
        if not self.editor.is_editing():
            self.canvas.focus_set()
            
            # 座標の取得（スクロール位置を考慮）
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            
            # クリックしたノードを選択状態にする
            clicked_node = self.find_node_at(cx, cy)
            
            if clicked_node:
                self.selected_node = clicked_node
                self.render()
                
                # アイコンクリックの判定
                items = self.canvas.find_overlapping(cx-2, cy-2, cx+2, cy+2)
                for item_id in items:
                    tags = self.canvas.gettags(item_id)
                    if "collapse_icon" in tags:
                        clicked_node.collapsed = not clicked_node.collapsed
                        self.render()
                        return "break"

                # ドラッグ開始の準備
                self.drag_handler.start_drag(event, self.selected_node)

    def _on_canvas_double_click(self, event):
        """ダブルクリックで編集モードを開始"""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_node = self.find_node_at(cx, cy)
        
        if clicked_node:
            self.selected_node = clicked_node
            self.render()
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
        self.selected_node = self.navigator.navigate(self.selected_node, direction)
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

    def render(self, force_center=False):
        self.graphics.clear()
        w, h = self._get_canvas_size()
        
        # レイアウト計算: ウィンドウサイズに依存しない固定の基準点を使用
        self.layout_engine.apply_layout(self.model, self.graphics, self.LOGICAL_CENTER_X, self.LOGICAL_CENTER_Y)
        
        # 全ノード描画
        self._draw_subtree(self.model.root)
        
        # スクロールと自動センタリング
        self._update_scroll_and_focus(w, h, force_center)

    def _get_canvas_size(self):
        self.root.update_idletasks()
        w = max(100, self.canvas.winfo_width())
        h = max(100, self.canvas.winfo_height())
        return w, h

    def _update_scroll_and_focus(self, w, h, force_center=False):
        bbox = self.canvas.bbox("all")
        if not bbox: return
        
        # コンテンツ周囲に余白
        margin = 500
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
        
        # scrollregionの変更を反映させる
        self.canvas.update_idletasks()
        
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

    def on_delete_node(self, event):
        if self.editor.is_editing(): return
        if self.selected_node.parent:
            parent = self.selected_node.parent
            parent.remove_child(self.selected_node)
            self.model.is_modified = True
            self.selected_node = parent
            self.render()

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
            from tkinter import messagebox
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
