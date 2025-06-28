"""测试下载服务。"""

import os
import pytest
import tempfile
import hashlib
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from src.services.downloader import VideoDownloader
from src.services.scanner import VideoScanner
from src.services.creator import CreatorManager
from src.models.videos import Video
from src.models.base import Base
from src.schemas.video import VideoInfo

@pytest.fixture
def temp_dir():
    """创建临时下载目录。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

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
def video_downloader(video_scanner, temp_dir):
    """创建下载服务实例。"""
    return VideoDownloader(
        video_scanner,
        temp_dir,
        max_workers=2
    )

@pytest.fixture
def mock_platform_api():
    """模拟平台API。"""
    mock_api = Mock()
    mock_downloader = AsyncMock()
    
    async def mock_download(file_path):
        # 模拟下载文件
        with open(file_path, 'wb') as f:
            f.write(b'test content')
            
    mock_downloader.download = mock_download
    mock_api.get_downloader.return_value = mock_downloader
    return mock_api

@pytest.fixture
def test_video(video_scanner):
    """创建测试视频。"""
    with Session(video_scanner.engine) as session:
        video = Video(
            id="test1",
            creator_id="creator1",
            platform="youtube",
            platform_id="video1",
            title="测试视频",
            url="https://youtube.com/watch?v=video1",
            publish_time=datetime.utcnow(),
            downloaded="pending"
        )
        session.add(video)
        session.commit()
        return VideoInfo.from_orm(video)

async def test_download_video(video_downloader, test_video, mock_platform_api):
    """测试下载单个视频。"""
    with patch.object(
        video_downloader,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        # 执行下载
        success = await video_downloader.download_video(test_video)
        assert success
        
        # 验证文件是否存在
        expected_dir = os.path.join(video_downloader.download_dir, "youtube")
        assert os.path.exists(expected_dir)
        
        files = os.listdir(expected_dir)
        assert len(files) == 1
        assert files[0].startswith("video1_")
        assert files[0].endswith(".mp4")
        
        # 验证视频状态
        with Session(video_downloader.scanner.engine) as session:
            video = session.query(Video).filter_by(id="test1").first()
            assert video.downloaded == "completed"
            assert video.file_path is not None
            assert video.file_size > 0
            assert video.file_md5 is not None

async def test_duplicate_file_detection(video_downloader, test_video, mock_platform_api):
    """测试重复文件检测。"""
    # 先下载一个视频
    with patch.object(
        video_downloader,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        await video_downloader.download_video(test_video)
        
        # 获取第一个文件的MD5
        with Session(video_downloader.scanner.engine) as session:
            first_video = session.query(Video).filter_by(id="test1").first()
            first_md5 = first_video.file_md5
            
        # 创建另一个相同内容的视频
        with Session(video_downloader.scanner.engine) as session:
            second_video = Video(
                id="test2",
                creator_id="creator1",
                platform="youtube",
                platform_id="video2",
                title="测试视频2",
                url="https://youtube.com/watch?v=video2",
                publish_time=datetime.utcnow(),
                downloaded="pending"
            )
            session.add(second_video)
            session.commit()
            second_video_info = VideoInfo.from_orm(second_video)
            
        # 尝试下载第二个视频
        success = await video_downloader.download_video(second_video_info)
        assert not success
        
        # 验证第二个视频状态
        with Session(video_downloader.scanner.engine) as session:
            video = session.query(Video).filter_by(id="test2").first()
            assert video.downloaded == "duplicate"
            assert video.file_path is None
            
        # 验证只有一个文件
        files = os.listdir(os.path.join(video_downloader.download_dir, "youtube"))
        assert len(files) == 1

def test_generate_file_path(video_downloader, test_video):
    """测试生成文件路径。"""
    file_path = video_downloader._generate_file_path(test_video)
    
    # 验证路径格式
    assert file_path.startswith(video_downloader.download_dir)
    assert "youtube" in file_path
    assert "video1_" in file_path
    assert file_path.endswith(".mp4")
    
    # 验证目录是否创建
    assert os.path.exists(os.path.dirname(file_path))

async def test_get_file_info(video_downloader):
    """测试获取文件信息。"""
    # 创建测试文件
    test_content = b"test content"
    test_file = os.path.join(video_downloader.download_dir, "test.mp4")
    with open(test_file, "wb") as f:
        f.write(test_content)
        
    # 获取文件信息
    file_info = await video_downloader._get_file_info(test_file)
    
    # 验证结果
    assert file_info["path"] == test_file
    assert file_info["size"] > 0
    
    # 验证MD5
    md5 = hashlib.md5()
    md5.update(test_content)
    assert file_info["md5"] == md5.hexdigest() 