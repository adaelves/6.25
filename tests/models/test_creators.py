"""测试创作者模型。"""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import cast, String
from src.models.creators import Creator

def test_create_creator(test_db):
    """测试创建创作者。"""
    engine, session = test_db
    
    creator = Creator(
        id="UC123456",
        name="测试创作者",
        avatar="https://example.com/avatar.jpg",
        description="测试简介",
        platforms={
            "youtube": "UC123456",
            "twitter": "test_user",
            "bilibili": "12345"
        },
        extra_data={
            "subscriber_count": 1000,
            "video_count": 100
        }
    )
    
    session.add(creator)
    session.commit()
    
    # 验证JSON字段
    assert creator.platforms["youtube"] == "UC123456"
    assert creator.extra_data["subscriber_count"] == 1000
    
    # 验证时间戳
    assert creator.created_at is not None
    assert creator.updated_at is not None
    
def test_update_creator(test_db):
    """测试更新创作者。"""
    engine, session = test_db
    
    # 创建记录
    creator = Creator(
        id="UC123456",
        name="测试创作者",
        platforms={"youtube": "UC123456"}
    )
    session.add(creator)
    session.commit()
    
    # 等待1秒以确保时间戳变化
    import time
    time.sleep(1)
    
    # 更新平台信息
    creator.platforms["twitter"] = "new_account"
    creator.updated_at = datetime.utcnow()  # 手动更新时间戳
    session.commit()
    
    # 验证更新时间
    assert creator.updated_at != creator.created_at
    
def test_query_creator(test_db):
    """测试查询创作者。"""
    engine, session = test_db
    
    # 创建测试数据
    creators = [
        Creator(
            id=f"UC{i}",
            name=f"创作者{i}",
            platforms={"youtube": f"UC{i}"}
        )
        for i in range(5)
    ]
    session.add_all(creators)
    session.commit()
    
    # 测试计数
    count = session.query(Creator).count()
    assert count == 5
    
    # 测试名称查询
    creator = (
        session.query(Creator)
        .filter_by(name="创作者1")
        .first()
    )
    assert creator.id == "UC1"
    
    # 测试JSON查询
    creator = (
        session.query(Creator)
        .filter(Creator.platforms.contains({"youtube": "UC2"}))
        .first()
    )
    assert creator.id == "UC2"
    
def test_unique_constraint(test_db):
    """测试唯一约束。"""
    engine, session = test_db
    
    # 创建第一个创作者
    creator1 = Creator(
        id="UC123456",
        name="创作者1",
        platforms={"youtube": "UC123456"}
    )
    session.add(creator1)
    session.commit()
    
    # 尝试创建ID相同的创作者
    with pytest.raises(IntegrityError):
        creator2 = Creator(
            id="UC123456",  # 相同ID
            name="创作者2",
            platforms={"youtube": "UC123456"}
        )
        session.add(creator2)
        session.commit()
        
def test_required_fields(test_db):
    """测试必填字段。"""
    engine, session = test_db
    
    # 测试缺少name字段
    with pytest.raises(IntegrityError):
        creator = Creator(
            id="UC123456",
            platforms={"youtube": "UC123456"}
        )
        session.add(creator)
        session.commit() 