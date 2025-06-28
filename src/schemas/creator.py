"""创作者数据模型。"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class CreatorUpdate(BaseModel):
    """创作者更新数据模型。
    
    用于验证创作者信息更新请求。
    
    Attributes:
        name: 创作者名称
        avatar: 头像URL
        description: 简介
        extra_data: 附加元数据
    """
    
    name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    extra_data: Optional[Dict[str, Any]] = None
    
    class Config:
        """配置类。"""
        json_encoders = {
            # 自定义JSON编码器
        }
        
class CreatorInfo(BaseModel):
    """创作者信息数据模型。
    
    用于API响应。
    
    Attributes:
        id: 创作者ID
        name: 创作者名称
        avatar: 头像URL
        description: 简介
        platforms: 平台ID映射
        extra_data: 附加元数据
    """
    
    id: str
    name: str
    avatar: Optional[str] = None
    description: Optional[str] = None
    platforms: Dict[str, str]
    extra_data: Dict[str, Any]
    
    class Config:
        """配置类。"""
        orm_mode = True  # 支持从ORM模型创建 