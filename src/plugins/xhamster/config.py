"""Xhamster下载器配置模块。"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

@dataclass
class XhamsterDownloaderConfig:
    """Xhamster下载器配置。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理地址
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        chunk_size: 下载块大小(字节)
        buffer_size: 写入缓冲区大小(字节)
        headers: 请求头
        cookies: Cookie
        user_agent: User-Agent
        quality: 视频质量 ('1080p', '720p', '480p', '240p')
        download_thumbnail: 是否下载缩略图
        download_preview: 是否下载预览图
        extract_title: 是否提取标题
        extract_description: 是否提取描述
        extract_tags: 是否提取标签
        extract_categories: 是否提取分类
        extract_duration: 是否提取时长
        extract_views: 是否提取观看次数
        extract_rating: 是否提取评分
        extract_uploader: 是否提取上传者信息
        extract_upload_date: 是否提取上传日期
        metadata_lang: 元数据语言
        filename_template: 文件名模板
        metadata_template: 元数据文件名模板
    """
    
    save_dir: Path = Path("downloads/xhamster")
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    chunk_size: int = 8192  # 8KB
    buffer_size: int = 1024 * 1024  # 1MB
    
    headers: Dict[str, str] = field(default_factory=lambda: {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
        "TE": "trailers"
    })
    
    cookies: Dict[str, str] = field(default_factory=dict)
    
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
    
    # 下载选项
    quality: str = "1080p"  # 默认下载最高质量
    download_thumbnail: bool = True
    download_preview: bool = False
    
    # 提取选项
    extract_title: bool = True
    extract_description: bool = True
    extract_tags: bool = True
    extract_categories: bool = True
    extract_duration: bool = True
    extract_views: bool = True
    extract_rating: bool = True
    extract_uploader: bool = True
    extract_upload_date: bool = True
    
    # 元数据选项
    metadata_lang: str = "zh-CN"
    filename_template: str = "%(title)s-%(id)s.%(ext)s"
    metadata_template: str = "%(title)s-%(id)s.info.json" 