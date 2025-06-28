"""数据库模型基础配置。

提供SQLAlchemy基础设置和工具函数。
"""

from contextlib import contextmanager
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
import os

# 创建基类
Base = declarative_base()

# 数据库连接配置
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite特定配置
    echo=False  # 设置为True可以显示SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    """获取数据库会话。
    
    用法:
    ```python
    with get_db() as db:
        db.query(Model).all()
    ```
    
    Returns:
        Session: 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库。
    
    创建所有表。
    """
    Base.metadata.create_all(bind=engine) 