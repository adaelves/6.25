"""国际化支持模块。

提供多语言支持功能。
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from PySide6.QtCore import QTranslator, QLocale

class I18nManager:
    """国际化管理器。
    
    提供以下功能：
    1. 加载语言资源
    2. 切换语言
    3. 翻译文本
    
    Attributes:
        current_locale: str, 当前语言
        translations: Dict[str, Dict[str, str]], 翻译数据
    """
    
    def __init__(self, locale: str = "zh_CN"):
        """初始化国际化管理器。
        
        Args:
            locale: 语言代码
        """
        self.current_locale = locale
        self.translations = {}
        self.translator = QTranslator()
        
        # 加载翻译
        self._load_translations()
        
    def _load_translations(self):
        """加载翻译数据。"""
        # 获取语言文件目录
        i18n_dir = Path(__file__).parent.parent / "i18n"
        
        # 加载所有语言文件
        for file in i18n_dir.glob("*.json"):
            locale = file.stem
            try:
                with open(file, "r", encoding="utf-8") as f:
                    self.translations[locale] = json.load(f)
            except Exception as e:
                print(f"加载语言文件失败 {file}: {e}")
                
    def switch_language(self, locale: str) -> bool:
        """切换语言。
        
        Args:
            locale: 语言代码
            
        Returns:
            bool: 是否切换成功
        """
        if locale not in self.translations:
            return False
            
        self.current_locale = locale
        
        # 加载Qt翻译文件
        qm_file = f":/i18n/{locale}.qm"
        if self.translator.load(qm_file):
            return True
            
        return False
        
    def tr(self, text: str) -> str:
        """翻译文本。
        
        Args:
            text: 原文
            
        Returns:
            str: 译文
        """
        # 获取当前语言的翻译
        translations = self.translations.get(self.current_locale, {})
        
        # 返回翻译或原文
        return translations.get(text, text)
        
    def get_languages(self) -> Dict[str, str]:
        """获取支持的语言列表。
        
        Returns:
            Dict[str, str]: 语言代码和名称的映射
        """
        return {
            "zh_CN": "简体中文",
            "en_US": "English",
            "ja_JP": "日本語",
            "ko_KR": "한국어"
        }
        
# 创建全局实例
i18n = I18nManager() 