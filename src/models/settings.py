import os
import json
from typing import Optional, Dict, Any

class Settings:
    """应用程序设置类"""
    
    def __init__(self) -> None:
        self._config_file = "config/settings.json"
        self._settings: Dict[str, Any] = {
            'download_path': 'downloads',
            'max_threads': 4,
            'use_proxy': False,
            'proxy': '127.0.0.1:7890',
            'language': 'zh_CN',
            'theme': 'dark'
        }
        self.load()
        
    def load(self) -> None:
        """从配置文件加载设置"""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self._settings.update(saved)
        except Exception as e:
            print(f"加载设置失败: {e}")
            
    def save(self) -> None:
        """保存设置到配置文件"""
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存设置失败: {e}")
            
    @property
    def download_path(self) -> str:
        """下载路径"""
        return self._settings['download_path']
        
    @download_path.setter
    def download_path(self, value: str) -> None:
        self._settings['download_path'] = value
        
    @property
    def max_threads(self) -> int:
        """最大线程数"""
        return self._settings['max_threads']
        
    @max_threads.setter
    def max_threads(self, value: int) -> None:
        self._settings['max_threads'] = value
        
    @property
    def use_proxy(self) -> bool:
        """是否使用代理"""
        return self._settings['use_proxy']
        
    @use_proxy.setter
    def use_proxy(self, value: bool) -> None:
        self._settings['use_proxy'] = value
        
    @property
    def proxy(self) -> str:
        """代理地址"""
        return self._settings['proxy']
        
    @proxy.setter
    def proxy(self, value: str) -> None:
        self._settings['proxy'] = value
        
    @property
    def language(self) -> str:
        """界面语言"""
        return self._settings['language']
        
    @language.setter
    def language(self, value: str) -> None:
        self._settings['language'] = value
        
    @property
    def theme(self) -> str:
        """界面主题"""
        return self._settings['theme']
        
    @theme.setter
    def theme(self, value: str) -> None:
        self._settings['theme'] = value 