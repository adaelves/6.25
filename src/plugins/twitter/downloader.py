"""Twitter视频下载器模块。

该模块负责从Twitter下载视频。
支持认证和代理功能。
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp
from datetime import datetime, timezone
import time

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import TwitterDownloaderConfig

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter视频下载器。
    
    使用yt-dlp库从Twitter下载视频。
    支持认证和代理功能。
    
    Attributes:
        config: TwitterDownloaderConfig, 下载器配置
    """
    
    def __init__(
        self,
        config: TwitterDownloaderConfig,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            cookie_manager: Cookie管理器，如果不提供则创建新实例
        """
        super().__init__(
            platform="twitter",
            save_dir=config.save_dir,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager
        )
        self.config = config
        
        # 如果配置中有cookies，保存到cookie管理器
        if config.cookies:
            self.cookie_manager.save_cookies("twitter", config.cookies)
        
    def _save_cookies_netscape(self, cookies: Dict[str, str], cookie_file: Path) -> None:
        """将Cookie保存为Netscape格式。
        
        Args:
            cookies: Cookie字典
            cookie_file: 保存路径
            
        Notes:
            Netscape格式:
            domain\tHTTP_ONLY\tpath\tSECURE\texpiry\tname\tvalue
        """
        # 确保目录存在
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置默认值
        domains = [".twitter.com", ".x.com"]  # 支持两个域名
        default_path = "/"
        # 设置过期时间为1年后
        expiry = int(time.time()) + 365 * 24 * 60 * 60
        
        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                # 写入文件头
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                f.write("# This is a generated file!  Do not edit.\n\n")
                
                # 写入每个Cookie到两个域名
                for domain in domains:
                    for name, value in cookies.items():
                        # domain HTTP_ONLY path SECURE expiry name value
                        line = f"{domain}\tTRUE\t{default_path}\tTRUE\t{expiry}\t{name}\t{value}\n"
                        f.write(line)
                    
            logger.info(f"Cookie已保存到Netscape格式文件: {cookie_file}")
            
        except Exception as e:
            logger.error(f"保存Netscape格式Cookie失败: {e}")
            raise
        
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """下载进度回调。
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            # 计算进度
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            if total > 0 and downloaded is not None:
                progress = downloaded / total
                speed_text = f"{speed/1024:.1f} KB/s" if speed else "Unknown"
                eta_text = f"{eta}s" if eta else "Unknown"
                
                self.update_progress(
                    progress,
                    f"下载进度: {downloaded}/{total} bytes"
                    f" ({speed_text}, ETA: {eta_text})"
                )
                
    def get_download_options(self) -> Dict[str, Any]:
        """获取下载选项。
        
        Returns:
            Dict[str, Any]: 下载选项字典
            
        Notes:
            - 使用Netscape格式的Cookie文件
            - 添加必要的认证头部
            - 启用详细日志和错误报告
        """
        # 检查Cookie状态
        cookies = self.cookie_manager.get_cookies("twitter")
        if not cookies:
            logger.error("未找到Twitter Cookie")
            raise ValueError("请先完成Twitter认证")
            
        # 检查必需的Cookie
        required_cookies = {"auth_token", "ct0"}
        missing_cookies = required_cookies - set(cookies.keys())
        if missing_cookies:
            logger.error(f"缺少必需的Cookie: {missing_cookies}")
            raise ValueError("Twitter认证信息不完整")
            
        # 保存为Netscape格式
        cookie_dir = Path("config/cookies")
        cookie_file = cookie_dir / "twitter.txt"  # 使用.txt扩展名
        self._save_cookies_netscape(cookies, cookie_file)
            
        # 构建下载选项
        options = {
            # Cookie认证
            'cookiefile': str(cookie_file),
            'http_headers': {
                # 基本头部
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                
                # Twitter特定头部
                'X-Twitter-Auth-Type': 'OAuth2Session',
                'X-Twitter-Client-Language': 'en',
                'X-Twitter-Active-User': 'yes',
                'Authorization': f'Bearer {cookies.get("auth_token", "")}',
                'x-csrf-token': cookies.get('ct0', ''),
                
                # 安全头部
                'Referer': 'https://twitter.com/',
                'Origin': 'https://twitter.com',
                'DNT': '1'
            },
            
            # Twitter API设置
            'extractor_args': {
                'twitter': {
                    'api': ['graphql'],
                }
            },
            
            # 认证设置
            'username': cookies.get('auth_token', ''),  # 使用auth_token作为用户名
            'password': cookies.get('ct0', ''),        # 使用ct0作为密码
            
            # 错误处理和日志
            'ignoreerrors': False,
            'verbose': True,
            
            # 下载设置
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': str(self.config.save_dir / '%(title)s.%(ext)s'),
            
            # 代理设置
            'proxy': self.config.proxy if self.config.proxy else None,
            
            # 重试设置
            'retries': 10,
            'retry_sleep': lambda n: 5 * (n + 1),
            
            # 调试设置
            'debug_printtraffic': True,
            'no_color': True
        }
        
        logger.debug(f"下载选项: {options}")
        return options
        
    def download(self, url: str) -> bool:
        """下载视频。
        
        Args:
            url: 视频URL
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            ValueError: Cookie无效或不完整
            Exception: 下载过程中的其他错误
        """
        try:
            logger.info(f"开始下载Twitter视频: {url}")
            
            # 获取下载选项
            options = self.get_download_options()
            
            # 添加进度回调
            options['progress_hooks'] = [self._progress_hook]
            
            # 执行下载
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.debug(f"使用选项下载: {options}")
                ydl.download([url])
                
            logger.info("Twitter视频下载完成")
            return True
            
        except ValueError as e:
            logger.error(f"Twitter认证错误: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Twitter视频下载出错: {e}")
            raise
            
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
            
        Raises:
            ValueError: URL无效
            DownloadError: 获取信息失败
        """
        try:
            ydl_opts = self.get_download_options()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise DownloadError(f"无法提取视频信息: {e}") 