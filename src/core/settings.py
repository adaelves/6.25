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
    """配置管理。"""
    
    def __init__(self):
        """初始化配置。"""
        self._config = {}
        self._config_file = Path('config.json')
        self._load()
        
    def get(self, key: str, default=None):
        """获取配置。
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(k)
            if value is None:
                return default
                
        return value
        
    def set(self, key: str, value):
        """设置配置。
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
            
        config[keys[-1]] = value
        self._save()
        
    def _load(self):
        """加载配置。"""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self._config = {}
            
    def _save(self):
        """保存配置。"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            
    def __getitem__(self, key: str):
        """获取配置。
        
        Args:
            key: 配置键
            
        Returns:
            Any: 配置值
            
        Raises:
            KeyError: 配置不存在
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
        
    def __setitem__(self, key: str, value):
        """设置配置。
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.set(key, value)

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