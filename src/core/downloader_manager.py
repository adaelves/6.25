"""下载器管理器模块。

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 
 

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 
 

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 

该模块负责管理不同平台的下载器。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.core.url_resolver import URLResolver, URLInfo
from src.plugins.youtube import YouTubeDownloader, YouTubeDownloaderConfig
from src.plugins.pornhub import PornhubDownloader, PornhubDownloaderConfig
from src.plugins.twitter import TwitterDownloader, TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class DownloaderManager:
    """下载器管理器类。"""
    
    def __init__(
        self,
        save_dir: Path,
        proxy: Optional[str] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器管理器。
        
        Args:
            save_dir: 保存目录
            proxy: 代理地址
            cookie_manager: Cookie管理器
        """
        self.save_dir = save_dir
        self.proxy = proxy
        self.cookie_manager = cookie_manager
        
        # 初始化下载器
        self.youtube_downloader = YouTubeDownloader(
            YouTubeDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.pornhub_downloader = PornhubDownloader(
            PornhubDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
        self.twitter_downloader = TwitterDownloader(
            TwitterDownloaderConfig(
                save_dir=save_dir,
                proxy=proxy
            ),
            cookie_manager=cookie_manager
        )
        
    async def download(self, url: str) -> Dict[str, Any]:
        """下载媒体。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
        """
        try:
            # 规范化URL
            if not url:
                return {
                    'success': False,
                    'message': "URL不能为空",
                    'url': url
                }
                
            # 解析URL
            url_info = URLResolver.resolve(url)
            if not url_info:
                # 检查是否包含已知平台的域名
                parsed = urlparse(url.lower())
                domain = parsed.netloc
                if 'pornhub' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub URL格式，请确保URL正确且完整",
                        'url': url
                    }
                elif 'youtube' in domain or 'youtu.be' in domain:
                    return {
                        'success': False,
                        'message': "不支持的YouTube URL格式，请使用标准视频链接",
                        'url': url
                    }
                elif 'twitter' in domain or 'x.com' in domain:
                    return {
                        'success': False,
                        'message': "不支持的Twitter URL格式，请使用标准推文或用户链接",
                        'url': url
                    }
                else:
                    return {
                        'success': False,
                        'message': "不支持的URL格式或平台",
                        'url': url
                    }
                
            # 根据平台和类型选择下载器
            if url_info.platform == 'youtube':
                if url_info.type == 'video':
                    return await self.youtube_downloader.download(url)
                else:
                    return {
                        'success': False,
                        'message': "目前仅支持下载单个YouTube视频",
                        'url': url
                    }
                    
            elif url_info.platform == 'pornhub':
                if url_info.type == 'video':
                    return await self.pornhub_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.pornhub_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Pornhub内容类型，仅支持视频和用户主页",
                        'url': url
                    }
                    
            elif url_info.platform == 'twitter':
                if url_info.type == 'tweet':
                    return await self.twitter_downloader.download(url)
                elif url_info.type == 'user':
                    return await self.twitter_downloader.download_user(url)
                else:
                    return {
                        'success': False,
                        'message': "不支持的Twitter内容类型，仅支持推文和用户主页",
                        'url': url
                    }
                    
            else:
                return {
                    'success': False,
                    'message': "不支持的平台",
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            return {
                'success': False,
                'message': f"下载失败: {str(e)}",
                'url': url
            } 
 