from typing import List, Tuple
from .models import Node, MindMapModel

class LayoutEngine:
    """マインドマップの配置計算を担当するクラス"""
    
    def __init__(self):
        self.h_margin = 80  # 横方向の余白
        self.v_gap = 40     # グループ間の垂直方向の最小隙間
        self.spacing_y = 30 # 垂直方向の最小間隔

    def calculate_subtree_height(self, node: Node, graphics):
        """そのノードを含むサブツリー全体の必要高さを計算・更新する"""
        font = graphics.root_font if node.parent is None else graphics.font
        node.width, node.height = graphics.get_text_size(node.text, font)
        
        if not node.children or node.collapsed:
            node.subtree_height = node.height
            return node.height
            
        total_height = sum(self.calculate_subtree_height(c, graphics) for c in node.children)
        total_height += self.spacing_y * (len(node.children) - 1)
        
        # サブツリーの高さは、自身の高さか子の合計か高い方（余白含む）
        node.subtree_height = max(node.height, total_height)
        return node.subtree_height

    def apply_layout(self, model: MindMapModel, graphics, center_x, center_y):
        """全体のレイアウトを計算し、各ノードの座標を決定する"""
        root = model.root
        self.calculate_subtree_height(root, graphics)
        
        root.x = center_x
        root.y = center_y
        
        # ルートの子ノードを左右に分ける
        right_all = [c for c in root.children if c.direction != 'left']
        left_all = [c for c in root.children if c.direction == 'left']
        
        r_groups = self._group_and_sort(right_all)
        l_groups = self._group_and_sort(left_all)
        
        # --- 配置の実行 ---
        # 各サイド（右・左）において、中央グループが膨らんだ場合に上下を適切に押し出す
        for side, groups in [('right', r_groups), ('left', l_groups)]:
            h_mid = self._get_group_height(groups[2])
            mid_boundary = max(root.height / 2, h_mid / 2)
            
            # 1. 中央セクター
            if groups[2]:
                self._layout_branch(groups[2], center_x, center_y, side)
            
            # 2. 上部セクター
            if groups[0]:
                h_top = self._get_group_height(groups[0])
                # 中央境界よりさらに上に配置
                start_y_top = center_y - mid_boundary - self.v_gap - h_top/2
                self._layout_branch(groups[0], center_x, start_y_top, side)
                
            # 3. 下部セクター
            if groups[1]:
                h_btm = self._get_group_height(groups[1])
                # 中央境界よりさらに下に配置
                start_y_btm = center_y + mid_boundary + self.v_gap + h_btm/2
                self._layout_branch(groups[1], center_x, start_y_btm, side)

    def _group_and_sort(self, nodes: List[Node]) -> dict:
        """ルート直下の子ノードを上下中の3つのグループに分ける"""
        # 0:上, 1:下, 2:中
        groups = {0: [], 1: [], 2: []}
        for i, n in enumerate(nodes):
            # サイド内のインデックスに基づいて3つのセクター（上・下・中）に振り分ける
            groups[i % 3].append(n)
        return groups

    def _get_group_height(self, nodes: List[Node]) -> float:
        if not nodes: return 0
        return sum(n.subtree_height for n in nodes) + self.spacing_y * (len(nodes) - 1)

    def _layout_branch(self, nodes, parent_x, start_y, direction):
        if not nodes:
            return
            
        total_height = sum(n.subtree_height for n in nodes) + self.spacing_y * (len(nodes) - 1)
        current_y = start_y - total_height / 2
        
        for node in nodes:
            # 水平位置の決定: 親の端から一定距離離れた場所に配置
            p = node.parent
            if direction == 'right':
                node.x = p.x + p.width/2 + self.h_margin + node.width/2
            else:
                node.x = p.x - p.width/2 - self.h_margin - node.width/2
                
            node.y = current_y + node.subtree_height / 2
            
            # 孫以降の再帰配置
            if node.children and not node.collapsed:
                self._layout_branch(node.children, node.x, node.y, direction)
            
            current_y += node.subtree_height + self.spacing_y
