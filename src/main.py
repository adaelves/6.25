#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""应用程序入口模块。"""

import sys
import os
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 配置日志
def setup_logging() -> None:
    """配置日志系统。"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def main() -> None:
    """应用程序入口函数。"""
    # 确保在项目根目录下运行
    os.chdir(PROJECT_ROOT)
    
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"应用程序启动，工作目录：{PROJECT_ROOT}")
    
    # 打印诊断信息
    logger.info(f"Python 路径：{sys.path}")
    logger.info(f"__file__: {__file__}")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 