import asyncio
import aiohttp
import os
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class DownloadTask:
    """下载任务数据类"""
    url: str
    title: str
    save_path: str
    total_size: int = 0
    downloaded_size: int = 0
    status: str = "waiting"  # waiting, downloading, paused, completed, error
    speed: int = 0  # bytes per second
    error_message: str = ""
    create_time: datetime = datetime.now()
    complete_time: Optional[datetime] = None
    thumbnail_url: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "save_path": self.save_path,
            "total_size": self.total_size,
            "downloaded_size": self.downloaded_size,
            "status": self.status,
            "speed": self.speed,
            "error_message": self.error_message,
            "create_time": self.create_time.isoformat(),
            "complete_time": self.complete_time.isoformat() if self.complete_time else None,
            "thumbnail_url": self.thumbnail_url
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DownloadTask":
        """从字典创建任务"""
        data["create_time"] = datetime.fromisoformat(data["create_time"])
        if data["complete_time"]:
            data["complete_time"] = datetime.fromisoformat(data["complete_time"])
        return cls(**data)

class DownloadManager:
    """下载管理器"""
    def __init__(self, config_manager):
        self.config = config_manager
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.download_path = Path(self.config.get_download_path())
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        # 加载历史记录
        self.history_file = self.download_path / "history.json"
        self.load_history()
    
    def load_history(self):
        """加载下载历史"""
        if not self.history_file.exists():
            return
            
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                for task_data in history:
                    task = DownloadTask.from_dict(task_data)
                    if task.status == "completed":
                        self.tasks[task.url] = task
        except Exception as e:
            print(f"加载下载历史失败: {e}")
    
    def save_history(self):
        """保存下载历史"""
        try:
            history = [
                task.to_dict()
                for task in self.tasks.values()
                if task.status == "completed"
            ]
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存下载历史失败: {e}")
    
    async def start(self):
        """启动下载管理器"""
        if self.session is None:
            # 设置代理
            proxy_settings = self.config.get_proxy_settings()
            proxy = None
            if proxy_settings["enabled"]:
                proxy = f"http://{proxy_settings['address']}"
            
            # 创建会话
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                trust_env=True,
                proxy=proxy
            )
    
    async def stop(self):
        """停止下载管理器"""
        if self.session:
            await self.session.close()
            self.session = None
        
        # 保存历史记录
        self.save_history()
    
    def add_task(self, url: str, title: str, thumbnail_url: str = "") -> DownloadTask:
        """添加下载任务"""
        if url in self.tasks:
            return self.tasks[url]
            
        save_path = self.download_path / f"{title}.mp4"
        # 如果文件已存在，添加序号
        index = 1
        while save_path.exists():
            save_path = self.download_path / f"{title}_{index}.mp4"
            index += 1
            
        task = DownloadTask(
            url=url,
            title=title,
            save_path=str(save_path),
            thumbnail_url=thumbnail_url
        )
        self.tasks[url] = task
        return task
    
    async def start_task(self, url: str, progress_callback: Optional[Callable] = None):
        """开始下载任务"""
        if url not in self.tasks:
            raise ValueError(f"任务不存在: {url}")
            
        task = self.tasks[url]
        if task.status == "downloading":
            return
            
        task.status = "downloading"
        download_task = asyncio.create_task(
            self._download_task(task, progress_callback)
        )
        self.active_tasks[url] = download_task
    
    async def pause_task(self, url: str):
        """暂停下载任务"""
        if url in self.active_tasks:
            self.active_tasks[url].cancel()
            del self.active_tasks[url]
            self.tasks[url].status = "paused"
    
    async def resume_task(self, url: str, progress_callback: Optional[Callable] = None):
        """恢复下载任务"""
        if url not in self.tasks:
            raise ValueError(f"任务不存在: {url}")
            
        task = self.tasks[url]
        if task.status != "paused":
            return
            
        await self.start_task(url, progress_callback)
    
    async def cancel_task(self, url: str):
        """取消下载任务"""
        if url in self.active_tasks:
            self.active_tasks[url].cancel()
            del self.active_tasks[url]
        
        if url in self.tasks:
            task = self.tasks[url]
            task.status = "cancelled"
            # 删除已下载的文件
            try:
                os.remove(task.save_path)
            except:
                pass
            del self.tasks[url]
    
    async def _download_task(self, task: DownloadTask, progress_callback: Optional[Callable] = None):
        """下载任务的具体实现"""
        if self.session is None:
            await self.start()
            
        try:
            async with self.session.get(task.url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"HTTP {response.status}")
                    
                # 获取文件大小
                task.total_size = int(response.headers.get("content-length", 0))
                
                # 创建文件
                async with aiohttp.StreamReader(response.content) as reader:
                    with open(task.save_path, "wb") as f:
                        chunk_size = self.config.get("download.chunk_size", 1024 * 1024)
                        while True:
                            chunk = await reader.read(chunk_size)
                            if not chunk:
                                break
                                
                            # 写入文件
                            f.write(chunk)
                            
                            # 更新进度
                            task.downloaded_size += len(chunk)
                            
                            # 计算速度
                            task.speed = len(chunk)  # 这里需要改进，使用时间窗口计算平均速度
                            
                            # 回调通知进度
                            if progress_callback:
                                progress_callback(task)
                                
                            # 检查是否需要限速
                            speed_limit = self.config.get_speed_limit()
                            if speed_limit > 0 and task.speed > speed_limit * 1024:
                                await asyncio.sleep(0.1)
                
                # 下载完成
                task.status = "completed"
                task.complete_time = datetime.now()
                task.speed = 0
                
                # 保存历史记录
                self.save_history()
                
        except asyncio.CancelledError:
            task.status = "paused"
            raise
            
        except Exception as e:
            task.status = "error"
            task.error_message = str(e)
            raise
            
        finally:
            if task.url in self.active_tasks:
                del self.active_tasks[task.url]
            
            # 最后一次回调，通知状态变化
            if progress_callback:
                progress_callback(task)
    
    def get_task(self, url: str) -> Optional[DownloadTask]:
        """获取任务信息"""
        return self.tasks.get(url)
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_active_tasks(self) -> List[DownloadTask]:
        """获取正在下载的任务"""
        return [
            task for task in self.tasks.values()
            if task.status == "downloading"
        ]
    
    def get_completed_tasks(self) -> List[DownloadTask]:
        """获取已完成的任务"""
        return [
            task for task in self.tasks.values()
            if task.status == "completed"
        ]
    
    def get_failed_tasks(self) -> List[DownloadTask]:
        """获取失败的任务"""
        return [
            task for task in self.tasks.values()
            if task.status == "error"
        ] 