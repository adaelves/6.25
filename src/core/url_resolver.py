"""URL解析器模块。

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 
 

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 
 

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 

该模块负责解析和识别不同平台的URL。
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

@dataclass
class URLInfo:
    """URL信息数据类。
    
    Attributes:
        platform: 平台名称
        type: 内容类型(video/user/channel等)
        id: 内容ID
        url: 原始URL
    """
    platform: str
    type: str
    id: str
    url: str

class URLResolver:
    """URL解析器类。"""
    
    # 平台域名映射
    PLATFORM_DOMAINS = {
        'pornhub.com': 'pornhub',
        'youtube.com': 'youtube',
        'youtu.be': 'youtube',
        'twitter.com': 'twitter',
        'x.com': 'twitter'
    }
    
    @classmethod
    def resolve(cls, url: str) -> Optional[URLInfo]:
        """解析URL。
        
        Args:
            url: 要解析的URL
            
        Returns:
            Optional[URLInfo]: URL信息，如果无法识别则返回None
        """
        # 规范化URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 解析URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # 获取平台名称
        platform = None
        for key, value in cls.PLATFORM_DOMAINS.items():
            if domain.endswith(key):
                platform = value
                break
                
        if not platform:
            return None
            
        # 根据平台解析
        if platform == 'pornhub':
            return cls._parse_pornhub_url(url, parsed)
        elif platform == 'youtube':
            return cls._parse_youtube_url(url, parsed)
        elif platform == 'twitter':
            return cls._parse_twitter_url(url, parsed)
            
        return None
        
    @classmethod
    def _parse_pornhub_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Pornhub URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        # 处理视频页面
        if '/view_video.php' in path:
            video_id = query.get('viewkey', [''])[0]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        # 处理用户/模特页面
        elif any(path.startswith(p) for p in ['/model/', '/pornstar/', '/users/', '/channels/']):
            user_id = path.split('/')[-1]
            if user_id:  # 确保用户ID不为空
                return URLInfo('pornhub', 'user', user_id, url)
            
        # 处理直接视频链接
        elif '/video/' in path:
            video_id = path.split('/')[-1]
            if video_id:
                if not video_id.startswith('ph'):
                    video_id = 'ph' + video_id
                return URLInfo('pornhub', 'video', video_id, url)
            
        return None
        
    @classmethod
    def _parse_youtube_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析YouTube URL。"""
        path = parsed.path.lower()
        query = parse_qs(parsed.query)
        
        if 'v' in query:
            return URLInfo('youtube', 'video', query['v'][0], url)
            
        elif path.startswith('/watch/'):
            return URLInfo('youtube', 'video', path.split('/')[-1], url)
            
        elif path.startswith('/channel/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif path.startswith('/user/'):
            return URLInfo('youtube', 'user', path.split('/')[-1], url)
            
        elif path.startswith('/c/'):
            return URLInfo('youtube', 'channel', path.split('/')[-1], url)
            
        elif parsed.netloc == 'youtu.be':
            return URLInfo('youtube', 'video', path[1:], url)
            
        return None
        
    @classmethod
    def _parse_twitter_url(cls, url: str, parsed) -> Optional[URLInfo]:
        """解析Twitter URL。"""
        path = parsed.path.lower()
        parts = [p for p in path.split('/') if p]
        
        if len(parts) == 1:
            return URLInfo('twitter', 'user', parts[0], url)
            
        elif len(parts) == 3 and parts[1] == 'status':
            return URLInfo('twitter', 'tweet', parts[2], url)
            
        return None 
 