"""数据库模型定义。

使用SQLAlchemy ORM实现数据库模型。
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# 视频-标签关联表
video_tags = Table(
    'video_tags',
    Base.metadata,
    Column('video_id', Integer, ForeignKey('videos.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Video(Base):
    """视频信息表。"""
    
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    platform = Column(String(50), nullable=False)  # 平台（youtube/pornhub等）
    video_id = Column(String(100), nullable=False)  # 平台视频ID
    url = Column(String(500), nullable=False)  # 原始URL
    title = Column(String(500))  # 标题
    description = Column(String(5000))  # 描述
    duration = Column(Float)  # 时长（秒）
    
    # 上传信息
    uploader = Column(String(100))  # 上传者
    uploader_id = Column(String(100))  # 上传者ID
    uploader_url = Column(String(500))  # 上传者主页
    upload_date = Column(DateTime)  # 上传时间
    
    # 统计信息
    view_count = Column(Integer, default=0)  # 播放数
    like_count = Column(Integer, default=0)  # 点赞数
    dislike_count = Column(Integer, default=0)  # 点踩数
    comment_count = Column(Integer, default=0)  # 评论数
    
    # 下载信息
    file_path = Column(String(500))  # 本地文件路径
    file_size = Column(Integer)  # 文件大小（字节）
    download_date = Column(DateTime, default=datetime.now)  # 下载时间
    is_downloaded = Column(Boolean, default=False)  # 是否已下载
    download_status = Column(String(50))  # 下载状态
    error_message = Column(String(500))  # 错误信息
    
    # 视频信息
    width = Column(Integer)  # 视频宽度
    height = Column(Integer)  # 视频高度
    fps = Column(Float)  # 帧率
    vcodec = Column(String(50))  # 视频编码
    acodec = Column(String(50))  # 音频编码
    abr = Column(Float)  # 音频码率
    
    # 缩略图
    thumbnail = Column(String(500))  # 缩略图URL
    thumbnail_path = Column(String(500))  # 本地缩略图路径
    
    # 元数据
    webpage_url = Column(String(500))  # 网页URL
    manifest_url = Column(String(500))  # 清单URL
    ext = Column(String(10))  # 文件扩展名
    format = Column(String(50))  # 格式
    format_id = Column(String(50))  # 格式ID
    
    # 关联
    tags = relationship('Tag', secondary=video_tags, back_populates='videos')  # 标签
    categories = relationship('Category', back_populates='videos')  # 分类
    
    # 创建/更新时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Video(id={self.id}, title='{self.title}', platform='{self.platform}')>"

class Tag(Base):
    """标签表。"""
    
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    videos = relationship('Video', secondary=video_tags, back_populates='tags')
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"

class Category(Base):
    """分类表。"""
    
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)  # 平台
    parent_id = Column(Integer, ForeignKey('categories.id'))
    videos = relationship('Video', back_populates='categories')
    subcategories = relationship('Category')
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', platform='{self.platform}')>"

class DownloadHistory(Base):
    """下载历史表。"""
    
    __tablename__ = 'download_history'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('videos.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    status = Column(String(50), nullable=False)  # success/failed/cancelled
    error_message = Column(String(500))
    file_path = Column(String(500))
    file_size = Column(Integer)
    download_speed = Column(Float)  # 平均下载速度（bytes/s）
    created_at = Column(DateTime, default=datetime.now)
    
    video = relationship('Video', backref='download_history')
    
    def __repr__(self):
        return f"<DownloadHistory(id={self.id}, video_id={self.video_id}, status='{self.status}')>" 