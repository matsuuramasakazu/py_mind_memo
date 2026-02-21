from .models import Node

class KeyboardNavigator:
    """キーボードによるノード間移動を管理するクラス"""
    def __init__(self, model, render_callback):
        self.model = model
        self.render_callback = render_callback

    def navigate(self, current_node, direction):
        """左右対称レイアウトに対応したナビゲーション"""
        curr = current_node
        new_node = curr
        
        if direction == "right":
            if curr == self.model.root:
                right_children = [c for c in curr.children if c.direction != 'left']
                if right_children: new_node = right_children[0]
            elif curr.direction != 'left':
                if curr.children: new_node = curr.children[0]
            else:
                if curr.parent: new_node = curr.parent
        elif direction == "left":
            if curr == self.model.root:
                left_children = [c for c in curr.children if c.direction == 'left']
                if left_children: new_node = left_children[0]
            elif curr.direction == 'left':
                if curr.children: new_node = curr.children[0]
            else:
                if curr.parent: new_node = curr.parent
        elif direction in ("up", "down") and curr.parent:
            siblings = [c for c in curr.parent.children if c.direction == curr.direction]
            if not siblings: siblings = curr.parent.children
            
            if curr.parent == self.model.root:
                def get_y_rank(node):
                    side_siblings = [c for c in curr.parent.children if c.direction == node.direction]
                    try:
                        side_idx = side_siblings.index(node)
                        point_type = side_idx % 3
                        y_rank = 0 if point_type == 0 else (1 if point_type == 2 else 2)
                        return (y_rank, side_idx // 3)
                    except ValueError: return (0, 0)
                siblings.sort(key=get_y_rank)
            
            try:
                idx = siblings.index(curr)
                if direction == "up" and idx > 0: new_node = siblings[idx-1]
                elif direction == "down" and idx < len(siblings) - 1: new_node = siblings[idx+1]
            except ValueError: pass
                
        return new_node
