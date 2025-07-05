"""样式定义模块"""

MAC_STYLE = """
QWidget {
    font-family: -apple-system, BlinkMacSystemFont;
    font-size: 13px;
}

QMainWindow, QDialog {
    background: #F6F6F6;
    border-radius: 10px;
}

QLineEdit, QComboBox {
    border: 1px solid #D0D0D0;
    border-radius: 6px;
    padding: 6px 12px;
    background: white;
    min-height: 28px;
}

QPushButton {
    background: #007AFF;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 80px;
}

QPushButton:hover {
    background: #0062CC;
}

QProgressBar {
    border: 1px solid #D0D0D0;
    border-radius: 6px;
    height: 20px;
    text-align: center;
}

QProgressBar::chunk {
    background: #007AFF;
    border-radius: 5px;
}

QListWidget {
    background: white;
    border: 1px solid #D0D0D0;
    border-radius: 6px;
    padding: 4px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(resources/icons/down-arrow.png);
}

QDialog {
    background: white;
}

QLabel {
    color: #333333;
}

QLabel[title="true"] {
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 10px;
}
""" 