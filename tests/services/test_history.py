"""测试历史记录服务。"""

import pytest
import time
import os
import json
import csv
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.services.history import HistoryService, DEFAULT_EXPORT_FIELDS
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

@pytest.fixture
def temp_dir(tmpdir):
    """创建临时目录。"""
    return str(tmpdir)

@pytest.fixture
def sample_data(history_service):
    """创建测试数据。"""
    items = []
    for i in range(5):
        item = MediaItem(
            url=f"https://youtube.com/watch?v=test{i}",
            title=f"测试视频{i}",
            platform="youtube",
            creator_id=f"UC{i}",
            file_path=f"/downloads/test{i}.mp4",
            file_size=1024 * 1024 * (i + 1),  # MB
            duration=60 * (i + 1)  # 秒
        )
        status = "success" if i % 2 == 0 else "failed"
        error = "下载失败" if status == "failed" else None
        history_service.log_download(item, status=status, error=error)
        items.append(item)
        time.sleep(0.1)  # 确保时间戳不同
    return items

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
    # 创建多条记录，每条记录间隔0.1秒
    for i in range(5):
        item = MediaItem(
            url=f"https://youtube.com/watch?v=test{i}",
            title=f"测试视频{i}",
            platform="youtube",
            creator_id=f"UC{i}"
        )
        history_service.log_download(item)
        time.sleep(0.1)  # 确保时间戳不同
    
    # 调试：检查所有记录的创建时间
    with Session(history_service.engine) as session:
        all_records = session.query(DownloadHistory).order_by(
            DownloadHistory.created_at.desc()
        ).all()
        print("\n调试信息：")
        for record in all_records:
            print(f"标题: {record.title}, 创建时间: {record.created_at}")
    
    # 验证记录数量和顺序
    records = history_service.get_recent(limit=3)
    assert len(records) == 3
    
    # 验证顺序（最新的在前）
    for i, record in enumerate(records):
        expected_index = 4 - i  # 4, 3, 2 (最新的在前)
        assert record.title == f"测试视频{expected_index}"
    
def test_get_by_status(history_service):
    """测试按状态获取记录。"""
    # 创建不同状态的记录
    for i in range(5):
        item = MediaItem(
            url=f"https://youtube.com/watch?v=test{i}",
            platform="youtube",
            creator_id=f"UC{i}"
        )
        status = "success" if i % 2 == 0 else "failed"
        history_service.log_download(item, status=status)
        time.sleep(0.1)  # 确保时间戳不同
    
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
                platform="youtube",
                creator_id=creator_id
            )
            history_service.log_download(item)
            time.sleep(0.1)  # 确保时间戳不同
            
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
        item = MediaItem(
            url=f"https://youtube.com/watch?v=test{i}",
            platform="youtube",
            creator_id=f"UC{i}"
        )
        history_service.log_download(item)
        time.sleep(0.1)  # 确保时间戳不同
        
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

def test_export_to_csv(history_service, sample_data, temp_dir):
    """测试导出CSV格式。"""
    output_file = os.path.join(temp_dir, "test.csv")
    
    # 执行导出
    assert history_service.export_history(output_file)
    
    # 验证文件存在
    assert os.path.exists(output_file)
    
    # 读取并验证内容
    with open(output_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # 验证记录数
        assert len(rows) == 5
        
        # 验证字段
        assert set(reader.fieldnames) == set(DEFAULT_EXPORT_FIELDS.values())
        
        # 验证内容（第一条记录）
        first_row = rows[0]
        assert first_row['视频标题'] == '测试视频0'
        assert first_row['状态'] == 'success'
        assert float(first_row['文件大小(MB)']) == 1.0
        assert float(first_row['时长(秒)']) == 60.0

def test_export_to_json(history_service, sample_data, temp_dir):
    """测试导出JSON格式。"""
    output_file = os.path.join(temp_dir, "test.json")
    
    # 执行导出
    assert history_service.export_history(output_file, format='json')
    
    # 验证文件存在
    assert os.path.exists(output_file)
    
    # 读取并验证内容
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
        # 验证结构
        assert 'total' in data
        assert 'fields' in data
        assert 'data' in data
        
        # 验证记录数
        assert data['total'] == 5
        assert len(data['data']) == 5
        
        # 验证字段
        assert set(data['fields']) == set(DEFAULT_EXPORT_FIELDS.keys())
        
        # 验证内容（第一条记录）
        first_record = data['data'][0]
        assert first_record['title'] == '测试视频0'
        assert first_record['status'] == 'success'
        assert float(first_record['file_size']) == 1.0
        assert first_record['duration'] == 60

def test_export_custom_fields(history_service, sample_data, temp_dir):
    """测试自定义字段导出。"""
    output_file = os.path.join(temp_dir, "custom.csv")
    custom_fields = {'title', 'status', 'file_size'}
    
    # 执行导出
    assert history_service.export_history(
        output_file,
        fields=custom_fields
    )
    
    # 验证文件存在
    assert os.path.exists(output_file)
    
    # 读取并验证内容
    with open(output_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # 验证字段
        expected_headers = {
            DEFAULT_EXPORT_FIELDS[field]
            for field in custom_fields
        }
        assert set(reader.fieldnames) == expected_headers

def test_export_time_range(history_service, sample_data, temp_dir):
    """测试时间范围过滤。"""
    output_file = os.path.join(temp_dir, "time_range.csv")
    
    # 修改部分记录的时间
    with Session(history_service.engine) as session:
        old_records = session.query(DownloadHistory).filter(
            DownloadHistory.id <= 2
        ).all()
        for record in old_records:
            record.created_at = datetime.utcnow() - timedelta(days=7)
        session.commit()
    
    # 导出最近3天的记录
    assert history_service.export_history(
        output_file,
        time_range=(
            datetime.utcnow() - timedelta(days=3),
            datetime.utcnow()
        )
    )
    
    # 验证记录数
    with open(output_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3

def test_export_status_filter(history_service, sample_data, temp_dir):
    """测试状态过滤。"""
    output_file = os.path.join(temp_dir, "success.csv")
    
    # 导出成功的记录
    assert history_service.export_history(
        output_file,
        status_filter='success'
    )
    
    # 验证记录数和状态
    with open(output_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3
        for row in rows:
            assert row['状态'] == 'success'

def test_export_invalid_format(history_service, temp_dir):
    """测试无效格式。"""
    output_file = os.path.join(temp_dir, "test.txt")
    
    # 验证异常
    with pytest.raises(ValueError) as exc:
        history_service.export_history(output_file, format='txt')
    assert "导出格式必须是'csv'或'json'" in str(exc.value)

def test_export_invalid_extension(history_service, temp_dir):
    """测试文件扩展名不匹配。"""
    output_file = os.path.join(temp_dir, "test.txt")
    
    # 验证异常
    with pytest.raises(ValueError) as exc:
        history_service.export_history(output_file)
    assert "文件名必须以.csv结尾" in str(exc.value)

def test_export_empty_result(history_service, temp_dir):
    """测试空结果集。"""
    output_file = os.path.join(temp_dir, "empty.csv")
    
    # 导出不存在的状态
    result = history_service.export_history(
        output_file,
        status_filter='not_exist'
    )
    
    # 验证结果
    assert result is False 