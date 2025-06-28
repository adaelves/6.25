"""Pornhub视频下载器模块。

该模块负责从Pornhub下载视频。
支持m3u8流媒体下载。
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import yt_dlp
from datetime import datetime
import time
from tqdm import tqdm
import m3u8
import requests
from urllib.parse import urljoin, urlparse

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import PornhubDownloaderConfig

logger = logging.getLogger(__name__)

class PornhubDownloader(BaseDownloader):
    """Pornhub视频下载器。
    
    支持以下功能：
    - m3u8流媒体下载
    - 自动重试和恢复
    - 进度显示
    - 视频信息提取和存储
    
    下载器实现了两种下载方式：
    1. 自定义m3u8下载器：专门处理m3u8流媒体
    2. yt-dlp下载器：作为默认下载器和备选方案
    
    Attributes:
        config: PornhubDownloaderConfig, 下载器配置
    """
    
    def __init__(
        self,
        config: PornhubDownloaderConfig,
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
            platform="pornhub",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager
        )
        self.config = config
        self._setup_yt_dlp()

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.ydl_opts = {
            # 基本配置
            'format': 'best',  # 选择最佳质量
            'outtmpl': os.path.join(str(self.config.save_dir), self.config.output_template),
            
            # 网络设置
            'proxy': self.config.proxy,
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            'fragment_retries': self.config.max_retries,
            
            # 下载设置
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            
            # 回调函数
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            
            # HLS下载设置
            'hls_prefer_native': True,
            'hls_split_discontinuity': True,
            
            # 自定义下载器
            'downloader': {
                'm3u8': self._m3u8_downloader
            },
            
            # 元数据
            'writeinfojson': True,
            'writethumbnail': True
        }

        # 添加Cookie支持
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("pornhub")
            if os.path.exists(cookie_file):
                self.ydl_opts['cookiefile'] = cookie_file

    def _m3u8_downloader(self, m3u8_url: str) -> str:
        """自定义m3u8下载器。

        专门用于处理m3u8流媒体下载，支持：
        - 自动提取base_uri
        - 片段重试和恢复
        - 详细的进度显示
        - 自定义HTTP头

        Args:
            m3u8_url: m3u8文件URL

        Returns:
            str: 下载的文件路径

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 下载m3u8文件
            response = requests.get(
                m3u8_url,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            # 从URL中提取base_uri
            parsed_url = urlparse(m3u8_url)
            base_uri = f"{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/"
            
            # 解析m3u8（不使用base_uri参数，因为某些版本不支持）
            playlist = m3u8.loads(response.text)
            if not playlist or not playlist.segments:
                raise DownloadError("无效的m3u8文件")
                
            # 准备下载
            total_segments = len(playlist.segments)
            downloaded = 0
            output_file = os.path.join(
                str(self.config.save_dir),
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"
            )
            
            # 下载所有片段
            with open(output_file, 'wb') as f:
                for segment in playlist.segments:
                    if not isinstance(segment, m3u8.model.Segment):
                        continue
                        
                    # 获取片段URL（手动处理base_uri）
                    segment_url = segment.uri
                    if not segment_url.startswith(('http://', 'https://')):
                        segment_url = urljoin(base_uri, segment_url)
                    
                    if not segment_url:
                        logger.warning(f"跳过无效片段: {segment}")
                        continue
                        
                    # 下载片段
                    for retry in range(self.config.max_retries):
                        try:
                            segment_response = requests.get(
                                segment_url,
                                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                                timeout=self.config.timeout,
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                    'Accept': '*/*',
                                    'Accept-Language': 'en-US,en;q=0.5',
                                    'Origin': f"{parsed_url.scheme}://{parsed_url.netloc}",
                                    'Referer': f"{parsed_url.scheme}://{parsed_url.netloc}/"
                                }
                            )
                            segment_response.raise_for_status()
                            f.write(segment_response.content)
                            break
                        except requests.exceptions.RequestException as e:
                            if retry == self.config.max_retries - 1:
                                raise DownloadError(f"下载片段失败: {str(e)}")
                            logger.warning(f"下载片段失败，重试 {retry + 1}/{self.config.max_retries}: {str(e)}")
                            time.sleep(1 * (retry + 1))  # 递增等待时间
                            
                    # 更新进度
                    downloaded += 1
                    progress = downloaded / total_segments
                    desc = f"下载进度: {downloaded}/{total_segments} ({progress:.1%})"
                    
                    if self.progress_callback:
                        self.progress_callback(progress, desc)
                    logger.debug(desc)
                        
            if downloaded == 0:
                raise DownloadError("没有成功下载任何片段")
                
            logger.info(f"下载完成: {output_file}")
            return output_file
            
        except requests.exceptions.RequestException as e:
            raise DownloadError(f"网络请求失败: {str(e)}")
        except m3u8.ParseError as e:
            raise DownloadError(f"解析m3u8文件失败: {str(e)}")
        except Exception as e:
            raise DownloadError(f"m3u8下载失败: {str(e)}")

    def download(self, url: str) -> Dict[str, Any]:
        """下载视频。

        该方法实现了两级下载策略：
        1. 首先尝试使用自定义m3u8下载器
        2. 如果m3u8下载失败，自动降级到yt-dlp下载器

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 下载结果，包含：
                - success: 是否成功
                - url: 原始URL
                - file_path: 下载文件路径（如果成功）
                - info: 视频信息（元数据）

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                raise DownloadError("不支持的URL格式")
                
            logger.info(f"开始下载视频: {url}")
            
            # 获取视频信息并下载
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise DownloadError("无法获取视频信息")
                except yt_dlp.utils.DownloadError as e:
                    raise DownloadError(f"获取视频信息失败: {str(e)}")
                    
                # 检查是否为m3u8流
                if info.get('protocol') == 'm3u8' or info.get('protocol') == 'm3u8_native':
                    # 使用自定义下载器
                    try:
                        file_path = self._m3u8_downloader(info['url'])
                        return {
                            'success': True,
                            'url': url,
                            'file_path': file_path,
                            'info': info
                        }
                    except Exception as e:
                        logger.error(f"m3u8下载失败，尝试使用默认下载器: {str(e)}")
                        # 如果m3u8下载失败，尝试使用默认下载器
                        result = ydl.download([url])
                        return {
                            'success': result == 0,
                            'url': url,
                            'info': info
                        }
                else:
                    # 使用默认下载器
                    result = ydl.download([url])
                    return {
                        'success': result == 0,
                        'url': url,
                        'info': info
                    }
                    
        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'url': url,
                'error': error_msg
            }

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
                if not hasattr(self, '_pbar'):
                    self._pbar = tqdm(total=100, desc=desc, unit='%')
                self._pbar.n = int(progress * 100)
                self._pbar.set_description(desc)
                self._pbar.refresh()

                # 调用进度回调
                if self.progress_callback:
                    self.progress_callback(progress, desc)

            elif d['status'] == 'finished':
                if hasattr(self, '_pbar'):
                    self._pbar.close()
                    delattr(self, '_pbar')
                logger.info(f"下载完成: {d['filename']}")
                if self.progress_callback:
                    self.progress_callback(1.0, "下载完成")

            elif d['status'] == 'error':
                if hasattr(self, '_pbar'):
                    self._pbar.close()
                    delattr(self, '_pbar')
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
        """验证URL是否为有效的Pornhub链接。

        Args:
            url: 要验证的URL

        Returns:
            bool: 是否为有效的Pornhub链接
        """
        return 'pornhub.com' in url