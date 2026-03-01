import base64
import math
import os

from .constants import MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT

def file_to_base64(file_path: str) -> str:
    """ファイルを読み込み、Base64エンコードされた文字列を返す"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image file not found: {file_path}")
    
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        raise IOError(f"Failed to read image file: {e}")

def calculate_subsample(width: int, height: int, max_width: int = MAX_IMAGE_WIDTH, max_height: int = MAX_IMAGE_HEIGHT) -> int:
    """指定されたサイズに収まるように最小の整数サンプリングレートを計算する"""
    if width <= max_width and height <= max_height:
        return 1
    
    # 幅と高さの比率を計算（より明確に math.ceil を使用）
    sample_x = math.ceil(width / max_width)
    sample_y = math.ceil(height / max_height)
    
    # 大きい方の比率をサンプリングレートとして採用
    return max(sample_x, sample_y)

def load_image_as_base64(file_path: str) -> str:
    """画像を読み込み、Base64エンコードされた文字列を返す。
    ※現在はBase64変換のみを行う（subsampleはメモリ上のPhotoImageに対して行うため）。
    """
    return file_to_base64(file_path)
