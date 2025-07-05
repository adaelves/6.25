import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QListWidget,
    QListWidgetItem, QTabWidget, QComboBox, QSpinBox, QCheckBox,
    QSystemTrayIcon, QMenu, QMessageBox, QFileDialog, QScrollArea,
    QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QThread, QObject
from PySide6.QtGui import QIcon, QAction

from ..core.config_manager import ConfigManager
from ..core.download_manager import DownloadManager, DownloadTask

class DownloadTaskWidget(QFrame):
    """下载任务卡片组件"""
    def __init__(self, task: DownloadTask, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.task = task
        
        layout = QVBoxLayout(self)
        
        # 标题
        self.title_label = QLabel(task.title)
        layout.addWidget(self.title_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.update_progress()
        layout.addWidget(self.progress_bar)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("暂停" if task.status == "downloading" else "继续")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        # 状态信息
        self.status_label = QLabel(self.get_status_text())
        layout.addWidget(self.status_label)
        
        # 连接信号
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn.clicked.connect(self.cancel_download)
    
    def update_progress(self):
        """更新进度条"""
        if self.task.total_size > 0:
            progress = int(self.task.downloaded_size / self.task.total_size * 100)
            self.progress_bar.setValue(progress)
            
            # 更新状态文本
            speed_text = f"{self.task.speed / 1024:.1f} KB/s" if self.task.speed > 0 else ""
            size_text = f"{self.task.downloaded_size / 1024 / 1024:.1f}/{self.task.total_size / 1024 / 1024:.1f} MB"
            self.status_label.setText(f"{self.get_status_text()} {speed_text} {size_text}")
    
    def get_status_text(self) -> str:
        """获取状态文本"""
        status_map = {
            "waiting": "等待中",
            "downloading": "下载中",
            "paused": "已暂停",
            "completed": "已完成",
            "error": f"错误: {self.task.error_message}",
            "cancelled": "已取消"
        }
        return status_map.get(self.task.status, "未知状态")
    
    def toggle_pause(self):
        """切换暂停/继续状态"""
        if self.task.status == "downloading":
            self.pause_btn.setText("继续")
            self.task.status = "paused"
        else:
            self.pause_btn.setText("暂停")
            self.task.status = "downloading"
    
    def cancel_download(self):
        """取消下载"""
        self.task.status = "cancelled"
        self.status_label.setText("已取消")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

class DownloadWorker(QObject):
    """下载工作线程"""
    progress_updated = Signal(DownloadTask)
    task_finished = Signal(DownloadTask)
    
    def __init__(self, download_manager: DownloadManager):
        super().__init__()
        self.manager = download_manager
        self.running = False
    
    async def run(self):
        """运行下载工作线程"""
        self.running = True
        await self.manager.start()
        
        while self.running:
            # 更新所有任务的状态
            for task in self.manager.get_active_tasks():
                self.progress_updated.emit(task)
            await asyncio.sleep(0.1)
    
    def stop(self):
        """停止工作线程"""
        self.running = False

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频下载器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化配置管理器
        self.config = ConfigManager()
        
        # 初始化下载管理器
        self.download_manager = DownloadManager(self.config)
        
        # 初始化下载工作线程
        self.download_thread = QThread()
        self.download_worker = DownloadWorker(self.download_manager)
        self.download_worker.moveToThread(self.download_thread)
        self.download_worker.progress_updated.connect(self.update_task_progress)
        self.download_thread.started.connect(lambda: asyncio.run(self.download_worker.run()))
        self.download_thread.start()
        
        # 加载样式表
        self.load_stylesheet()
        
        # 创建中心部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # 顶部工具栏
        self.create_toolbar()
        
        # 全局速度显示
        self.speed_widget = self.create_speed_widget()
        self.layout.addWidget(self.speed_widget)
        
        # URL输入区域
        self.url_widget = self.create_url_input()
        self.layout.addWidget(self.url_widget)
        
        # 主标签页
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # 添加各个标签页
        self.setup_download_tab()
        self.setup_history_tab()
        self.setup_creator_tab()
        self.setup_settings_tab()
        
        # 初始化系统托盘
        self.setup_tray()
        
        # 启动定时器更新速度显示
        self.speed_timer = QTimer(self)
        self.speed_timer.timeout.connect(self.update_speed)
        self.speed_timer.start(1000)
        
        # 加载配置
        self.load_config()
        
        # 加载历史记录
        self.load_history()
    
    def closeEvent(self, event):
        """关闭窗口事件"""
        # 停止下载工作线程
        self.download_worker.stop()
        self.download_thread.quit()
        self.download_thread.wait()
        
        # 停止下载管理器
        asyncio.run(self.download_manager.stop())
        
        event.accept()

    def load_stylesheet(self):
        """加载样式表"""
        style_path = Path(__file__).parent / "styles.qss"
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def load_config(self):
        """加载配置到界面"""
        # 下载路径
        path = self.config.get_download_path()
        self.path_input.setText(path)
        
        # 最大线程数
        threads = self.config.get_max_threads()
        self.thread_spin.setValue(threads)
        
        # 下载限速
        speed_limit = self.config.get_speed_limit()
        self.speed_limit.setValue(speed_limit)
        
        # 代理设置
        proxy_settings = self.config.get_proxy_settings()
        self.proxy_check.setChecked(proxy_settings["enabled"])
        self.proxy_input.setText(proxy_settings["address"])
    
    def load_history(self):
        """加载下载历史"""
        for task in self.download_manager.get_completed_tasks():
            self.add_history_item(task)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        
        # 添加工具栏按钮
        start_all = QAction("全部开始", self)
        start_all.triggered.connect(self.start_all_tasks)
        pause_all = QAction("全部暂停", self)
        pause_all.triggered.connect(self.pause_all_tasks)
        toolbar.addAction(start_all)
        toolbar.addAction(pause_all)

    def create_speed_widget(self) -> QWidget:
        """创建速度显示组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        self.download_speed = QLabel("↓ 0 KB/s")
        self.upload_speed = QLabel("↑ 0 KB/s")
        
        layout.addStretch()
        layout.addWidget(self.download_speed)
        layout.addWidget(self.upload_speed)
        
        return widget

    def create_url_input(self) -> QWidget:
        """创建URL输入区域"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入视频URL或粘贴多个链接（换行分隔）")
        
        self.download_btn = QPushButton("开始下载")
        self.download_btn.clicked.connect(self.start_download)
        
        layout.addWidget(self.url_input)
        layout.addWidget(self.download_btn)
        
        return widget

    def setup_download_tab(self):
        """设置下载任务标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 使用滚动区域包装任务列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 任务列表容器
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.addStretch()
        
        scroll.setWidget(self.task_container)
        layout.addWidget(scroll)
        
        self.tabs.addTab(tab, "下载任务")

    def setup_history_tab(self):
        """设置历史记录标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        
        self.tabs.addTab(tab, "历史记录")

    def setup_creator_tab(self):
        """设置创作者监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.creator_list = QListWidget()
        layout.addWidget(self.creator_list)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加创作者")
        refresh_btn = QPushButton("刷新")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(refresh_btn)
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(tab, "创作者监控")

    def setup_settings_tab(self):
        """设置设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 下载路径设置
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择下载路径")
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_download_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # 最大线程数
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("最大下载线程："))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 16)
        self.thread_spin.setValue(4)
        thread_layout.addWidget(self.thread_spin)
        layout.addLayout(thread_layout)
        
        # 下载限速
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("下载限速(KB/s)："))
        self.speed_limit = QSpinBox()
        self.speed_limit.setRange(0, 10000)
        self.speed_limit.setValue(0)
        self.speed_limit.setSpecialValueText("不限速")
        speed_layout.addWidget(self.speed_limit)
        layout.addLayout(speed_layout)
        
        # 代理设置
        proxy_layout = QHBoxLayout()
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("127.0.0.1:7890")
        proxy_layout.addWidget(self.proxy_check)
        proxy_layout.addWidget(self.proxy_input)
        layout.addLayout(proxy_layout)
        
        # 保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        self.tabs.addTab(tab, "设置")

    def setup_tray(self):
        """设置系统托盘"""
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("视频下载器")
        
        menu = QMenu()
        show_action = menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show)
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)
        
        self.tray.setContextMenu(menu)
        self.tray.show()

    @Slot()
    def browse_download_path(self):
        """选择下载路径"""
        path = QFileDialog.getExistingDirectory(self, "选择下载路径")
        if path:
            self.path_input.setText(path)

    @Slot()
    def save_settings(self):
        """保存设置"""
        # 保存下载路径
        self.config.set_download_path(self.path_input.text())
        
        # 保存最大线程数
        self.config.set_max_threads(self.thread_spin.value())
        
        # 保存下载限速
        self.config.set_speed_limit(self.speed_limit.value())
        
        # 保存代理设置
        self.config.set_proxy_settings(
            self.proxy_check.isChecked(),
            self.proxy_input.text()
        )
        
        QMessageBox.information(self, "提示", "设置已保存")

    @Slot()
    def start_download(self):
        """开始下载"""
        urls = self.url_input.text().split("\n")
        for url in urls:
            if url.strip():
                # 创建下载任务
                task = self.download_manager.add_task(
                    url=url.strip(),
                    title=f"视频_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                
                # 添加任务卡片
                self.add_task_widget(task)
                
                # 开始下载
                asyncio.run(self.download_manager.start_task(url))
        
        self.url_input.clear()

    def add_task_widget(self, task: DownloadTask):
        """添加任务卡片"""
        widget = DownloadTaskWidget(task)
        self.task_layout.insertWidget(self.task_layout.count() - 1, widget)

    def add_history_item(self, task: DownloadTask):
        """添加历史记录项"""
        item = QListWidgetItem(f"{task.title} - {task.complete_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.history_list.addItem(item)

    @Slot(DownloadTask)
    def update_task_progress(self, task: DownloadTask):
        """更新任务进度"""
        # 查找任务卡片
        for i in range(self.task_layout.count()):
            widget = self.task_layout.itemAt(i).widget()
            if isinstance(widget, DownloadTaskWidget) and widget.task.url == task.url:
                widget.task = task
                widget.update_progress()
                break

    @Slot()
    def update_speed(self):
        """更新全局速度显示"""
        total_download_speed = 0
        total_upload_speed = 0
        
        for task in self.download_manager.get_active_tasks():
            total_download_speed += task.speed
        
        self.download_speed.setText(f"↓ {total_download_speed / 1024:.1f} KB/s")
        self.upload_speed.setText(f"↑ {total_upload_speed / 1024:.1f} KB/s")

    def start_all_tasks(self):
        """开始所有任务"""
        for task in self.download_manager.get_all_tasks():
            if task.status in ["waiting", "paused"]:
                asyncio.run(self.download_manager.start_task(task.url))

    def pause_all_tasks(self):
        """暂停所有任务"""
        for task in self.download_manager.get_active_tasks():
            asyncio.run(self.download_manager.pause_task(task.url))

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 