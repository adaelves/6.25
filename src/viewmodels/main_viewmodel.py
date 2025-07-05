"""主窗口视图模型"""

import os
import asyncio
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, Slot

from src.models.downloader import VideoDownloader
from src.models.database import Database

class MainViewModel(QObject):
    """主窗口视图模型"""
    
    # 信号定义
    download_started = Signal(str)  # 视频标题
    download_progress = Signal(str, int)  # 视频标题, 进度
    download_speed = Signal(int, int)  # 速度(KB/s), 剩余时间(s)
    download_complete = Signal(str, str)  # 视频标题, 文件路径
    download_error = Signal(str, str)  # 视频标题, 错误信息
    
    def __init__(
        self,
        download_path: str = "downloads",
        proxy: Optional[str] = None
    ):
        super().__init__()
        
        # 初始化模型
        self.downloader = VideoDownloader(download_path, proxy)
        self.database = Database()
        
        # 当前下载任务
        self._current_download: Optional[Dict[str, Any]] = None
    
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """下载进度回调
        
        Args:
            d: 进度信息
        """
        if d["status"] == "downloading":
            # 计算下载进度
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            
            if total > 0:
                progress = int(downloaded * 100 / total)
                self.download_progress.emit(
                    self._current_download["title"],
                    progress
                )
            
            # 计算下载速度
            speed = d.get("speed", 0)
            if speed:
                speed_kb = int(speed / 1024)
                eta = d.get("eta", 0)
                self.download_speed.emit(speed_kb, eta)
    
    @Slot(str, str, str)
    async def start_download(
        self,
        url: str,
        format: str = "MP4",
        quality: str = "1080p"
    ) -> None:
        """开始下载视频
        
        Args:
            url: 视频URL
            format: 目标格式
            quality: 视频质量
        """
        try:
            # 获取视频信息
            info = self.downloader.get_video_info(url)
            self._current_download = info
            
            # 发送开始信号
            self.download_started.emit(info["title"])
            
            # 开始下载
            result = await self.downloader.download(
                url,
                format,
                quality,
                self._progress_hook
            )
            
            # 保存到数据库
            self.database.add_download(
                url=url,
                title=result["title"],
                format=format,
                quality=quality,
                file_path=result["file_path"],
                file_size=result["file_size"]
            )
            
            # 发送完成信号
            self.download_complete.emit(
                result["title"],
                result["file_path"]
            )
            
        except Exception as e:
            # 发送错误信号
            if self._current_download:
                self.download_error.emit(
                    self._current_download["title"],
                    str(e)
                )
            else:
                self.download_error.emit("未知视频", str(e))
        
        finally:
            self._current_download = None
    
    @Slot()
    def get_history(self, limit: int = 50, offset: int = 0) -> list:
        """获取下载历史
        
        Args:
            limit: 返回记录数量限制
            offset: 起始偏移
            
        Returns:
            list: 下载记录列表
        """
        return self.database.get_downloads(limit, offset)
    
    @Slot(int)
    def delete_history(self, download_id: int) -> None:
        """删除下载记录
        
        Args:
            download_id: 下载记录ID
        """
        self.database.delete_download(download_id)
    
    @Slot()
    def clear_history(self) -> None:
        """清空下载历史"""
        self.database.clear_history() 