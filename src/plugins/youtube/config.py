"""YouTube下载器配置模块。

提供线程安全的配置管理功能。
支持配置验证、自动备份和类型检查。
"""

import os
import json
import threading
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Type, get_type_hints
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigValidationError(Exception):
    """配置验证错误。"""
    pass

class ThreadSafeConfig:
    """线程安全的配置基类。
    
    提供线程安全的配置读写和自动备份功能。
    """
    
    def __init__(self, config_dir: Path):
        """初始化配置管理器。
        
        Args:
            config_dir: 配置文件目录
        """
        self._lock = threading.Lock()
        self._config_dir = config_dir
        self._config_file = config_dir / "config.json"
        self._backup_dir = config_dir / "backups"
        
        # 创建必要的目录
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        
    def _backup(self):
        """备份当前配置。"""
        try:
            if self._config_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self._backup_dir / f"config_{timestamp}.json"
                shutil.copy2(self._config_file, backup_file)
                
                # 清理旧备份（只保留最近10个）
                backups = sorted(self._backup_dir.glob("config_*.json"))
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        old_backup.unlink()
                        
        except Exception as e:
            logger.error(f"备份配置失败: {str(e)}")
            
    def _save(self, data: Dict[str, Any]):
        """保存配置到文件。
        
        Args:
            data: 要保存的配置数据
        """
        try:
            self._backup()
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            raise
            
    def _load(self) -> Dict[str, Any]:
        """从文件加载配置。
        
        Returns:
            Dict[str, Any]: 加载的配置数据
        """
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            return {}

@dataclass
class YouTubeDownloaderConfig:
    """YouTube下载器配置。
    
    线程安全的配置类，支持：
    - 类型验证
    - 自动备份
    - 配置恢复
    
    Attributes:
        save_dir: 保存目录
        output_template: 输出文件名模板
        proxy: 代理服务器
        timeout: 超时时间（秒）
        max_retries: 最大重试次数
        enable_4k: 是否启用4K下载
        enable_hdr: 是否启用HDR下载
        max_bitrate: 最大码率（Kbps）
        prefer_codec: 首选编码器
        merge_output_format: 合并输出格式
    """
    
    save_dir: Path
    output_template: str = "%(title)s.%(ext)s"
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    
    # 视频质量设置
    enable_4k: bool = False
    enable_hdr: bool = False
    max_bitrate: Optional[int] = None  # Kbps
    prefer_codec: str = "vp09"  # vp09, av01, avc1
    
    # 输出格式设置
    merge_output_format: str = "mp4"
    
    # 线程安全
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    
    # 兼容性映射
    _LEGACY_MAPPING = {
        'max_height': 'max_bitrate',  # 旧版本使用max_height，新版本使用max_bitrate
        'prefer_quality': 'enable_4k',  # 旧版本使用prefer_quality，新版本使用enable_4k
        'chunk_size': None,  # 废弃的参数
        'max_concurrent_downloads': None,  # 废弃的参数
        'speed_limit': None,  # 废弃的参数
        'custom_headers': None  # 废弃的参数
    }
    
    def __post_init__(self):
        """初始化后处理。
        
        验证配置值的类型和范围。
        """
        self._validate_types()
        self._validate_values()
        
        # 确保目录存在
        if isinstance(self.save_dir, str):
            self.save_dir = Path(self.save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def _validate_types(self):
        """验证属性类型。
        
        Raises:
            ConfigValidationError: 类型验证失败
        """
        hints = get_type_hints(self.__class__)
        for name, hint in hints.items():
            if name.startswith('_'):
                continue
                
            value = getattr(self, name)
            if value is not None:
                try:
                    # 处理Optional类型
                    if hasattr(hint, "__origin__") and hint.__origin__ is Optional:
                        hint = hint.__args__[0]
                    
                    # Path类型特殊处理
                    if hint is Path and isinstance(value, str):
                        continue
                        
                    if not isinstance(value, hint):
                        raise ConfigValidationError(
                            f"属性 {name} 类型错误: 期望 {hint.__name__}, "
                            f"实际 {type(value).__name__}"
                        )
                except Exception as e:
                    raise ConfigValidationError(f"类型验证失败: {str(e)}")
                    
    def _validate_values(self):
        """验证属性值的合法性。
        
        Raises:
            ConfigValidationError: 值验证失败
        """
        if self.max_bitrate is not None and self.max_bitrate <= 0:
            raise ConfigValidationError("max_bitrate必须大于0")
            
        if self.timeout <= 0:
            raise ConfigValidationError("timeout必须大于0")
            
        if self.max_retries < 0:
            raise ConfigValidationError("max_retries不能为负数")
            
        if self.prefer_codec not in ["vp09", "av01", "avc1"]:
            raise ConfigValidationError("prefer_codec必须是vp09、av01或avc1之一")
            
    def update(self, **kwargs):
        """更新配置。
        
        Args:
            **kwargs: 要更新的配置项
            
        Raises:
            ConfigValidationError: 配置验证失败
        """
        with self._lock:
            # 更新属性
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                else:
                    raise ConfigValidationError(f"未知的配置项: {key}")
                    
            # 验证新的配置
            self._validate_types()
            self._validate_values()
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        with self._lock:
            data = asdict(self)
            # 移除内部属性
            data.pop('_lock', None)
            # 转换Path对象
            data['save_dir'] = str(self.save_dir)
            return data
            
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YouTubeDownloaderConfig":
        """从字典创建配置。
        
        支持旧版本配置的迁移。
        
        Args:
            data: 配置字典
            
        Returns:
            YouTubeDownloaderConfig: 配置对象
            
        Raises:
            ConfigValidationError: 配置验证失败
        """
        # 复制数据以避免修改原字典
        config_data = data.copy()
        
        # 处理旧版本配置
        for old_key, new_key in cls._LEGACY_MAPPING.items():
            if old_key in config_data:
                value = config_data.pop(old_key)
                if new_key:  # 如果有对应的新参数
                    if old_key == 'max_height':
                        # 将旧的max_height转换为max_bitrate
                        # 使用简单的转换规则：1080p约等于5000Kbps
                        config_data[new_key] = value * 5
                    elif old_key == 'prefer_quality':
                        # 将prefer_quality转换为enable_4k
                        config_data[new_key] = value == '4k' or value == '2160p'
                    else:
                        config_data[new_key] = value
                logger.info(f"迁移旧配置参数 {old_key} -> {new_key if new_key else '已废弃'}")
        
        # 转换特殊类型
        if 'save_dir' in config_data:
            config_data['save_dir'] = Path(config_data['save_dir'])
            
        try:
            return cls(**config_data)
        except Exception as e:
            raise ConfigValidationError(f"创建配置失败: {str(e)}")

class YouTubeConfigManager(ThreadSafeConfig):
    """YouTube配置管理器。
    
    提供线程安全的配置管理功能。
    """
    
    def __init__(self, config_dir: Path):
        """初始化配置管理器。
        
        Args:
            config_dir: 配置文件目录
        """
        super().__init__(config_dir)
        self._config: Optional[YouTubeDownloaderConfig] = None
        self._load_config()
        
    def _load_config(self):
        """加载配置。"""
        with self._lock:
            try:
                data = self._load()
                if data:
                    self._config = YouTubeDownloaderConfig.from_dict(data)
                else:
                    # 使用默认配置
                    self._config = YouTubeDownloaderConfig(
                        save_dir=self._config_dir / "downloads"
                    )
                    self._save(self._config.to_dict())
            except Exception as e:
                logger.error(f"加载配置失败: {str(e)}")
                # 使用默认配置
                self._config = YouTubeDownloaderConfig(
                    save_dir=self._config_dir / "downloads"
                )
                self._save(self._config.to_dict())
                
    def get_config(self) -> YouTubeDownloaderConfig:
        """获取配置。
        
        Returns:
            YouTubeDownloaderConfig: 配置对象
        """
        with self._lock:
            return self._config
            
    def update_config(self, **kwargs):
        """更新配置。
        
        Args:
            **kwargs: 要更新的配置项
        """
        with self._lock:
            self._config.update(**kwargs)
            self._save(self._config.to_dict())
            
    def reset_config(self):
        """重置为默认配置。"""
        with self._lock:
            self._config = YouTubeDownloaderConfig(
                save_dir=self._config_dir / "downloads"
            )
            self._save(self._config.to_dict()) 