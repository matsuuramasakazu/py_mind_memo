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
    if n == 1:
        return [90.0]
    if n == 2:
        return [60.0, 120.0]
    if n == 3:
        return [60.0, 120.0, 240.0]
    if n == 4:
        return [60.0, 120.0, 240.0, 300.0]

    # n >= 5
    angles = []
    if n % 2 == 1:
        # 奇数
        left_count = (n + 1) // 2   # 先頭グループ（左側：0°〜180°）
        right_count = (n - 1) // 2  # 後半グループ（右側：180°〜360°）
        for m in range(1, left_count + 1):
            angles.append(m * 180.0 / (left_count + 1))
        for m in range(1, right_count + 1):
            angles.append(180.0 + m * 180.0 / (right_count + 1))
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
        self.h_margin = 80   # ルート子トピックと root topic 間の最小余白
        self.v_gap = 40      # （互換性のため残す）
        self.spacing_y = 30  # 垂直方向の最小間隔（孫以降のサブツリー用）

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
            font = graphics.font
            child.width, child.height = graphics.get_text_size(child, font)

        # 配置半径を root topic サイズと子トピックサイズから動的に決定
        # root topic の外縁 + h_margin + 最大の子の半幅 を確保する
        max_child_half_w = max(c.width / 2 for c in children) if children else 0
        max_child_half_h = max(c.height / 2 for c in children) if children else 0
        root_half_w = root.width / 2 + 12  # draw_node の角丸矩形マージンと合わせる
        root_half_h = root.height / 2 + 10

        # 直接の衝突を避けるため、どの方向でも root topic の輪郭から h_margin 離れた位置に子を置く
        # 半径は root のサイズを考慮して各軸で計算し大きい方を取る
        radius_x = root_half_w + self.h_margin + max_child_half_w
        radius_y = root_half_h + self.h_margin + max_child_half_h
        # 楕円的な配置にならないよう大きい方で統一
        radius = max(radius_x, radius_y)

        for child, angle_deg in zip(children, angles):
            angle_rad = math.radians(angle_deg)
            # 真上=0°、時計回り → x=sin, y=-cos
            child.x = center_x + radius * math.sin(angle_rad)
            child.y = center_y - radius * math.cos(angle_rad)

            # direction を左右で設定（collapse_icon 描画や drag_drop との互換性のため）
            # 角度 0°〜180° → 右側、180°〜360° → 左側
            if angle_deg <= 180.0:
                child.direction = 'right'
            else:
                child.direction = 'left'
            # 子孫にも方向を伝播
            child.update_direction_recursive(child.direction)

            # 孫以降のサブツリーを従来の縦方向レイアウトで配置
            if child.children and not child.collapsed:
                self._layout_branch(child.children, child.x, child.y, child.direction)

    # ──────────────────────────────────────────────
    # 孫以降のサブツリー配置（従来ロジックをそのまま維持）
    # ──────────────────────────────────────────────

    def _get_group_height(self, nodes: List[Node]) -> float:
        if not nodes:
            return 0
        return sum(n.subtree_height for n in nodes) + self.spacing_y * (len(nodes) - 1)

    def _layout_branch(self, nodes, parent_x, start_y, direction):
        if not nodes:
            return

        total_height = sum(n.subtree_height for n in nodes) + self.spacing_y * (len(nodes) - 1)
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
