"""应用入口模块"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.views.main_window import MainWindow

def main():
    """应用主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用图标和样式
    app.setWindowIcon(QIcon("resources/icons/app.svg"))
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 