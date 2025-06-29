"""创作者监控对话框测试模块。"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from src.gui.dialogs.creator_monitor_dialog import CreatorMonitorDialog
from src.models.creator import Creator, CreatorStats
from src.services.creator import CreatorManager
from src.services.scanner import VideoScanner

@pytest.fixture
def mock_creator_manager():
    """创建模拟的创作者管理器。"""
    manager = Mock(spec=CreatorManager)
    
    # 模拟创作者数据
    creator1 = Mock(spec=Creator)
    creator1.id = "creator1"
    creator1.name = "测试创作者1"
    creator1.platforms = {"YouTube": "channel1"}
    creator1.stats = CreatorStats(
        total_videos=100,
        downloaded_videos=50,
        total_duration=3600,
        total_size=1024*1024*1024,
        sync_status="已同步"
    )
    
    creator2 = Mock(spec=Creator)
    creator2.id = "creator2"
    creator2.name = "测试创作者2"
    creator2.platforms = {"Bilibili": "12345"}
    creator2.stats = CreatorStats(
        total_videos=200,
        downloaded_videos=150,
        total_duration=7200,
        total_size=2*1024*1024*1024,
        sync_status="同步中"
    )
    
    manager.search_creators.return_value = [creator1, creator2]
    manager.get_creator.side_effect = lambda id: {
        "creator1": creator1,
        "creator2": creator2
    }.get(id)
    
    return manager

@pytest.fixture
def mock_video_scanner():
    """创建模拟的视频扫描器。"""
    scanner = Mock(spec=VideoScanner)
    return scanner

def test_init(qtbot, mock_creator_manager, mock_video_scanner):
    """测试对话框初始化。"""
    dialog = CreatorMonitorDialog(mock_creator_manager, mock_video_scanner)
    qtbot.addWidget(dialog)
    
    # 检查标题
    assert dialog.windowTitle() == "创作者监控"
    
    # 检查平台选择
    assert dialog.platform_combo.count() == 6
    assert dialog.platform_combo.currentText() == "全部平台"
    
    # 检查表格
    assert dialog.table.columnCount() == 8
    assert dialog.table.rowCount() == 2
    
    # 检查第一行数据
    assert dialog.table.item(0, 0).text() == "creator1"
    assert dialog.table.item(0, 1).text() == "测试创作者1"
    assert dialog.table.item(0, 2).text() == "YouTube"
    assert dialog.table.item(0, 3).text() == "100"
    assert dialog.table.item(0, 4).text() == "50"
    assert dialog.table.item(0, 5).text() == str(timedelta(seconds=3600))
    assert dialog.table.item(0, 6).text() == "1.0 GB"
    assert dialog.table.item(0, 7).text() == "已同步"

def test_sync_creators(qtbot, mock_creator_manager, mock_video_scanner):
    """测试同步创作者。"""
    dialog = CreatorMonitorDialog(mock_creator_manager, mock_video_scanner)
    qtbot.addWidget(dialog)
    
    # 触发同步
    dialog._sync_creators()
    
    # 验证调用
    mock_video_scanner.scan_creators.assert_called_once_with(None)
    assert mock_creator_manager.search_creators.call_count == 2  # 初始化 + 同步后刷新

def test_platform_filter(qtbot, mock_creator_manager, mock_video_scanner):
    """测试平台筛选。"""
    dialog = CreatorMonitorDialog(mock_creator_manager, mock_video_scanner)
    qtbot.addWidget(dialog)
    
    # 切换平台
    dialog.platform_combo.setCurrentText("YouTube")
    
    # 验证搜索调用
    mock_creator_manager.search_creators.assert_called_with("", "YouTube")

def test_context_menu(qtbot, mock_creator_manager, mock_video_scanner, monkeypatch):
    """测试右键菜单。"""
    dialog = CreatorMonitorDialog(mock_creator_manager, mock_video_scanner)
    qtbot.addWidget(dialog)
    
    # 模拟确认框返回Yes
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    
    # 触发删除操作
    dialog._delete_creator("creator1")
    
    # 验证删除调用
    mock_creator_manager.delete_creator.assert_called_once_with("creator1")
    
def test_update_stats(qtbot, mock_creator_manager, mock_video_scanner):
    """测试统计信息更新。"""
    dialog = CreatorMonitorDialog(mock_creator_manager, mock_video_scanner)
    qtbot.addWidget(dialog)
    
    # 修改统计信息
    creator = mock_creator_manager.get_creator("creator1")
    creator.stats.total_videos = 150
    creator.stats.downloaded_videos = 75
    
    # 触发更新
    dialog._update_stats()
    
    # 验证更新后的数据
    assert dialog.table.item(0, 3).text() == "150"
    assert dialog.table.item(0, 4).text() == "75" 