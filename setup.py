#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器安装脚本。

编译Qt资源文件并安装依赖。
"""

import os
import subprocess
from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

def compile_resources():
    """编译Qt资源文件。"""
    # 检查pyside6-rcc是否可用
    try:
        subprocess.run(['pyside6-rcc', '--version'], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: pyside6-rcc not found. Please install PySide6 first.")
        return False
        
    # 编译资源文件
    src_dir = os.path.join('src', 'resources')
    qrc_file = os.path.join(src_dir, 'icons.qrc')
    py_file = os.path.join(src_dir, 'icons_rc.py')
    
    try:
        subprocess.run(
            ['pyside6-rcc', '-o', py_file, qrc_file],
            check=True
        )
        print(f"Successfully compiled {qrc_file} to {py_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error compiling resources: {e}")
        return False

class CustomDevelopCommand(develop):
    """自定义开发模式命令。"""
    
    def run(self):
        compile_resources()
        develop.run(self)

class CustomInstallCommand(install):
    """自定义安装命令。"""
    
    def run(self):
        compile_resources()
        install.run(self)

setup(
    name="video-downloader",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A video downloader with GUI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/video-downloader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "video-downloader=src.main:main",
        ],
    },
    cmdclass={
        'develop': CustomDevelopCommand,
        'install': CustomInstallCommand,
    }
) 