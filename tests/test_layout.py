import unittest
from py_mind_memo.layout import compute_root_child_angles


class TestComputeRootChildAngles(unittest.TestCase):
    """compute_root_child_angles(n) の角度計算ロジックを検証する。
    
    Issue #9 に記載された具体例を基準値として使用する。
    """

    def _assert_angles(self, n, expected, places=1):
        """角度リストを小数第1位まで比較するヘルパー"""
        result = compute_root_child_angles(n)
        self.assertEqual(
            len(result), len(expected),
            f"n={n}: 要素数が違います。expected={len(expected)}, got={len(result)}"
        )
        for i, (r, e) in enumerate(zip(result, expected)):
            self.assertAlmostEqual(
                r, e, places=places,
                msg=f"n={n}, index={i}: expected {e}°, got {r:.2f}°"
            )

    def test_n1(self):
        self._assert_angles(1, [90.0])

    def test_n2(self):
        self._assert_angles(2, [60.0, 120.0])

    def test_n3(self):
        self._assert_angles(3, [60.0, 120.0, 240.0])

    def test_n4(self):
        self._assert_angles(4, [60.0, 120.0, 240.0, 300.0])

    def test_n5(self):
        # Issue本文の具体例: 45°, 90°, 135°, 240°, 300°
        self._assert_angles(5, [45.0, 90.0, 135.0, 240.0, 300.0])

    def test_n6(self):
        # Issue本文の具体例: 45°, 90°, 135°, 225°, 270°, 315°
        self._assert_angles(6, [45.0, 90.0, 135.0, 225.0, 270.0, 315.0])

    def test_n7(self):
        # Issue本文の具体例: 36°, 72°, 108°, 144°, 225°, 270°, 315°
        self._assert_angles(7, [36.0, 72.0, 108.0, 144.0, 225.0, 270.0, 315.0])

    def test_returns_correct_count(self):
        """compute_root_child_angles は常に n 個の要素を返す"""
        for n in range(1, 15):
            result = compute_root_child_angles(n)
            self.assertEqual(len(result), n, f"n={n}: 要素数が一致しません")

    def test_angles_in_valid_range(self):
        """すべての角度が 0° < angle <= 360° の範囲に収まること"""
        for n in range(1, 15):
            for angle in compute_root_child_angles(n):
                self.assertGreater(angle, 0.0, f"n={n}: 角度 {angle}° が 0 以下")
                self.assertLessEqual(angle, 360.0, f"n={n}: 角度 {angle}° が 360 超")


if __name__ == '__main__':
    unittest.main()
