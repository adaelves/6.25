"""配置管理模块。

提供应用程序配置的加载、保存和迁移功能。
支持JSON格式的配置文件。
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器。
    
    管理应用程序的配置信息。
    支持配置的加载、保存和版本迁移。
    
    Attributes:
        config_dir: Path, 配置文件目录
        config_file: Path, 配置文件路径
        config: Dict[str, Any], 当前配置
        version: int, 配置版本号
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        "version": 2,  # 当前配置版本
        "general": {
            "language": "zh_CN",
            "theme": "light",
            "save_dir": "downloads",
            "max_concurrent_downloads": 3,
            "check_update": True
        },
        "network": {
            "proxy": "http://127.0.0.1:7890",
            "timeout": 30,
            "retries": 3,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        },
        "download": {
            "output_template": "%(uploader)s/%(title)s-%(id)s.%(ext)s",
            "merge_output_format": "mp4",
            "write_thumbnail": True,
            "write_description": True,
            "write_info_json": True,
            "write_comments": False,
            "write_subtitles": True,
            "embed_subtitles": True,
            "embed_thumbnail": True,
            "add_metadata": True
        },
        "platforms": {
            "youtube": {
                "enabled": True,
                "save_dir": "downloads/youtube",
                "quality": "1080p",
                "download_subtitles": True,
                "subtitle_languages": ["zh-Hans", "en"],
                "cookies_file": "config/youtube_cookies.txt"
            },
            "twitter": {
                "enabled": True,
                "save_dir": "downloads/twitter",
                "include_replies": False,
                "include_retweets": False,
                "cookies_file": "config/twitter_cookies.txt"
            },
            "pornhub": {
                "enabled": True,
                "save_dir": "downloads/pornhub",
                "quality": "best",
                "download_thumbnails": True,
                "cookies_file": "config/pornhub_cookies.txt"
            }
        }
    }
    
    def __init__(self, config_dir: Optional[str] = None):
        """初始化配置管理器。
        
        Args:
            config_dir: 配置目录路径，默认为"config"
        """
        # 设置配置目录
        self.config_dir = Path(config_dir) if config_dir else Path("config")
        self.config_file = self.config_dir / "config.json"
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self.load()
        
        # 获取版本号
        self.version = self.config.get("version", 1)
        
        # 如果需要，执行配置迁移
        if self.version < self.DEFAULT_CONFIG["version"]:
            self.migrate()
            
    def load(self) -> Dict[str, Any]:
        """加载配置文件。
        
        如果配置文件不存在，创建默认配置。
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.info(f"已加载配置文件: {self.config_file}")
                return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            
        # 如果加载失败或文件不存在，使用默认配置
        logger.info("使用默认配置")
        return self.DEFAULT_CONFIG.copy()
        
    def save(self) -> None:
        """保存配置到文件。"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项。
        
        支持使用点号访问嵌套配置。
        
        Args:
            key: 配置键，支持点号分隔
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        try:
            value = self.config
            for k in key.split("."):
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
            
    def set(self, key: str, value: Any) -> None:
        """设置配置项。
        
        支持使用点号设置嵌套配置。
        
        Args:
            key: 配置键，支持点号分隔
            value: 配置值
        """
        keys = key.split(".")
        config = self.config
        
        # 遍历到最后一个键之前
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        # 设置最后一个键的值
        config[keys[-1]] = value
        
        # 保存配置
        self.save()
        
    def migrate(self) -> None:
        """迁移旧版本配置到新版本。"""
        try:
            if self.version == 1:
                # 从v1迁移到v2
                self._migrate_v1_to_v2()
                
            # 更新版本号
            self.config["version"] = self.DEFAULT_CONFIG["version"]
            self.version = self.DEFAULT_CONFIG["version"]
            
            # 保存更新后的配置
            self.save()
            logger.info(f"配置已迁移到v{self.version}")
            
        except Exception as e:
            logger.error(f"配置迁移失败: {str(e)}")
            
    def _migrate_v1_to_v2(self) -> None:
        """将v1配置迁移到v2。"""
        # 保存旧配置的副本
        old_config = self.config.copy()
        
        # 使用新的默认配置
        self.config = self.DEFAULT_CONFIG.copy()
        
        # 迁移通用设置
        if "general" in old_config:
            self.config["general"].update(old_config["general"])
            
        # 迁移网络设置
        if "network" in old_config:
            self.config["network"].update(old_config["network"])
            
        # 迁移下载设置
        if "download" in old_config:
            self.config["download"].update(old_config["download"])
            
        # 迁移平台特定设置
        if "platforms" in old_config:
            for platform in ["youtube", "twitter", "pornhub"]:
                if platform in old_config["platforms"]:
                    self.config["platforms"][platform].update(
                        old_config["platforms"][platform]
                    )
                    
    def reset(self) -> None:
        """重置为默认配置。"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
        logger.info("配置已重置为默认值")
        
    def __getitem__(self, key: str) -> Any:
        """实现字典式访问。"""
        return self.get(key)
        
    def __setitem__(self, key: str, value: Any) -> None:
        """实现字典式设置。"""
        self.set(key, value) 