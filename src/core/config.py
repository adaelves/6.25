"""统一的下载器配置系统。

提供所有下载器共用的配置选项。
"""

from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import logging

logger = logging.getLogger(__name__)

@dataclass
class DownloaderConfig:
    """下载器基础配置。
    
    为所有下载器提供统一的配置接口。
    支持从JSON文件加载和保存配置。
    
    Attributes:
        save_dir: 保存目录
        filename_template: 文件名模板
        max_concurrent_downloads: 最大并发下载数
        speed_limit: 速度限制(bytes/s)
        chunk_size: 分块大小(bytes)
        max_retries: 最大重试次数
        proxy: 代理服务器
        timeout: 超时时间(秒)
        custom_headers: 自定义请求头
    """
    
    save_dir: Path
    filename_template: str = "{author}/{title}_{quality}{ext}"
    max_concurrent_downloads: int = 3
    speed_limit: int = 0  # 0表示不限速
    chunk_size: int = 8192
    max_retries: int = 3
    proxy: Optional[str] = None
    timeout: float = 30.0
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    # 文件名模板变量说明
    TEMPLATE_VARS = {
        "title": "视频标题",
        "author": "作者",
        "id": "视频ID",
        "quality": "视频质量",
        "date": "发布日期(YYYY-MM-DD)",
        "time": "发布时间(HH-MM-SS)",
        "timestamp": "发布时间戳",
        "duration": "视频时长(秒)",
        "views": "播放量",
        "likes": "点赞数",
        "comments": "评论数",
        "description": "视频描述",
        "category": "视频分类",
        "tags": "视频标签",
        "ext": "文件扩展名"
    }
    
    def __post_init__(self):
        """初始化后处理。"""
        if isinstance(self.save_dir, str):
            self.save_dir = Path(self.save_dir)
            
        # 设置默认请求头
        if not self.custom_headers:
            self.custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br"
            }
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        return {
            "save_dir": str(self.save_dir),
            "filename_template": self.filename_template,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "speed_limit": self.speed_limit,
            "chunk_size": self.chunk_size,
            "max_retries": self.max_retries,
            "proxy": self.proxy,
            "timeout": self.timeout,
            "custom_headers": self.custom_headers
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DownloaderConfig":
        """从字典创建配置。
        
        Args:
            data: 配置字典
            
        Returns:
            DownloaderConfig: 配置对象
        """
        return cls(**data)
        
    def save(self, path: Union[str, Path]):
        """保存配置到文件。
        
        Args:
            path: 配置文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            
    @classmethod
    def load(cls, path: Union[str, Path]) -> "DownloaderConfig":
        """从文件加载配置。
        
        Args:
            path: 配置文件路径
            
        Returns:
            DownloaderConfig: 配置对象
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
        
    def validate_template(self, template: Optional[str] = None) -> bool:
        """验证文件名模板。
        
        Args:
            template: 要验证的模板，默认使用当前模板
            
        Returns:
            bool: 模板是否有效
        """
        template = template or self.filename_template
        try:
            # 尝试使用所有可能的变量格式化模板
            test_vars = {var: "test" for var in self.TEMPLATE_VARS}
            template.format(**test_vars)
            return True
        except (KeyError, ValueError):
            return False
            
    def format_filename(self, info: Dict[str, Any]) -> str:
        """使用视频信息格式化文件名。
        
        Args:
            info: 视频信息字典
            
        Returns:
            str: 格式化后的文件名
            
        Raises:
            KeyError: 缺少必要的模板变量
        """
        # 准备模板变量
        template_vars = {}
        for var in self.TEMPLATE_VARS:
            if var in info:
                template_vars[var] = info[var]
            else:
                # 对于缺失的变量使用默认值
                template_vars[var] = ""
                
        # 格式化文件名
        filename = self.filename_template.format(**template_vars)
        
        # 清理文件名中的非法字符
        filename = "".join(c for c in filename if c.isprintable() and c not in r'<>:"/\|?*')
        
        return filename.strip()

class ConfigManager:
    """配置管理器。
    
    负责配置文件的读写和版本迁移。
    支持配置版本管理和自动迁移。
    
    Attributes:
        config_file: Path, 配置文件路径
        current_version: int, 当前配置版本
        config: Dict[str, Any], 当前配置
    """
    
    # 当前配置版本
    CURRENT_VERSION = 2
    
    # 默认配置
    DEFAULT_CONFIG = {
        'version': CURRENT_VERSION,
        'downloads': 'downloads',
        'cookies': {
            'twitter': None,
            'youtube': None,
            'pornhub': None
        },
        'proxy': None,
        'timeout': 30,
        'max_retries': 3,
        'language': 'zh_CN'
    }
    
    def __init__(self, config_file: str = 'config.json'):
        """初始化配置管理器。
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = Path(config_file)
        self.config = self.load()
        
    def load(self) -> Dict[str, Any]:
        """加载配置。
        
        如果配置文件不存在，创建默认配置。
        如果配置版本过低，自动迁移到最新版本。
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if not self.config_file.exists():
                logger.info(f"配置文件不存在，创建默认配置: {self.config_file}")
                self.save(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 检查配置版本
            version = config.get('version', 1)
            if version < self.CURRENT_VERSION:
                logger.info(f"配置版本过低(v{version})，开始迁移...")
                config = self.migrate_config(config, version)
                self.save(config)
                
            return config
            
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            return self.DEFAULT_CONFIG.copy()
            
    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置。
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保配置目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
            logger.info(f"配置已保存: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            return False
            
    def migrate_config(self, config: Dict[str, Any], from_version: int) -> Dict[str, Any]:
        """迁移配置到最新版本。
        
        支持从任意旧版本迁移到最新版本。
        
        Args:
            config: 旧配置
            from_version: 当前版本
            
        Returns:
            Dict[str, Any]: 迁移后的配置
        """
        # 版本1 -> 版本2
        if from_version == 1:
            config = self.migrate_v1_to_v2(config)
            from_version = 2
            
        # 版本2 -> 版本3 (预留)
        if from_version == 2:
            # config = self.migrate_v2_to_v3(config)
            # from_version = 3
            pass
            
        return config
        
    def migrate_v1_to_v2(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """从v1迁移到v2。
        
        v1 -> v2的变更:
        1. 重命名save_path为downloads
        2. 统一Cookie管理结构
        
        Args:
            old_config: v1配置
            
        Returns:
            Dict[str, Any]: v2配置
        """
        new_config = {
            'version': 2,
            'downloads': old_config['save_path'],
            'cookies': {
                'twitter': old_config.get('twitter_cookie'),
                'youtube': old_config.get('youtube_token')
            }
        }
        
        logger.info("配置从v1迁移到v2完成")
        return new_config
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项。
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any) -> bool:
        """设置配置项。
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            bool: 是否设置成功
        """
        try:
            self.config[key] = value
            return self.save(self.config)
        except Exception as e:
            logger.error(f"设置配置失败: {str(e)}")
            return False
            
    def reset(self) -> bool:
        """重置为默认配置。
        
        Returns:
            bool: 是否重置成功
        """
        try:
            self.config = self.DEFAULT_CONFIG.copy()
            return self.save(self.config)
        except Exception as e:
            logger.error(f"重置配置失败: {str(e)}")
            return False 