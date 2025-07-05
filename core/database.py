"""数据库管理模块"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from .models import DownloadHistory, VideoInfo, CreatorInfo

class DatabaseManager:
    """数据库管理类"""
    def __init__(self, db_path: str = "history.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("DatabaseManager")
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # 创建创作者表
                c.execute('''CREATE TABLE IF NOT EXISTS creators (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    avatar_url TEXT,
                    description TEXT
                )''')
                
                # 创建视频信息表
                c.execute('''CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    creator_id TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    publish_time TEXT NOT NULL,
                    thumbnail_url TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    FOREIGN KEY (creator_id) REFERENCES creators (id)
                )''')
                
                # 创建下载历史表
                c.execute('''CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    download_time TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    duration INTEGER NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos (id)
                )''')
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise
    
    def add_download_history(self, history: DownloadHistory) -> bool:
        """添加下载历史记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # 1. 保存创作者信息
                c.execute('''INSERT OR REPLACE INTO creators 
                           (id, name, platform, avatar_url, description)
                           VALUES (?, ?, ?, ?, ?)''',
                        (history.video.creator.id,
                         history.video.creator.name,
                         history.video.creator.platform,
                         history.video.creator.avatar_url,
                         history.video.creator.description))
                
                # 2. 保存视频信息
                c.execute('''INSERT OR REPLACE INTO videos
                           (id, title, description, creator_id, duration,
                            publish_time, thumbnail_url, view_count, like_count)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (history.video.id,
                         history.video.title,
                         history.video.description,
                         history.video.creator.id,
                         history.video.duration,
                         history.video.publish_time.isoformat(),
                         history.video.thumbnail_url,
                         history.video.view_count,
                         history.video.like_count))
                
                # 3. 保存下载历史
                c.execute('''INSERT INTO download_history
                           (video_id, download_time, save_path, file_size, duration)
                           VALUES (?, ?, ?, ?, ?)''',
                        (history.video.id,
                         history.download_time.isoformat(),
                         history.save_path,
                         history.file_size,
                         history.duration))
                
                conn.commit()
                self.logger.info(f"Added download history for video: {history.video.title}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error adding download history: {e}")
            return False
    
    def get_download_history(self, limit: int = 100) -> List[DownloadHistory]:
        """获取下载历史记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                query = '''
                    SELECT 
                        h.*,
                        v.*,
                        c.*
                    FROM download_history h
                    JOIN videos v ON h.video_id = v.id
                    JOIN creators c ON v.creator_id = c.id
                    ORDER BY h.download_time DESC
                    LIMIT ?
                '''
                
                c.execute(query, (limit,))
                rows = c.fetchall()
                
                history_list = []
                for row in rows:
                    # 构建创作者信息
                    creator = CreatorInfo(
                        id=row['id'],
                        name=row['name'],
                        platform=row['platform'],
                        avatar_url=row['avatar_url'],
                        description=row['description']
                    )
                    
                    # 构建视频信息
                    video = VideoInfo(
                        id=row['id'],
                        title=row['title'],
                        description=row['description'],
                        creator=creator,
                        duration=row['duration'],
                        publish_time=datetime.fromisoformat(row['publish_time']),
                        thumbnail_url=row['thumbnail_url'],
                        view_count=row['view_count'],
                        like_count=row['like_count']
                    )
                    
                    # 构建下载历史记录
                    history = DownloadHistory(
                        video=video,
                        download_time=datetime.fromisoformat(row['download_time']),
                        save_path=row['save_path'],
                        file_size=row['file_size'],
                        duration=row['duration']
                    )
                    
                    history_list.append(history)
                
                return history_list
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting download history: {e}")
            return []
    
    def clear_history(self) -> bool:
        """清空下载历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM download_history")
                conn.commit()
                self.logger.info("Download history cleared")
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error clearing history: {e}")
            return False 