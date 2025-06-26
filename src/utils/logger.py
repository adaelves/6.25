#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志管理模块。

提供统一的日志配置和管理功能。
"""

import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logger(
    name: str = "video_downloader",
    log_file: str = "logs/download.log",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    配置日志记录器。

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件数量

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志目录
    log_dir = os.path.dirname(log_file)
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 如果已经有处理器，不重复添加
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件处理器（支持日志轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    return logger

# 创建默认日志记录器
logger = setup_logger()

def get_logger(name: str = "video_downloader") -> logging.Logger:
    """
    获取指定名称的日志记录器。

    Args:
        name: 日志记录器名称

    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name) 