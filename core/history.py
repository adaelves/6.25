"""历史记录管理模块"""

import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime

class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, db_path: str = 'history.db'):
        """初始化历史记录管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        
    def add_record(self, url: str, title: str, date: str) -> bool:
        """添加下载记录
        
        Args:
            url: 视频URL
            title: 视频标题
            date: 下载日期
            
        Returns:
            bool: 是否添加成功
        """
        try:
            self.cursor.execute(
                'INSERT INTO downloads (url, title, date) VALUES (?, ?, ?)',
                (url, title, date)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
            
    def get_record_by_url(self, url: str) -> Optional[Tuple]:
        """根据URL获取记录
        
        Args:
            url: 视频URL
            
        Returns:
            Optional[Tuple]: 记录元组，如果不存在则返回None
        """
        self.cursor.execute(
            'SELECT * FROM downloads WHERE url = ?',
            (url,)
        )
        return self.cursor.fetchone()
        
    def get_all_records(self) -> List[Tuple]:
        """获取所有记录
        
        Returns:
            List[Tuple]: 记录列表
        """
        self.cursor.execute('SELECT * FROM downloads ORDER BY created_at DESC')
        return self.cursor.fetchall()
        
    def get_recent_records(self, limit: int = 10) -> List[Tuple]:
        """获取最近的记录
        
        Args:
            limit: 限制数量
            
        Returns:
            List[Tuple]: 记录列表
        """
        self.cursor.execute(
            'SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?',
            (limit,)
        )
        return self.cursor.fetchall()
        
    def batch_delete(self, ids: List[int]) -> bool:
        """批量删除记录
        
        Args:
            ids: 要删除的记录ID列表
            
        Returns:
            bool: 是否删除成功
        """
        try:
            placeholders = ','.join('?' * len(ids))
            self.cursor.execute(
                f'DELETE FROM downloads WHERE id IN ({placeholders})',
                ids
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close() 