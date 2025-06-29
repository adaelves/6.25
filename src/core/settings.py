"""设置模块。

提供应用程序配置的管理功能。
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Settings:
    """设置管理器。
    
    管理应用程序的配置信息，包括：
    1. 下载设置
    2. 代理设置
    3. 界面设置
    4. 平台设置
    """
    
    def __init__(self, config_file: str = "config.json"):
        """初始化设置管理器。
        
        Args:
            config_file: 配置文件路径，默认为"config.json"
        """
        self.config_file = Path(config_file)
        
        # 默认设置
        self.defaults = {
            # 下载设置
            "download": {
                "save_dir": str(Path.home() / "Downloads"),
                "max_concurrent": 3,
                "chunk_size": 1024 * 1024,  # 1MB
                "timeout": 30,
                "max_retries": 3,
                "auto_retry": True
            },
            
            # 代理设置
            "proxy": {
                "enabled": False,
                "type": "http",
                "host": "127.0.0.1",
                "port": 7890
            },
            
            # 界面设置
            "ui": {
                "theme": "light",
                "language": "zh_CN",
                "font_size": 12,
                "window_size": [800, 600],
                "window_position": [100, 100],
                "show_tray": True,
                "minimize_to_tray": True
            },
            
            # 平台设置
            "platforms": {
                "xvideos": {
                    "enabled": True,
                    "quality": "best"
                },
                "tumblr": {
                    "enabled": True,
                    "api_key": "",
                    "download_type": "all"  # all, video, photo
                }
            }
        }
        
        # 加载设置
        self.settings = self.load()
        
    def load(self) -> Dict[str, Any]:
        """加载设置。
        
        Returns:
            Dict[str, Any]: 设置字典
        """
        try:
            # 如果配置文件存在则加载
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    
                # 更新默认值
                self._update_recursive(self.defaults, settings)
                return self.defaults
                
        except Exception as e:
            logger.error(f"加载设置失败: {e}")
            
        return self.defaults
        
    def save(self) -> bool:
        """保存设置。
        
        Returns:
            bool: 是否保存成功
        """
        try:
            # 创建父目录
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存设置
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(
                    self.settings,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
            return True
            
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取设置值。
        
        Args:
            key: 设置键名，支持点号分隔的多级键名
            default: 默认值
            
        Returns:
            Any: 设置值
        """
        try:
            # 分割键名
            keys = key.split(".")
            value = self.settings
            
            # 逐级获取值
            for k in keys:
                value = value[k]
                
            return value
            
        except Exception:
            return default
            
    def set(self, key: str, value: Any) -> bool:
        """设置值。
        
        Args:
            key: 设置键名，支持点号分隔的多级键名
            value: 设置值
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 分割键名
            keys = key.split(".")
            target = self.settings
            
            # 逐级设置值
            for k in keys[:-1]:
                target = target.setdefault(k, {})
                
            target[keys[-1]] = value
            return True
            
        except Exception as e:
            logger.error(f"设置值失败: {e}")
            return False
            
    def _update_recursive(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any]
    ) -> None:
        """递归更新字典。
        
        Args:
            target: 目标字典
            source: 源字典
        """
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._update_recursive(target[key], value)
            else:
                target[key] = value 