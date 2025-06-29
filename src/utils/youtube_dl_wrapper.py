"""YouTube下载器封装。

提供对youtube-dl的增强封装。
"""

import logging
import os
import sys
import subprocess
import shutil
import platform
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.request import urlretrieve

from ..exceptions import ProcessError

logger = logging.getLogger(__name__)

class YoutubeDLWrapper:
    """YouTube下载器封装。
    
    提供以下功能：
    1. HDR元数据保留
    2. 跨平台支持
    3. 自动安装依赖
    4. 错误处理
    
    Attributes:
        exiftool_path: exiftool路径
        temp_dir: 临时目录
    """
    
    # exiftool下载地址
    EXIFTOOL_URLS = {
        'Windows': 'https://exiftool.org/exiftool-12.60.zip',
        'Darwin': 'https://exiftool.org/Image-ExifTool-12.60.dmg',
        'Linux': 'https://exiftool.org/Image-ExifTool-12.60.tar.gz'
    }
    
    def __init__(self):
        """初始化下载器。"""
        self.temp_dir = tempfile.mkdtemp()
        self.exiftool_path = self._get_exiftool_path()
        
    def _get_exiftool_path(self) -> str:
        """获取exiftool路径。
        
        Returns:
            str: exiftool路径
            
        Raises:
            ProcessError: 获取失败
        """
        try:
            # 检查是否已安装
            exiftool_path = shutil.which('exiftool')
            if exiftool_path:
                return exiftool_path
                
            # 获取系统信息
            system = platform.system()
            if system not in self.EXIFTOOL_URLS:
                raise ProcessError(f"Unsupported system: {system}")
                
            # 下载exiftool
            url = self.EXIFTOOL_URLS[system]
            archive_path = os.path.join(
                self.temp_dir,
                os.path.basename(url)
            )
            
            logger.info(f"Downloading exiftool from {url}")
            urlretrieve(url, archive_path)
            
            # 解压并安装
            if system == 'Windows':
                return self._install_windows(archive_path)
            elif system == 'Darwin':
                return self._install_macos(archive_path)
            else:
                return self._install_linux(archive_path)
                
        except Exception as e:
            logger.error(f"Failed to get exiftool: {e}")
            raise ProcessError(f"Failed to get exiftool: {e}")
            
    def _install_windows(self, archive_path: str) -> str:
        """Windows平台安装。
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            str: exiftool路径
        """
        try:
            # 解压zip
            import zipfile
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(self.temp_dir)
                
            # 重命名exe
            exe_path = os.path.join(self.temp_dir, 'exiftool(-k).exe')
            new_path = os.path.join(self.temp_dir, 'exiftool.exe')
            os.rename(exe_path, new_path)
            
            return new_path
            
        except Exception as e:
            logger.error(f"Failed to install on Windows: {e}")
            raise ProcessError(f"Failed to install on Windows: {e}")
            
    def _install_macos(self, archive_path: str) -> str:
        """macOS平台安装。
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            str: exiftool路径
        """
        try:
            # 挂载dmg
            mount_point = os.path.join(self.temp_dir, 'dmg')
            os.makedirs(mount_point, exist_ok=True)
            
            subprocess.run([
                'hdiutil', 'attach',
                archive_path,
                '-mountpoint', mount_point
            ], check=True)
            
            # 安装pkg
            pkg_path = os.path.join(mount_point, 'ExifTool.pkg')
            subprocess.run([
                'installer', '-pkg',
                pkg_path,
                '-target', '/'
            ], check=True)
            
            # 卸载dmg
            subprocess.run([
                'hdiutil', 'detach',
                mount_point
            ], check=True)
            
            return '/usr/local/bin/exiftool'
            
        except Exception as e:
            logger.error(f"Failed to install on macOS: {e}")
            raise ProcessError(f"Failed to install on macOS: {e}")
            
    def _install_linux(self, archive_path: str) -> str:
        """Linux平台安装。
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            str: exiftool路径
        """
        try:
            # 解压tar.gz
            subprocess.run([
                'tar', 'xzf',
                archive_path,
                '-C', self.temp_dir
            ], check=True)
            
            # 编译安装
            src_dir = os.path.join(
                self.temp_dir,
                'Image-ExifTool-12.60'
            )
            subprocess.run([
                'perl', 'Makefile.PL'
            ], cwd=src_dir, check=True)
            
            subprocess.run([
                'make', 'install'
            ], cwd=src_dir, check=True)
            
            return '/usr/local/bin/exiftool'
            
        except Exception as e:
            logger.error(f"Failed to install on Linux: {e}")
            raise ProcessError(f"Failed to install on Linux: {e}")
            
    def preserve_hdr(
        self,
        input_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """保留HDR元数据。
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径，可选
            
        Returns:
            str: 输出文件路径
            
        Raises:
            ProcessError: 处理失败
        """
        try:
            # 生成输出路径
            if not output_path:
                filename = os.path.basename(input_path)
                output_path = os.path.join(
                    os.path.dirname(input_path),
                    f"hdr_{filename}"
                )
                
            # 复制文件
            shutil.copy2(input_path, output_path)
            
            # 保留HDR元数据
            subprocess.run([
                self.exiftool_path,
                '-TagsFromFile', input_path,
                '-ColorPrimaries',
                '-TransferCharacteristics',
                '-MatrixCoefficients',
                '-MasteringDisplayColorVolume',
                '-MaxContentLightLevel',
                '-MaxFrameAverageLightLevel',
                output_path
            ], check=True)
            
            # 删除备份文件
            backup_path = f"{output_path}_original"
            if os.path.exists(backup_path):
                os.remove(backup_path)
                
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to preserve HDR metadata: {e}")
            raise ProcessError(f"Failed to preserve HDR metadata: {e}")
            
    def __del__(self):
        """清理临时文件。"""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up temp dir: {e}") 