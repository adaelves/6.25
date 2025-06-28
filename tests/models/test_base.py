"""测试数据库基础配置。"""

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from src.models.base import Base

def test_get_db(test_db):
    """测试数据库会话获取。"""
    engine, session = test_db
    assert isinstance(session, Session)
    
def test_init_db(test_db):
    """测试数据库初始化。"""
    engine, session = test_db
    
    # 删除所有表
    Base.metadata.drop_all(engine)
    
    # 重新初始化
    Base.metadata.create_all(engine)
    
    # 验证表是否创建
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'download_history' in tables
    assert 'creators' in tables 