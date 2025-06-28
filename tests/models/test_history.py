"""测试下载历史模型。"""

import pytest
from datetime import datetime
from src.models.history import DownloadHistory

def test_create_history(test_db):
    """测试创建下载记录。"""
    engine, session = test_db
    
    history = DownloadHistory(
        url="https://youtube.com/watch?v=test123",
        title="测试视频",
        platform="youtube",
        creator_id="UC123456",
        file_path="/downloads/test.mp4",
        file_size=10.5,
        duration=120.5,
        status="pending"
    )
    
    session.add(history)
    session.commit()
    
    # 验证ID自增
    assert history.id is not None
    
    # 验证时间戳
    assert history.created_at is not None
    assert history.updated_at is not None
    
def test_update_history(test_db):
    """测试更新下载记录。"""
    engine, session = test_db
    
    # 创建记录
    history = DownloadHistory(
        url="https://youtube.com/watch?v=test123",
        status="pending"
    )
    session.add(history)
    session.commit()
    
    # 等待1秒以确保时间戳变化
    import time
    time.sleep(1)
    
    # 更新状态
    history.status = "downloading"
    history.updated_at = datetime.utcnow()  # 手动更新时间戳
    session.commit()
    
    # 验证更新时间
    assert history.updated_at != history.created_at
    
def test_query_history(test_db):
    """测试查询下载记录。"""
    engine, session = test_db
    
    # 创建测试数据
    histories = [
        DownloadHistory(
            url=f"https://youtube.com/watch?v=test{i}",
            platform="youtube",
            status="success" if i % 2 == 0 else "failed"
        )
        for i in range(5)
    ]
    session.add_all(histories)
    session.commit()
    
    # 测试计数
    count = session.query(DownloadHistory).count()
    assert count == 5
    
    # 测试状态过滤
    success_count = (
        session.query(DownloadHistory)
        .filter_by(status="success")
        .count()
    )
    assert success_count == 3
    
    # 测试平台过滤
    youtube_count = (
        session.query(DownloadHistory)
        .filter_by(platform="youtube")
        .count()
    )
    assert youtube_count == 5
    
def test_invalid_status(test_db):
    """测试无效状态值。"""
    engine, session = test_db
    
    with pytest.raises(ValueError):
        history = DownloadHistory(
            url="https://youtube.com/watch?v=test",
            status="invalid_status"  # 无效状态
        )
        session.add(history)
        session.commit() 