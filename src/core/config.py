"""统一的下载器配置系统。

提供所有下载器共用的配置选项。
"""

from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import json

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