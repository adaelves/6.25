"""测试配置文件。"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base import Base

@pytest.fixture(scope="function")
def test_db():
    """创建测试数据库。
    
    Returns:
        tuple: (engine, session)
    """
    # 创建临时数据库文件
    temp_db = tempfile.NamedTemporaryFile(delete=True)
    temp_db.close()
    
    # 创建数据库引擎
    engine = create_engine(
        "sqlite:///:memory:",  # 使用内存数据库
        connect_args={"check_same_thread": False}
    )
    
    # 创建表
    Base.metadata.create_all(engine)
    
    # 创建会话
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield engine, session
    
    # 清理
    session.close()
    Base.metadata.drop_all(engine) 