"""测试创作者管理服务。"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.services.creator import CreatorManager
from src.models.creators import Creator
from src.schemas.creator import CreatorUpdate
from src.models.base import Base

@pytest.fixture
def creator_manager():
    """创建创作者管理服务实例。"""
    manager = CreatorManager("sqlite:///:memory:")
    # 初始化数据库表
    Base.metadata.create_all(manager.engine)
    return manager

@pytest.fixture
def mock_platform_api():
    """模拟平台API。"""
    mock_api = Mock()
    mock_api.get_followed_creators.return_value = [
        Mock(
            id="user1",
            name="测试用户1",
            avatar_url="http://example.com/avatar1.jpg",
            description="测试简介1",
            metadata={"followers": 1000}
        ),
        Mock(
            id="user2",
            name="测试用户2",
            avatar_url="http://example.com/avatar2.jpg",
            description="测试简介2",
            metadata={"followers": 2000}
        )
    ]
    return mock_api

def test_sync_creators(creator_manager, mock_platform_api):
    """测试同步创作者数据。"""
    with patch.object(
        creator_manager,
        '_get_platform_api',
        return_value=mock_platform_api
    ):
        # 执行同步
        assert creator_manager.sync_creators("twitter")
        
        # 验证数据
        with Session(creator_manager.engine) as session:
            creators = session.query(Creator).all()
            assert len(creators) == 2
            
            creator1 = creators[0]
            assert creator1.name == "测试用户1"
            assert creator1.avatar == "http://example.com/avatar1.jpg"
            assert creator1.description == "测试简介1"
            assert creator1.extra_data == {"followers": 1000}
            assert "twitter" in creator1.platforms
            
def test_update_creator(creator_manager):
    """测试更新创作者信息。"""
    # 创建测试数据
    creator_manager._update_or_create(
        platform_id="test1",
        platform="twitter",
        name="原始名称",
        description="原始简介"
    )
    
    # 更新数据
    update_data = CreatorUpdate(
        name="新名称",
        description="新简介",
        extra_data={"followers": 3000}
    )
    
    updated = creator_manager.update_creator(
        platform="twitter",
        platform_id="test1",
        update_data=update_data
    )
    
    assert updated is not None
    assert updated.name == "新名称"
    assert updated.description == "新简介"
    assert updated.extra_data == {"followers": 3000}
    
def test_search_creators(creator_manager):
    """测试搜索创作者。"""
    # 创建测试数据
    creator_manager._update_or_create(
        platform_id="test1",
        platform="twitter",
        name="测试用户1",
        description="测试简介"
    )
    creator_manager._update_or_create(
        platform_id="test2",
        platform="youtube",
        name="测试用户2",
        description="另一个简介"
    )
    
    # 测试关键词搜索
    results = creator_manager.search_creators("测试")
    assert len(results) == 2
    
    # 测试平台过滤
    results = creator_manager.search_creators("测试", platform="twitter")
    assert len(results) == 1
    assert results[0].name == "测试用户1"
    
def test_delete_creator(creator_manager):
    """测试删除创作者。"""
    # 创建测试数据
    creator_manager._update_or_create(
        platform_id="test1",
        platform="twitter",
        name="测试用户"
    )
    
    # 删除数据
    assert creator_manager.delete_creator("twitter", "test1")
    
    # 验证删除
    with Session(creator_manager.engine) as session:
        creator = session.query(Creator).first()
        assert creator is None
        
def test_get_creator(creator_manager):
    """测试获取创作者信息。"""
    # 创建测试数据
    original = creator_manager._update_or_create(
        platform_id="test1",
        platform="twitter",
        name="测试用户",
        extra_data={"followers": 1000}
    )
    
    # 获取数据
    creator = creator_manager.get_creator("twitter", "test1")
    assert creator is not None
    assert creator.id == original.id
    assert creator.name == "测试用户"
    assert creator.extra_data == {"followers": 1000}
    
def test_unified_id_generation(creator_manager):
    """测试统一ID生成。"""
    id1 = creator_manager._generate_unified_id("twitter", "user1")
    id2 = creator_manager._generate_unified_id("twitter", "user1")
    id3 = creator_manager._generate_unified_id("youtube", "user1")
    
    # 相同平台和用户ID应该生成相同的统一ID
    assert id1 == id2
    # 不同平台应该生成不同的统一ID
    assert id1 != id3 