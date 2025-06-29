"""tumblr 信息提取器模块。"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.core.extractor import BaseExtractor
from src.core.exceptions import ExtractError

logger = logging.getLogger(__name__)

class TumblrExtractor(BaseExtractor):
    """tumblr 信息提取器。
    
    支持以下功能：
    1. 帖子信息提取
    2. 博客信息提取
    3. 标签搜索
    4. 用户帖子列表提取
    """
    
    # API 端点
    API_BASE = "https://api.tumblr.com/v2"
    
    # URL模式
    VALID_URL_PATTERN = re.compile(
        r'https?://(?:www\.)?([^.]+)\.tumblr\.com/(?:post/(\d+)|tagged/([^/?]+))'
    )
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化提取器。
        
        Args:
            api_key: Tumblr API密钥，可选
        """
        super().__init__()
        self.api_key = api_key
        
    def extract(self, url: str) -> Dict[str, Any]:
        """提取信息。
        
        Args:
            url: 页面URL
            
        Returns:
            Dict[str, Any]: 信息字典
            
        Raises:
            ExtractError: 提取失败
        """
        try:
            # 验证URL
            if not self.validate_url(url):
                raise ExtractError(f"不支持的URL格式: {url}")
                
            # 解析URL类型
            blog_name, post_id, tag = self._parse_url(url)
            
            # 根据URL类型提取信息
            if post_id:
                return self._extract_post(blog_name, post_id)
            elif tag:
                return self._extract_tagged_posts(blog_name, tag)
            else:
                raise ExtractError("无效的URL格式")
                
        except Exception as e:
            raise ExtractError(f"提取失败: {e}")
            
    def _extract_post(
        self,
        blog_name: str,
        post_id: str
    ) -> Dict[str, Any]:
        """提取帖子信息。
        
        Args:
            blog_name: 博客名称
            post_id: 帖子ID
            
        Returns:
            Dict[str, Any]: 帖子信息
            
        Raises:
            ExtractError: 提取失败
        """
        # 构建API请求
        api_url = f"{self.API_BASE}/blog/{blog_name}/posts"
        params = {
            'api_key': self.api_key,
            'id': post_id,
            'reblog_info': 'true',
            'notes_info': 'true'
        }
        
        try:
            # 发送请求
            response = self.session.get(api_url, params=params)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            if 'response' not in data:
                raise ExtractError("API响应格式错误")
                
            posts = data['response'].get('posts', [])
            if not posts:
                raise ExtractError("帖子不存在")
                
            post = posts[0]
            
            # 提取媒体信息
            media_info = self._extract_media_info(post)
            
            # 构建信息字典
            info = {
                'id': post_id,
                'blog_name': blog_name,
                'type': post.get('type'),
                'title': post.get('title'),
                'summary': post.get('summary'),
                'body': post.get('body'),
                'tags': post.get('tags', []),
                'date': post.get('date'),
                'timestamp': post.get('timestamp'),
                'note_count': post.get('note_count'),
                'media': media_info,
                'url': post.get('post_url'),
                'extractor': 'tumblr',
                'extractor_key': 'Tumblr'
            }
            
            return info
            
        except requests.exceptions.RequestException as e:
            raise ExtractError(f"API请求失败: {e}")
            
    def _extract_tagged_posts(
        self,
        blog_name: str,
        tag: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """提取标签下的帖子列表。
        
        Args:
            blog_name: 博客名称
            tag: 标签名
            limit: 返回数量限制
            
        Returns:
            Dict[str, Any]: 帖子列表信息
            
        Raises:
            ExtractError: 提取失败
        """
        # 构建API请求
        api_url = f"{self.API_BASE}/blog/{blog_name}/posts"
        params = {
            'api_key': self.api_key,
            'tag': tag,
            'limit': limit
        }
        
        try:
            # 发送请求
            response = self.session.get(api_url, params=params)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            if 'response' not in data:
                raise ExtractError("API响应格式错误")
                
            posts = data['response'].get('posts', [])
            
            # 提取每个帖子的信息
            posts_info = []
            for post in posts:
                media_info = self._extract_media_info(post)
                
                post_info = {
                    'id': post.get('id'),
                    'type': post.get('type'),
                    'title': post.get('title'),
                    'summary': post.get('summary'),
                    'tags': post.get('tags', []),
                    'date': post.get('date'),
                    'media': media_info,
                    'url': post.get('post_url')
                }
                
                posts_info.append(post_info)
                
            # 构建信息字典
            info = {
                'blog_name': blog_name,
                'tag': tag,
                'total_posts': len(posts_info),
                'posts': posts_info,
                'extractor': 'tumblr',
                'extractor_key': 'Tumblr'
            }
            
            return info
            
        except requests.exceptions.RequestException as e:
            raise ExtractError(f"API请求失败: {e}")
            
    def _extract_media_info(self, post: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取帖子中的媒体信息。
        
        Args:
            post: 帖子信息
            
        Returns:
            List[Dict[str, Any]]: 媒体信息列表
        """
        media = []
        
        # 提取视频信息
        if 'video_url' in post:
            media.append({
                'type': 'video',
                'url': post['video_url'],
                'thumbnail': post.get('thumbnail_url')
            })
            
        # 提取图片信息
        photos = post.get('photos', [])
        for photo in photos:
            if 'original_size' in photo:
                media.append({
                    'type': 'photo',
                    'url': photo['original_size']['url'],
                    'width': photo['original_size']['width'],
                    'height': photo['original_size']['height']
                })
                
        return media
        
    def _parse_url(self, url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """解析URL。
        
        Args:
            url: URL地址
            
        Returns:
            Tuple[str, Optional[str], Optional[str]]: 博客名、帖子ID和标签
            
        Raises:
            ValueError: URL格式错误
        """
        match = self.VALID_URL_PATTERN.match(url)
        if not match:
            raise ValueError("无效的Tumblr URL")
            
        blog_name = match.group(1)
        post_id = match.group(2)
        tag = match.group(3)
        
        return blog_name, post_id, tag
        
    def validate_url(self, url: str) -> bool:
        """验证URL是否合法。
        
        Args:
            url: URL地址
            
        Returns:
            bool: 是否合法
        """
        return bool(self.VALID_URL_PATTERN.match(url)) 