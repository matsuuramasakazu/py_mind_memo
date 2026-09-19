import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
from py_mind_memo.models import MindMapModel
from py_mind_memo.view import MindMapView
from py_mind_memo.graphics import GraphicsEngine
from py_mind_memo.constants import (
    FONT_FAMILY, FONT_SIZE_NORMAL, FONT_SIZE_ROOT,
    FONT_SIZE_MIN, FONT_SIZE_MAX, FONT_SIZE_STEP
)

class TestGraphicsFontSizes(unittest.TestCase):
    def test_set_font_sizes(self):
        """GraphicsEngine.set_font_sizes でフォントタプルが更新されること"""
        canvas = MagicMock(spec=tk.Canvas)
        graphics = GraphicsEngine(canvas)
        self.assertEqual(graphics.font, (FONT_FAMILY, FONT_SIZE_NORMAL))
        self.assertEqual(graphics.root_font, (FONT_FAMILY, FONT_SIZE_ROOT, "bold"))

        graphics.set_font_sizes(14, 16)
        self.assertEqual(graphics.font, (FONT_FAMILY, 14))
        self.assertEqual(graphics.root_font, (FONT_FAMILY, 16, "bold"))

    def test_measure_char_cache(self):
        """_measure_char が文字幅をキャッシュして重複計算を防ぐこと"""
        canvas = MagicMock(spec=tk.Canvas)
        graphics = GraphicsEngine(canvas)
        mock_font = MagicMock()
        mock_font.measure.return_value = 8

        w1 = graphics._measure_char(mock_font, "あ")
        w2 = graphics._measure_char(mock_font, "あ")

        self.assertEqual(w1, 8)
        self.assertEqual(w2, 8)
        # 2回呼ばれてもキャッシュにより measure は1回のみ実行される
        mock_font.measure.assert_called_once_with("あ")


class TestFontZoom(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw() # ウィンドウを表示しない
        self.patchers = [
            patch('py_mind_memo.view.GraphicsEngine'),
            patch('py_mind_memo.view.LayoutEngine'),
            patch('py_mind_memo.view.DragDropHandler'),
            patch('py_mind_memo.view.KeyboardNavigator'),
            patch('py_mind_memo.view.MindMapView._create_menu'),
            patch('py_mind_memo.view.MindMapView.render'),
        ]
        for p in self.patchers:
            p.start()

        self.view = MindMapView(self.root)
        self.view.render.reset_mock()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.root.destroy()

    def test_initial_font_size(self):
        """初期フォントサイズが FONT_SIZE_NORMAL (10pt) であること"""
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL)

    def test_zoom_in_via_wheel(self):
        """Ctrl+ホイール上回転でフォントサイズが拡大し、ステータス表示が即時更新され、デバウンスで描画されること"""
        event = MagicMock()
        event.delta = 120
        res = self.view.on_font_zoom_wheel(event)
        self.assertEqual(res, "break")
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL + 1)
        self.assertIn("11pt", self.view.status_bar.cget("text"))
        self.assertIsNotNone(self.view._font_render_timer)

        # デバウンスタイマー発火
        self.view._on_debounced_font_render()
        self.view.graphics.set_font_sizes.assert_called_with(
            FONT_SIZE_NORMAL + 1, FONT_SIZE_ROOT + 1
        )
        self.view.render.assert_called_once()

    def test_zoom_out_via_wheel(self):
        """Ctrl+ホイール下回転でフォントサイズが縮小すること"""
        event = MagicMock()
        event.delta = -120
        res = self.view.on_font_zoom_wheel(event)
        self.assertEqual(res, "break")
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL - 1)
        self.assertIn("9pt", self.view.status_bar.cget("text"))

        # デバウンスタイマー発火
        self.view._on_debounced_font_render()
        self.view.graphics.set_font_sizes.assert_called_with(
            FONT_SIZE_NORMAL - 1, FONT_SIZE_ROOT - 1
        )
        self.view.render.assert_called_once()

    def test_zoom_in_out_linux_events(self):
        """Linux環境の Button-4/Button-5 イベントで拡大・縮小できること"""
        self.view.on_font_zoom_in(None)
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL + 1)
        self.view.on_font_zoom_out(None)
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL)

    def test_zoom_min_limit(self):
        """下限リミット (FONT_SIZE_MIN=6pt) 未満にならないこと"""
        self.view.current_font_size = FONT_SIZE_MIN
        self.view.render.reset_mock()
        self.view.change_font_size(-1)
        self.assertEqual(self.view.current_font_size, FONT_SIZE_MIN)
        self.assertIsNone(self.view._font_render_timer)

    def test_zoom_max_limit(self):
        """上限リミット (FONT_SIZE_MAX=32pt) を超えないこと"""
        self.view.current_font_size = FONT_SIZE_MAX
        self.view.render.reset_mock()
        self.view.change_font_size(1)
        self.assertEqual(self.view.current_font_size, FONT_SIZE_MAX)
        self.assertIsNone(self.view._font_render_timer)

    def test_reset_font_size(self):
        """Ctrl+0 で初期サイズに即時リセットされ、ステータスに「初期値」と表示されること"""
        # まず拡大
        self.view.change_font_size(3)
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL + 3)

        # リセット（即座にrenderが走る）
        self.view.render.reset_mock()
        res = self.view.on_font_zoom_reset(None)
        self.assertEqual(res, "break")
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL)
        self.view.render.assert_called_once()
        self.assertIn("(初期値)", self.view.status_bar.cget("text"))

    def test_reset_font_size_already_normal(self):
        """既に初期サイズの場合はリセット時に再描画されないこと"""
        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL)
        self.view.render.reset_mock()
        self.view.on_font_zoom_reset(None)
        self.view.render.assert_not_called()

    def test_editor_font_update_when_editing(self):
        """編集中にフォントサイズが適用された場合、editor.update_font が呼ばれ、render() は呼ばれないこと"""
        self.view.editor = MagicMock()
        self.view.editor.is_editing.return_value = True
        self.view.render.reset_mock()

        self.view.change_font_size(1)
        self.view._on_debounced_font_render()

        self.view.editor.update_font.assert_called_once()
        self.view.render.assert_not_called()

    def test_model_not_modified_and_no_history(self):
        """フォントサイズ変更はモデルやUndo履歴（スナップショット）に影響を与えないこと"""
        initial_modified = self.view.model.is_modified
        can_undo_before = self.view.history.can_undo()

        self.view.change_font_size(2)
        self.view._on_debounced_font_render()

        self.assertEqual(self.view.model.is_modified, initial_modified)
        self.assertEqual(self.view.history.can_undo(), can_undo_before)

    def test_font_render_debouncing(self):
        """連続ホイール操作中は再描画が遅延され、最後に1回だけ再描画されること"""
        self.view.render.reset_mock()

        # 連続して5回ホイール操作
        for _ in range(5):
            self.view.change_font_size(1)

        self.assertEqual(self.view.current_font_size, FONT_SIZE_NORMAL + 5)
        # 操作中は render() は一切実行されていない
        self.assertEqual(self.view.render.call_count, 0)
        self.assertIsNotNone(self.view._font_render_timer)

        # デバウンスタイマー満了で1回だけ実行
        self.view._on_debounced_font_render()
        self.assertEqual(self.view.render.call_count, 1)
        self.view.graphics.set_font_sizes.assert_called_with(
            FONT_SIZE_NORMAL + 5, FONT_SIZE_ROOT + 5
        )

class TestNodeEditorFontUpdate(unittest.TestCase):
    def test_update_font_applies_current_graphics_font(self):
        """NodeEditor.update_font で編集中ウィジェットのフォントが更新されること"""
        from py_mind_memo.editor import NodeEditor
        from py_mind_memo.models import Node

        root = MagicMock(spec=tk.Tk)
        canvas = MagicMock(spec=tk.Canvas)
        model = MagicMock(spec=MindMapModel)
        graphics = MagicMock()
        graphics.font = (FONT_FAMILY, 14)
        graphics.root_font = (FONT_FAMILY, 16, "bold")

        editor = NodeEditor(canvas, root, graphics, on_finish=MagicMock(), model=model)

        # 子ノードの編集中の場合
        parent_node = Node("Parent")
        child_node = Node("Child", parent=parent_node)
        editor.editing_node = child_node
        editor.editing_entry = MagicMock()
        editor.update_font()
        editor.editing_entry.config.assert_called_with(font=(FONT_FAMILY, 14))

        # ルートノードの編集中の場合
        root_node = Node("Root", parent=None)
        editor.editing_node = root_node
        editor.editing_entry = MagicMock()
        editor.update_font()
        editor.editing_entry.config.assert_called_with(font=(FONT_FAMILY, 16, "bold"))


if __name__ == '__main__':
    unittest.main()
