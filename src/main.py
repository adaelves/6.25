#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主程序入口。
"""

import os
import sys
from pathlib import Path

# 将项目根目录添加到Python路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.gui.main_window import MainWindow
from PySide6.QtWidgets import QApplication

def main():
    """程序入口函数。"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 