"""创作者监控对话框模块。

提供创作者监控界面。
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QComboBox,
    QMessageBox,
    QMenu,
    QHeaderView,
    QAction,
    QProgressBar,
    QLineEdit
)
from PySide6.QtCore import Qt, Signal, QTimer

from ...services.creator import CreatorManager
from ...services.scanner import VideoScanner
from ...utils.i18n import i18n

class CreatorMonitorDialog(QDialog):
    """创作者监控对话框。
    
    提供以下功能：
    1. 创作者列表
    2. 同步状态
    3. 视频统计
    4. 错误信息
    
    Signals:
        creator_updated: 创作者更新信号
    """
    
    creator_updated = Signal(str)
    
    def __init__(
        self,
        creator_manager: CreatorManager,
        video_scanner: VideoScanner,
        parent: Optional[QWidget] = None
    ):
        """初始化创作者监控对话框。
        
        Args:
            creator_manager: 创作者管理器
            video_scanner: 视频扫描器
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.creator_manager = creator_manager
        self.video_scanner = video_scanner
        self._creators = []  # 缓存创作者列表
        
        self.setWindowTitle(i18n.tr("创作者监控"))
        self.setMinimumSize(800, 600)
        
        # 创建界面
        self._create_ui()
        
        # 创建定时器
        self._create_timer()
        
        # 设置进度条
        self.progress_bar.hide()
        
        # 设置虚拟滚动
        self.table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        # 虚拟滚动参数
        self._visible_rows = 20  # 可见行数
        self._buffer_rows = 10   # 缓冲行数
        self._total_rows = 0     # 总行数
        self._current_scroll = 0  # 当前滚动位置
        
        # 加载数据
        self._load_data()
        
        # 连接信号
        self.video_scanner.scan_progress.connect(self._on_scan_progress)
        self.video_scanner.scan_finished.connect(self._on_scan_finished)
        
    def _create_ui(self):
        """创建界面。"""
        layout = QVBoxLayout()
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 平台选择
        self.platform_combo = QComboBox()
        self.platform_combo.addItems([
            i18n.tr("全部平台"),
            "YouTube",
            "Twitter",
            "Bilibili",
            "抖音",
            "快手"
        ])
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        toolbar.addWidget(QLabel(i18n.tr("平台:")))
        toolbar.addWidget(self.platform_combo)
        
        # 同步按钮
        self.sync_button = QPushButton(i18n.tr("同步"))
        self.sync_button.clicked.connect(self._sync_creators)
        toolbar.addWidget(self.sync_button)
        
        # 刷新按钮
        self.refresh_button = QPushButton(i18n.tr("刷新"))
        self.refresh_button.clicked.connect(self._load_data)
        toolbar.addWidget(self.refresh_button)
        
        # 批量操作按钮
        batch_button = QPushButton(i18n.tr("批量操作"))
        batch_menu = QMenu()
        
        # 批量同步
        batch_sync_action = QAction(i18n.tr("批量同步"), self)
        batch_sync_action.triggered.connect(self._batch_sync)
        batch_menu.addAction(batch_sync_action)
        
        # 批量删除
        batch_delete_action = QAction(i18n.tr("批量删除"), self)
        batch_delete_action.triggered.connect(self._batch_delete)
        batch_menu.addAction(batch_delete_action)
        
        batch_button.setMenu(batch_menu)
        toolbar.addWidget(batch_button)
        
        toolbar.addStretch()
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(i18n.tr("搜索创作者..."))
        self.search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_edit)
        
        layout.addLayout(toolbar)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            i18n.tr("ID"),
            i18n.tr("名称"),
            i18n.tr("平台"),
            i18n.tr("视频数"),
            i18n.tr("已下载"),
            i18n.tr("总时长"),
            i18n.tr("总大小"),
            i18n.tr("状态")
        ])
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        
        # 启用多选
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        
        # 设置右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._show_context_menu
        )
        
        # 设置样式
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f7f7f7;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        
        layout.addWidget(self.table)
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel()
        self.sync_status_label = QLabel()
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.sync_status_label)
        layout.addLayout(status_layout)
        
        self.setLayout(layout)
        
    def _create_timer(self):
        """创建定时器。"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(5000)  # 5秒更新一次 

    def _load_data(self):
        """加载数据。"""
        try:
            # 获取当前平台
            platform = self.platform_combo.currentText()
            if platform == i18n.tr("全部平台"):
                platform = None
                
            # 获取创作者列表
            self._creators = self.creator_manager.search_creators("", platform)
            self._total_rows = len(self._creators)
            
            # 更新表格
            self._update_visible_rows()
            
            # 更新状态栏
            self.status_label.setText(i18n.tr("共 {count} 个创作者").format(count=self._total_rows))
            
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("加载数据失败: {error}").format(error=str(e))
            )
            
    def _update_visible_rows(self):
        """更新可见行。"""
        if not self._creators:
            return
            
        # 计算可见范围
        start = max(0, self._current_scroll - self._buffer_rows)
        end = min(self._total_rows, self._current_scroll + self._visible_rows + self._buffer_rows)
        
        # 设置表格行数
        self.table.setRowCount(self._total_rows)
        
        # 更新可见行
        for row in range(start, end):
            creator = self._creators[row]
            
            # 检查行是否已经填充
            if not self.table.item(row, 0):
                self._fill_row(row, creator)
                
    def _fill_row(self, row: int, creator: Creator):
        """填充表格行。
        
        Args:
            row: 行号
            creator: 创作者对象
        """
        # ID
        id_item = QTableWidgetItem(creator.id)
        self.table.setItem(row, 0, id_item)
        
        # 名称
        name_item = QTableWidgetItem(creator.name)
        self.table.setItem(row, 1, name_item)
        
        # 平台
        platforms = ", ".join(creator.platforms.keys())
        platform_item = QTableWidgetItem(platforms)
        self.table.setItem(row, 2, platform_item)
        
        # 获取统计信息
        stats = creator.stats
        if stats:
            # 视频数
            total_item = QTableWidgetItem(str(stats.total_videos))
            self.table.setItem(row, 3, total_item)
            
            # 已下载
            downloaded_item = QTableWidgetItem(str(stats.downloaded_videos))
            self.table.setItem(row, 4, downloaded_item)
            
            # 总时长
            duration = timedelta(seconds=stats.total_duration)
            duration_item = QTableWidgetItem(str(duration))
            self.table.setItem(row, 5, duration_item)
            
            # 总大小
            size_item = QTableWidgetItem(self._format_size(stats.total_size))
            self.table.setItem(row, 6, size_item)
            
            # 状态
            status_item = QTableWidgetItem(stats.sync_status)
            self.table.setItem(row, 7, status_item)
            
    def _format_size(self, size: int) -> str:
        """格式化文件大小。
        
        Args:
            size: 文件大小（字节）
            
        Returns:
            str: 格式化后的大小
        """
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/1024/1024:.1f} MB"
        else:
            return f"{size/1024/1024/1024:.1f} GB"

    def _on_scan_progress(self, current: int, total: int):
        """扫描进度更新处理。
        
        Args:
            current: 当前进度
            total: 总数
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.show()
        
        # 更新状态
        self.sync_status_label.setText(
            i18n.tr("正在同步: {current}/{total}").format(
                current=current,
                total=total
            )
        )
        
    def _on_scan_finished(self):
        """扫描完成处理。"""
        self.progress_bar.hide()
        self.sync_status_label.clear()
        
        # 刷新数据
        self._load_data()
        
    def _on_search(self, text: str):
        """搜索处理。
        
        Args:
            text: 搜索文本
        """
        # 获取当前平台
        platform = self.platform_combo.currentText()
        if platform == i18n.tr("全部平台"):
            platform = None
            
        # 搜索创作者
        self._creators = self.creator_manager.search_creators(text, platform)
        self._total_rows = len(self._creators)
        
        # 更新表格
        self._update_visible_rows()
        
        # 更新状态栏
        self.status_label.setText(i18n.tr("共 {count} 个创作者").format(
            count=self._total_rows
        ))
        
    def _sync_creators(self):
        """同步创作者数据。"""
        try:
            # 禁用按钮
            self.sync_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            
            # 获取当前平台
            platform = self.platform_combo.currentText()
            if platform == i18n.tr("全部平台"):
                platform = None
                
            # 开始同步
            self.video_scanner.scan_creators(platform)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("同步失败: {error}").format(error=str(e))
            )
            
            # 启用按钮
            self.sync_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
            
    def _update_stats(self):
        """更新统计信息。"""
        try:
            # 获取所有创作者ID
            creator_ids = []
            for row in range(self.table.rowCount()):
                creator_id = self.table.item(row, 0).text()
                creator_ids.append(creator_id)
                
            # 获取最新统计信息
            for row, creator_id in enumerate(creator_ids):
                creator = self.creator_manager.get_creator(creator_id)
                if not creator:
                    continue
                    
                stats = creator.stats
                if not stats:
                    continue
                    
                # 更新统计数据
                self.table.item(row, 3).setText(str(stats.total_videos))
                self.table.item(row, 4).setText(str(stats.downloaded_videos))
                self.table.item(row, 5).setText(str(timedelta(seconds=stats.total_duration)))
                self.table.item(row, 6).setText(self._format_size(stats.total_size))
                self.table.item(row, 7).setText(stats.sync_status)
                
        except Exception as e:
            print(f"更新统计信息失败: {e}")
            
    def _on_platform_changed(self, platform: str):
        """平台切换处理。
        
        Args:
            platform: 平台名称
        """
        self._load_data()
        
    def _show_context_menu(self, pos):
        """显示右键菜单。
        
        Args:
            pos: 鼠标位置
        """
        menu = QMenu(self)
        
        # 获取选中的行
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
            
        # 获取创作者ID
        creator_id = self.table.item(row, 0).text()
        
        # 添加菜单项
        sync_action = QAction(i18n.tr("同步"), self)
        sync_action.triggered.connect(lambda: self._sync_creator(creator_id))
        menu.addAction(sync_action)
        
        delete_action = QAction(i18n.tr("删除"), self)
        delete_action.triggered.connect(lambda: self._delete_creator(creator_id))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec_(self.table.viewport().mapToGlobal(pos))
        
    def _sync_creator(self, creator_id: str):
        """同步指定创作者。
        
        Args:
            creator_id: 创作者ID
        """
        try:
            self.video_scanner.scan_creator(creator_id)
            self._load_data()
            
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("同步失败: {error}").format(error=str(e))
            )
            
    def _delete_creator(self, creator_id: str):
        """删除指定创作者。
        
        Args:
            creator_id: 创作者ID
        """
        try:
            # 确认删除
            reply = QMessageBox.question(
                self,
                i18n.tr("确认"),
                i18n.tr("确定要删除该创作者吗？"),
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.creator_manager.delete_creator(creator_id)
                self._load_data()
                
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("删除失败: {error}").format(error=str(e))
            )
            
    def _on_scroll(self, value: int):
        """滚动事件处理。
        
        Args:
            value: 滚动位置
        """
        # 计算当前第一个可见行
        row_height = self.table.rowHeight(0)
        viewport_height = self.table.viewport().height()
        
        self._current_scroll = value // row_height
        self._visible_rows = viewport_height // row_height
        
        # 更新可见行
        self._update_visible_rows()
        
    def resizeEvent(self, event):
        """窗口大小改变事件。"""
        super().resizeEvent(event)
        
        # 重新计算可见行数
        row_height = self.table.rowHeight(0)
        viewport_height = self.table.viewport().height()
        self._visible_rows = viewport_height // row_height
        
        # 更新可见行
        self._update_visible_rows()
        
    def _batch_sync(self):
        """批量同步创作者。"""
        try:
            # 获取选中的行
            selected_rows = set(item.row() for item in self.table.selectedItems())
            if not selected_rows:
                QMessageBox.warning(
                    self,
                    i18n.tr("警告"),
                    i18n.tr("请先选择要同步的创作者")
                )
                return
                
            # 获取创作者ID
            creator_ids = [
                self.table.item(row, 0).text()
                for row in selected_rows
            ]
            
            # 确认同步
            reply = QMessageBox.question(
                self,
                i18n.tr("确认"),
                i18n.tr("确定要同步选中的 {count} 个创作者吗？").format(
                    count=len(creator_ids)
                ),
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 禁用按钮
                self.sync_button.setEnabled(False)
                self.refresh_button.setEnabled(False)
                
                # 执行同步
                for creator_id in creator_ids:
                    self.video_scanner.scan_creator(creator_id)
                    
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("批量同步失败: {error}").format(error=str(e))
            )
            
            # 启用按钮
            self.sync_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
            
    def _batch_delete(self):
        """批量删除创作者。"""
        try:
            # 获取选中的行
            selected_rows = set(item.row() for item in self.table.selectedItems())
            if not selected_rows:
                QMessageBox.warning(
                    self,
                    i18n.tr("警告"),
                    i18n.tr("请先选择要删除的创作者")
                )
                return
                
            # 获取创作者ID
            creator_ids = [
                self.table.item(row, 0).text()
                for row in selected_rows
            ]
            
            # 确认删除
            reply = QMessageBox.question(
                self,
                i18n.tr("确认"),
                i18n.tr("确定要删除选中的 {count} 个创作者吗？").format(
                    count=len(creator_ids)
                ),
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 执行删除
                for creator_id in creator_ids:
                    self.creator_manager.delete_creator(creator_id)
                    
                # 刷新数据
                self._load_data()
                
        except Exception as e:
            QMessageBox.warning(
                self,
                i18n.tr("错误"),
                i18n.tr("批量删除失败: {error}").format(error=str(e))
            ) 