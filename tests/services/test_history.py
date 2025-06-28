"""测试历史记录服务。"""

import pytest
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.services.history import HistoryService
from src.schemas.media import MediaItem
from src.models.history import DownloadHistory
from src.models.base import Base

@pytest.fixture
def history_service():
    """创建历史记录服务实例。"""
    service = HistoryService("sqlite:///:memory:")
    # 初始化数据库表
    Base.metadata.create_all(service.engine)
    return service

def test_log_download(history_service):
    """测试记录下载历史。"""
    item = MediaItem(
        url="https://youtube.com/watch?v=test123",
        title="测试视频",
        platform="youtube",
        creator_id="UC123456",
        file_path="/downloads/test.mp4",
        file_size=10.5,
        duration=120.5
    )
    
    # 记录下载
    assert history_service.log_download(item)
    
    # 验证记录
    records = history_service.get_recent(limit=1)
    assert len(records) == 1
    record = records[0]
    
    assert record.url == item.url
    assert record.title == item.title
    assert record.platform == item.platform
    assert record.creator_id == item.creator_id
    assert record.file_path == item.file_path
    assert record.file_size == item.file_size
    assert record.duration == item.duration
    assert record.status == "success"
    
def test_get_recent(history_service):
    """测试获取最近记录。"""
    # 创建多条记录，每条记录间隔1秒
    for i in range(5):
        item = MediaItem(
            url=f"https://youtube.com/watch?v=test{i}",
            title=f"测试视频{i}",
            platform="youtube"
        )
        history_service.log_download(item)
        time.sleep(1)  # 确保时间戳不同
    
    # 验证记录数量和顺序
    records = history_service.get_recent(limit=3)
    assert len(records) == 3
    
    # 验证顺序（最新的在前）
    for i, record in enumerate(records):
        expected_index = 4 - i  # 4, 3, 2
        assert record.title == f"测试视频{expected_index}"
    
def test_get_by_status(history_service):
    """测试按状态获取记录。"""
    # 创建不同状态的记录
    for i in range(5):
        item = MediaItem(url=f"https://youtube.com/watch?v=test{i}")
        status = "success" if i % 2 == 0 else "failed"
        history_service.log_download(item, status=status)
        time.sleep(1)  # 确保时间戳不同
    
    # 验证成功记录
    success_records = history_service.get_by_status("success")
    assert len(success_records) == 3
    for record in success_records:
        assert record.status == "success"
        
    # 验证失败记录
    failed_records = history_service.get_by_status("failed")
    assert len(failed_records) == 2
    for record in failed_records:
        assert record.status == "failed"
        
def test_get_by_creator(history_service):
    """测试获取创作者记录。"""
    # 创建不同创作者的记录
    creators = ["UC1", "UC2"]
    for creator_id in creators:
        for i in range(3):
            item = MediaItem(
                url=f"https://youtube.com/watch?v=test{i}",
                creator_id=creator_id
            )
            history_service.log_download(item)
            time.sleep(1)  # 确保时间戳不同
            
    # 验证每个创作者的记录
    for creator_id in creators:
        records = history_service.get_by_creator(creator_id)
        assert len(records) == 3
        for record in records:
            assert record.creator_id == creator_id
            
def test_clear_history(history_service):
    """测试清理历史记录。"""
    # 创建一些记录
    for i in range(5):
        item = MediaItem(url=f"https://youtube.com/watch?v=test{i}")
        history_service.log_download(item)
        time.sleep(1)  # 确保时间戳不同
        
    # 修改部分记录的创建时间
    with Session(history_service.engine) as session:
        old_records = session.query(DownloadHistory).filter(
            DownloadHistory.id <= 2
        ).all()
        for record in old_records:
            record.created_at = datetime.utcnow() - timedelta(days=40)
        session.commit()
    
    # 清理30天前的记录
    assert history_service.clear_history(days=30)
    
    # 验证剩余记录
    records = history_service.get_recent()
    assert len(records) == 3  # 应该只剩下3条记录 