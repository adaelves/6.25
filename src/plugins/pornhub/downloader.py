"""Pornhub视频下载器模块。

该模块负责从Pornhub下载视频。
支持m3u8流媒体下载。
"""

import os
import logging
import json
import re
from typing import Optional, Dict, Any, List, Callable, Generator
from pathlib import Path
import yt_dlp
from datetime import datetime
import time
from tqdm import tqdm
import m3u8
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import asyncio
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.downloader import BaseDownloader, DownloadTask, DownloadStatus
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
    - 频道视频批量下载
    
    下载器实现了两种下载方式：
    1. 自定义m3u8下载器：专门处理m3u8流媒体
    2. yt-dlp下载器：作为默认下载器和备选方案
    
    Attributes:
        config: PornhubDownloaderConfig, 下载器配置
    """
    
    # 基础URL
    BASE_URL = "https://cn.pornhub.com"  # 使用中国区域的域名
    
    # URL正则表达式
    CHANNEL_URL_PATTERN = re.compile(
        r"^https?://(?:cn\.)?pornhub\.com/channels/[^/]+(?:/videos)?/?(?:\?.*)?$"
    )
    
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
            proxy=config.proxy or "127.0.0.1:7890",
            timeout=config.timeout or 60,
            max_retries=config.max_retries or 5,
            cookie_manager=cookie_manager,
            config=config
        )
        
        self.config = config
        
        # 确保保存目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置yt-dlp配置
        self.yt_dlp_opts = {
            'format': 'best',  # 选择最佳质量
            'paths': {
                'home': str(self.save_dir),  # 设置主目录
                'temp': str(self.save_dir / 'temp'),  # 临时文件目录
            },
            'outtmpl': {
                'default': str(self.save_dir / '%(title)s.%(ext)s'),  # 默认输出模板
                'chapter': str(self.save_dir / '%(title)s-%(section_number)s.%(ext)s'),  # 章节模板
                'thumbnail': str(self.save_dir / 'thumbnails/%(title)s.%(ext)s'),  # 缩略图模板
            },
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'retries': self.max_retries,
            'socket_timeout': self.timeout,
            'http_chunk_size': 1024 * 1024,  # 1MB
            'buffersize': 1024 * 1024 * 10,  # 10MB
            'proxy': f'http://{self.proxy}' if self.proxy else None,
            'verify': False,
            'nocheckcertificate': True,
            'progress_hooks': [self._progress_hook],
            'concurrent_fragment_downloads': 3,
            'fragment_retries': 10,
            'retry_sleep_functions': {'fragment': lambda n: 1 + n * 2},
            'extractor_retries': 3,
            'file_access_retries': 3,
            'hls_prefer_native': True,
            'hls_split_discontinuity': True,
            'external_downloader_args': ['--timeout', '60'],
        }
        
        # 添加Cookie
        if cookie_manager:
            cookies = cookie_manager.get_cookies("pornhub")
            if cookies:
                # 创建临时cookie文件
                cookie_file = Path("temp_cookies.txt")
                with open(cookie_file, "w") as f:
                    for cookie in cookies:
                        f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                               f"{'TRUE' if cookie.secure else 'FALSE'}\t0\t"
                               f"{cookie.name}\t{cookie.value}\n")
                self.yt_dlp_opts['cookiefile'] = str(cookie_file)
            else:
                # 如果没有特定的cookie，尝试使用默认的请求头
                self.yt_dlp_opts['headers'] = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                }
                
    def _create_session(self) -> requests.Session:
        """创建HTTP会话。
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = super()._create_session()
        
        # 禁用SSL验证
        session.verify = False
        
        # 设置重试策略
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504, 429],
            allowed_methods=["GET", "POST", "HEAD"]
        )
        
        # 创建适配器
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False
        )
        
        # 配置适配器
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 更新请求头
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        })
        
        return session

    def _m3u8_downloader(self, m3u8_url: str, info: Dict[str, Any]) -> str:
        """自定义m3u8下载器。

        专门用于处理m3u8流媒体下载，支持：
        - 自动提取base_uri
        - 片段重试和恢复
        - 详细的进度显示
        - 自定义HTTP头
        - 视频格式转换

        Args:
            m3u8_url: m3u8文件URL
            info: 视频信息字典

        Returns:
            str: 下载的文件路径

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 从info中提取必要信息
            uploader = info.get('uploader', 'unknown')
            title = info.get('title', 'untitled')
            video_id = info.get('id', '')
            
            # 创建上传者目录
            uploader_dir = self.save_dir / self._sanitize_filename(uploader)
            uploader_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成临时ts文件路径
            temp_ts = uploader_dir / f"{video_id}_temp.ts"
            
            # 生成最终mp4文件路径
            final_filename = f"{self._sanitize_filename(title)}-{video_id}.mp4"
            output_file = uploader_dir / final_filename

            # 下载m3u8文件
            response = requests.get(
                m3u8_url,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 从URL中提取base_uri
            parsed_url = urlparse(m3u8_url)
            base_uri = f"{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/"
            
            # 解析m3u8
            playlist = m3u8.loads(response.text)
            if not playlist or not playlist.segments:
                raise DownloadError("无效的m3u8文件")
                
            # 准备下载
            total_segments = len(playlist.segments)
            downloaded = 0
            
            # 下载所有片段
            with open(temp_ts, 'wb') as f:
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
                    for retry in range(self.max_retries):
                        try:
                            segment_response = requests.get(
                                segment_url,
                                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                                timeout=self.timeout,
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
                            if retry == self.max_retries - 1:
                                raise DownloadError(f"下载片段失败: {str(e)}")
                            logger.warning(f"下载片段失败，重试 {retry + 1}/{self.max_retries}: {str(e)}")
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
                
            # 转换格式
            try:
                import ffmpeg
                
                # 更新进度
                if self.progress_callback:
                    self.progress_callback(0.95, "正在转换视频格式...")
                
                # 使用ffmpeg转换为mp4
                stream = ffmpeg.input(str(temp_ts))
                stream = ffmpeg.output(stream, str(output_file), acodec='copy', vcodec='copy')
                ffmpeg.run(stream, quiet=True, overwrite_output=True)
                
                # 删除临时ts文件
                temp_ts.unlink()
                
                logger.info(f"下载完成: {output_file}")
                return str(output_file)
                
            except Exception as e:
                logger.error(f"格式转换失败: {str(e)}")
                # 如果转换失败，保留ts文件并重命名
                temp_ts.rename(uploader_dir / f"{self._sanitize_filename(title)}-{video_id}.ts")
                return str(temp_ts)
            
        except requests.exceptions.RequestException as e:
            raise DownloadError(f"网络请求失败: {str(e)}")
        except m3u8.ParseError as e:
            raise DownloadError(f"解析m3u8文件失败: {str(e)}")
        except Exception as e:
            raise DownloadError(f"m3u8下载失败: {str(e)}")

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符。
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 替换非法字符
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
            
        # 移除前后空格
        filename = filename.strip()
        
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = 'untitled'
            
        return filename

    async def download(self, url: str) -> Dict[str, Any]:
        """下载视频。

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 下载结果信息

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                raise DownloadError("不支持的URL格式")

            # 使用yt-dlp下载
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                try:
                    # 提取视频信息
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: ydl.extract_info(url, download=False)
                    )
                    
                    if not info:
                        raise DownloadError("无法获取视频信息")

                    # 下载视频
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: ydl.download([url])
                    )

                    return {
                        'success': True,
                        'title': info.get('title', ''),
                        'uploader': info.get('uploader', ''),
                        'duration': info.get('duration', 0),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'format': info.get('format', ''),
                        'url': url,
                        'download_path': str(self.save_dir / f"{info.get('title', 'video')}.mp4")
                    }

                except Exception as e:
                    logger.error(f"yt-dlp下载失败: {str(e)}")
                    # 如果yt-dlp失败，尝试使用m3u8下载器
                    if 'm3u8' in str(e).lower() or 'hls' in str(e).lower():
                        logger.info("尝试使用m3u8下载器")
                        return await self._m3u8_downloader(url, info)
                    raise DownloadError(str(e))

        except DownloadError as e:
            # 直接重新抛出 DownloadError
            raise e
        except Exception as e:
            logger.error(f"下载失败: {url} -> {str(e)}")
            raise DownloadError(str(e))

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

    def download_user(self, url: str) -> Dict[str, Any]:
        """下载用户/频道的所有视频。

        Args:
            url: 用户/频道URL

        Returns:
            Dict[str, Any]: 下载结果，包含：
                - success: 是否成功
                - url: 原始URL
                - downloaded: 成功下载数量
                - failed: 失败数量
                - videos: 视频列表

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                logger.error(f"无效的URL格式: {url}")
                raise DownloadError("不支持的URL格式")
                
            logger.info(f"开始下载用户/频道视频: {url}")
            
            # 配置yt-dlp选项
            opts = self.yt_dlp_opts.copy()
            opts.update({
                'extract_flat': True,  # 只提取视频信息，不下载
                'quiet': True,
                'no_warnings': True
            })
            
            # 获取视频列表
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    # 更新进度
                    if self.progress_callback:
                        self.progress_callback(0.0, "正在获取视频列表...")
                    
                    logger.info("正在提取视频列表...")
                    # 获取用户/频道信息
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        logger.error("无法获取用户/频道信息")
                        raise DownloadError("无法获取用户/频道信息")
                        
                    # 获取视频列表
                    videos = []
                    if 'entries' in info:
                        videos = list(info['entries'])
                        logger.info(f"找到 {len(videos)} 个视频")
                    else:
                        videos = [info]
                        logger.info("找到 1 个视频")
                        
                    if not videos:
                        logger.info("没有找到任何视频")
                        return {
                            'success': True,
                            'url': url,
                            'downloaded': 0,
                            'failed': 0,
                            'videos': []
                        }
                        
                    # 下载每个视频
                    total = len(videos)
                    downloaded = 0
                    failed = 0
                    results = []
                    
                    for i, video in enumerate(videos, 1):
                        try:
                            # 更新进度
                            progress = i / total
                            status = f"正在下载第 {i}/{total} 个视频"
                            if self.progress_callback:
                                self.progress_callback(progress, status)
                            logger.info(status)
                                
                            # 获取视频URL
                            video_url = video.get('webpage_url') or video.get('url')
                            video_title = video.get('title', 'unknown')
                            
                            if not video_url:
                                logger.warning(f"跳过无效视频: {video_title}")
                                failed += 1
                                continue
                                
                            logger.info(f"开始下载视频: {video_title}")
                            # 下载视频
                            result = self.download(video_url)
                            results.append(result)
                            
                            if result['success']:
                                downloaded += 1
                                logger.info(f"视频下载成功: {video_title}")
                            else:
                                failed += 1
                                logger.error(f"视频下载失败: {video_title} - {result.get('error', '未知错误')}")
                                
                        except Exception as e:
                            logger.error(f"下载视频失败: {str(e)}")
                            failed += 1
                            
                        # 报告当前进度
                        logger.info(f"当前进度: 成功 {downloaded} 个，失败 {failed} 个，总共 {total} 个")
                            
                    # 完成下载
                    final_status = f"下载完成: 成功 {downloaded} 个，失败 {failed} 个，总共 {total} 个"
                    logger.info(final_status)
                    if self.progress_callback:
                        self.progress_callback(1.0, final_status)
                        
                    return {
                        'success': downloaded > 0,
                        'url': url,
                        'downloaded': downloaded,
                        'failed': failed,
                        'videos': results
                    }
                    
                except yt_dlp.utils.DownloadError as e:
                    error_msg = f"获取视频列表失败: {str(e)}"
                    logger.error(error_msg)
                    raise DownloadError(error_msg)
                    
        except Exception as e:
            error_msg = f"下载用户/频道视频失败: {str(e)}"
            logger.error(error_msg)
            if self.progress_callback:
                self.progress_callback(0.0, f"错误: {error_msg}")
            return {
                'success': False,
                'url': url,
                'error': error_msg,
                'downloaded': 0,
                'failed': 0,
                'videos': []
            }

    def _validate_channel_url(self, url: str) -> bool:
        """验证频道URL格式。
        
        Args:
            url: 频道URL
            
        Returns:
            bool: URL是否有效
        """
        return bool(self.CHANNEL_URL_PATTERN.match(url))
        
    def _normalize_channel_url(self, url: str) -> str:
        """标准化频道URL。
        
        Args:
            url: 原始URL
            
        Returns:
            str: 标准化后的URL
        """
        # 确保URL以/videos结尾
        if not url.endswith('/videos'):
            url = url.rstrip('/') + '/videos'
            
        # 解析URL
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        # 设置默认参数
        query.update({
            'o': ['mr'],  # 最近上传
            't': ['a']    # 所有时间
        })
        
        # 重建URL
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(query, doseq=True)}"
        
    def _extract_channel_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """提取频道信息。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Dict[str, Any]: 频道信息
        """
        info = {
            'title': '',
            'description': '',
            'subscriber_count': 0,
            'video_count': 0
        }
        
        try:
            # 提取频道标题
            title_elem = soup.find('h1', class_='channelsHeader')
            if title_elem:
                info['title'] = title_elem.get_text(strip=True)
                
            # 提取频道描述
            desc_elem = soup.find('div', class_='descriptionContainer')
            if desc_elem:
                info['description'] = desc_elem.get_text(strip=True)
                
            # 提取订阅数
            sub_elem = soup.find('span', class_='subsCount')
            if sub_elem:
                sub_text = sub_elem.get_text(strip=True)
                info['subscriber_count'] = self._parse_count(sub_text)
                
            # 提取视频数
            count_elem = soup.find('span', class_='videosCount')
            if count_elem:
                count_text = count_elem.get_text(strip=True)
                info['video_count'] = self._parse_count(count_text)
                
        except Exception as e:
            logger.warning(f"提取频道信息时出错: {e}")
            
        return info
        
    def _parse_count(self, text: str) -> int:
        """解析数字文本。
        
        Args:
            text: 数字文本(如"1.2K", "3.5M")
            
        Returns:
            int: 实际数字
        """
        try:
            text = text.strip().upper()
            if 'K' in text:
                return int(float(text.replace('K', '')) * 1000)
            elif 'M' in text:
                return int(float(text.replace('M', '')) * 1000000)
            else:
                return int(float(text))
        except:
            return 0
            
    def _get_channel_videos(self, url: str) -> Generator[str, None, None]:
        """获取频道视频列表。
        
        Args:
            url: 频道URL
            
        Yields:
            str: 视频URL
            
        Raises:
            DownloadError: 获取视频列表失败
        """
        page = 1
        while True:
            try:
                # 构建页面URL
                page_url = f"{url}&page={page}"
                
                # 获取页面内容
                response = self.session.get(
                    page_url,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # 解析页面
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 提取视频链接
                video_links = soup.find_all('a', class_='videoTitle')
                if not video_links:
                    break
                    
                # 生成视频URL
                for link in video_links:
                    video_url = urljoin(self.BASE_URL, link['href'])
                    yield video_url
                    
                # 检查是否有下一页
                next_button = soup.find('li', class_='page_next')
                if not next_button or 'disabled' in next_button.get('class', []):
                    break
                    
                page += 1
                
            except requests.RequestException as e:
                raise DownloadError(
                    f"获取频道视频列表失败: {str(e)}",
                    "network",
                    "请检查网络连接或重试",
                    {
                        "页码": page,
                        "URL": page_url
                    }
                )
            except Exception as e:
                raise DownloadError(
                    f"解析频道页面失败: {str(e)}",
                    "format",
                    "请检查URL是否正确",
                    {
                        "页码": page,
                        "URL": page_url
                    }
                )
                
    async def download_channel(
        self,
        url: str,
        max_videos: Optional[int] = None,
        download_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """下载频道视频。
        
        Args:
            url: 频道URL
            max_videos: 最大下载视频数，None表示无限制
            download_dir: 下载目录，None使用默认目录
            
        Returns:
            Dict[str, Any]: 下载结果统计
            
        Raises:
            ValueError: URL无效
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_channel_url(url):
                raise ValueError(f"无效的频道URL: {url}")
                
            # 标准化URL
            url = self._normalize_channel_url(url)
            
            # 获取频道信息
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            channel_info = self._extract_channel_info(soup)
            
            # 设置下载目录
            if download_dir:
                original_dir = self.save_dir
                self.save_dir = download_dir
                
            # 初始化统计信息
            stats = {
                'channel_info': channel_info,
                'total_videos': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [],
                'tasks': []
            }
            
            try:
                # 下载视频
                for video_url in self._get_channel_videos(url):
                    # 检查是否达到最大数量
                    if max_videos and stats['total_videos'] >= max_videos:
                        break
                        
                    stats['total_videos'] += 1
                    
                    try:
                        # 异步下载视频
                        task_id = await self.async_download(video_url)
                        stats['tasks'].append(task_id)
                        
                        # 等待下载完成
                        while True:
                            task = self.get_download_status(task_id)
                            if task.status == DownloadStatus.COMPLETED:
                                stats['successful'] += 1
                                break
                            elif task.status == DownloadStatus.FAILED:
                                stats['failed'] += 1
                                if task.error:
                                    stats['errors'].append(str(task.error))
                                break
                            elif task.status == DownloadStatus.CANCELED:
                                stats['skipped'] += 1
                                break
                            await asyncio.sleep(1)
                            
                    except Exception as e:
                        stats['failed'] += 1
                        stats['errors'].append(str(e))
                        logger.error(f"下载视频失败: {video_url} -> {e}")
                        
            finally:
                # 恢复原始下载目录
                if download_dir:
                    self.save_dir = original_dir
                    
            return stats
            
        except Exception as e:
            raise DownloadError(
                f"下载频道失败: {str(e)}",
                "channel",
                "请检查频道URL是否正确",
                {
                    "URL": url,
                    "错误": str(e)
                }
            )