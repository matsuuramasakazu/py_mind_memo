import base64

from .constants import MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT

def file_to_base64(file_path: str) -> str:
    """ファイルを読み込み、Base64エンコードされた文字列を返す"""
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def calculate_subsample(width: int, height: int, max_width: int = MAX_IMAGE_WIDTH, max_height: int = MAX_IMAGE_HEIGHT) -> int:
    """指定されたサイズに収まるように最小の整数サンプリングレートを計算する"""
    if width <= max_width and height <= max_height:
        return 1
    
    # 幅と高さの比率を計算（切り上げ相当の整数計算）
    sample_x = (width + max_width - 1) // max_width
    sample_y = (height + max_height - 1) // max_height
    
    # 大きい方の比率をサンプリングレートとして採用（どちらも上限に収めるため）
    return max(sample_x, sample_y)

def load_image_as_base64(file_path: str) -> str:
    """画像を読み込み、Base64エンコードされた文字列を返す。
    ※現在はBase64変換のみを行う（subsampleはメモリ上のPhotoImageに対して行うため）。
    """
    return file_to_base64(file_path)
