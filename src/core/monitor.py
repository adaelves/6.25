from typing import Dict, Any, List, Optional
import threading
import time
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class CreatorMonitor:
    """创作者监控服务。"""
    
    def __init__(self, settings: Dict[str, Any]):
        """初始化监控服务。
        
        Args:
            settings: 配置信息
        """
        self.settings = settings
        self._stop = False
        self._thread = None
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def start(self):
        """启动监控。"""
        if self._thread is not None:
            return
            
        self._stop = False
        self._thread = threading.Thread(target=self._monitor_loop)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """停止监控。"""
        self._stop = True
        if self._thread is not None:
            self._thread.join()
            self._thread = None
            
    def _monitor_loop(self):
        """监控循环。"""
        while not self._stop:
            try:
                # 获取创作者列表
                creators = self.settings.get('monitor.creators', [])
                
                # 检查每个创作者
                for creator in creators:
                    if self._stop:
                        break
                        
                    try:
                        # 获取最新视频
                        latest_video = self._get_latest_video(creator)
                        
                        if latest_video:
                            # 更新创作者信息
                            creator['latest_video'] = latest_video
                            
                            # 保存设置
                            self.settings.set('monitor.creators', creators)
                            
                    except Exception as e:
                        logger.error(f"检查创作者失败: {e}")
                        
                # 等待下一次检查
                for _ in range(300):  # 5分钟
                    if self._stop:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"监控循环失败: {e}")
                
    def _get_latest_video(self, creator: Dict[str, Any]) -> Optional[str]:
        """获取最新视频。
        
        Args:
            creator: 创作者信息
            
        Returns:
            str: 视频链接
        """
        platform = creator['platform'].lower()
        creator_id = creator['id']
        
        if platform == 'youtube':
            return self._get_youtube_video(creator_id)
        elif platform == 'twitter':
            return self._get_twitter_video(creator_id)
        elif platform == 'bilibili':
            return self._get_bilibili_video(creator_id)
            
        return None
        
    def _get_youtube_video(self, channel_id: str) -> Optional[str]:
        """获取YouTube最新视频。
        
        Args:
            channel_id: 频道ID
            
        Returns:
            str: 视频链接
        """
        try:
            # 获取频道页面
            url = f'https://www.youtube.com/channel/{channel_id}/videos'
            response = self._session.get(url)
            response.raise_for_status()
            
            # 提取视频链接
            import re
            pattern = r'href="/watch\?v=([^"]+)"'
            match = re.search(pattern, response.text)
            
            if match:
                return f'https://www.youtube.com/watch?v={match.group(1)}'
                
        except Exception as e:
            logger.error(f"获取YouTube视频失败: {e}")
            
        return None
        
    def _get_twitter_video(self, user_id: str) -> Optional[str]:
        """获取Twitter最新视频。
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 视频链接
        """
        try:
            # 获取用户页面
            url = f'https://twitter.com/{user_id}'
            response = self._session.get(url)
            response.raise_for_status()
            
            # 提取视频链接
            import re
            pattern = r'href="/[^/]+/status/(\d+)"'
            match = re.search(pattern, response.text)
            
            if match:
                return f'https://twitter.com/{user_id}/status/{match.group(1)}'
                
        except Exception as e:
            logger.error(f"获取Twitter视频失败: {e}")
            
        return None
        
    def _get_bilibili_video(self, user_id: str) -> Optional[str]:
        """获取Bilibili最新视频。
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 视频链接
        """
        try:
            # 获取用户信息
            url = f'https://api.bilibili.com/x/space/acc/info?mid={user_id}'
            response = self._session.get(url)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] != 0:
                raise ValueError(data['message'])
                
            # 获取最新视频
            url = f'https://api.bilibili.com/x/space/arc/search?mid={user_id}&ps=1&pn=1'
            response = self._session.get(url)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] != 0:
                raise ValueError(data['message'])
                
            videos = data['data']['list']['vlist']
            if videos:
                return f'https://www.bilibili.com/video/{videos[0]["bvid"]}'
                
        except Exception as e:
            logger.error(f"获取Bilibili视频失败: {e}")
            
        return None 