"""数据库模块"""

import os
import sqlite3
from typing import List, Optional, Dict
from datetime import datetime

class Database:
    """SQLite数据库管理类"""
    
    def __init__(self, db_file: str = "downloads.db"):
        self.db_file = db_file
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库"""
        if not os.path.exists(self.db_file):
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 创建下载历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        format TEXT NOT NULL,
                        quality TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'completed'
                    )
                """)
                
                conn.commit()
    
    def add_download(
        self,
        url: str,
        title: str,
        format: str,
        quality: str,
        file_path: str,
        file_size: int
    ) -> int:
        """添加下载记录
        
        Args:
            url: 视频URL
            title: 视频标题
            format: 下载格式
            quality: 视频质量
            file_path: 文件路径
            file_size: 文件大小
            
        Returns:
            int: 记录ID
        """
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO downloads (
                    url, title, format, quality,
                    file_path, file_size
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (url, title, format, quality, file_path, file_size)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_downloads(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """获取下载历史
        
        Args:
            limit: 返回记录数量限制
            offset: 起始偏移
            
        Returns:
            List[Dict]: 下载记录列表
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT * FROM downloads
                ORDER BY download_date DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_download(self, download_id: int) -> Optional[Dict]:
        """获取单条下载记录
        
        Args:
            download_id: 下载记录ID
            
        Returns:
            Optional[Dict]: 下载记录
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM downloads WHERE id = ?",
                (download_id,)
            )
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_status(
        self,
        download_id: int,
        status: str
    ) -> None:
        """更新下载状态
        
        Args:
            download_id: 下载记录ID
            status: 新状态
        """
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE downloads SET status = ? WHERE id = ?",
                (status, download_id)
            )
            conn.commit()
    
    def delete_download(self, download_id: int) -> None:
        """删除下载记录
        
        Args:
            download_id: 下载记录ID
        """
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM downloads WHERE id = ?",
                (download_id,)
            )
            conn.commit()
    
    def clear_history(self) -> None:
        """清空下载历史"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads")
            conn.commit() 