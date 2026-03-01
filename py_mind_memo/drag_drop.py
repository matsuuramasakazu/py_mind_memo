import tkinter as tk
from .models import Node

class DragDropHandler:
    """ノードのドラッグ＆ドロップ移動を管理するクラス"""
    def __init__(self, canvas, model, graphics, layout_engine, render_callback, find_node_at, logical_center_x, logical_center_y):
        self.canvas = canvas
        self.model = model
        self.graphics = graphics
        self.layout_engine = layout_engine
        self.render_callback = render_callback
        self.find_node_at = find_node_at
        self.logical_center_x = logical_center_x
        self.logical_center_y = logical_center_y
        self.drag_data = {}

    def start_drag(self, event, node):
        if not node: return
        self.drag_data = {"item": node, "x": event.x, "y": event.y, "dragging": False}

    def handle_motion(self, event):
        if not self.drag_data.get("item"): return
        
        # 一定以上動かしたらドラッグ開始とみなす
        if not self.drag_data["dragging"]:
            dx = abs(event.x - self.drag_data["x"])
            dy = abs(event.y - self.drag_data["y"])
            if dx > 5 or dy > 5:
                self.drag_data["dragging"] = True
                self.drag_data["ghost_id"] = self.canvas.create_rectangle(
                    0, 0, 0, 0, outline="#0078d7", width=2, dash=(4, 4), tags="ghost"
                )

        if self.drag_data["dragging"]:
            node = self.drag_data["item"]
            cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            w, h = node.width, node.height
            self.canvas.coords(self.drag_data["ghost_id"], cx - w/2, cy - h/2, cx + w/2, cy + h/2)

            # 移動先の影表示
            target_node = self.find_node_at(cx, cy)
            if target_node and target_node != node and not target_node.is_descendant_of(node) and target_node != node.parent:
                self.show_move_shadow(node, target_node)
            else:
                self.hide_move_shadow()

            self._handle_auto_scroll(event)

    def handle_drop(self, event):
        if not self.drag_data.get("dragging"):
            self.drag_data = {}
            return

        self.canvas.delete("ghost")
        self.hide_move_shadow()
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        target_node = self.find_node_at(cx, cy)
        dropped_node = self.drag_data["item"]
        
        if target_node and target_node != dropped_node and target_node != dropped_node.parent:
            if not target_node.is_descendant_of(dropped_node) and dropped_node != self.model.root:
                dropped_node.move_to(target_node)
                if target_node == self.model.root:
                    dropped_node.direction = self.model.get_balanced_direction(exclude_node=dropped_node)
                else:
                    dropped_node.direction = target_node.direction
                dropped_node.update_direction_recursive(dropped_node.direction)
                self.render_callback()
        
        self.drag_data = {}

    def _handle_auto_scroll(self, event):
        cv_w, cv_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        margin = 50
        self.drag_data["scroll_tick"] = self.drag_data.get("scroll_tick", 0) + 1
        if self.drag_data["scroll_tick"] % 5 == 0:
            if event.x < margin: self.canvas.xview_scroll(-1, "units")
            elif event.x > cv_w - margin: self.canvas.xview_scroll(1, "units")
            if event.y < margin: self.canvas.yview_scroll(-1, "units")
            elif event.y > cv_h - margin: self.canvas.yview_scroll(1, "units")

    def show_move_shadow(self, dragged_node: Node, target_node: Node):
        if self.drag_data.get("shadow_target_id") == target_node.id: return
        self.hide_move_shadow()
        
        h_margin = self.layout_engine.h_margin if hasattr(self.layout_engine, 'h_margin') else 80
        spacing_y = self.layout_engine.spacing_y if hasattr(self.layout_engine, 'spacing_y') else 30

        if target_node == self.model.root:
            direction = self.model.get_balanced_direction(exclude_node=dragged_node)
        else:
            direction = target_node.direction

        if direction == 'left':
            sx = target_node.x - target_node.width/2 - h_margin - dragged_node.width/2
        else:
            sx = target_node.x + target_node.width/2 + h_margin + dragged_node.width/2

        if target_node.children and not target_node.collapsed:
            last_child = max(target_node.children, key=lambda c: c.y)
            child_sh = getattr(last_child, 'subtree_height', last_child.height)
            dragged_sh = getattr(dragged_node, 'subtree_height', dragged_node.height)
            sy = last_child.y + child_sh/2 + spacing_y + dragged_sh/2
        else:
            sy = target_node.y

        temp_dir = dragged_node.direction
        dragged_node.direction = direction

        sw, sh = dragged_node.width, dragged_node.height
        shadow_id = self.canvas.create_rectangle(
            sx - sw/2, sy - sh/2, sx + sw/2, sy + sh/2,
            fill="#e0e0e0", outline="#cccccc", tags="move_shadow"
        )
        self.canvas.lower(shadow_id)
        
        tmp_x, tmp_y = dragged_node.x, dragged_node.y
        dragged_node.x, dragged_node.y = sx, sy
        
        self.graphics.draw_move_shadow_connection(target_node, dragged_node)
        
        dragged_node.x, dragged_node.y = tmp_x, tmp_y
        dragged_node.direction = temp_dir
        
        self.drag_data["shadow_target_id"] = target_node.id

    def hide_move_shadow(self):
        self.canvas.delete("move_shadow")
        self.drag_data["shadow_target_id"] = None
