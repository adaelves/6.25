"""Pornhub 下载器数据模型。"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 
 

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 
 

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoInfo:
    """视频信息数据类。
    
    Attributes:
        id: 视频ID
        title: 视频标题
        uploader: 上传者
        uploader_url: 上传者主页
        duration: 时长(秒)
        view_count: 观看次数
        like_count: 点赞数
        resolution: 分辨率
        filesize: 文件大小(字节)
        format: 视频格式
        thumbnail: 缩略图URL
        tags: 标签列表
        categories: 分类列表
        upload_date: 上传日期
    """
    
    id: str
    title: str
    uploader: str
    uploader_url: str
    duration: int
    view_count: int
    like_count: int
    resolution: str
    filesize: int
    format: str
    thumbnail: str
    tags: List[str]
    categories: List[str]
    upload_date: str

@dataclass
class DownloadProgress:
    """下载进度数据类。
    
    Attributes:
        status: 下载状态
        downloaded_bytes: 已下载字节数
        total_bytes: 总字节数
        speed: 下载速度(字节/秒)
        eta: 预计剩余时间(秒)
        filename: 文件名
        tmpfilename: 临时文件名
        elapsed: 已用时间(秒)
        phase: 当前阶段
        phase_progress: 当前阶段进度(0-100)
    """
    
    status: str
    downloaded_bytes: int
    total_bytes: int
    speed: float
    eta: int
    filename: str
    tmpfilename: str
    elapsed: float
    phase: str
    phase_progress: float 
 