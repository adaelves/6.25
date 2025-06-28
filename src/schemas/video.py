"""视频数据模型。"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

class VideoInfo(BaseModel):
    """视频信息数据模型。
    
    用于API响应。
    
    Attributes:
        id: 视频ID
        creator_id: 创作者ID
        platform: 平台名称
        platform_id: 平台视频ID
        title: 标题
        description: 描述
        url: 视频URL
        thumbnail: 缩略图URL
        duration: 时长（秒）
        publish_time: 发布时间
        extra_data: 附加元数据
        downloaded: 下载状态
        file_path: 本地文件路径
        file_size: 文件大小(MB)
        file_md5: 文件MD5
    """
    
    id: str
    creator_id: str
    platform: str
    platform_id: str
    title: str
    description: Optional[str] = None
    url: HttpUrl
    thumbnail: Optional[HttpUrl] = None
    duration: Optional[float] = None
    publish_time: datetime
    extra_data: Dict[str, Any] = {}
    downloaded: str = 'pending'
    file_path: Optional[str] = None
    file_size: Optional[float] = None
    file_md5: Optional[str] = None
    
    class Config:
        """配置类。"""
        orm_mode = True
        
class VideoUpdate(BaseModel):
    """视频更新数据模型。
    
    用于更新请求。
    
    Attributes:
        title: 标题
        description: 描述
        extra_data: 附加元数据
        downloaded: 下载状态
        file_path: 本地文件路径
        file_size: 文件大小
        file_md5: 文件MD5
    """
    
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    extra_data: Optional[Dict[str, Any]] = None
    downloaded: Optional[str] = Field(None, regex='^(pending|downloading|completed|failed)$')
    file_path: Optional[str] = Field(None, max_length=1000)
    file_size: Optional[float] = Field(None, gt=0)
    file_md5: Optional[str] = Field(None, regex='^[a-f0-9]{32}$')
    
    class Config:
        """配置类。"""
        json_encoders = {
            # 自定义JSON编码器
        } 