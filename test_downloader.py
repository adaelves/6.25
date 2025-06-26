#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
下载器测试模块。
"""

import os
import sys
from pathlib import Path

from src.core.downloader import BaseDownloader
from src.utils.logger import logger

def test_download(url: str, save_dir: str = "downloads") -> bool:
    """
    测试下载功能。

    Args:
        url: 要下载的URL
        save_dir: 保存目录

    Returns:
        bool: 是否下载成功
    """
    try:
        # 创建下载器
        downloader = BaseDownloader(
            save_dir=save_dir,
            proxy="http://127.0.0.1:7890"
        )

        # 获取文件名
        filename = os.path.basename(url)
        save_path = Path(save_dir) / filename

        # 开始下载
        logger.info(f"开始下载: {url}")
        success = downloader.download(url, save_path)
        logger.info(f"下载{'成功' if success else '失败'}: {url}")
        return success

    except Exception as e:
        logger.error(f"下载出错: {url}\n错误: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        test_download(url) 