"""tumblr 下载器模块。"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, NetworkError, AuthError
from src.utils.http import get_content_type, get_filename_from_url
from src.utils.retry import retry_on_network_error

logger = logging.getLogger(__name__)

class TumblrDownloader(BaseDownloader):
    """tumblr 下载器。
    
    支持以下功能：
    1. 视频下载
    2. 图片下载
    3. 批量下载
    4. 断点续传
    5. 进度回调
    6. 代理支持
    """
    
    # API 端点
    API_BASE = "https://api.tumblr.com/v2"
    
    def __init__(self, config: Any):
        """初始化下载器。
        
        Args:
            config: 下载器配置
        """
        super().__init__(
            platform="tumblr",
            save_dir=config.save_dir,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=config.cookie_manager,
            config=config
        )
        
        # API 密钥
        self.api_key = getattr(config, 'tumblr_api_key', None)
        if not self.api_key:
            logger.warning("未配置 Tumblr API 密钥，部分功能可能受限")
            
    @retry_on_network_error
    def extract_post_info(self, url: str) -> Dict[str, Any]:
        """提取帖子信息。
        
        Args:
            url: 帖子URL
            
        Returns:
            Dict[str, Any]: 帖子信息字典
            
        Raises:
            NetworkError: 网络错误
            AuthError: 认证错误
        """
        try:
            # 解析博客名和帖子ID
            blog_name, post_id = self._parse_post_url(url)
            
            # 构建API请求
            api_url = f"{self.API_BASE}/blog/{blog_name}/posts"
            params = {
                'api_key': self.api_key,
                'id': post_id,
                'reblog_info': 'true',
                'notes_info': 'true'
            }
            
            # 发送请求
            response = self.session.get(
                api_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            if 'response' not in data:
                raise DownloadError("API响应格式错误")
                
            post = data['response'].get('posts', [])
            if not post:
                raise DownloadError("帖子不存在")
                
            return post[0]
            
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code in (401, 403):
                    raise AuthError("API密钥无效或访问被拒绝")
            raise NetworkError(f"网络请求失败: {e}")
            
    def download(
        self,
        url: str,
        save_path: Optional[Path] = None,
        media_type: str = 'all',
        **kwargs
    ) -> bool:
        """下载帖子中的媒体文件。
        
        Args:
            url: 帖子URL
            save_path: 保存路径，可选
            media_type: 媒体类型，可选值：'all'、'video'、'photo'
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
            NetworkError: 网络错误
            AuthError: 认证错误
        """
        try:
            # 提取帖子信息
            post = self.extract_post_info(url)
            
            # 提取媒体URL
            media_urls = self._extract_media_urls(post, media_type)
            if not media_urls:
                raise DownloadError("未找到可下载的媒体文件")
                
            # 下载所有媒体文件
            success = True
            for media_url in media_urls:
                # 生成保存路径
                if not save_path:
                    filename = self._generate_filename(
                        post.get('summary', 'untitled'),
                        self._get_extension(media_url)
                    )
                    file_save_path = self.save_dir / filename
                else:
                    file_save_path = save_path
                    
                # 下载单个文件
                success &= super().download(
                    media_url,
                    file_save_path,
                    **kwargs
                )
                
            return success
            
        except Exception as e:
            raise DownloadError(f"下载失败: {e}")
            
    def _parse_post_url(self, url: str) -> Tuple[str, str]:
        """解析帖子URL。
        
        Args:
            url: 帖子URL
            
        Returns:
            Tuple[str, str]: 博客名和帖子ID
            
        Raises:
            ValueError: URL格式错误
        """
        match = re.match(
            r'https?://([^.]+)\.tumblr\.com/post/(\d+)',
            url
        )
        if not match:
            raise ValueError("无效的Tumblr帖子URL")
            
        return match.groups()
        
    def _extract_media_urls(
        self,
        post: Dict[str, Any],
        media_type: str = 'all'
    ) -> List[str]:
        """提取媒体URL。
        
        Args:
            post: 帖子信息
            media_type: 媒体类型
            
        Returns:
            List[str]: 媒体URL列表
        """
        urls = []
        
        # 提取视频URL
        if media_type in ('all', 'video'):
            if 'video_url' in post:
                urls.append(post['video_url'])
                
        # 提取图片URL
        if media_type in ('all', 'photo'):
            photos = post.get('photos', [])
            for photo in photos:
                if 'original_size' in photo:
                    urls.append(photo['original_size']['url'])
                    
        return urls
        
    def _get_extension(self, url: str) -> str:
        """获取文件扩展名。
        
        Args:
            url: 文件URL
            
        Returns:
            str: 文件扩展名
        """
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix
        return ext if ext else '.unknown'
        
    def _validate_url(self, url: str) -> bool:
        """验证URL是否合法。
        
        Args:
            url: URL地址
            
        Returns:
            bool: 是否合法
        """
        return bool(re.match(
            r'https?://[^.]+\.tumblr\.com/post/\d+',
            url
        )) 