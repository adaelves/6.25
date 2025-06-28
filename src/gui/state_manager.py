"""GUI状态管理器模块。

负责管理和同步GUI组件的状态。
实现了状态变化的线程安全处理和UI更新。
"""

import threading
import logging
from typing import Set, Dict, Any, Optional
from enum import Enum, auto
from PySide6.QtWidgets import QWidget, QPushButton, QProgressBar, QLineEdit
from PySide6.QtCore import Signal, QObject

logger = logging.getLogger(__name__)

class DownloadState(Enum):
    """下载状态枚举。"""
    PAUSED = auto()   # 暂停
    RUNNING = auto()  # 运行中
    STOPPED = auto()  # 停止
    ERROR = auto()    # 错误
    COMPLETED = auto() # 完成

class StateManager(QObject):
    """状态管理器。
    
    管理下载器的状态和相关UI组件的同步。
    
    Signals:
        state_changed: 当状态发生改变时发出
        progress_updated: 当进度更新时发出
        error_occurred: 当发生错误时发出
    """
    
    state_changed = Signal(DownloadState, DownloadState)  # 旧状态, 新状态
    progress_updated = Signal(float, str)  # 进度值, 状态消息
    error_occurred = Signal(str)  # 错误消息
    
    def __init__(self):
        """初始化状态管理器。"""
        super().__init__()
        
        # 初始化状态
        self._state = DownloadState.STOPPED
        self._progress = 0.0
        self._status_message = ""
        
        # 线程锁
        self._state_lock = threading.Lock()
        self._progress_lock = threading.Lock()
        
        # 关联的UI组件
        self._linked_widgets: Set[QWidget] = set()
        
        # 组件状态映射
        self._widget_states: Dict[DownloadState, Dict[str, Any]] = {
            DownloadState.PAUSED: {
                'download_btn': {'enabled': True, 'text': '继续'},
                'cancel_btn': {'enabled': True, 'text': '取消'},
                'pause_btn': {'enabled': False, 'text': '暂停'},
                'progress_bar': {'enabled': False},
                'url_input': {'enabled': False}
            },
            DownloadState.RUNNING: {
                'download_btn': {'enabled': False, 'text': '下载'},
                'cancel_btn': {'enabled': True, 'text': '取消'},
                'pause_btn': {'enabled': True, 'text': '暂停'},
                'progress_bar': {'enabled': True},
                'url_input': {'enabled': False}
            },
            DownloadState.STOPPED: {
                'download_btn': {'enabled': True, 'text': '下载'},
                'cancel_btn': {'enabled': False, 'text': '取消'},
                'pause_btn': {'enabled': False, 'text': '暂停'},
                'progress_bar': {'enabled': False},
                'url_input': {'enabled': True}
            },
            DownloadState.ERROR: {
                'download_btn': {'enabled': True, 'text': '重试'},
                'cancel_btn': {'enabled': False, 'text': '取消'},
                'pause_btn': {'enabled': False, 'text': '暂停'},
                'progress_bar': {'enabled': False},
                'url_input': {'enabled': True}
            },
            DownloadState.COMPLETED: {
                'download_btn': {'enabled': True, 'text': '下载'},
                'cancel_btn': {'enabled': False, 'text': '取消'},
                'pause_btn': {'enabled': False, 'text': '暂停'},
                'progress_bar': {'enabled': False},
                'url_input': {'enabled': True}
            }
        }
    
    def link_widget(self, widget: QWidget, widget_id: str) -> None:
        """关联UI组件。
        
        Args:
            widget: 要关联的组件
            widget_id: 组件标识
        """
        widget.setObjectName(widget_id)
        self._linked_widgets.add(widget)
        self._update_widget_state(widget, self._state)
        
    def unlink_widget(self, widget: QWidget) -> None:
        """取消关联UI组件。
        
        Args:
            widget: 要取消关联的组件
        """
        self._linked_widgets.discard(widget)
        
    def set_state(self, new_state: DownloadState) -> None:
        """设置新状态。
        
        Args:
            new_state: 新状态
        """
        with self._state_lock:
            if new_state == self._state:
                return
                
            old_state = self._state
            self._state = new_state
            
            # 更新UI
            self._update_ui(old_state, new_state)
            
            # 发出信号
            self.state_changed.emit(old_state, new_state)
            
            logger.debug(f"状态变更: {old_state.name} -> {new_state.name}")
            
    def get_state(self) -> DownloadState:
        """获取当前状态。
        
        Returns:
            DownloadState: 当前状态
        """
        with self._state_lock:
            return self._state
            
    def update_progress(self, progress: float, message: str) -> None:
        """更新进度信息。
        
        Args:
            progress: 进度值(0-1)
            message: 状态消息
        """
        with self._progress_lock:
            self._progress = progress
            self._status_message = message
            
            # 发出信号
            self.progress_updated.emit(progress, message)
            
    def report_error(self, error: str) -> None:
        """报告错误。
        
        Args:
            error: 错误消息
        """
        self.set_state(DownloadState.ERROR)
        self.error_occurred.emit(error)
        logger.error(f"下载错误: {error}")
        
    def _update_ui(self, old_state: DownloadState, new_state: DownloadState) -> None:
        """更新UI组件状态。
        
        Args:
            old_state: 旧状态
            new_state: 新状态
        """
        for widget in self._linked_widgets:
            self._update_widget_state(widget, new_state)
            
    def _update_widget_state(self, widget: QWidget, state: DownloadState) -> None:
        """更新单个组件状态。
        
        Args:
            widget: 要更新的组件
            state: 目标状态
        """
        widget_id = widget.objectName()
        if not widget_id:
            return
            
        # 获取组件状态配置
        state_config = self._widget_states.get(state, {}).get(widget_id)
        if not state_config:
            return
            
        # 更新组件属性
        for prop, value in state_config.items():
            if prop == 'enabled':
                widget.setEnabled(value)
            elif prop == 'text' and isinstance(widget, QPushButton):
                widget.setText(value)
            elif prop == 'value' and isinstance(widget, QProgressBar):
                widget.setValue(value)
            elif prop == 'readonly' and isinstance(widget, QLineEdit):
                widget.setReadOnly(value)
                
        # 强制重绘
        widget.update() 