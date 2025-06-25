class DownloadCanceled(Exception):
    """用户取消下载异常。
    
    当用户主动取消下载时抛出此异常。
    下载器会负责清理临时文件和释放资源。
    """
    pass 