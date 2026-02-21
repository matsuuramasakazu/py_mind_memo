import tkinter as tk
from .view import MindMapView

def main():
    root = tk.Tk()
    root.geometry("1000x800")
    app = MindMapView(root)
    root.mainloop()

if __name__ == "__main__":
    main()
