"""测试视频扫描服务。"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.services.scanner import VideoScanner
from src.services.creator import CreatorManager
from src.models.videos import Video
from src.models.creators import Creator
from src.models.base import Base
from src.schemas.video import VideoInfo

@pytest.fixture
def creator_manager():
    """创建创作者管理服务实例。"""
    manager = CreatorManager("sqlite:///:memory:")
    Base.metadata.create_all(manager.engine)
    return manager

@pytest.fixture
def video_scanner(creator_manager):
    """创建视频扫描服务实例。"""
    scanner = VideoScanner(
        "sqlite:///:memory:",
        creator_manager,
        max_workers=2
    )
    Base.metadata.create_all(scanner.engine)
    return scanner

@pytest.fixture
def mock_platform_api():
    """模拟平台API。"""
    mock_api = Mock()
    mock_api.get_creator_videos.return_value = [
        {
            "platform": "youtube",
            "id": "video1",
            "title": "测试视频1",
            "description": "测试描述1",
            "url": "https://youtube.com/watch?v=video1",
            "thumbnail": "https://img.youtube.com/video1.jpg",
            "duration": 120.5,
            "publish_time": datetime.utcnow(),
            "metadata": {"views": 1000}
        },
        {
            "platform": "youtube",
            "id": "video2",
            "title": "测试视频2",
            "description": "测试描述2",
            "url": "https://youtube.com/watch?v=video2",
            "thumbnail": "https://img.youtube.com/video2.jpg",
            "duration": 180.0,
            "publish_time": datetime.utcnow(),
            "metadata": {"views": 2000}
        }
    ]
    return mock_api

@pytest.fixture
def test_creator(creator_manager):
    """创建测试用创作者。"""
    creator = creator_manager._update_or_create(
        platform_id="channel1",
        platform="youtube",
        name="测试创作者",
        description="测试简介"
    )
    return creator

async def test_scan_creator_videos(video_scanner, test_creator, mock_platform_api):
    """测试扫描创作者视频。"""
    with patch.object(
        video_scanner,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        # 执行扫描
        videos = await video_scanner.scan_creator_videos(
            "youtube",
            "channel1"
        )
        
        # 验证结果
        assert len(videos) == 2
        
        video1 = videos[0]
        assert video1.platform == "youtube"
        assert video1.platform_id == "video1"
        assert video1.title == "测试视频1"
        assert video1.creator_id == test_creator.id
        
        # 验证数据库记录
        with Session(video_scanner.engine) as session:
            db_videos = session.query(Video).all()
            assert len(db_videos) == 2
            
            db_video1 = db_videos[0]
            assert db_video1.platform == "youtube"
            assert db_video1.title == "测试视频1"
            assert db_video1.downloaded == "pending"

async def test_scan_all_creators(video_scanner, test_creator, mock_platform_api):
    """测试扫描所有创作者。"""
    with patch.object(
        video_scanner,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        # 执行扫描
        results = await video_scanner.scan_all_creators()
        
        # 验证结果
        assert len(results) == 1
        assert test_creator.id in results
        
        creator_videos = results[test_creator.id]
        assert len(creator_videos) == 2
        
        video1 = creator_videos[0]
        assert video1.platform == "youtube"
        assert video1.title == "测试视频1"

async def test_check_updates(video_scanner, test_creator, mock_platform_api):
    """测试检查更新。"""
    with patch.object(
        video_scanner,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        # 执行更新检查
        results = await video_scanner.check_updates(
            interval=timedelta(hours=1)
        )
        
        # 验证结果
        assert len(results) == 1
        assert test_creator.id in results
        
        creator_videos = results[test_creator.id]
        assert len(creator_videos) == 2

def test_get_pending_videos(video_scanner, test_creator):
    """测试获取待下载视频。"""
    # 创建测试数据
    with Session(video_scanner.engine) as session:
        video1 = Video(
            id="test1",
            creator_id=test_creator.id,
            platform="youtube",
            platform_id="video1",
            title="测试视频1",
            url="https://youtube.com/watch?v=video1",
            publish_time=datetime.utcnow(),
            downloaded="pending"
        )
        video2 = Video(
            id="test2",
            creator_id=test_creator.id,
            platform="youtube",
            platform_id="video2",
            title="测试视频2",
            url="https://youtube.com/watch?v=video2",
            publish_time=datetime.utcnow(),
            downloaded="completed"
        )
        session.add_all([video1, video2])
        session.commit()
        
    # 获取待下载视频
    pending = video_scanner.get_pending_videos()
    
    # 验证结果
    assert len(pending) == 1
    assert pending[0].id == "test1"
    assert pending[0].downloaded == "pending"

def test_update_video_status(video_scanner, test_creator):
    """测试更新视频状态。"""
    # 创建测试数据
    with Session(video_scanner.engine) as session:
        video = Video(
            id="test1",
            creator_id=test_creator.id,
            platform="youtube",
            platform_id="video1",
            title="测试视频",
            url="https://youtube.com/watch?v=video1",
            publish_time=datetime.utcnow(),
            downloaded="pending"
        )
        session.add(video)
        session.commit()
        
    # 更新状态
    file_info = {
        'path': '/downloads/video1.mp4',
        'size': 10.5,
        'md5': 'a' * 32
    }
    updated = video_scanner.update_video_status(
        "test1",
        "completed",
        file_info
    )
    
    # 验证结果
    assert updated is not None
    assert updated.downloaded == "completed"
    assert updated.file_path == file_info['path']
    assert updated.file_size == file_info['size']
    assert updated.file_md5 == file_info['md5']
    
    # 验证数据库记录
    with Session(video_scanner.engine) as session:
        video = session.query(Video).filter_by(id="test1").first()
        assert video.downloaded == "completed"
        assert video.file_path == file_info['path']
        assert video.file_size == file_info['size']
        assert video.file_md5 == file_info['md5']

def test_generate_video_id(video_scanner):
    """测试生成视频ID。"""
    id1 = video_scanner._generate_video_id("youtube", "video1")
    id2 = video_scanner._generate_video_id("youtube", "video1")
    id3 = video_scanner._generate_video_id("twitter", "video1")
    
    # 相同平台和视频ID应该生成相同的统一ID
    assert id1 == id2
    # 不同平台应该生成不同的统一ID
    assert id1 != id3 