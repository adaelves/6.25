#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主程序入口。
"""

import os
import sys
import logging
from pathlib import Path

# 将项目根目录添加到Python路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.core.download_scheduler import DownloadScheduler
from src.core.settings import Settings
from src.core.cookie_manager import CookieManager

def setup_logging():
    """配置日志。"""
    log_dir = ROOT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                log_dir / "app.log",
                encoding="utf-8"
            )
        ]
    )

def main():
    """程序入口函数。"""
    # 配置日志
    setup_logging()
    
    # 创建应用程序
    app = QApplication(sys.argv)
    
    # 初始化设置
    settings = Settings()
    
    # 初始化 Cookie 管理器
    cookie_manager = CookieManager()
    
    # 初始化下载调度器
    scheduler = DownloadScheduler(
        max_concurrent=settings.get("download.max_concurrent", 3),
        max_retries=settings.get("download.max_retries", 3),
        default_timeout=settings.get("download.timeout", 30),
        cache_dir=ROOT_DIR / "cache",
        cookie_manager=cookie_manager
    )
    
    # 创建主窗口
    window = MainWindow(
        scheduler=scheduler,
        settings=settings
    )
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 