"""Instagram下载器配置模块。"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

@dataclass
class InstagramDownloaderConfig:
    """Instagram下载器配置。
    
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
        download_video: 是否下载视频
        download_image: 是否下载图片
        download_story: 是否下载故事
        download_reel: 是否下载Reel
        download_album: 是否下载相册
        download_highlight: 是否下载精选故事
        download_igtv: 是否下载IGTV
        download_avatar: 是否下载头像
        extract_comments: 是否提取评论
        extract_likes: 是否提取点赞数
        extract_caption: 是否提取描述
        extract_location: 是否提取位置
        extract_tagged_users: 是否提取标记用户
        extract_hashtags: 是否提取话题标签
        metadata_lang: 元数据语言
        filename_template: 文件名模板
        metadata_template: 元数据文件名模板
    """
    
    save_dir: Path = Path("downloads/instagram")
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
        "TE": "trailers"
    })
    
    cookies: Dict[str, str] = field(default_factory=dict)
    
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
    
    # 下载选项
    download_video: bool = True
    download_image: bool = True
    download_story: bool = True
    download_reel: bool = True
    download_album: bool = True
    download_highlight: bool = True
    download_igtv: bool = True
    download_avatar: bool = False
    
    # 提取选项
    extract_comments: bool = True
    extract_likes: bool = True
    extract_caption: bool = True
    extract_location: bool = True
    extract_tagged_users: bool = True
    extract_hashtags: bool = True
    
    # 元数据选项
    metadata_lang: str = "zh-CN"
    filename_template: str = "%(uploader)s/%(title)s-%(id)s.%(ext)s"
    metadata_template: str = "%(uploader)s/%(title)s-%(id)s.info.json" 