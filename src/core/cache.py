"""缓存系统。

提供智能缓存功能，包含内存缓存和磁盘缓存。
"""

import logging
import os
import time
import json
import pickle
import zlib
from typing import Any, Optional, Dict, List, Tuple
from collections import OrderedDict
from threading import Lock
from pathlib import Path
import threading
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)

class CacheItem:
    """缓存项。
    
    Attributes:
        value: 值
        expire_at: 过期时间
        compressed: 是否压缩
    """
    
    def __init__(
        self,
        value: Any,
        expire_at: Optional[float] = None,
        compressed: bool = False
    ):
        """初始化缓存项。
        
        Args:
            value: 值
            expire_at: 过期时间，可选
            compressed: 是否压缩，默认False
        """
        self.value = value
        self.expire_at = expire_at
        self.compressed = compressed
        
    def is_expired(self) -> bool:
        """检查是否过期。
        
        Returns:
            bool: 是否过期
        """
        return (
            self.expire_at is not None
            and time.time() > self.expire_at
        )
        
    def serialize(self) -> bytes:
        """序列化。
        
        Returns:
            bytes: 序列化后的数据
        """
        data = pickle.dumps(self.value)
        if self.compressed:
            data = zlib.compress(data)
        return data
        
    @classmethod
    def deserialize(
        cls,
        data: bytes,
        compressed: bool = False
    ) -> Any:
        """反序列化。
        
        Args:
            data: 序列化数据
            compressed: 是否压缩，默认False
            
        Returns:
            Any: 反序列化后的值
        """
        if compressed:
            data = zlib.decompress(data)
        return pickle.loads(data)

class LRUCache:
    """LRU内存缓存。
    
    Attributes:
        capacity: 容量
        cache: 缓存字典
        lock: 线程锁
    """
    
    def __init__(self, capacity: int):
        """初始化缓存。
        
        Args:
            capacity: 容量
        """
        self.capacity = capacity
        self.cache: OrderedDict[str, CacheItem] = OrderedDict()
        self.lock = Lock()
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存。
        
        Args:
            key: 键
            
        Returns:
            Optional[Any]: 值
        """
        with self.lock:
            if key not in self.cache:
                return None
                
            # 获取缓存项
            item = self.cache[key]
            
            # 检查是否过期
            if item.is_expired():
                del self.cache[key]
                return None
                
            # 更新访问顺序
            self.cache.move_to_end(key)
            
            return item.value
            
    def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ):
        """设置缓存。
        
        Args:
            key: 键
            value: 值
            ttl: 过期时间(秒)，可选
        """
        with self.lock:
            # 计算过期时间
            expire_at = (
                time.time() + ttl if ttl is not None
                else None
            )
            
            # 创建缓存项
            item = CacheItem(value, expire_at)
            
            # 检查容量
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
                
            # 更新缓存
            self.cache[key] = item
            self.cache.move_to_end(key)
            
    def remove(self, key: str):
        """删除缓存。
        
        Args:
            key: 键
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                
    def clear(self):
        """清空缓存。"""
        with self.lock:
            self.cache.clear()
            
    def __contains__(self, key: str) -> bool:
        """检查键是否存在。"""
        with self.lock:
            return key in self.cache

class DiskCache:
    """磁盘缓存。
    
    Attributes:
        cache_dir: 缓存目录
        lock: 线程锁
    """
    
    def __init__(self, cache_dir: str):
        """初始化缓存。
        
        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        
    def _get_path(self, key: str) -> Path:
        """获取缓存文件路径。
        
        Args:
            key: 键
            
        Returns:
            Path: 文件路径
        """
        # 使用键的哈希值作为文件名
        filename = f"{hash(key)}.cache"
        return self.cache_dir / filename
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存。
        
        Args:
            key: 键
            
        Returns:
            Optional[Any]: 值
        """
        with self.lock:
            path = self._get_path(key)
            if not path.exists():
                return None
                
            try:
                # 读取元数据
                meta_path = path.with_suffix('.meta')
                if not meta_path.exists():
                    return None
                    
                with meta_path.open('r') as f:
                    meta = json.load(f)
                    
                # 检查是否过期
                expire_at = meta.get('expire_at')
                if (
                    expire_at is not None
                    and time.time() > expire_at
                ):
                    self.remove(key)
                    return None
                    
                # 读取数据
                with path.open('rb') as f:
                    data = f.read()
                    
                # 反序列化
                return CacheItem.deserialize(
                    data,
                    meta.get('compressed', False)
                )
                
            except Exception as e:
                logger.error(f"Failed to read cache: {e}")
                self.remove(key)
                return None
                
    def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        compress: bool = False
    ):
        """设置缓存。
        
        Args:
            key: 键
            value: 值
            ttl: 过期时间(秒)，可选
            compress: 是否压缩，默认False
        """
        with self.lock:
            try:
                # 创建缓存项
                item = CacheItem(
                    value,
                    (
                        time.time() + ttl
                        if ttl is not None else None
                    ),
                    compress
                )
                
                # 序列化数据
                data = item.serialize()
                
                # 写入数据
                path = self._get_path(key)
                with path.open('wb') as f:
                    f.write(data)
                    
                # 写入元数据
                meta = {
                    'key': key,
                    'expire_at': item.expire_at,
                    'compressed': item.compressed,
                    'size': len(data),
                    'created_at': time.time()
                }
                
                meta_path = path.with_suffix('.meta')
                with meta_path.open('w') as f:
                    json.dump(meta, f)
                    
            except Exception as e:
                logger.error(f"Failed to write cache: {e}")
                self.remove(key)
                
    def remove(self, key: str):
        """删除缓存。
        
        Args:
            key: 键
        """
        with self.lock:
            path = self._get_path(key)
            meta_path = path.with_suffix('.meta')
            
            if path.exists():
                path.unlink()
            if meta_path.exists():
                meta_path.unlink()
                
    def clear(self):
        """清空缓存。"""
        with self.lock:
            for path in self.cache_dir.glob('*'):
                path.unlink()
                
    def __contains__(self, key: str) -> bool:
        """检查键是否存在。"""
        with self.lock:
            return self._get_path(key).exists()

class SmartCache:
    """智能缓存。
    
    提供以下功能：
    1. 两级缓存（内存+磁盘）
    2. 自动过期
    3. 数据压缩
    4. 序列化支持
    5. 线程安全
    
    Attributes:
        memory_cache: 内存缓存
        disk_cache: 磁盘缓存
    """
    
    def __init__(
        self,
        memory_capacity: int = 1000,
        cache_dir: str = './cache'
    ):
        """初始化缓存。
        
        Args:
            memory_capacity: 内存缓存容量，默认1000
            cache_dir: 磁盘缓存目录，默认'./cache'
        """
        self.memory_cache = LRUCache(memory_capacity)
        self.disk_cache = DiskCache(cache_dir)
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存。
        
        Args:
            key: 键
            
        Returns:
            Optional[Any]: 值
        """
        # 优先从内存缓存获取
        value = self.memory_cache.get(key)
        if value is not None:
            return value
            
        # 从磁盘缓存获取
        value = self.disk_cache.get(key)
        if value is not None:
            # 写入内存缓存
            self.memory_cache.put(key, value)
            return value
            
        return None
        
    def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        compress: bool = False
    ):
        """设置缓存。
        
        Args:
            key: 键
            value: 值
            ttl: 过期时间(秒)，可选
            compress: 是否压缩，默认False
        """
        # 写入内存缓存
        self.memory_cache.put(key, value, ttl)
        
        # 写入磁盘缓存
        self.disk_cache.put(key, value, ttl, compress)
        
    def remove(self, key: str):
        """删除缓存。
        
        Args:
            key: 键
        """
        self.memory_cache.remove(key)
        self.disk_cache.remove(key)
        
    def clear(self):
        """清空缓存。"""
        self.memory_cache.clear()
        self.disk_cache.clear()
        
    def __contains__(self, key: str) -> bool:
        """检查键是否存在。"""
        return (
            key in self.memory_cache
            or key in self.disk_cache
        ) 