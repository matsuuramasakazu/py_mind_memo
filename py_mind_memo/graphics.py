import tkinter as tk
import tkinter.font as tkfont
import base64
import re
import hashlib
from typing import Dict
from .models import Node, Reference
from .constants import (
    COLOR_TEXT, COLOR_ROOT_OUTLINE, COLOR_ROOT_FILL,
    COLOR_HIGHLIGHT_FILL, COLOR_HIGHLIGHT_OUTLINE,
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_ROOT,
    BRANCH_COLORS, IMAGE_SPACING
)

class GraphicsEngine:
    """tkinter.Canvas上での描画を管理するクラス"""
    
    # マークアップ解析用の正規表現パターン（再コンパイルを防ぐためクラス定数化）
    MARKUP_PATTERN = re.compile(r'(<br/?>|<b>|</b>|<i>|</i>|<u>|</u>|<c:#[0-9a-fA-F]{6}>|</c>)')

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.node_items: Dict[str, list] = {}  # node_id -> list of item ids
        self.text_items: Dict[str, int] = {} 
        self.line_items: Dict[str, list] = {} 
        self.image_items: Dict[str, int] = {}
        self.reference_items: Dict[str, list] = {} # ref_id -> list of item ids (line and handles)
        self.image_cache: Dict[str, tk.PhotoImage] = {}  # GC防止用のキャッシュ
        
        # 定数
        self.BEZIER_STEPS = 15
        self.TAPERED_BEZIER_STEPS = 30
        
        # デザイン設定
        self.text_color = COLOR_TEXT
        self.root_outline = COLOR_ROOT_OUTLINE
        self.font = (FONT_FAMILY, FONT_SIZE_NORMAL)
        self.root_font = (FONT_FAMILY, FONT_SIZE_ROOT, "bold")
        
        self.branch_colors = BRANCH_COLORS

    def _get_node_color(self, node: Node):
        """ノードの系統色を取得（ルートの子ノードに基づき決定）"""
        if node.parent is None:
            return self.root_outline
        
        # ルートの何番目の子孫か
        curr = node
        while curr.parent and curr.parent.parent:
            curr = curr.parent
        
        if curr.parent is None: return self.root_outline
        
        try:
            idx = curr.parent.children.index(curr)
            return self.branch_colors[idx % len(self.branch_colors)]
        except ValueError:
            return self.branch_colors[0]

    def _create_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return self.canvas.create_polygon(points, **kwargs, smooth=True)

    def _parse_markup(self, text: str):
        """
        マークアップ解析してセグメントのリストを返す。
        セグメントは (text, font_style, underline, color) のリスト。
        """
        parts = self.MARKUP_PATTERN.split(text)
        
        segments = []
        current_bold = False
        current_italic = False
        current_underline = False
        current_color = self.text_color
        
        color_stack = []
        
        for part in parts:
            if not part: continue
            
            if part == "<b>": current_bold = True
            elif part == "</b>": current_bold = False
            elif part == "<i>": current_italic = True
            elif part == "</i>": current_italic = False
            elif part == "<u>": current_underline = True
            elif part == "</u>": current_underline = False
            elif part.startswith("<c:"):
                color_stack.append(current_color)
                current_color = part[3:-1]
            elif part == "</c>":
                if color_stack: current_color = color_stack.pop()
                else: current_color = self.text_color
            elif part in ("<br>", "<br/>"):
                segments.append(("\n", "normal", False, current_color))
            else:
                # テキスト部分
                style = []
                if current_bold: style.append("bold")
                if current_italic: style.append("italic")
                font_style = " ".join(style) if style else "normal"
                segments.append((part, font_style, current_underline, current_color))
        
        return segments

    def _wrap_rich_text(self, text: str, base_font, max_width: int):
        """
        リッチテキストを指定された幅で折り返す。
        戻り値は行のリスト。各行はセグメント (text, font_style, underline, color) のリスト。
        """
        paragraphs = text.split("\n")
        all_wrapped_lines = []
        
        family = base_font[0]
        size = base_font[1]
        
        # フォントオブジェクトのキャッシュ（パフォーマンス向上用）
        font_cache = {}

        def get_font(style):
            if style not in font_cache:
                font_tuple = (family, size, style) if style != "normal" else (family, size)
                font_cache[style] = tkfont.Font(family=family, size=size, weight="bold" if "bold" in style else "normal", slant="italic" if "italic" in style else "roman")
            return font_cache[style]

        for p in paragraphs:
            segments = self._parse_markup(p)
            if not segments:
                all_wrapped_lines.append([])
                continue
                
            current_line_segments = []
            current_line_width = 0
            
            for txt, style, underline, color in segments:
                font_obj = get_font(style)
                
                # 文字単位で分割（日本語対応のため）
                # より高度にするなら単語単位が良いが、まずは確実な文字単位
                pending_txt = ""
                for char in txt:
                    char_w = font_obj.measure(char)
                    if current_line_width + char_w > max_width and current_line_segments or (current_line_width + char_w > max_width and pending_txt):
                        # 現在の行を確定
                        if pending_txt:
                            current_line_segments.append((pending_txt, style, underline, color))
                        all_wrapped_lines.append(current_line_segments)
                        current_line_segments = []
                        current_line_width = 0
                        pending_txt = ""
                    
                    pending_txt += char
                    current_line_width += char_w
                
                if pending_txt:
                    current_line_segments.append((pending_txt, style, underline, color))
            
            if current_line_segments:
                all_wrapped_lines.append(current_line_segments)
            elif not p: # 空行の場合
                all_wrapped_lines.append([])

        return all_wrapped_lines

    def get_text_size(self, node: Node, base_font, max_width: int = 250):
        """マルチラインとマークアップ、自動折り返しを考慮したサイズ計算（画像分も含む）"""
        # キャッシュチェック（テキストとフォント、画像データに変更がなければキャッシュを返す）
        font_key = f"{base_font[0]}_{base_font[1]}"
        # image_data 自体をキーに含めると重いため、blake2b でハッシュ化して衝突を防ぐ
        image_key = (
            hashlib.blake2b(node.image_data.encode("utf-8"), digest_size=12).hexdigest()
            if node.image_data else None
        )
        cache_key = (node.text, font_key, image_key)
        if hasattr(node, '_size_cache') and node._size_cache_key == cache_key:
            return node._size_cache

        wrapped_lines = self._wrap_rich_text(node.text, base_font, max_width)
        
        max_w = 0
        total_h = 0
        
        # 画像のサイズを取得
        img_w = 0
        img_h = 0
        if node.image_data:
            current_data_hash = hash(node.image_data)
            photo = None

            if node.id in self.image_cache:
                cached_photo, cached_data_hash = self.image_cache[node.id]
                if cached_data_hash == current_data_hash:
                    photo = cached_photo
            
            if photo is None:
                try:
                    photo = tk.PhotoImage(data=base64.b64decode(node.image_data))
                    self.image_cache[node.id] = (photo, current_data_hash)
                except Exception:
                    photo = None
            
            if photo:
                img_w = photo.width()
                img_h = photo.height() + IMAGE_SPACING # spacing
        
        family = base_font[0]
        size = base_font[1]
        
        # フォントオブジェクトのキャッシュ
        font_objs = {}
        def get_font_metrics(style):
            if style not in font_objs:
                f = tkfont.Font(family=family, size=size, 
                               weight="bold" if "bold" in style else "normal", 
                               slant="italic" if "italic" in style else "roman")
                font_objs[style] = f
            return font_objs[style]

        for line_segments in wrapped_lines:
            line_w = 0
            line_max_h = 0
            
            if not line_segments:
                total_h += size + 10
                continue

            for txt, style, underline, color in line_segments:
                f_obj = get_font_metrics(style)
                line_w += f_obj.measure(txt)
                # フォントの高さ（アセント+ディセント）をベースにする
                line_max_h = max(line_max_h, f_obj.metrics("linespace"))
            
            max_w = max(max_w, line_w)
            total_h += (line_max_h if line_max_h > 0 else size + 10)
            
        result = max(100, max(max_w + 20, img_w + 20)), max(35, total_h + 12 + img_h)
        # キャッシュに保存
        node._size_cache = result
        node._size_cache_key = cache_key
        return result


    def _draw_rich_text(self, x, y, node, base_font, tags):
        """リッチテキストを自動折り返しを考慮して描画する（画像対応）"""
        wrapped_lines = self._wrap_rich_text(node.text, base_font, 250)
        family = base_font[0]
        size = base_font[1]
        
        # 全体の高さを計算して開始Y座標を調整
        w, h = self.get_text_size(node, base_font)
        
        # 画像がある場合は先に描画
        img_h_offset = 0
        if node.image_data and node.id in self.image_cache:
            photo, _ = self.image_cache[node.id]
            img_h = photo.height()
            # 画像をテキストの上に描画
            img_tags = list(tags) + ["node_image"]
            img_id = self.canvas.create_image(x, y - h/2 + 10 + img_h/2, image=photo, tags=tuple(img_tags))
            self.image_items[node.id] = img_id
            img_h_offset = img_h + IMAGE_SPACING

        curr_y = y - h/2 + 10 + img_h_offset
        
        item_ids = []
        
        for line_segments in wrapped_lines:
            # 行の幅を計算して中央寄せの開始Xを決定
            line_w = 0
            temp_items = []
            
            if not line_segments:
                curr_y += size + 10
                continue

            for txt, style, underline, color in line_segments:
                font = (family, size, style) if style != "normal" else (family, size)
                tid = self.canvas.create_text(0, 0, text=txt, font=font)
                bbox = self.canvas.bbox(tid)
                self.canvas.delete(tid)
                if bbox:
                    line_w += (bbox[2] - bbox[0])
                    temp_items.append((txt, font, underline, color, bbox[2]-bbox[0], bbox[3]-bbox[1]))
            
            curr_x = x - line_w / 2
            max_line_h = 0
            
            for txt, font, underline, color, seg_w, seg_h in temp_items:
                # テキスト描画
                tid = self.canvas.create_text(
                    curr_x + seg_w/2, curr_y + seg_h/2,
                    text=txt, font=font, fill=color, tags=tags, anchor="center"
                )
                item_ids.append(tid)
                
                if underline:
                    # アンダーライン描画
                    lx1 = curr_x
                    lx2 = curr_x + seg_w
                    ly = curr_y + seg_h - 2
                    uid = self.canvas.create_line(lx1, ly, lx2, ly, fill=color, width=1, tags=tags)
                    item_ids.append(uid)
                
                curr_x += seg_w
                max_line_h = max(max_line_h, seg_h)
            
            curr_y += (max_line_h if max_line_h > 0 else size + 10)
            
        return item_ids

    def _calculate_bezier_points(self, p0, p1, p2, p3, steps):
        """ベジェ曲線の点列を計算する"""
        points = []
        def bz(t, v0, v1, v2, v3):
            return (1-t)**3 * v0 + 3*(1-t)**2 * t * v1 + 3*(1-t) * t**2 * v2 + t**3 * v3
        
        for i in range(steps + 1):
            t = i / steps
            x = bz(t, p0[0], p1[0], p2[0], p3[0])
            y = bz(t, p0[1], p1[1], p2[1], p3[1])
            points.append((x, y))
        return points

    def draw_node(self, node: Node, is_selected: bool = False):
        x, y = node.x, node.y
        is_root = node.parent is None
        font = self.root_font if is_root else self.font
        
        node.width, node.height = self.get_text_size(node, font)
        w, h = node.width, node.height
        
        if node.id in self.node_items:
            for item in self.node_items[node.id]: self.canvas.delete(item)
        if node.id in self.text_items:
            # 既に削除済み（node_itemsに含まれているため）
            pass
        if node.id in self.image_items:
            self.canvas.delete(self.image_items[node.id])
            del self.image_items[node.id]
        
        items = []
        color = self._get_node_color(node)
        
        # 選択状態の強調表示（背面に配置）
        if is_selected:
            # 淡いブルーのハイライトボックス
            p_h = 4
            highlight_id = self._create_rounded_rect(
                x - w/2 - 10, y - h/2 - p_h, x + w/2 + 10, y + h/2 + p_h,
                radius=6, fill=COLOR_HIGHLIGHT_FILL, outline=COLOR_HIGHLIGHT_OUTLINE, width=1, tags=("node", node.id)
            )
            items.append(highlight_id)

        if is_root:
            # ルートノード：太い枠線の角丸長方形
            outline_w = 4 if is_selected else 3
            fill_color = COLOR_ROOT_FILL if is_selected else "white"
            rect_id = self._create_rounded_rect(
                x - w/2 - 12, y - h/2 - 10, x + w/2 + 12, y + h/2 + 10,
                radius=10, fill=fill_color, outline=color, width=outline_w, tags=("node", node.id)
            )
            items.append(rect_id)
        else:
            # サブトピック：下線のみ
            line_y = y + h/2
            lx1, lx2 = x - w/2 - 5, x + w/2 + 5
            u_width = 3 if is_selected else 2
            underline_id = self.canvas.create_line(
                lx1, line_y, lx2, line_y, fill=color, width=u_width, tags=("node", node.id)
            )
            items.append(underline_id)

        self.node_items[node.id] = items
        
        # テキスト（リッチテキスト対応）
        text_item_ids = self._draw_rich_text(
            x, y, node, font, tags=("text", node.id)
        )
        self.text_items[node.id] = text_item_ids[0] if text_item_ids else None
        # 全てのアイテムを管理可能にするために node_items に追加
        self.node_items[node.id].extend(text_item_ids)
        
        if node.children and node.parent:
            self._draw_collapse_icon(node)
        
        if node.parent:
            self.draw_connection(node)

    def _get_connection_points(self, node: Node, parent: Node):
        """接続の開始点、制御点、終了点を計算する"""
        if parent.parent is None:
            return self._get_root_connection_points(node, parent)
        else:
            return self._get_subtree_connection_points(node, parent)

    def _get_root_connection_points(self, node: Node, parent: Node):
        """ルートからの接続点を計算。

        接続線の終点は、子トピックの下線のうち root topic に近い側の端点。
        root topic の矩形輪郭と、root中心から終点への方向ベクトルの交点を起点とする。
        """
        # 子トピック側の終点：root に近い側の下線端点
        # draw_node で引かれる下線は lx1=x-w/2-5, lx2=x+w/2+5
        if node.direction != 'left':
            # 右側の子 → 左端（root 寄り）
            nx = node.x - node.width / 2 - 5
        else:
            # 左側の子 → 右端（root 寄り）
            nx = node.x + node.width / 2 + 5
        ny = node.y + node.height / 2

        # root topic の矩形の半幅・半高（draw_node の角丸矩形マージンと合わせる）
        w_h = parent.width / 2 + 12
        h_h = parent.height / 2 + 10

        # root 中心 → 子トピック終点 の方向ベクトル
        dx = nx - parent.x
        dy = ny - parent.y

        # 矩形輪郭との交点を計算（クリッピング）
        px, py = self._calc_rect_edge_point(parent.x, parent.y, w_h, h_h, dx, dy)

        # 制御点（テーパードベジェ用：水平方向補間）
        ddx = nx - px
        cp1x, cp2x = px + ddx * 0.4, px + ddx * 0.6
        cp1y = cp2y = ny if abs(ny - py) > 1 else py

        return (px, py), (cp1x, cp1y), (cp2x, cp2y), (nx, ny), True  # is_tapered


    @staticmethod
    def _calc_rect_edge_point(cx: float, cy: float, w_h: float, h_h: float,
                              dx: float, dy: float):
        """
        中心 (cx, cy)、半幅 w_h、半高 h_h の矩形の輪郭上の点を返す。
        中心から (dx, dy) 方向ベクトルが矩形の辺と交わる点。
        dx=dy=0 の場合は中心をそのまま返す。
        """
        # 極端に小さい値による浮動小数点誤差を考慮 (epsilon = 1e-9)
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return cx, cy

        t_candidates = []
        # 右辺 (+x) / 左辺 (-x)
        if dx != 0:
            t = (w_h if dx > 0 else -w_h) / dx
            if t > 0:
                t_candidates.append(t)
        # 下辺 (+y) / 上辺 (-y)
        if dy != 0:
            t = (h_h if dy > 0 else -h_h) / dy
            if t > 0:
                t_candidates.append(t)

        t = min(t_candidates)
        return cx + dx * t, cy + dy * t


    def _get_subtree_connection_points(self, node: Node, parent: Node):
        """子トピック間の接続点を計算"""
        parent_dir = 'right' if node.x > parent.x else 'left'
        px = parent.x + parent.width/2 if parent_dir == 'right' else parent.x - parent.width/2
        py = parent.y + parent.height/2
        nx = node.x - node.width/2 if parent_dir == 'right' else node.x + node.width/2
        ny = node.y + node.height/2
        
        dx = nx - px
        cp1x, cp2x = px + dx * 0.4, px + dx * 0.6
        cp1y, cp2y = py, ny
        
        return (px, py), (cp1x, cp1y), (cp2x, cp2y), (nx, ny), False # not_tapered

    def draw_connection(self, node: Node):
        if not node.parent or node.parent.collapsed: return
        if node.id in self.line_items:
            for item in self.line_items[node.id]: self.canvas.delete(item)
        
        color = self._get_node_color(node)
        p1, cp1, cp2, p2, is_tapered = self._get_connection_points(node, node.parent)
        
        if is_tapered:
            items = self._draw_tapered_bezier(p1[0], p1[1], p2[0], p2[1], color, 8, 2)
        else:
            items = self._draw_bezier(p1[0], p1[1], cp1[0], cp1[1], cp2[0], cp2[1], p2[0], p2[1], color, 2)
        
        self.line_items[node.id] = items

    def draw_move_shadow_connection(self, parent_node: Node, shadow_node: Node):
        """移動先の影用の接続線を描画する"""
        color = "#cccccc"
        p1, cp1, cp2, p2, is_tapered = self._get_connection_points(shadow_node, parent_node)
        
        steps = 20
        points = self._calculate_bezier_points(p1, cp1, cp2, p2, steps)
        
        for i in range(len(points) - 1):
            t = i / steps
            width = (8 + (2 - 8) * t) if is_tapered else 2
            self.canvas.create_line(
                points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                fill=color, width=width, capstyle="round", tags="move_shadow"
            )

    def _draw_bezier(self, x1, y1, cp1x, cp1y, cp2x, cp2y, x2, y2, color, width, tags=None):
        steps = self.BEZIER_STEPS
        points = self._calculate_bezier_points((x1, y1), (cp1x, cp1y), (cp2x, cp2y), (x2, y2), steps)
        items = []
        for i in range(len(points) - 1):
            line_id = self.canvas.create_line(
                points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                fill=color, width=width, capstyle="round", tags=tags
            )
            items.append(line_id)
        return items

    def _draw_tapered_bezier(self, x1, y1, x2, y2, color, start_w, end_w, tags=None):
        steps = self.TAPERED_BEZIER_STEPS
        dx = x2 - x1
        cp1x, cp2x = x1 + dx * 0.4, x1 + dx * 0.6
        cp1y = cp2y = y2 if abs(y2 - y1) > 1 else y1
        
        points = self._calculate_bezier_points((x1, y1), (cp1x, cp1y), (cp2x, cp2y), (x2, y2), steps)
        items = []
        for i in range(len(points) - 1):
            t = i / steps
            w = start_w + (end_w - start_w) * t
            line_id = self.canvas.create_line(
                points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                fill=color, width=w, capstyle="round", tags=tags
            )
            items.append(line_id)
        return items

    def _draw_collapse_icon(self, node: Node):
        """折り畳み/展開用のアイコンを描画する"""
        # 実際には方向(direction)に基づいた方が正確
        if node.direction == 'left':
            x = node.x - node.width/2 - 10
        else:
            x = node.x + node.width/2 + 10
            
        y = node.y + node.height/2
        radius = 8
        
        color = self._get_node_color(node)
        
        # アイコンの円
        circle_id = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="white", outline=color, width=1, tags=("collapse_icon", node.id)
        )
        self.node_items[node.id].append(circle_id)
        
        if node.collapsed:
            # 折りたたみ中：子ノードの数を表示
            count = len(node.children)
            text_id = self.canvas.create_text(
                x, y, text=str(count), font=("Yu Gothic", 7), fill=color, tags=("collapse_icon", node.id)
            )
            self.node_items[node.id].append(text_id)
        else:
            # 展開中：マイナス記号を表示
            line_id = self.canvas.create_line(
                x - 4, y, x + 4, y, fill=color, width=1, tags=("collapse_icon", node.id)
            )
            self.node_items[node.id].append(line_id)

    def draw_reference(self, ref: Reference, source_node: Node, target_node: Node, is_selected: bool = False):
        if ref.id in self.reference_items:
            for item in self.reference_items[ref.id]: 
                self.canvas.delete(item)
        
        items = []
        
        source_y_center = source_node.y
        target_y_center = target_node.y
        
        if source_y_center >= target_y_center:
            # 接続元が下、接続先が上 -> 接続元上辺から接続先下辺
            sy = source_node.y - source_node.height / 2
            ty = target_node.y + target_node.height / 2
        else:
            # 接続元が上、接続先が下 -> 接続元下辺から接続先上辺
            sy = source_node.y + source_node.height / 2
            ty = target_node.y - target_node.height / 2
            
        sx = source_node.x
        tx = target_node.x
        
        # 制御点の計算
        if ref.cp1_x is not None and ref.cp1_y is not None:
            cp1x, cp1y = ref.cp1_x, ref.cp1_y
        else:
            cp1x, cp1y = sx, sy + (ty - sy) * 0.3
            
        if ref.cp2_x is not None and ref.cp2_y is not None:
            cp2x, cp2y = ref.cp2_x, ref.cp2_y
        else:
            cp2x, cp2y = tx, ty - (ty - sy) * 0.3
            
        # 参照線の描画
        line_id = self.canvas.create_line(
            sx, sy, cp1x, cp1y, cp2x, cp2y, tx, ty,
            smooth=True, dash=(8, 4), arrow=tk.LAST,
            fill="black", width=2, tags=("reference", ref.id)
        )
        items.append(line_id)
        
        # 選択時のハンドルとガイド線の描画
        if is_selected:
            g1 = self.canvas.create_line(sx, sy, cp1x, cp1y, fill="gray", dash=(2,2), tags=("reference_guide", ref.id))
            g2 = self.canvas.create_line(tx, ty, cp2x, cp2y, fill="gray", dash=(2,2), tags=("reference_guide", ref.id))
            items.extend([g1, g2])
            
            r = 4
            h1 = self.canvas.create_oval(
                cp1x - r, cp1y - r, cp1x + r, cp1y + r,
                fill="white", outline="blue", tags=("reference_handle", f"{ref.id}_cp1")
            )
            h2 = self.canvas.create_oval(
                cp2x - r, cp2y - r, cp2x + r, cp2y + r,
                fill="white", outline="blue", tags=("reference_handle", f"{ref.id}_cp2")
            )
            items.extend([h1, h2])
            
        self.reference_items[ref.id] = items

    def clear(self):
        self.canvas.delete("all")
        self.node_items.clear()
        self.text_items.clear()
        self.line_items.clear()
        self.reference_items.clear()
