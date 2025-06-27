"""Pornhub 下载器配置模块。

该模块定义了 Pornhub 下载器的配置类。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PornhubDownloaderConfig:
    """Pornhub 下载器配置类。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理地址
        timeout: 超时时间（秒）
        max_retries: 最大重试次数
        output_template: 输出文件名模板
        max_height: 最大视频高度
        min_height: 最小视频高度
        prefer_quality: 首选视频质量
        merge_output_format: 视频合并输出格式
        max_downloads: 每页最大下载数量
        cookies_file: Cookies 文件路径
    """
    
    save_dir: Path
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    output_template: str = "%(uploader)s/%(title)s-%(id)s.%(ext)s"
    max_height: Optional[int] = 1080
    min_height: Optional[int] = 480
    prefer_quality: str = "1080p"
    merge_output_format: str = "mp4"
    max_downloads: int = 50
    cookies_file: Optional[str] = None 