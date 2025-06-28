"""YouTube视频下载器模块。

该模块负责从YouTube下载视频。
支持会员视频下载和字幕下载。
自动处理年龄限制和会员限制。
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import yt_dlp
import requests
from bs4 import BeautifulSoup

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, APIError
from src.utils.cookie_manager import CookieManager
from .config import YouTubeDownloaderConfig

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器。
    
    支持会员视频下载和字幕下载。
    自动处理年龄限制和会员限制。
    
    Attributes:
        config: YouTubeDownloaderConfig, 下载器配置
    """
    
    def __init__(
        self,
        config: YouTubeDownloaderConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器。

        Args:
            config: 下载器配置
            progress_callback: 进度回调函数
            cookie_manager: Cookie管理器
        """
        super().__init__(
            platform="youtube",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager,
            config=config
        )
        
        # 设置yt-dlp
        self._setup_yt_dlp()
        
        # 验证Cookie
        if cookie_manager and cookie_manager.get_cookies("youtube"):
            try:
                self.check_cookie_valid()
                logger.info("YouTube Cookie 验证成功")
            except ValueError as e:
                logger.warning(f"YouTube Cookie 验证失败: {str(e)}")

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(str(self.config.save_dir), '%(uploader)s/%(title)s-%(id)s.%(ext)s'),
            
            # 提取设置
            'extract_flat': False,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            
            # 网络设置
            'nocheckcertificate': True,
            'proxy': self.config.proxy,
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            
            # 回调函数
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            
            # 字幕设置
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-Hans', 'en'],
            'postprocessors': [{
                'key': 'FFmpegEmbedSubtitle',
                'already_have_subtitle': False,
            }],
            
            # 媒体处理设置
            'merge_output_format': 'mp4',
            'writethumbnail': True,
            'embedthumbnail': True,
            
            # 元数据
            'add_metadata': True,
            'addmetadata': True,
            
            # 年龄限制
            'age_limit': 99,
        }

        # 添加Cookie文件
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("youtube")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file

    def check_cookie_valid(self) -> bool:
        """验证YouTube Cookie是否有效。
        
        通过访问会员专属页面来验证Cookie是否有效。
        
        Returns:
            bool: Cookie是否有效
            
        Raises:
            ValueError: Cookie无效或已过期
        """
        try:
            # 获取Cookie
            cookies = self.cookie_manager.get_cookies("youtube")
            if not cookies:
                raise ValueError("未找到YouTube Cookie")
                
            # 构建请求头
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/91.0.4472.124 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # 访问会员专属页面
            test_url = "https://www.youtube.com/account"
            response = requests.get(
                test_url,
                headers=headers,
                cookies=cookies,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析响应
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查是否包含会员专享内容标识
            if "会员专享" in response.text or "Premium" in response.text:
                logger.info("YouTube Cookie 验证成功")
                return True
                
            raise ValueError("Cookie无效或已过期")
            
        except requests.RequestException as e:
            raise ValueError(f"验证Cookie时网络错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"验证Cookie失败: {str(e)}")

    def _progress_hook(self, d: Dict[str, Any]):
        """下载进度回调。

        Args:
            d: 进度信息
        """
        try:
            if d['status'] == 'downloading':
                # 计算下载进度
                progress = 0.0
                desc = f"下载中: {d['filename']}"
                
                if 'total_bytes' in d and d['total_bytes']:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d['total_bytes']
                    progress = downloaded / total
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    if speed:
                        desc += f" - {speed/1024/1024:.1f}MB/s"
                    if eta:
                        desc += f" - 剩余{eta}秒"
                
                # 更新进度条
                if self.progress_callback:
                    self.progress_callback(progress, desc)

            elif d['status'] == 'finished':
                logger.info(f"下载完成: {d['filename']}")
                if self.progress_callback:
                    self.progress_callback(1.0, "下载完成")

            elif d['status'] == 'error':
                error_msg = f"下载出错: {d.get('error', '未知错误')}"
                logger.error(error_msg)
                if self.progress_callback:
                    self.progress_callback(0.0, error_msg)
                    
        except Exception as e:
            logger.error(f"处理进度回调时出错: {str(e)}")
            if self.progress_callback:
                self.progress_callback(0.0, f"进度更新出错: {str(e)}")

    def _postprocessor_hook(self, d: Dict[str, Any]):
        """后处理回调。

        Args:
            d: 处理信息
        """
        try:
            if d['status'] == 'started':
                msg = f"开始处理: {d.get('postprocessor', '')}"
                logger.info(msg)
                if self.progress_callback:
                    self.progress_callback(0.0, msg)
                    
            elif d['status'] == 'finished':
                msg = f"处理完成: {d.get('postprocessor', '')}"
                logger.info(msg)
                if self.progress_callback:
                    self.progress_callback(1.0, msg)
                    
            elif d['status'] == 'error':
                error_msg = f"处理出错: {d.get('error', '未知错误')}"
                logger.error(error_msg)
                if self.progress_callback:
                    self.progress_callback(0.0, error_msg)
                    
        except Exception as e:
            logger.error(f"处理后处理回调时出错: {str(e)}")
            if self.progress_callback:
                self.progress_callback(0.0, f"处理更新出错: {str(e)}")

    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的YouTube链接。

        Args:
            url: 要验证的URL

        Returns:
            bool: 是否为有效的YouTube链接
        """
        return 'youtube.com' in url or 'youtu.be' in url

    def download(self, url: str) -> Dict[str, Any]:
        """下载YouTube视频。

        支持以下URL类型:
        - 单个视频
        - 播放列表
        - 频道视频
        - 直播回放

        Args:
            url: YouTube URL

        Returns:
            Dict[str, Any]: 下载结果

        Raises:
            DownloadError: 下载失败
        """
        if not self._validate_url(url):
            raise DownloadError(f"无效的YouTube URL: {url}")
            
        try:
            # 验证Cookie
            if self.cookie_manager and self.cookie_manager.get_cookies("youtube"):
                self.check_cookie_valid()
            
            # 开始下载
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # 处理下载结果
                result = {
                    'title': info.get('title', ''),
                    'uploader': info.get('uploader', ''),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'description': info.get('description', ''),
                    'upload_date': info.get('upload_date', ''),
                    'webpage_url': info.get('webpage_url', url),
                }
                
                # 添加下载文件信息
                if 'requested_downloads' in info:
                    result['downloads'] = [{
                        'path': d['filepath'],
                        'format': d['format'],
                        'filesize': d.get('filesize', 0),
                        'ext': d['ext']
                    } for d in info['requested_downloads']]
                    
                return result
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            raise DownloadError(f"下载失败: {str(e)}")
