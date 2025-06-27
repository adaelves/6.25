#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""应用程序入口模块。"""

import sys
import os
import logging
import json
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from plugins.twitter.downloader import TwitterDownloader
from plugins.twitter.config import TwitterDownloaderConfig
from utils.cookie_manager import CookieManager

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

def load_config() -> Dict[str, Any]:
    """加载配置文件。
    
    Returns:
        Dict[str, Any]: 配置字典
    """
    config_path = PROJECT_ROOT / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def download_twitter(url: str, progress_callback=None) -> Dict[str, Any]:
    """智能下载Twitter媒体。
    
    根据情况自动选择合适的下载器实现。
    
    Args:
        url: Twitter URL
        progress_callback: 进度回调函数
        
    Returns:
        Dict[str, Any]: 下载结果
    """
    # 加载配置
    config = load_config()
    
    # 创建下载器配置
    twitter_config = TwitterDownloaderConfig(
        save_dir=Path(config.get("download", {}).get("output_dir", "downloads/twitter")),
        proxy=config.get("network", {}).get("proxy"),
        timeout=config.get("network", {}).get("timeout", 30),
        max_retries=config.get("network", {}).get("retries", 5),
        cookies_file=config.get("twitter", {}).get("cookies_file", "config/twitter_cookies.txt"),
        output_template=config.get("twitter", {}).get("output_template", "%(uploader)s/%(upload_date)s-%(title)s-%(id)s.%(ext)s")
    )
    
    # 创建Cookie管理器
    cookie_manager = CookieManager()
    
    # 创建下载器
    downloader = TwitterDownloader(
        config=twitter_config,
        progress_callback=progress_callback,
        cookie_manager=cookie_manager
    )
    
    # 根据URL类型选择下载方法
    if '/status/' in url:
        return downloader.download(url)
    else:
        return downloader.download_channel(url)

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