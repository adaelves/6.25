"""xvideos 信息提取器模块。"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.core.extractor import BaseExtractor
from src.core.exceptions import ExtractError

logger = logging.getLogger(__name__)

class XvideosExtractor(BaseExtractor):
    """xvideos 信息提取器。
    
    支持以下功能：
    1. 视频信息提取
    2. 视频列表提取
    3. 搜索结果提取
    4. 用户视频提取
    """
    
    # URL模式
    VALID_URL_PATTERN = re.compile(r'https?://(?:www\.)?xvideos\.com/(?:video(\d+)|(?:channels|pornstars)/([^/]+))')
    
    # 视频信息提取正则表达式
    VIDEO_INFO_PATTERN = re.compile(r'html5player\.setVideoTitle\(\'(.*?)\'\)')
    VIDEO_URL_PATTERN = re.compile(r'html5player\.setVideoUrlHigh\(\'(.*?)\'\)')
    VIDEO_THUMB_PATTERN = re.compile(r'html5player\.setThumbUrl\(\'(.*?)\'\)')
    VIDEO_DURATION_PATTERN = re.compile(r'html5player\.setVideoDuration\((\d+)\)')
    
    def __init__(self):
        """初始化提取器。"""
        super().__init__()
        
    def extract(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: 视频页面URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            ExtractError: 提取失败
        """
        try:
            # 验证URL
            if not self.validate_url(url):
                raise ExtractError(f"不支持的URL格式: {url}")
                
            # 获取页面内容
            response = self.session.get(url)
            response.raise_for_status()
            html = response.text
            
            # 提取视频信息
            info = self._extract_video_info(html, url)
            
            return info
            
        except Exception as e:
            raise ExtractError(f"提取失败: {e}")
            
    def _extract_video_info(self, html: str, url: str) -> Dict[str, Any]:
        """从HTML中提取视频信息。
        
        Args:
            html: 页面HTML内容
            url: 视频页面URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            ExtractError: 提取失败
        """
        # 提取基本信息
        title_match = self.VIDEO_INFO_PATTERN.search(html)
        url_match = self.VIDEO_URL_PATTERN.search(html)
        thumb_match = self.VIDEO_THUMB_PATTERN.search(html)
        duration_match = self.VIDEO_DURATION_PATTERN.search(html)
        
        if not (title_match and url_match):
            raise ExtractError("无法提取视频信息")
            
        # 使用BeautifulSoup提取更多信息
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取上传时间
        upload_date = None
        date_element = soup.find('span', {'class': 'upload-date'})
        if date_element:
            try:
                upload_date = datetime.strptime(
                    date_element.text.strip(),
                    '%Y-%m-%d'
                ).strftime('%Y%m%d')
            except ValueError:
                pass
                
        # 提取标签
        tags = []
        tag_elements = soup.find_all('a', {'class': 'tag'})
        for tag in tag_elements:
            tags.append(tag.text.strip())
            
        # 提取作者信息
        uploader = None
        uploader_url = None
        author_element = soup.find('span', {'class': 'name'})
        if author_element:
            uploader = author_element.text.strip()
            author_link = author_element.find('a')
            if author_link:
                uploader_url = author_link.get('href')
                
        # 构建信息字典
        info = {
            'id': self._extract_video_id(url),
            'title': title_match.group(1),
            'url': url_match.group(1),
            'thumbnail': thumb_match.group(1) if thumb_match else None,
            'duration': int(duration_match.group(1)) if duration_match else None,
            'webpage_url': url,
            'upload_date': upload_date,
            'tags': tags,
            'uploader': uploader,
            'uploader_url': uploader_url,
            'extractor': 'xvideos',
            'extractor_key': 'Xvideos'
        }
        
        return info
        
    def _extract_video_id(self, url: str) -> Optional[str]:
        """从URL中提取视频ID。
        
        Args:
            url: 视频页面URL
            
        Returns:
            Optional[str]: 视频ID
        """
        match = self.VALID_URL_PATTERN.match(url)
        if match:
            return match.group(1)
        return None
        
    def validate_url(self, url: str) -> bool:
        """验证URL是否合法。
        
        Args:
            url: URL地址
            
        Returns:
            bool: 是否合法
        """
        return bool(self.VALID_URL_PATTERN.match(url)) 