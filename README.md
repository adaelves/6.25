# 视频下载器

一个带有图形界面的视频下载器，支持多个平台。

## 功能特点

- 支持多个视频平台（YouTube、Twitter、Bilibili等）
- 图形用户界面，操作简单
- 支持下载进度显示
- 支持代理设置
- 支持视频质量选择
- 支持断点续传
- 支持并发下载
- 支持速度限制

## 安装要求

- Python 3.10 或更高版本
- 依赖包（见 requirements.txt）

## 安装方法

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/video-downloader.git
cd video-downloader
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 安装程序：
```bash
pip install -e .
```

## 使用方法

1. 启动程序：
```bash
video-downloader
```

2. 在程序界面中：
   - 输入视频URL
   - 点击"开始下载"按钮
   - 等待下载完成

## 配置说明

- 下载目录：默认为 `downloads` 目录
- 代理设置：默认使用 `http://127.0.0.1:7890`
- 视频质量：默认选择 1080p
- 输出格式：默认为 MP4

## 开发说明

- 使用 MVVM 架构
- 使用 PySide6 构建界面
- 使用 yt-dlp 下载 YouTube 视频
- 使用 logging 模块记录日志
- 支持插件式扩展

## 许可证

MIT License 