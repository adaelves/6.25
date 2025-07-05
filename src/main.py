"""主程序入口模块"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from src.views.main_window import MainWindow

def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    
    # 设置macOS风格调色板
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(245, 245, 247))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(255, 255, 255))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 