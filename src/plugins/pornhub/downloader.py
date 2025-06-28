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
            cookie_manager=cookie_manager,
            config=config
        )
        
        # 设置yt-dlp
        self._setup_yt_dlp()

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': 'best',  # 选择最佳质量
            'outtmpl': os.path.join(
                str(self.save_dir),
                '%(uploader)s',
                '%(title)s-%(id)s.%(ext)s'
            ),
            
            # 网络设置
            'proxy': self.proxy,
            'socket_timeout': self.timeout,
            'retries': self.max_retries,
            'fragment_retries': self.max_retries,
            
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
            'writethumbnail': True,
            
            # 格式处理
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }, {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }

        # 添加Cookie支持
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("pornhub")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file

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
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
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
                        file_path = self._m3u8_downloader(info['url'], info)
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