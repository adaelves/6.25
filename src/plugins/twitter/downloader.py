"""Twitter视频下载器模块。

该模块负责从Twitter下载视频和图片。
支持认证和代理功能。
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp
from datetime import datetime, timezone
import time
import requests

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
                
                # 区分视频和图片的进度
                media_type = "视频" if d.get('video_ext') else "图片"
                self.update_progress(
                    progress,
                    f"{media_type}下载进度: {downloaded}/{total} bytes"
                    f" ({speed_text}, ETA: {eta_text})"
                )
                
    def _post_process_hook(self, d: Dict[str, Any]) -> None:
        """后处理回调。
        
        Args:
            d: 处理信息字典
        """
        status = d.get('status')
        if status == 'finished':
            filename = d.get('filename', '')
            if filename:
                media_type = "视频" if filename.endswith('.mp4') else "图片"
                logger.info(f"{media_type}下载完成: {filename}")
                
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
        """下载视频或图片。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            ValueError: Cookie无效或不完整
            Exception: 下载过程中的其他错误
        """
        try:
            logger.info(f"开始下载Twitter内容: {url}")
            
            # 获取基本下载选项
            options = self.get_download_options()
            
            # 先获取推文信息以确定用户名
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                username = info.get('uploader', 'unknown')
                
            # 创建用户专属目录
            user_dir = self.config.save_dir / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 添加图片和视频下载相关选项
            media_options = {
                'extract_flat': True,  # 扁平化提取
                'extract_images': True,  # 启用图片提取
                'writethumbnail': True,  # 下载缩略图
                'paths': {
                    'home': str(user_dir)  # 用户专属目录
                },
                'outtmpl': {
                    'default': '%(id)s.%(ext)s',  # 视频模板
                    'image': '%(id)s_%(autonumber)d.%(ext)s',  # 图片模板
                    'thumbnail': '%(id)s_thumb.%(ext)s'  # 缩略图模板
                },
                'progress_hooks': [self._progress_hook],  # 进度回调
                'postprocessor_hooks': [self._post_process_hook],  # 后处理回调
                
                # 图片下载器设置
                'postprocessors': [{
                    'key': 'FFmpegMetadata',  # 保留元数据
                }, {
                    'key': 'ModifyChapters',  # 处理章节信息
                    'remove_chapters_patterns': ['.*?']  # 移除所有章节
                }],
                
                # 强制下载所有媒体
                'download_archive': None,  # 禁用下载历史
                'break_on_reject': False,  # 遇到错误继续
                'ignore_no_formats_error': True,  # 忽略格式错误
                'extract_flat': False  # 禁用扁平化提取以获取完整信息
            }
            
            # 合并选项
            options.update(media_options)
            
            # 执行下载
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.debug(f"使用选项下载: {options}")
                info = ydl.extract_info(url, download=True)
                
                # 记录下载结果
                entries = info.get('entries', [info]) if info.get('_type') == 'playlist' else [info]
                video_count = len([e for e in entries if e.get('_type') == 'video'])
                image_count = len([e for e in entries if e.get('_type') == 'image'])
                
                # 如果没有找到视频或图片，尝试从推文信息中提取图片URL
                if video_count == 0 and image_count == 0 and 'photos' in info:
                    photos = info.get('photos', [])
                    for i, photo in enumerate(photos, 1):
                        photo_url = photo.get('url')
                        if photo_url:
                            photo_path = user_dir / f"{info['id']}_{i}.jpg"
                            # 使用yt-dlp下载图片
                            ydl.download([photo_url])
                            image_count += 1
                
                logger.info(
                    f"下载完成到目录 {user_dir}: "
                    f"{video_count}个视频, "
                    f"{image_count}张图片"
                )
                
            return True
            
        except ValueError as e:
            logger.error(f"Twitter认证错误: {e}")
            raise
            
        except Exception as e:
            if "No video could be found in this tweet" in str(e):
                # 如果是纯图片推文，尝试重新下载
                logger.info("推文不包含视频，尝试下载图片...")
                try:
                    return self._download_images_only(url)
                except Exception as img_e:
                    logger.error(f"图片下载失败: {img_e}")
                    raise
            else:
                logger.error(f"Twitter内容下载出错: {e}")
                raise
                
    def _download_images_only(self, url: str) -> bool:
        """专门处理纯图片推文的下载。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
        """
        try:
            options = self.get_download_options()
            options.update({
                'format': 'jpg',  # 只下载图片
                'extract_flat': False,
                'extract_images': True,
                'writethumbnail': True,
                'skip_video': True,  # 跳过视频
                'ignoreerrors': True,  # 忽略错误继续下载
                'extract_info_only': True  # 先只提取信息
            })
            
            # 先提取信息
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    logger.error("无法获取推文信息")
                    return False
                
                # 从GraphQL响应中提取信息
                tweet_data = info.get('_api_data', {})
                if not tweet_data:
                    logger.error("无法从API响应中获取推文数据")
                    return False
                
                # 提取用户信息和推文ID
                result = tweet_data.get('data', {}).get('threaded_conversation_with_injections_v2', {}).get('instructions', [])
                if not result:
                    logger.error("无法获取推文详细信息")
                    return False
                
                # 遍历结果找到推文信息
                tweet_entry = None
                for instruction in result:
                    if instruction.get('type') == 'TimelineAddEntries':
                        entries = instruction.get('entries', [])
                        for entry in entries:
                            if 'tweet' in entry.get('content', {}).get('itemContent', {}):
                                tweet_entry = entry.get('content', {}).get('itemContent', {}).get('tweet', {})
                                break
                
                if not tweet_entry:
                    logger.error("无法找到推文内容")
                    return False
                
                # 提取用户信息
                user_results = tweet_entry.get('core', {}).get('user_results', {}).get('result', {})
                username = user_results.get('legacy', {}).get('screen_name')
                if not username:
                    logger.error("无法获取用户名")
                    return False
                
                # 提取推文ID和媒体信息
                tweet_legacy = tweet_entry.get('legacy', {})
                tweet_id = tweet_legacy.get('id_str')
                media_entities = tweet_legacy.get('extended_entities', {}).get('media', [])
                
                if not tweet_id or not media_entities:
                    logger.error("无法获取推文ID或媒体信息")
                    return False
                
                # 创建用户目录
                user_dir = self.config.save_dir / username
                user_dir.mkdir(parents=True, exist_ok=True)
                
                # 下载所有图片
                success = False
                for i, media in enumerate(media_entities, 1):
                    if media.get('type') != 'photo':
                        continue
                        
                    photo_url = media.get('media_url_https')
                    if not photo_url:
                        continue
                    
                    # 获取最大尺寸的图片URL
                    photo_url = f"{photo_url}?format=jpg&name=4096x4096"
                    
                    # 构建保存路径
                    save_path = user_dir / f"{tweet_id}_{i}.jpg"
                    
                    try:
                        logger.info(f"下载第{i}张图片: {photo_url}")
                        # 使用requests直接下载图片
                        response = requests.get(photo_url, 
                                             headers=options.get('http_headers', {}),
                                             proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                                             timeout=30)
                        response.raise_for_status()
                        
                        # 保存图片
                        with open(save_path, 'wb') as f:
                            f.write(response.content)
                            
                        success = True
                        logger.info(f"图片已保存到: {save_path}")
                    except Exception as e:
                        logger.error(f"下载第{i}张图片失败: {e}")
                        continue
                
                if success:
                    logger.info(f"图片下载完成到目录: {user_dir}")
                    return True
                else:
                    logger.error("所有图片下载失败")
                    return False
                    
        except Exception as e:
            logger.error(f"图片下载过程出错: {e}")
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