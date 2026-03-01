import math
from typing import List, Tuple
from .models import Node, MindMapModel


def compute_root_child_angles(n: int) -> List[float]:
    """
    root topic の子トピック n 個を追加した後の各角度リストを返す。
    角度は真上=0°、時計回りを正とする。

    n=1〜4 はハードコード、n>=5 は Issue #9 の数式で計算する。
    各グループ内でのインデックスを m=1,2,... として使用する。
    """
    precomputed_angles = {
        1: [90.0],
        2: [60.0, 120.0],
        3: [60.0, 120.0, 240.0],
        4: [60.0, 120.0, 240.0, 300.0],
    }
    if n in precomputed_angles:
        return precomputed_angles[n]

    # n >= 5
    angles = []
    if n % 2 == 1:
        # 奇数
        right_side_count = (n + 1) // 2   # 先頭グループ（右側：0°〜180°）
        left_side_count = (n - 1) // 2  # 後半グループ（左側：180°〜360°）
        for m in range(1, right_side_count + 1):
            angles.append(m * 180.0 / (right_side_count + 1))
        for m in range(1, left_side_count + 1):
            angles.append(180.0 + m * 180.0 / (left_side_count + 1))
    else:
        # 偶数
        half = n // 2
        for m in range(1, half + 1):
            angles.append(m * 180.0 / (half + 1))
        for m in range(1, half + 1):
            angles.append(180.0 + m * 180.0 / (half + 1))

    return angles



class LayoutEngine:
    """マインドマップの配置計算を担当するクラス"""

    def __init__(self):
        self.h_margin = 80   # root topic と子トピック列の水平余白
        self.v_gap = 40      # （互換性のため残す）
        self.spacing_y = 30  # 垂直方向の最小間隔

    def calculate_subtree_height(self, node: Node, graphics):
        """そのノードを含むサブツリー全体の必要高さを計算・更新する"""
        font = graphics.root_font if node.parent is None else graphics.font
        node.width, node.height = graphics.get_text_size(node, font)

        if not node.children or node.collapsed:
            node.subtree_height = node.height
            return node.height

        total_height = sum(self.calculate_subtree_height(c, graphics) for c in node.children)
        total_height += self.spacing_y * (len(node.children) - 1)

        node.subtree_height = max(node.height, total_height)
        return node.subtree_height

    def apply_layout(self, model: MindMapModel, graphics, center_x, center_y):
        """全体のレイアウトを計算し、各ノードの座標を決定する"""
        root = model.root
        self.calculate_subtree_height(root, graphics)

        root.x = center_x
        root.y = center_y

        children = root.children
        n = len(children)
        if n == 0:
            return

        # 角度リストを取得（追加順に対応）
        angles = compute_root_child_angles(n)

        # 各子トピックのサイズを事前計算
        for child in children:
            child.width, child.height = graphics.get_text_size(child, graphics.font)

        # ── 角度で左右グループに振り分ける ──
        # 角度 0°〜180°  → 右側（direction='right'）
        # 角度 180°〜360° → 左側（direction='left'）
        # 同時に「上から下」の縦順を決めるため、角度の値で並べる
        #   右側: angle 昇順 → 小さい角度ほど画面上方
        #   左側: angle 降順 → 大きい角度（360°寄り）ほど画面上方

        right_pairs: List[Tuple[float, Node]] = []
        left_pairs: List[Tuple[float, Node]] = []

        for child, angle in zip(children, angles):
            if angle <= 180.0:
                right_pairs.append((angle, child))
                child.direction = 'right'
            else:
                left_pairs.append((angle, child))
                child.direction = 'left'
            child.update_direction_recursive(child.direction)

        # 縦並び順（上→下）に並べ直す
        right_pairs.sort(key=lambda t: t[0])          # 昇順
        left_pairs.sort(key=lambda t: t[0], reverse=True)  # 降順

        right_nodes = [c for _, c in right_pairs]
        left_nodes  = [c for _, c in left_pairs]

        # ── 固定 X 列を計算（root サイズ + 余白 + 子の半幅） ──
        root_half_w = root.width / 2 + 12  # draw_node の角丸矩形マージンと合わせる

        if right_nodes:
            max_hw = max(c.width / 2 for c in right_nodes)
            right_x = center_x + root_half_w + self.h_margin + max_hw
            self._layout_root_children(right_nodes, right_x, center_y, 'right')

        if left_nodes:
            max_hw = max(c.width / 2 for c in left_nodes)
            left_x = center_x - root_half_w - self.h_margin - max_hw
            self._layout_root_children(left_nodes, left_x, center_y, 'left')

    def get_simulated_root_drop_position(self, root: Node, new_node: Node) -> Tuple[float, float, str]:
        """root直下へのドロップ時のシミュレーション座標を移動前の状態で計算する"""
        old_children = [c for c in root.children if c != new_node]
        n_new = len(old_children) + 1
        new_angles = compute_root_child_angles(n_new)
        
        new_angle = new_angles[-1]
        new_direction = 'right' if new_angle <= 180.0 else 'left'
        
        group_pairs = []
        for child, angle in zip(old_children, new_angles[:-1]):
            group_dir = 'right' if angle <= 180.0 else 'left'
            if group_dir == new_direction:
                group_pairs.append((angle, child))
        group_pairs.append((new_angle, new_node))
        
        if new_direction == 'right':
            group_pairs.sort(key=lambda t: t[0])
        else:
            group_pairs.sort(key=lambda t: t[0], reverse=True)
            
        group_nodes = [node for _, node in group_pairs]
        new_node_idx = group_nodes.index(new_node)
        
        node_above = None
        for i in range(new_node_idx - 1, -1, -1):
            n = group_nodes[i]
            if getattr(n, 'direction', None) == new_direction:
                node_above = n
                break
                
        node_below = None
        for i in range(new_node_idx + 1, len(group_nodes)):
            n = group_nodes[i]
            if getattr(n, 'direction', None) == new_direction:
                node_below = n
                break

        new_h = getattr(new_node, 'subtree_height', new_node.height)
        
        if node_above:
            ref_y = node_above.y
            ref_h = getattr(node_above, 'subtree_height', node_above.height)
            target_y = ref_y + ref_h / 2 + self.spacing_y + new_h / 2
        elif node_below:
            ref_y = node_below.y
            ref_h = getattr(node_below, 'subtree_height', node_below.height)
            target_y = ref_y - ref_h / 2 - self.spacing_y - new_h / 2
        else:
            target_y = root.y
            
        root_half_w = root.width / 2 + 12
        max_hw = getattr(new_node, 'width', 0) / 2
        old_nodes_on_side = [c for c in old_children if getattr(c, 'direction', None) == new_direction]
        if old_nodes_on_side:
            max_hw = max(max_hw, max(getattr(n, 'width', 0) / 2 for n in old_nodes_on_side))
            
        if new_direction == 'right':
            target_x = root.x + root_half_w + self.h_margin + max_hw
        else:
            target_x = root.x - root_half_w - self.h_margin - max_hw
            
        return target_x, target_y, new_direction

    def get_simulated_child_drop_position(self, target_node: Node, new_node: Node) -> Tuple[float, float, str]:
        """root以外の子ノードへのドロップ時のシミュレーション座標を計算する"""
        direction = target_node.direction
        if direction == 'left':
            target_x = target_node.x - target_node.width/2 - self.h_margin - new_node.width/2
        else:
            target_x = target_node.x + target_node.width/2 + self.h_margin + new_node.width/2

        if target_node.children and not target_node.collapsed:
            last_child = max(target_node.children, key=lambda c: c.y)
            child_sh = getattr(last_child, 'subtree_height', last_child.height)
            dragged_sh = getattr(new_node, 'subtree_height', new_node.height)
            target_y = last_child.y + child_sh/2 + self.spacing_y + dragged_sh/2
        else:
            target_y = target_node.y

        return target_x, target_y, direction

    # ──────────────────────────────────────────────────────────────
    # root 直下子ノードの縦方向配置
    # ──────────────────────────────────────────────────────────────

    def _layout_root_children(self, nodes: List[Node], child_x: float,
                               center_y: float, direction: str):
        """root 直下の子ノードを固定 X 列・縦方向に等間隔で配置する。"""
        total_height = (sum(n.subtree_height for n in nodes)
                        + self.spacing_y * (len(nodes) - 1))
        current_y = center_y - total_height / 2

        for node in nodes:
            node.x = child_x
            node.y = current_y + node.subtree_height / 2

            if node.children and not node.collapsed:
                self._layout_branch(node.children, node.x, node.y, direction)

            current_y += node.subtree_height + self.spacing_y

    # ──────────────────────────────────────────────────────────────
    # 孫以降のサブツリー配置（従来ロジック）
    # ──────────────────────────────────────────────────────────────

    def _get_group_height(self, nodes: List[Node]) -> float:
        if not nodes:
            return 0
        return sum(n.subtree_height for n in nodes) + self.spacing_y * (len(nodes) - 1)

    def _layout_branch(self, nodes: List[Node], parent_x: float,
                        start_y: float, direction: str):
        if not nodes:
            return

        total_height = (sum(n.subtree_height for n in nodes)
                        + self.spacing_y * (len(nodes) - 1))
        current_y = start_y - total_height / 2

        for node in nodes:
            p = node.parent
            if direction == 'right':
                node.x = p.x + p.width / 2 + self.h_margin + node.width / 2
            else:
                node.x = p.x - p.width / 2 - self.h_margin - node.width / 2

            node.y = current_y + node.subtree_height / 2

            if node.children and not node.collapsed:
                self._layout_branch(node.children, node.x, node.y, direction)

            current_y += node.subtree_height + self.spacing_y
