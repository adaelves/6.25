"""模型混入类。

提供通用的模型功能混入。
"""

from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

class TimestampMixin:
    """时间戳混入。
    
    为模型添加创建时间和更新时间字段。
    """
    
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    ) 