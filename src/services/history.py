"""下载历史记录服务。

提供下载历史的记录和查询功能。
"""

from datetime import datetime, timedelta
import csv
import json
import os
from typing import List, Optional, Dict, Any, Set
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from tqdm import tqdm

from ..models.history import DownloadHistory
from ..schemas.media import MediaItem

logger = logging.getLogger(__name__)

# 默认导出字段
DEFAULT_EXPORT_FIELDS = {
    'id': '记录ID',
    'url': '视频链接',
    'title': '视频标题',
    'platform': '平台',
    'creator_id': '创作者ID',
    'file_path': '文件路径',
    'file_size': '文件大小(MB)',
    'duration': '时长(秒)',
    'status': '状态',
    'error_message': '错误信息',
    'created_at': '创建时间',
    'updated_at': '更新时间'
}

class HistoryService:
    """下载历史记录服务。
    
    提供下载历史的记录和查询功能。
    
    Attributes:
        engine: SQLAlchemy引擎实例
    """
    
    def __init__(self, db_url: str):
        """初始化历史记录服务。
        
        Args:
            db_url: 数据库连接URL
        """
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False}  # SQLite特定配置
        )
        
    def log_download(
        self,
        item: MediaItem,
        status: str = 'success',
        error: Optional[str] = None
    ) -> bool:
        """记录下载历史。
        
        Args:
            item: 媒体项
            status: 下载状态，默认为'success'
            error: 错误信息，可选
            
        Returns:
            bool: 是否记录成功
            
        Raises:
            ValueError: 当状态值无效时
        """
        try:
            with Session(self.engine) as session:
                now = datetime.utcnow()
                history = DownloadHistory(
                    url=item.url,
                    title=item.title,
                    platform=item.platform,
                    creator_id=item.creator_id,
                    file_path=item.file_path,
                    file_size=item.file_size,
                    duration=item.duration,
                    status=status,
                    error=error,
                    created_at=now,
                    updated_at=now
                )
                session.add(history)
                session.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to log download history: {e}")
            return False
            
    def get_recent(self, limit: int = 100) -> List[DownloadHistory]:
        """获取最近的下载记录。
        
        Args:
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent history: {e}")
            return []
            
    def get_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[DownloadHistory]:
        """按状态获取下载记录。
        
        Args:
            status: 下载状态
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
            
        Raises:
            ValueError: 当状态值无效时
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).filter_by(
                    status=status
                ).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get history by status: {e}")
            return []
            
    def get_by_creator(
        self,
        creator_id: str,
        limit: int = 100
    ) -> List[DownloadHistory]:
        """获取指定创作者的下载记录。
        
        Args:
            creator_id: 创作者ID
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).filter_by(
                    creator_id=creator_id
                ).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get history by creator: {e}")
            return []
            
    def clear_history(self, days: int = 30) -> bool:
        """清理指定天数之前的历史记录。
        
        Args:
            days: 保留天数，默认30天
            
        Returns:
            bool: 是否清理成功
        """
        try:
            with Session(self.engine) as session:
                cutoff = datetime.utcnow() - timedelta(days=days)
                session.query(DownloadHistory).filter(
                    DownloadHistory.created_at < cutoff
                ).delete()
                session.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to clear history: {e}")
            return False

    def export_history(
        self,
        filename: str,
        format: str = 'csv',
        fields: Optional[Set[str]] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        status_filter: Optional[str] = None,
        batch_size: int = 1000
    ) -> bool:
        """导出下载历史记录。

        Args:
            filename: 导出文件路径
            format: 导出格式，支持'csv'和'json'，默认'csv'
            fields: 要导出的字段集合，默认导出所有字段
            time_range: 时间范围元组(开始时间, 结束时间)，可选
            status_filter: 状态过滤，可选
            batch_size: 批处理大小，默认1000条

        Returns:
            bool: 是否导出成功

        Raises:
            ValueError: 当format参数无效或filename后缀不匹配时
        """
        if format not in ('csv', 'json'):
            raise ValueError("导出格式必须是'csv'或'json'")

        # 验证文件后缀
        expected_ext = '.csv' if format == 'csv' else '.json'
        if not filename.endswith(expected_ext):
            raise ValueError(f"文件名必须以{expected_ext}结尾")

        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

        try:
            with Session(self.engine) as session:
                # 构建查询
                query = session.query(DownloadHistory)
                
                # 应用过滤条件
                if time_range:
                    start_time, end_time = time_range
                    query = query.filter(
                        DownloadHistory.created_at >= start_time,
                        DownloadHistory.created_at <= end_time
                    )
                if status_filter:
                    query = query.filter_by(status=status_filter)

                # 获取总记录数
                total_count = query.count()
                if total_count == 0:
                    logger.warning("没有找到符合条件的记录")
                    return False

                # 使用要导出的字段或默认字段
                export_fields = fields or DEFAULT_EXPORT_FIELDS.keys()

                # 创建进度条
                pbar = tqdm(total=total_count, desc="导出进度")

                if format == 'csv':
                    return self._export_to_csv(
                        filename, query, export_fields,
                        batch_size, pbar
                    )
                else:
                    return self._export_to_json(
                        filename, query, export_fields,
                        batch_size, pbar
                    )

        except SQLAlchemyError as e:
            logger.error(f"导出历史记录失败: {e}")
            return False
        except Exception as e:
            logger.error(f"导出过程中发生错误: {e}")
            return False

    def _export_to_csv(
        self,
        filename: str,
        query: Any,
        fields: Set[str],
        batch_size: int,
        pbar: Any
    ) -> bool:
        """导出为CSV格式。"""
        try:
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=fields,
                    extrasaction='ignore'
                )
                
                # 写入表头（使用中文字段名）
                headers = {
                    field: DEFAULT_EXPORT_FIELDS.get(field, field)
                    for field in fields
                }
                writer.writerow(headers)

                # 分批写入数据
                offset = 0
                while True:
                    records = query.limit(batch_size).offset(offset).all()
                    if not records:
                        break

                    for record in records:
                        row = record.to_dict()
                        # 格式化特殊字段
                        if 'file_size' in row:
                            row['file_size'] = f"{row['file_size'] / 1024 / 1024:.2f}"
                        writer.writerow(row)
                        pbar.update(1)

                    offset += batch_size

                return True

        except Exception as e:
            logger.error(f"CSV导出失败: {e}")
            return False
        finally:
            pbar.close()

    def _export_to_json(
        self,
        filename: str,
        query: Any,
        fields: Set[str],
        batch_size: int,
        pbar: Any
    ) -> bool:
        """导出为JSON格式。"""
        try:
            results = []
            offset = 0
            
            while True:
                records = query.limit(batch_size).offset(offset).all()
                if not records:
                    break

                for record in records:
                    row = record.to_dict()
                    # 只保留指定字段
                    filtered_row = {
                        k: v for k, v in row.items()
                        if k in fields
                    }
                    # 格式化特殊字段
                    if 'file_size' in filtered_row:
                        filtered_row['file_size'] = f"{filtered_row['file_size'] / 1024 / 1024:.2f}"
                    results.append(filtered_row)
                    pbar.update(1)

                offset += batch_size

            # 写入JSON文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        'total': len(results),
                        'fields': list(fields),
                        'data': results
                    },
                    f,
                    ensure_ascii=False,
                    indent=2
                )

            return True

        except Exception as e:
            logger.error(f"JSON导出失败: {e}")
            return False
        finally:
            pbar.close() 