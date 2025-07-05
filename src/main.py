#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主程序入口。
"""

import sys
import asyncio
import qasync
from PySide6.QtGui import QIcon  # 先导入 QtGui
from PySide6.QtCore import QTranslator, QLocale
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from src.views.main_window import MainWindow
from src.viewmodels.main_viewmodel import MainViewModel

async def main() -> None:
    """应用程序主入口"""
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 设置国际化
    translator = QTranslator()
    if translator.load(QLocale(), "", "", "translations"):
        app.installTranslator(translator)
    
    # 创建主窗口和视图模型
    window = MainWindow()
    viewmodel = MainViewModel()
    
    # 连接信号
    window.download_requested.connect(viewmodel.start_download)
    window.path_changed.connect(viewmodel.update_download_path)
    viewmodel.download_progress.connect(
        lambda vid, prog: window.add_download_task(vid)[0].setValue(prog)
    )
    viewmodel.download_speed.connect(window.update_speed)
    
    # 显示主窗口
    window.show()
    
    # 运行事件循环
    await qasync.QApplication.instance().exec()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        sys.exit(0) 