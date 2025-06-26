"""B站视频下载器模块。

该模块负责从B站下载视频和弹幕。
"""

import os
import time
import json
import logging
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from src.core.downloader import BaseDownloader
from src.core.exceptions import (
    BiliBiliError,
    NetworkError,
    DownloadCanceled
)
from src.core.config import DownloaderConfig
from src.core.speed_limiter import SpeedLimiter
from .extractor import BilibiliExtractor
from .danmaku import download_danmaku

logger = logging.getLogger(__name__)

class BilibiliDownloader(BaseDownloader):
    """B站视频下载器。
    
    继承自BaseDownloader，实现B站视频的下载功能。
    支持多分辨率选择、自动合并分段和弹幕下载。
    支持速度限制和并发控制。
    
    Attributes:
        config: DownloaderConfig, 下载器配置
        extractor: BilibiliExtractor, 视频信息提取器
        ffmpeg_path: str, FFmpeg可执行文件路径
        speed_limiter: Optional[SpeedLimiter], 速度限制器
    """
    
    # 清晰度代码映射
    QUALITY_MAP = {
        120: "4K",
        116: "1080P60",
        80: "1080P",
        74: "720P60",
        64: "720P",
        32: "480P",
        16: "360P"
    }
    
    def __init__(
        self,
        config: DownloaderConfig,
        sessdata: Optional[str] = None,
        ffmpeg_path: str = "ffmpeg"
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            sessdata: B站登录凭证，用于下载高清晰度视频
            ffmpeg_path: FFmpeg可执行文件路径
        """
        super().__init__(save_dir=str(config.save_dir))
        self.config = config
        self.extractor = BilibiliExtractor(sessdata=sessdata)
        self.ffmpeg_path = ffmpeg_path
        self.speed_limiter = (
            SpeedLimiter(config.speed_limit) if config.speed_limit > 0 else None
        )
        self._temp_files = set()
        
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 包含视频信息的字典
                
        Raises:
            ValueError: URL格式无效
            ConnectionError: 网络连接错误
            TimeoutError: 请求超时
        """
        try:
            info = self.extractor.extract_info(url)
            if not info:
                raise ValueError(f"无法获取视频信息: {url}")
                
            return {
                "title": info.get("title", ""),
                "author": info.get("owner", {}).get("name", ""),
                "quality": self.QUALITY_MAP.get(
                    info.get("quality", 0), 
                    "未知"
                ),
                "duration": info.get("duration", 0),
                "description": info.get("desc", "")
            }
            
        except BiliBiliError as e:
            raise ConnectionError(str(e))
        except Exception as e:
            raise ValueError(str(e))
        
    def download(
        self,
        url: str,
        save_path: Path,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """下载B站视频。
        
        Args:
            url: 视频URL
            save_path: 保存路径
            progress_callback: 进度回调函数，参数为0~1的浮点数
            cancel_event: 取消事件，用于取消下载
            
        Returns:
            bool: 下载是否成功
            
        Raises:
            ValueError: URL无效
            RuntimeError: 下载失败
            DownloadCanceled: 用户取消下载
        """
        try:
            # 获取视频信息
            info = self.extractor.extract_info(url)
            if not info:
                raise ValueError(f"无法获取视频信息: {url}")
                
            # 检查是否是大会员专享视频
            if self._is_vip_only(info) and not self.extractor.sessdata:
                raise RuntimeError("该视频需要大会员权限")
                
            # 检查地区限制
            if self._is_area_limited(info):
                raise RuntimeError("该视频在当前地区不可用")
                
            # 获取视频流信息
            streams = self._get_video_streams(info["bvid"], info["cid"])
            if not streams:
                raise RuntimeError("无法获取视频流信息")
                
            # 选择最高画质
            stream = self._select_best_quality(streams)
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 下载视频分段
                segment_files = self._download_segments(
                    stream["segments"],
                    Path(temp_dir),
                    progress_callback,
                    cancel_event
                )
                
                if not segment_files:
                    if cancel_event and cancel_event.is_set():
                        raise DownloadCanceled("用户取消下载")
                    raise RuntimeError("视频分段下载失败")
                    
                # 合并视频分段
                if not self._merge_segments(segment_files, save_path):
                    raise RuntimeError("视频合并失败")
                    
                # 下载弹幕
                danmaku_path = save_path.with_suffix(".xml")
                if not download_danmaku(info["cid"], danmaku_path):
                    logger.warning("弹幕下载失败")
                    
            return True
            
        except DownloadCanceled:
            self._clean_temp_files()
            return False
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self._clean_temp_files()
            return False
            
    def _is_vip_only(self, info: Dict[str, Any]) -> bool:
        """检查是否是大会员专享视频。
        
        Args:
            info: 视频信息
            
        Returns:
            bool: 是否是大会员专享
        """
        return info.get("is_vip_only", False)
        
    def _is_area_limited(self, info: Dict[str, Any]) -> bool:
        """检查是否有地区限制。
        
        Args:
            info: 视频信息
            
        Returns:
            bool: 是否有地区限制
        """
        return info.get("is_area_limited", False)
        
    def _get_video_streams(self, bvid: str, cid: str) -> List[Dict[str, Any]]:
        """获取视频流信息。
        
        Args:
            bvid: BV号
            cid: 视频CID
            
        Returns:
            List[Dict[str, Any]]: 视频流信息列表
        """
        try:
            params = {
                "bvid": bvid,
                "cid": cid,
                "qn": 120,  # 请求最高画质
                "fnval": 16  # 返回dash格式
            }
            
            response = self._make_request(
                "https://api.bilibili.com/x/player/playurl",
                params=params
            )
            
            if response["code"] != 0:
                raise RuntimeError(f"获取视频流失败: {response['message']}")
                
            return response["data"]["dash"]["video"]
            
        except Exception as e:
            logger.error(f"获取视频流失败: {e}")
            return []
            
    def _select_best_quality(self, streams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """选择最佳画质。
        
        Args:
            streams: 视频流列表
            
        Returns:
            Dict[str, Any]: 选中的视频流
            
        Raises:
            RuntimeError: 无可用视频流
        """
        if not streams:
            raise RuntimeError("无可用视频流")
            
        # 按清晰度排序
        streams.sort(key=lambda x: x["quality"], reverse=True)
        
        # 选择可用的最高清晰度
        for stream in streams:
            if self._check_stream_availability(stream):
                return stream
                
        raise RuntimeError("所有视频流均不可用")
        
    def _check_stream_availability(self, stream: Dict[str, Any]) -> bool:
        """检查视频流是否可用。
        
        Args:
            stream: 视频流信息
            
        Returns:
            bool: 是否可用
        """
        try:
            response = requests.head(
                stream["base_url"],
                headers=self.extractor.headers,
                proxies=self.extractor.proxies,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
            
    def _download_segments(
        self,
        segments: List[Dict[str, Any]],
        temp_dir: Path,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> List[Path]:
        """下载视频分段。
        
        Args:
            segments: 分段信息列表
            temp_dir: 临时目录
            progress_callback: 进度回调函数
            cancel_event: 取消事件
            
        Returns:
            List[Path]: 分段文件路径列表
            
        Raises:
            DownloadCanceled: 用户取消下载
        """
        segment_files = []
        total_segments = len(segments)
        
        with ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_downloads
        ) as executor:
            futures = []
            
            for i, segment in enumerate(segments):
                segment_path = temp_dir / f"segment_{i:03d}.m4s"
                self._temp_files.add(segment_path)
                
                future = executor.submit(
                    self._download_segment,
                    segment["base_url"],
                    segment_path,
                    cancel_event
                )
                futures.append((future, segment_path, i))
                
            for future, path, index in futures:
                try:
                    if cancel_event and cancel_event.is_set():
                        raise DownloadCanceled("用户取消下载")
                        
                    if future.result():
                        segment_files.append(path)
                        progress = (index + 1) / total_segments
                        self.update_progress(
                            progress,
                            f"下载进度: {index + 1}/{total_segments} 个分段"
                        )
                    else:
                        return []
                except DownloadCanceled:
                    raise
                except Exception as e:
                    logger.error(f"分段下载失败: {e}")
                    return []
                    
        return sorted(segment_files)
        
    def _download_segment(
        self,
        url: str,
        save_path: Path,
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """下载视频分段。
        
        Args:
            url: 分段URL
            save_path: 保存路径
            cancel_event: 取消事件
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadCanceled: 用户取消下载
        """
        try:
            response = requests.get(
                url,
                headers=self.extractor.headers,
                proxies=self.extractor.proxies,
                stream=True,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                    if cancel_event and cancel_event.is_set():
                        raise DownloadCanceled("用户取消下载")
                        
                    if self.speed_limiter:
                        self.speed_limiter.wait_sync(len(chunk))
                        
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    if total_size:
                        progress = downloaded_size / total_size
                        speed = (
                            self.speed_limiter.current_speed if self.speed_limiter
                            else 0
                        )
                        self.update_progress(
                            progress,
                            f"下载进度: {downloaded_size}/{total_size} bytes"
                            f" ({speed/1024:.1f} KB/s)"
                        )
                        
            return True
            
        except Exception as e:
            logger.error(f"下载分段失败: {e}")
            if save_path.exists():
                save_path.unlink()
            return False
            
    def _merge_segments(
        self,
        segment_files: List[Path],
        output_path: Path
    ) -> bool:
        """合并视频分段。
        
        Args:
            segment_files: 分段文件路径列表
            output_path: 输出文件路径
            
        Returns:
            bool: 是否合并成功
        """
        try:
            # 准备FFmpeg命令
            concat_file = output_path.with_suffix(".txt")
            self._temp_files.add(concat_file)
            
            # 写入concat文件
            with open(concat_file, "w", encoding="utf-8") as f:
                for file in segment_files:
                    f.write(f"file '{file.absolute()}'\n")
                    
            # 执行合并
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-y",
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"合并失败: {result.stderr}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"合并失败: {e}")
            return False
            
    def _make_request(self, url: str, **kwargs) -> Dict[str, Any]:
        """发送API请求。
        
        Args:
            url: API地址
            **kwargs: 请求参数
            
        Returns:
            Dict[str, Any]: 响应数据
            
        Raises:
            RuntimeError: 请求失败
        """
        try:
            response = requests.get(
                url,
                headers=self.extractor.headers,
                proxies=self.extractor.proxies,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            
            data = response.json()
            if data["code"] != 0:
                raise RuntimeError(f"API请求失败: {data['message']}")
                
            return data
            
        except Exception as e:
            logger.error(f"请求失败 {url}: {e}")
            raise RuntimeError(f"API请求失败: {e}")
            
    def _clean_temp_files(self):
        """清理临时文件。"""
        for path in self._temp_files.copy():
            try:
                if path.exists():
                    path.unlink()
                self._temp_files.remove(path)
            except Exception as e:
                logger.error(f"清理临时文件失败 {path}: {e}")
                
        self._temp_files.clear() 