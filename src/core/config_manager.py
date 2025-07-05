import json
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    """配置管理器，负责管理应用程序设置"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "download": {
                "path": str(Path.home() / "Downloads" / "VideoDownloader"),
                "max_threads": 4,
                "speed_limit": 0,  # 0表示不限速
                "chunk_size": 1024 * 1024,  # 1MB
                "timeout": 30,  # 30秒超时
                "retry_times": 3,
                "auto_rename": True
            },
            "proxy": {
                "enabled": False,
                "address": "127.0.0.1:7890"
            },
            "ui": {
                "language": "zh_CN",
                "theme": "dark",
                "minimize_to_tray": True,
                "show_notifications": True
            },
            "plugins": {
                "youtube": {
                    "enabled": True,
                    "prefer_quality": "1080p",
                    "download_subtitle": True
                },
                "twitter": {
                    "enabled": True,
                    "include_retweets": False
                },
                "pornhub": {
                    "enabled": True,
                    "prefer_quality": "best"
                }
            },
            "monitoring": {
                "check_interval": 300,  # 5分钟
                "auto_download": True,
                "notify_new_videos": True
            }
        }
        
        if not self.config_file.exists():
            self.save_config(default_config)
            return default_config
            
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 合并默认配置，确保所有必要的配置项都存在
                self._merge_configs(default_config, config)
                return config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return default_config
            
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """保存配置到文件"""
        try:
            config = config or self.config
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        try:
            value = self.config
            for k in key.split("."):
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
            
    def set(self, key: str, value: Any) -> bool:
        """设置配置项"""
        try:
            keys = key.split(".")
            target = self.config
            for k in keys[:-1]:
                target = target.setdefault(k, {})
            target[keys[-1]] = value
            return self.save_config()
        except Exception as e:
            print(f"设置配置项失败: {e}")
            return False
            
    def _merge_configs(self, default: Dict[str, Any], current: Dict[str, Any]) -> None:
        """递归合并配置，确保所有默认配置项都存在"""
        for key, value in default.items():
            if key not in current:
                current[key] = value
            elif isinstance(value, dict) and isinstance(current[key], dict):
                self._merge_configs(value, current[key])
                
    def get_download_path(self) -> str:
        """获取下载路径"""
        return self.get("download.path")
        
    def get_max_threads(self) -> int:
        """获取最大线程数"""
        return self.get("download.max_threads", 4)
        
    def get_speed_limit(self) -> int:
        """获取下载速度限制"""
        return self.get("download.speed_limit", 0)
        
    def get_proxy_settings(self) -> Dict[str, Any]:
        """获取代理设置"""
        return {
            "enabled": self.get("proxy.enabled", False),
            "address": self.get("proxy.address", "127.0.0.1:7890")
        }
        
    def set_download_path(self, path: str) -> bool:
        """设置下载路径"""
        return self.set("download.path", path)
        
    def set_max_threads(self, threads: int) -> bool:
        """设置最大线程数"""
        return self.set("download.max_threads", max(1, min(threads, 16)))
        
    def set_speed_limit(self, limit: int) -> bool:
        """设置下载速度限制"""
        return self.set("download.speed_limit", max(0, limit))
        
    def set_proxy_settings(self, enabled: bool, address: str) -> bool:
        """设置代理"""
        success = True
        success &= self.set("proxy.enabled", enabled)
        success &= self.set("proxy.address", address)
        return success 