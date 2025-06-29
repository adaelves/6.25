"""xvideos 下载器模块。"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, NetworkError, AuthError
from src.utils.http import get_content_type, get_filename_from_url
from src.utils.retry import retry_on_network_error

logger = logging.getLogger(__name__)

class XvideosDownloader(BaseDownloader):
    """xvideos 视频下载器。
    
    支持以下功能：
    1. 视频信息提取
    2. 最高质量视频下载
    3. 断点续传
    4. 进度回调
    5. 代理支持
    """
    
    # 视频信息提取正则表达式
    VIDEO_INFO_PATTERN = re.compile(r'html5player\.setVideoTitle\(\'(.*?)\'\)')
    VIDEO_URL_PATTERN = re.compile(r'html5player\.setVideoUrlHigh\(\'(.*?)\'\)')
    VIDEO_THUMB_PATTERN = re.compile(r'html5player\.setThumbUrl\(\'(.*?)\'\)')
    
    def __init__(self, config: Any):
        """初始化下载器。
        
        Args:
            config: 下载器配置
        """
        super().__init__(
            platform="xvideos",
            save_dir=config.save_dir,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=config.cookie_manager,
            config=config
        )
        
    @retry_on_network_error
    def extract_video_info(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: 视频页面URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            NetworkError: 网络错误
            AuthError: 认证错误
        """
        try:
            # 获取页面内容
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # 提取视频信息
            html = response.text
            title_match = self.VIDEO_INFO_PATTERN.search(html)
            url_match = self.VIDEO_URL_PATTERN.search(html)
            thumb_match = self.VIDEO_THUMB_PATTERN.search(html)
            
            if not (title_match and url_match):
                raise DownloadError("无法提取视频信息")
                
            # 构建信息字典
            info = {
                'title': title_match.group(1),
                'url': url_match.group(1),
                'thumbnail': thumb_match.group(1) if thumb_match else None,
                'webpage_url': url
            }
            
            return info
            
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code in (401, 403):
                    raise AuthError("访问被拒绝，请检查登录状态")
            raise NetworkError(f"网络请求失败: {e}")
            
    def download(self, url: str, save_path: Optional[Path] = None, **kwargs) -> bool:
        """下载视频。
        
        Args:
            url: 视频页面URL
            save_path: 保存路径，可选
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
            NetworkError: 网络错误
            AuthError: 认证错误
        """
        try:
            # 提取视频信息
            info = self.extract_video_info(url)
            
            # 生成保存路径
            if not save_path:
                filename = self._generate_filename(info['title'], '.mp4')
                save_path = self.save_dir / filename
                
            # 下载视频
            return super().download(info['url'], save_path, **kwargs)
            
        except Exception as e:
            raise DownloadError(f"下载失败: {e}")
            
    def _validate_url(self, url: str) -> bool:
        """验证URL是否合法。
        
        Args:
            url: URL地址
            
        Returns:
            bool: 是否合法
        """
        return bool(re.match(r'https?://(?:www\.)?xvideos\.com/video\d+', url)) 