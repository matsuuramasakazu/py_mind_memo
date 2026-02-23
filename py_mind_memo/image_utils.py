import base64
import tkinter as tk

def file_to_base64(file_path: str) -> str:
    """ファイルを読み込み、Base64エンコードされた文字列を返す"""
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def calculate_subsample(width: int, height: int, max_width: int = 200, max_height: int = 200) -> int:
    """200x200に収まるように最小の整数サンプリングレートを計算する"""
    if width <= max_width and height <= max_height:
        return 1
    
    # 幅と高さの比率を計算（切り上げ相当の整数計算）
    sample_x = (width + max_width - 1) // max_width
    sample_y = (height + max_height - 1) // max_height
    
    # 大きい方の比率をサンプリングレートとして採用（どちらも上限に収めるため）
    return max(sample_x, sample_y)

def get_processed_image_data(file_path: str) -> str:
    """画像を読み込み、必要に応じて縮小（擬似）し、Base64で返す。
    ※tk.PhotoImage.subsampleはメモリ上のインスタンスに対して動作するため、
    ここではBase64文字列への変換のみを行う。
    """
    return file_to_base64(file_path)
