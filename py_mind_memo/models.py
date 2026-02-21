import uuid
from typing import List, Optional

class Node:
    """マインドマップの単一のトピックを表すクラス"""
    def __init__(self, text: str, parent: Optional['Node'] = None):
        self.id = str(uuid.uuid4())
        self.text = text
        self.parent = parent
        self.children: List['Node'] = []
        self.direction = None  # 'left' or 'right' (主にルートの子ノードで使用)
        
        # UI表示用のプロパティ
        self.x = 0.0
        self.y = 0.0
        self.width = 100
        self.height = 40
        self.color = None
        self.collapsed = False

    def add_child(self, text: str, direction: Optional[str] = None) -> 'Node':
        child = Node(text, parent=self)
        if direction:
            child.direction = direction
        else:
            # 親の方向を継承
            child.direction = self.direction
        child.color = self.color # 親の色を継承
        self.children.append(child)
        return child

    def remove_child(self, node: 'Node'):
        if node in self.children:
            self.children.remove(node)

    def move_to(self, new_parent: 'Node'):
        """このノードを新しい親ノードの下に移動する"""
        if self.parent:
            self.parent.remove_child(self)
        self.parent = new_parent
        new_parent.children.append(self)
        self.color = new_parent.color # 移動した先の親の色を継承
        # 方向は新しい親の方向を引き継ぐか、ルート直下なら再計算が必要だが
        if new_parent.parent is None: # ルート直下への移動
             self.direction = None # 再計算させる
        else:
             self.direction = new_parent.direction
        
        # 移動先の親が折りたたまれている場合は展開する
        if new_parent.collapsed:
            new_parent.collapsed = False

    def update_direction_recursive(self, direction):
        """ノードとその子孫の方向を再帰的に更新"""
        self.direction = direction
        for child in self.children:
            child.update_direction_recursive(direction)

    def is_descendant_of(self, potential_ancestor):
        """このノードが指定したノードの子孫かどうかをチェック"""
        curr = self
        while curr:
            if curr == potential_ancestor:
                return True
            curr = curr.parent
        return False

    def to_dict(self) -> dict:
        """シリアライズ用の辞書変換"""
        return {
            "id": self.id,
            "text": self.text,
            "direction": self.direction,
            "color": self.color,
            "collapsed": self.collapsed,
            "children": [child.to_dict() for child in self.children]
        }

    @classmethod
    def from_dict(cls, data: dict, parent: Optional['Node'] = None) -> 'Node':
        """辞書からの復元"""
        node = cls(data["text"], parent=parent)
        node.id = data.get("id", str(uuid.uuid4()))
        node.direction = data.get("direction")
        node.color = data.get("color")
        node.collapsed = data.get("collapsed", False)
        for child_data in data.get("children", []):
            child = cls.from_dict(child_data, parent=node)
            node.children.append(child)
        return node

class MindMapModel:
    """マインドマップ全体を管理するモデル"""
    def __init__(self, root_text: str = "Root Topic"):
        self.root = Node(root_text)
        self.is_modified = False

    def add_node(self, parent_node: Node, text: str = "New Topic") -> Node:
        """指定したノードに子ノードを追加する。ルート直下の場合は方向を自動調整する。"""
        direction = None
        if parent_node == self.root:
            direction = self.get_balanced_direction()
        
        node = parent_node.add_child(text, direction)
        self.is_modified = True
        return node

    def get_balanced_direction(self, exclude_node: Optional[Node] = None) -> str:
        """ルートの子ノードの左右バランスを考慮した方向を返す"""
        right_nodes = [c for c in self.root.children if c.direction != 'left' and c != exclude_node]
        left_nodes = [c for c in self.root.children if c.direction == 'left' and c != exclude_node]
        
        if len(right_nodes) <= len(left_nodes):
            return 'right'
        else:
            return 'left'

    def find_node_by_id(self, node_id: str, current: Optional[Node] = None) -> Optional[Node]:
        if current is None:
            current = self.root
        
        if current.id == node_id:
            return current
        
        for child in current.children:
            found = self.find_node_by_id(node_id, child)
            if found:
                return found
        return None

    def save(self) -> dict:
        return self.root.to_dict()

    def load(self, data: dict):
        self.root = Node.from_dict(data)
